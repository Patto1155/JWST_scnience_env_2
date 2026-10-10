"""Independently verify incomplete actual Cloudy outputs without scoring them."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(receipt, runs):
    manifest = json.loads(receipt.read_text())
    records = []
    for row in manifest["records"]:
        if not row["files"]:
            records.append({"model_id": row["model_id"], "raw_files_declared": False})
            continue
        for item in row["files"]:
            path = runs / item["name"]
            assert path.stat().st_size == item["bytes"] and digest(path) == item["sha256"]
        text = (runs / (row["model_id"] + ".out")).read_text()
        assert "Cloudy ends:" not in text
        assert (runs / (row["model_id"] + ".lin")).stat().st_size == 0
        assert (runs / (row["model_id"] + ".avr")).stat().st_size == 0
        assert not row["scientific_prediction_used"] and not row["complete_thermal_output"]
        records.append(
            {
                "model_id": row["model_id"],
                "observed_complete_thermal_summary": False,
                "line_table_bytes": 0,
                "temperature_average_bytes": 0,
                "all_file_hashes_match": True,
            }
        )
    return {
        "schema_version": 1,
        "source_receipt_sha256": digest(receipt),
        "records": records,
        "scope": (
            "Independent raw-file hashes and observed incompleteness verified. "
            "Execution wallcap/cancellation timing cannot be reconstructed from these "
            "files alone; no incomplete prediction accepted."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("receipt", "runs", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.receipt, args.runs), indent=2) + "\n")


if __name__ == "__main__":
    main()
