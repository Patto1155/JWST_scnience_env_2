"""Replay the frozen SMACS raw-reduction dependency gate from compact receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from discovery.smacs_raw_preflight import DATA_CAP, FREEZE_COMMIT, RAW_NAMES


def evaluate(downloads: dict, headers: dict, selector: dict, reference_heads: dict) -> dict:
    """Missing/over-budget calibration cannot be reported as a measured null."""
    receipts = downloads.get("receipts", [])
    if downloads.get("freeze_commit") != FREEZE_COMMIT:
        raise ValueError("raw receipts do not identify the frozen design")
    if sorted(row.get("product_id", "") for row in receipts) != sorted(RAW_NAMES):
        raise ValueError("raw contributors differ from the frozen pair")
    if len(headers.get("products", [])) != 2:
        raise ValueError("both raw header identities are required")
    for row in headers["products"]:
        h = row["header"]
        if h["FILENAME"] not in RAW_NAMES or h["FILTER"] != "F444W":
            raise ValueError("raw header identity mismatch")
    refs = selector.get("references", {})
    dark_name = refs.get("dark")
    dark_rows = [r for r in reference_heads.get("products", []) if r["filename"] == dark_name]
    if len(dark_rows) != 1 or dark_rows[0].get("status") != 200:
        raise ValueError("required dark reference has no successful identity/size probe")
    dark_bytes = int(dark_rows[0]["content_length"])
    body_bytes = sum(int(row["bytes"]) for row in receipts)
    if dark_bytes + body_bytes <= DATA_CAP:
        raise ValueError("this replay does not establish a calibration budget block")
    return {
        "freeze_commit": FREEZE_COMMIT,
        "target": {"source_id": 1043, "ra_deg": 110.63858928243717, "dec_deg": -73.48487214542632},
        "status": "blocked: required reference exceeds frozen transfer cap",
        "scientific_verdict": "independent-reduction persistence not measured",
        "grade_proposal_for_parent": "Unconfirmed lead",
        "new_context": selector["context"],
        "old_context": "jwst_1535.pmap",
        "required_dark_reference": dark_name,
        "dark_reference_bytes": dark_bytes,
        "verified_raw_body_bytes": body_bytes,
        "dark_plus_raw_minimum_bytes": dark_bytes + body_bytes,
        "data_cap_bytes": DATA_CAP,
        "control_artifacts": {"null": None, "injection_recovery": None, "independent_repeat": None},
        "first_datamodel_open_started_utc": selector.get("first_datamodel_open_started_utc"),
        "not_run": [
            "Detector1 or Image2 raw reprocessing",
            "new calibrated photometry, centroid association or held-out astrometry",
            "structured-light rank null under four frozen background operators",
            "same-field measured-PSF calibration and positive/negative injection recovery",
            "other-epoch forced photometry (both cone queries timed out)",
            "source identity, high-redshift/dropout classification or variability inference",
        ],
    }


def replay(receipt_dir: Path) -> dict:
    names = (
        "e_raw_downloads.json",
        "e_raw_headers.json",
        "e_crds_remote.json",
        "e_reference_heads.json",
    )
    inputs = [json.loads((receipt_dir / name).read_text()) for name in names]
    result = evaluate(*inputs)
    result["receipt_sha256"] = {
        name: hashlib.sha256((receipt_dir / name).read_bytes()).hexdigest() for name in names
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = replay(args.receipt_dir)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
