"""Known half-normal boundary validates numerical amplitude normalization."""

import numpy as np
from scipy.stats import norm

from discovery.research2_cloudy_heldout_review import moments_and_interval


def test_nonnegative_zero_center_is_half_normal_not_clipped_zero():
    expected, variance, interval = moments_and_interval(0, 2.0)
    assert abs(expected - 2 * np.sqrt(2 / np.pi)) < 1e-12
    assert abs(variance - 4 * (1 - 2 / np.pi)) < 1e-12
    np.testing.assert_allclose(interval, 2 * norm.ppf([0.5125, 0.9875]), atol=1e-11)
