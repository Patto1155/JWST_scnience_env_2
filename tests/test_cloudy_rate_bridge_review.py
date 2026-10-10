import numpy as np

from discovery.research2_cloudy_rate_bridge_review import gram_fit, total_covariance


def test_direct_physical_amplitude_boundary_refits_continuum():
    x = np.arange(4.0)
    design = np.column_stack((np.ones(4), x))
    values = 2 - 3 * x
    coefficients, _, chi = gram_fit(design, np.eye(4), values, True)
    np.testing.assert_allclose(coefficients, [-2.5, 0.0])
    assert chi == 45


def test_covariance_assembly_has_known_separable_gram_oracle():
    block = np.diag(np.arange(1.0, 10.0))
    blocks = np.stack((block, 4 * block))
    kernel = np.array([[1.0, 0.25], [0.25, 1.0]])
    expected = np.block([[block, 0.5 * block], [0.5 * block, 4 * block]]) * 1.5
    np.testing.assert_allclose(total_covariance(blocks, kernel, 1.5), expected)
