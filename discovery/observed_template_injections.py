"""Frozen observed-profile injections into disjoint actual mosaic backgrounds.

These are synthetic controls conditioned on four selected observed templates,
source-masked positions and one dependent mosaic. Finite-stamp flux is preserved
under size changes; noisy template wings and missing fresh source-Poisson noise
prevent interpreting the curves as faint-galaxy population completeness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.stats import sigma_clipped_stats
from astropy.wcs.utils import proj_plane_pixel_scales
from photutils.segmentation import SourceCatalog, deblend_sources, detect_sources
from scipy.ndimage import binary_dilation, distance_transform_edt, zoom

from discovery.deep_control_recovery import freeze, json_hash, load_inputs, minimum_pixels
from discovery.deep_reference_comparison import measurement

TEMPLATE_IDS = ("190909", "187956", "186837", "20189546")
FLUXES_NJY = (5.0, 10.0, 20.0, 40.0, 80.0, 160.0, 320.0)
SPATIAL_SCALES = (0.65, 1.0, 1.5)
TEMPLATE_RADIUS_ARCSEC = 0.45
MATCH_RADIUS_ARCSEC = 0.2
CROP_HALF_PIXELS = 24
MAX_SITES_PER_IMAGE = 10
RANDOM_SEED = 314159


def array_hash(array: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(array, dtype="<f8").tobytes()).hexdigest()


def sized_template(stamp: np.ndarray, scale: float) -> np.ndarray:
    """Resize a nonnegative finite profile, preserving its declared integrated flux."""
    if stamp.ndim != 2 or stamp.shape[0] != stamp.shape[1] or stamp.shape[0] % 2 != 1:
        raise ValueError("Template must be an odd square")
    if not np.isfinite(stamp).all() or np.any(stamp < 0) or stamp.sum() <= 0 or not math.isfinite(scale) or scale <= 0:
        raise ValueError("Finite positive profile and size are required")
    side = max(3, int(round(stamp.shape[0] * scale)))
    if side % 2 == 0:
        side += 1
    resized = zoom(stamp, side / stamp.shape[0], order=1, prefilter=False)
    if resized.shape != (side, side) or resized.sum() <= 0:
        raise ValueError("Invalid interpolated profile")
    return resized / resized.sum()


def template_annulus_mask(distance_arcsec: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """True radial 0.7–1.0 arcsec annulus, excluding enclosing-square corners."""
    if distance_arcsec.shape != valid.shape:
        raise ValueError("Template distance and validity shapes differ")
    return np.isfinite(distance_arcsec) & (distance_arcsec >= 0.7) & (distance_arcsec <= 1.0) & valid


def observed_template(bundle: dict, reference: dict) -> tuple[np.ndarray, dict]:
    if bundle["header"].get("BUNIT") != "10.0*nanoJansky":
        raise ValueError("This experiment expects the pinned DAWN 10-nJy pixel-flux unit")
    x, y = bundle["wcs"].world_to_pixel(SkyCoord(reference["ra_deg"], reference["dec_deg"], unit="deg"))
    ix, iy = int(round(float(x))), int(round(float(y)))
    scale = float(np.sqrt(np.prod(proj_plane_pixel_scales(bundle["wcs"]) * 3600)))
    half = int(math.ceil(TEMPLATE_RADIUS_ARCSEC / scale))
    signed = bundle["sci"][iy-half:iy+half+1, ix-half:ix+half+1].copy()
    if signed.shape != (2*half+1, 2*half+1):
        raise ValueError("Template stamp truncated at image boundary")
    yy, xx = np.mgrid[-half:half+1, -half:half+1]
    distance = np.hypot(xx + ix - x, yy + iy - y) * scale
    # A broader local annulus supplies only a scalar sky estimate. Neighbours
    # and observed noise remain possible template contaminants and are reported.
    outer = int(math.ceil(1.0 / scale))
    by, bx = np.mgrid[-outer:outer+1, -outer:outer+1]
    background = bundle["sci"][iy-outer:iy+outer+1, ix-outer:ix+outer+1]
    valid = bundle["validity_mask"][iy-outer:iy+outer+1, ix-outer:ix+outer+1]
    annulus = template_annulus_mask(np.hypot(bx + ix - x, by + iy - y) * scale, valid)
    if background.shape != annulus.shape or annulus.sum() < 20:
        raise ValueError("Insufficient observed template background")
    _, sky, _ = sigma_clipped_stats(background[annulus], sigma=3)
    signed -= sky
    footprint = distance <= TEMPLATE_RADIUS_ARCSEC
    signed[~footprint] = 0
    profile = np.maximum(signed, 0)
    if profile.sum() <= 0:
        raise ValueError("Observed template has no positive finite-stamp signal")
    normalized = profile / profile.sum()
    cx = float(np.sum(normalized * xx))
    cy = float(np.sum(normalized * yy))
    # Keep the original measured stamp phase rather than forcing a fitted model.
    report = {"reference": reference, "radius_arcsec": TEMPLATE_RADIUS_ARCSEC,
              "stamp_shape_pixels": list(profile.shape), "array_sha256": array_hash(normalized),
              "positive_stamp_flux_njy": float(profile.sum() * 10), "signed_stamp_flux_njy": float(signed.sum() * 10),
              "clipped_negative_to_positive_flux": float(-signed[signed < 0].sum() / profile.sum()),
              "centroid_offset_from_stamp_center_arcsec": [cx * scale, cy * scale],
              "measured_original_aperture": measurement(bundle, ra_deg=reference["ra_deg"], dec_deg=reference["dec_deg"]),
              "profile_caveat": "Observed noisy background-subtracted profile clipped positive within finite radius; can include neighbour flux; not a noiseless true galaxy"}
    return normalized, report


def masked_sites(bundle: dict) -> tuple[list[dict], dict]:
    image, valid = bundle["sci"], bundle["validity_mask"]
    _, median, sigma = sigma_clipped_stats(image[valid], sigma=3)
    segments = detect_sources(np.where(valid, image-median, 0), threshold=2*sigma, npixels=5, mask=~valid)
    sources = np.zeros(image.shape, bool) if segments is None else segments.data > 0
    excluded = binary_dilation(sources, iterations=4) | ~valid
    distance = distance_transform_edt(np.pad(~excluded, 1))[1:-1, 1:-1]
    scale = float(np.sqrt(np.prod(proj_plane_pixel_scales(bundle["wcs"]) * 3600)))
    # Nonoverlapping squares even if WCS orientation differs across cutouts.
    spacing = int(math.ceil((2*CROP_HALF_PIXELS+1)*math.sqrt(2))) + 1
    insertion_radius = TEMPLATE_RADIUS_ARCSEC * max(SPATIAL_SCALES) + 2*scale
    sites = []
    for y in range(CROP_HALF_PIXELS+2, image.shape[0]-CROP_HALF_PIXELS-2, spacing):
        for x in range(CROP_HALF_PIXELS+2, image.shape[1]-CROP_HALF_PIXELS-2, spacing):
            crop_valid = valid[y-CROP_HALF_PIXELS:y+CROP_HALF_PIXELS+1, x-CROP_HALF_PIXELS:x+CROP_HALF_PIXELS+1]
            if not crop_valid.all() or distance[y, x]*scale < insertion_radius:
                continue
            sky = bundle["wcs"].pixel_to_world(x, y)
            sites.append({"x": x, "y": y, "ra_deg": float(sky.ra.deg), "dec_deg": float(sky.dec.deg),
                          "nearest_source_mask_distance_arcsec": float(distance[y, x]*scale),
                          "spatial_block": f"{x//160}-{y//160}"})
    return sites, {"full_image_median": float(median), "full_image_sigma": float(sigma),
                   "eligible_grid_sites_before_cross_image_dedup": len(sites),
                   "pixel_scale_arcsec": scale, "crop_half_pixels": CROP_HALF_PIXELS,
                   "source_mask_fraction": float(excluded.mean()),
                   "selection_caveat": "Positive two-sigma source masking censors positive tails; chosen backgrounds are not a random sky population"}


def build_plan(input_dir: Path, original: Path) -> tuple[dict, dict, dict]:
    frozen = freeze(input_dir, original)
    _, images = load_inputs(input_dir, original)
    by_name = {p["filename"]: b for b, p in images}
    arrays, templates = {}, []
    for identifier in TEMPLATE_IDS:
        matches = [r for r in frozen["references"] if any(o.rsplit("_", 1)[-1] == identifier for o in r["observation_ids"])]
        if len(matches) != 1:
            raise ValueError("Frozen observed template identity is not unique")
        reference = matches[0]
        profile, report = observed_template(by_name[reference["primary_deep_image"]], reference)
        report["template_id"] = identifier
        report["sized_profiles"] = []
        for scale in SPATIAL_SCALES:
            sized = sized_template(profile, scale)
            if sized.shape[0] >= 2*CROP_HALF_PIXELS-4:
                raise ValueError("Sized observed profile leaves insufficient detector margin")
            report["sized_profiles"].append({"spatial_scale": scale, "shape": list(sized.shape), "sha256": array_hash(sized)})
            arrays[(identifier, scale)] = sized
        templates.append(report)
    rng = np.random.default_rng(RANDOM_SEED)
    sites, image_reports = [], []
    exclusion_radius = (2*CROP_HALF_PIXELS+1)*0.05*math.sqrt(2)
    for bundle, provenance in images:
        candidates, report = masked_sites(bundle)
        report["filename"] = provenance["filename"]
        report["angular_area_min_pixels"] = minimum_pixels(frozen["original_pixel_area_arcsec2"], report["pixel_scale_arcsec"]**2)
        report["legacy_min_pixels"] = 5
        accepted = 0
        for index in rng.permutation(len(candidates)):
            site = candidates[int(index)]
            sky = SkyCoord(site["ra_deg"], site["dec_deg"], unit="deg")
            if sites:
                previous = SkyCoord([s["ra_deg"] for s in sites], [s["dec_deg"] for s in sites], unit="deg")
                if np.any(sky.separation(previous).arcsec <= exclusion_radius):
                    continue
            site.update({"image": provenance["filename"], "site_id": f"site-{len(sites):03d}"})
            # Spatial blocks remain image-scoped; all cutouts share contributors.
            site["spatial_block"] = provenance["filename"] + ":" + site["spatial_block"]
            sites.append(site)
            accepted += 1
            if accepted == MAX_SITES_PER_IMAGE:
                break
        report["selected_disjoint_sites"] = accepted
        image_reports.append(report)
    if len(sites) < 10:
        raise ValueError("Too few disjoint observed background sites")
    plan = {"schema_version": 1, "evidence_kind": "frozen_synthetic_profiles_on_actual_background_pixels",
            "basis_frozen_control_sha256": json_hash(frozen), "deep_inputs": frozen["deep_inputs"],
            "template_ids": list(TEMPLATE_IDS), "templates": templates,
            "fluxes_finite_stamp_njy": list(FLUXES_NJY), "spatial_scales": list(SPATIAL_SCALES),
            "random_seed": RANDOM_SEED, "sites": sites, "image_reports": image_reports,
            "match_radius_arcsec": MATCH_RADIUS_ARCSEC,
            "detector_scope": "49-pixel local segmentation/deblending at fixed full-uninjected-image median and five-sigma threshold; threshold not refit after insertion",
            "dependence": "All templates/amplitudes/sizes reuse identical sites; disjoint pixel stamps are one dependent GOODS mosaic, not independent fields/visits",
            "operator_assumptions": ["Fresh source Poisson noise omitted; stored WHT and correlated background retained",
                                     "Observed clipped templates retain a fixed noise realization and finite-radius truncation",
                                     "Spatial scaling is an interpolation sensitivity, not a physical redshift/PSF evolution model",
                                     "Site masking avoids source cores; this does not calibrate dense crowding or unmasked-sky completeness"]}
    plan["plan_content_sha256"] = json_hash(plan)
    return plan, arrays, by_name


def injected_crop(background: np.ndarray, profile: np.ndarray, flux_njy: float) -> np.ndarray:
    if background.ndim != 2 or min(background.shape) <= max(profile.shape) or not math.isfinite(flux_njy) or flux_njy < 0:
        raise ValueError("Injection must fit a two-dimensional background with nonnegative flux")
    if not np.isfinite(profile).all() or np.any(profile < 0) or not np.isclose(profile.sum(), 1):
        raise ValueError("Injected profile must be normalized and nonnegative")
    values = background.copy()
    cy, cx = (n//2 for n in background.shape)
    half = profile.shape[0]//2
    values[cy-half:cy+half+1, cx-half:cx+half+1] += profile * (flux_njy/10.0)
    return values


def local_detection(values: np.ndarray, median: float, sigma: float, min_pixels: int, scale_arcsec: float) -> dict:
    segment = detect_sources(values-median, threshold=5*sigma, npixels=min_pixels)
    if segment is None:
        return {"status": "not_detected", "nearest_centroid_arcsec": None, "matches": 0}
    segment = deblend_sources(values-median, segment, npixels=min_pixels, progress_bar=False)
    catalog = SourceCatalog(values-median, segment)
    cy, cx = (n//2 for n in values.shape)
    distances = np.array([np.hypot(float(r.xcentroid)-cx, float(r.ycentroid)-cy)*scale_arcsec for r in catalog])
    matched = int(np.sum(distances <= MATCH_RADIUS_ARCSEC))
    return {"status": "matched" if matched == 1 else "ambiguous" if matched > 1 else "not_detected",
            "nearest_centroid_arcsec": float(np.nanmin(distances)) if len(distances) else None, "matches": matched}


def blocked_interval(successes: list[bool], blocks: list[str], seed: int) -> dict:
    """Conditional resampling of whole spatial blocks, preserving paired site trials."""
    unique = sorted(set(blocks))
    if len(unique) < 4:
        return {"status": "insufficient_spatial_blocks", "block_count": len(unique)}
    indices = [np.flatnonzero(np.array(blocks) == block) for block in unique]
    values = np.array(successes, dtype=float)
    rng = np.random.default_rng(seed)
    estimates = []
    for _ in range(500):
        selected = np.concatenate([indices[i] for i in rng.integers(0, len(indices), len(indices))])
        estimates.append(float(values[selected].mean()))
    lower, upper = np.quantile(estimates, [0.025, 0.975])
    return {"status": "conditional_empirical_resampling", "lower": float(lower), "upper": float(upper),
            "spatial_blocks": len(unique), "resamples": 500,
            "interpretation": "Within this masked background design only; degenerate intervals at zero or one do not bound unseen failures; no field/systematic or calibrated 95-percent coverage guarantee"}


def adjacent_flux_changes(trials: list[dict]) -> list[dict]:
    """Count paired losses/gains without assuming recovery increases with flux."""
    sequences = defaultdict(list)
    for trial in trials:
        sequences[(trial["template_id"], trial["spatial_scale"], trial["site_id"])].append(trial)
    changes = defaultdict(lambda: {"matched_then_nonmatched": 0, "nonmatched_then_matched": 0, "paired_sites": 0})
    for (template, spatial_scale, _), sequence in sequences.items():
        ordered = sorted(sequence, key=lambda r: r["finite_stamp_flux_njy"])
        for lower, higher in zip(ordered, ordered[1:]):
            for mode in ("legacy", "angular_area"):
                key = (template, spatial_scale, lower["finite_stamp_flux_njy"], higher["finite_stamp_flux_njy"], mode)
                first = lower["detections"][mode]["status"] == "matched"
                second = higher["detections"][mode]["status"] == "matched"
                changes[key]["matched_then_nonmatched"] += first and not second
                changes[key]["nonmatched_then_matched"] += second and not first
                changes[key]["paired_sites"] += 1
    return [{"template_id": k[0], "spatial_scale": k[1], "lower_flux_njy": k[2], "higher_flux_njy": k[3],
             "mode": k[4], **v} for k, v in sorted(changes.items()) if v["matched_then_nonmatched"]]


def execute(plan: dict, input_dir: Path, original: Path) -> tuple[dict, list[dict]]:
    reproduced, arrays, images = build_plan(input_dir, original)
    if json_hash(plan) != json_hash(reproduced):
        raise ValueError("Frozen injection plan differs from pinned reproducible inputs")
    reports = {r["filename"]: r for r in plan["image_reports"]}
    trials, baseline = [], []
    for site in plan["sites"]:
        report = reports[site["image"]]
        x, y = site["x"], site["y"]
        background = images[site["image"]]["sci"][y-CROP_HALF_PIXELS:y+CROP_HALF_PIXELS+1, x-CROP_HALF_PIXELS:x+CROP_HALF_PIXELS+1]
        for mode in ("legacy", "angular_area"):
            result = local_detection(background, report["full_image_median"], report["full_image_sigma"],
                                     report[mode+"_min_pixels"], report["pixel_scale_arcsec"])
            baseline.append({"site_id": site["site_id"], "mode": mode, **result})
        for (identifier, spatial_scale), profile in arrays.items():
            for flux in FLUXES_NJY:
                values = injected_crop(background, profile, flux)
                trial = {"site_id": site["site_id"], "spatial_block": site["spatial_block"], "template_id": identifier,
                         "spatial_scale": spatial_scale, "finite_stamp_flux_njy": flux, "detections": {}}
                for mode in ("legacy", "angular_area"):
                    trial["detections"][mode] = local_detection(values, report["full_image_median"], report["full_image_sigma"],
                                                                report[mode+"_min_pixels"], report["pixel_scale_arcsec"])
                trials.append(trial)
    groups = defaultdict(list)
    for trial in trials:
        groups[(trial["template_id"], trial["spatial_scale"], trial["finite_stamp_flux_njy"])].append(trial)
    curves = []
    for key, rows in sorted(groups.items()):
        modes = {}
        for mode in ("legacy", "angular_area"):
            successful = [r["detections"][mode]["status"] == "matched" for r in rows]
            modes[mode] = {"matched": sum(successful), "sites": len(rows), "fraction": sum(successful)/len(rows),
                           "ambiguous": sum(r["detections"][mode]["status"] == "ambiguous" for r in rows),
                           "conditional_spatial_block_interval": blocked_interval(successful, [r["spatial_block"] for r in rows], RANDOM_SEED)}
        curves.append({"template_id": key[0], "spatial_scale": key[1], "finite_stamp_flux_njy": key[2], "modes": modes,
                       "paired_legacy_only_matches": sum(r["detections"]["legacy"]["status"] == "matched" and r["detections"]["angular_area"]["status"] != "matched" for r in rows),
                       "paired_angular_area_only_matches": sum(r["detections"]["angular_area"]["status"] == "matched" and r["detections"]["legacy"]["status"] != "matched" for r in rows)})
    summary = {"schema_version": 1, "evidence_kind": "synthetic_observed_profile_injections_into_actual_backgrounds",
               "frozen_plan_sha256": json_hash(plan), "total_insertion_trials": len(trials), "disjoint_background_sites": len(plan["sites"]),
               "distinct_observed_templates": len(TEMPLATE_IDS), "dependent_mosaic_groups": 1,
               "baseline_null_controls": baseline, "curves": curves, "full_trials_sha256": json_hash(trials),
               "paired_flux_increase_recovery_losses": adjacent_flux_changes(trials),
               "limits": plan["operator_assumptions"] + [plan["dependence"],
                   "Local crop operator is not equivalent to global segmentation for segments/deblends connected outside the crop",
                   "Centroid nonmatch can indicate blending or phase/extent offsets rather than missing injected flux",
                   "No classifier, color/SED selection, artifact recall or real faint-population completeness is estimated",
                   "Conditional block intervals reuse source-masked sites and cannot certify frequentist coverage or independent visits"]}
    return summary, trials


def plot_summary(summary: dict, output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    figure, axes = plt.subplots(2, 2, figsize=(10, 7), sharex=True, sharey=True)
    names = {"190909": "190909: bright low-z stamp", "187956": "187956: bright intermediate-z stamp",
             "186837": "186837: blended/displaced stamp", "20189546": "20189546: noisy robust high-z stamp"}
    colors = {0.65: "#267baf", 1.0: "#438c45", 1.5: "#a551a1"}
    for axis, identifier in zip(axes.flat, TEMPLATE_IDS):
        for size in SPATIAL_SCALES:
            rows = sorted([r for r in summary["curves"] if r["template_id"] == identifier and r["spatial_scale"] == size],
                          key=lambda r: r["finite_stamp_flux_njy"])
            for mode, style in [("legacy", "-"), ("angular_area", "--")]:
                axis.plot([r["finite_stamp_flux_njy"] for r in rows], [r["modes"][mode]["fraction"] for r in rows],
                          color=colors[size], linestyle=style, marker="o", markersize=3)
        axis.set_title(names[identifier], fontsize=10)
        axis.set_xscale("log", base=2)
        axis.set_ylim(-0.04, 1.04)
        axis.set_xticks([5, 20, 80, 320], labels=["5", "20", "80", "320"])
        axis.grid(alpha=0.2)
    for axis in axes[:, 0]:
        axis.set_ylabel("Matched centroids / 29 fixed sites")
    for axis in axes[-1, :]:
        axis.set_xlabel("Flux in finite scaled template (nJy)")
    handles = [Line2D([0], [0], color=colors[s], label=f"Size scale {s}") for s in SPATIAL_SCALES]
    handles += [Line2D([0], [0], color="black", linestyle=style, label=label)
                for style, label in [("-", "5 connected pixels"), ("--", "8 connected pixels")]]
    figure.legend(handles=handles, loc="lower center", ncol=5, frameon=False, fontsize=9)
    figure.suptitle("Observed-profile injections on disjoint masked real backgrounds", fontsize=13)
    figure.text(0.5, 0.93, "Fixed noisy templates, local operator, one dependent mosaic; conditional sensitivity, not population completeness",
                ha="center", fontsize=9)
    figure.tight_layout(rect=[0, 0.06, 1, 0.92])
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=160)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["freeze", "execute"])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--full-output", type=Path)
    parser.add_argument("--figure", type=Path)
    args = parser.parse_args()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if args.mode == "freeze":
            result, _, _ = build_plan(args.input, args.original)
            output = args.plan
        else:
            if args.output is None or args.full_output is None:
                parser.error("execute requires --output and --full-output")
            result, trials = execute(json.loads(args.plan.read_text()), args.input, args.original)
            if args.figure is not None:
                plot_summary(result, args.figure)
            args.full_output.parent.mkdir(parents=True, exist_ok=True)
            args.full_output.write_text(json.dumps(trials, indent=2, allow_nan=False) + "\n")
            output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
