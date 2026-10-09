from __future__ import annotations

import hashlib
import json
import numpy as np
import pytest
from astropy.io import fits
from discovery.deep_reference_comparison import load_deep_cutout, measurement

def receipt(path):
    path.with_name(path.name + ".provenance.json").write_text(json.dumps({
        "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
    }))


def test_inverse_variance_and_scaled_flux_unit(tmp_path):
    sci = np.zeros((48, 48), dtype=np.float32)
    sci[24, 24] = 3
    header = fits.Header({"CTYPE1": "RA---TAN", "CTYPE2": "DEC--TAN", "CRVAL1": 53.0,
                         "CRVAL2": -27.0, "CRPIX1": 25, "CRPIX2": 25,
                         "CDELT1": -.05 / 3600, "CDELT2": .05 / 3600,
                         "BUNIT": "10.0*nanoJansky", "EXTVER": "SCI"})
    science = fits.PrimaryHDU(sci, header=header)
    weight = fits.ImageHDU(np.full(sci.shape, 25), name="F444W-CLEAR")
    weight.header["EXTVER"] = "WHT"
    path = tmp_path / "cutout.fits"
    fits.HDUList([science, weight]).writeto(path)
    receipt(path)
    bundle, _ = load_deep_cutout(path)
    np.testing.assert_allclose(bundle["err"], .2)
    row = measurement(bundle, x=24, y=24)
    assert row["calibration_status"] == "calibrated"
    assert row["background_subtracted_flux_jy"] == pytest.approx(30e-9)


