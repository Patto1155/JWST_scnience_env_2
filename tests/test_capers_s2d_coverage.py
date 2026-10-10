"""Support-bit and missing-DQ oracles plus actual rectified-source coverage."""

import numpy as np

from data_pipeline.capers_s2d_coverage import replay, support_counts


def test_signed_context_bit_retained_and_missing_dq_is_explicit():
    wave = np.array([[2.3, 2.4]])
    science = -np.ones((1, 2))
    error = weight = np.ones((1, 2))
    context = np.array([[[-2147483648, 0]]], dtype=np.int32)
    result = support_counts(wave, science, error, weight, context)
    assert result["uv_wavelength_pixels_before_quality_cuts"] == 2
    assert result["uv_supported_pixels_before_dq"] == 1
    assert not result["dq_array_present"]
    assert result["uv_supported_pixels_after_supplied_dq"] is None
    flagged = support_counts(wave, science, error, weight, context, np.array([[1, 0]]))
    assert flagged["uv_supported_pixels_after_supplied_dq"] == 0


def test_actual_source_coordinate_grid_has_no_uv_before_any_masks():
    report = replay()
    assert report["shape"] == [31, 277]
    assert report["actual_nrs1_contributors"] == report["actual_nrs2_contributors"] == 18
    assert report["coverage"]["finite_wavelength_pixels"] == 8587
    assert report["coverage"]["positive_error_weight_context_supported_pixels"] == 7049
    assert report["coverage"]["uv_wavelength_pixels_before_quality_cuts"] == 0
    assert report["coverage"]["uv_supported_pixels_before_dq"] == 0
    assert report["coverage"]["uv_supported_pixels_after_supplied_dq"] is None
    assert report["source_X1D_grid_crosscheck_passed"]
