"""Tests for sky-footprint geometry.

The synthetic WCS cases mirror real NIRCam geometry: a long-wave detector at
0.063"/px covering ~129", and a short-wave detector at 0.031"/px covering ~63"
of the same field, offset to one quadrant.
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from tools.jwst.footprints import (
    detector_token,
    module_letter,
    modules_are_disjoint,
    overlap_fraction,
    sky_to_pixel,
)

FIELD_CENTER_RA = 110.7
FIELD_CENTER_DEC = -73.47


def _bundle(ra_center, dec_center, pixel_scale_arcsec, size):
    """Build a minimal bundle with a tangent-plane WCS and a blank science array."""
    header = fits.Header()
    header["NAXIS"] = 2
    header["NAXIS1"] = size
    header["NAXIS2"] = size
    header["CTYPE1"] = "RA---TAN"
    header["CTYPE2"] = "DEC--TAN"
    header["CRPIX1"] = size / 2.0
    header["CRPIX2"] = size / 2.0
    header["CRVAL1"] = ra_center
    header["CRVAL2"] = dec_center
    header["CDELT1"] = -pixel_scale_arcsec / 3600.0
    header["CDELT2"] = pixel_scale_arcsec / 3600.0
    return {"sci": np.zeros((size, size)), "wcs": WCS(header)}


def test_detector_and_module_parsing():
    name = "jwst_SMACS_F090W_jw02736001001_02101_00004_nrca1_i2d"
    assert detector_token(name) == "nrca1"
    assert module_letter(name) == "a"
    assert module_letter("jw01180030001_03201_00001_nrcb1_i2d") == "b"
    assert detector_token("jwst_ngc1234_f200w") is None
    assert module_letter("jwst_ngc1234_f200w") is None


def test_module_name_difference_is_advisory():
    """Names differ, but actual overlap needs WCS and cannot follow from names."""
    reference = "jwst_GS_F444W_jw01180030001_09201_00003_nrcalong_i2d"
    blue_wrong = "jwst_GS_F090W_jw01180030001_03201_00001_nrcb1_i2d"
    blue_right = "jwst_GS_F090W_jw01180026001_03201_00003_nrca1_i2d"
    assert modules_are_disjoint(reference, blue_wrong) is True
    assert modules_are_disjoint(reference, blue_right) is False


def test_modules_are_disjoint_is_false_when_unknown():
    assert modules_are_disjoint("mystery_a", "mystery_b") is False


def test_identical_footprints_fully_overlap():
    bundle = _bundle(FIELD_CENTER_RA, FIELD_CENTER_DEC, 0.063, 2048)
    assert overlap_fraction(bundle, bundle) == pytest.approx(1.0)


def test_shortwave_detector_covers_about_a_quarter_of_longwave_field():
    """One SW detector tiles ~1/4 of the LW field, offset to a quadrant."""
    longwave = _bundle(FIELD_CENTER_RA, FIELD_CENTER_DEC, 0.063, 2048)
    quadrant_offset_deg = (2048 * 0.063 / 4.0) / 3600.0
    shortwave = _bundle(
        FIELD_CENTER_RA + quadrant_offset_deg / np.cos(np.radians(FIELD_CENTER_DEC)),
        FIELD_CENTER_DEC + quadrant_offset_deg,
        0.031,
        2048,
    )
    # Fraction of the long-wave field measurable in the short-wave image.
    assert overlap_fraction(longwave, shortwave) == pytest.approx(0.25, abs=0.05)
    # The reverse is near-total: the SW footprint sits inside the LW field.
    assert overlap_fraction(shortwave, longwave) > 0.9


def test_disjoint_pointings_have_zero_overlap():
    """Module A and module B are separated by far more than a field width."""
    module_a = _bundle(FIELD_CENTER_RA, FIELD_CENTER_DEC, 0.063, 2048)
    module_b = _bundle(FIELD_CENTER_RA + 0.2, FIELD_CENTER_DEC, 0.063, 2048)
    assert overlap_fraction(module_a, module_b) == 0.0


def test_overlap_is_zero_without_wcs():
    bundle = _bundle(FIELD_CENTER_RA, FIELD_CENTER_DEC, 0.063, 2048)
    assert overlap_fraction(bundle, {"sci": np.zeros((10, 10)), "wcs": None}) == 0.0


def test_sky_to_pixel_returns_none_off_array():
    """An off-array position must return None, never a usable-looking coordinate.

    This is the failure that produced 1418 fabricated non-detections: an
    off-detector aperture returned flux 0, which read as a perfect dropout.
    """
    bundle = _bundle(FIELD_CENTER_RA, FIELD_CENTER_DEC, 0.063, 2048)
    assert sky_to_pixel(bundle, FIELD_CENTER_RA, FIELD_CENTER_DEC) is not None
    assert sky_to_pixel(bundle, FIELD_CENTER_RA + 5.0, FIELD_CENTER_DEC) is None
    assert sky_to_pixel(bundle, None, None) is None


def test_sky_to_pixel_center_maps_to_array_center():
    size = 2048
    bundle = _bundle(FIELD_CENTER_RA, FIELD_CENTER_DEC, 0.063, size)
    x, y = sky_to_pixel(bundle, FIELD_CENTER_RA, FIELD_CENTER_DEC)
    assert x == pytest.approx(size / 2.0 - 1, abs=1.0)
    assert y == pytest.approx(size / 2.0 - 1, abs=1.0)


def test_different_modules_across_visits_can_have_identical_sky_coverage():
    """Synthetic control: opposite modules reobserving one sky position."""
    name_a = "jw01180026001_03201_00003_nrca1_i2d"
    name_b = "jw01180030001_03201_00001_nrcb1_i2d"
    assert modules_are_disjoint(name_a, name_b) is True  # advisory only
    a = _bundle(FIELD_CENTER_RA, FIELD_CENTER_DEC, 0.031, 64)
    b = _bundle(FIELD_CENTER_RA, FIELD_CENTER_DEC, 0.031, 64)
    assert overlap_fraction(a, b) == pytest.approx(1.0)
