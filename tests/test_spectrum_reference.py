"""Spectral diagnostics validate units and errors without guessing abundances."""

import hashlib

import numpy as np
import pytest
from astropy.io import fits

from tools.jwst.spectroscopy import summarize_extracted_spectrum


def spectrum(tmp_path, *, unit="uJy", wave_unit="um", flux=None, err=None):
    columns = [
        fits.Column(name="wave", format="D", unit=wave_unit, array=[1.0, 2.0, 3.0, 4.0]),
        fits.Column(
            name="flux",
            format="D",
            unit=unit,
            array=flux if flux is not None else [3.0, -4.0, np.nan, 1.0],
        ),
        fits.Column(
            name="err",
            format="D",
            unit=unit,
            array=err if err is not None else [1.0, 1.0, 1.0, 0.0],
        ),
    ]
    table = fits.BinTableHDU.from_columns(columns, name="SPEC1D")
    table.header["SRCRA"] = 150.0933255
    table.header["SRCDEC"] = 2.2731627
    table.header["TARG_RA"] = 150.11  # Pointing coordinates are not the source.
    path = tmp_path / "extraction.fits"
    fits.HDUList([fits.PrimaryHDU(), table]).writeto(path)
    return path


def test_signed_snr_validity_units_and_source_identity(tmp_path):
    path = spectrum(tmp_path)
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    result = summarize_extracted_spectrum(path, expected_sha256=expected)
    assert result["hash_verified_against_receipt"] is True
    assert result["samples"]["valid"] == 2
    assert result["samples"]["excluded"] == 2
    assert result["samples"]["nonfinite_flux"] == 1
    assert result["samples"]["nonfinite_or_nonpositive_error"] == 1
    assert result["signed_bin_snr"]["median"] == -0.5
    assert result["signed_bin_snr"]["bins_ge_3"] == 1
    assert result["signed_bin_snr"]["bins_le_minus_3"] == 1
    assert result["diagonal_zero_flux_statistic"]["sum_squared_signed_bin_snr"] == 25
    assert result["source_position"]["ra_deg"] == 150.0933255
    assert result["wavelength_range_um"] == [1, 2]


def test_other_equivalent_units_are_converted(tmp_path):
    path = spectrum(tmp_path, unit="Jy", wave_unit="nm", flux=[1.0, 2.0, 3.0, 4.0], err=[1.0] * 4)
    result = summarize_extracted_spectrum(path)
    assert result["wavelength_range_um"] == pytest.approx([0.001, 0.004])
    assert result["signed_bin_snr"]["median"] == 2.5


@pytest.mark.parametrize("unit", [None, "DN/s", "Jy/sr"])
def test_missing_or_incompatible_flux_units_rejected(tmp_path, unit):
    with pytest.raises(ValueError, match="unit"):
        summarize_extracted_spectrum(spectrum(tmp_path, unit=unit))


def test_no_valid_error_is_not_zero_noise_certainty(tmp_path):
    with pytest.raises(ValueError, match="no samples"):
        summarize_extracted_spectrum(spectrum(tmp_path, err=[0.0, -1.0, np.nan, np.inf]))


def test_wrong_receipt_hash_rejected_before_analysis(tmp_path):
    with pytest.raises(ValueError, match="SHA256"):
        summarize_extracted_spectrum(spectrum(tmp_path), expected_sha256="0" * 64)


def test_image_is_not_treated_as_spectral_table(tmp_path):
    path = tmp_path / "image.fits"
    fits.PrimaryHDU(np.zeros((10, 10))).writeto(path)
    with pytest.raises(ValueError, match="SPEC1D"):
        summarize_extracted_spectrum(path)
