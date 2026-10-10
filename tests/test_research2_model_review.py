"""Independent numerical solver controls for atmosphere and observing design."""

import numpy as np
import pytest

from discovery.research2_flame_review import scalar_gls
from discovery.research2_observation_review import numeric_gram


def test_scalar_gls_retains_negative_measurement_and_zero_amplitude_boundary():
    flux = np.array([-3.0, -4.0])
    c = np.array([[2.0, 0.3], [0.3, 1.0]])
    models = np.array([[2.0, 1.0], [1.0, 1.0]])
    q, amplitude, shape = scalar_gls(flux, c, models)
    assert np.array_equal(amplitude, [0.0, 0.0])
    assert np.allclose(q, flux @ np.linalg.solve(c, flux))
    assert np.all(shape > 0)


def test_scalar_gls_heldout_flux_does_not_leak():
    models = np.array([[1.0, 1.0, 1.0], [1.0, 2.0, 3.0]])
    c = np.eye(3)
    first = scalar_gls(np.array([1.0, 2.0, 3.0]), c, models, [0, 1])
    second = scalar_gls(np.array([1.0, 2.0, 900.0]), c, models, [0, 1])
    assert np.array_equal(first[0], second[0])
    assert np.array_equal(first[1], second[1])


def test_numeric_gram_unit_area_norm_scales_inversely_with_width():
    first = numeric_gram([2.3], [1000.0], 0.0)
    wider = numeric_gram([2.3], [500.0], 0.0)
    assert first[0, 0] == pytest.approx(2 * wider[0, 0], rel=1e-11)
    broad = numeric_gram([2.3, 2.305], [1000.0, 3000.0], 1000.0)
    assert np.linalg.eigvalsh(broad).min() > 0
    assert broad[0, 1] > 0
