import numpy as np

from discovery.research2_capers_source_review import pixel_gate


def test_signed_context_and_absent_dq_are_explicit():
    wave = np.array([[2.5, 4.0]])
    ones = np.ones_like(wave)
    context = np.array([[[-2147483648, 0]]], dtype=np.int32)
    result = pixel_gate(wave, ones, ones, ones, context)
    assert result["uv_wavelength_pixels_before_quality_cuts"] == 1
    assert result["positive_error_weight_context_supported_pixels"] == 1
    assert result["uv_supported_pixels_after_supplied_dq"] is None


def test_bad_flags_cannot_explain_missing_coordinates():
    wave = np.array([[1.84, 3.9]])
    ones = np.ones_like(wave)
    context = np.ones((1, *wave.shape), dtype=np.int32)
    result = pixel_gate(wave, ones, ones, ones, context, dq=np.ones_like(wave, dtype=np.uint32))
    assert result["uv_wavelength_pixels_before_quality_cuts"] == 0
    assert result["uv_supported_pixels_after_supplied_dq"] == 0


def test_coordinate_is_counted_before_science_or_flag_mask():
    wave = np.array([[2.5]])
    ones = np.ones_like(wave)
    result = pixel_gate(wave, np.array([[np.nan]]), ones, ones, np.zeros((1, 1, 1), dtype=np.int32))
    assert result["uv_wavelength_pixels_before_quality_cuts"] == 1
    assert result["uv_supported_pixels_before_dq"] == 0
