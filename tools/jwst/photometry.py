"""JWST aperture photometry with explicit physical units and measurability."""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord

from tools.jwst.flux_calibration import ab_magnitude, celestial_wcs, flux_density_factors

try:
    from tools.jwst.fits_loader import load_fits_bundle, smart_load_data
    FITS_LOADER_AVAILABLE = True
except ImportError:
    FITS_LOADER_AVAILABLE = False


def _load_measurement_inputs(image_data: Any, strict_data: Optional[bool]) -> Dict[str, Any]:
    if isinstance(image_data, dict) and "sci" in image_data:
        bundle = dict(image_data)
    elif isinstance(image_data, str):
        if not FITS_LOADER_AVAILABLE:
            raise ImportError("FITS loader not available")
        bundle = load_fits_bundle(image_data)
    else:
        if image_data is None:
            if not FITS_LOADER_AVAILABLE:
                raise ValueError("No image data available for photometry")
            image_data = smart_load_data(image_data, strict_data=strict_data)
        bundle = {"sci": np.asarray(image_data, dtype=float)}
    image = np.asarray(bundle["sci"], dtype=float)
    if image.ndim != 2 or int((bundle.get("header") or {}).get("NAXIS", 2)) > 2:
        raise ValueError("Photometry requires a 2D image; integration/cube averaging needs a separate uncertainty model")
    bundle["sci"] = image
    return bundle


def _uncertainty(image: np.ndarray, err: np.ndarray | None, aperture: np.ndarray,
                 annulus: np.ndarray, coefficients: np.ndarray) -> tuple[float | None, str]:
    """Variance of sum(c_i SCI_i) - sum(c_i) * mean(annulus SCI).

    No covariance/correlation correction is inferred from the ERR or WHT arrays.
    The caller exposes this limitation for drizzled images.
    """
    n_annulus = int(np.sum(annulus))
    if not np.any(aperture) or n_annulus == 0:
        return None, "missing_aperture_or_background"
    ca = coefficients[aperture]
    if err is not None:
        ea, eb = err[aperture], err[annulus]
        if np.any(~np.isfinite(ea)) or np.any(ea < 0) or np.any(~np.isfinite(eb)) or np.any(eb < 0):
            return None, "invalid_err"
        source_variance = np.sum((ca * ea) ** 2)
        mean_variance = np.sum(eb ** 2) / n_annulus ** 2
        method = "err_diagonal_plus_background_mean"
    elif n_annulus >= 2:
        variance = float(np.var(image[annulus], ddof=1))
        source_variance = variance * np.sum(ca ** 2)
        mean_variance = variance / n_annulus
        method = "annulus_empirical_diagonal"
    else:
        return None, "insufficient_annulus_for_noise"
    value = float(np.sqrt(source_variance + np.sum(ca) ** 2 * mean_variance))
    # A noiseless synthetic image does not establish zero observational error.
    return (value if value > 0 else None), (method if value > 0 else "zero_noise_not_estimated")


def extract_photometry(
    image_data: Any = None,
    x: float = None,
    y: float = None,
    aperture_radius: float = 5.0,
    background_annulus_inner_radius: float = 6.0,
    background_annulus_outer_radius: float = 10.0,
    strict_data: Optional[bool] = None,
    aperture_radius_arcsec: float | None = None,
    background_annulus_inner_radius_arcsec: float | None = None,
    background_annulus_outer_radius_arcsec: float | None = None,
    ra_deg: float | None = None,
    dec_deg: float | None = None,
) -> Dict[str, Any]:
    """Measure raw sums and, when BUNIT supports it, calibrated Jy/AB values.

    Angular aperture parameters use actual celestial separations. Reuse the same
    RA/Dec and angular radii across filters for matched sky apertures. Apertures
    use pixel-centre membership, not subpixel fractional weights or PSF matching.
    Unknown calibration fails closed (physical values None, raw sums retained).
    """
    bundle = _load_measurement_inputs(image_data, strict_data)
    image = bundle["sci"]
    h, w = image.shape
    wcs = celestial_wcs(bundle)
    if (ra_deg is None) != (dec_deg is None):
        raise ValueError("ra_deg and dec_deg must be specified together")
    if ra_deg is not None:
        if wcs is None:
            raise ValueError("Sky coordinates require a celestial WCS")
        if x is not None or y is not None:
            raise ValueError("Specify either sky coordinates or pixel coordinates")
        x, y = wcs.world_to_pixel(SkyCoord(ra_deg, dec_deg, unit="deg"))
    x, y = float(w / 2 if x is None else x), float(h / 2 if y is None else y)
    radii = np.array([aperture_radius, background_annulus_inner_radius, background_annulus_outer_radius], dtype=float)
    angular_radii = None
    if aperture_radius_arcsec is not None:
        if wcs is None:
            raise ValueError("Angular apertures require a celestial WCS")
        angular_radii = np.array([
            aperture_radius_arcsec,
            background_annulus_inner_radius_arcsec if background_annulus_inner_radius_arcsec is not None else aperture_radius_arcsec * 1.2,
            background_annulus_outer_radius_arcsec if background_annulus_outer_radius_arcsec is not None else aperture_radius_arcsec * 2.0,
        ], dtype=float)
        check_radii = angular_radii
    else:
        if background_annulus_inner_radius_arcsec is not None or background_annulus_outer_radius_arcsec is not None:
            raise ValueError("Angular annulus requires aperture_radius_arcsec")
        check_radii = radii
    if not np.all(np.isfinite([x, y])) or not np.all(np.isfinite(check_radii)):
        raise ValueError("Coordinates and aperture radii must be finite")
    if not (0 < check_radii[0] < check_radii[1] < check_radii[2]):
        raise ValueError("Require 0 < aperture radius < inner annulus < outer annulus")

    center = None
    if angular_radii is not None:
        center = wcs.pixel_to_world(x, y)
        boundary = center.directional_offset_by(np.linspace(0, 360, 129) * u.deg, angular_radii[-1] * u.arcsec)
        bx, by = wcs.world_to_pixel(boundary)
        footprint_radius = float(max(np.max(np.abs(bx - x)), np.max(np.abs(by - y)))) + 2
        if not np.isfinite(footprint_radius):
            raise ValueError("Angular aperture does not project to a finite image footprint")
        # Informational pixel radii only; angular mask below is authoritative.
        scales = np.linalg.svd(wcs.pixel_scale_matrix, compute_uv=False) * 3600
        radii = angular_radii / np.sqrt(np.prod(scales))
    else:
        footprint_radius = float(radii[-1])
    x0, x1 = int(np.floor(x - footprint_radius)), int(np.ceil(x + footprint_radius)) + 1
    y0, y1 = int(np.floor(y - footprint_radius)), int(np.ceil(y + footprint_radius)) + 1
    xx, yy = np.meshgrid(np.arange(x0, x1), np.arange(y0, y1))
    if angular_radii is not None:
        distance = wcs.pixel_to_world(xx, yy).separation(center).arcsec
        mask_radii = angular_radii
    else:
        distance = np.hypot(xx - x, yy - y)
        mask_radii = radii
    aperture_full = distance <= mask_radii[0]
    annulus_full = (distance >= mask_radii[1]) & (distance <= mask_radii[2])
    total_pixels = int(np.sum(aperture_full))
    in_image = (xx >= 0) & (xx < w) & (yy >= 0) & (yy < h)
    aperture_in_image = int(np.sum(aperture_full & in_image))
    # Keep window-sized arrays even off image, without indexing beyond the SCI.
    values = np.full(xx.shape, np.nan)
    values[in_image] = image[yy[in_image], xx[in_image]]
    valid = in_image & np.isfinite(values)
    validity = bundle.get("validity_mask")
    if validity is not None:
        validity = np.asarray(validity, dtype=bool)
        if validity.shape != image.shape:
            raise ValueError("validity_mask shape must match SCI")
        valid[in_image] &= validity[yy[in_image], xx[in_image]]
    weight = bundle.get("wht")
    if weight is not None:
        weight = np.asarray(weight, dtype=float)
        if weight.shape != image.shape:
            raise ValueError("WHT shape must match SCI")
        valid[in_image] &= np.isfinite(weight[yy[in_image], xx[in_image]]) & (weight[yy[in_image], xx[in_image]] > 0)
    aperture, annulus = aperture_full & valid, annulus_full & valid
    n_ap, n_ann = int(np.sum(aperture)), int(np.sum(annulus))
    err_window = None
    err = bundle.get("err")
    if err is not None:
        err = np.asarray(err, dtype=float)
        if err.shape != image.shape:
            raise ValueError("ERR shape must match SCI")
        err_window = np.full(xx.shape, np.nan)
        err_window[in_image] = err[yy[in_image], xx[in_image]]

    status = ("off_image" if aperture_in_image == 0 else "no_valid_pixels" if n_ap == 0
              else "partial_coverage" if n_ap < total_pixels else "measured")
    flux = float(np.sum(values[aperture])) if n_ap else None
    bg = float(np.mean(values[annulus])) if n_ann else None
    bg_std = float(np.std(values[annulus], ddof=1)) if n_ann > 1 else None
    subtracted = flux - bg * n_ap if flux is not None and bg is not None else None
    raw_error, uncertainty_method = _uncertainty(values, err_window, aperture, annulus, np.ones(xx.shape))
    snr = float(subtracted / raw_error) if subtracted is not None and raw_error is not None else None
    calibration = flux_density_factors(bundle, xx, yy)
    factors = calibration["factor_jy"]
    flux_jy = subtracted_jy = error_jy = None
    if factors is not None and n_ap:
        flux_jy = float(np.sum(values[aperture] * factors[aperture]))
        if bg is not None:
            subtracted_jy = float(np.sum((values[aperture] - bg) * factors[aperture]))
        error_jy, _ = _uncertainty(values, err_window, aperture, annulus, factors)
    if factors is not None:
        snr = float(subtracted_jy / error_jy) if subtracted_jy is not None and error_jy is not None else None
    area = calibration["pixel_area_sr"]
    result = {
        "flux": flux, "background_subtracted_flux": subtracted, "flux_error": raw_error,
        "raw_flux_unit": calibration["input_unit"] or "unknown",
        "flux_jy": flux_jy, "background_subtracted_flux_jy": subtracted_jy, "flux_error_jy": error_jy,
        "magnitude": ab_magnitude(flux_jy), "background_subtracted_magnitude": ab_magnitude(subtracted_jy),
        "magnitude_system": "AB" if calibration["status"] == "calibrated" else None,
        "calibration_status": calibration["status"], "measurement_status": status,
        "background_status": "measured" if n_ann else "missing_annulus",
        "uncertainty_method": uncertainty_method,
        "uncertainty_assumptions": "diagonal pixel noise; drizzle covariance, calibration and aperture corrections excluded",
        "pixel_area_source": calibration["pixel_area_source"],
        "mean_pixel_area_sr": float(np.mean(area[aperture])) if area is not None and n_ap else None,
        "snr": snr, "snr_basis": ("flux_jy" if factors is not None else "raw_flux") if snr is not None else None, "background_mean": bg, "background_std": bg_std,
        "coverage_fraction": float(n_ap / total_pixels) if total_pixels else 0.0,
        "x": x, "y": y, "aperture_radius": float(radii[0]),
        "background_annulus_inner_radius": float(radii[1]), "background_annulus_outer_radius": float(radii[2]),
        "aperture_radius_arcsec": float(angular_radii[0]) if angular_radii is not None else None,
        "background_annulus_inner_radius_arcsec": float(angular_radii[1]) if angular_radii is not None else None,
        "background_annulus_outer_radius_arcsec": float(angular_radii[2]) if angular_radii is not None else None,
        "pixels_in_aperture": total_pixels, "valid_pixel_count": n_ap, "annulus_pixel_count": n_ann,
        "dataset_name": bundle.get("dataset_name"), "file_path": bundle.get("file_path"),
    }
    if weight is not None:
        result["mean_weight"] = float(np.mean(weight[yy[aperture], xx[aperture]])) if n_ap else None
    return result


def compute_color_index(flux_band1: float, flux_band2: float) -> Dict[str, Any]:
    """Compute an AB colour from positive fluxes in the SAME physical unit.

    Call with calibrated Jy fluxes, not raw surface-brightness sums from images
    on different grids. This function cannot infer units from two bare floats.
    """
    if flux_band1 is None or flux_band2 is None or not np.all(np.isfinite([flux_band1, flux_band2])) or flux_band1 <= 0 or flux_band2 <= 0:
        return {"color_index": None, "flux_ratio": None, "error": "Fluxes must be finite, positive, and in the same physical unit"}
    ratio = flux_band1 / flux_band2
    return {"color_index": float(-2.5 * np.log10(ratio)), "flux_ratio": float(ratio),
            "band1_flux": float(flux_band1), "band2_flux": float(flux_band2)}
