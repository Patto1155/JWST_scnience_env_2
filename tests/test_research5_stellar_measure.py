"""Regression for the real QLP legacy/new flux-column transition."""

import json

import numpy as np
import pytest
from astropy.io import fits

from discovery import research5_stellar_measure as pilot


def test_qlp_column_rename_preserves_mode_measurement(tmp_path, monkeypatch):
    """A renamed detrended column must not disappear from epoch comparisons."""
    times = np.linspace(3100, 3125, 512)
    dt = 200 / 86400
    signal = 1 + 0.001 * np.sinc(pilot.FREQ * dt) * np.cos(
        2 * np.pi * pilot.FREQ * (times - pilot.EPOCH)
    )
    receipts = []
    for sector, name in [(40, "KSPSAP_FLUX"), (74, "DET_FLUX")]:
        columns = [
            fits.Column(name="TIME", format="D", array=times),
            fits.Column(name="QUALITY", format="J", array=np.zeros(len(times))),
            fits.Column(name="SAP_FLUX", format="D", array=signal),
            fits.Column(name=name, format="D", array=signal),
            fits.Column(name=f"{name}_SML", format="D", array=signal),
        ]
        table = fits.BinTableHDU.from_columns(columns)
        table.header["TIMEDEL"] = dt
        path = tmp_path / f"s{sector}.fits"
        fits.HDUList([fits.PrimaryHDU(), table]).writeto(path)
        receipts.append({"sector": sector, "compressed_path": str(path)})
    (tmp_path / "research5_stellar_inputs.json").write_text(json.dumps(receipts))
    monkeypatch.setattr(pilot, "OUT", tmp_path)
    pilot.main()
    report = json.loads((tmp_path / "research5_stellar_measurements.json").read_text())
    old, new = report["rows"]
    a = old["fits"]["KSPSAP_FLUX_SML"]["amplitude_ppm"]
    b = new["fits"]["DET_FLUX_SML"]["amplitude_ppm"]
    assert b == pytest.approx(a, abs=1e-9)
    assert b == pytest.approx(1000, abs=2)
    assert new["fits"]["DET_FLUX"][
        "1000ppm_integration_aware_window_recovery_ppm"
    ] == pytest.approx(1000, abs=1e-8)
