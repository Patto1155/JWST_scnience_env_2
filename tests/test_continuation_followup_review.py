"""Counterexamples protect the independent reviewer from silent NaN success."""

import numpy as np
import pytest

from discovery.continuation_followup_review import (
    LINE_ORDER,
    NATIVE_SCENARIOS,
    check_native_arrays,
    compare_native_model,
)


def likelihood():
    return {
        "fluxes": np.arange(5, dtype=float).tolist(),
        "flux_covariance": np.eye(5).tolist(),
        "flux_units": "1e-20 erg s^-1 cm^-2",
        "line_order": list(LINE_ORDER),
    }


def test_exact_zero_covariance_entries_are_finite_and_wrong_ones_rejected():
    saved = likelihood()
    result = compare_native_model(np.arange(5.0), np.eye(5), saved)
    assert result["max_covariance_absolute_error_over_largest_saved_entry"] == 0
    changed = np.eye(5)
    changed[0, 1] = changed[1, 0] = 0.001
    with pytest.raises(ValueError, match="disagrees"):
        compare_native_model(np.arange(5.0), changed, saved)


@pytest.mark.parametrize("target", ("stored", "computed"))
def test_nonfinite_covariance_never_becomes_silent_success(target):
    saved, computed = likelihood(), np.eye(5)
    if target == "stored":
        saved["flux_covariance"][0][1] = float("nan")
    else:
        computed[0, 1] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        compare_native_model(np.arange(5.0), computed, saved)


def test_covariance_order_units_and_shape_are_mandatory():
    saved = likelihood()
    saved["line_order"] = list(reversed(LINE_ORDER))
    with pytest.raises(ValueError, match="order"):
        compare_native_model(np.arange(5.0), np.eye(5), saved)
    saved = likelihood()
    saved["flux_units"] = "Jy"
    with pytest.raises(ValueError, match="units"):
        compare_native_model(np.arange(5.0), np.eye(5), saved)
    with pytest.raises(ValueError, match="aligned"):
        compare_native_model(np.arange(4.0), np.eye(4), likelihood())


def test_empty_or_reordered_native_scenarios_fail_before_any_fit():
    with pytest.raises(ValueError, match="four"):
        check_native_arrays({}, {"scenarios": []})
    reversed_report = {"scenarios": [{"name": name} for name in reversed(NATIVE_SCENARIOS)]}
    with pytest.raises(ValueError, match="four"):
        check_native_arrays({}, reversed_report)
