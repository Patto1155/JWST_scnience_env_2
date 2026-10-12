"""Bounded exploratory VarWISE acquisition; trusted operator workflow."""

import argparse
import gzip
import hashlib
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_output"


def acquire(name: str, url: str, params=None, limit=30_000_000):
    started = time.time()
    with requests.get(url, params=params, timeout=90, stream=True) as r:
        chunks = []
        total = 0
        for chunk in r.iter_content(65536):
            total += len(chunk)
            if total > limit:
                raise RuntimeError("Response budget exceeded")
            chunks.append(chunk)
        body = b"".join(chunks)
        receipt = {
            "url": r.url,
            "status": r.status_code,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "elapsed_seconds": time.time() - started,
            "exploratory": True,
        }
    path = OUT / f"research5_time_{name}"
    path.with_suffix(path.suffix + ".gz").write_bytes(gzip.compress(body, mtime=0))
    path.with_suffix(path.suffix + ".receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt), flush=True)
    if receipt["status"] != 200:
        raise RuntimeError(f"Acquisition failed: HTTP {receipt['status']}")
    return body


def verified_bytes(name: str) -> bytes:
    """Reject changed response bodies and unsuccessful acquisition responses."""
    path = OUT / f"research5_time_{name}"
    receipt = json.loads(path.with_suffix(path.suffix + ".receipt.json").read_text())
    body = gzip.decompress(path.with_suffix(path.suffix + ".gz").read_bytes())
    if (
        receipt["status"] != 200
        or len(body) != receipt["bytes"]
        or hashlib.sha256(body).hexdigest() != receipt["sha256"]
    ):
        raise ValueError(f"Input identity failed: {name}")
    return body


def tap(name, query):
    return acquire(
        name,
        "https://irsa.ipac.caltech.edu/TAP/sync",
        {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": query},
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode")
    args = p.parse_args()
    if args.mode == "schema":
        tap(
            "schema.csv",
            (
                "SELECT column_name,datatype,description FROM TAP_SCHEMA.columns "
                "WHERE table_name='varwisepure'"
            ),
        )
    elif args.mode == "paper":
        acquire(
            "paz2026.pdf", "https://irsa.ipac.caltech.edu/data/WISE/VarWISE/docs/Paz_et_al_2026.pdf"
        )
    elif args.mode == "screen":
        tap(
            "screen.csv",
            (
                "SELECT TOP 200 * FROM varwisepure WHERE w1_amp>1 AND dec>0 AND dec<70 "
                "AND w1mag<14 AND gmag<19 AND plx>3*e_plx AND blended_source<0.1 "
                "AND latent_artifact<0.1 AND (vartype='yso' OR vartype='unclear' "
                "OR vartype='cv' OR vartype='sn') ORDER BY w1_amp DESC"
            ),
        )
