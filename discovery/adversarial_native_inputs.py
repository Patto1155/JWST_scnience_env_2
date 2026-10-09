"""Read-only independent checksum and full-slit quality audit of native originals.

This intentionally imports neither acquisition nor its quality-count code. It
does not extract a spectrum or validate source-trace completeness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from astropy.io import fits

UV_REST_ANGSTROM = {
    "NIV_1486": 1486.5,
    "CIV_1549": 1549.5,
    "HeII_OIII_1654": 1654.0,
    "NIII_1750": 1750.0,
    "CIII_1908": 1908.0,
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            value.update(block)
    return value.hexdigest()


def audit(inventory_path: Path, report_path: Path, native_dir: Path) -> dict:
    inventory = json.loads(inventory_path.read_text())
    report = json.loads(report_path.read_text())
    pins = {row["filename"]: row for row in inventory["products"]}
    exposures = report["exposures"]
    names = [row["metadata"]["filename"] for row in exposures]
    if len(pins) != 9 or len(names) != 9 or len(set(names)) != 9 or set(names) != set(pins):
        raise ValueError("Audit requires the complete nine-original inventory")
    if report["source_spectrum_receipt"]["sha256"] != inventory["source_spectrum_sha256"]:
        raise ValueError("Source-spectrum provenance differs")
    records = []
    for record in exposures:
        pin = pins[record["metadata"]["filename"]]
        parent = native_dir / pin["filename"]
        slit_name = record["derived_slit_filename"]
        if Path(slit_name).name != slit_name:
            raise ValueError("Derived slit filename must be a basename")
        slit = native_dir / slit_name
        if parent.stat().st_size != pin["expected_bytes"] or digest(parent) != pin["sha256"]:
            raise ValueError("Original does not match externally pinned bytes")
        slit_digest = digest(slit)
        if slit_digest != record["identity_quality"]["sha256"]:
            raise ValueError("Derived slit does not match selected batch")
        with fits.open(slit, memmap=False) as hdul:
            science, error, dq, wave = [
                hdul[name].data for name in ("SCI", "ERR", "DQ", "WAVELENGTH")
            ]
            if hdul["SCI"].header["SRCNAME"] != "5224_277193":
                raise ValueError("Unexpected source identifier")
            if not (science.shape == error.shape == dq.shape == wave.shape):
                raise ValueError("Native arrays have different shapes")
            valid = np.isfinite(science) & np.isfinite(error) & (error > 0)
            valid &= np.isfinite(wave) & (wave > 0) & ((dq & 3) == 0)
            windows = record["uv_window_quality"]
            if len(windows) != 5 or {w["line_group"] for w in windows} != set(UV_REST_ANGSTROM):
                raise ValueError("Expected five UV-group windows")
            counts = []
            for expected in windows:
                center = UV_REST_ANGSTROM[expected["line_group"]] * 1e-4 * 15.44
                if not np.isclose(center, expected["center_um_at_z14p44"], rtol=0, atol=1e-12):
                    raise ValueError("Reported line center differs from fixed z=14.44")
                if expected["halfwidth_velocity_kms"] != 3500:
                    raise ValueError("Reported window differs from fixed 3500-km/s support")
                halfwidth = center * 3500 / 299792.458
                selected = np.isfinite(wave) & (abs(wave - center) <= halfwidth)
                total, usable = int(selected.sum()), int((valid & selected).sum())
                if total <= 0:
                    raise ValueError("A claimed UV support window is empty")
                if (
                    total != expected["full_slit_window_pixels"]
                    or usable != expected["usable_pixels"]
                ):
                    raise ValueError("Independent array counts differ from report")
                counts.append({"pixels": total, "usable": usable})
        records.append(
            {
                "filename": parent.name,
                "original_sha256": pin["sha256"],
                "original_bytes": parent.stat().st_size,
                "derivative_sha256": slit_digest,
                "full_slit_uv_windows": counts,
            }
        )
    total_bytes = sum(row["original_bytes"] for row in records)
    if total_bytes != report["budget"]["actual_original_bytes"]:
        raise ValueError("Reported aggregate byte count differs from actual originals")
    return {
        "review_date": "2026-10-09",
        "method": "Direct FITS/array counts and SHA256 independent of "
        "acquisition/window_quality implementation",
        "scope": "Native full-slit UV quality only; not trace quality, "
        "line detection, or independent abundance samples",
        "count": len(records),
        "original_bytes": total_bytes,
        "inventory_sha256": digest(inventory_path),
        "batch_report_sha256": digest(report_path),
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory", type=Path, default=Path("data_sources/followup/mom_native_inventory.json")
    )
    parser.add_argument(
        "--report", type=Path, default=Path("research_output/mom_native_batch.json")
    )
    parser.add_argument("--native-dir", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("research_output/adversarial_followup_checks.json")
    )
    args = parser.parse_args()
    result = audit(args.inventory, args.report, args.native_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "records"}, indent=2))


if __name__ == "__main__":
    main()
