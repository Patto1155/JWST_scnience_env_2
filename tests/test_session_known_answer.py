"""Dimensional, sign and strict-threshold oracles for the frozen check."""

import astropy.units as u
import numpy as np
import pytest
from astropy.io import fits
from scipy.special import ndtr

from data_pipeline.session_known_answer import (
    REDSHIFT,
    REST_A,
    compare,
    measure,
    normalized_table,
)


def test_si_units_and_missing_unit_rejection():
    columns = fits.ColDefs(
        [
            fits.Column(name="WAVELENGTH", format="D", unit="m", array=[5e-6]),
            fits.Column(name="FLUX", format="D", unit="W m-3", array=[3e-13]),
            fits.Column(name="FLUX_ERR", format="D", unit="W m-3", array=[1e-13]),
        ]
    )
    hdu = fits.BinTableHDU.from_columns(columns)
    normalized = normalized_table(hdu.data, hdu.columns)
    assert normalized["WAVELENGTH"][0] == pytest.approx(5)
    assert normalized["FLUX"][0] == pytest.approx(3e-20)
    hdu.columns["FLUX"].unit = None
    with pytest.raises(ValueError, match="Undeclared"):
        normalized_table(hdu.data, hdu.columns)


def test_threshold_and_nonboundary_requirement():
    assert compare(36.1, 0.4, valid=True)["pass_1sigma"]
    assert not compare(36.7, 0.4, valid=True)["pass_1sigma"]
    assert compare(36.7, 0.4, valid=True)["pass_2sigma"]
    assert not compare(37.5, 0.4, valid=True)["pass_2sigma"]
    assert not compare(35.8, 0.4, valid=False)["pass_2sigma"]


def test_pixel_integrated_signed_line_recovery():
    center = REST_A * (1 + REDSHIFT) / 10000
    wave = np.arange(center - 0.03, center + 0.03, 0.0004)
    width = 0.0004
    shape = (ndtr((wave + width / 2 - center - 0.0001) / 0.0008)
             - ndtr((wave - width / 2 - center - 0.0001) / 0.0008)) / (width * 10000)
    flux = (1.2 + 358 * shape) * 1e-20
    table = {"WAVELENGTH": wave, "FLUX": flux, "FLUX_ERR": np.full(len(wave), 1e-20)}
    report = measure(table)
    assert report["fit"]["covariance_valid"]
    assert report["comparison"]["recovered_flux_1e19"] == pytest.approx(35.8, rel=1e-7)
    assert report["comparison"]["pass_1sigma"]
    assert (3e-13 * u.W / u.m**3).to_value(u.erg / u.s / u.cm**2 / u.AA) == pytest.approx(3e-20)


def test_combined_error_amendment_is_strict_and_keeps_original_contract():
    from data_pipeline.session_known_answer import compare

    # Combined-error recovery can pass while the immutable original test fails.
    report = compare(28.36421, 0.71922, valid=True, published=29.49712, published_error=0.60019)
    assert not report["pass_1sigma"]
    assert report["pass_combined_2sigma_amendment"]
    # Exact 2 sigma is excluded by the user's strict inequality.
    boundary = compare(10.0, 4.0, valid=True, published=0.0, published_error=3.0)
    assert not boundary["pass_combined_2sigma_amendment"]
    invalid = compare(0.0, 1.0, valid=False, published=0.0, published_error=1.0)
    assert not invalid["pass_combined_2sigma_amendment"]
