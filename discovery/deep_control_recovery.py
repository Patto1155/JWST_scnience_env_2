"""Freeze geometry-selected real controls before evaluating deep F444W pixels.

The existing footprint was targeted at three previous failures. All additional
catalogue controls in its union are selected by geometry alone, with one image
per conservative sky group. This is conditional recovery, not survey completeness.
Native-grid classifier scores are deliberately not transferred to these mosaics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
from astropy.stats import sigma_clipped_stats
from astropy.wcs.utils import proj_plane_pixel_scales
from photutils.segmentation import SourceCatalog, deblend_sources, detect_sources
from scipy.ndimage import distance_transform_edt

from data_pipeline.followup_data import MANIFEST, verify
from data_pipeline.original_images import verify_image
from data_pipeline.research_sources import load_manifest
from discovery.deep_reference_comparison import APERTURE, blank_noise, load_deep_cutout, measurement
from discovery.real_validation import grouped_jades, match_sky
from tools.jwst.fits_loader import load_fits_bundle
from tools.jwst.footprints import sky_to_pixel

REFERENCE_CSV = Path("data_sources/pilot/jades_dr4_reference.csv")
SEED_OBSERVATIONS = {"20074794", "20083087", "20189546"}
MATCH_RADIUS_ARCSEC = 0.2
DETECTION_SIGMA = 5.0
NATIVE_MIN_PIXELS = 5


def json_hash(value: dict | list) -> str:
    normalized = json.loads(json.dumps(value, allow_nan=False))
    return hashlib.sha256(json.dumps(normalized, sort_keys=True, allow_nan=False).encode()).hexdigest()


def grid_area(bundle: dict) -> float:
    """Local projected pixel area; detector sensitivity is not matched by area alone."""
    return float(np.prod(proj_plane_pixel_scales(bundle["wcs"]) * 3600))


def minimum_pixels(original_area: float, current_area: float) -> int:
    if not np.isfinite([original_area, current_area]).all() or min(original_area, current_area) <= 0:
        raise ValueError("Pixel areas must be finite and positive")
    return max(1, int(math.ceil(NATIVE_MIN_PIXELS * original_area / current_area - 1e-10)))


def covered_margin(bundle: dict, references: list[dict]) -> list[float | None]:
    """Conservative valid circular footprint using inscribed pixel-scale distance.

    Invalid pixels and array exterior both count as boundaries. This deliberately
    requires more margin than the photometry annulus, avoiding edge-biased trials.
    Pixel amplitudes never influence reference selection.
    """
    scales = proj_plane_pixel_scales(bundle["wcs"]) * 3600
    distance = distance_transform_edt(np.pad(bundle["validity_mask"], 1))[1:-1, 1:-1]
    result = []
    for ref in references:
        xy = sky_to_pixel(bundle, ref["ra_deg"], ref["dec_deg"])
        if xy is None:
            result.append(None)
            continue
        x, y = xy
        ix, iy = int(round(x)), int(round(y))
        if not (0 <= ix < distance.shape[1] and 0 <= iy < distance.shape[0]):
            result.append(None)
            continue
        # Subtract a full pixel for centre quantization and finite pixel footprints.
        result.append(float(max(0, distance[iy, ix] - 1) * min(scales)))
    return result


def load_inputs(input_dir: Path, original: Path) -> tuple[dict, list[tuple[dict, dict]]]:
    original_manifest = Path(__file__).resolve().parents[1] / "data_sources/original_images.json"
    pinned = [p for p in json.loads(original_manifest.read_text())["images"] if p["product_filename"] == original.name]
    if len(pinned) != 1:
        raise ValueError("Original comparison image absent from pinned input inventory")
    verify_image(original, pinned[0])
    original_bundle = load_fits_bundle(str(original.resolve()))
    verify(original)
    products = load_manifest(MANIFEST)["sources"][1]["products"]
    images = []
    for product in sorted(products, key=lambda p: p["filename"]):
        bundle, provenance = load_deep_cutout(input_dir / product["filename"])
        receipt = provenance["receipt"]
        if receipt["bytes"] != product["expected_bytes"] or receipt["sha256"] != product["sha256"]:
            raise ValueError("Deep image disagrees with pinned public manifest")
        images.append((bundle, provenance))
    return original_bundle, images


def freeze(input_dir: Path, original: Path, reference_csv: Path = REFERENCE_CSV) -> dict:
    original_bundle, images = load_inputs(input_dir, original)
    references, groups = grouped_jades(reference_csv)
    original_area = grid_area(original_bundle)
    margin_arcsec = max(APERTURE["background_annulus_outer_radius_arcsec"], 16 * math.sqrt(original_area))
    margins = [covered_margin(bundle, references) for bundle, _ in images]
    original_margins = covered_margin(original_bundle, references)
    selected = []
    for i, reference in enumerate(references):
        eligible = [(m[i], provenance["filename"]) for m, (_, provenance) in zip(margins, images)
                    if m[i] is not None and m[i] >= margin_arcsec]
        if not eligible:
            continue
        # Maximum geometry margin first, then filename, without measuring brightness/depth.
        primary = sorted(eligible, key=lambda p: (-p[0], p[1]))[0]
        seeded = any(identifier.rsplit("_", 1)[-1] in SEED_OBSERVATIONS
                     for identifier in reference["observation_ids"])
        selected.append({**reference, "role": "previously_selected_failure_seed" if seeded else "additional_geometry_control",
                         "primary_deep_image": primary[1], "available_deep_images": sorted(p[1] for p in eligible),
                         "original_covered": original_margins[i] is not None and original_margins[i] >= margin_arcsec})
    inputs = [{"filename": p["filename"], "bytes": p["receipt"]["bytes"], "sha256": p["receipt"]["sha256"],
               "pixel_area_arcsec2": grid_area(b), "contributors_sha256": json_hash(sorted(p["contributors"])),
               "contributor_count": len(p["contributors"])} for b, p in images]
    result = {
        "schema_version": 1,
        "selection_contract": "All A/B/C grouped JADES refs with complete valid angular margin in union of three fixed targeted cutouts; no SCI-amplitude, detection or redshift cut",
        "targeted_footprint_limitation": "Cutouts centered on three historical high-z nonrecoveries; additional controls are blind to pixel outcomes but footprint is biased",
        "reference_csv_sha256": hashlib.sha256(reference_csv.read_bytes()).hexdigest(),
        "reference_grouping": groups,
        "required_valid_margin_arcsec": margin_arcsec,
        "original_pixel_area_arcsec2": original_area,
        "original_input": {"filename": original.name, **verify(original)},
        "deep_inputs": inputs,
        "references": sorted(selected, key=lambda r: r["sky_group_id"]),
        "counts_by_role_and_cohort": dict(sorted(Counter(r["role"] + "/" + r["cohort"] for r in selected).items())),
        "control_catalogue_is_frozen_before_pixel_evaluation": True,
    }
    result["frozen_content_sha256"] = json_hash(result)
    return result


def detections(bundle: dict, npixels: int, margin_arcsec: float) -> list[dict]:
    image, valid = bundle["sci"], bundle["validity_mask"]
    _, median, sigma = sigma_clipped_stats(image[valid], sigma=3)
    if not np.isfinite(sigma) or sigma <= 0:
        return []
    values = np.where(valid, image - median, 0)
    segment = detect_sources(values, threshold=DETECTION_SIGMA * sigma, npixels=npixels, mask=~valid)
    if segment is None:
        return []
    # An unexpected deblender failure is not silently interpreted as no sources.
    segment = deblend_sources(values, segment, npixels=npixels, progress_bar=False)
    catalog = SourceCatalog(values, segment)
    output = []
    for row in catalog:
        x, y = float(row.xcentroid), float(row.ycentroid)
        if not np.isfinite([x, y]).all():
            continue
        point = bundle["wcs"].pixel_to_world(x, y)
        output.append({"x": x, "y": y, "ra_deg": float(point.ra.deg), "dec_deg": float(point.dec.deg)})
    margins = covered_margin(bundle, output)
    return [row for row, margin in zip(output, margins) if margin is not None and margin >= margin_arcsec]


def summarize(rows: list[dict], key: str) -> list[dict]:
    output = []
    strata = sorted({(r["reference"]["role"], r["reference"]["cohort"]) for r in rows})
    for role, cohort in strata:
        selected = [r for r in rows if r["reference"]["role"] == role and r["reference"]["cohort"] == cohort]
        eligible = [r for r in selected if r.get(key) is not None]
        counts = Counter(r[key]["status"] for r in eligible)
        output.append({"role": role, "cohort": cohort, "groups_in_deep_union": len(selected),
                       "covered_group_denominator": len(eligible), "matched": counts["matched"],
                       "ambiguous": counts["ambiguous"], "not_detected": counts["not_detected"],
                       "conditional_recovery_fraction": counts["matched"] / len(eligible) if eligible else None})
    return output


def evaluate(frozen: dict, input_dir: Path, original: Path, reference_csv: Path = REFERENCE_CSV) -> dict:
    if json_hash(frozen) != json_hash(freeze(input_dir, original, reference_csv)):
        raise ValueError("Frozen cohort/provenance differs from deterministic geometry policy")
    original_bundle, images = load_inputs(input_dir, original)
    area = frozen["original_pixel_area_arcsec2"]
    margin = frozen["required_valid_margin_arcsec"]
    original_refs = [r for r in frozen["references"] if r["original_covered"]]
    original_detections = detections(original_bundle, NATIVE_MIN_PIXELS, margin)
    original_matches = dict(zip([r["source_id"] for r in original_refs], match_sky(original_refs, original_detections, MATCH_RADIUS_ARCSEC)))
    rows, image_reports = [], []
    original_contributor = original.name.replace("_i2d.fits", "_rate.fits")
    for bundle, provenance in images:
        references = [r for r in frozen["references"] if r["primary_deep_image"] == provenance["filename"]]
        # Include other-image primary references in association ambiguity checks.
        covered_refs = [r for r in frozen["references"] if provenance["filename"] in r["available_deep_images"]]
        legacy = detections(bundle, NATIVE_MIN_PIXELS, margin)
        area_pixels = minimum_pixels(area, grid_area(bundle))
        area_matched = detections(bundle, area_pixels, margin)
        legacy_map = dict(zip([r["source_id"] for r in covered_refs], match_sky(covered_refs, legacy, MATCH_RADIUS_ARCSEC)))
        area_map = dict(zip([r["source_id"] for r in covered_refs], match_sky(covered_refs, area_matched, MATCH_RADIUS_ARCSEC)))
        noise = blank_noise(bundle)
        image_reports.append({"filename": provenance["filename"], "legacy_min_pixels": NATIVE_MIN_PIXELS,
                              "angular_area_min_pixels": area_pixels, "legacy_detections": len(legacy),
                              "angular_area_detections": len(area_matched),
                              "original_in_contributors": original_contributor in provenance["contributors"],
                              "noise": {k: v for k, v in noise.items() if k not in {"samples_jy", "positions_pixels"}}})
        for reference in references:
            legacy_match, area_match = legacy_map[reference["source_id"]], area_map[reference["source_id"]]
            phot = measurement(bundle, ra_deg=reference["ra_deg"], dec_deg=reference["dec_deg"])
            phot["blank_scatter_snr_diagnostic"] = (phot["background_subtracted_flux_jy"] / noise["sigma_jy"]
                                                   if phot["background_subtracted_flux_jy"] is not None and noise["sigma_jy"] else None)
            rows.append({"reference": reference, "deep_legacy_detection": legacy_match,
                         "deep_angular_area_detection": area_match, "deep_aperture": phot,
                         "original_detection": original_matches.get(reference["source_id"]),
                         "original_aperture": measurement(original_bundle, ra_deg=reference["ra_deg"], dec_deg=reference["dec_deg"])
                         if reference["original_covered"] else None})
    shared = []
    for i, (_, first) in enumerate(images):
        for _, second in images[i+1:]:
            shared.append({"first": first["filename"], "second": second["filename"],
                           "shared_native_contributors": len(set(first["contributors"]) & set(second["contributors"]))})
    return {
        "schema_version": 1, "evidence_kind": "actual_public_pixels_geometry_frozen_conditional_controls",
        "frozen_catalogue_sha256": json_hash(frozen), "aperture_arcsec": APERTURE,
        "detector": {"sigma": DETECTION_SIGMA, "match_radius_arcsec": MATCH_RADIUS_ARCSEC,
                     "not_detected_status_meaning": "No detection centroid within matching radius; blends and shifted centroids can cause nonrecovery without absent source flux",
                     "angular_area_experiment": "Only minimum connected area matched; threshold noise/sampling/PSF remain different"},
        "image_reports": image_reports, "contributor_dependence": shared,
        "unique_source_groups": len(rows), "duplicate_images_not_pooled": True,
        "summaries": {k: summarize(rows, k) for k in ("original_detection", "deep_legacy_detection", "deep_angular_area_detection")},
        "rows": sorted(rows, key=lambda r: r["reference"]["sky_group_id"]),
        "limits": ["Targeted footprint, targeted spectroscopy and operational catalog labels prevent population completeness/contamination claims",
                   "Seed high-z failures remain separate from additional geometry controls; no additional robust high-z denominator may exist",
                   "Shared contributors and sky prevent treating cutouts as independent observations; each group has one geometry-chosen primary image",
                   "No native-grid classifier scores; conditional classifier rejection is not estimated",
                   "Blank-scatter SNR omits source Poisson and spatial-depth/model uncertainty; aperture SNR is not segmentation significance",
                   "Area-matched detection is a counterfactual operator sensitivity, not a PSF-matched or noise-equivalent experiment"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["freeze", "evaluate"])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--reference-csv", type=Path, default=REFERENCE_CSV)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if args.mode == "freeze":
            result = freeze(args.input, args.original, args.reference_csv)
            destination = args.frozen
        else:
            if args.output is None:
                parser.error("evaluate requires --output")
            result = evaluate(json.loads(args.frozen.read_text()), args.input, args.original, args.reference_csv)
            destination = args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
