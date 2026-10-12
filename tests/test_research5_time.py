"""Scientific-boundary tests for time-domain source and state comparisons."""

import gzip
import hashlib
import json

import pytest

from discovery import research5_time_scout as acquisition
from discovery.research5_time_followup import compare, quality_rows


def test_input_identity_rejects_changed_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(acquisition, "OUT", tmp_path)
    body = b"mjd,mag\n60000,18\n"
    (tmp_path / "research5_time_sample.csv.gz").write_bytes(gzip.compress(body))
    receipt = {"status": 200, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    (tmp_path / "research5_time_sample.csv.receipt.json").write_text(json.dumps(receipt))
    assert acquisition.verified_bytes("sample.csv") == body
    (tmp_path / "research5_time_sample.csv.gz").write_bytes(gzip.compress(body + b"changed"))
    with pytest.raises(ValueError, match="Input identity failed"):
        acquisition.verified_bytes("sample.csv")


def test_nonfinite_astrometry_and_nonpositive_errors_rejected():
    g = {"ra": "57", "dec": "35", "pmra": "0", "pmdec": "0"}
    row = {"mjd": "60000", "mag": "18", "magerr": ".05", "ra": "57", "dec": "35", "catflags": "0"}
    assert len(quality_rows([row], g)) == 1
    for field in ["ra", "dec", "mjd", "mag", "magerr"]:
        bad = {**row, field: "nan"}
        assert quality_rows([bad], g) == []
    for err in ["0", "-.01"]:
        assert quality_rows([{**row, "magerr": err}], g) == []


def test_epoch_binning_ignores_exposure_pseudoreplication_and_outside_windows():
    a = [{"mjd": i * 30 + 1, "mag": 18.0} for i in range(3)]
    b = [{"mjd": i * 30 + 301, "mag": 18.6} for i in range(3)]
    data = a * 20 + b * 20 + [{"mjd": 200, "mag": -100.0}]
    result = compare(data, [[0, 90]], [[300, 390]])
    assert result["a_bins"] == result["b_bins"] == 3
    assert result["a_obs"] == result["b_obs"] == 60
    assert result["contrast_b_minus_a"] == pytest.approx(0.6)
    assert result["ci95_conditional_30day"] == pytest.approx([0.6, 0.6])
    # Distinct objects are passed separately: neither acquires the other's state.
    assert compare(a, [[0, 90]], [[300, 390]])["eligible"] is False
    assert compare(b, [[0, 90]], [[300, 390]])["eligible"] is False
