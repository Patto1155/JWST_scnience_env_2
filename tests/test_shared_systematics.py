"""Independent algebra and known-distribution controls for systematic limits."""

import numpy as np
import pytest
from scipy.stats import norm

from tools.jwst.shared_systematics import assumed_coverage, equal_variance_scale_interval, gls


def test_weighted_mean_oracle_and_common_mode_nullspace():
    variance = np.array([1.0, 4.0, 9.0])
    design = np.ones((3, 1))
    values = np.array([2.0, 3.0, -1.0])
    coefficient, covariance, operator, _ = gls(design, np.diag(variance), values)
    weights = (1 / variance) / np.sum(1 / variance)
    assert coefficient[0] == pytest.approx(weights @ values)
    assert covariance[0, 0] == pytest.approx(1 / np.sum(1 / variance))
    assert np.allclose(operator[0], weights)
    # Adding the same arbitrary shared calibration amplitude changes the mean
    # but leaves every group contrast invariant. No sample SD bounds that mode.
    contrast = np.eye(3) - np.ones((3, 3)) / 3
    assert np.allclose(contrast @ (values + 1234), contrast @ values)
    shifted, _, _, _ = gls(design, np.diag(variance), values + 1234)
    assert shifted[0] - coefficient[0] == pytest.approx(1234)


def test_signed_spectrum_injection_and_low_rank_systematic_covariance():
    rng = np.random.default_rng(14831486)
    design = rng.normal(size=(30, 3))
    covariance = np.diag(rng.uniform(0.5, 2, size=30))
    truth = np.array([4.0, -2.0, 1.0])
    coefficient, parameter_covariance, operator, statistic = gls(design, covariance, design @ truth)
    assert np.allclose(coefficient, truth)
    assert statistic < 1e-24
    direction = np.array([0, 3.0, 0])
    measurement_mode = design @ direction
    systematic = np.outer(measurement_mode, measurement_mode)
    assert np.allclose(operator @ systematic @ operator.T, np.outer(direction, direction))
    assert np.all(np.diag(parameter_covariance) > 0)


def test_coverage_simulation_matches_independent_closed_form():
    answer = assumed_coverage(1.0, 100000, 5224)
    exact = 2 * norm.cdf(norm.ppf(0.975) / np.sqrt(2)) - 1
    assert answer["omitted_systematic_exact_95_coverage"] == pytest.approx(exact)
    assert abs(answer["omitted_systematic_simulated_95_coverage"] - exact) < 0.006
    assert abs(answer["included_systematic_simulated_95_coverage"] - 0.95) < 0.006
    assert answer["distribution_measured"] is False
    assert exact < 0.84


def test_three_groups_give_very_weak_even_idealized_variance_interval():
    lower, upper = equal_variance_scale_interval(3)
    assert 0.52 < lower < 0.53
    assert 6.28 < upper < 6.29
    assert equal_variance_scale_interval(30)[1] < upper
    with pytest.raises(ValueError):
        equal_variance_scale_interval(1)
    with pytest.raises(ValueError):
        assumed_coverage(-1, 10000, 1)
