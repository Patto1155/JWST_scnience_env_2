"""
Build a JWST universe table, source-level high-z candidates, and evidence artifacts.

This script:
- Loads all registered datasets from the database
- Computes masked global and quadrant statistics plus 100-bin histograms
- Detects unique red-band sources instead of ranking raw bright pixels
- Flags source-level F090W/F444W dropout candidates
- Generates field overviews, color diagnostics, and evidence bundles
- Writes results to research_output/*.json and updates memory/report markdowns
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core_api.db import SessionLocal
from core_api.models.datasets import Dataset
from discovery.proposal_channels import (
    BLUE_FILTER,
    MID_FILTER,
    REFERENCE_FILTER,
    attach_proposal_metadata,
    build_portfolio_shortlist,
    build_measurement_status_by_filter,
    compute_completeness_score,
    compute_target_color_baseline,
    is_measured_status,
    summarize_proposal_channels,
)
from tools.jwst.fits_loader import load_fits_bundle
from tools.jwst.footprints import (
    MIN_USEFUL_OVERLAP,
    overlap_fraction,
)
from tools.jwst.photometry import compute_color_index, extract_photometry
from tools.jwst.dropout import dropout_upper_limit_ratio, physical_flux
from astropy.wcs.utils import proj_plane_pixel_scales
from tools.jwst.source_detection import detect_sources
from tools.jwst.visualization import (
    candidate_evidence_bundle,
    render_field_overview,
    save_color_diagnostic_plot,
)


RESEARCH_DIR = Path("research_output")
VISUALS_DIR = RESEARCH_DIR / "visuals"
SOURCE_CATALOG_DIR = RESEARCH_DIR / "source_catalogs"
RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
VISUALS_DIR.mkdir(parents=True, exist_ok=True)
SOURCE_CATALOG_DIR.mkdir(parents=True, exist_ok=True)
APERTURE_RADII = [2, 3, 5]


def _masked_image(bundle: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
    """Return an image with invalid pixels masked as NaN plus the validity mask."""
    image = np.asarray(bundle["sci"], dtype=float)
    valid_mask = np.asarray(bundle["validity_mask"], dtype=bool)
    return np.where(valid_mask, image, np.nan), valid_mask


def quadrant_slices(shape):
    """Return slice tuples for four quadrants of an image."""
    h, w = shape[-2], shape[-1]
    mid_h, mid_w = h // 2, w // 2
    return [
        (slice(0, mid_h), slice(0, mid_w)),
        (slice(0, mid_h), slice(mid_w, w)),
        (slice(mid_h, h), slice(0, mid_w)),
        (slice(mid_h, h), slice(mid_w, w)),
    ]


def _summary_stats(values: np.ndarray) -> Dict[str, float]:
    """Compute robust summary stats on a 1D vector of valid values."""
    if values.size == 0:
        return {
            "mean": 0.0,
            "median": 0.0,
            "std": 0.0,
            "min": 0.0,
            "max": 0.0,
        }
    return {
        "mean": float(np.nanmean(values)),
        "median": float(np.nanmedian(values)),
        "std": float(np.nanstd(values)),
        "min": float(np.nanmin(values)),
        "max": float(np.nanmax(values)),
    }


def compute_quadrant_stats(masked_image: np.ndarray) -> List[Dict[str, float]]:
    """Compute stats for each quadrant using only valid pixels."""
    stats = []
    for slc in quadrant_slices(masked_image.shape):
        quad_values = masked_image[slc]
        quad_valid = quad_values[np.isfinite(quad_values)]
        stats.append(_summary_stats(quad_valid))
    return stats


def _histogram(values: np.ndarray, bins: int = 100) -> Dict[str, Any]:
    """Create a histogram summary for valid values."""
    if values.size == 0:
        return {"bin_centers": [], "counts": [], "total_pixels": 0}

    counts, bin_edges = np.histogram(values, bins=bins)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    return {
        "bin_centers": [float(item) for item in bin_centers],
        "counts": [int(item) for item in counts],
        "total_pixels": int(values.size),
    }


def build_universe_table(datasets: List[Dataset]) -> List[Dict[str, Any]]:
    """Compute masked image summaries for every dataset."""
    entries = []
    for ds in datasets:
        name = ds.name
        meta = ds.meta_data or {}
        try:
            bundle = load_fits_bundle(name)
        except Exception as exc:
            entries.append(
                {
                    "name": name,
                    "target": meta.get("target"),
                    "filter": meta.get("filter"),
                    "proposal_id": meta.get("proposal_id"),
                    "error": f"load_failed: {exc}",
                }
            )
            continue

        masked_image, valid_mask = _masked_image(bundle)
        valid_values = masked_image[np.isfinite(masked_image)]
        stats = _summary_stats(valid_values)

        entries.append(
            {
                "name": name,
                "target": meta.get("target") or bundle.get("target"),
                "filter": meta.get("filter") or bundle.get("filter"),
                "instrument": meta.get("instrument") or bundle.get("instrument"),
                "proposal_id": meta.get("proposal_id"),
                "file_path": meta.get("file_path") or bundle.get("file_path"),
                "shape": list(masked_image.shape),
                "summary_stats": stats,
                "percentile_25": float(np.nanpercentile(valid_values, 25))
                if valid_values.size
                else 0.0,
                "percentile_75": float(np.nanpercentile(valid_values, 75))
                if valid_values.size
                else 0.0,
                "quadrant_stats": compute_quadrant_stats(masked_image),
                "histogram": _histogram(valid_values, bins=100),
                "valid_pixel_count": int(np.sum(valid_mask)),
                "coverage_fraction": float(np.sum(valid_mask) / valid_mask.size),
            }
        )
    return entries


def _group_entries_by_target(
    entries: List[Dict[str, Any]],
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """Group universe-table entries by target and filter."""
    grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for entry in entries:
        if entry.get("error"):
            continue
        target = entry.get("target") or "UNKNOWN"
        filt = str(entry.get("filter") or "").upper()
        grouped[target][filt].append(entry)
    return grouped


MIN_FOOTPRINT_OVERLAP = MIN_USEFUL_OVERLAP


def _product_rank(dataset_name: str) -> int:
    """Rank calibration product flavors, preferring resampled i2d mosaics."""
    name = dataset_name.lower()
    if "i2d" in name:
        return 3
    if "_crf" in name:
        return 2
    if "_cal" in name:
        return 1
    return 0


def _overlap_with_reference(reference_bundle: Dict[str, Any], candidate_name: str) -> float:
    """Measure how much of the reference footprint a candidate dataset covers."""
    try:
        candidate_bundle = load_fits_bundle(candidate_name)
    except Exception:
        return 0.0
    return overlap_fraction(reference_bundle, candidate_bundle)


def _pick_overlapping_dataset(
    entries: Dict[str, List[Dict[str, Any]]],
    filter_name: str,
    reference_name: str,
    reference_bundle: Dict[str, Any],
) -> Tuple[Optional[str], float]:
    """Pick the dataset for one filter that actually overlaps the reference sky.

    Candidates are ranked by measured footprint overlap first and product
    quality second, so a lexicographic accident can never select an exposure on
    a different NIRCam module.
    """
    scored: List[Tuple[float, int, str]] = []
    for item in entries.get(filter_name, []):
        name = item["name"]
        overlap = _overlap_with_reference(reference_bundle, name)
        if overlap < MIN_FOOTPRINT_OVERLAP:
            continue
        scored.append((overlap, _product_rank(name), name))

    if not scored:
        return None, 0.0

    best = max(scored)
    return best[2], best[0]


def _load_catalog_sources(catalog_path: str) -> List[Dict[str, Any]]:
    """Load source list from a detect_sources JSON catalog."""
    path = Path(catalog_path)
    return json.loads(path.read_text(encoding="utf-8")).get("sources", [])


def _map_for_reference(
    grouped_entries: Dict[str, List[Dict[str, Any]]],
    reference_name: str,
) -> Tuple[Dict[str, str], Dict[str, float]]:
    """Resolve every filter against one candidate reference dataset."""
    dataset_map: Dict[str, str] = {REFERENCE_FILTER: reference_name}
    overlap_by_filter: Dict[str, float] = {REFERENCE_FILTER: 1.0}

    try:
        reference_bundle = load_fits_bundle(reference_name)
    except Exception:
        return dataset_map, overlap_by_filter

    for filter_name in grouped_entries.keys():
        if filter_name == REFERENCE_FILTER:
            continue
        chosen, overlap = _pick_overlapping_dataset(
            grouped_entries, filter_name, reference_name, reference_bundle
        )
        if chosen:
            dataset_map[filter_name] = chosen
            overlap_by_filter[filter_name] = overlap
    return dataset_map, overlap_by_filter


def _build_target_dataset_map(
    grouped_entries: Dict[str, List[Dict[str, Any]]],
) -> Tuple[Dict[str, str], Dict[str, float]]:
    """Resolve one dataset per filter that shares sky with the reference filter.

    The reference filter anchors the selection and every other band is chosen by
    measured WCS footprint overlap against it. Which reference to anchor on is
    itself a choice: two exposures of the same field in the reference filter can
    differ in whether any blue exposure overlaps them at all. So each candidate
    reference is scored by how much of the required-band coverage it actually
    buys, and the best one wins.

    A filter with no overlapping exposure is left out of the map entirely rather
    than paired with disjoint sky, so downstream code sees a missing band
    instead of a fabricated non-detection.
    """
    reference_options = [item["name"] for item in grouped_entries.get(REFERENCE_FILTER, [])]
    if not reference_options:
        return {}, {}

    required = [BLUE_FILTER, MID_FILTER]
    best_map: Dict[str, str] = {}
    best_overlap: Dict[str, float] = {}
    best_key: Tuple[int, float, int, str] = (-1, -1.0, -1, "")

    for reference_name in reference_options:
        dataset_map, overlap_by_filter = _map_for_reference(grouped_entries, reference_name)
        required_bands = sum(1 for filt in required if filt in dataset_map)
        required_overlap = sum(overlap_by_filter.get(filt, 0.0) for filt in required)
        key = (
            required_bands,
            required_overlap,
            _product_rank(reference_name),
            reference_name,
        )
        if key > best_key:
            best_key = key
            best_map = dataset_map
            best_overlap = overlap_by_filter

    return best_map, best_overlap


def _dataset_position_from_source(
    source: Dict[str, Any],
    dataset_name: str,
) -> Tuple[float, float]:
    """Resolve source coordinates in a target dataset using the source sky center."""
    if dataset_name == source["reference_dataset"]:
        return float(source["position"]["x"]), float(source["position"]["y"])

    bundle = load_fits_bundle(dataset_name)
    wcs = bundle.get("wcs")
    sky_center = source.get("sky_center") or {}
    if wcs is None or sky_center.get("ra") is None or sky_center.get("dec") is None:
        return float(source["position"]["x"]), float(source["position"]["y"])

    x, y = wcs.world_to_pixel_values(float(sky_center["ra"]), float(sky_center["dec"]))
    return float(x), float(y)


def _quality_flags(
    reference_r3: Dict[str, Any],
    blue_r3: Optional[Dict[str, Any]],
    mid_r3: Optional[Dict[str, Any]],
    edge_distance_px: float,
) -> List[str]:
    """Generate conservative quality flags for source-level candidates."""
    flags: List[str] = []
    if float(reference_r3.get("coverage_fraction") or 0.0) < 0.9:
        flags.append("low_coverage")
        if int(reference_r3.get("pixels_in_aperture") or 0) <= 0:
            flags.append("reference_offchip")
        else:
            flags.append("reference_unmeasured_low_coverage")
    if reference_r3.get("snr") is None or float(reference_r3["snr"]) < 5.0:
        flags.append("low_snr")
    if float(reference_r3.get("background_subtracted_flux") or 0.0) <= 0.0:
        flags.append("nonpositive_reference_flux")
    if float(edge_distance_px or 0.0) < 16.0:
        flags.append("near_edge")
    if blue_r3 is not None and float(blue_r3.get("coverage_fraction") or 0.0) < 0.9:
        flags.append("low_blue_coverage")
        if int(blue_r3.get("pixels_in_aperture") or 0) <= 0:
            flags.append("blue_offchip")
        else:
            flags.append("blue_unmeasured_low_coverage")
    if mid_r3 is not None and float(mid_r3.get("coverage_fraction") or 0.0) < 0.9:
        flags.append("low_mid_coverage")
        if int(mid_r3.get("pixels_in_aperture") or 0) <= 0:
            flags.append("mid_offchip")
        else:
            flags.append("mid_unmeasured_low_coverage")
    return list(dict.fromkeys(flags))


def _ratio_from_fluxes(blue_flux: float, red_flux: float) -> Optional[float]:
    """Compute a dropout ratio while tolerating non-detections in the blue band."""
    if red_flux is None or red_flux <= 0:
        return None
    return float(max(blue_flux or 0.0, 0.0) / red_flux)


def _color_point(candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build one F090-F200 vs F200-F444 point when all bands are valid."""
    photometry = candidate.get("photometry_by_filter") or {}
    required = [BLUE_FILTER, MID_FILTER, REFERENCE_FILTER]
    if not all(filt in photometry for filt in required):
        return None

    values = {}
    for filt in required:
        r3 = photometry[filt]["3"]
        flux = physical_flux(r3)
        coverage = float(r3.get("coverage_fraction") or 0.0)
        if flux is None or flux <= 0 or coverage < 0.9:
            return None
        values[filt] = flux

    c1 = compute_color_index(values[BLUE_FILTER], values[MID_FILTER])
    c2 = compute_color_index(values[MID_FILTER], values[REFERENCE_FILTER])
    if c1.get("color_index") is None or c2.get("color_index") is None:
        return None

    return {
        "source_id": candidate["source_id"],
        "x_color": float(c1["color_index"]),
        "y_color": float(c2["color_index"]),
        "highlight": bool(
            candidate.get("ratio_f090_f444") is not None and candidate["ratio_f090_f444"] < 0.05
        ),
    }


def _clip_unit_interval(value: float) -> float:
    """Clamp a value to the inclusive [0, 1] interval."""
    return float(max(0.0, min(1.0, float(value))))


def _validation_summary(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Score one candidate for shortlist triage and record falsification clues."""
    aperture_checks = list(candidate.get("aperture_checks") or [])
    ratio = candidate.get("ratio_f090_f444")
    red_snr = candidate.get("red_snr_r3")
    coverage = float(candidate.get("coverage_fraction_r3") or 0.0)
    edge_distance = float(candidate.get("edge_distance_px") or 0.0)
    photometry_by_filter = candidate.get("photometry_by_filter") or {}
    measurement_status_by_filter = candidate.get("measurement_status_by_filter") or {}
    completeness_score = float(candidate.get("completeness_score") or 0.0)
    novelty_score = float(candidate.get("novelty_score") or 0.0)
    falsification_flags = list(candidate.get("falsification_flags") or [])
    disqualifying_flags = list(candidate.get("disqualifying_flags") or [])
    blue_r3 = (photometry_by_filter.get(BLUE_FILTER) or {}).get("3") or {}
    mid_r3 = (photometry_by_filter.get(MID_FILTER) or {}).get("3") or {}

    blue_snr = blue_r3.get("snr")
    mid_flux = physical_flux(mid_r3) or 0.0
    mid_coverage = float(mid_r3.get("coverage_fraction") or 0.0) if mid_r3 else 0.0
    dropout_fraction = (
        float(np.mean([1.0 if item.get("dropout_lt_0p05") else 0.0 for item in aperture_checks]))
        if aperture_checks
        else 0.0
    )

    # An unmeasured blue band cannot supply evidence for a dropout. Zeroing the
    # ratio and aperture-consistency terms here stops an off-detector aperture
    # from scoring a perfect break on 55% of the total weight.
    blue_evidence_available = is_measured_status(
        str(measurement_status_by_filter.get(BLUE_FILTER) or "")
    )
    if not blue_evidence_available:
        ratio_score = 0.0
        aperture_score = 0.0
    else:
        ratio_score = 0.0 if ratio is None else _clip_unit_interval((0.2 - float(ratio)) / 0.2)
        aperture_score = dropout_fraction
    snr_score = 0.0 if red_snr is None else _clip_unit_interval((float(red_snr) - 5.0) / 10.0)
    coverage_score = _clip_unit_interval((coverage - 0.8) / 0.2)
    edge_score = _clip_unit_interval((edge_distance - 16.0) / 24.0)
    blue_status = measurement_status_by_filter.get(BLUE_FILTER)
    reference_status = measurement_status_by_filter.get(REFERENCE_FILTER)
    if blue_status and not is_measured_status(blue_status):
        blue_nondetection_score = 0.0
    elif blue_snr is None:
        blue_nondetection_score = 0.4
    else:
        blue_nondetection_score = _clip_unit_interval((5.0 - float(blue_snr)) / 6.0)

    weighted_score = (
        0.30 * ratio_score
        + 0.25 * aperture_score
        + 0.20 * snr_score
        + 0.15 * blue_nondetection_score
        + 0.05 * coverage_score
        + 0.05 * edge_score
    )
    weighted_score = 0.80 * weighted_score + 0.10 * completeness_score + 0.10 * novelty_score

    keep_reasons: List[str] = []
    reject_reasons: List[str] = []

    if not blue_evidence_available:
        reject_reasons.append("f090_f444_ratio_undefined_blue_unmeasured")
    elif ratio is not None and float(ratio) < 0.05:
        keep_reasons.append("f090_f444_ratio_below_0p05")
    else:
        reject_reasons.append("f090_f444_ratio_not_dropout_like")

    if not blue_evidence_available:
        reject_reasons.append("dropout_undefined_blue_unmeasured")
    elif dropout_fraction >= 1.0:
        keep_reasons.append("dropout_stable_across_all_apertures")
    elif dropout_fraction >= 0.67:
        keep_reasons.append("dropout_stable_across_most_apertures")
    else:
        reject_reasons.append("dropout_not_stable_across_apertures")

    if red_snr is not None and float(red_snr) >= 8.0:
        keep_reasons.append("reference_snr_ge_8")
    elif red_snr is None or float(red_snr) < 5.0:
        reject_reasons.append("reference_snr_below_5")

    if blue_snr is not None and float(blue_snr) <= 2.0:
        keep_reasons.append("blue_band_not_significantly_detected")
    elif blue_snr is not None and float(blue_snr) > 2.0:
        reject_reasons.append("blue_band_detected_above_snr_2")

    if coverage >= 0.95:
        keep_reasons.append("reference_coverage_ge_0p95")
    elif coverage < 0.9:
        reject_reasons.append("reference_coverage_below_0p9")

    if edge_distance >= 32.0:
        keep_reasons.append("well_inside_detector_footprint")
    elif edge_distance < 16.0:
        reject_reasons.append("source_near_detector_edge")

    if mid_r3:
        if mid_flux > 0.0 and mid_coverage >= 0.9:
            keep_reasons.append("mid_band_flux_measured")
        elif mid_coverage < 0.5:
            reject_reasons.append("mid_band_coverage_too_low")

    if not is_measured_status(str(measurement_status_by_filter.get(MID_FILTER) or "")):
        reject_reasons.append("mid_filter_not_measured")

    if completeness_score >= 0.95:
        keep_reasons.append("required_filters_measured")
    elif completeness_score < 0.67:
        reject_reasons.append("required_filters_incomplete")

    if novelty_score >= 0.6:
        keep_reasons.append("novel_candidate_signature")

    for flag in falsification_flags:
        reject_reasons.append(f"falsification:{flag}")

    validation_status = "reject"
    if not reject_reasons and weighted_score >= 0.8:
        validation_status = "strong_keep"
    elif weighted_score >= 0.65 and not reject_reasons:
        validation_status = "keep"
    elif weighted_score >= 0.5:
        validation_status = "review"

    if reference_status and not is_measured_status(reference_status):
        validation_status = "reject"
        reject_reasons.append("reference_filter_not_measured")
    elif blue_status and not is_measured_status(blue_status):
        if validation_status in {"strong_keep", "keep"}:
            validation_status = "review"
        reject_reasons.append("blue_filter_not_measured")

    if disqualifying_flags:
        if validation_status == "strong_keep":
            validation_status = "review"
        elif validation_status == "keep":
            validation_status = "review"
        if validation_status == "review" and "reference_unmeasured" in disqualifying_flags:
            validation_status = "reject"
        reject_reasons.extend(f"disqualifying:{flag}" for flag in disqualifying_flags)

    reject_reasons = list(dict.fromkeys(reject_reasons))
    keep_reasons = list(dict.fromkeys(keep_reasons))

    return {
        "validation_score": float(weighted_score),
        "validation_status": validation_status,
        "dropout_aperture_fraction": float(dropout_fraction),
        "blue_snr_r3": float(blue_snr) if blue_snr is not None else None,
        "mid_flux_r3": float(mid_flux),
        "mid_coverage_r3": float(mid_coverage),
        "completeness_score": float(completeness_score),
        "novelty_score": float(novelty_score),
        "keep_reasons": keep_reasons,
        "reject_reasons": reject_reasons,
        "component_scores": {
            "dropout_ratio": float(ratio_score),
            "aperture_consistency": float(aperture_score),
            "reference_snr": float(snr_score),
            "blue_nondetection": float(blue_nondetection_score),
            "coverage": float(coverage_score),
            "edge_distance": float(edge_score),
            "completeness": float(completeness_score),
            "novelty": float(novelty_score),
        },
    }


def _analyze_target_sources(
    target: str,
    grouped_entries: Dict[str, List[Dict[str, Any]]],
    *,
    anomalous_dataset_names: set[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """Detect red sources, measure colors, and generate target-level artifacts."""
    dataset_map, footprint_overlap = _build_target_dataset_map(grouped_entries)
    reference_dataset = dataset_map.get(REFERENCE_FILTER)
    blue_dataset = dataset_map.get(BLUE_FILTER)
    mid_dataset = dataset_map.get(MID_FILTER)

    if not reference_dataset or not blue_dataset:
        # Without an overlapping blue exposure there is no dropout test to run.
        return [], [], {}

    bundle_by_filter: Dict[str, Dict[str, Any]] = {}
    for filter_name in {BLUE_FILTER, MID_FILTER, REFERENCE_FILTER}:
        dataset_name = dataset_map.get(filter_name)
        if dataset_name:
            bundle_by_filter[filter_name] = load_fits_bundle(dataset_name)

    catalog_result = detect_sources(
        image_data=reference_dataset,
        top_n=200,
        border_margin=16,
        output_dir=str(SOURCE_CATALOG_DIR),
        output_prefix=f"{target}_sources",
    )
    sources = _load_catalog_sources(catalog_result["catalog_path"])

    all_sources: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []

    for source in sources:
        source_id = int(source["source_id"])
        ref_x = float(source["x"])
        ref_y = float(source["y"])
        sky_center = {
            "ra": source.get("ra"),
            "dec": source.get("dec"),
        }

        per_filter: Dict[str, Dict[str, Any]] = {}
        per_dataset: Dict[str, Dict[str, Any]] = {}
        for filter_name, dataset_name in dataset_map.items():
            if filter_name not in {BLUE_FILTER, MID_FILTER, REFERENCE_FILTER}:
                continue

            if dataset_name == reference_dataset:
                dataset_x, dataset_y = ref_x, ref_y
            else:
                bundle = bundle_by_filter[filter_name]
                if (
                    bundle.get("wcs") is not None
                    and sky_center["ra"] is not None
                    and sky_center["dec"] is not None
                ):
                    dataset_x, dataset_y = bundle["wcs"].world_to_pixel_values(
                        float(sky_center["ra"]),
                        float(sky_center["dec"]),
                    )
                else:
                    continue

            bundle = bundle_by_filter[filter_name]
            reference_wcs = bundle_by_filter[REFERENCE_FILTER].get("wcs")
            if (
                reference_wcs is None
                or not reference_wcs.has_celestial
                or sky_center["ra"] is None
                or sky_center["dec"] is None
            ):
                # No shared sky coordinate means no cross-band measurement.
                continue
            reference_scale = float(
                np.sqrt(np.prod(proj_plane_pixel_scales(reference_wcs.celestial))) * 3600.0
            )
            if not np.isfinite(reference_scale) or reference_scale <= 0:
                continue

            aperture_results: Dict[str, Any] = {}
            for radius in APERTURE_RADII:
                aperture_results[str(radius)] = extract_photometry(
                    image_data=bundle,
                    ra_deg=float(sky_center["ra"]),
                    dec_deg=float(sky_center["dec"]),
                    aperture_radius_arcsec=float(radius) * reference_scale,
                    background_annulus_inner_radius_arcsec=6.0 * reference_scale,
                    background_annulus_outer_radius_arcsec=10.0 * reference_scale,
                )

            per_filter[filter_name] = aperture_results
            per_dataset[dataset_name] = aperture_results

        if REFERENCE_FILTER not in per_filter or BLUE_FILTER not in per_filter:
            continue

        reference_r3 = per_filter[REFERENCE_FILTER]["3"]
        blue_r3 = per_filter[BLUE_FILTER]["3"]
        mid_r3 = (per_filter.get(MID_FILTER) or {}).get("3") or {}
        ratio_r3 = dropout_upper_limit_ratio(blue_r3, reference_r3)

        aperture_checks = []
        all_apertures_dropout = True
        for radius in APERTURE_RADII:
            blue_measurement = per_filter[BLUE_FILTER][str(radius)]
            red_measurement = per_filter[REFERENCE_FILTER][str(radius)]
            ratio = dropout_upper_limit_ratio(blue_measurement, red_measurement)
            is_dropout = ratio is not None and ratio < 0.05
            aperture_checks.append(
                {
                    "radius": radius,
                    "f444_flux": physical_flux(red_measurement),
                    "f090_flux": physical_flux(blue_measurement),
                    "ratio_f090_f444": ratio,
                    "dropout_lt_0p05": is_dropout,
                }
            )
            all_apertures_dropout = all_apertures_dropout and is_dropout

        quality_flags = _quality_flags(
            reference_r3,
            blue_r3,
            mid_r3,
            float(source.get("edge_distance_px") or 0.0),
        )
        reference_flux_jy = physical_flux(reference_r3)
        blue_flux_jy = physical_flux(blue_r3)
        physical_ratio = ratio_r3

        measurement_status_by_filter = build_measurement_status_by_filter(
            per_filter, radius_key="3"
        )
        completeness_score = compute_completeness_score(
            measurement_status_by_filter,
            required_filters=[BLUE_FILTER, REFERENCE_FILTER, MID_FILTER],
        )

        valid_ratios = [
            item["ratio_f090_f444"]
            for item in aperture_checks
            if item["ratio_f090_f444"] is not None
        ]
        base_record = {
            "target": target,
            "source_id": source_id,
            "position": {"x": ref_x, "y": ref_y},
            "sky_center": sky_center,
            "reference_dataset": reference_dataset,
            "f444_dataset": reference_dataset,
            "f090_dataset": blue_dataset,
            "f200_dataset": mid_dataset,
            "f444_flux": reference_flux_jy,
            "flux_unit": "Jy",
            "selection_ratio_kind": "blue_2sigma_upper_limit_over_red_flux",
            "f090_flux": blue_flux_jy,
            "ratio_f090_f444": ratio_r3,
            "aperture_checks": aperture_checks,
            "all_apertures_dropout": all_apertures_dropout,
            "mean_ratio": float(np.mean(valid_ratios)) if valid_ratios else None,
            "red_snr_r3": reference_r3.get("snr"),
            "coverage_fraction": float(reference_r3["coverage_fraction"]),
            "coverage_fraction_r3": float(reference_r3["coverage_fraction"]),
            "edge_distance_px": float(source.get("edge_distance_px") or 0.0),
            "quality_flags": quality_flags,
            "measurement_status_by_filter": measurement_status_by_filter,
            "measured_filters": [
                filt
                for filt, status in measurement_status_by_filter.items()
                if is_measured_status(status)
            ],
            "unmeasured_filters": [
                filt
                for filt, status in measurement_status_by_filter.items()
                if not is_measured_status(status)
            ],
            "completeness_score": float(completeness_score),
            "footprint_overlap_by_filter": dict(footprint_overlap),
            "f444_flux_jy": reference_flux_jy,
            "f444_ab_magnitude": reference_r3.get("background_subtracted_magnitude"),
            "physical_ratio_f090_f444": physical_ratio,
            "photometry_by_filter": per_filter,
            "photometry_by_dataset": per_dataset,
            "screen_identity": "exploratory_proposal",
            "note": "Source-level JWST proposal candidate",
        }
        all_sources.append(base_record)

    color_baseline = compute_target_color_baseline(all_sources)
    for source in all_sources:
        proposal_metadata = attach_proposal_metadata(
            source,
            color_baseline=color_baseline,
            anomalous_dataset_names=anomalous_dataset_names,
        )
        source.update(proposal_metadata)
        source["validation"] = _validation_summary(source)
        source["validation_score"] = source["validation"]["validation_score"]
        source["validation_status"] = source["validation"]["validation_status"]
        source["keep_reasons"] = list(source["validation"]["keep_reasons"])
        source["reject_reasons"] = list(source["validation"]["reject_reasons"])
        source["note"] = (
            f"Source-level JWST proposal candidate via "
            f"{source.get('primary_channel') or 'no_primary_channel'}"
        )

        statuses = source.get("measurement_status_by_filter") or {}
        reference_status = statuses.get(REFERENCE_FILTER)
        blue_status = statuses.get(BLUE_FILTER)
        if (
            source.get("proposal_channels")
            and is_measured_status(str(reference_status or ""))
            # A dropout requires an actual blue measurement. Without one the
            # ratio is a division by an off-detector zero, not a non-detection.
            and is_measured_status(str(blue_status or ""))
            and physical_flux(
                (source["photometry_by_filter"][REFERENCE_FILTER] or {}).get("3") or {}
            )
            is not None
            and physical_flux((source["photometry_by_filter"][BLUE_FILTER] or {}).get("3") or {})
            is not None
            and float(source.get("f444_flux") or 0.0) > 0.0
        ):
            candidates.append(dict(source))

    candidates_by_flux = sorted(
        candidates,
        key=lambda item: float(item.get("f444_flux") or 0.0),
        reverse=True,
    )
    for rank, candidate in enumerate(candidates_by_flux, start=1):
        candidate["rank_by_reference_flux"] = rank

    candidates.sort(
        key=lambda item: (
            float(item.get("validation_score") or 0.0),
            float(item.get("completeness_score") or 0.0),
            float(item.get("novelty_score") or 0.0),
            float(item.get("f444_flux") or 0.0),
        ),
        reverse=True,
    )
    top_ranked = build_portfolio_shortlist(candidates, max_candidates=10)

    evidence_records: List[Dict[str, Any]] = []
    comparison_datasets = [name for name in [blue_dataset, mid_dataset] if name]
    for rank, candidate in enumerate(top_ranked, start=1):
        evidence = candidate_evidence_bundle(
            reference_dataset=reference_dataset,
            comparison_datasets=comparison_datasets,
            catalog_path=catalog_result["catalog_path"],
            source_id=int(candidate["source_id"]),
            cutout_size=64,
            aperture_radii=APERTURE_RADII,
            output_dir=str(VISUALS_DIR),
            output_prefix=f"{target}_source_{candidate['source_id']}_rank_{rank}",
        )
        candidate["artifacts"] = evidence["artifacts"]
        candidate["evidence_output_path"] = evidence["output_path"]
        candidate["evidence_sidecar_path"] = evidence["sidecar_path"]
        candidate["rank_by_validation_score"] = rank
        evidence_records.append(candidate)

    overview = render_field_overview(
        image_data=reference_dataset,
        catalog_path=catalog_result["catalog_path"],
        highlight_source_ids=[item["source_id"] for item in candidates[:25]],
        top_n=50,
        output_dir=str(VISUALS_DIR),
        output_prefix=f"{target}_field",
    )

    color_points = []
    for source in all_sources:
        point = _color_point(source)
        if point is not None:
            color_points.append(point)

    color_plot_path = save_color_diagnostic_plot(
        points=color_points,
        output_path=str(VISUALS_DIR / f"{target}_color_diagnostic.png"),
        target=target,
    )

    target_summary = {
        "target": target,
        "reference_dataset": reference_dataset,
        "blue_dataset": blue_dataset,
        "mid_dataset": mid_dataset,
        "catalog_path": catalog_result["catalog_path"],
        "segmentation_overlay_path": catalog_result["segmentation_overlay_path"],
        "field_overview_path": overview["output_path"],
        "color_diagnostic_path": color_plot_path,
        "source_count": catalog_result["source_count"],
        "candidate_count": len(candidates),
        "shortlist_count": len(top_ranked),
        "proposal_channel_counts": (
            summarize_proposal_channels(candidates, top_ranked).get("candidate_channel_counts")
            if candidates
            else {}
        ),
    }
    return candidates, evidence_records, target_summary


def detect_anomalies(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Identify statistical outliers and non-Gaussian brightness patterns."""
    means = [entry["summary_stats"]["mean"] for entry in entries if entry.get("summary_stats")]
    stds = [entry["summary_stats"]["std"] for entry in entries if entry.get("summary_stats")]
    if not means or not stds:
        return []

    mean_med, mean_std = np.median(means), np.std(means)
    std_med, std_spread = np.median(stds), np.std(stds)

    anomalies = []
    for entry in entries:
        stats = entry.get("summary_stats") or {}
        if not stats:
            continue

        mean_val = stats.get("mean")
        std_val = stats.get("std")
        flags = []
        if mean_std > 0 and abs(mean_val - mean_med) > 3 * mean_std:
            flags.append(f"mean_outlier | mean={mean_val:.4e} vs median {mean_med:.4e}")
        if std_spread > 0 and abs(std_val - std_med) > 3 * std_spread:
            flags.append(f"std_outlier | std={std_val:.4e} vs median {std_med:.4e}")

        max_val = stats.get("max")
        if max_val is not None and std_val > 0:
            tail_threshold = max(100 * std_val, 1000 * max(abs(mean_val), 1e-6))
            if (max_val - mean_val) > tail_threshold:
                flags.append("heavy_tail / potential cosmic ray")

        if flags:
            anomalies.append(
                {
                    "name": entry["name"],
                    "target": entry.get("target"),
                    "filter": entry.get("filter"),
                    "flags": flags,
                    "mean": mean_val,
                    "std": std_val,
                    "max": max_val,
                }
            )
    return anomalies


def write_json(path: Path, data: Any):
    """Write a JSON artifact with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    print(f"Wrote {path}")


def update_memory(entries, highz, anomalies, target_summaries, shortlist):
    """Create a concise research memory log."""
    lines = [
        "# Research Memory\n",
        "## Universe Table snapshot\n",
        f"- Datasets analyzed: {len(entries)}",
        f"- High-z source candidates: {len(highz)}",
        f"- Shortlist candidates: {len(shortlist)}",
        f"- Anomaly flags: {len(anomalies)}\n",
    ]

    if target_summaries:
        lines.append("### Target evidence products\n")
        for summary in target_summaries:
            lines.append(
                f"- {summary['target']}: {summary['candidate_count']} candidates, shortlist={summary.get('shortlist_count', 0)}, "
                f"overview={summary['field_overview_path']}, colors={summary['color_diagnostic_path']}"
            )
        lines.append("")

    if shortlist:
        lines.append("### Shortlist\n")
        for candidate in shortlist[:5]:
            snr_text = (
                f"{float(candidate['red_snr_r3']):.2f}"
                if candidate.get("red_snr_r3") is not None
                else "None"
            )
            lines.append(
                f"- {candidate['target']} source {candidate['source_id']} at "
                f"(x={candidate['position']['x']:.0f}, y={candidate['position']['y']:.0f}): "
                f"F090/F444={str(candidate.get('ratio_f090_f444'))}, "
                f"score={float(candidate.get('validation_score') or 0.0):.3f}, "
                f"SNR={snr_text}, "
                f"channel={candidate.get('primary_channel')}, "
                f"completeness={float(candidate.get('completeness_score') or 0.0):.2f}"
            )
        lines.append("")

    if anomalies:
        lines.append("### Anomalies\n")
        for anomaly in anomalies[:5]:
            lines.append(
                f"- {anomaly['name']} ({anomaly.get('target')} {anomaly.get('filter')}): "
                f"{'; '.join(anomaly['flags'])}"
            )
        lines.append("")

    path = RESEARCH_DIR / "RESEARCH_MEMORY.md"
    path.write_text("\n".join(lines))
    print(f"Wrote {path}")


def update_report(entries, highz, anomalies, target_summaries, shortlist):
    """Create a brief research report with rerun instructions."""
    lines = [
        "# Research Report\n",
        "This run built a masked Universe Table from registered JWST datasets and applied source-level dropout screening.\n",
        "## Key Findings",
        f"- Catalogued {len(entries)} datasets across programs (JADES 1180, CEERS 1345, SMACS 2736).",
        f"- High-z source candidates: {len(highz)} flagged by source-level F090W/F444W dropouts.",
        f"- Review shortlist: {len(shortlist)} highest-scoring candidates after falsification-aware triage.",
        f"- Anomaly flags: {len(anomalies)} statistical outliers/non-Gaussian tails.\n",
    ]

    if target_summaries:
        lines.append("### Visual evidence products")
        for summary in target_summaries:
            lines.append(
                f"- {summary['target']}: "
                f"overview={summary['field_overview_path']}, "
                f"segmentation={summary['segmentation_overlay_path']}, "
                f"colors={summary['color_diagnostic_path']}, "
                f"shortlist={summary.get('shortlist_count', 0)}"
            )
        lines.append("")

    if shortlist:
        lines.append("### Shortlist highlights")
        for candidate in shortlist[:5]:
            lines.append(
                f"- {candidate['target']} source {candidate['source_id']} at "
                f"(x={candidate['position']['x']:.0f}, y={candidate['position']['y']:.0f}): "
                f"F090/F444={str(candidate.get('ratio_f090_f444'))}, "
                f"score={float(candidate.get('validation_score') or 0.0):.3f}, "
                f"status={candidate.get('validation_status')}, "
                f"channel={candidate.get('primary_channel')}, "
                f"rejections={', '.join(candidate.get('reject_reasons') or []) or 'none'}"
            )
        lines.append("")

    if anomalies:
        lines.append("### Notable anomalies")
        for anomaly in anomalies[:5]:
            lines.append(
                f"- {anomaly['name']} ({anomaly.get('target')} {anomaly.get('filter')}): "
                f"{'; '.join(anomaly['flags'])}"
            )
        lines.append("")

    lines.extend(
        [
            "## Rerun instructions",
            "- Ensure API is running: `python run_api.py`",
            "- Rebuild Universe Table: `python discovery/build_universe_table.py`",
            "- Review shortlist: `research_output/highz_shortlist.json`",
            '- View strict-ready datasets: `curl "http://localhost:8000/datasets/?limit=20&strict_ready=true"`',
            "",
        ]
    )

    path = RESEARCH_DIR / "RESEARCH_REPORT.md"
    path.write_text("\n".join(lines))
    print(f"Wrote {path}")


def main():
    """Rebuild source-level research outputs from registered JWST datasets."""
    db = SessionLocal()
    try:
        datasets = db.query(Dataset).all()
    finally:
        db.close()

    entries = build_universe_table(datasets)
    grouped = _group_entries_by_target(entries)
    anomalies = detect_anomalies(entries)
    anomalous_dataset_names = {str(item.get("name") or "") for item in anomalies}

    highz_candidates: List[Dict[str, Any]] = []
    validation_top: List[Dict[str, Any]] = []
    target_summaries: List[Dict[str, Any]] = []
    for target, grouped_entries in grouped.items():
        target_candidates, target_top, summary = _analyze_target_sources(
            target,
            grouped_entries,
            anomalous_dataset_names=anomalous_dataset_names,
        )
        highz_candidates.extend(target_candidates)
        validation_top.extend(target_top)
        if summary:
            target_summaries.append(summary)

    shortlist = build_portfolio_shortlist(highz_candidates, max_candidates=25)
    proposal_summary = summarize_proposal_channels(highz_candidates, shortlist)

    write_json(RESEARCH_DIR / "universe_table_summary.json", entries)
    write_json(RESEARCH_DIR / "highz_candidates.json", highz_candidates)
    write_json(RESEARCH_DIR / "highz_shortlist.json", shortlist)
    write_json(RESEARCH_DIR / "highz_validation_top10.json", validation_top)
    write_json(RESEARCH_DIR / "anomaly_catalog.json", anomalies)
    write_json(RESEARCH_DIR / "proposal_channel_summary.json", proposal_summary)
    update_memory(entries, highz_candidates, anomalies, target_summaries, shortlist)
    update_report(entries, highz_candidates, anomalies, target_summaries, shortlist)


if __name__ == "__main__":
    main()
