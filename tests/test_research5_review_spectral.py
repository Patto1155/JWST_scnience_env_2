"""Numerical mask and continuum controls for the independent line audit."""

import numpy as np

from discovery.research5_review_spectral import Z, measure


def spectrum() -> dict:
    wave = np.arange(6000.0, 7000.0, 0.5)
    center = 6088.64 * (1 + Z)
    flux = 2 + 0.001 * (wave - center)
    flux[np.argmin(abs(wave - center))] += 100 / 0.5
    return {
        "wavelength": wave,
        "flux": flux,
        "ivar": np.ones(len(wave)) * 4,
        "mask": np.full(len(wave), 65552),
        "data_release": "SDSS-DR17",
    }


def test_advisory_policy_recovers_exact_line_and_linear_continuum():
    record = spectrum()
    strict = measure(record, 6088.64, 8.0, (20.0, 40.0), "strict", "linear")
    assert strict["flux_1e17"] is None
    result = measure(record, 6088.64, 8.0, (20.0, 40.0), "advisory_diagnostic", "linear")
    assert abs(result["flux_1e17"] - 100) < 1e-10
    assert result["conditional_diagonal_error_1e17"] > 0
    assert result["predefined_sky_excluded_fraction"] > 0
    assert abs(result["covered_unmasked_fraction"] - 1) < 1e-10


def test_bright_sky_rejection_preserves_unavailable_measurement():
    record = spectrum()
    center = 6088.64 * (1 + Z)
    record["mask"][abs(record["wavelength"] - center) < 9] |= 1 << 23
    result = measure(record, 6088.64, 8.0, (20.0, 40.0), "advisory_diagnostic", "linear")
    assert result["flux_1e17"] is None
    assert result["conditional_diagonal_error_1e17"] is None
    assert result["covered_unmasked_fraction"] < 0.9
