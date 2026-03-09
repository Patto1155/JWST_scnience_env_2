"""JWST photometry tools."""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

try:
    from tools.jwst.fits_loader import load_fits_bundle, smart_load_data

    FITS_LOADER_AVAILABLE = True
except ImportError:
    FITS_LOADER_AVAILABLE = False


def _collapse_to_2d(array: Optional[np.ndarray]) -> Optional[np.ndarray]:
    """Collapse higher-dimensional arrays to 2D while preserving NaNs."""
    if array is None:
        return None

    arr = np.asarray(array, dtype=float)
    if arr.ndim <= 2:
        return arr

    collapse_axes = tuple(range(arr.ndim - 2))
    return np.nanmean(arr, axis=collapse_axes)


def _load_measurement_inputs(
    image_data: Any,
    strict_data: Optional[bool],
) -> Dict[str, Any]:
    """Load image, error, weight, and mask inputs for photometry."""
    if isinstance(image_data, dict) and "sci" in image_data:
        bundle = image_data
        return {
            "image": _collapse_to_2d(bundle["sci"]),
            "err": _collapse_to_2d(bundle.get("err")),
            "wht": _collapse_to_2d(bundle.get("wht")),
            "validity_mask": _collapse_to_2d(bundle.get("validity_mask")),
            "dataset_name": bundle.get("dataset_name"),
            "file_path": bundle.get("file_path"),
        }

    if isinstance(image_data, str):
        if not FITS_LOADER_AVAILABLE:
            raise ImportError("FITS loader not available")
        bundle = load_fits_bundle(image_data)
        return {
            "image": _collapse_to_2d(bundle["sci"]),
            "err": _collapse_to_2d(bundle.get("err")),
            "wht": _collapse_to_2d(bundle.get("wht")),
            "validity_mask": _collapse_to_2d(bundle.get("validity_mask")),
            "dataset_name": bundle["dataset_name"],
            "file_path": bundle["file_path"],
        }

    if image_data is None:
        if FITS_LOADER_AVAILABLE:
            image = smart_load_data(image_data, strict_data=strict_data)
        else:
            h, w = 100, 100
            cx, cy = w // 2, h // 2
            y_arr, x_arr = np.ogrid[:h, :w]
            r_sq = (x_arr - cx) ** 2 + (y_arr - cy) ** 2
            image = 1000 * np.exp(-r_sq / (2 * 10 ** 2)) + np.random.normal(0, 10, (h, w))
        arr = _collapse_to_2d(image)
        return {
            "image": arr,
            "err": None,
            "wht": None,
            "validity_mask": np.isfinite(arr),
            "dataset_name": None,
            "file_path": None,
        }

    arr = _collapse_to_2d(np.asarray(image_data, dtype=float))
    return {
        "image": arr,
        "err": None,
        "wht": None,
        "validity_mask": np.isfinite(arr),
        "dataset_name": None,
        "file_path": None,
    }


def extract_photometry(
    image_data: Any = None,
    x: float = None,
    y: float = None,
    aperture_radius: float = 5.0,
    background_annulus_inner_radius: float = 6.0,
    background_annulus_outer_radius: float = 10.0,
    strict_data: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Extract photometry from JWST image data.

    Returns a backward-compatible raw aperture flux plus background-subtracted
    and uncertainty-aware quantities for scientific candidate vetting.
    """
    loaded = _load_measurement_inputs(image_data, strict_data=strict_data)
    image = loaded["image"]
    err = loaded["err"]
    wht = loaded["wht"]
    validity_mask = loaded["validity_mask"]

    if image is None:
        raise ValueError("No image data available for photometry")

    if validity_mask is None:
        validity_mask = np.isfinite(image)
    else:
        validity_mask = np.asarray(validity_mask, dtype=bool)

    h, w = image.shape
    if x is None:
        x = w / 2
    if y is None:
        y = h / 2

    if (
        float(x) + float(aperture_radius) < 0
        or float(y) + float(aperture_radius) < 0
        or float(x) - float(aperture_radius) >= w
        or float(y) - float(aperture_radius) >= h
    ):
        result = {
            "flux": 0.0,
            "magnitude": None,
            "background_subtracted_flux": 0.0,
            "background_subtracted_magnitude": None,
            "flux_error": 0.0,
            "snr": None,
            "background_mean": 0.0,
            "background_std": 0.0,
            "coverage_fraction": 0.0,
            "x": float(x),
            "y": float(y),
            "aperture_radius": float(aperture_radius),
            "background_annulus_inner_radius": float(background_annulus_inner_radius),
            "background_annulus_outer_radius": float(background_annulus_outer_radius),
            "pixels_in_aperture": 0,
            "valid_pixel_count": 0,
            "annulus_pixel_count": 0,
            "dataset_name": loaded["dataset_name"],
            "file_path": loaded["file_path"],
        }
        if wht is not None and wht.shape == image.shape:
            result["mean_weight"] = 0.0
        return result

    footprint_radius = float(
        max(
            aperture_radius,
            background_annulus_inner_radius,
            background_annulus_outer_radius,
        )
    )
    x_min = max(int(np.floor(float(x) - footprint_radius)), 0)
    x_max = min(int(np.ceil(float(x) + footprint_radius)) + 1, w)
    y_min = max(int(np.floor(float(y) - footprint_radius)), 0)
    y_max = min(int(np.ceil(float(y) + footprint_radius)) + 1, h)

    image_window = image[y_min:y_max, x_min:x_max]
    mask_window = validity_mask[y_min:y_max, x_min:x_max]
    err_window = err[y_min:y_max, x_min:x_max] if err is not None and err.shape == image.shape else None
    wht_window = wht[y_min:y_max, x_min:x_max] if wht is not None and wht.shape == image.shape else None

    y_arr, x_arr = np.ogrid[y_min:y_max, x_min:x_max]
    r_sq = (x_arr - float(x)) ** 2 + (y_arr - float(y)) ** 2
    aperture_mask = r_sq <= float(aperture_radius) ** 2
    annulus_mask = (
        (r_sq >= float(background_annulus_inner_radius) ** 2)
        & (r_sq <= float(background_annulus_outer_radius) ** 2)
    )

    aperture_valid = aperture_mask & mask_window
    annulus_valid = annulus_mask & mask_window

    aperture_values = image_window[aperture_valid]
    annulus_values = image_window[annulus_valid]

    pixels_in_aperture = int(np.sum(aperture_mask))
    valid_pixel_count = int(np.sum(aperture_valid))
    annulus_pixel_count = int(np.sum(annulus_valid))
    coverage_fraction = (
        float(valid_pixel_count / pixels_in_aperture) if pixels_in_aperture > 0 else 0.0
    )

    flux = float(np.nansum(aperture_values)) if valid_pixel_count > 0 else 0.0
    background_mean = (
        float(np.nanmean(annulus_values)) if annulus_pixel_count > 0 else 0.0
    )
    background_std = (
        float(np.nanstd(annulus_values)) if annulus_pixel_count > 1 else 0.0
    )
    background_subtracted_flux = flux - (background_mean * valid_pixel_count)

    if err_window is not None:
        aperture_err = np.asarray(err_window, dtype=float)[aperture_valid]
        aperture_variance = float(np.nansum(np.square(aperture_err)))
    else:
        aperture_variance = 0.0

    background_variance = float((background_std ** 2) * valid_pixel_count)
    flux_error = float(np.sqrt(max(aperture_variance + background_variance, 0.0)))

    snr = None
    if flux_error > 0:
        snr = float(background_subtracted_flux / flux_error)

    zeropoint = 25.0
    magnitude = -2.5 * np.log10(flux) + zeropoint if flux > 0 else None
    background_subtracted_magnitude = (
        -2.5 * np.log10(background_subtracted_flux) + zeropoint
        if background_subtracted_flux > 0
        else None
    )

    result = {
        "flux": float(flux),
        "magnitude": float(magnitude) if magnitude is not None else None,
        "background_subtracted_flux": float(background_subtracted_flux),
        "background_subtracted_magnitude": (
            float(background_subtracted_magnitude)
            if background_subtracted_magnitude is not None
            else None
        ),
        "flux_error": float(flux_error),
        "snr": snr,
        "background_mean": float(background_mean),
        "background_std": float(background_std),
        "coverage_fraction": float(coverage_fraction),
        "x": float(x),
        "y": float(y),
        "aperture_radius": float(aperture_radius),
        "background_annulus_inner_radius": float(background_annulus_inner_radius),
        "background_annulus_outer_radius": float(background_annulus_outer_radius),
        "pixels_in_aperture": pixels_in_aperture,
        "valid_pixel_count": valid_pixel_count,
        "annulus_pixel_count": annulus_pixel_count,
        "dataset_name": loaded["dataset_name"],
        "file_path": loaded["file_path"],
    }

    if wht_window is not None:
        result["mean_weight"] = float(np.nanmean(wht_window[aperture_valid])) if valid_pixel_count > 0 else 0.0

    return result


def compute_color_index(
    flux_band1: float,
    flux_band2: float,
) -> Dict[str, Any]:
    """
    Compute color index from two band fluxes.

    Args:
        flux_band1: Flux in first band
        flux_band2: Flux in second band

    Returns:
        Dictionary with color index and related metrics
    """
    if flux_band1 <= 0 or flux_band2 <= 0:
        return {
            "color_index": None,
            "flux_ratio": None,
            "error": "Invalid flux values (must be positive)",
        }

    flux_ratio = flux_band1 / flux_band2
    color_index = -2.5 * np.log10(flux_ratio)

    return {
        "color_index": float(color_index),
        "flux_ratio": float(flux_ratio),
        "band1_flux": float(flux_band1),
        "band2_flux": float(flux_band2),
    }
