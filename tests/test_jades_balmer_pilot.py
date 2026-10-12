"""Focused checks for the scientific pilot's identity and uncertainty contracts."""

import numpy as np
import pytest

from tools.jwst.jades_balmer_pilot import fit_line, spectrum_key


def test_target_identity_prevents_window_overwrite():
    left = spectrum_key("7496", "f170lp-g235m", 5, "FLUX", "Hb")
    right = spectrum_key("8656", "f170lp-g235m", 5, "FLUX", "Hb")
    assert left != right
    assert left.startswith("7496_") and right.startswith("8656_")


def test_masked_window_is_unavailable_not_zero_flux():
    wave = np.linspace(1.68, 1.72, 80)
    data = {"WAVELENGTH": wave, "FLUX": np.full(80, np.nan), "FLUX_ERR": np.ones(80) * 1e-21}
    with pytest.raises(ValueError, match="Insufficient finite"):
        fit_line(data, 4862.68, 2.493465347981974)


def test_unconstrained_line_has_no_zero_error_claim():
    # The center is outside a masked core; a zero continuum supplies no shape information.
    wave = np.linspace(1.68, 1.72, 80)
    flux = np.zeros(80)
    flux[np.abs(wave - 1.6988) < 0.005] = np.nan
    data = {"WAVELENGTH": wave, "FLUX": flux, "FLUX_ERR": np.ones(80) * 1e-21}
    result, _ = fit_line(data, 4862.68, 2.493465347981974)
    assert result["diagonal_err_1e20"] is None or result["diagonal_err_1e20"] > 1


def test_injected_integrated_line_flux_normalization():
    # Numerical quadrature generates flux density independently of the fitter's CDF response.
    from scipy.integrate import quad

    z = 2.493465347981974
    center = 4862.68 * (1 + z) / 1e4
    width = 0.00065
    wave = center + np.arange(-35, 36) * 0.0006
    spacing = wave[1] - wave[0]
    area = 2.3e-18
    flux = np.array(
        [
            quad(
                lambda w: np.exp(-0.5 * ((w - center) / width) ** 2),
                w - spacing / 2,
                w + spacing / 2,
                epsabs=1e-14,
            )[0]
            * area
            / (np.sqrt(2 * np.pi) * width * spacing * 1e4)
            + 3.1e-21
            for w in wave
        ]
    )
    data = {"WAVELENGTH": wave, "FLUX": flux, "FLUX_ERR": np.ones_like(wave) * 1e-21}
    result, _ = fit_line(data, 4862.68, z)
    assert result["covariance_valid"]
    assert result["flux_1e20"] == pytest.approx(230.0, rel=1e-6)
