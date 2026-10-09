"""Endpoint and full-grid counterexamples for the independent wavelength audit."""

import numpy as np
import pytest

from discovery.continuation_physical_review import multiplet_audit
from discovery.continuation_wavecorr_review import bin_design, linear_extrapolation, normal_fit


def test_mapping_extrapolates_endpoints_and_preserves_missing_pixels():
    wave = np.array([0.9, 1.0, 1.5, 2.0, 2.1, np.nan])
    result = linear_extrapolation(wave, [1, 1.5, 2], [1.01, 1.515, 2.02])
    assert np.allclose(result[:-1], wave[:-1] * 1.01)
    assert np.isnan(result[-1])
    assert result[0] < 1.01  # np.interp's clamping loses this physical edge shift.
    with pytest.raises(ValueError, match="invertible"):
        linear_extrapolation(wave, [1, 1.5, 2], [1.01, 1.515, 1.50])


def test_rejected_column_does_not_widen_retained_native_bins():
    wave = np.linspace(2.0, 3.2, 101)
    keep = np.delete(np.arange(len(wave)), 35)
    resolution_wave, resolution = np.array([2, 3.2]), np.array([200, 200])
    full = bin_design(wave[None], np.arange(len(wave)), resolution_wave, resolution)
    selected = bin_design(wave[None], keep, resolution_wave, resolution)
    assert np.array_equal(selected, full[keep])
    shortened = bin_design(wave[None, keep], np.arange(len(keep)), resolution_wave, resolution)
    assert np.max(abs(selected[:, 2:] - shortened[:, 2:])) > 1e-6


def test_atomic_contract_cannot_be_guessed_from_unknown_version(tmp_path):
    with pytest.raises(ValueError, match="explicit single-line v1 or doublet v2"):
        multiplet_audit(tmp_path, version=3)


def test_normal_solver_accepts_zero_cross_covariance_but_rejects_nonfinite():
    values = np.array([1, 2, -1, 4, 5, 6, 7])
    saved = {
        "flux_units": "1e-20 erg s^-1 cm^-2",
        "line_order": ["NIV", "CIV", "HeII_OIII", "NIII", "CIII"],
        "fluxes": values[2:].tolist(),
        "flux_covariance": np.eye(5).tolist(),
        "conditional_chi2": 0,
    }
    assert normal_fit(np.eye(7), np.eye(7), values, saved) == (0, 0, 0)
    saved["flux_covariance"][0][1] = np.nan
    with pytest.raises(ValueError, match="finite aligned"):
        normal_fit(np.eye(7), np.eye(7), values, saved)
