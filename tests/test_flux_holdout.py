"""Safeguards for a prospectively frozen one-shot outcome access."""

import json

import pytest
import requests

from data_pipeline import flux_holdout


def test_denied_preflight_preserves_holdout_and_prevents_retry(tmp_path, monkeypatch):
    prediction = tmp_path / "prediction.json"
    prediction.write_text(json.dumps({"rows": [{
        "unique_id": "goods-s-mediumjwst_1", "configuration": "g235m_f170lp"
    }]}))
    monkeypatch.setattr(flux_holdout.subprocess, "check_output",
                        lambda command, **kw: "commit" if kw else prediction.read_bytes())
    attempts = []

    def deny(*args, **kwargs):
        attempts.append(args[0])
        raise requests.exceptions.ProxyError("Tunnel connection failed: 403 Forbidden")

    monkeypatch.setattr(flux_holdout.requests, "head", deny)
    monkeypatch.setattr(flux_holdout.requests, "get",
                        lambda *a, **kw: pytest.fail("Denied HEAD must never issue GET"))
    output = tmp_path / "result.json"
    flux_holdout.run(prediction, output)
    report = json.loads(output.read_text())
    assert report["body_bytes"] == 0 and report["rows"] == []
    assert "NOT_EVALUABLE" in report["verdict"]
    with pytest.raises(FileExistsError):
        flux_holdout.run(prediction, output)
    assert len(attempts) == 1


def test_uncommitted_prediction_refused_before_network(tmp_path, monkeypatch):
    prediction = tmp_path / "prediction.json"
    prediction.write_text('{"rows": []}')
    monkeypatch.setattr(flux_holdout.subprocess, "check_output",
                        lambda command, **kw: "commit" if kw else b"different")
    monkeypatch.setattr(flux_holdout.requests, "head",
                        lambda *a, **kw: pytest.fail("No access before committed freeze"))
    with pytest.raises(ValueError, match="committed unchanged"):
        flux_holdout.run(prediction, tmp_path / "result.json")
