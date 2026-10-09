"""Joint valid sky area measured on the reference image's pixel-centre grid.

This is a coverage diagnostic, not an aperture-safe survey effective area. A
valid centre in every filter need not have a fully covered surrounding aperture.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from tools.jwst.flux_calibration import celestial_wcs, pixel_solid_angle_sr

SR_TO_ARCSEC2 = (180.0 * 3600.0 / np.pi) ** 2


def _sample_valid_pixels(bundle: dict[str, Any], x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Inspect only requested native pixels, avoiding full-mask copies for ranking."""
    science = np.asarray(bundle["sci"])
    if science.ndim != 2:
        raise ValueError("Coverage requires a two-dimensional science image")
    valid = np.asarray(bundle["validity_mask"], dtype=bool)[y, x] & np.isfinite(science[y, x])
    for plane in ("err", "wht"):
        values = bundle.get(plane)
        if values is not None:
            values = np.asarray(values)[y, x]
            valid &= np.isfinite(values) & (values > 0)
    return valid


def sampled_joint_valid_fraction(
    reference: dict[str, Any],
    comparisons: list[dict[str, Any]],
    *,
    grid_size: int = 40,
) -> float:
    """Bounded deterministic ranking score, not a measured final survey area.

    A reference-grid sample tests actual WCS registration and native validity
    simultaneously in all supplied bands. Every sampled reference centre is in
    the denominator, including invalid reference pixels. Exact selected-image
    pixel-centre area should subsequently use ``joint_valid_coverage``.
    """
    if grid_size <= 0:
        raise ValueError("grid_size must be positive")
    reference_wcs = celestial_wcs(reference)
    if reference_wcs is None:
        raise ValueError("Reference image lacks a celestial WCS")
    height, width = np.asarray(reference["sci"]).shape
    x, y = np.meshgrid(
        np.linspace(0, width - 1, min(grid_size, width)).astype(int),
        np.linspace(0, height - 1, min(grid_size, height)).astype(int),
    )
    x, y = x.ravel(), y.ravel()
    valid = _sample_valid_pixels(reference, x, y)
    longitude, latitude = reference_wcs.pixel_to_world_values(x, y)
    for bundle in comparisons:
        wcs = celestial_wcs(bundle)
        if wcs is None:
            raise ValueError("Comparison image lacks a celestial WCS")
        bh, bw = np.asarray(bundle["sci"]).shape
        bx, by = wcs.world_to_pixel_values(longitude, latitude)
        inside = np.isfinite(bx) & np.isfinite(by) & (bx >= -0.5) & (bx < bw - 0.5)
        inside &= (by >= -0.5) & (by < bh - 0.5)
        band_valid = np.zeros(valid.size, dtype=bool)
        band_valid[inside] = _sample_valid_pixels(
            bundle, np.floor(bx[inside] + 0.5).astype(int), np.floor(by[inside] + 0.5).astype(int)
        )
        valid &= band_valid
    return float(valid.mean())


def scientific_valid_mask(bundle: dict[str, Any]) -> np.ndarray:
    """Require finite SCI and available valid errors, in addition to loader masks."""
    science = np.asarray(bundle["sci"])
    if science.ndim != 2:
        raise ValueError("Coverage requires a two-dimensional science image")
    mask = np.asarray(bundle["validity_mask"], dtype=bool).copy()
    if mask.shape != science.shape:
        raise ValueError("Science and validity mask shapes disagree")
    mask &= np.isfinite(science)
    errors = bundle.get("err")
    if errors is not None:
        errors = np.asarray(errors)
        if errors.shape != science.shape:
            raise ValueError("Science and ERR shapes disagree")
        mask &= np.isfinite(errors) & (errors > 0)
    return mask


def joint_valid_coverage(
    reference: dict[str, Any],
    comparisons: dict[str, dict[str, Any]],
    *,
    chunk_pixels: int = 65536,
) -> dict[str, Any]:
    """Integrate reference pixel areas whose centres map to valid other pixels.

    Native comparison pixel membership is nearest pixel centre, with explicit
    half-pixel footprint boundaries. WCS is never replaced by a nominal scale.
    No source-detection, PSF, aperture-edge or depth completeness is implied.
    """
    if chunk_pixels <= 0:
        raise ValueError("chunk_pixels must be positive")
    reference_wcs = celestial_wcs(reference)
    if reference_wcs is None:
        raise ValueError("Reference image lacks a celestial WCS")
    ref_mask = scientific_valid_mask(reference)
    comparison_info = {}
    for name, bundle in comparisons.items():
        wcs = celestial_wcs(bundle)
        if wcs is None:
            raise ValueError(f"Comparison {name} lacks a celestial WCS")
        comparison_info[name] = (wcs, scientific_valid_mask(bundle))

    total_valid = int(ref_mask.sum())
    height, width = ref_mask.shape
    reference_area = 0.0
    joint_area = 0.0
    joint_count = 0
    by_band = {name: {"pixel_count": 0, "area_arcsec2": 0.0} for name in comparisons}
    for start in range(0, height * width, chunk_pixels):
        flat = np.arange(start, min(start + chunk_pixels, height * width))
        flat = flat[ref_mask.ravel()[flat]]
        if not flat.size:
            continue
        y, x = np.divmod(flat, width)
        longitude, latitude = reference_wcs.pixel_to_world_values(x, y)
        areas = pixel_solid_angle_sr(reference_wcs, x, y) * SR_TO_ARCSEC2
        reference_area += float(areas.sum())
        joint = np.ones(flat.size, dtype=bool)
        for name, (wcs, mask) in comparison_info.items():
            bx, by = wcs.world_to_pixel_values(longitude, latitude)
            bx, by = np.asarray(bx), np.asarray(by)
            inside = (
                np.isfinite(bx)
                & np.isfinite(by)
                & (bx >= -0.5)
                & (bx < mask.shape[1] - 0.5)
                & (by >= -0.5)
                & (by < mask.shape[0] - 0.5)
            )
            valid = np.zeros(flat.size, dtype=bool)
            ix = np.floor(bx[inside] + 0.5).astype(int)
            iy = np.floor(by[inside] + 0.5).astype(int)
            valid[inside] = mask[iy, ix]
            by_band[name]["pixel_count"] += int(valid.sum())
            by_band[name]["area_arcsec2"] += float(areas[valid].sum())
            joint &= valid
        joint_count += int(joint.sum())
        joint_area += float(areas[joint].sum())
    return {
        "method": "reference_pixel_centres_with_native_validity_and_spherical_pixel_areas",
        "reference_shape": [height, width],
        "reference_valid_pixel_count": total_valid,
        "reference_valid_area_arcsec2": reference_area,
        "joint_valid_pixel_count": joint_count,
        "joint_valid_fraction_of_reference_valid": joint_count / total_valid
        if total_valid
        else None,
        "joint_valid_area_arcsec2": joint_area,
        "joint_valid_area_arcmin2": joint_area / 3600.0,
        "comparison_coverage": by_band,
        "limitations": [
            "Reference-grid pixel-centre discretization, not exact fractional reprojection",
            "Area is not aperture-safe, PSF-corrected or depth/completeness weighted",
            "Uses SCI/ERR/WHT validity; upstream DQ policy must be documented separately",
        ],
    }
