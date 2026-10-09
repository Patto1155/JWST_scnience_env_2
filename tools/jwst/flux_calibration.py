"""Unit-aware flux-density conversion for calibrated two-dimensional images.

No count-rate zeropoint is invented. Surface brightness is integrated using the
solid angle of the actual image grid, not a nominal instrument pixel scale.
"""
from __future__ import annotations

from typing import Any, Mapping

import numpy as np
from astropy import units as u
from astropy.wcs import WCS

ARCSEC2_TO_SR = (np.pi / (180.0 * 3600.0)) ** 2
AB_ZERO_JY = 3631.0


def celestial_wcs(bundle: Mapping[str, Any]) -> WCS | None:
    """Return only a genuinely celestial FITS WCS, never a default identity WCS."""
    wcs = bundle.get("wcs")
    if wcs is None and bundle.get("header") is not None:
        try:
            wcs = WCS(bundle["header"])
        except (ValueError, TypeError):
            return None
    if wcs is not None and getattr(wcs, "has_celestial", False):
        return wcs.celestial
    return None


def _unit_vectors(longitude: np.ndarray, latitude: np.ndarray) -> np.ndarray:
    lon, lat = np.deg2rad(longitude), np.deg2rad(latitude)
    return np.stack((np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)), axis=-1)


def _triangle_area(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    numerator = np.abs(np.sum(a * np.cross(b - a, c - a), axis=-1))
    denominator = 1 + np.sum(a * b, axis=-1) + np.sum(b * c, axis=-1) + np.sum(c * a, axis=-1)
    return 2 * np.arctan2(numerator, denominator)


def pixel_solid_angle_sr(wcs: WCS, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Integrate four celestial pixel corners as two spherical triangles.

    Suitable for small imaging pixels, including TAN/SIP grids; this integrates
    the local pixel polygon rather than using the projection-plane determinant.
    """
    corners = []
    for dx, dy in ((-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5)):
        world = wcs.pixel_to_world_values(np.asarray(x) + dx, np.asarray(y) + dy)
        lon, lat = world[wcs.wcs.lng], world[wcs.wcs.lat]
        corners.append(_unit_vectors(np.asarray(lon), np.asarray(lat)))
    a, b, c, d = corners
    area = _triangle_area(a, b, c) + _triangle_area(a, c, d)
    if np.any(~np.isfinite(area)) or np.any(area <= 0):
        raise ValueError("Celestial WCS gives nonfinite or nonpositive pixel solid angle")
    return area


def _header_value(bundle: Mapping[str, Any], name: str) -> Any:
    for key in ("header", "primary_header"):
        header = bundle.get(key)
        if header is not None and name in header:
            return header[name]
    return None


def flux_density_factors(bundle: Mapping[str, Any], x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    """Return Jy per raw SCI unit for each pixel, or an explicit failure status.

    Recognizes flux density per pixel (Jy, nJy, uJy, MJy, Jy/pixel etc.) and
    surface brightness convertible to Jy/sr. DN/s or missing BUNIT remain raw.
    ERR is assumed to share SCI units, as specified for calibrated JWST products.
    """
    raw_unit = _header_value(bundle, "BUNIT")
    result: dict[str, Any] = {
        "input_unit": str(raw_unit) if raw_unit is not None else None,
        "status": "missing_bunit" if raw_unit is None else "unsupported_bunit",
        "factor_jy": None, "pixel_area_source": None, "pixel_area_sr": None,
    }
    if raw_unit is None:
        return result
    try:
        unit = u.Unit(str(raw_unit).replace("µ", "u").replace("μ", "u"))
    except (ValueError, TypeError):
        return result
    if unit.is_equivalent(u.Jy):
        result.update(status="calibrated", factor_jy=np.full(np.shape(x), unit.to(u.Jy)))
        return result
    if unit.is_equivalent(u.Jy / u.pix):
        result.update(status="calibrated", factor_jy=np.full(np.shape(x), unit.to(u.Jy / u.pix)))
        return result
    if not unit.is_equivalent(u.Jy / u.sr):
        return result

    wcs = celestial_wcs(bundle)
    if wcs is not None:
        try:
            area = pixel_solid_angle_sr(wcs, x, y)
        except (ValueError, TypeError, IndexError):
            result["status"] = "invalid_wcs_pixel_area"
            return result
        source = "celestial_wcs_pixel_corners"
    else:
        area_value = _header_value(bundle, "PIXAR_SR")
        source = "header_PIXAR_SR"
        if area_value is None:
            area_value = _header_value(bundle, "PIXAR_A2")
            source = "header_PIXAR_A2"
            try:
                area_value = float(area_value) * ARCSEC2_TO_SR
            except (TypeError, ValueError):
                area_value = None
        try:
            area_scalar = float(area_value)
        except (TypeError, ValueError):
            result["status"] = "missing_pixel_area"
            return result
        if not np.isfinite(area_scalar) or area_scalar <= 0:
            result["status"] = "invalid_pixel_area"
            return result
        area = np.full(np.shape(x), area_scalar)
    result.update(status="calibrated", factor_jy=unit.to(u.Jy / u.sr) * area,
                  pixel_area_source=source, pixel_area_sr=area)
    return result


def ab_magnitude(flux_jy: float | None) -> float | None:
    """AB magnitude of a positive flux density; signed fluxes retain no magnitude."""
    if flux_jy is None or not np.isfinite(flux_jy) or flux_jy <= 0:
        return None
    return float(-2.5 * np.log10(flux_jy / AB_ZERO_JY))
