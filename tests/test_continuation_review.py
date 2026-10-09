"""Independent algebra controls for the reviewer, not science-data substitutes."""

import numpy as np
import pytest

from discovery.continuation_review import fieller_oracle


def test_quadratic_ratio_oracle_respects_covariance():
    independent = fieller_oracle(10, 5, 1, 0.1, 0)
    positively_correlated = fieller_oracle(10, 5, 1, 0.1, 0.2)
    assert independent[0] < 2 < independent[1]
    assert positively_correlated[1] - positively_correlated[0] < independent[1] - independent[0]
    # Common change of numerical units must leave the ratio set invariant.
    assert fieller_oracle(100, 50, 100, 10, 20) == pytest.approx(positively_correlated)


def test_observed_bounded_oracle_refuses_unidentified_denominator():
    with pytest.raises(ValueError, match="bounded"):
        fieller_oracle(10, 0.01, 1, 0.1, 0)


def test_reviewer_does_not_hide_negative_signed_ratios():
    interval = fieller_oracle(-10, 5, 1, 0.1, 0)
    assert np.isfinite(interval).all()
    assert interval[0] < -2 < interval[1] < 0
