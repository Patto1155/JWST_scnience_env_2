"""Controls for the calibration replay, sample leverage and actual DQ accounting."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from tools.jwst.line_sensitivity import Extraction, SOURCE_HASH
from tools.jwst.point_resolution import (
    leave_one_bin_out,
    native_batch_quality,
    native_quality_support,
    read_point_resolution,
)


def test_point_curve_replay_rejects_corrupt_transform(tmp_path):
    path = tmp_path / "point.csv"
    path.write_text("wavelength_um,point_R\n1,100\n2,200\n3,300\n")
    receipt = {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "coefficients_descending": [100, 0],
        "source_receipt": {"requested_url": "https://example.invalid/pinned", "sha256": "abc"},
        "grid_receipt": {"sha256": "def"},
        "citation": "test fixture",
    }
    provenance = Path(str(path) + ".provenance.json")
    provenance.write_text(json.dumps(receipt))
    wave, resolution, metadata = read_point_resolution(path)
    assert np.allclose(wave, [1, 2, 3])
    assert np.allclose(resolution, [100, 200, 300])
    assert metadata["transform_replayed"]
    receipt["coefficients_descending"] = [101, 0]
    provenance.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="cannot be replayed"):
        read_point_resolution(path)
    path.write_text(path.read_text() + "4,400\n")
    with pytest.raises(ValueError, match="does not match receipt"):
        read_point_resolution(path)


def test_leverage_omits_each_good_bin_once_preserving_original_grid():
    wave = np.linspace(2.15, 3.2, 55)
    error = np.full_like(wave, 0.002)
    mask = np.ones(len(wave), dtype=bool)
    mask[10] = False
    # Independent smooth known continuum. Omitting individual bins should never
    # invent line flux even though those bins define the sampling geometry.
    ext = Extraction("flat", wave, 0.02 + 0.003 * (wave - 2.675), error, mask, {})
    result = leave_one_bin_out(ext, np.array([0.5, 6]), np.array([100, 100]))
    assert result["full_bin_grid_preserved"]
    assert result["deletions"] == 54
    assert {r["omitted_full_grid_index"] for r in result["records"]} == set(np.flatnonzero(mask))
    assert all(r["remaining_fit_bins"] == 53 for r in result["records"])
    assert all(np.max(np.abs(r["line_fluxes"])) < 1e-9 for r in result["records"])
    assert mask[10] == 0  # input mask was not mutated


def test_native_dq_support_rejects_saturated_and_nonfinite(tmp_path):
    wave = np.array([[2.296, 2.299, 2.394], [2.297, 2.298, 2.395]])
    science = np.ones_like(wave)
    error = np.ones_like(wave)
    science[1, 1] = np.nan
    dq = np.array([[0, 1, 0], [2, 0, 0]], dtype=np.uint32)
    primary = fits.PrimaryHDU()
    primary.header["CAL_VER"] = "test"
    primary.header["CRDS_CTX"] = "test"
    sci = fits.ImageHDU(science, name="SCI")
    sci.header["SRCNAME"] = "5224_277193"
    sci.header["SRCTYPE"] = "EXTENDED"
    sci.header["BUNIT"] = "MJy/sr"
    path = tmp_path / "native.fits"
    fits.HDUList(
        [
            primary,
            sci,
            fits.ImageHDU(error, name="ERR"),
            fits.ImageHDU(wave, name="WAVELENGTH"),
            fits.ImageHDU(dq, name="DQ"),
        ]
    ).writeto(path)
    Path(str(path) + ".provenance.json").write_text(
        json.dumps(
            {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "input_receipt": {"requested_url": "https://example.invalid/native"},
                "exposure_time_s": 100,
            }
        )
    )
    source_wave = np.linspace(2.15, 3.2, 100)
    leverage = {
        "per_line_extrema": {
            n: {"minimum_omitted_index": int(np.argmin(np.abs(source_wave - center)))}
            for n, center in [("NIV", 2.297), ("CIV", 2.394)]
        }
    }
    result = native_quality_support(
        path, np.array([0.5, 6]), np.array([100, 100]), leverage, source_wave
    )
    assert result["usable_native_pixels"] == 3
    assert result["line_window_quality_support"]["NIV"]["do_not_use_pixels_all_rows"] == 1
    assert result["line_window_quality_support"]["NIV"]["saturated_pixels_all_rows"] == 1
    assert (
        result["highest_leverage_bin_native_overlap"]["NIV"]["native_usable_pixels_in_bin_all_rows"]
        == 1
    )
    # Counting the same exposure twice must not turn one native quality control
    # into two independent observations.
    batch_path = tmp_path / "batch.json"
    record = {
        "derived_slit_filename": path.name,
        "identity_quality": {"sha256": result["input_sha256"]},
        "metadata": {"position_number": 1},
    }
    batch_path.write_text(
        json.dumps(
            {
                "source_spectrum_receipt": {"sha256": SOURCE_HASH},
                "exposures": [record, record],
                "budget": {"actual_original_bytes": 100},
            }
        )
    )
    with pytest.raises(ValueError, match="Duplicate exposure"):
        native_batch_quality(
            batch_path, tmp_path, np.array([0.5, 6]), np.array([100, 100]), leverage, source_wave
        )
