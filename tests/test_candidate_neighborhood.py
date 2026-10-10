"""Independent linear/operator and spatial-misspecification checks."""

import numpy as np
import pytest

from discovery.candidate_neighborhood import fixed_neighbors, neighborhood_fit, svd_fit


def test_signed_svd_recovery_and_independent_covariance():
    rng = np.random.default_rng(88)
    design = rng.normal(size=(200, 5))
    beta = np.array([-17.0, 10.0, 2.0, -6.0, 0.4])
    errors = np.linspace(0.5, 2.0, 200)
    coef, covariance, singular = svd_fit(design, design @ beta, errors)
    np.testing.assert_allclose(coef, beta, atol=1e-12)
    weighted = design / errors[:, None]
    independent = np.linalg.solve(weighted.T @ weighted, np.eye(5))
    np.testing.assert_allclose(covariance, independent, atol=1e-13)
    assert singular[-1] > 0


def test_zero_support_and_duplicate_nuisance_are_not_fabricated_identifiability():
    design = np.ones((100, 2))
    with pytest.raises(ValueError, match="Rank-deficient"):
        svd_fit(design, np.ones(100), np.ones(100))
    design[:, 1] = 0
    with pytest.raises(ValueError, match="Zero-support"):
        svd_fit(design, np.ones(100), np.ones(100))


def test_spatial_predictions_recover_truth_and_reject_unmodeled_structure():
    yy, xx = np.mgrid[-15:16, -15:16]
    target = np.exp(-(xx**2 + yy**2) / 8)
    target /= target.sum()
    neighbor = np.exp(-((xx - 6) ** 2 + (yy + 5) ** 2) / 6)
    neighbor /= neighbor.sum()
    background = 3 + 0.01 * xx - 0.03 * yy + 0.001 * xx**2
    data = -15 * target + 30 * neighbor + background
    result = neighborhood_fit(
        data,
        np.ones_like(data),
        0.1,
        [target, neighbor],
        ["target", "neighbor"],
        [0],
        halfwidth=1.5,
    )
    assert result["signed_target_template_total_njy"] == pytest.approx(-15, abs=1e-8)
    assert result["heldout_standardized_rms"] < 1e-10
    assert result["conditional_predictive_gate_pass"]
    wrong = data + 30 * np.sin(xx) * np.cos(yy)
    failure = neighborhood_fit(
        wrong,
        np.ones_like(data),
        0.1,
        [target, neighbor],
        ["target", "neighbor"],
        [0],
        halfwidth=1.5,
    )
    assert not failure["conditional_predictive_gate_pass"]
    assert len(failure["spatial_block_folds"]) == 6


def test_guide_geometry_excludes_target_and_separates_neighbor_peaks():
    yy, xx = np.mgrid[-30:31, -30:31]
    target = 100 * np.exp(-(xx**2 + yy**2) / 2)
    neighbor = 30 * np.exp(-((xx - 12) ** 2 + (yy - 8) ** 2) / 2)
    peaks = fixed_neighbors(target + neighbor, np.ones_like(target), 0.05, (0, 0))
    assert len(peaks) == 1
    np.testing.assert_allclose(peaks[0], [0.6, 0.4], atol=0.01)
