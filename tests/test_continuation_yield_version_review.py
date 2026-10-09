"""Analytic positive-normalization and interval-cone counterexamples."""

import numpy as np
import pytest

from discovery.continuation_yield_version_review import cone_deviance


def test_cone_interior_is_a_mixture_and_not_nearest_endpoint():
    assert cone_deviance([2, 1], np.eye(2), 1, 3) < 1e-20
    assert cone_deviance([2, 1], np.eye(2), 1, 1) == pytest.approx(0.5)


def test_signed_negative_measurement_uses_positive_quadrant_reference():
    assert cone_deviance([-1, 2], np.eye(2), 1, 1) == pytest.approx(3.5)
    assert cone_deviance([-1, -1], np.eye(2), 1, 3) < 1e-20
    with pytest.raises(ValueError, match="SPD"):
        cone_deviance([1, 1], [[1, np.nan], [np.nan, 1]], 1, 3)
