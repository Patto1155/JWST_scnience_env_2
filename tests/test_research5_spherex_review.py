"""Model-product tests of flux recovery, subpixel normalization and astrometry."""

import astropy.units as u
import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS
from photutils.psf import ImagePSF

from discovery.research5_spherex_review import (
    benign_flag_mask,
    linear_photometry,
    local_solid_angle,
    native_psf,
    response_coverage,
    select_zone,
)


@pytest.fixture
def epsf():
    yy, xx = np.mgrid[:33, :33]
    # Pixel-convolved asymmetric toy ePSF, not scientific observations.
    model = np.exp(-(((xx - 16) / 3.5) ** 2) / 2 - ((yy - 16) / 4.1) ** 2 / 2)
    return model / (model.sum() / 25)


@pytest.mark.parametrize("x,y", [(10.0, 10.0), (10.49, 9.81), (10.88, 10.22)])
def test_native_psf_matches_official_photutils_renderer(epsf, x, y):
    psf, raw_sum = native_psf(epsf, (21, 21), x, y)
    yy, xx = np.indices((21, 21))
    official = ImagePSF(epsf, oversampling=5).evaluate(xx, yy, 1.0, x, y)
    official /= official.sum()
    np.testing.assert_allclose(psf, official, rtol=2e-12, atol=1e-14)
    assert psf.sum() == pytest.approx(1)
    assert raw_sum > 0


def test_no_renormalization_to_retained_pixels(epsf):
    psf, _ = native_psf(epsf, (21, 21), 10.49, 10.21)
    variance = np.full(psf.shape, 0.09)
    yy, xx = np.indices(psf.shape)
    image = 23.7 * psf + 1.4 + 0.02 * (xx - 10.49) - 0.03 * (yy - 10.21)
    good = np.ones(psf.shape, dtype=bool)
    good[10, 10] = False
    fit = linear_photometry(image, variance, psf, good, 10.49, 10.21, plane=True)
    assert fit["amplitude"] == pytest.approx(23.7, rel=1e-12)
    assert fit["usable_psf_fraction"] < 1
    assert fit["formal_error"] > 0


def test_native_psf_support_normalized_outside_cutout(epsf):
    # Cropping must preserve missing flux fraction, rather than forcing sum one.
    psf, _ = native_psf(epsf, (6, 6), 0.1, 0.1)
    assert 0 < psf.sum() < 0.9


def test_source_position_zone_selection():
    table = np.array([(100, 100), (1900, 1900)], dtype=[("XCENTER", float), ("YCENTER", float)])
    assert select_zone(table, 1800, 1810) == 1


def test_qr3_source_information_bits_not_bad_pixels():
    header = fits.Header(
        {
            "MSKN0021": "SOURCE",
            "MSKM0021": 1 << 21,
            "MSKN0012": "FULLSAMPLE",
            "MSKM0012": 1 << 12,
            "MSKN0019": "OUTLIER",
            "MSKM0019": 1 << 19,
        }
    )
    benign = benign_flag_mask(header)
    assert benign == (1 << 21) | (1 << 12)
    assert ((1 << 21) & ~benign) == 0
    assert (((1 << 21) | (1 << 19)) & ~benign) != 0


def test_surface_brightness_to_flux_solid_angle():
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [11, 11]
    wcs.wcs.cdelt = [-6.2 / 3600, 6.2 / 3600]
    wcs.wcs.crval = [57.641985, 35.585679]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    omega = local_solid_angle(wcs, 10, 10)
    expected = (6.2 * u.arcsec).to_value(u.rad) ** 2
    assert omega == pytest.approx(expected, rel=1e-6)
    assert omega * 1e9 == pytest.approx(0.9035, abs=0.001)


def test_sparse_channels_do_not_create_observed_response_coverage():
    response = np.column_stack([np.linspace(2, 4, 201), np.ones(201)])
    coverage = response_coverage(np.array([2.5, 3.5]), np.array([0.1, 0.1]), response)
    assert coverage["nominal_support_response_fraction"] == pytest.approx(0.1, abs=0.001)
    assert coverage["interpolation_hull_response_fraction"] == pytest.approx(0.5, abs=0.001)
    assert coverage["nonoverlapping_nominal_channel_count"] == 2


def test_repeated_same_channel_does_not_increase_coverage():
    response = np.column_stack([np.linspace(2, 4, 201), np.ones(201)])
    coverage = response_coverage(np.array([3, 3, 3, 3]), np.full(4, 0.1), response)
    assert coverage["nonoverlapping_nominal_channel_count"] == 1
    assert coverage["nominal_support_response_fraction"] == pytest.approx(0.05, abs=0.001)
