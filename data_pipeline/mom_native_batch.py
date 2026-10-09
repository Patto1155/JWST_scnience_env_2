"""Bounded nine-exposure native MoM-z14 acquisition from verified SLITS metadata.

Each archive product is HEAD-verified before any new full download. Expected
aggregate bytes must fit the declared budget; each stream has a 64 MiB cap.
Only compact receipts/identity/DQ summaries belong in git, not the raw images.
"""
from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from astropy.io import fits

from data_pipeline.followup_data import extract_native_slit, verify
from data_pipeline.research_sources import fetch_product, probe_product

PER_FILE_CAP = 64 * 1024 * 1024
TOTAL_CAP = 600 * 1024 * 1024
INVENTORY = Path(__file__).resolve().parents[1] / "data_sources/followup/mom_native_inventory.json"


def exposure_products(spectrum: Path) -> tuple[list[dict], dict]:
    receipt = verify(spectrum)
    with fits.open(spectrum) as hdul:
        table = hdul["SLITS"].data
        if len(table) != 9 or not np.all(table["source_id"] == 277193):
            raise ValueError("Expected the nine identity-verified MoM source277193 SLITS entries")
        if not np.allclose(table["source_ra"], 150.0933255, rtol=0, atol=1e-7):
            raise ValueError("SLITS source RA mismatch")
        if not np.allclose(table["source_dec"], 2.2731627, rtol=0, atol=1e-7):
            raise ValueError("SLITS source Dec mismatch")
        products = []
        for row in table:
            filename = str(row["filename"])
            match = re.fullmatch(r"(jw05224004001_\d{5}_\d{5}_nrs2)_clear_prism_raw\.21\.5224_277193\.fits", filename)
            if match is None:
                raise ValueError("Unexpected metadata exposure filename")
            official = match.group(1) + "_cal.fits"
            products.append({"id": official, "filename": official,
                             "url": "https://mast.stsci.edu/api/v0.1/Download/file?uri=mast:JWST/product/" + official,
                             "source_slits_filename": filename, "source_id": 277193,
                             "position_number": int(row["position_number"]),
                             "exposure_time_s": float(row["exposure_time"]),
                             "start_time": float(row["start_time"])})
    if len({p["filename"] for p in products}) != 9:
        raise ValueError("Exposure metadata contains duplicates")
    return products, receipt


def window_quality(path: Path) -> list[dict]:
    """Count native usability in full-slit UV windows, not extracted-line SNR."""
    verify(path)
    with fits.open(path, memmap=False) as hdul:
        sci = next(h for h in hdul if h.name == "SCI")
        version = sci.header["EXTVER"]
        dq = np.array(hdul["DQ", version].data, dtype=np.uint32)
        wave = np.array(hdul["WAVELENGTH", version].data, dtype=float)
        err = np.array(hdul["ERR", version].data, dtype=float)
        image = np.array(sci.data, dtype=float)
    valid = np.isfinite(wave) & (wave > 0) & np.isfinite(err) & (err > 0) & np.isfinite(image)
    valid &= (dq & 3) == 0
    lines = {"NIV_1486": 1486.5, "CIV_1549": 1549.5, "HeII_OIII_1654": 1654.,
             "NIII_1750": 1750., "CIII_1908": 1908.}
    result = []
    for label, rest in lines.items():
        center = rest * 1e-4 * (1 + 14.44)
        halfwidth = center * 3500 / 299792.458
        region = np.isfinite(wave) & (np.abs(wave - center) <= halfwidth)
        count = int(np.sum(region))
        result.append({"line_group": label, "center_um_at_z14p44": center,
                       "halfwidth_velocity_kms": 3500, "full_slit_window_pixels": count,
                       "dq_do_not_use": int(np.sum(region & ((dq & 1) != 0))),
                       "dq_saturated": int(np.sum(region & ((dq & 2) != 0))),
                       "usable_pixels": int(np.sum(region & valid)),
                       "usable_fraction": float(np.sum(region & valid) / count) if count else None,
                       "columns_with_any_usable_pixel": int(np.sum(np.any(region & valid, axis=0))),
                       "limitation": "Entire spatial slit; not trace-only coverage or extracted UV-line significance"})
    return result


def acquire_batch(spectrum: Path, output: Path, max_bytes: int = TOTAL_CAP) -> dict:
    if not 0 < max_bytes <= TOTAL_CAP:
        raise ValueError("Native batch ceiling must be within 600MiB")
    products, spectrum_receipt = exposure_products(spectrum)
    inventory = json.loads(INVENTORY.read_text())
    if inventory["source_spectrum_sha256"] != spectrum_receipt["sha256"]:
        raise ValueError("Spectrum bytes differ from pinned native inventory")
    expected = {p["filename"]: p for p in inventory["products"]}
    if set(expected) != {p["filename"] for p in products}:
        raise ValueError("Metadata exposure names differ from pinned native inventory")
    output.mkdir(parents=True, exist_ok=True)

    def prepare(product):
        path = output / product["filename"]
        pin = expected[product["filename"]]
        if pin["url"] != product["url"] or pin["source_slits_filename"] != product["source_slits_filename"]:
            raise ValueError("Exposure metadata differs from pinned original identity")
        if pin["expected_bytes"] > PER_FILE_CAP:
            raise ValueError("Pinned native original exceeds per-file ceiling")
        if path.exists():
            previous = verify(path)
            if previous["bytes"] != pin["expected_bytes"] or previous["sha256"] != pin["sha256"]:
                raise ValueError("Cached native original differs from pinned inventory")
            return {**product, "expected_bytes": previous["bytes"], "sha256": previous["sha256"],
                    "availability": "existing_receipt_verified"}
        probe = probe_product(product, timeout=30)
        if probe["status"] != 200 or probe["content_length"] is None:
            raise ValueError("Official native product availability/size not verified")
        size = int(probe["content_length"])
        if size <= 0 or size > PER_FILE_CAP:
            raise ValueError("Official native product exceeds per-file ceiling")
        if size != pin["expected_bytes"]:
            raise ValueError("Official native product size differs from pinned inventory")
        return {**product, "expected_bytes": size, "sha256": pin["sha256"], "head_receipt": probe,
                "availability": "public_archive_head_verified"}

    with ThreadPoolExecutor(max_workers=3) as executor:
        prepared = list(executor.map(prepare, products))
    expected_total = sum(p["expected_bytes"] for p in prepared)
    if expected_total > max_bytes:
        raise ValueError("Aggregate native exposure size exceeds batch ceiling")

    def retrieve(product):
        path = output / product["filename"]
        receipt = verify(path) if path.exists() else fetch_product(
            product, path, max_bytes=PER_FILE_CAP, timeout=60
        )
        slit = output / product["filename"].replace("_cal.fits", "_277193_native.fits")
        summary = extract_native_slit(path, slit)
        if abs(summary["source_ra_deg"] - 150.0933255) > 1e-7 or abs(summary["source_dec_deg"] - 2.2731627) > 1e-7:
            raise ValueError("Native product source coordinate identity mismatch")
        return {"metadata": product, "native_exposure_receipt": receipt,
                "derived_slit_filename": slit.name, "identity_quality": summary,
                "uv_window_quality": window_quality(slit)}

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(retrieve, prepared))
    return {"schema_version": 1, "source_spectrum_receipt": spectrum_receipt,
            "budget": {"per_file_max_bytes": PER_FILE_CAP, "batch_max_bytes": max_bytes,
                       "actual_original_bytes": sum(r["native_exposure_receipt"]["bytes"] for r in results),
                       "scope": "Nine native originals; first was already acquired under preceding100MiBpilot"},
            "exposures": results,
            "limits": ["Nine actual calibrated exposures, not nine independent abundance measurements",
                       "OfficialEXTENDED treatment differs from DJA point-source pathloss",
                       "Shared reference/background choices can correlate nods; do not assume independent draws",
                       "Full-slit DQ usability is not trace-only quality or a fitted line significance"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spectrum", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = acquire_batch(args.spectrum, args.output)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
