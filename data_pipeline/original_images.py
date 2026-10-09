"""Bounded acquisition and strict verification of selected original MAST images.

Filenames reconstructed from saved catalogs are identifiers, not verification.
Only complete, checksum-pinned SCI/ERR/WHT products pass this readiness gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from data_pipeline.research_sources import fetch_product

MAX_PRODUCT_BYTES = 300 * 1024**2
MAX_TOTAL_BYTES = 1536 * 1024**2


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_image(path: str | Path, product: dict[str, Any]) -> dict[str, Any]:
    """Verify full array data and identifier metadata before scientific use."""
    path = Path(path)
    if product.get("product_kind") != "original_full_i2d":
        raise ValueError("readiness requires original_full_i2d, not PSFs/headers/cutouts")
    if not product.get("sha256") or file_sha256(path) != product["sha256"]:
        raise ValueError("original image checksum missing or mismatched")
    if path.stat().st_size != product["expected_bytes"]:
        raise ValueError("original image size mismatch")
    with fits.open(path, memmap=True) as hdul:
        if not all(name in hdul for name in ("SCI", "ERR", "WHT")):
            raise ValueError("original i2d requires SCI, ERR and WHT")
        sci, err, wht = (hdul[name].data for name in ("SCI", "ERR", "WHT"))
        if sci.ndim != 2 or err.shape != sci.shape or wht.shape != sci.shape:
            raise ValueError("invalid original science/error/weight array shapes")
        header, primary = hdul["SCI"].header, hdul[0].header
        if primary.get("FILENAME") != product["product_filename"]:
            raise ValueError("FILENAME disagrees with acquisition manifest")
        if primary.get("FILTER") != product["filter"]:
            raise ValueError("FILTER disagrees with acquisition manifest")
        if not WCS(header).has_celestial:
            raise ValueError("original science image has no celestial WCS")
        if header.get("BUNIT") != "MJy/sr":
            raise ValueError("this original-image gate expects MJy/sr")
        good = np.isfinite(sci) & np.isfinite(err) & (err > 0) & np.isfinite(wht) & (wht > 0)
        if not np.any(good):
            raise ValueError("original image has no usable calibrated pixels")
        return {
            "shape": list(sci.shape),
            "valid_pixels": int(good.sum()),
            "valid_fraction": float(good.mean()),
            "bunit": header.get("BUNIT"),
            "cal_ver": primary.get("CAL_VER"),
            "crds_context": primary.get("CRDS_CTX"),
            "detector": primary.get("DETECTOR"),
            "expstart_mjd": primary.get("EXPSTART"),
            "expmid_mjd": primary.get("EXPMID"),
            "exposure_time_s": primary.get("EFFEXPTM"),
            "readiness": "original_full_image_verified",
        }


def provision(manifest: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    """Acquire exactly the named products, reuse only checksum-verified inputs."""
    products = manifest["images"]
    total = sum(int(p["expected_bytes"]) for p in products)
    if total > MAX_TOTAL_BYTES:
        raise ValueError("selected original-image acquisition exceeds total byte ceiling")
    output = Path(output_dir)
    images = []
    for product in products:
        if int(product["expected_bytes"]) > MAX_PRODUCT_BYTES:
            raise ValueError("selected original-image product exceeds byte ceiling")
        name = product["product_filename"]
        if name != Path(name).name:
            raise ValueError("product filename must be a basename")
        destination = output / name
        if not destination.exists():
            fetch_product(product, destination, max_bytes=MAX_PRODUCT_BYTES, timeout=45)
        summary = verify_image(destination, product)
        images.append(
            {**product, "path": str(destination.resolve()), "kind": "science_image", **summary}
        )
    payload = {
        "schema_version": 1,
        "complete_original_archive": False,
        "selected_product_bytes": total,
        "images": images,
        "caveats": [
            "Selected original full products, not the complete historical 26-exposure archive.",
            "Current archive reprocessing is pinned; historical numerical results may differ.",
            "Positive ERR/WHT masks do not replace detector diagnostics or full DQ history.",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "images_manifest.json").write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def register_verified_images(payload: dict[str, Any]) -> int:
    """Opt-in catalog registration; callers can select a dedicated DATABASE_URL."""
    from core_api.db import SessionLocal, init_db
    from core_api.models.datasets import Dataset

    init_db()
    inserted = 0
    with SessionLocal() as session:
        for row in payload["images"]:
            name = (
                f"jwst_{row['target']}_{row['filter']}_"
                f"{row['product_filename'].removesuffix('.fits')}"
            )
            existing = session.query(Dataset).filter(Dataset.name == name).first()
            metadata = {
                "file_path": row["path"],
                "target": row["target"],
                "filter": row["filter"],
                "sha256": row["sha256"],
            }
            if existing is None:
                session.add(
                    Dataset(
                        name=name,
                        description="Verified original MAST i2d image",
                        meta_data=metadata,
                        tags=["jwst", "original_full_i2d"],
                    )
                )
                inserted += 1
            else:
                existing.meta_data = metadata
        session.commit()
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("data/original_round2"))
    parser.add_argument(
        "--register",
        action="store_true",
        help="Register verified originals in the configured database",
    )
    args = parser.parse_args()
    payload = provision(json.loads(args.manifest.read_text()), args.output_dir)
    if args.register:
        payload["registered_new_datasets"] = register_verified_images(payload)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
