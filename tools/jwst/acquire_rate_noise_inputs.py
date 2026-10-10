"""Acquire only pinned RATE/noise-audit inputs with bounded verified ranges."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
from pathlib import Path

import requests

from tools.jwst.native_rate_noise import MANIFEST
from tools.jwst.native_reduction import sha256


def acquire(output_dir: Path) -> dict:
    manifest = json.loads(MANIFEST.read_text())
    if (
        manifest["scientific_bytes"] + manifest["source_bytes"]
        > manifest["selected_download_cap_bytes"]
    ):
        raise ValueError("declared allocation exceeded")
    output_dir.mkdir(parents=True, exist_ok=True)
    targets = []
    for pin in manifest["products"] + manifest["sources"]:
        path = output_dir / pin["filename"]
        if path.exists():
            if path.stat().st_size != pin["bytes"] or sha256(path) != pin["sha256"]:
                raise ValueError("existing file differs from pinned identity")
            continue
        targets.append(pin)
    jobs = []
    for pin in targets:
        temporary = output_dir / (pin["filename"] + ".partial")
        if temporary.exists():
            raise ValueError("unfinished download exists; preserve or remove it explicitly")
        with temporary.open("wb") as stream:
            stream.truncate(pin["bytes"])
        step = 4 * 1024**2
        if pin in manifest["sources"]:
            jobs.append((pin, None, None))
        else:
            jobs.extend(
                (pin, start, min(start + step, pin["bytes"]) - 1)
                for start in range(0, pin["bytes"], step)
            )

    def transfer(job: tuple) -> int:
        pin, start, stop = job
        headers = {} if start is None else {"Range": f"bytes={start}-{stop}"}
        response = requests.get(pin["url"], headers=headers, timeout=120)
        if start is None:
            response.raise_for_status()
            expected = pin["bytes"]
            offset = 0
        else:
            if (
                response.status_code != 206
                or response.headers.get("Content-Range") != f"bytes {start}-{stop}/{pin['bytes']}"
            ):
                raise ValueError("server range/identity contract mismatch")
            expected = stop - start + 1
            offset = start
        if len(response.content) != expected:
            raise ValueError("received length differs from manifest/range")
        with (output_dir / (pin["filename"] + ".partial")).open("r+b") as stream:
            stream.seek(offset)
            stream.write(response.content)
        return expected

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        received = sum(pool.map(transfer, jobs))
    for pin in targets:
        temporary = output_dir / (pin["filename"] + ".partial")
        if temporary.stat().st_size != pin["bytes"] or sha256(temporary) != pin["sha256"]:
            raise ValueError("assembled whole-file pin mismatch")
        temporary.replace(output_dir / pin["filename"])
    return {"downloaded_bytes": received, "pinned_products": 9, "pinned_sources": 3, "workers": 8}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(acquire(args.output_dir)))


if __name__ == "__main__":
    main()
