"""Alternate-solver controls that fail for rank or cone-sign mistakes."""

import numpy as np
import pytest

from discovery.research2_independent_review import dual_projection, svd_fit


def test_svd_recovers_signed_flux_with_correlated_noise():
    x = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    c = np.array([[2.0, 0.2, 0.1], [0.2, 1.0, 0.3], [0.1, 0.3, 3.0]])
    truth = np.array([-3.0, 4.0])
    beta, covariance, operator, q = svd_fit(x, c, x @ truth)
    assert np.allclose(beta, truth)
    assert np.allclose(operator @ x, np.eye(2))
    assert np.allclose(covariance, operator @ c @ operator.T)
    assert q < 1e-25


def test_svd_rejects_duplicate_line_response():
    x = np.ones((5, 2))
    with pytest.raises(ValueError, match="Rank-deficient"):
        svd_fit(x, np.eye(5), np.arange(5.0))


def test_independent_polar_solver_certifies_distance_not_zero():
    a = np.eye(2)
    y = np.array([-3.0, 4.0])
    residual = dual_projection(a, y)
    assert np.allclose(residual, [-3.0, 0.0], atol=1e-10)
    assert residual @ residual == pytest.approx(9.0)
    assert np.max(a.T @ residual) < 1e-10


def test_polar_solver_returns_zero_for_representable_positive_spectrum():
    residual = dual_projection(np.eye(3), np.array([1.0, 2.0, 3.0]))
    assert np.linalg.norm(residual) < 1e-10
