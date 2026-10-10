"""Independent controls for complete pair search, signed data and cone witnesses."""

import numpy as np
import pytest
from scipy.optimize import nnls

from discovery.survivor_multiplicity import best_pair, cone_fit


def test_exact_pair_enumeration_matches_independent_nnls_every_pair():
    rng = np.random.default_rng(481)
    shapes = rng.uniform(0.01, 1.0, (7, 9))
    shapes[-1] = 1.0
    flux = 7.0 * shapes[:, 2] + 3.0 * shapes[:, 7] + rng.normal(0, 0.1, 7)
    covariance = np.diag(np.linspace(0.1, 0.4, 7)) + 0.06 * np.ones((7, 7))
    lower = np.linalg.cholesky(covariance)
    data = np.linalg.solve(lower, flux)
    candidates = []
    for i in range(9):
        for j in range(i + 1, 9):
            design = np.linalg.solve(lower, shapes[:, [i, j]])
            coefficients, residual = nnls(design, data)
            candidates.append((residual**2, shapes[:, [i, j]] @ coefficients))
    expected = min(candidates, key=lambda pair: pair[0])
    measured = best_pair(flux, covariance, shapes)
    assert measured["chi2_conditional"] == pytest.approx(expected[0], abs=1e-11)
    assert measured["prediction_njy"] == pytest.approx(expected[1], abs=1e-10)


def test_held_band_has_no_effect_and_collinear_boundary_is_retained():
    shapes = np.array([[1.0, 2.0, 3.0], [2.0, 4.0, 6.0], [1.0, 1.0, 1.0]])
    covariance = np.eye(3)
    retained = np.array([0, 1])
    first = best_pair(np.array([3.0, 6.0, 1.0]), covariance, shapes, retained)
    second = best_pair(np.array([3.0, 6.0, 1e9]), covariance, shapes, retained)
    assert first == second
    assert first["chi2_conditional"] < 1e-28
    negative = best_pair(-np.ones(3), covariance, shapes)
    assert negative["prediction_njy"] == [0.0, 0.0, 0.0]
    assert negative["chi2_conditional"] == 3.0


def test_dual_witness_bounds_every_nonnegative_mixture_independently():
    shapes = np.array([[1.0, 0.5], [0.1, 0.4], [1.0, 1.0]])
    flux = np.array([1.0, 2.0, 1.0])
    covariance = np.diag([0.1, 0.2, 0.3]) + 0.05 * np.ones((3, 3))
    result = cone_fit(flux, covariance, shapes)
    weights = np.array(result["dual_band_weights_per_njy"])
    assert weights @ covariance @ weights == pytest.approx(1.0)
    assert np.max(weights @ shapes) < 1e-12
    assert weights @ flux == pytest.approx(np.sqrt(result["chi2_conditional"]))
    for coefficients in ([0, 0], [5, 2], [1, 100], [12, 48]):
        residual = flux - shapes @ coefficients
        loss = residual @ np.linalg.solve(covariance, residual)
        assert loss >= result["chi2_conditional"] - 1e-12


def test_asymmetric_or_nonpositive_covariance_is_rejected():
    with pytest.raises(ValueError, match="symmetric"):
        best_pair(np.ones(2), np.array([[1, 1], [0, 1]]), np.ones((2, 2)))
    with pytest.raises(np.linalg.LinAlgError):
        cone_fit(np.ones(2), np.diag([1, -1]), np.ones((2, 2)))
