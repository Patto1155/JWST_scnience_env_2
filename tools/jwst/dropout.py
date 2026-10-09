"""Physical, uncertainty-aware dropout measurements (not redshift confirmation)."""

from __future__ import annotations

import math
from typing import Any


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def physical_flux(
    measurement: dict[str, Any], key: str = "background_subtracted_flux_jy"
) -> float | None:
    """Return a finite calibrated quantity, never substitute an unobserved zero."""
    if measurement.get("calibration_status") != "calibrated":
        return None
    try:
        value = float(measurement[key])
    except (KeyError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def dropout_upper_limit_ratio(
    blue: dict[str, Any], red: dict[str, Any], *, sigma: float = 2.0
) -> float | None:
    """Conservative blue limit divided by red flux in matched angular apertures.

    This is a photometric screen, not a photometric-redshift likelihood. PSF
    matching/aperture corrections and correlated noise remain separate concerns.
    """
    if not math.isfinite(sigma) or sigma <= 0:
        raise ValueError("sigma must be finite and positive")
    for item in (blue, red):
        if item.get("measurement_status") != "measured":
            return None
        if item.get("background_status") != "measured":
            return None
        coverage = _finite(item.get("coverage_fraction"))
        if coverage is None or not 0.9 <= coverage <= 1.0:
            return None
    try:
        blue_radius = float(blue["aperture_radius_arcsec"])
        red_radius = float(red["aperture_radius_arcsec"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (
        blue_radius > 0
        and math.isfinite(blue_radius)
        and math.isclose(blue_radius, red_radius, rel_tol=1e-6)
    ):
        return None
    blue_flux, red_flux = physical_flux(blue), physical_flux(red)
    blue_error = physical_flux(blue, "flux_error_jy")
    red_error = physical_flux(red, "flux_error_jy")
    if None in (blue_flux, red_flux, blue_error, red_error):
        return None
    if blue_error <= 0 or red_error <= 0 or red_flux <= 0:
        return None
    if red_flux / red_error < 5.0 or blue_flux / blue_error > 2.0:
        return None
    return (max(blue_flux, 0.0) + sigma * blue_error) / red_flux
