"""Frozen known-YSO metadata feasibility pilot; never downloads science pixels."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("AA Tau", "BP Tau", "DG Tau", "DR Tau", "HL Tau", "T Tau")
FREEZE = ROOT / "docs/frozen/F_YSO_DESIGN.md"
FIRST_OLD_MJD, LAST_OLD_MJD = 61269.077386667, 61277.226


def sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


class BoundedMetadata:
    """Account consumed bodies even on non-200 or parsing failure; no raw retention."""

    def __init__(self, out: Path, timeout: float = 12, cap: int = 30_000_000):
        self.out, self.timeout, self.cap = out, timeout, cap
        self.out.mkdir(parents=True, exist_ok=True)
        self.total = 0
        self.receipts: list[dict] = []
        self.first_access: str | None = None

    def get(self, name: str, url: str, params: dict | None = None) -> bytes | None:
        started = time.monotonic()
        timestamp = datetime.now(timezone.utc).isoformat()
        if self.first_access is None:
            self.first_access = timestamp
        receipt = {
            "name": name,
            "requested_url": url,
            "params": params,
            "utc_started": timestamp,
            "status": None,
            "bytes": 0,
        }
        chunks: list[bytes] = []
        try:
            # Conservative cap on each read; count before testing budget.
            with requests.get(url, params=params, stream=True, timeout=self.timeout) as response:
                receipt.update(url=response.url, status=response.status_code)
                for chunk in response.iter_content(65536):
                    self.total += len(chunk)
                    receipt["bytes"] += len(chunk)
                    chunks.append(chunk)
                    if self.total > self.cap:
                        raise RuntimeError("Metadata response-body budget exceeded")
                if response.status_code != 200:
                    raise RuntimeError(f"HTTP {response.status_code}")
            body = b"".join(chunks)
        except (requests.RequestException, RuntimeError) as error:
            receipt["error"] = str(error)
            body = None
        receipt["sha256_consumed_body"] = sha256(b"".join(chunks))
        receipt["elapsed_seconds"] = time.monotonic() - started
        self.receipts.append(receipt)
        (self.out / f"f_{name}_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        return body


def csv_rows(body: bytes) -> list[dict]:
    text = body.decode("utf-8-sig")
    if text.lstrip().startswith("<"):
        raise ValueError("Archive response is XML/HTML, not requested CSV")
    return list(csv.DictReader(io.StringIO(text)))


def epoch_inventory(rows: list[dict], baseline_keys: set[tuple[str, str]]) -> dict:
    """Distinct physical exposures; metadata cannot certify spectral W1 coverage."""
    exposures: dict[tuple[str, str], dict] = {}
    for row in rows:
        if not row.get("obs_id") or not row.get("energy_bandpassname"):
            raise ValueError("Missing exposure identity")
        key = row["obs_id"], row["energy_bandpassname"]
        mjd = float(row["t_min"])
        item = {
            "obs_id": key[0],
            "detector": key[1],
            "mjd_start": mjd,
            "collection": row.get("obs_collection"),
            "access_url": row.get("access_url"),
        }
        exposures.setdefault(key, item)
    values = sorted(exposures.values(), key=lambda x: (x["mjd_start"], x["obs_id"], x["detector"]))
    in_window = [x for x in values if 61090 <= x["mjd_start"] <= 61310]
    new = [x for x in values if (x["obs_id"], x["detector"]) not in baseline_keys]
    new_in_window = [x for x in new if 61090 <= x["mjd_start"] <= 61310]
    dates = [x["mjd_start"] for x in values]
    return {
        "raw_rows": len(rows),
        "unique_physical_exposures": len(values),
        "date_range_mjd": [min(dates), max(dates)] if dates else None,
        "new_exposures_vs_baseline": new,
        "new_inside_original_window": new_in_window,
        "in_original_window_count": len(in_window),
        "source_W1_coverage": "not measured: detector bandpass is not source response",
        "metadata_spans_30days": bool(dates and max(dates) - min(dates) >= 30),
        "exposures": values,
        "scientific_grade": "not assessed by metadata",
    }


def exact_identity(rows: list[dict], name: str) -> dict:
    if len(rows) != 1:
        return {"name": name, "status": "blocked: exact identity is not unique", "rows": rows}
    row = rows[0]
    # SIMBAD's compact main object types for YSO and T Tauri; no flux/type inference.
    otype = row.get("otype", "").strip()
    if otype not in {"TT*", "Y*O", "Or*", "YSO", "TTau*"}:
        return {
            "name": name,
            "status": "blocked: main type is not frozen eligible class",
            "rows": rows,
        }
    return {
        "name": name,
        "status": "identity eligible",
        "main_id": row["main_id"],
        "otype": otype,
        "ra": float(row["ra"]),
        "dec": float(row["dec"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "research_output/session_20261014")
    parser.add_argument("--timeout", type=float, default=12)
    args = parser.parse_args()
    # Verify actual frozen commit against committed file before any acquisition.
    import subprocess

    freeze_commit = subprocess.check_output(
        ["git", "log", "--format=%H", "-1", "--", "docs/frozen/F_YSO_DESIGN.md"],
        cwd=ROOT,
        text=True,
    ).strip()
    committed = subprocess.check_output(
        ["git", "show", f"{freeze_commit}:docs/frozen/F_YSO_DESIGN.md"], cwd=ROOT
    )
    if FREEZE.read_bytes() != committed:
        raise RuntimeError("Frozen design has uncommitted changes")
    acquisition = BoundedMetadata(args.out, args.timeout)
    docs = acquisition.get(
        "spherex_overview", "https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_qr.html"
    )
    collections = (
        sorted({f"spherex_qr{x}" for x in re.findall(r"QR([23])", docs.decode(errors="replace"))})
        if docs
        else []
    )
    # QR3 is known input, not a claim that no newer release exists.
    collections = sorted(set(collections + ["spherex_qr3"]))
    import gzip

    baseline_path = ROOT / "research_output/research5_time_spherex_qr3_sia.csv.gz"
    baseline = csv_rows(gzip.decompress(baseline_path.read_bytes()))
    baseline_keys = {(r["obs_id"], r["energy_bandpassname"]) for r in baseline}
    summary = {
        "freeze_commit": freeze_commit,
        "freeze_sha256": sha256(committed),
        "mode": "metadata only; no flux/pixels/lightcurves acquired",
        "collection_discovery_complete": docs is not None,
        "collections_checked": collections,
        "executed_code_sha256": sha256(Path(__file__).read_bytes()),
        "targets": [],
        "DDE54": [],
    }
    for collection in collections:
        body = acquisition.get(
            f"dde54_{collection}",
            "https://irsa.ipac.caltech.edu/SIA",
            {
                "COLLECTION": collection,
                "POS": "CIRCLE 57.6419783 35.5856917 0.000277778",
                "BAND": "2.8e-6 3.9e-6",
                "CALIB": "2",
                "RESPONSEFORMAT": "CSV",
                "MAXREC": "10000",
            },
        )
        if body is None:
            summary["DDE54"].append({"collection": collection, "status": "archive query blocked"})
        else:
            try:
                inventory = epoch_inventory(csv_rows(body), baseline_keys)
                summary["DDE54"].append(
                    {"collection": collection, "status": "metadata received", **inventory}
                )
            except (ValueError, KeyError) as error:
                summary["DDE54"].append(
                    {"collection": collection, "status": f"parse blocked: {error}"}
                )
    for i, name in enumerate(TARGETS):
        query = (
            "SELECT DISTINCT b.main_id,b.otype,b.ra,b.dec FROM basic AS b JOIN ident AS i "
            f"ON b.oid=i.oidref WHERE i.id IN ('{name}','* {name}')"
        )
        body = acquisition.get(
            f"identity_{i}",
            "https://simbad.cds.unistra.fr/simbad/sim-tap/sync",
            {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": query},
        )
        if body is None:
            target = {"name": name, "status": "identity query blocked"}
        else:
            try:
                target = exact_identity(csv_rows(body), name)
            except (ValueError, KeyError) as error:
                target = {"name": name, "status": f"parse blocked: {error}"}
        if target["status"] == "identity eligible":
            all_rows = []
            target["collection_queries"] = []
            for collection in collections:
                body = acquisition.get(
                    f"yso_{i}_{collection}_sia",
                    "https://irsa.ipac.caltech.edu/SIA",
                    {
                        "COLLECTION": collection,
                        "POS": f"CIRCLE {target['ra']} {target['dec']} 0.000277778",
                        "BAND": "2.8e-6 3.9e-6",
                        "CALIB": "2",
                        "RESPONSEFORMAT": "CSV",
                        "MAXREC": "10000",
                    },
                )
                status = "archive query blocked"
                if body is not None:
                    try:
                        rows = csv_rows(body)
                        all_rows.extend(rows)
                        status = "metadata received"
                    except (ValueError, KeyError) as error:
                        status = f"parse blocked: {error}"
                target["collection_queries"].append({"collection": collection, "status": status})
            if all_rows:
                target["spherex_metadata"] = epoch_inventory(all_rows, set())
        summary["targets"].append(target)
    summary.update(
        first_instrumented_access_utc=acquisition.first_access,
        response_body_bytes=acquisition.total,
        receipts=acquisition.receipts,
        not_run=[
            "science pixel or lightcurve acquisition",
            "synthetic W1 measurement",
            "NEOWISE/ZTF time series",
            "field-star null",
            "injection recovery",
            "new-epoch claim",
            "GOODS-N",
        ],
    )
    (args.out / "f_metadata_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        json.dumps(
            {
                "freeze_commit": freeze_commit,
                "response_body_bytes": acquisition.total,
                "summary": str(args.out / "f_metadata_summary.json"),
            },
            indent=2,
        )
    )
    return 0  # Successful blocked receipt production is not a scientific PASS.


if __name__ == "__main__":
    raise SystemExit(main())
