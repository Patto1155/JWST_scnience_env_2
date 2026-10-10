"""Independent physical profile controls including amplitude boundary."""

import numpy as np

from discovery.research2_cloudy_likelihood_review import constrained_full_fit


def test_full_data_fit_recovers_truth_with_correlated_noise_and_continuum():
    rng = np.random.default_rng(5140)
    design = rng.normal(size=(19, 7))
    factor = np.eye(19) + rng.normal(size=(19, 19)) / 20
    covariance = factor @ factor.T
    ratios = np.array([0.1, 0.2, 0.4, 0.8, 1.0])
    y = design[:, :2] @ [101.0, -77.0] + design[:, 2:] @ ratios * 9.0
    beta, _, statistic = constrained_full_fit(design, covariance, y, ratios)
    np.testing.assert_allclose(beta, [101, -77, 9], atol=1e-12)
    assert statistic < 1e-23


def test_negative_amplitude_is_refitted_at_boundary_with_free_continuum():
    design = np.vstack((np.eye(7), np.eye(7)))
    ratios = np.ones(5)
    y = design[:, :2] @ [21.0, -8.0] - design[:, 2:] @ ratios * 3.0
    beta, _, statistic = constrained_full_fit(design, np.eye(14), y, ratios)
    np.testing.assert_allclose(beta, [21, -8, 0], atol=1e-12)
    assert abs(statistic - 90) < 1e-12
