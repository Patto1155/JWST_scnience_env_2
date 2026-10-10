"""Atmosphere family unit identity and independently solved retained-band fits."""

import numpy as np
import pytest

from discovery.survivor_flame import audit_units, fit_vectorized, parse_table
from discovery.survivor_atmosphere import BANDS


def test_units_crosscheck_uses_independent_jy_zeropoints_and_rejects_wrong_units():
    points = np.array([2245, 1746, 1120, 758, 417, 273, 184.0])
    magnitude = np.array([[24, 22, 21, 23, 22, 17, 15], [20, 19, 19, 17, 17, 16, 16]])
    raw = 10 ** (-0.4 * magnitude) * points * 1e3
    first, second, ratios = audit_units(raw, magnitude, points)
    assert first == pytest.approx(second)
    assert ratios == pytest.approx(np.ones_like(ratios))
    with pytest.raises(ValueError, match="consistency"):
        audit_units(raw * 1e3, magnitude, points)
    with pytest.raises(ValueError, match="consistency"):
        audit_units(raw, magnitude, np.ones(7) * 3631)
    with pytest.raises(ValueError, match="Nonpositive"):
        audit_units(-raw, magnitude, points)


def test_physical_header_and_real_filter_identity_cannot_be_guessed():
    header = ["Teff", "log(g)", "Mass/Mjup", "Radius/Rjup", "Age/Gyr", "log(L/Lsun)", *BANDS]
    table = " ".join(header) + "\n400 4.5 12 1 4 -6 " + " ".join(["0.2"] * 7) + "\n"
    h, a = parse_table(table)
    assert h == header
    assert a.shape == (1, 13)
    with pytest.raises(ValueError, match="band header"):
        parse_table(table.replace("F444W", "F200W"))
    with pytest.raises(ValueError, match="physical header"):
        parse_table(table.replace("Radius/Rjup", "radius"))
    with pytest.raises(ValueError, match="row lengths"):
        parse_table(table + "400 4.5\n")
    with pytest.raises(ValueError, match="Nonfinite"):
        parse_table(table.replace("12", "nan"))


def test_full_covariant_best_and_heldout_against_independent_scalar_gls():
    rng = np.random.default_rng(289)
    absolute = rng.uniform(0.1, 3, (20, 7))
    metadata = [{"chemistry": "eq" if i % 2 else "deq", "row": i} for i in range(20)]
    flux = 3.5 * absolute[6] / absolute[6, -1] + rng.normal(0, 0.02, 7)
    covariance = np.diag(np.arange(1, 8) * 0.03) + 0.015 * np.ones((7, 7))
    retained = np.array([0, 1, 2, 4, 5, 6])
    actual = fit_vectorized(flux, covariance, absolute, metadata, retained)[0]
    inverse = np.linalg.inv(covariance[np.ix_(retained, retained)])
    expected = []
    for i in range(20):
        shape = absolute[i] / absolute[i, -1]
        design = shape[retained]
        amplitude = max(0, design @ inverse @ flux[retained] / (design @ inverse @ design))
        residual = flux[retained] - amplitude * design
        expected.append((residual @ inverse @ residual, amplitude * shape, i))
    minimum = min(expected, key=lambda x: x[0])
    assert actual["chi2_conditional"] == pytest.approx(minimum[0])
    assert actual["prediction_njy"] == pytest.approx(minimum[1])
    assert actual["grid_index"] == minimum[2]
    changed = flux.copy()
    changed[3] = 1e30
    assert actual == fit_vectorized(changed, covariance, absolute, metadata, retained)[0]
