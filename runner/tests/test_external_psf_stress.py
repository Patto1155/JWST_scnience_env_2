"""Independent PSF resampling and scientific-provenance failure tests."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from discovery.external_psf_stress import (
    gaussian_kernel, independent_stamp, load_verified_psf, resample_kernel, run_cell,
)

ROOT = Path(__file__).resolve().parents[2]


def test_identity_resampling_and_flux_preservation():
    kernel = gaussian_kernel(1.5, 31)
    result, meta = resample_kernel(kernel, 0.063, 0.063, 31)
    np.testing.assert_allclose(result, kernel, atol=1e-14)
    assert result.sum() == pytest.approx(1.0)
    assert meta["retained_fraction"] == pytest.approx(1.0)


def test_overlap_resampling_retains_symmetry_and_records_lost_wings():
    result, meta = resample_kernel(gaussian_kernel(6, 61), 0.03, 0.063, 9)
    assert 0 < meta["retained_fraction"] < 1
    assert result.sum() == pytest.approx(1)
    np.testing.assert_allclose(result, result[::-1, ::-1], atol=1e-14)
    assert np.unravel_index(result.argmax(), result.shape) == (4, 4)


@pytest.mark.parametrize("kernel", [np.ones((4, 4)), np.zeros((5, 5)), -np.ones((5, 5)),
                                    np.full((5, 5), np.nan)])
def test_bad_template_rejected(kernel):
    with pytest.raises(ValueError):
        resample_kernel(kernel, .03, .063)


def test_profile_renderer_is_normalized_and_extension_broadens():
    psf = gaussian_kernel(1.0)
    np.testing.assert_array_equal(independent_stamp(psf, 0), psf)
    extended = independent_stamp(psf, 1.5)
    assert extended.sum() == pytest.approx(1)
    assert extended[30, 30] < psf[30, 30]
    assert np.all(extended >= 0)


def test_verified_input_refuses_changed_bytes_and_wrong_filter(tmp_path):
    path = tmp_path / "psf.fits"
    hdu = fits.PrimaryHDU(gaussian_kernel(2, 61))
    hdu.header["PIXELSCL"] = .03
    hdu.header["FILTER"] = "F444W"
    hdu.writeto(path)
    raw = path.read_bytes()
    receipt = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
               "requested_url": "https://example.org/psf.fits", "resolved_url": "https://example.org/psf.fits",
               "retrieved_utc": "2026-10-09T00:00:00+00:00"}
    path.with_name(path.name + ".provenance.json").write_text(json.dumps(receipt))
    kernel, _ = load_verified_psf(path, "F444W")
    assert kernel.sum() == pytest.approx(1)
    with pytest.raises(ValueError, match="FILTER"):
        load_verified_psf(path, "F277W")
    path.write_bytes(raw + b"tampered")
    with pytest.raises(ValueError, match="receipt"):
        load_verified_psf(path, "F444W")


def test_actual_detection_chain_preserves_trial_counts_and_paired_noise():
    model = json.loads((ROOT / "research_output/artifact_classifier.json").read_text())
    args = dict(flux=240.0, radius=0, seed=913, batch=0)
    a = run_cell(gaussian_kernel(1), "F444W", model, kind="a", **args)
    b = run_cell(gaussian_kernel(1), "F444W", model, kind="b", **args)
    assert len(a) == len(b) == 16
    assert [x["paired_trial_id"] for x in a] == [x["paired_trial_id"] for x in b]
    assert [x["recovered"] for x in a] == [True] * 16
    assert [x["artifact_score"] for x in a] == [x["artifact_score"] for x in b]
    assert all(x["match_distance_px"] <= 2.5 for x in a)
