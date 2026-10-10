"""Restore four bounded primary nominal dispersion inputs from committed receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data_sources/pilot/observation_design"


def acquire(output: Path, cap_bytes: int = 100 * 1024 * 1024) -> list[dict]:
    receipt = json.loads((SOURCE / "receipt.json").read_text())
    items = [row for row in receipt["records"] if row["name"].endswith(".fits")]
    if sum(row["bytes"] for row in items) > cap_bytes:
        raise ValueError("selected products exceed declared acquisition cap")
    output.mkdir(parents=True, exist_ok=True)
    result = []
    for item in items:
        path = output / item["name"]
        if path.exists():
            data = path.read_bytes()
            if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise ValueError("existing input differs from pin; refusing overwrite")
        else:
            chunks = []
            total = 0
            with requests.get(item["url"], stream=True, timeout=60) as response:
                response.raise_for_status()
                for chunk in response.iter_content(65536):
                    total += len(chunk)
                    if total > item["bytes"] or total > cap_bytes:
                        raise ValueError("response exceeds pinned byte budget")
                    chunks.append(chunk)
            data = b"".join(chunks)
            if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise ValueError("download differs from primary input pin")
            path.write_bytes(data)
        result.append(
            {
                "filename": item["name"],
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=SOURCE)
    args = parser.parse_args()
    print(json.dumps(acquire(args.output), indent=2))


if __name__ == "__main__":
    main()
