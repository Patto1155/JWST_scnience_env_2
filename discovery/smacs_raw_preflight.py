"""Frozen SMACS raw-product identity and transfer preflight; no photometry."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

FREEZE_COMMIT = "90110ef1913beff9d8537f5fc05361655cbdee6f"
RAW_NAMES = tuple(
    f"jw02736001001_02105_{exposure}_nrcalong_uncal.fits" for exposure in ("00003", "00004")
)
DATA_CAP = 1_610_612_736
METADATA_CAP = 30_000_000
DOWNLOAD_ROOT = "https://mast.stsci.edu/api/v0.1/Download/file?"


def planned_budget(sizes: list[int], *, already_charged: int = 0) -> dict:
    """Refuse missing/invalid lengths or transfers exceeding the frozen ceiling."""
    if len(sizes) != 2 or any(type(size) is not int or size <= 0 for size in sizes):
        raise ValueError("both frozen raw products require positive integer lengths")
    if type(already_charged) is not int or already_charged < 0:
        raise ValueError("invalid charged byte count")
    planned = sum(sizes)
    if already_charged + planned > DATA_CAP:
        raise ValueError("raw transfer alone exceeds frozen total cap")
    return {
        "raw_planned_bytes": planned,
        "already_charged_bytes": already_charged,
        "remaining_for_calibration_and_epoch_bytes": DATA_CAP - already_charged - planned,
    }


def environment() -> dict:
    versions = {}
    for package in ("jwst", "crds", "astropy", "numpy"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def run(*, timeout: float = 30) -> dict:
    """HEAD the fixed UNCAL names and acquire a bounded metadata-only cone."""
    probes = []
    for name in RAW_NAMES:
        url = DOWNLOAD_ROOT + urlencode({"uri": "mast:JWST/product/" + name})
        record = {"filename": name, "requested_url": url}
        try:
            with urlopen(Request(url, method="HEAD"), timeout=timeout) as response:
                record.update(
                    status=response.status,
                    resolved_url=response.url,
                    content_length=response.headers.get("Content-Length"),
                    content_type=response.headers.get("Content-Type"),
                )
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        probes.append(record)
    cone_request = {
        "service": "Mast.Caom.Cone",
        "params": {"ra": 110.63858928243717, "dec": -73.48487214542632, "radius": 0.001},
        "format": "json",
        "pagesize": 1000,
        "page": 1,
    }
    cone = {"request": cone_request, "requested_url": "https://mast.stsci.edu/api/v0/invoke"}
    try:
        request = Request(
            cone["requested_url"],
            data=urlencode({"request": json.dumps(cone_request)}).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urlopen(request, timeout=timeout) as response:
            body = response.read(METADATA_CAP + 1)
            cone.update(
                status=response.status, bytes=len(body), sha256=hashlib.sha256(body).hexdigest()
            )
            if len(body) > METADATA_CAP:
                raise ValueError("metadata ceiling exceeded; no further requests")
            payload = json.loads(body)
            cone["mast_status"] = payload.get("status")
            cone["paging"] = payload.get("paging")
            # Only observation metadata, deliberately no scientific pixel/flux arrays.
            keys = (
                "obsid",
                "obs_id",
                "obs_collection",
                "instrument_name",
                "filters",
                "t_min",
                "t_max",
                "dataURL",
                "s_region",
                "target_name",
                "calib_level",
            )
            cone["observations"] = [
                {key: row.get(key) for key in keys}
                for row in payload.get("data", [])
                if row.get("obs_collection") == "JWST"
            ]
    except Exception as exc:
        cone["error"] = f"{type(exc).__name__}: {exc}"
    try:
        budget = planned_budget([int(row["content_length"]) for row in probes])
    except (KeyError, TypeError, ValueError) as exc:
        budget = {"status": "blocked", "reason": str(exc)}
    return {
        "freeze_commit": FREEZE_COMMIT,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "environment": environment(),
        "raw_metadata": probes,
        "cone_metadata": cone,
        "budget": budget,
        "raw_body_bytes": 0,
        "outcome_arrays_opened": False,
        "scientific_verdict": "not measured",
        "limitations": [
            "HEAD response does not verify body identity, raw calibration or coverage.",
            "Cone metadata does not establish target coverage or epoch usability.",
            "No raw repeat, null control or injection recovery is executed by this preflight.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    result = run(timeout=args.timeout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "budget": result["budget"]}))


if __name__ == "__main__":
    main()
