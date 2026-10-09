"""Independent unit, axis, sign and double-application wavecorr oracles."""

import numpy as np
import pytest
from astropy.modeling.models import Tabular2D

from tools.jwst.native_wavecorr import (
    REFERENCE,
    ROOT,
    correct_wavelength,
    decode_blocks,
    load_wavecorr_replay,
    offset_pixels,
    read_reference,
)


def test_pinned_asdf_stride_axes_and_real_nonzero_center():
    reference = read_reference()
    assert reference["offset_pixels"][10, 10] == pytest.approx(0.015952110290527344)
    # This reference is a toy model, and a centered source does NOT mean zero.
    assert offset_pixels(reference, np.array([2.95e-6]), 0)[0] != 0
    assert np.all(reference["variance_values"] == 0.1**2)
    assert offset_pixels(reference, np.array([2.95e-6]), -0.1)[0] < 0


def test_offset_matches_independent_astropy_table_and_axis_counterexample():
    reference = read_reference()
    model = Tabular2D(
        points=(reference["wavelength_m"], reference["source_xpos_fraction_of_MOS_pitch"]),
        lookup_table=reference["offset_pixels"],
        method="linear",
        bounds_error=False,
        fill_value=None,
    )
    wave = np.array([0.52, 1.3, 2.296, 2.68, 3.17, 5.4]) * 1e-6
    expected = model(wave, -0.107)
    assert np.allclose(offset_pixels(reference, wave, -0.107), expected, rtol=0, atol=1e-15)
    transposed = {**reference, "offset_pixels": reference["offset_pixels"].T}
    assert np.max(np.abs(offset_pixels(transposed, wave, -0.107) - expected)) > 0.1


def test_wrong_units_position_and_corrupt_reference_fail_closed(tmp_path):
    reference = read_reference()
    for wrong in [np.array([2.68]), np.array([np.nan])]:
        with pytest.raises(ValueError, match="meters"):
            offset_pixels(reference, wrong, -0.1)
    for position in [-0.51, np.nan]:
        with pytest.raises(ValueError, match="fraction"):
            offset_pixels(reference, np.array([2.68e-6]), position)
    content = bytearray(REFERENCE.read_bytes())
    content[content.find(b"\xd3BLK") + 100] ^= 1
    changed = tmp_path / "reference.asdf"
    changed.write_bytes(content)
    with pytest.raises(ValueError, match="differs"):
        read_reference(changed)
    with pytest.raises(ValueError, match="checksum"):
        decode_blocks(bytes(content))


def test_linear_dispersion_sign_and_meter_to_micron_oracle():
    # Independent analytic reference has a constant -0.2 detector-pixel shift.
    reference = {
        "wavelength_m": np.array([1e-6, 4e-6]),
        "source_xpos_fraction_of_MOS_pitch": np.array([-0.5, 0.5]),
        "offset_pixels": np.full((2, 2), -0.2),
    }
    wave = np.broadcast_to(np.linspace(2, 3, 51), (3, 51)).copy()
    # Dispersion .02 micron/pixel must be supplied in METERS/pixel.
    dispersion = np.full_like(wave, 0.02e-6)
    result, _ = correct_wavelength(wave, dispersion, reference, -0.1, already_corrected=False)
    assert np.allclose(result, wave - 0.004, rtol=0, atol=1e-14)
    # Wrong sign would move the actual observed template in the opposite direction.
    assert not np.allclose(result, wave + 0.004)
    assert np.allclose(dispersion, np.gradient(wave, axis=1) * 1e-6)
    with pytest.raises(ValueError, match="meters per pixel"):
        correct_wavelength(wave, dispersion * 1e6, reference, -0.1, already_corrected=False)
    for state in [True, None]:
        with pytest.raises(ValueError, match="already"):
            correct_wavelength(wave, dispersion, reference, -0.1, already_corrected=state)


def test_mapping_uses_column_means_and_preserves_nan_science_mask():
    reference = read_reference()
    wave = np.broadcast_to(np.linspace(2.15, 3.2, 75), (3, 75)).copy()
    wave[0] -= 0.0001
    wave[2] += 0.0001
    wave[0, 25] = np.nan
    corrected, metadata = correct_wavelength(
        wave, np.full_like(wave, 0.01e-6), reference, -0.107, already_corrected=False
    )
    mean = np.nanmean(wave, axis=0)
    expected_mean = mean + offset_pixels(reference, mean * 1e-6, -0.107) * 0.01
    assert np.allclose(metadata["mapping_delta_wavelength_um"], expected_mean - mean, atol=1e-14)
    assert np.array_equal(np.isfinite(corrected), np.isfinite(wave))
    assert np.all(np.diff(corrected[1]) > 0)


def test_noninvertible_prediction_is_rejected():
    reference = {
        "wavelength_m": np.array([1e-6, 4e-6]),
        "source_xpos_fraction_of_MOS_pitch": np.array([-0.5, 0.5]),
        "offset_pixels": np.full((2, 2), -2000),
    }
    wave = np.broadcast_to(np.linspace(2, 3, 51), (3, 51)).copy()
    dispersion = np.broadcast_to(np.linspace(1e-8, 2e-8, 51), wave.shape)
    with pytest.raises(ValueError, match="Noninvertible"):
        correct_wavelength(wave, dispersion, reference, -0.1, already_corrected=False)


def test_compact_loader_has_real_derived_fields_without_fabricated_science():
    report = ROOT / "research_output/mom_native_wavecorr.json"
    original = load_wavecorr_replay(report, corrected=False)
    corrected = load_wavecorr_replay(report, corrected=True)
    for old, new in zip(original["data"], corrected["data"]):
        assert "science" not in old and "science" not in new
        assert "variance" not in new and "point_pathloss" not in new
        assert np.array_equal(old["good"], new["good"])
        assert np.any(np.abs(old["wave"] - new["wave"]) > 1e-5)
    assert np.array_equal(original["flux"], corrected["flux"], equal_nan=True)
    assert np.array_equal(original["covariance_blocks"], corrected["covariance_blocks"])
    assert np.array_equal(
        original["spatial_covariance_blocks"], corrected["spatial_covariance_blocks"]
    )
