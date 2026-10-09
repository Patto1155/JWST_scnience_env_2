"""JWST-specific visualization tools for candidate vetting."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.nddata import Cutout2D
from astropy.nddata.utils import NoOverlapError
import astropy.units as u

from tools.jwst.fits_loader import load_fits_bundle
from tools.jwst.photometry import compute_color_index, extract_photometry
from tools.jwst.flux_calibration import celestial_wcs, pixel_solid_angle_sr, ARCSEC2_TO_SR

EVIDENCE_SCHEMA_VERSION = 2


def _sanitize_name(value: str) -> str:
    """Convert arbitrary values into filesystem-safe output prefixes."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "jwst"


def _json_ready(value: Any) -> Any:
    """Convert numpy-heavy structures into JSON-safe values."""
    if isinstance(value, dict):
        return {key: _json_ready(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return value


def _normalize_image_for_display(
    image: np.ndarray,
    valid_mask: np.ndarray,
    lower_pct: float = 1.0,
    upper_pct: float = 99.5,
) -> np.ndarray:
    """Create an asinh-stretched display image using valid pixels only."""
    valid_values = image[valid_mask]
    if valid_values.size == 0:
        return np.zeros_like(image, dtype=float)

    vmin = float(np.nanpercentile(valid_values, lower_pct))
    vmax = float(np.nanpercentile(valid_values, upper_pct))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        vmax = vmin + 1.0

    clipped = np.clip(np.where(valid_mask, image, vmin), vmin, vmax)
    scaled = (clipped - vmin) / (vmax - vmin)
    return np.arcsinh(10.0 * scaled) / np.arcsinh(10.0)


def _load_catalog(catalog_path: str) -> Dict[str, Any]:
    """Load a JSON source catalog."""
    path = Path(catalog_path)
    if not path.exists():
        raise FileNotFoundError(f"Catalog not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_source_from_catalog(catalog_path: str, source_id: int) -> Dict[str, Any]:
    """Find one source entry in a JSON source catalog."""
    catalog = _load_catalog(catalog_path)
    for source in catalog.get("sources", []):
        if int(source.get("source_id")) == int(source_id):
            return source
    raise ValueError(f"source_id={source_id} not present in catalog {catalog_path}")


def _resolve_center(
    reference_bundle: Dict[str, Any],
    x: Optional[float],
    y: Optional[float],
    catalog_path: Optional[str],
    source_id: Optional[int],
) -> Tuple[float, float, Optional[SkyCoord], Optional[Dict[str, Any]]]:
    """Resolve reference pixel center and sky center from direct or catalog input."""
    source_entry = None
    if source_id is not None:
        if not catalog_path:
            raise ValueError("catalog_path is required when source_id is provided")
        source_entry = _resolve_source_from_catalog(catalog_path, source_id)
        if x is None:
            x = float(source_entry["x"])
        if y is None:
            y = float(source_entry["y"])

    if x is None or y is None:
        raise ValueError("Provide x/y or catalog_path + source_id")

    sky_center = None
    wcs = celestial_wcs(reference_bundle)
    if wcs is not None:
        try:
            sky_center = wcs.pixel_to_world(float(x), float(y))
        except Exception:
            sky_center = None

    return float(x), float(y), sky_center, source_entry


def _resolve_dataset_position(
    bundle: Dict[str, Any],
    sky_center: Optional[SkyCoord],
    fallback_x: float,
    fallback_y: float,
) -> Tuple[float, float]:
    """Resolve pixel coordinates in a dataset using WCS when available."""
    wcs = celestial_wcs(bundle)
    if sky_center is not None and wcs is not None:
        try:
            x, y = wcs.world_to_pixel(sky_center)
            return float(x), float(y)
        except Exception:
            pass
    return float(fallback_x), float(fallback_y)


def _cutout_for_bundle(
    bundle: Dict[str, Any],
    center_x: float,
    center_y: float,
    cutout_size: int,
) -> Dict[str, Any]:
    """Build aligned cutouts for science, error, weight, and mask arrays."""
    position = (float(center_x), float(center_y))
    size = (int(cutout_size), int(cutout_size))
    wcs = bundle.get("wcs")

    def make_cutout(data, fill_value):
        if data is None:
            return None
        try:
            return Cutout2D(
                np.asarray(data, dtype=float),
                position=position,
                size=size,
                wcs=wcs,
                mode="partial",
                fill_value=fill_value,
            )
        except NoOverlapError:
            return None

    sci_cutout = make_cutout(bundle["sci"], np.nan)
    if sci_cutout is None:
        empty_shape = (int(cutout_size), int(cutout_size))
        return {
            "sci": np.full(empty_shape, np.nan, dtype=float),
            "err": np.full(empty_shape, np.nan, dtype=float),
            "wht": np.zeros(empty_shape, dtype=float),
            "validity_mask": np.zeros(empty_shape, dtype=bool),
            "center_x": (float(cutout_size) - 1.0) / 2.0,
            "center_y": (float(cutout_size) - 1.0) / 2.0,
            "dataset_x": float(position[0]),
            "dataset_y": float(position[1]),
            "off_chip": True,
        }

    err_cutout = make_cutout(bundle.get("err"), np.nan)
    wht_cutout = make_cutout(bundle.get("wht"), 0.0)
    mask_cutout = make_cutout(bundle.get("validity_mask").astype(float), 0.0)
    cutout_center = sci_cutout.to_cutout_position(position)

    return {
        "sci": sci_cutout.data,
        "err": err_cutout.data if err_cutout is not None else None,
        "wht": wht_cutout.data if wht_cutout is not None else None,
        "validity_mask": (mask_cutout.data > 0.5) if mask_cutout is not None else np.isfinite(sci_cutout.data),
        "center_x": float(cutout_center[0]),
        "center_y": float(cutout_center[1]),
        "dataset_x": float(position[0]),
        "dataset_y": float(position[1]),
        "off_chip": False,
    }


def _quality_flags(reference_r3: Dict[str, Any], source_entry: Optional[Dict[str, Any]]) -> List[str]:
    """Generate conservative quality flags for a candidate."""
    flags: List[str] = []
    if float(reference_r3.get("coverage_fraction") or 0.0) < 0.9:
        flags.append("low_coverage")
    snr = reference_r3.get("snr")
    if snr is None or float(snr) < 5.0:
        flags.append("low_snr")
    flux_jy = reference_r3.get("background_subtracted_flux_jy")
    if reference_r3.get("calibration_status") != "calibrated":
        flags.append("uncalibrated_reference")
    if reference_r3.get("measurement_status") in {"off_image", "no_valid_pixels"}:
        flags.append("unmeasured_reference")
    if reference_r3.get("background_status") != "measured":
        flags.append("missing_reference_background")
    if flux_jy is not None and float(flux_jy) <= 0:
        flags.append("nonpositive_reference_flux")
    if source_entry and float(source_entry.get("edge_distance_px") or 0.0) < 16.0:
        flags.append("near_edge")
    return flags


def _add_aperture_overlay(
    ax,
    center_x: float,
    center_y: float,
    aperture_radius: float,
    annulus_inner: float,
    annulus_outer: float,
) -> None:
    """Overlay the source center, aperture, and annulus on an axes."""
    ax.axvline(center_x, color="cyan", linestyle="--", linewidth=0.8, alpha=0.7)
    ax.axhline(center_y, color="cyan", linestyle="--", linewidth=0.8, alpha=0.7)
    ax.add_patch(plt.Circle((center_x, center_y), aperture_radius, fill=False, color="lime", linewidth=1.0))
    ax.add_patch(plt.Circle((center_x, center_y), annulus_inner, fill=False, color="orange", linewidth=0.8, linestyle=":"))
    ax.add_patch(plt.Circle((center_x, center_y), annulus_outer, fill=False, color="orange", linewidth=0.8, linestyle=":"))


def candidate_evidence_bundle(
    reference_dataset: str,
    comparison_datasets: List[str],
    x: float = None,
    y: float = None,
    catalog_path: Optional[str] = None,
    source_id: Optional[int] = None,
    cutout_size: int = 64,
    aperture_radii: List[int] = None,
    background_annulus_inner_radius: float = 6.0,
    background_annulus_outer_radius: float = 10.0,
    output_dir: str = "visuals",
    output_prefix: Optional[str] = None,
    strict_data: Optional[bool] = None,
    aperture_radius_arcsec: Optional[float] = None,
    background_annulus_inner_radius_arcsec: Optional[float] = None,
    background_annulus_outer_radius_arcsec: Optional[float] = None,
) -> Dict[str, Any]:
    """Render calibrated evidence using common sky apertures where WCS permits.

    ``aperture_radius_arcsec`` sets radius key 3; other radius keys scale with
    it. Defaults derive angular sizes from the actual reference-grid pixel area.
    Colours are Jy aperture diagnostics, with no filter PSF correction.
    """
    del strict_data  # strictness is enforced by the sandbox calling conventions

    aperture_radii = list(aperture_radii or [2, 3, 5])
    if 3 not in aperture_radii:
        raise ValueError("Evidence requires radius key 3 for its reference summary")
    science_datasets = [reference_dataset]
    for dataset_name in comparison_datasets:
        if dataset_name not in science_datasets:
            science_datasets.append(dataset_name)

    reference_bundle = load_fits_bundle(reference_dataset)
    ref_x, ref_y, sky_center, source_entry = _resolve_center(
        reference_bundle,
        x=x,
        y=y,
        catalog_path=catalog_path,
        source_id=source_id,
    )

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    prefix = output_prefix or _sanitize_name(
        f"{reference_dataset}_{source_id if source_id is not None else f'x{int(ref_x)}_y{int(ref_y)}'}"
    )
    panel_path = output_root / f"{prefix}_evidence.png"
    sidecar_path = output_root / f"{prefix}_evidence.json"

    # Match every filter on the sky using angular radii derived from the actual
    # reference grid. Keys remain the original reference-pixel radii for callers.
    ref_wcs = celestial_wcs(reference_bundle)
    angular_options = {}
    if aperture_radius_arcsec is not None or background_annulus_inner_radius_arcsec is not None or background_annulus_outer_radius_arcsec is not None:
        if ref_wcs is None or sky_center is None:
            raise ValueError("Angular evidence apertures require reference celestial WCS")
    if ref_wcs is not None and sky_center is not None:
        scale = float(np.sqrt(pixel_solid_angle_sr(ref_wcs, np.asarray(ref_x), np.asarray(ref_y)) / ARCSEC2_TO_SR))
        angular_scale = float(aperture_radius_arcsec) / 3 if aperture_radius_arcsec is not None else scale
        angular_options = {
            "aperture_radius_arcsec": float(aperture_radius_arcsec) if aperture_radius_arcsec is not None else 3 * scale,
            "background_annulus_inner_radius_arcsec": float(background_annulus_inner_radius_arcsec) if background_annulus_inner_radius_arcsec is not None else background_annulus_inner_radius * angular_scale,
            "background_annulus_outer_radius_arcsec": float(background_annulus_outer_radius_arcsec) if background_annulus_outer_radius_arcsec is not None else background_annulus_outer_radius * angular_scale,
        }
    input_fingerprints = []
    for dataset in science_datasets:
        source = load_fits_bundle(dataset)
        file_path = source.get("file_path")
        stat = Path(file_path).stat() if file_path and Path(file_path).exists() else None
        input_fingerprints.append({"dataset": dataset, "path": file_path,
                                   "size": stat.st_size if stat else None,
                                   "mtime_ns": stat.st_mtime_ns if stat else None})
    request = {"reference_dataset": reference_dataset, "comparison_datasets": comparison_datasets,
               "x": ref_x, "y": ref_y, "source_id": source_id, "cutout_size": cutout_size,
               "aperture_radii": aperture_radii,
               "background_annulus_inner_radius": background_annulus_inner_radius,
               "background_annulus_outer_radius": background_annulus_outer_radius,
               "angular_options": angular_options, "input_fingerprints": input_fingerprints}
    if panel_path.exists() and sidecar_path.exists():
        try:
            cached = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            cached = {}
        if cached.get("evidence_schema_version") == EVIDENCE_SCHEMA_VERSION and cached.get("request") == request:
            return {
                "source_id": cached.get("source_id"), "reference_dataset": reference_dataset,
                "comparison_datasets": comparison_datasets, "sky_center": cached.get("sky_center"),
                "quality_flags": cached.get("quality_flags", []), "ratio_f090_f444": cached.get("ratio_f090_f444"),
                "color_indices": cached.get("color_indices", {}), "color_status": cached.get("color_status"),
                "color_flux_unit": "Jy", "aperture_matching": cached.get("aperture_matching"),
                "photometry": cached.get("photometry", {}), "output_path": str(panel_path),
                "sidecar_path": str(sidecar_path), "artifacts": cached.get("artifacts", []), "cache_hit": True,
            }

    dataset_summaries: List[Dict[str, Any]] = []
    photometry_by_dataset: Dict[str, Dict[str, Any]] = {}
    filter_flux_map: Dict[str, float] = {}

    for dataset_name in science_datasets:
        bundle = load_fits_bundle(dataset_name)
        dataset_x, dataset_y = _resolve_dataset_position(bundle, sky_center, ref_x, ref_y)
        cutout = _cutout_for_bundle(bundle, dataset_x, dataset_y, cutout_size=cutout_size)

        registered_sky = False
        dataset_wcs = celestial_wcs(bundle)
        if sky_center is not None and dataset_wcs is not None:
            try:
                registered_sky = bool(dataset_wcs.pixel_to_world(dataset_x, dataset_y).separation(sky_center).arcsec < 1e-3)
            except (ValueError, TypeError):
                registered_sky = False
        aperture_results = {}
        for radius in aperture_radii:
            matched_options = dict(angular_options) if registered_sky else {}
            if matched_options:
                matched_options["aperture_radius_arcsec"] *= float(radius) / 3.0
            aperture_results[str(radius)] = extract_photometry(
                image_data=bundle,
                x=dataset_x,
                y=dataset_y,
                aperture_radius=float(radius),
                background_annulus_inner_radius=background_annulus_inner_radius,
                background_annulus_outer_radius=background_annulus_outer_radius,
                **matched_options,
            )

        dataset_summary = {
            "dataset_name": dataset_name,
            "file_path": bundle["file_path"],
            "filter": bundle.get("filter"),
            "target": bundle.get("target"),
            "instrument": bundle.get("instrument"),
            "dataset_x": dataset_x,
            "dataset_y": dataset_y,
            "astrometry_status": "matched_sky" if registered_sky else "pixel_only",
            "cutout": cutout,
        }
        dataset_summaries.append(dataset_summary)
        photometry_by_dataset[dataset_name] = aperture_results

        filter_name = str(bundle.get("filter") or "")
        radius_three = aperture_results.get("3")
        if (filter_name and radius_three is not None and registered_sky and angular_options
                and radius_three.get("calibration_status") == "calibrated"
                and radius_three.get("background_status") == "measured"
                and float(radius_three.get("coverage_fraction") or 0) >= .9
                and radius_three.get("background_subtracted_flux_jy") is not None):
            filter_flux_map[filter_name] = float(radius_three["background_subtracted_flux_jy"])

    reference_r3 = photometry_by_dataset[reference_dataset]["3"]
    quality_flags = _quality_flags(reference_r3, source_entry)
    if any(item["astrometry_status"] != "matched_sky" for item in dataset_summaries):
        quality_flags.append("unregistered_band_astrometry")
    if any(photometry_by_dataset[item["dataset_name"]]["3"].get("calibration_status") != "calibrated" for item in dataset_summaries):
        quality_flags.append("uncalibrated_band")

    ratio_f090_f444 = None
    if "F090W" in filter_flux_map and "F444W" in filter_flux_map and filter_flux_map["F444W"] > 0:
        ratio_f090_f444 = float(filter_flux_map["F090W"] / filter_flux_map["F444W"])

    total_panels = len(dataset_summaries) + 2
    ncols = 3
    nrows = math.ceil(total_panels / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(5.0 * ncols, 5.0 * nrows))
    axes_list = list(np.atleast_1d(axes).ravel())

    for idx, dataset_summary in enumerate(dataset_summaries):
        ax = axes_list[idx]
        cutout = dataset_summary["cutout"]
        valid_mask = np.asarray(cutout["validity_mask"], dtype=bool)
        display = _normalize_image_for_display(cutout["sci"], valid_mask)
        ax.imshow(display, cmap="magma", origin="lower")
        _add_aperture_overlay(
            ax,
            cutout["center_x"],
            cutout["center_y"],
            aperture_radius=photometry_by_dataset[dataset_summary["dataset_name"]]["3"]["aperture_radius"],
            annulus_inner=photometry_by_dataset[dataset_summary["dataset_name"]]["3"]["background_annulus_inner_radius"],
            annulus_outer=photometry_by_dataset[dataset_summary["dataset_name"]]["3"]["background_annulus_outer_radius"],
        )
        filter_name = dataset_summary.get("filter") or dataset_summary["dataset_name"]
        title = str(filter_name)
        if cutout.get("off_chip"):
            title += " (off-chip)"
        ax.set_title(title)
        ax.set_xticks([])
        ax.set_yticks([])

    reference_cutout = dataset_summaries[0]["cutout"]
    sn_ax = axes_list[len(dataset_summaries)]
    reference_err = reference_cutout["err"]
    if reference_err is not None:
        sn_image = np.divide(
            reference_cutout["sci"],
            reference_err,
            out=np.zeros_like(reference_cutout["sci"], dtype=float),
            where=np.isfinite(reference_err) & (reference_err > 0),
        )
    else:
        sn_image = np.zeros_like(reference_cutout["sci"], dtype=float)
    sn_image = np.clip(sn_image, -3.0, 25.0)
    sn_ax.imshow(sn_image, cmap="viridis", origin="lower", vmin=-3.0, vmax=25.0)
    _add_aperture_overlay(
        sn_ax,
        reference_cutout["center_x"],
        reference_cutout["center_y"],
        aperture_radius=reference_r3["aperture_radius"],
        annulus_inner=reference_r3["background_annulus_inner_radius"],
        annulus_outer=reference_r3["background_annulus_outer_radius"],
    )
    sn_ax.set_title("Reference S/N")
    sn_ax.set_xticks([])
    sn_ax.set_yticks([])

    coverage_ax = axes_list[len(dataset_summaries) + 1]
    coverage_image = np.where(reference_cutout["validity_mask"], 1.0, 0.0)
    coverage_ax.imshow(coverage_image, cmap="gray", origin="lower", vmin=0.0, vmax=1.0)
    _add_aperture_overlay(
        coverage_ax,
        reference_cutout["center_x"],
        reference_cutout["center_y"],
        aperture_radius=reference_r3["aperture_radius"],
        annulus_inner=reference_r3["background_annulus_inner_radius"],
        annulus_outer=reference_r3["background_annulus_outer_radius"],
    )
    coverage_ax.set_title("Reference Coverage")
    coverage_ax.set_xticks([])
    coverage_ax.set_yticks([])

    for ax in axes_list[total_panels:]:
        ax.axis("off")

    ra = None
    dec = None
    if sky_center is not None:
        ra = float(sky_center.ra.deg)
        dec = float(sky_center.dec.deg)

    title_bits = [
        f"source={source_id}" if source_id is not None else f"x={ref_x:.1f}, y={ref_y:.1f}",
        (f"ref_flux_r3={reference_r3['background_subtracted_flux_jy']:.3g} Jy"
         if reference_r3.get("background_subtracted_flux_jy") is not None else "ref_flux_r3=unavailable"),
        f"snr_r3={reference_r3['snr']:.2f}" if reference_r3.get("snr") is not None else "snr_r3=None",
        f"coverage_r3={reference_r3['coverage_fraction']:.2f}",
    ]
    if ratio_f090_f444 is not None:
        title_bits.append(f"F090/F444={ratio_f090_f444:.3f}")
    fig.suptitle(
        f"{reference_bundle.get('target') or reference_dataset} | " + " | ".join(title_bits),
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(panel_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    color_indices = {}
    if (
        "F090W" in filter_flux_map
        and "F444W" in filter_flux_map
        and filter_flux_map["F090W"] > 0
        and filter_flux_map["F444W"] > 0
    ):
        color_indices["F090W_F444W"] = compute_color_index(
            flux_band1=filter_flux_map["F090W"],
            flux_band2=filter_flux_map["F444W"],
        )
    if (
        "F090W" in filter_flux_map
        and "F200W" in filter_flux_map
        and filter_flux_map["F090W"] > 0
        and filter_flux_map["F200W"] > 0
    ):
        color_indices["F090W_F200W"] = compute_color_index(
            flux_band1=filter_flux_map["F090W"],
            flux_band2=filter_flux_map["F200W"],
        )
    if (
        "F200W" in filter_flux_map
        and "F444W" in filter_flux_map
        and filter_flux_map["F200W"] > 0
        and filter_flux_map["F444W"] > 0
    ):
        color_indices["F200W_F444W"] = compute_color_index(
            flux_band1=filter_flux_map["F200W"],
            flux_band2=filter_flux_map["F444W"],
        )

    color_status = "matched_aperture_fluxes_psf_uncorrected" if color_indices else "unavailable_or_nonpositive_fluxes"
    aperture_matching = "same_sky_angular" if angular_options else "pixel_only_no_cross_band_science"
    sidecar = {
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION, "request": request,
        "color_flux_unit": "Jy", "color_status": color_status, "aperture_matching": aperture_matching,
        "source_id": source_id,
        "reference_dataset": reference_dataset,
        "comparison_datasets": comparison_datasets,
        "reference_pixel_center": {"x": ref_x, "y": ref_y},
        "sky_center": {"ra": ra, "dec": dec},
        "aperture_radii": aperture_radii,
        "background_annulus_inner_radius": background_annulus_inner_radius,
        "background_annulus_outer_radius": background_annulus_outer_radius,
        "quality_flags": quality_flags,
        "ratio_f090_f444": ratio_f090_f444,
        "color_indices": color_indices,
        "source_entry": source_entry,
        "datasets": [
            {
                "dataset_name": item["dataset_name"],
                "file_path": item["file_path"],
                "filter": item["filter"],
                "target": item["target"],
                "instrument": item["instrument"],
                "dataset_x": item["dataset_x"],
                "dataset_y": item["dataset_y"],
                "off_chip": bool(item["cutout"].get("off_chip")),
                "astrometry_status": item["astrometry_status"],
            }
            for item in dataset_summaries
        ],
        "photometry": photometry_by_dataset,
        "artifacts": [
            {"path": str(panel_path), "kind": "evidence_panel"},
            {"path": str(sidecar_path), "kind": "evidence_sidecar"},
        ],
    }
    sidecar_path.write_text(json.dumps(_json_ready(sidecar), indent=2), encoding="utf-8")

    return {
        "source_id": source_id,
        "reference_dataset": reference_dataset,
        "comparison_datasets": comparison_datasets,
        "sky_center": {"ra": ra, "dec": dec},
        "quality_flags": quality_flags,
        "ratio_f090_f444": ratio_f090_f444,
        "photometry": photometry_by_dataset,
        "output_path": str(panel_path),
        "sidecar_path": str(sidecar_path),
        "artifacts": [
            {"path": str(panel_path), "kind": "evidence_panel"},
            {"path": str(sidecar_path), "kind": "evidence_sidecar"},
        ],
        "cache_hit": False,
        "color_indices": color_indices, "color_flux_unit": "Jy", "color_status": color_status,
        "aperture_matching": aperture_matching,
    }


def render_field_overview(
    image_data: str,
    catalog_path: str,
    highlight_source_ids: Optional[List[Any]] = None,
    top_n: int = 50,
    output_dir: str = "visuals",
    output_prefix: Optional[str] = None,
    strict_data: Optional[bool] = None,
) -> Dict[str, Any]:
    """Render a red-band field overview with source overlays and candidate highlights."""
    del strict_data  # strictness is enforced by the sandbox calling conventions

    bundle = load_fits_bundle(image_data)
    image = np.asarray(bundle["sci"], dtype=float)
    valid_mask = np.asarray(bundle["validity_mask"], dtype=bool)
    catalog = _load_catalog(catalog_path)
    sources = list(catalog.get("sources", []))
    ranked_sources = sorted(
        sources,
        key=lambda item: float(item.get("flux_proxy") or 0.0),
        reverse=True,
    )

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    prefix = output_prefix or _sanitize_name(image_data)
    output_path = output_root / f"{prefix}_field_overview.png"

    fig, ax = plt.subplots(figsize=(10, 10))
    ax.imshow(_normalize_image_for_display(image, valid_mask), cmap="gray", origin="lower")

    if sources:
        ax.scatter(
            [float(item["x"]) for item in sources],
            [float(item["y"]) for item in sources],
            s=8,
            c="white",
            alpha=0.55,
            linewidths=0.0,
        )

    source_lookup = {int(item["source_id"]): item for item in sources}
    highlight_count = 0
    for entry in highlight_source_ids or []:
        suspect = False
        if isinstance(entry, dict):
            source_id = int(entry["source_id"])
            suspect = bool(entry.get("suspect", False))
        else:
            source_id = int(entry)

        source = source_lookup.get(source_id)
        if source is None:
            continue

        if suspect:
            color = "red"
        elif float(source.get("coverage_fraction") or 0.0) < 0.9 or float(source.get("edge_distance_px") or 0.0) < 16.0:
            color = "orange"
        else:
            color = "lime"

        ax.scatter(
            [float(source["x"])],
            [float(source["y"])],
            s=60,
            facecolors="none",
            edgecolors=color,
            linewidths=1.2,
        )
        highlight_count += 1

    for source in ranked_sources[: max(int(top_n), 0)]:
        ax.text(
            float(source["x"]) + 3.0,
            float(source["y"]) + 3.0,
            str(source["source_id"]),
            color="white",
            fontsize=7,
            alpha=0.8,
        )

    ax.set_title(f"{bundle.get('target') or image_data} field overview")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return {
        "output_path": str(output_path),
        "highlight_count": highlight_count,
        "artifacts": [{"path": str(output_path), "kind": "field_overview"}],
    }


def save_color_diagnostic_plot(
    points: Iterable[Dict[str, Any]],
    output_path: str,
    target: str,
) -> str:
    """Save a simple F090-F200 vs F200-F444 diagnostic plot."""
    point_list = list(points)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 6))
    if point_list:
        x_values = [float(point["x_color"]) for point in point_list]
        y_values = [float(point["y_color"]) for point in point_list]
        colors = ["lime" if point.get("highlight") else "white" for point in point_list]
        sizes = [35 if point.get("highlight") else 18 for point in point_list]
        ax.scatter(
            x_values,
            y_values,
            c=colors,
            s=sizes,
            edgecolors="black",
            linewidths=0.4,
            alpha=0.8,
        )

    ax.set_xlabel("F090 - F200")
    ax.set_ylabel("F200 - F444")
    ax.set_title(f"{target} color diagnostic")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(output)
