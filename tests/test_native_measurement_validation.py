"""Independent GLS/prediction and calibration-identifiability controls."""

import json
from pathlib import Path

import numpy as np
import pytest
from scipy.linalg import block_diag

from tools.jwst.native_measurement_validation import (
    apply_signed_response,
    common_systematic_identifiability,
    declared_source,
    held_out_prediction,
    response,
    signed_response_coupling,
    solve_measurement,
    source_wavelength,
    transported_covariance,
)
from tools.jwst.native_reduction import (
    extract_columns,
    gaussian_profile,
    mixing_matrix,
    signed_profiles,
)

ROOT = Path(__file__).resolve().parents[1]


def test_gls_matches_independent_normal_equation_with_correlated_noise():
    rng = np.random.default_rng(4277)
    design = rng.normal(size=(31, 7))
    root = rng.normal(size=(31, 31))
    covariance = root @ root.T + np.eye(31)
    truth = rng.normal(size=7)
    values = design @ truth + rng.normal(size=31)
    actual = solve_measurement(design, covariance, values)
    precision = np.linalg.inv(covariance)
    v = np.linalg.inv(design.T @ precision @ design)
    expected = v @ design.T @ precision @ values
    assert np.allclose(actual["coefficients"], expected, rtol=1e-12, atol=1e-12)
    assert np.allclose(actual["covariance"], v, rtol=1e-12, atol=1e-12)
    assert np.allclose(actual["estimator"] @ design, np.eye(7), atol=1e-12)
    assert np.allclose(actual["estimator"] @ covariance @ actual["estimator"].T, v, atol=1e-12)
    with pytest.raises(ValueError, match="rank deficient"):
        solve_measurement(np.column_stack([design[:, 0], design[:, 0]]), covariance, values)


def test_held_out_prediction_profiles_separate_continuum_and_propagates_training_error():
    rng = np.random.default_rng(741)
    a = rng.normal(size=(40, 7))
    truth = np.array([4, -2, 3, 5, 1, 2, 6.0])
    train = {"continuum_order": 1, "solution": solve_measurement(a, np.eye(40), a @ truth)}
    # Test continuum is allowed to differ arbitrarily from the training one.
    other = truth.copy()
    other[:2] = [11, 18]
    test = {"design": a, "covariance": np.eye(40), "values": a @ other}
    prediction = held_out_prediction(train, test)
    assert prediction["predictive_chi2"] < 1e-23
    # Explicit eliminate the two continuum modes using precision projector.
    test["values"] += a[:, 2] * 2
    f = train["solution"]["coefficients"][2:]
    vf = train["solution"]["covariance"][2:, 2:]
    precision = np.linalg.inv(np.eye(40) + a[:, 2:] @ vf @ a[:, 2:].T)
    p = (
        precision
        - precision
        @ a[:, :2]
        @ np.linalg.inv(a[:, :2].T @ precision @ a[:, :2])
        @ a[:, :2].T
        @ precision
    )
    resid = test["values"] - a[:, 2:] @ f
    expected = float(resid @ p @ resid)
    assert held_out_prediction(train, test)["predictive_chi2"] == pytest.approx(expected, rel=1e-12)
    assert expected > 0


def test_full_native_bin_edges_are_preserved_across_quality_mask_and_subset_covariance():
    wave = np.linspace(2.1, 3.3, 42)
    rows = 8
    good = np.ones((rows, len(wave)), bool)
    d = {
        "wave": np.broadcast_to(wave, (rows, len(wave))),
        "good": good,
        "trace_seed": np.full(len(wave), 4.0),
        "sigma_refined": 0.8,
    }
    selected = np.array([2, 3, 9, 12, 19, 27, 35, 36])
    rw = np.array([0.5, 6.0])
    r = np.array([120.0, 120.0])
    components = [
        ([1483.321, 1486.496], [1, 2]),
        ([1549.0], [1]),
        ([1654.0], [1]),
        ([1750.0], [1]),
        ([1908.0], [1]),
    ]
    full = response([d], np.arange(len(wave)), rw, r, components)
    assert np.allclose(response([d], selected, rw, r, components), full[selected], atol=1e-14)
    assert np.allclose(source_wavelength(d), wave)
    blocks = np.broadcast_to(np.array([[2.0, 0.3, 0], [0.3, 1, 0], [0, 0, 3]]), (len(wave), 3, 3))
    kernel = np.eye(len(selected))
    actual = transported_covariance(blocks, selected, kernel, 2, [2, 0])
    expected = block_diag(*[np.diag([6.0, 4.0]) for _ in selected])
    assert np.allclose(actual, expected)
    with pytest.raises(ValueError):
        transported_covariance(blocks, selected, kernel, -1, [0, 1])


def test_signed_known_source_uses_raw_nod_difference_without_resubtracting_cal_science():
    columns = 64
    rows = 28
    wave = np.linspace(2.1, 3.3, columns)
    data = []
    for i, trace in enumerate((7.0, 12.0, 17.0)):
        data.append(
            {
                "wave": np.broadcast_to(wave, (rows, columns)),
                "good": np.ones((rows, columns), bool),
                "trace_seed": np.full(columns, trace),
                "sigma_refined": 0.8,
                "point_pathloss": np.ones((rows, columns)),
                "science": np.full((rows, columns), 100 + i),
                "group": "03",
            }
        )
    rw = np.array([0.5, 6])
    r = np.array([150.0, 150.0])
    components = [
        ([1483.321, 1486.496], [1, 2]),
        ([1549.0], [1]),
        ([1654.0], [1]),
        ([1750.0], [1]),
        ([1908.0], [1]),
    ]
    truth = np.array([2, -0.5, 20, 15, 15, 5, 12.0])
    before = [d["science"].copy() for d in data]
    actual = declared_source(data, rw, r, components, truth, sigma=0.8, offset=0)
    spec = response([data[0]], np.arange(columns), rw, r, components) @ truth
    positive = np.array([gaussian_profile(d["trace_seed"], 0.8, rows) * spec[None] for d in data])
    expected = np.einsum("ij,jrc->irc", mixing_matrix(), positive)
    assert np.allclose(actual, expected)
    assert np.any(actual < 0)
    assert all(np.array_equal(d["science"], x) for d, x in zip(data, before))


def test_common_systematic_is_not_identified_by_three_group_agreement():
    result = common_systematic_identifiability()
    assert result["source_plus_common_offset_design_rank"] == 1
    assert result["common_systematic_upper_bound_from_group_agreement"] is None
    assert result["group_contrast_response_to_common_offset"] == [0, 0]
    # Any offset can be absorbed into the true flux, leaving observables fixed.
    for bias in (-100.0, 0, 100.0):
        assert np.allclose(np.ones(3) * (4 - bias) + np.ones(3) * bias, 4)


def test_ghost_wavelength_counterexample_and_transported_response_closure():
    rows, columns = 28, 96
    base = np.linspace(2.1, 3.3, columns)
    # Same detector-pixel wavelength map in every nod, but different source
    # rows sample different wavelengths. One source spectrum feeds all ghosts.
    wave = base[None] + (np.arange(rows)[:, None] - 14) * 0.003
    data = []
    for trace in (8.0, 14.0, 20.0):
        good = np.ones((rows, columns), bool)
        good[0] = False
        pathloss = np.full((rows, columns), 0.8)
        pathloss[0] = np.nan
        data.append(
            {
                "wave": wave,
                "good": good,
                "point_pathloss": pathloss,
                "trace_seed": np.full(columns, trace),
                "sigma_refined": 0.8,
                "science": np.zeros_like(wave),
                "variance": np.ones_like(wave),
                "group": "03",
            }
        )
    components = [
        ([1483.321, 1486.496], [1, 2]),
        ([1549.0], [1]),
        ([1654.0], [1]),
        ([1750.0], [1]),
        ([1908.0], [1]),
    ]
    rw, r = np.array([0.5, 6.0]), np.array([220.0, 220.0])
    selected = np.arange(columns)
    truth = np.array([2, -0.5, 20, 15, 15, 5, 12.0])
    profiles = signed_profiles(data, 0.8, 0)
    _, operators, _ = extract_columns(data, profiles)
    coupling = signed_response_coupling(data, operators, selected, 0.8, 0)
    positive_design = response(data, selected, rw, r, components)
    transported = apply_signed_response(positive_design, coupling)
    injected = declared_source(data, rw, r, components, truth, sigma=0.8, offset=0)
    assert np.isfinite(injected).all()
    values = np.sum(injected * operators, axis=1).T.reshape(-1)
    assert np.allclose(values, transported @ truth, atol=1e-14)
    assert np.allclose(np.sum(coupling, axis=2), 1, atol=1e-12)
    corrected = np.linalg.lstsq(transported, values, rcond=None)[0]
    legacy = np.linalg.lstsq(positive_design, values, rcond=None)[0]
    assert np.allclose(corrected, truth, atol=1e-10)
    assert abs(legacy[2] - truth[2]) > 3
    with pytest.raises(ValueError, match="dimensions differ"):
        apply_signed_response(positive_design[:-1], coupling)


def test_committed_native_measurement_validation_keeps_hypotheses_and_signed_uncertainty():
    path = ROOT / "research_output/mom_native_measurement_validation.json"
    result = json.loads(path.read_text())
    assert len(result["one_factor_sensitivity_fits"]) == 28
    assert len(result["held_out_rate_group_checks"]) == 6
    assert result["alternative_likelihoods_pooled"] is False
    assert result["nuisance_ranges_empirically_calibrated"] is False
    assert result["elemental_NC_identified"] is False
    assert len(result["actual_pixel_input_hashes"]) == 9
    injection = result["signed_operator_injections"]
    assert injection["draws"] == 4000
    assert injection["formal_pixel_noise_covariance_standardized_max_error"] < 5
    for case in injection["pixel_signed_operator_injections"]:
        assert max(abs(np.array(case["conditional_95_marginal_coverage"]) - 0.95)) < 0.035
    matched = injection["pixel_signed_operator_injections"][0]
    assert max(abs(np.array(matched["deterministic_flux_bias"]))) < 0.01
    assert injection["empirical_unknown_noise_coverage_established"] is False
    legacy = injection["legacy_response_matched_profile_failure"]
    assert legacy["noise_free_recovered_fluxes"][0] < 14
    assert legacy["conditional_95_marginal_coverage"][0] < 0.85
    assert len(result["signed_forward_corrected_baseline_fits"]) == 4
    assert len(result["signed_forward_corrected_group_checks"]) == 3
