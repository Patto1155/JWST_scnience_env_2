import numpy as np
import pytest

from tools.jwst.wavelength_mixture import marginal_coefficient_moments, shift_row_wavelength


def test_constant_design_recovers_exact_gaussian_with_signed_flux():
    design = np.array([[1.0], [1.0], [1.0]])
    result = marginal_coefficient_moments(
        [design, design], np.eye(3), np.array([-1.0, -2.0, -3.0]), [0.25, 0.75]
    )
    assert result["coefficients"][0] == pytest.approx(-2)
    assert result["covariance"][0, 0] == pytest.approx(1 / 3)
    np.testing.assert_allclose(result["weights"], [0.25, 0.75])


def test_integrated_likelihood_includes_coefficient_determinant():
    result = marginal_coefficient_moments(
        [np.ones((3, 1)), 2 * np.ones((3, 1))], np.eye(3), np.zeros(3), [0.5, 0.5]
    )
    np.testing.assert_allclose(result["weights"], [2 / 3, 1 / 3])


def test_row_shift_extrapolates_and_keeps_native_sampling():
    wave = np.array([[2.0, 2.1, 2.2, 2.3]])
    np.testing.assert_allclose(shift_row_wavelength(wave, -0.25), wave - 0.025)


def test_budget_override_cannot_exceed_frozen_allowance(tmp_path):
    from tools.jwst.mom_noise_challenge_run import run

    with pytest.raises(ValueError, match="authorized 1.5 GiB"):
        run(
            tmp_path / "receipt.json",
            tmp_path / "compact.npz",
            calibration_verdict="blocked",
            cap_bytes=1_610_612_737,
        )
    assert not (tmp_path / "receipt.json").exists()


def test_missing_row_is_preserved_not_synthesized():
    wave = np.array([[np.nan, np.nan, 0.0, 0.0]])
    np.testing.assert_equal(shift_row_wavelength(wave, 0.5), wave)


def test_fixed_source_operator_skips_same_unusable_masked_row():
    from tools.jwst.native_row_response import row_source_design

    wave = np.array([[np.nan, np.nan, 0.0, 0.0]])
    source = {
        "wave": wave,
        "good": np.zeros_like(wave, dtype=bool),
        "trace_seed": np.zeros(4),
        "point_pathloss": np.ones_like(wave),
    }
    shifted = dict(source, wave=shift_row_wavelength(wave, 0.5))
    before = row_source_design(
        [source], np.array([1.0, 6.0]), np.array([100.0, 100.0]), [], 1.0, 0.0
    )
    after = row_source_design(
        [shifted], np.array([1.0, 6.0]), np.array([100.0, 100.0]), [], 1.0, 0.0
    )
    np.testing.assert_array_equal(before, after)
    assert not np.any(after)


def test_fixed_red_windows_exclude_missing_wavelength_rows():
    from tools.jwst.mom_noise_challenge_run import red_window_indices

    waves = np.full((9, 28, 40), np.nan)
    waves[:, 0, :20] = 3.45
    waves[:, 0, 20:] = 3.8
    np.testing.assert_array_equal(red_window_indices(waves), np.arange(20))
    assert len(red_window_indices(np.zeros_like(waves))) == 0


def test_full41_node_seven_coefficient_mixture_serializes_signed_result():
    import json
    from pathlib import Path

    from tools.jwst.native_measurement_validation import serial_fit

    rng = np.random.default_rng(4)
    design = rng.normal(size=(200, 7))
    truth = np.array([0.0, 0.0, -1.0, 2.0, 1.0, 0.0, 1.0])
    nodes, weights = np.polynomial.legendre.leggauss(41)
    designs = [design.copy() for _ in nodes]
    fit = marginal_coefficient_moments(designs, np.eye(200), design @ truth, weights / 2)
    atomic = json.loads(Path("research_output/mom_atomic_grid_niv_doublet_v2.json").read_text())
    emissivity = next(
        x["emissivity_erg_cm3_s"]
        for x in atomic["records"]
        if x["temperature_K"] == 20000 and x["electron_density_cm3"] == 1000
    )
    answer = serial_fit(fit, emissivity, 1)
    assert answer["fluxes"][0] == pytest.approx(-1)
    json.dumps(answer, allow_nan=False)
