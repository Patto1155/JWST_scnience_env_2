from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from data_pipeline.followup_data import acquire, extract_native_slit, point_coefficients, verify


def receipt(path):
    path.with_name(path.name + ".provenance.json").write_text(json.dumps({
        "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
    }))


def test_pinned_point_curve_is_positive_and_narrower_than_uniform():
    directory = Path(__file__).resolve().parents[1] / "data_sources/followup"
    verify(directory / "unite_point_prism_resolution.fits")
    point = fits.getdata(directory / "unite_point_prism_resolution.fits", 1)
    table = np.genfromtxt(directory / "unite_point_prism_resolution.csv", delimiter=",", names=True)
    assert len(point) == 1001
    np.testing.assert_allclose(point["R"], table["point_R"])
    assert np.all(point["R"] > 0)
    window = (point["WAVELENGTH"] > 2.2) & (point["WAVELENGTH"] < 3.0)
    assert np.all(table["point_R"][window] > table["uniform_R"][window])


def test_author_calibration_is_data_not_executed(tmp_path):
    source = 'raise RuntimeError("must never execute")\n_DEGRAAFF25_R_COEFFS: dict = {"prism": (0, 0, 0, 0, 0, 0, 100)}'
    assert point_coefficients(source)[-1] == 100
    with pytest.raises(ValueError, match="lacks"):
        point_coefficients('coefficients = {"prism": (100,)}')


def test_input_receipt_detects_corruption(tmp_path):
    path = tmp_path / "data"
    path.write_bytes(b"first")
    receipt(path)
    path.write_bytes(b"other")
    with pytest.raises(ValueError, match="SHA256"):
        verify(path)


def test_coherently_rewritten_cached_input_cannot_change_manifest(monkeypatch, tmp_path):
    import data_pipeline.followup_data as module

    path = tmp_path / "cached"
    path.write_bytes(b"altered")
    receipt(path)
    product = {"filename": path.name, "expected_bytes": 7,
               "sha256": hashlib.sha256(b"correct").hexdigest()}
    monkeypatch.setattr(module, "load_manifest", lambda _: {"sources": [{"products": [product]}]})
    monkeypatch.setattr(module, "fetch_product", lambda *a, **kw: pytest.fail("Network must not be called"))
    with pytest.raises(ValueError, match="pinned manifest"):
        acquire(tmp_path)
    product["sha256"] = hashlib.sha256(b"altered").hexdigest()
    product["max_bytes"] = 6
    with pytest.raises(ValueError, match="per-product ceiling"):
        acquire(tmp_path)


def test_native_slit_identity_dq_units_preserved(tmp_path):
    primary = fits.PrimaryHDU()
    science = fits.ImageHDU(np.ones((4, 5)), name="SCI")
    science.header.update({"EXTVER": 2, "SOURCEID": 277193, "SRCRA": 150.0933255,
                           "SRCDEC": 2.2731627, "SLITID": 21, "SRCTYPE": "EXTENDED", "BUNIT": "MJy/sr"})
    dq = np.zeros((4, 5), dtype=np.uint32)
    dq[0, 0], dq[0, 1], dq[0, 2] = 1, 2, 4
    planes = [science]
    for name, values in [("DQ", dq), ("ERR", np.ones((4, 5))), ("WAVELENGTH", np.full((4, 5), 2.3))]:
        hdu = fits.ImageHDU(values, name=name)
        hdu.header["EXTVER"] = 2
        planes.append(hdu)
    path = tmp_path / "official.fits"
    fits.HDUList([primary, *planes]).writeto(path)
    receipt(path)
    out = tmp_path / "target.fits"
    report = extract_native_slit(path, out)
    assert report["finite_positive_error_wavelength_and_dq_usable"] == 18
    assert report["dq_nonzero"] == 3
    assert report["source_type_upstream"] == "EXTENDED"
    np.testing.assert_array_equal(fits.getdata(out, ("DQ", 2)), dq)
    verify(out)
    with pytest.raises(ValueError, match="exactly one"):
        extract_native_slit(path, tmp_path / "bad.fits", source_id=99)


def test_committed_resolution_bytes_match_receipts():
    directory = Path(__file__).resolve().parents[1] / "data_sources/followup"
    for name in ["unite_point_prism_resolution.fits", "unite_point_prism_resolution.csv"]:
        verify(directory / name)
