"""Acquire bounded, versioned deep GOODS survivor cutouts and model inputs.

The checked-in inventory pins every downloaded byte.  DAWN mosaics can contain
the selection images: these are deeper modeling inputs, not independent epochs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS

from data_pipeline.followup_data import verify
from data_pipeline.research_sources import fetch_product

MANIFEST = Path(__file__).resolve().parents[1] / "data_sources/survivor_deep/manifest.json"
MAX_TOTAL = 100 * 1024 * 1024


def verify_pinned(path: Path, product: dict) -> dict:
    receipt = verify(path)
    if receipt["sha256"] != product["sha256"] or receipt["bytes"] != product["expected_bytes"]:
        raise ValueError("Input differs from pinned deep-survivor inventory")
    return receipt


def acquire(directory: Path, manifest_path: Path = MANIFEST) -> dict:
    manifest = json.loads(manifest_path.read_text())
    remaining, rows = MAX_TOTAL, []
    for product in manifest["products"]:
        path = directory / product["filename"]
        limit = min(product["max_bytes"], remaining)
        if limit <= 0:
            raise ValueError("Deep-survivor aggregate byte ceiling exhausted")
        if not path.exists():
            fetch_product(product, path, max_bytes=limit, timeout=45)
        receipt = verify_pinned(path, product)
        if receipt["bytes"] > limit:
            raise ValueError("Cached product exceeds aggregate ceiling")
        remaining -= receipt["bytes"]
        if product["kind"] == "deep_science_inverse_variance_cutout":
            with fits.open(path) as hdul:
                if len(hdul) != 2 or hdul[0].header.get("EXTVER") != "SCI":
                    raise ValueError("Unexpected DAWN science/weight layout")
                if hdul[1].header.get("EXTVER") != "WHT":
                    raise ValueError("DAWN second extension is not inverse-variance WHT")
                if hdul[0].header.get("FILTER") != product["filter"] + "-CLEAR":
                    raise ValueError("Requested filter and actual cutout disagree")
                wcs = WCS(hdul[0].header).celestial
                center = wcs.pixel_to_world(
                    (hdul[0].data.shape[1] - 1) / 2, (hdul[0].data.shape[0] - 1) / 2
                )
                requested = SkyCoord(product["ra_deg"], product["dec_deg"], unit="deg")
                if requested.separation(center).arcsec > 0.1:
                    raise ValueError("Returned cutout center does not identify requested sky")
        rows.append({"filename": path.name, **receipt})
    return {
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "actual_bytes": MAX_TOTAL - remaining,
        "aggregate_ceiling_bytes": MAX_TOTAL,
        "products": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(acquire(args.output), indent=2))


if __name__ == "__main__":
    main()
