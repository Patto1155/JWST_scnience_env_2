"""Versioned public-source inventory and bounded, checksummed downloads.

Nothing connects to the network at import. ``validate`` is wholly offline;
``probe`` sends HEAD only; ``fetch`` requires a selected manifest product.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "data_sources" / "manifest.json"
DEFAULT_LIMIT = 5 * 1024 * 1024


def load_manifest(path: str | Path = DEFAULT_MANIFEST) -> dict:
    data = json.loads(Path(path).read_text())
    validate_manifest(data)
    return data


def validate_manifest(data: dict) -> None:
    if data.get("schema_version") != 1:
        raise ValueError("unsupported manifest schema_version")
    seen = set()
    for source in data["sources"]:
        for field in (
            "id",
            "title",
            "version",
            "canonical_url",
            "access",
            "science_use",
            "caveats",
        ):
            if not source.get(field):
                raise ValueError(f"missing source field {field}")
        if source["id"] in seen:
            raise ValueError("duplicate source id")
        seen.add(source["id"])
        if urlparse(source["canonical_url"]).scheme != "https":
            raise ValueError("canonical_url must be HTTPS")
        products = set()
        for product in source.get("products", []):
            if product["id"] in products:
                raise ValueError("duplicate product id")
            products.add(product["id"])
            if urlparse(product["url"]).scheme != "https":
                raise ValueError("product URL must be HTTPS")
            size = product.get("expected_bytes")
            if size is not None and (not isinstance(size, int) or size <= 0):
                raise ValueError("expected_bytes must be a positive integer or null")


def selected_product(manifest: dict, source_id: str, product_id: str) -> dict:
    source = next((s for s in manifest["sources"] if s["id"] == source_id), None)
    if source is None:
        raise ValueError(f"unknown source: {source_id}")
    product = next((p for p in source.get("products", []) if p["id"] == product_id), None)
    if product is None:
        raise ValueError(f"unknown product: {source_id}/{product_id}")
    return product


def probe_product(product: dict, timeout: float = 20) -> dict:
    with urlopen(Request(product["url"], method="HEAD"), timeout=timeout) as response:
        return {
            "requested_url": product["url"],
            "resolved_url": response.url,
            "status": response.status,
            "content_length": response.headers.get("Content-Length"),
            "content_type": response.headers.get("Content-Type"),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
        }


def fetch_product(
    product: dict, destination: str | Path, *, max_bytes: int = DEFAULT_LIMIT, timeout: float = 30
) -> dict:
    """Stream one product under a byte ceiling, then atomically write file + receipt.

    The checksum pins retrieved bytes; ETag is recorded but never treated as a SHA.
    Partial downloads are removed. Existing targets are never overwritten.
    """
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if (
        product.get("expected_bytes", 0) is not None
        and product.get("expected_bytes", 0) > max_bytes
    ):
        raise ValueError("manifest size exceeds byte ceiling")
    destination = Path(destination)
    receipt_path = destination.with_name(destination.name + ".provenance.json")
    if destination.exists() or receipt_path.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with urlopen(
            Request(product["url"], headers={"User-Agent": "jwst-science-sources/1"}),
            timeout=timeout,
        ) as response:
            length = response.headers.get("Content-Length")
            if length and int(length) > max_bytes:
                raise ValueError("server size exceeds byte ceiling")
            if response.status != 200:
                raise ValueError(f"unexpected HTTP status: {response.status}")
            digest, size = hashlib.sha256(), 0
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
                temporary = Path(stream.name)
                while chunk := response.read(min(65536, max_bytes - size + 1)):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("stream exceeds byte ceiling")
                    digest.update(chunk)
                    stream.write(chunk)
            if length and size != int(length):
                raise ValueError("download does not match server Content-Length")
            expected = product.get("expected_bytes")
            if expected is not None and size != expected:
                raise ValueError("download does not match manifest byte size")
            checksum = digest.hexdigest()
            if product.get("sha256") and checksum != product["sha256"]:
                raise ValueError("download checksum mismatch")
            receipt = {
                "requested_url": product["url"],
                "resolved_url": response.url,
                "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                "bytes": size,
                "sha256": checksum,
                "content_type": response.headers.get("Content-Type"),
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
                "product_id": product["id"],
                "max_bytes": max_bytes,
            }
        # Link publishes without replacing a file created concurrently.
        os.link(temporary, destination)
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        return receipt
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def extract_jades_references(input_fits: str | Path, output_csv: str | Path) -> dict:
    """Retain every Obs_info row and explicit quality; never deduplicate by NIRSpec_ID.

    Requires astropy only for this operation. Raw null sentinels are preserved;
    consumers must quality-filter rather than treating tentative redshifts as truth.
    """
    import csv
    from collections import Counter

    import numpy as np
    from astropy.io import fits

    input_fits, output_csv = Path(input_fits), Path(output_csv)
    receipt_file = output_csv.with_name(output_csv.name + ".provenance.json")
    if output_csv.exists() or receipt_file.exists():
        raise FileExistsError(output_csv)
    columns = [
        "Unique_ID",
        "PID",
        "TIER",
        "NIRSpec_ID",
        "NIRCam_DR5_ID",
        "NIRCam_DR3_ID",
        "ObsDate",
        "RA_TARG",
        "Dec_TARG",
        "Field",
        "z_phot",
        "z_Spec",
        "z_Spec_flag",
        "z_R1000",
        "z_R1000n",
        "z_PRISM",
        "MUV",
    ]
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with fits.open(input_fits) as hdus:
        table = hdus["Obs_info"].data
        missing = set(columns) - set(table.names)
        if missing:
            raise ValueError(f"missing DR4 reference columns: {sorted(missing)}")
        with output_csv.open("w", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(columns)
            for row in table:
                writer.writerow([row[c] for c in columns])
        flags = dict(Counter(str(x).strip() for x in table["z_Spec_flag"]))
        robust = np.isin(table["z_Spec_flag"], ["A", "B"])
        summary = {
            "rows": len(table),
            "quality_flags": flags,
            "robust_ab_z_ge_6": int(np.sum(robust & (table["z_Spec"] >= 6))),
            "robust_ab_z_lt_3": int(
                np.sum(robust & (table["z_Spec"] >= 0) & (table["z_Spec"] < 3))
            ),
        }
    raw_receipt = input_fits.with_name(input_fits.name + ".provenance.json")
    source_receipt = json.loads(raw_receipt.read_text()) if raw_receipt.exists() else {}
    raw_hash = hashlib.sha256()
    with input_fits.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            raw_hash.update(chunk)
    if source_receipt.get("sha256") and raw_hash.hexdigest() != source_receipt["sha256"]:
        output_csv.unlink()
        raise ValueError("raw catalogue checksum differs from receipt")
    content = output_csv.read_bytes()
    receipt = {
        "source_url": source_receipt.get("requested_url"),
        "source_sha256": raw_hash.hexdigest(),
        "source_bytes": input_fits.stat().st_size,
        "source_version": "JADES DR4 Combined_DR4_external_v1.2.1.fits",
        "source_receipt": source_receipt,
        "transform": "extract_jades_references: every Obs_info row; selected columns",
        "columns": columns,
        "summary": summary,
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "derived_utc": datetime.now(timezone.utc).isoformat(),
        "caveats": [
            "Rows are observations, not unique astrophysical objects.",
            "Only A/B are highly robust; C secure, D tentative, E no redshift.",
            "Preserve null sentinels; match tier+ID or coordinates.",
        ],
    }
    receipt_file.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "list", "probe", "fetch"))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source")
    parser.add_argument("--product")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    if args.action == "validate":
        result = {"valid": True, "sources": len(manifest["sources"])}
    elif args.action == "list":
        result = [
            {
                "id": s["id"],
                "version": s["version"],
                "products": [p["id"] for p in s.get("products", [])],
            }
            for s in manifest["sources"]
        ]
    else:
        if not args.source or not args.product:
            parser.error("probe/fetch require --source and --product")
        product = selected_product(manifest, args.source, args.product)
        if args.action == "probe":
            result = probe_product(product)
        else:
            if not args.output:
                parser.error("fetch requires --output")
            result = fetch_product(product, args.output, max_bytes=args.max_bytes)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
