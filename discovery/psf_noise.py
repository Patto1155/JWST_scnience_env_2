"""Finite-template PSF corrections and blank-sky aperture covariance diagnostics.

Modeled PSFs are not observed stars. Blank-aperture variance is image-specific
and combines covariance, residual confusion and background structure; it is not
an isolated measurement of a drizzle kernel or a universal ERR multiplier.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits
from scipy.ndimage import binary_dilation, gaussian_filter, label
from scipy.signal import fftconvolve

from tools.jwst.flux_calibration import celestial_wcs, flux_density_factors

DEFAULT_RADII = (0.126, 0.189, 0.315, 0.45, 0.6)
DEFAULT_PHASES = (
    (0.0, 0.0),
    (-0.4, -0.4),
    (-0.4, 0),
    (-0.4, 0.4),
    (0, -0.4),
    (0, 0.4),
    (0.4, -0.4),
    (0.4, 0),
    (0.4, 0.4),
)


def _validate_radii(radii: tuple[float, ...]) -> None:
    if not radii or not np.all(np.isfinite(radii)) or min(radii) <= 0:
        raise ValueError("aperture radii must be finite and positive")


def verified_template(path: Path, filter_name: str) -> tuple[np.ndarray, dict[str, Any]]:
    """Read the uncropped template only after validating its download receipt."""
    raw = path.read_bytes()
    receipt = json.loads(path.with_name(path.name + ".provenance.json").read_text())
    checksum = hashlib.sha256(raw).hexdigest()
    if checksum != receipt["sha256"] or len(raw) != receipt["bytes"]:
        raise ValueError(f"PSF receipt mismatch: {path}")
    with fits.open(path) as hdus:
        hdu = next(h for h in hdus if h.data is not None and h.data.ndim == 2)
        image = np.asarray(hdu.data, float)
        header = hdu.header
        if str(header.get("FILTER", "")).upper() != filter_name:
            raise ValueError("PSF FILTER does not match requested filter")
        scale = float(header["PIXELSCL"])
    if (
        not np.isfinite(scale)
        or scale <= 0
        or any(n % 2 == 0 for n in image.shape)
        or not np.isfinite(image).all()
        or np.any(image < 0)
        or image.sum() <= 0
    ):
        raise ValueError("require finite nonnegative odd template and positive angular scale")
    return image / image.sum(), {
        "filter": filter_name,
        "sha256": checksum,
        "bytes": len(raw),
        "requested_url": receipt["requested_url"],
        "retrieved_utc": receipt["retrieved_utc"],
        "input_scale_arcsec": scale,
        "template_shape": list(image.shape),
        "original_template_sum": float(image.sum()),
        "normalization": "finite supplied template; unmodeled outer wings are unknown",
        "origin": "official JADES DR5 modeled PSF, not observed-star measurement",
    }


def overlap_resample(
    kernel: np.ndarray,
    input_scale: float,
    output_scale: float,
    size: int,
    phase: tuple[float, float] = (0, 0),
) -> np.ndarray:
    """Integrate piecewise-constant source pixels onto a shifted output grid.

    A source at phase (x, y) lies that many output pixels from the central pixel.
    Unlike the old stress crop this returns flux relative to the full supplied
    template and does not silently renormalize cropped or resampled wings.
    """
    kernel = np.asarray(kernel, float)
    if (
        kernel.ndim != 2
        or any(n % 2 == 0 for n in kernel.shape)
        or size <= 0
        or size % 2 == 0
        or not np.all(np.isfinite([input_scale, output_scale, *phase]))
        or min(input_scale, output_scale) <= 0
        or not np.isfinite(kernel).all()
        or np.any(kernel < 0)
        or kernel.sum() <= 0
    ):
        raise ValueError("invalid PSF resampling inputs")

    def overlap(n: int, offset: float) -> np.ndarray:
        old = (np.arange(n + 1) - n / 2) * input_scale + offset * output_scale
        new = (np.arange(size + 1) - size / 2) * output_scale
        return (
            np.maximum(
                0,
                np.minimum(new[1:, None], old[None, 1:])
                - np.maximum(new[:-1, None], old[None, :-1]),
            )
            / input_scale
        )

    return overlap(kernel.shape[0], phase[1]) @ kernel @ overlap(kernel.shape[1], phase[0]).T


def circular_weights(
    size: int, radius_pixels: float, *, phase: tuple[float, float] = (0, 0), subsamples: int = 16
) -> np.ndarray:
    """Fractional circular pixel area; 1 sample reproduces centre membership."""
    if size <= 0 or size % 2 == 0 or radius_pixels <= 0 or subsamples < 1:
        raise ValueError("require odd size, positive radius and subsamples")
    if not np.all(np.isfinite([radius_pixels, *phase])):
        raise ValueError("nonfinite aperture geometry")
    yy, xx = np.mgrid[:size, :size] - size // 2
    result = np.zeros((size, size), float)
    offsets = (np.arange(subsamples) + 0.5) / subsamples - 0.5
    for dy in offsets:
        for dx in offsets:
            result += np.hypot(xx + dx - phase[0], yy + dy - phase[1]) <= radius_pixels
    return result / subsamples**2


def psf_correction_report(
    directory: Path,
    *,
    radii: tuple[float, ...] = DEFAULT_RADII,
    output_scale: float = 0.063,
    subsamples: int = 16,
    annulus_factors: tuple[float, float] = (2.0, 10 / 3),
    annulus_radii_arcsec: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Evaluate PSF response in matched angular apertures and background annuli."""
    _validate_radii(radii)
    if (
        annulus_radii_arcsec is not None
        and not max(radii) < annulus_radii_arcsec[0] < annulus_radii_arcsec[1]
    ):
        raise ValueError("fixed annulus requires max aperture < inner < outer")
    if not 1 < annulus_factors[0] < annulus_factors[1]:
        raise ValueError("annulus factors must satisfy 1 < inner < outer")
    if not np.isfinite(output_scale) or output_scale <= 0 or subsamples < 1:
        raise ValueError("positive finite output scale and subsamples required")
    result: dict[str, Any] = {
        "experiment": "modeled PSF finite-template aperture response",
        "model_not_observed": True,
        "output_scale_arcsec": output_scale,
        "aperture_radii_arcsec": list(radii),
        "annulus_inner_factor": annulus_factors[0],
        "annulus_outer_factor": annulus_factors[1],
        "fixed_annulus_radii_arcsec": annulus_radii_arcsec,
        "subsamples_per_axis": subsamples,
        "phases_xy_pixels": list(DEFAULT_PHASES),
        "uncertainty_provenance": {
            "phase_envelopes": "deterministic sensitivity range over nine specified pixel phases",
            "integration_comparison": "fractional-area versus pixel-centre membership sensitivity",
            "not_included": [
                "PSF modeling uncertainty",
                "field/visit PSF variation",
                "source extension",
                "calibration uncertainty",
                "flux outside the supplied ~20 arcsec template",
            ],
            "statistical_confidence_intervals": False,
        },
        "filters": [],
        "differential_colors": [],
    }
    responses: dict[str, dict[float, list[dict[str, float]]]] = {}
    outer_radius = (
        annulus_radii_arcsec[1]
        if annulus_radii_arcsec is not None
        else annulus_factors[1] * max(radii)
    )
    measurement_size = 2 * int(np.ceil(outer_radius / output_scale + 2)) + 1
    weight_cache = {}
    for radius in radii:
        inner_r, outer_r = (
            annulus_radii_arcsec
            if annulus_radii_arcsec is not None
            else (annulus_factors[0] * radius, annulus_factors[1] * radius)
        )
        for phase in DEFAULT_PHASES:
            for sampling in (1, subsamples):
                ap = circular_weights(
                    measurement_size, radius / output_scale, phase=phase, subsamples=sampling
                )
                outer = circular_weights(
                    measurement_size, outer_r / output_scale, phase=phase, subsamples=sampling
                )
                inner = circular_weights(
                    measurement_size, inner_r / output_scale, phase=phase, subsamples=sampling
                )
                weight_cache[(radius, phase, sampling)] = (ap, outer - inner)
    for filter_name, filename in (("F277W", "f277wa"), ("F356W", "f356wa"), ("F444W", "f444wa")):
        template, provenance = verified_template(
            directory / f"{filename}_v5.0_mpsf.fits", filter_name
        )
        # Retain the full supplied template with a guard for the shifted source.
        size = (
            2
            * int(
                np.ceil(
                    max(template.shape) * provenance["input_scale_arcsec"] / (2 * output_scale) + 2
                )
            )
            + 1
        )
        phase_images = [
            overlap_resample(template, provenance["input_scale_arcsec"], output_scale, size, phase)
            for phase in DEFAULT_PHASES
        ]
        center_image = phase_images[0]
        yy, xx = np.mgrid[:size, :size] - size // 2
        crop61 = (np.abs(xx) <= 30) & (np.abs(yy) <= 30)
        crop_fraction = float(center_image[crop61].sum())
        item: dict[str, Any] = {
            "provenance": provenance,
            "resampled_shape": [size, size],
            "retained_fraction_full_resample": float(center_image.sum()),
            "old_61px_crop_retained_fraction": crop_fraction,
            "old_crop_normalization_flux_inflation": 1 / crop_fraction,
            "apertures": [],
        }
        responses[filter_name] = {}
        for radius in radii:
            rows = []
            for phase, image in zip(DEFAULT_PHASES, phase_images):
                half = measurement_size // 2
                mid = size // 2
                image = image[mid - half : mid + half + 1, mid - half : mid + half + 1]
                for sampling in (1, subsamples):
                    ap, ann = weight_cache[(radius, phase, sampling)]
                    ee = float(np.sum(image * ap))
                    ann_ee = float(np.sum(image * ann))
                    if ann.sum() <= 0:
                        raise ValueError("annulus has no sampled pixels")
                    response = ee - float(ap.sum() / ann.sum()) * ann_ee
                    if response <= 0:
                        raise ValueError("modeled net aperture response is nonpositive")
                    rows.append(
                        {
                            "phase_x": phase[0],
                            "phase_y": phase[1],
                            "subsamples": sampling,
                            "encircled_energy": ee,
                            "annulus_energy": ann_ee,
                            "net_response": response,
                            "total_flux_multiplier": 1 / response,
                        }
                    )
            fractional = [r for r in rows if r["subsamples"] == subsamples]
            centered = fractional[0]
            responses[filter_name][radius] = fractional
            item["apertures"].append(
                {
                    "radius_arcsec": radius,
                    "centered_fractional": centered,
                    "fractional_ee_phase_range": [
                        min(r["encircled_energy"] for r in fractional),
                        max(r["encircled_energy"] for r in fractional),
                    ],
                    "fractional_response_phase_range": [
                        min(r["net_response"] for r in fractional),
                        max(r["net_response"] for r in fractional),
                    ],
                    "pixel_center_ee_phase_range": [
                        min(r["encircled_energy"] for r in rows if r["subsamples"] == 1),
                        max(r["encircled_energy"] for r in rows if r["subsamples"] == 1),
                    ],
                    "old_crop_renormalized_centered_ee": centered["encircled_energy"]
                    / crop_fraction,
                    "measurements": rows,
                }
            )
        result["filters"].append(item)
    for first, second in combinations(responses, 2):
        for radius in radii:
            a, b = responses[first][radius], responses[second][radius]
            # Same centering phase paired across bands; independent phase extremes also shown.
            paired = [-2.5 * np.log10(x["net_response"] / y["net_response"]) for x, y in zip(a, b)]
            independent = [
                -2.5 * np.log10(x["net_response"] / y["net_response"]) for x in a for y in b
            ]
            result["differential_colors"].append(
                {
                    "bands": [first, second],
                    "radius_arcsec": radius,
                    "observed_minus_intrinsic_color_mag_centered": float(paired[0]),
                    "paired_phase_color_bias_range_mag": [float(min(paired)), float(max(paired))],
                    "independent_phase_color_bias_range_mag": [
                        float(min(independent)),
                        float(max(independent)),
                    ],
                    "correction_to_add_to_aperture_color_mag": float(-paired[0]),
                    "assumption": "identical unresolved source position; one modeled PSF per band",
                }
            )
    return result


def robust_sigma(values: np.ndarray) -> float:
    values = np.asarray(values, float)
    return float(1.482602218505602 * np.median(np.abs(values - np.median(values))))


def source_mask(
    image: np.ndarray,
    valid: np.ndarray,
    *,
    dilation: int = 5,
    threshold: float = 3,
    minimum_area: int = 5,
) -> np.ndarray:
    """Conservative connected positive-source mask; do not sigma clip apertures."""
    if image.shape != valid.shape or image.ndim != 2 or dilation < 0 or threshold <= 0:
        raise ValueError("invalid source-mask inputs")
    if np.count_nonzero(valid) < 20:
        raise ValueError("too few valid sky pixels")
    baseline = float(np.median(image[valid]))
    filled = np.where(valid, image - baseline, 0)
    coverage = gaussian_filter(valid.astype(float), 1)
    smoothed = gaussian_filter(filled, 1) / np.maximum(coverage, 0.01)
    sigma = robust_sigma(smoothed[valid & (coverage > 0.99)])
    if not np.isfinite(sigma) or sigma <= 0:
        raise ValueError("sky noise cannot be estimated from a constant/invalid image")
    segments, _ = label(valid & (coverage > 0.99) & (smoothed > threshold * sigma))
    sizes = np.bincount(segments.ravel())
    selected = sizes >= minimum_area
    selected[0] = False
    masked = selected[segments]
    return binary_dilation(masked, iterations=dilation) if dilation else masked


def _summarize_blanks(rows: list[dict[str, Any]], *, seed: int, bootstrap: int) -> dict[str, Any]:
    if len(rows) < 20:
        return {
            "status": "insufficient_blank_apertures",
            "n_apertures": len(rows),
            "minimum_apertures": 20,
            "noise_multiplier": None,
        }
    flux = np.array([r["net_flux"] for r in rows])
    diagonal = np.array([r["diagonal_sigma"] for r in rows])
    if not np.isfinite(diagonal).all() or np.any(diagonal <= 0):
        raise ValueError("diagonal blank-aperture sigma must be finite and positive")
    normalized = flux / diagonal
    multiplier = robust_sigma(normalized)
    groups = sorted({r["spatial_block"] for r in rows})
    indices = [
        np.array([i for i, r in enumerate(rows) if r["spatial_block"] == group]) for group in groups
    ]
    interval = None
    if len(groups) >= 4 and bootstrap >= 20:
        rng = np.random.default_rng(seed)
        estimates = []
        for _ in range(bootstrap):
            sampled = np.concatenate(
                [indices[i] for i in rng.integers(0, len(groups), len(groups))]
            )
            estimates.append(robust_sigma(normalized[sampled]))
        interval = [float(x) for x in np.quantile(estimates, [0.025, 0.975])]
    aperture = np.array([r["aperture_flux"] for r in rows])
    background = np.array([r["background_contribution"] for r in rows])
    covariance = float(np.cov(aperture, background, ddof=1)[0, 1])
    var_ap = float(np.var(aperture, ddof=1))
    var_bg = float(np.var(background, ddof=1))
    return {
        "status": "measured",
        "n_apertures": len(rows),
        "n_spatial_blocks": len(groups),
        "noise_multiplier": multiplier,
        "noise_multiplier_block_bootstrap_95": interval,
        "ordinary_normalized_sigma": float(np.std(normalized, ddof=1)),
        "median_net_flux": float(np.median(flux)),
        "robust_net_sigma": robust_sigma(flux),
        "ordinary_net_variance": float(np.var(flux, ddof=1)),
        "median_diagonal_sigma": float(np.median(diagonal)),
        "aperture_variance": var_ap,
        "background_contribution_variance": var_bg,
        "aperture_background_covariance": covariance,
        "variance_identity_ap_plus_bg_minus_2cov": var_ap + var_bg - 2 * covariance,
        "aperture_background_correlation": (
            covariance / np.sqrt(var_ap * var_bg) if var_ap > 0 and var_bg > 0 else None
        ),
        "spatial_blocks": [
            {
                "id": group,
                "n_apertures": len(index),
                "normalized_sigma": robust_sigma(normalized[index]) if len(index) >= 5 else None,
            }
            for group, index in zip(groups, indices)
        ],
    }


def blank_aperture_report(
    bundle: dict[str, Any],
    *,
    radii: tuple[float, ...] = (0.126, 0.189, 0.315),
    pixel_scale_arcsec: float | None = None,
    block_size: int = 128,
    mask: np.ndarray | None = None,
    seed: int = 731,
    bootstrap: int = 500,
    synthetic: bool = False,
    max_apertures: int = 1000,
    annulus_factors: tuple[float, float] = (2.0, 10 / 3),
    annulus_radii_arcsec: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Measure fully covered, disjoint blank aperture+annulus footprints.

    Uses celestial separations where WCS exists. Explicit pixel scale is only a
    fallback for synthetic/raw diagnostics. Pixel centre membership exactly
    matches the existing photometry estimator, including annulus covariance.
    Errors must come from explicit ERR or empirical local annulus scatter; WHT
    is a validity mask and is never assumed to be inverse variance.
    """
    _validate_radii(radii)
    if (
        annulus_radii_arcsec is not None
        and not max(radii) < annulus_radii_arcsec[0] < annulus_radii_arcsec[1]
    ):
        raise ValueError("fixed annulus requires max aperture < inner < outer")
    if not 1 < annulus_factors[0] < annulus_factors[1]:
        raise ValueError("annulus factors must satisfy 1 < inner < outer")
    if block_size < 1 or bootstrap < 0 or max_apertures < 20:
        raise ValueError("invalid block/bootstrap/aperture budget")
    image = np.asarray(bundle["sci"], float)
    if image.ndim != 2:
        raise ValueError("blank apertures require a genuine 2D image")
    valid = np.isfinite(image)
    for key in ("validity_mask", "wht", "dq", "err"):
        plane = bundle.get(key)
        if plane is None:
            continue
        plane = np.asarray(plane)
        if plane.shape != image.shape:
            raise ValueError(f"{key} shape must match SCI")
        if key == "validity_mask":
            valid &= plane.astype(bool)
        elif key == "dq":
            valid &= plane == 0
        else:
            valid &= np.isfinite(plane) & (plane > 0)
    bundle = dict(bundle)
    wcs = celestial_wcs(bundle)
    bundle["wcs"] = wcs
    if wcs is not None:
        scales = np.linalg.svd(wcs.pixel_scale_matrix, compute_uv=False) * 3600
        scale = float(min(scales))  # conservative bounding radius for anisotropic grids
    elif pixel_scale_arcsec is not None:
        scale = float(pixel_scale_arcsec)
    else:
        raise ValueError("angular blank apertures require WCS or explicit fallback scale")
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("invalid sky pixel scale")
    outer_radius = (
        annulus_radii_arcsec[1]
        if annulus_radii_arcsec is not None
        else annulus_factors[1] * max(radii)
    )
    margin = int(np.ceil(outer_radius / scale)) + 2
    if mask is None:
        sources = source_mask(image, valid, dilation=int(np.ceil(max(radii) / scale)) + 2)
        mask_method = "3sigma connected smoothed sources; min5 pixels; radius-dependent dilation"
    else:
        sources = np.asarray(mask, bool)
        if sources.shape != image.shape:
            raise ValueError("source mask shape must match SCI")
        mask_method = "explicit supplied source mask"
    blank = valid & ~sources
    step = 2 * margin + 1
    rng = np.random.default_rng(seed)
    # A random translated grid does not overlap supports, unlike random sampling.
    offset_x, offset_y = rng.integers(0, step, 2)
    positions = [
        (x, y)
        for y in range(margin + int(offset_y), image.shape[0] - margin, step)
        for x in range(margin + int(offset_x), image.shape[1] - margin, step)
    ]
    if len(positions) > max_apertures:
        chosen = np.sort(rng.choice(len(positions), max_apertures, replace=False))
        positions = [positions[i] for i in chosen]
    result: dict[str, Any] = {
        "experiment": "blank aperture plus annulus empirical noise",
        "synthetic_control": synthetic,
        "not_an_isolated_drizzle_factor": True,
        "shape": list(image.shape),
        "pixel_scale_arcsec": scale,
        "angular_geometry": "celestial_separation" if wcs else "explicit_scale",
        "mask_method": mask_method,
        "DQ_policy": "all nonzero bits excluded if DQ present",
        "valid_pixels": int(valid.sum()),
        "source_masked_pixels": int((valid & sources).sum()),
        "seed": seed,
        "block_size_pixels": block_size,
        "bootstrap_draws": bootstrap,
        "sampling": "random translated grid, disjoint largest aperture/annulus supports",
        "attempted_positions": len(positions),
        "annulus_inner_factor": annulus_factors[0],
        "annulus_outer_factor": annulus_factors[1],
        "fixed_annulus_radii_arcsec": annulus_radii_arcsec,
        "apertures": [],
        "limits": [
            "Background/confusion/flat errors and covariance are not separately identifiable.",
            "One image and connected source mask cannot establish source-free sky truth.",
            "Spatial block bootstrap is conditional on blocks; long-range covariance remains.",
            "ERR assumed in SCI units, as in calibrated JWST products; WHT only masks coverage.",
            "This measures sky-limited uncertainty, not source Poisson or calibration uncertainty.",
            "Multiplier belongs to this image, aperture, annulus, mask and noise baseline only.",
        ],
    }
    for radius in radii:
        inner_r, outer_r = (
            annulus_radii_arcsec
            if annulus_radii_arcsec is not None
            else (annulus_factors[0] * radius, annulus_factors[1] * radius)
        )
        rows = []
        for x, y in positions:
            xx, yy = np.meshgrid(
                np.arange(x - margin, x + margin + 1), np.arange(y - margin, y + margin + 1)
            )
            if wcs is not None:
                center = wcs.pixel_to_world(x, y)
                distance = wcs.pixel_to_world(xx, yy).separation(center).arcsec
            else:
                distance = np.hypot(xx - x, yy - y) * scale
            ap = distance <= radius
            ann = (distance >= inner_r) & (distance <= outer_r)
            support = ap | ann
            if (
                not np.any(ap)
                or np.count_nonzero(ann) < 2
                or not np.all(blank[yy[support], xx[support]])
            ):
                continue
            values = image[yy, xx]
            calibration = flux_density_factors(bundle, xx, yy)
            factors = calibration["factor_jy"]
            if factors is None:
                factors = np.ones(values.shape)
            coefficients = np.where(ap, factors, 0)
            coefficients[ann] = -float(np.sum(factors[ap])) / int(ann.sum())
            if bundle.get("err") is not None:
                errors = np.asarray(bundle["err"])[yy, xx]
                variance = float(np.sum((coefficients[support] * errors[support]) ** 2))
                noise_baseline = "ERR diagonal plus background-mean variance"
            else:
                variance = float(np.var(values[ann], ddof=1) * np.sum(coefficients**2))
                noise_baseline = "local annulus empirical diagonal"
            if not np.isfinite(variance) or variance <= 0:
                continue
            aperture_flux = float(np.sum(values[ap] * factors[ap]))
            background_contribution = float(np.mean(values[ann]) * np.sum(factors[ap]))
            rows.append(
                {
                    "x": x,
                    "y": y,
                    "spatial_block": f"{x // block_size}:{y // block_size}",
                    "aperture_flux": aperture_flux,
                    "background_contribution": background_contribution,
                    "net_flux": aperture_flux - background_contribution,
                    "diagonal_sigma": float(np.sqrt(variance)),
                    "flux_unit": "Jy"
                    if calibration["status"] == "calibrated"
                    else calibration["input_unit"] or "unknown raw SCI unit",
                    "calibration_status": calibration["status"],
                    "noise_baseline": noise_baseline,
                    "n_aperture_pixels": int(ap.sum()),
                    "n_annulus_pixels": int(ann.sum()),
                }
            )
        result["apertures"].append(
            {
                "radius_arcsec": radius,
                **_summarize_blanks(rows, seed=seed, bootstrap=bootstrap),
                "measurements": rows,
            }
        )
    return result


def validate_photometry_transfer(
    bundle: dict[str, Any], report: dict[str, Any], *, checks_per_radius: int = 4
) -> list[dict[str, Any]]:
    """Check the same actual blank centres against the production photometer.

    This is an operator/calibration transfer check, not independent sky truth.
    Reports numerical residuals without replacing either stored measurement.
    """
    from tools.jwst.photometry import extract_photometry

    checks = []
    for aperture in report["apertures"]:
        radius = aperture["radius_arcsec"]
        annulus = report["fixed_annulus_radii_arcsec"] or (
            radius * report["annulus_inner_factor"],
            radius * report["annulus_outer_factor"],
        )
        for row in aperture["measurements"][:checks_per_radius]:
            actual = extract_photometry(
                image_data=bundle,
                x=row["x"],
                y=row["y"],
                aperture_radius_arcsec=radius,
                background_annulus_inner_radius_arcsec=annulus[0],
                background_annulus_outer_radius_arcsec=annulus[1],
            )
            reference_flux = actual["background_subtracted_flux_jy"]
            reference_error = actual["flux_error_jy"]
            flux_delta = row["net_flux"] - reference_flux if reference_flux is not None else None
            sigma_ratio = row["diagonal_sigma"] / reference_error if reference_error else None
            matched = (
                row["n_aperture_pixels"] == actual["valid_pixel_count"]
                and row["n_annulus_pixels"] == actual["annulus_pixel_count"]
                and flux_delta is not None
                and abs(flux_delta) < 1e-15
                and sigma_ratio is not None
                and abs(sigma_ratio - 1) < 1e-8
            )
            checks.append(
                {
                    "radius_arcsec": radius,
                    "x": row["x"],
                    "y": row["y"],
                    "production_flux_jy": reference_flux,
                    "flux_residual_jy": flux_delta,
                    "diagonal_sigma_ratio": sigma_ratio,
                    "matched_operator": matched,
                }
            )
    return checks


def read_image(path: Path) -> dict[str, Any]:
    """Strict named-HDU read: never infer ERR from an unrelated extension."""
    with fits.open(path, memmap=False) as hdus:
        if "SCI" not in hdus:
            raise ValueError("real image requires explicitly named SCI extension")
        hdu = hdus["SCI"]
        bundle = {
            "sci": np.asarray(hdu.data, float),
            "header": hdu.header.copy(),
            "primary_header": hdus[0].header.copy(),
        }
        if bundle["sci"].ndim != 2:
            raise ValueError("blank sky estimator does not collapse spectral cubes")
        for name in ("ERR", "WHT", "DQ"):
            if name in hdus and hdus[name].data is not None:
                bundle[name.lower()] = np.asarray(hdus[name].data)
    return bundle


def synthetic_noise_controls(*, seed: int = 731) -> dict[str, Any]:
    """Known white/convolved Gaussian controls, never evidence about actual sky."""
    rng = np.random.default_rng(seed)
    white = rng.normal(size=(768, 768))
    kernel = np.outer([1.0, 2.0, 1.0], [1.0, 2.0, 1.0])
    kernel /= np.sqrt(np.sum(kernel**2))
    correlated = fftconvolve(white, kernel, mode="same")
    controls = []
    for name, image in (("white", white), ("3x3 correlated", correlated)):
        report = blank_aperture_report(
            {"sci": image, "err": np.ones_like(image), "header": {"BUNIT": "nJy"}},
            radii=(0.126, 0.189, 0.315),
            pixel_scale_arcsec=0.063,
            mask=np.zeros(image.shape, bool),
            seed=seed,
            synthetic=True,
            bootstrap=500,
        )
        report["control_name"] = name
        report["known_pixel_variance"] = 1.0
        report["known_noise_kernel"] = (
            [[float(x) for x in row] for row in kernel] if name != "white" else [[1.0]]
        )
        controls.append(report)
    return {"synthetic_control": True, "seed": seed, "controls": controls}


def render_report(report: dict[str, Any]) -> str:
    lines = [
        "# PSF aperture response and empirical noise diagnostics",
        "",
        "The PSF results use verified public **modeled** templates. Noise controls are",
        "synthetic unless an actual-image receipt is explicitly listed. Sensitivity",
        "ranges are not observational uncertainty confidence intervals.",
        "",
    ]
    psf = report["psf"]
    command = report.get("command_parameters", {})
    repro = "python -m discovery.psf_noise --psf-directory data_sources/pilot"
    if command:
        repro += " --radii " + " ".join(str(r) for r in command["radii_arcsec"])
        if command["fixed_annulus_radii_arcsec"]:
            repro += " --annulus-radii " + " ".join(
                str(r) for r in command["fixed_annulus_radii_arcsec"]
            )
        repro += " --output-scale " + str(command["output_scale_arcsec"])
        for image_path in command["image_paths"]:
            repro += " --image data/original_round2/" + Path(image_path).name
    lines += [
        "## Finite-template response near a common 0.189 arcsec radius",
        "",
        "An explicitly recorded background annulus is subtracted. These",
        "point-source corrections do not recover total extended-galaxy flux.",
        "",
        "| Band | Aperture EE | Net response | Total multiplier | Old 61px crop retained |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for item in psf["filters"]:
        row = min(item["apertures"], key=lambda x: abs(x["radius_arcsec"] - 0.189))
        centered = row["centered_fractional"]
        lines.append(
            f"| {item['provenance']['filter']} | {centered['encircled_energy']:.5f} | "
            f"{centered['net_response']:.5f} | {centered['total_flux_multiplier']:.5f} | "
            f"{item['old_61px_crop_retained_fraction']:.5f} |"
        )
    lines += [
        "",
        "## Uncorrected point-source color biases",
        "",
        "Reported value is aperture color minus intrinsic color; subtract it to",
        "correct the modeled unresolved-source color. The sign matters.",
        "",
        "| Bands | Radius arcsec | Centered bias mag | Paired phase sensitivity range |",
        "| --- | ---: | ---: | --- |",
    ]
    for row in psf["differential_colors"]:
        lo, hi = row["paired_phase_color_bias_range_mag"]
        lines.append(
            f"| {' − '.join(row['bands'])} | {row['radius_arcsec']:.3f} | "
            f"{row['observed_minus_intrinsic_color_mag_centered']:.5f} | {lo:.5f} to {hi:.5f} |"
        )
    lines += [
        "",
        "## Noise calibration controls",
        "",
        "| Input | Radius arcsec | Blanks | Robust empirical / diagonal sigma | Block 95% interval |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    controls = report["synthetic_noise"]["controls"] + report.get("real_images", [])
    for control in controls:
        name = control.get("control_name", control.get("input_path", "real image"))
        for row in control["apertures"]:
            ratio = row["noise_multiplier"]
            interval = row.get("noise_multiplier_block_bootstrap_95")
            ratio_text = f"{ratio:.3f}" if ratio is not None else "unavailable"
            ci_text = f"{interval[0]:.3f}–{interval[1]:.3f}" if interval else "unavailable"
            lines.append(
                f"| {name} | {row['radius_arcsec']:.3f} | {row['n_apertures']} | {ratio_text} | {ci_text} |"
            )
    lines += [
        "",
        "The multiplier is fitted to normalized net blank fluxes, includes the",
        "aperture–annulus covariance, and belongs to this image/mask/aperture/noise",
        "baseline. It is not an isolated or universal drizzle factor. Disjoint",
        "footprints avoid direct aperture overlap; spatial blocks address some",
        "remaining dependence. Source confusion and large-scale backgrounds remain.",
        "",
        "## Reproduce",
        "",
        "```bash",
        repro,
        "# Add --image path/to/calibrated_i2d.fits for an actual sky estimate.",
        "```",
        "",
        "JSON retains all phase trials, blank positions, diagonal errors, covariance",
        "identity checks, hashes and deterministic seeds. PSF modeling, field",
        "variation, outside-template wings, source extension and absolute calibration",
        "are not quantified by the deterministic sensitivity ranges.",
        "",
    ]
    if not report.get("real_images"):
        lines += [
            "No actual sky image was provisioned for this report. The synthetic",
            "controls verify estimator response; they do not measure JWST drizzle noise.",
            "",
        ]
    if report.get("real_images"):
        checks = [
            c for image in report["real_images"] for c in image.get("operator_transfer_checks", [])
        ]
        lines += [
            f"Production photometry transfer: {sum(c['matched_operator'] for c in checks)}/{len(checks)} "
            "blank positions agree in pixel masks, calibrated flux and diagonal sigma.",
            "",
        ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--psf-directory", type=Path, required=True)
    parser.add_argument("--image", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, default=Path("research_output/psf_noise.json"))
    parser.add_argument("--report", type=Path, default=Path("research_output/PSF_NOISE.md"))
    parser.add_argument("--seed", type=int, default=731)
    parser.add_argument("--radii", type=float, nargs="+", default=list(DEFAULT_RADII))
    parser.add_argument("--annulus-radii", type=float, nargs=2)
    parser.add_argument("--output-scale", type=float, default=0.063)
    args = parser.parse_args()
    report = {
        "schema_version": 1,
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "psf": psf_correction_report(
            args.psf_directory,
            radii=tuple(args.radii),
            output_scale=args.output_scale,
            annulus_radii_arcsec=tuple(args.annulus_radii) if args.annulus_radii else None,
        ),
        "synthetic_noise": synthetic_noise_controls(seed=args.seed),
        "real_images": [],
    }
    for path in args.image:
        image_report = blank_aperture_report(
            read_image(path),
            seed=args.seed,
            radii=tuple(args.radii),
            annulus_radii_arcsec=tuple(args.annulus_radii) if args.annulus_radii else None,
        )
        image_report["operator_transfer_checks"] = validate_photometry_transfer(
            read_image(path), image_report
        )
        image_report["input_path"] = str(path)
        image_report["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        image_report["bytes"] = path.stat().st_size
        report["real_images"].append(image_report)
    report["command_parameters"] = {
        "psf_directory": str(args.psf_directory),
        "image_paths": [str(p) for p in args.image],
        "radii_arcsec": args.radii,
        "fixed_annulus_radii_arcsec": args.annulus_radii,
        "output_scale_arcsec": args.output_scale,
        "seed": args.seed,
    }
    for path in (args.output, args.report):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    args.report.write_text(render_report(report))
    print(
        f"Wrote PSF response, synthetic controls and {len(args.image)} actual-image noise reports"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
