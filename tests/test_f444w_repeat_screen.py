"""Synthetic classification controls; observed results are separately hash-pinned."""

import pytest

from discovery.f444w_repeat_screen import classify_pair


def _measurement(flux, error):
    return {
        "background_subtracted_flux_jy": flux,
        "flux_error_jy": error,
        "calibration_status": "calibrated",
        "measurement_status": "measured",
        "background_status": "measured",
        "coverage_fraction": 1.0,
    }


def test_partial_repeat_is_untestable_not_a_zero_flux_nondetection():
    repeat = _measurement(0, 1)
    repeat.update(measurement_status="partial_coverage", coverage_fraction=0.7)
    assert classify_pair(_measurement(100, 1), repeat)["status"].startswith("untestable")


def test_depth_difference_requires_significant_flux_discrepancy():
    result = classify_pair(_measurement(5, 1), _measurement(2, 1))
    assert result["status"] == "inconclusive_depth"
    assert result["absolute_flux_difference_sigma"] < 3


def test_error_inflation_reveals_insufficient_rejection_depth():
    reference, repeat = _measurement(20, 1), _measurement(0, 1)
    assert classify_pair(reference, repeat)["status"] == "single_epoch_only"
    assert classify_pair(reference, repeat, error_scale=10)["status"] == "inconclusive_depth"


def test_persistence_does_not_require_exactly_constant_measured_flux():
    result = classify_pair(_measurement(100, 1), _measurement(107, 1))
    assert result["status"] == "persistent_detection"
    assert result["comparison_reference_flux_ratio"] == pytest.approx(1.07)
