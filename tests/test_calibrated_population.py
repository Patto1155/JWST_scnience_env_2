"""Numerical controls do not certify real-sky calibration."""

import numpy as np
import pytest
from scipy.special import ndtr

from data_pipeline.calibrated_population import marginal_fit, pull_summary


def test_signed_flux_and_nuisance_variance():
    wave = np.arange(1.97, 2.03, 0.001)
    center, dw, width = 2.0, 0.001, 0.0012
    profile = (ndtr((wave + dw / 2 - center) / width) - ndtr((wave - dw / 2 - center) / width)) / (
        dw * 10000
    )
    table = {
        "WAVELENGTH": wave,
        "FLUX": (0.2 - 100 * profile) * 1e-20,
        "FLUX_ERR": np.full(len(wave), 0.02e-20),
    }
    fit = marginal_fit(table, 5000, 3)
    assert abs(fit["flux_1e20"] + 100) < 5 * fit["error_1e20"]
    assert fit["flux_1e20"] < 0
    assert fit["error_1e20"] > 0
    assert fit["nodes"] == 41 * 41


def test_missing_window_is_not_a_flux_null():
    table = {"WAVELENGTH": np.array([1, 2, 3]), "FLUX": np.zeros(3), "FLUX_ERR": np.ones(3)}
    with pytest.raises(ValueError, match="Insufficient"):
        marginal_fit(table, 5000, 3)


def test_pull_width_cannot_identify_published_error_scale():
    assert pull_summary([1.0] * 11)["gate"] == "FAIL_TOO_FEW"
    result = pull_summary(list(np.linspace(-4, 4, 30)))
    assert result["sd"] > 2
    assert not result["error_scale_identified"]


def test_received_overlength_body_is_charged_before_rejection(tmp_path, monkeypatch):
    import json

    from data_pipeline import calibrated_population_run as runner

    class Response:
        status_code = 200
        headers = {"Content-Length": "4"}

        def raise_for_status(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def iter_content(self, size):
            yield b"12345678"

    monkeypatch.setattr(runner.requests, "head", lambda *a, **k: Response())
    monkeypatch.setattr(runner.requests, "get", lambda *a, **k: Response())
    draw = tmp_path / "draw.json"
    draw.write_text(
        json.dumps(
            {
                "training": [
                    {"unique_id": "goods-s-mediumjwst_123456", "configuration": "g235m_f170lp"}
                ],
                "heldout": [],
            }
        )
    )
    report = runner.run(draw, "training", tmp_path / "out.json", 0, "testfreeze")
    assert report["total_bytes"] == 8
    assert report["receipts"][0]["bytes"] == 8
    assert "charged" in report["results"][0]["error"]
