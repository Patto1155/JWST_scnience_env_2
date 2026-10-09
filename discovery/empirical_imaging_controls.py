"""Finite-sample sky tails, pixel covariance and mirrored-image controls.

Blank apertures are spatially held out from their scale estimator. Nominal
binomial intervals remain conditional diagnostics: disjoint supports do not
remove long-range sky correlations or source-mask selection. Mirrored images
are controls from the same data, not independent observations or contamination
rates. PSF width variations below are explicit instrumental nuisance models.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.stats import sigma_clipped_stats
from photutils.segmentation import SourceCatalog, deblend_sources, detect_sources
from scipy.stats import beta, norm

from discovery.audit_candidates import audit_candidate, summarize
from discovery.image_photometry_rerun import (
    REQUIRED_FILTERS,
    load_selection_measurements,
    sha256_file,
    verify_image_manifest,
)
from discovery.native_psf import native_response, source_geometry
from discovery.photometry_sensitivity import rescale_measurements
from discovery.psf_noise import (
    blank_aperture_report,
    read_image,
    robust_sigma,
    source_mask,
    verified_template,
)
from tools.jwst.flux_calibration import celestial_wcs
from tools.jwst.photometry import extract_photometry


def binomial_interval(k: int, n: int) -> list[float] | None:
    """Nominal two-sided Clopper-Pearson 95%; zero trials is not zero risk."""
    if n < 0 or not 0 <= k <= n:
        raise ValueError("invalid binomial counts")
    if n == 0:
        return None
    return [
        0.0 if k == 0 else float(beta.ppf(0.025, k, n - k + 1)),
        1.0 if k == n else float(beta.ppf(0.975, k + 1, n - k)),
    ]


def heldout_tails(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Cross-fit median/MAD on the other checkerboard of 128-pixel blocks.

    No apertures are clipped after sampling; tails are counts of held-out signed
    residuals, not a Gaussian extrapolation from a robust fitted core.
    """
    if len(rows) < 40:
        return {"status": "insufficient_heldout_apertures", "n": len(rows)}
    if any(
        not np.isfinite(r["diagonal_sigma"])
        or r["diagonal_sigma"] <= 0
        or not np.isfinite(r["net_flux"])
        for r in rows
    ):
        raise ValueError("heldout measurements require finite flux and positive finite error")
    values = np.array([r["net_flux"] / r["diagonal_sigma"] for r in rows])
    folds = np.array([sum(map(int, r["spatial_block"].split(":"))) % 2 for r in rows])
    standardized = np.full(len(rows), np.nan)
    calibration = []
    for fold in (0, 1):
        training = values[folds != fold]
        heldout = folds == fold
        if len(training) < 20 or int(heldout.sum()) < 20:
            return {"status": "insufficient_checkerboard_fold", "n": len(rows)}
        median, scale = float(np.median(training)), robust_sigma(training)
        if not np.isfinite(scale) or scale <= 0:
            raise ValueError("heldout scale must be positive")
        standardized[heldout] = (values[heldout] - median) / scale
        calibration.append(
            {
                "heldout_fold": fold,
                "n_training": len(training),
                "n_heldout": int(heldout.sum()),
                "training_median": median,
                "training_mad_sigma": scale,
            }
        )
    counts = []
    for threshold in (2.0, 3.0, 4.0, 5.0):
        for sign, label in ((1, "positive"), (-1, "negative")):
            events = sign * standardized >= threshold
            k, n = int(events.sum()), len(rows)
            counts.append(
                {
                    "threshold": threshold,
                    "sign": label,
                    "events": k,
                    "trials": n,
                    "empirical_fraction": k / n,
                    "nominal_binomial_95": binomial_interval(k, n),
                    "gaussian_one_sided_reference_only": float(norm.sf(threshold)),
                    "fold_counts": [int(events[folds == f].sum()) for f in (0, 1)],
                }
            )
    return {
        "status": "measured",
        "n": len(rows),
        "fold_calibrations": calibration,
        "heldout_standardized_quantiles": [
            float(x) for x in np.quantile(standardized, [0, 0.001, 0.01, 0.5, 0.99, 0.999, 1])
        ],
        "heldout_ordinary_sigma": float(np.std(standardized, ddof=1)),
        "tails": counts,
        "smallest_empirical_rank_resolution": 1 / (len(rows) + 1),
        "confidence_scope": "nominal independent-Bernoulli interval; long-range correlations remain",
        "five_sigma_gaussian_certified": False,
    }


def valid_pixels(bundle: dict[str, Any]) -> np.ndarray:
    image = np.asarray(bundle["sci"])
    valid = np.isfinite(image)
    for key in ("err", "wht"):
        if bundle.get(key) is not None:
            values = np.asarray(bundle[key])
            valid &= np.isfinite(values) & (values > 0)
    if bundle.get("dq") is not None:
        valid &= np.asarray(bundle["dq"]) == 0
    return valid


def pixel_covariance(bundle: dict[str, Any], mask: np.ndarray) -> dict[str, Any]:
    """Ordinary observed off-source covariance after 128-pixel block means.

    Spatial variation/confusion are not isolated from resampling covariance.
    This is not substituted into a stationary aperture-error model.
    """
    image = np.asarray(bundle["sci"], float)
    valid = valid_pixels(bundle) & ~mask
    if bundle.get("err") is None:
        return {"status": "explicit_ERR_missing"}
    if np.count_nonzero(valid) < 20:
        return {"status": "insufficient_off_source_pixels", "pixels": int(valid.sum())}
    standardized = np.zeros_like(image)
    standardized[valid] = image[valid] / np.asarray(bundle["err"])[valid]
    for y in range(0, image.shape[0], 128):
        for x in range(0, image.shape[1], 128):
            block = standardized[y : y + 128, x : x + 128]
            accepted = valid[y : y + 128, x : x + 128]
            if accepted.any():
                block[accepted] -= float(np.mean(block[accepted]))
    variance = float(np.mean(standardized[valid] ** 2))
    rows = []
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1), (2, 0), (0, 2), (4, 0), (0, 4), (8, 0), (0, 8)):
        height, width = image.shape
        pair = valid[: height - dy, : width - dx] & valid[dy:, dx:]
        a = standardized[: height - dy, : width - dx][pair]
        b = standardized[dy:, dx:][pair]
        covariance = float(np.mean(a * b)) if len(a) else None
        rows.append(
            {
                "dx": dx,
                "dy": dy,
                "pairs": len(a),
                "ordinary_covariance_in_ERR_units": covariance,
                "covariance_over_zero_lag": covariance / variance
                if covariance is not None and variance > 0
                else None,
            }
        )
    return {
        "status": "measured",
        "ERR_normalized_variance": variance,
        "lags": rows,
        "detrending": "ordinary mean separately in 128x128 output-pixel blocks",
        "independent_pair_assumption": False,
        "stationary_noise_kernel_claimed": False,
    }


def mirrored_screen(
    bundles: dict[str, dict[str, Any]], *, radius: float, annulus: tuple[float, float]
) -> dict[str, Any]:
    """Blind negative F444 segmentation and sign-reversed photometry in all bands.

    Exactly the production threshold=3/min_pixels=9/deblend/border=16 settings.
    Sky medians disappear under the aperture-minus-annulus operator.
    """
    reference = bundles["F444W"]
    original = np.asarray(reference["sci"], float)
    # The production detector uses finite SCI and positive WHT. Uncertainty is
    # validated later by photometry, rather than defining segmentation pixels.
    valid = np.isfinite(original)
    if reference.get("wht") is not None:
        valid &= np.isfinite(reference["wht"]) & (reference["wht"] > 0)
    elif reference.get("err") is not None:
        valid &= np.isfinite(reference["err"])
    _, median, std = sigma_clipped_stats(original[valid], sigma=3)
    negative = np.where(valid, -(original - median), 0)
    seg = detect_sources(negative, 3 * std, n_pixels=9, mask=~valid)
    if seg is None:
        return {"n_negative_detections": 0, "summary": summarize([]), "audits": []}
    seg = deblend_sources(negative, seg, n_pixels=9, progress_bar=False)
    catalog = SourceCatalog(negative, seg, mask=~valid)
    mirrored = {
        band: {**bundle, "sci": -np.asarray(bundle["sci"])} for band, bundle in bundles.items()
    }
    proposals = []
    wcs = celestial_wcs(reference)
    height, width = original.shape
    for source in catalog:
        x, y = float(source.x_centroid), float(source.y_centroid)
        if min(x, y, width - 1 - x, height - 1 - y) < 16:
            continue
        coordinate = wcs.pixel_to_world(x, y)
        photometry = {}
        for band in REQUIRED_FILTERS:
            bx, by = celestial_wcs(bundles[band]).world_to_pixel(coordinate)
            photometry[band] = {
                "3": extract_photometry(
                    image_data=mirrored[band],
                    x=float(bx),
                    y=float(by),
                    aperture_radius_arcsec=radius,
                    background_annulus_inner_radius_arcsec=annulus[0],
                    background_annulus_outer_radius_arcsec=annulus[1],
                )
            }
        proposals.append(
            {
                "source_id": int(source.label),
                "target": "SMACS mirrored control",
                "sky_center": {"ra": coordinate.ra.deg, "dec": coordinate.dec.deg},
                "photometry_by_filter": photometry,
            }
        )
    audits = [audit_candidate(p) for p in proposals]
    return {
        "n_negative_detections": len(proposals),
        "summary": summarize(audits),
        "threshold_sigma": 3,
        "min_pixels": 9,
        "deblend": True,
        "border_margin": 16,
        "independent_exposure": False,
        "contamination_rate": None,
        "interpretation": "same-image signed-tail detection control; astrophysical sources make signs asymmetric",
        "audits": audits,
    }


def psf_sensitivity(
    bundles: dict[str, dict[str, Any]],
    proposals: list[dict[str, Any]],
    noise: dict[str, float],
    *,
    radius: float,
    annulus: tuple[float, float],
    short_psf: Path,
    long_psf: Path,
) -> dict[str, Any]:
    """Finite point-source and +/-10% width nuisance at the raw survivors.

    JADES models transported to SMACS are sensitivity assumptions, not a
    source-specific or field-specific PSF calibration.
    """
    raw = [p for p in proposals if audit_candidate(p)["audit_verdict"] == "survives"]
    provenance, response = {}, {}
    pinned = {
        r["filter"]: r["sha256"]
        for r in json.loads(Path("data_sources/native_psf_products.json").read_text())["products"]
    }
    pinned["F444W"] = "b74abf676cd57f272ada642a27fbb6a8fcb6e0181407357784d812c7f5fd6db2"
    for band in REQUIRED_FILTERS:
        path = (
            long_psf / "f444wa_v5.0_mpsf.fits"
            if band == "F444W"
            else short_psf / f"{band.lower()}_v5.0_mpsf.fits"
        )
        template, info = verified_template(path, band)
        if info["sha256"] != pinned[band]:
            raise ValueError("PSF differs from pinned research model inventory")
        provenance[band] = info
        for proposal in raw:
            world = SkyCoord(**proposal["sky_center"], unit="deg")
            x, y = celestial_wcs(bundles[band]).world_to_pixel(world)
            scale, phase, geometry = source_geometry(
                bundles[band], float(x), float(y), radius=radius, annulus=annulus
            )
            for width in (0.9, 1.0, 1.1):
                record = native_response(
                    template,
                    input_scale=info["input_scale_arcsec"] * width,
                    output_scale=scale,
                    phase=phase,
                    radius=radius,
                    annulus=annulus,
                    geometry=geometry,
                )
                response[(proposal["source_id"], band, width)] = record["total_flux_multiplier"]
    scenarios = []
    for width in (0.9, 1.0, 1.1):
        factors = {
            (p["source_id"], band): response[(p["source_id"], band, width)]
            for p in raw
            for band in REQUIRED_FILTERS
        }
        changed = rescale_measurements(raw, noise, factors)
        scenarios.append(
            {
                "width_multiplier": width,
                "noise_multipliers": noise,
                "summary_on_original_ten_only": summarize([audit_candidate(p) for p in changed]),
                "audit_details": [audit_candidate(p) for p in changed],
            }
        )
    return {
        "model_not_observed": True,
        "field_transfer_assumed": "JADES GOODS-S PSF to SMACS",
        "no_extended_galaxy_total_claim": True,
        "provenance": provenance,
        "responses": [
            {
                "source_id": key[0],
                "band": key[1],
                "width_multiplier": key[2],
                "total_flux_multiplier": value,
            }
            for key, value in response.items()
        ],
        "scenarios": scenarios,
    }


def selected_images(
    verified: list[dict[str, Any]], selected: dict[str, str], receipts: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Resolve frozen product names/hashes without retaining old cache paths."""
    result = {}
    for band in REQUIRED_FILTERS:
        matches = [
            r
            for r in verified
            if Path(r["resolved_path"]).name == Path(selected[band]).name
            and r["filter"] == band
            and r["sha256"] == receipts[band]["sha256"]
        ]
        if len(matches) != 1:
            raise ValueError(
                "Selected science bytes disagree with frozen catalog or are duplicated"
            )
        result[band] = matches[0]
    return result


def run(
    manifest: Path,
    catalog_dir: Path,
    output: Path,
    full_output: Path,
    *,
    short_psf: Path,
    long_psf: Path,
) -> dict[str, Any]:
    verified, blocked = verify_image_manifest(manifest)
    if blocked:
        raise ValueError(f"Image manifest has blocked rows: {blocked}")
    summary = json.loads((catalog_dir / "rerun_summary.json").read_text())
    selected = summary["targets"][0]["selected_datasets"]
    receipts = {r["filter"]: r for r in summary["image_receipts"]}
    images = selected_images(verified, selected, receipts)
    bundles, image_reports, full_reports, noise = {}, [], [], {}
    metadata = json.loads((catalog_dir / "selection_metadata.json").read_text())
    replay = json.loads((catalog_dir / "compact_replay_verification.json").read_text())
    for filename, key in (
        ("selection_measurements.csv", "selection_csv_sha256"),
        ("selection_metadata.json", "selection_metadata_sha256"),
    ):
        if sha256_file(catalog_dir / filename) != replay[key]:
            raise ValueError("Compact selection artifact hash mismatch")
    proposals = load_selection_measurements(
        catalog_dir / "selection_measurements.csv", catalog_dir / "selection_metadata.json"
    )
    if summarize([audit_candidate(p) for p in proposals]) != replay["audit_summary"]:
        raise ValueError("Compact selection does not reproduce frozen baseline")
    radius = metadata["aperture_radius_arcsec_by_filter"]["F444W"]
    annulus = tuple(metadata["annulus_radii_arcsec"][k] for k in ("inner", "outer"))
    for band in REQUIRED_FILTERS:
        row = images[band]
        path = Path(row["resolved_path"])
        bundle = read_image(path)
        bundle["wcs"] = celestial_wcs(bundle)
        bundles[band] = bundle
        valid = valid_pixels(bundle)
        scale = float(
            min(np.linalg.svd(celestial_wcs(bundle).pixel_scale_matrix, compute_uv=False)) * 3600
        )
        dilation = int(np.ceil(0.3145519191699558 / scale)) + 2
        mask = source_mask(bundle["sci"], valid, dilation=dilation)
        diagnostics = []
        for mask_label, current in (
            ("positive_sources", mask),
            (
                "both_signs_sensitivity",
                mask | source_mask(-bundle["sci"], valid, dilation=dilation),
            ),
        ):
            blanks = blank_aperture_report(
                bundle,
                radii=(2 * radius / 3, radius, 5 * radius / 3),
                mask=current,
                seed=731,
                bootstrap=500,
                max_apertures=5000,
                annulus_radii_arcsec=annulus,
            )
            for item in blanks["apertures"]:
                item["heldout_tails"] = heldout_tails(item["measurements"])
            full_reports.append({"band": band, "mask_label": mask_label, "blanks": blanks})
            compact = {
                **blanks,
                "apertures": [
                    {k: v for k, v in item.items() if k not in ("measurements", "spatial_blocks")}
                    for item in blanks["apertures"]
                ],
            }
            compact["mask_label"] = mask_label
            compact["pixel_covariance"] = pixel_covariance(bundle, current)
            diagnostics.append(compact)
            if mask_label == "positive_sources":
                noise[band] = blanks["apertures"][1]["noise_multiplier"]
        image_reports.append(
            {
                "filter": band,
                "sha256": row["sha256"],
                "product_filename": path.name,
                "diagnostics": diagnostics,
            }
        )
        print(json.dumps({"band": band, "noise_factor": noise[band]}), flush=True)
    raw_audits = [audit_candidate(p) for p in proposals]
    changed_audits = [audit_candidate(p) for p in rescale_measurements(proposals, noise)]
    result = {
        "experiment": "SMACS observed tails, covariance, negative-image and finite PSF controls",
        "manifest_sha256": sha256_file(manifest),
        "catalog_sha256": replay["selection_csv_sha256"],
        "operator_metadata_sha256": replay["selection_metadata_sha256"],
        "raw_baseline": summarize(raw_audits),
        "noise_sensitivity_all_proposals": summarize(changed_audits),
        "noise_sensitivity_raw_survivors": [
            a
            for a, raw in zip(changed_audits, raw_audits, strict=True)
            if raw["audit_verdict"] == "survives"
        ],
        "real_images": image_reports,
        "mirrored_image_control": mirrored_screen(bundles, radius=radius, annulus=annulus),
        "point_psf_width_sensitivity": psf_sensitivity(
            bundles,
            proposals,
            noise,
            radius=radius,
            annulus=annulus,
            short_psf=short_psf,
            long_psf=long_psf,
        ),
        "limitations": [
            "Single-field selected blank sky is not an independent faint-galaxy recovery test.",
            "Source masks condition the sampled distribution; symmetric masks can censor true noise extremes.",
            "Checkerboard folds and disjoint footprints leave long-range spatial correlations.",
            "Nominal binomial intervals do not certify Gaussian five-sigma false-positive rates.",
            "Pixel covariance includes residual confusion and structure; no stationary drizzle kernel inferred.",
            "Sky multipliers on total source errors are sensitivity cases, not calibrated Poisson errors.",
            "Mirrored detections do not measure prevalence; source/background sign asymmetry matters.",
            "JADES PSF transport and width variations are assumptions, not SMACS calibration or galaxy totals.",
            "No source identity, redshift, abundance, population rate or discovery is inferred.",
        ],
    }
    full_output.parent.mkdir(parents=True, exist_ok=True)
    full_output.write_text(json.dumps(full_reports, indent=2, allow_nan=False) + "\n")
    result["full_blank_samples"] = {
        "filename": full_output.name,
        "sha256": sha256_file(full_output),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("catalog_dir", type=Path)
    parser.add_argument("--short-psf", type=Path, required=True)
    parser.add_argument("--long-psf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--full-output", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        args.manifest,
        args.catalog_dir,
        args.output,
        args.full_output,
        short_psf=args.short_psf,
        long_psf=args.long_psf,
    )
    print(
        json.dumps(
            {
                "raw": result["raw_baseline"]["survivors"],
                "noise": result["noise_sensitivity_all_proposals"]["survivors"],
                "mirrored": result["mirrored_image_control"]["summary"]["survivors"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
