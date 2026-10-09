"""Acquire the exact public M92 catalogue and two non-jittered F444W exposures.

The complete plan is 534,424,320 bytes, below 600 MiB. No F150W mosaic or
unfiltered bulk download is permitted. Product URI and size must still agree
with fresh MAST metadata, and SHA256 pins the bytes used for the experiment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from data_pipeline.research_sources import fetch_product

PINNED: dict[str, dict[str, Any]] = {
    "hlsp_jwststars_jwst_nircam_m92_f090w-f150w-f277w-f444w_v1_phot.fits": {
        "bytes": 299278080,
        "sha256": "184efd394861258f147668959d14098f32c3c917bece1119a4b4f15a415dfa83",
        "obsid": 433869969,
    },
    "jw01334001001_04101_00001_nrcalong_cal.fits": {
        "bytes": 117573120,
        "sha256": "7fa99ab0486c6d1ebdbde9a53e6e772b710368ff55937c0240b683fc1875781a",
        "obsid": 87622494,
    },
    "jw01334001001_04101_00004_nrcalong_cal.fits": {
        "bytes": 117573120,
        "sha256": "1e22ed5d1c73b984db4989d31eded5398f016f8908684a209caa8046516d9160",
        "obsid": 87622494,
    },
}


def acquire(output: Path) -> dict:
    total = sum(p["bytes"] for p in PINNED.values())
    assert total < 600 * 1024**2
    output.mkdir(parents=True, exist_ok=True)
    metadata = []
    for obsid in sorted({p["obsid"] for p in PINNED.values()}):
        payload = {
            "service": "Mast.Caom.Products",
            "params": {"obsid": obsid},
            "format": "json",
            "pagesize": 1000,
            "page": 1,
        }
        request = Request(
            "https://mast.stsci.edu/api/v0/invoke",
            data=urlencode({"request": json.dumps(payload)}).encode(),
        )
        with urlopen(request, timeout=30) as response:
            raw = response.read(5 * 1024**2 + 1)
            if len(raw) > 5 * 1024**2:
                raise ValueError("Metadata response exceeded bounded read")
        parsed = json.loads(raw)
        if parsed.get("status") != "COMPLETE":
            raise ValueError("Incomplete MAST metadata query")
        (output / f"mast-products-{obsid}.json").write_bytes(raw)
        metadata.extend(parsed["data"])
    receipts = []
    for filename, pin in PINNED.items():
        matching = [r for r in metadata if r["productFilename"] == filename]
        if len(matching) != 1 or matching[0]["size"] != pin["bytes"]:
            raise ValueError(f"MAST metadata changed for {filename}")
        product = {
            "id": filename,
            "url": "https://mast.stsci.edu/api/v0.1/Download/file?uri=" + matching[0]["dataURI"],
            "expected_bytes": pin["bytes"],
            "sha256": pin["sha256"],
        }
        destination = output / filename
        if destination.exists():
            if destination.stat().st_size != pin["bytes"]:
                raise ValueError(f"Existing size mismatch: {filename}")
            digest = hashlib.sha256()
            with destination.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
            if digest.hexdigest() != pin["sha256"]:
                raise ValueError(f"Existing hash mismatch: {filename}")
            receipts.append(
                json.loads(destination.with_name(filename + ".provenance.json").read_text())
            )
        else:
            receipts.append(fetch_product(product, destination, max_bytes=pin["bytes"], timeout=45))
    result = {
        "schema_version": 1,
        "total_product_bytes": total,
        "products": receipts,
        "excluded": [
            "M92 exposure 3 has documented excess astrometric jitter",
            "F150W HLSP reference mosaic exceeds the bounded acquisition cap",
        ],
        "source_documentation": "https://archive.stsci.edu/hlsp/jwststars",
        "source_readme": "https://archive.stsci.edu/hlsps/jwststars/hlsp_jwststars_readme.txt",
        "doi": "10.17909/cn6n-xg90",
        "license": "CC BY 4.0",
    }
    (output / "real_validation_acquisition.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(acquire(args.output), indent=2))


if __name__ == "__main__":
    main()
