import numpy as np

from discovery.research2_cloudy_grid_rate_review import gram_fit, total_covariance


def test_nonnegative_constraint_refits_continuum_not_clipped_unrestricted_solution():
    x = np.arange(4.0)
    design = np.column_stack((np.ones(4), x))
    coefficient, _, statistic = gram_fit(design, np.eye(4), 2 - 3 * x, True)
    np.testing.assert_allclose(coefficient, [-2.5, 0])
    assert statistic == 45


def test_reused_precision_equals_direct_gls_with_correlated_noise():
    covariance = np.array([[2.0, 0.5, 0.2], [0.5, 3.0, 0.8], [0.2, 0.8, 4.0]])
    design = np.column_stack((np.ones(3), np.arange(3.0)))
    values = np.array([1.0, 3.0, 2.0])
    direct = gram_fit(design, covariance, values)
    cached = gram_fit(design, covariance, values, precision=np.linalg.inv(covariance))
    for a, b in zip(direct, cached):
        np.testing.assert_allclose(a, b, atol=1e-13)


def test_block_covariance_uses_measured_kernel_separately_from_noise_scale():
    block = np.diag(np.arange(1.0, 10.0))
    blocks = np.stack((block, 4 * block))
    kernel = np.array([[1.0, 0.25], [0.25, 1.0]])
    expected = np.block([[block, 0.5 * block], [0.5 * block, 4 * block]]) * 1.5
    np.testing.assert_allclose(total_covariance(blocks, kernel, 1.5), expected)
