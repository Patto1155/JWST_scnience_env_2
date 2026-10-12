"""Independent numerical controls for the frozen FRB feasibility oracle."""

import csv
import gzip
import math
from pathlib import Path

import pytest

from discovery.research4_frb_review import NOMINAL_FLAGS, review


def write_control(path: Path, source_count: int) -> list[dict[str, str]]:
    rows = []
    for source in range(source_count):
        for burst in range(6):
            rows.append(
                {
                    "event_id": f"{source}_{burst}",
                    "repeater_name": f"control_{source}",
                    "sub_num": "0",
                    "snr_fitb": "30",
                    "dm_fitb": str(100 + burst),
                    "dm_fitb_err": "0.01",
                    "scat_time": str(math.exp(burst) * 0.01),
                    "scat_time_err": "0.0001",
                    "mjd_inf": str(59000 + burst),
                    "high_freq": "750",
                    "low_freq": "450",
                    "peak_freq": "500",
                    **{flag: "0" for flag in NOMINAL_FLAGS},
                }
            )
    write_rows(path, rows)
    return rows


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_exact_centered_covariance_and_temporal_halves(tmp_path):
    catalog = tmp_path / "synthetic.csv"
    write_control(catalog, 6)
    result = review(catalog)
    assert result["feasibility_gate_passed"]
    assert result["equal_source_mean_covariance"] == pytest.approx(3.5, abs=1e-12)
    for source in result["source_statistics"]:
        assert source["early"]["covariance_ddof1"] == pytest.approx(1.0, abs=1e-12)
        assert source["late"]["covariance_ddof1"] == pytest.approx(1.0, abs=1e-12)


def test_insufficient_sources_stop_before_covariance(tmp_path):
    catalog = tmp_path / "synthetic.csv"
    write_control(catalog, 5)
    result = review(catalog)
    assert result["qualified_source_count"] == 5
    assert not result["covariances_computed"]
    assert result["equal_source_mean_covariance"] is None
    assert result["source_statistics"] == []


def test_limits_and_shared_subbursts_do_not_create_extra_events(tmp_path):
    catalog = tmp_path / "synthetic.csv"
    rows = write_control(catalog, 6)
    rows[0]["scat_time"] = "<0.01"
    rows.append({**rows[1], "sub_num": "1"})
    write_rows(catalog, rows)
    result = review(catalog)
    assert result["row_count"] == 37
    assert result["unique_event_count"] == 36
    assert len(result["selected_event_ids"]) == 34
    assert "0_0" not in result["selected_event_ids"]
    assert "0_1" not in result["selected_event_ids"]
    assert result["qualified_source_count"] == 5
    assert not result["covariances_computed"]


def test_gzip_transport_preserves_original_csv_identity_and_selection(tmp_path):
    catalog = tmp_path / "synthetic.csv"
    write_control(catalog, 6)
    packed = tmp_path / "synthetic.csv.gz"
    packed.write_bytes(gzip.compress(catalog.read_bytes(), mtime=0))
    plain = review(catalog)
    compressed = review(packed)
    for key in (
        "catalog_bytes",
        "catalog_sha256",
        "selected_event_ids",
        "source_statistics",
        "equal_source_mean_covariance",
    ):
        assert compressed[key] == plain[key]
    assert compressed["input_artifact_bytes"] < plain["input_artifact_bytes"]
    assert compressed["input_artifact_sha256"] != plain["input_artifact_sha256"]
