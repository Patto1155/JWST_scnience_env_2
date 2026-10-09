"""Bounded public acquisition and numerical UNITE point-resolution derivative.

The downloaded author code is parsed as data with AST, never imported/executed.
No network happens during import. Public cutouts keep their reduction provenance.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from astropy.io import fits

from data_pipeline.research_sources import fetch_product, load_manifest

MANIFEST = Path(__file__).resolve().parents[1] / "data_sources/followup/manifest.json"


def verify(path: Path) -> dict:
    receipt = json.loads(path.with_name(path.name + ".provenance.json").read_text())
    if path.stat().st_size != receipt["bytes"]:
        raise ValueError("Input size differs from receipt")
    if hashlib.sha256(path.read_bytes()).hexdigest() != receipt["sha256"]:
        raise ValueError("Input SHA256 differs from receipt")
    return receipt


def acquire(output: Path, max_total_bytes: int = 100 * 1024 * 1024) -> list[dict]:
    """Fetch the seven preselected products, one bounded native exposure included."""
    receipts = []
    remaining = max_total_bytes
    for source in load_manifest(MANIFEST)["sources"]:
        for product in source["products"]:
            filename = product["filename"]
            path = output / filename
            limit = min(product.get("max_bytes", 8 * 1024 * 1024), remaining)
            if limit <= 0:
                raise ValueError("Total acquisition budget exhausted")
            receipt = verify(path) if path.exists() else fetch_product(
                product, path, max_bytes=limit, timeout=45
            )
            if receipt["bytes"] > limit:
                raise ValueError("Cached input exceeds selected per-product ceiling")
            if product.get("expected_bytes") is not None and receipt["bytes"] != product["expected_bytes"]:
                raise ValueError("Cached input size differs from pinned manifest")
            if product.get("sha256") and receipt["sha256"] != product["sha256"]:
                raise ValueError("Cached input SHA256 differs from pinned manifest")
            remaining -= receipt["bytes"]
            if remaining < 0:
                raise ValueError("Existing inputs exceed total acquisition budget")
            receipts.append({"filename": filename, **receipt})
    return receipts


def point_coefficients(source: str) -> tuple[float, ...]:
    """Read the author's documented descending-power coefficients, fail closed."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "_DEGRAAFF25_R_COEFFS":
                values = ast.literal_eval(node.value)["prism"]
                coefficients = tuple(float(x) for x in values)
                if len(coefficients) != 7 or not np.all(np.isfinite(coefficients)):
                    raise ValueError("Unexpected PRISM polynomial calibration")
                return coefficients
    raise ValueError("Pinned source lacks expected point-source calibration")


def derive_point_resolution(input_dir: Path, output_dir: Path) -> dict:
    source = input_dir / "unite_source.py"
    dispersion = input_dir / "unite_dispersion.fits"
    source_receipt, grid_receipt = verify(source), verify(dispersion)
    coefficients = point_coefficients(source.read_text())
    with fits.open(dispersion) as hdul:
        wavelength = np.array(hdul[1].data["WAVELENGTH"], dtype=float)
        uniform = np.array(hdul[1].data["R"], dtype=float)
        dlds = np.array(hdul[1].data["DLDS"], dtype=float)
    resolving_power = np.polyval(coefficients, wavelength)
    if np.any(~np.isfinite(resolving_power)) or np.any(resolving_power <= 0):
        raise ValueError("Nonpositive derived resolving power")
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "unite_point_prism_resolution.csv"
    with csv_path.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["wavelength_um", "point_R", "uniform_R", "dlds_um_per_pixel"])
        writer.writerows(zip(wavelength, resolving_power, uniform, dlds))
    fits_path = output_dir / "unite_point_prism_resolution.fits"
    primary = fits.PrimaryHDU()
    primary.header["ORIGIN"] = "Derived from pinned UNITE author calibration; not observed LSF"
    primary.header["RSOURCE"] = "POINT"
    primary.header["BUNIT"] = "dimensionless"
    table = fits.BinTableHDU.from_columns([
        fits.Column(name="WAVELENGTH", format="D", unit="MICRONS", array=wavelength),
        fits.Column(name="DLDS", format="D", unit="MICRONS/PIXEL", array=dlds),
        fits.Column(name="R", format="D", unit="RESOLUTION", array=resolving_power),
    ])
    fits.HDUList([primary, table]).writeto(fits_path, overwrite=True)
    receipt = {
        "kind": "derived_generic_point_source_resolution_not_source_specific_lsf",
        "transform": "np.polyval(descending coefficients, official wavelength_um grid)",
        "coefficients_descending": coefficients,
        "source_receipt": source_receipt,
        "grid_receipt": grid_receipt,
        "software_license": "UNITE GPLv3+; source code not redistributed here",
        "citation": "UNITE; de Graaff et al. DOI 10.1051/0004-6361/202347755",
        "limitation": "Current pinned UNITE calibration, not exact paper runtime or MoM shutter-specific LSF",
    }
    for path in (csv_path, fits_path):
        info = {
            **receipt, "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        path.with_name(path.name + ".provenance.json").write_text(json.dumps(info, indent=2) + "\n")
    return {**receipt, "derived_fits": fits_path.name, "derived_csv": csv_path.name}


def extract_native_slit(input_fits: Path, output_fits: Path, source_id: int = 277193) -> dict:
    """Keep an identity-verified native calibrated slit and its actual DQ planes.

    This is a compact derivative of one official exposure, not a new extraction
    of the nine-exposure DJA stack. Preserve upstream SRCTYPE and calibration.
    """
    input_receipt = verify(input_fits)
    with fits.open(input_fits, memmap=False) as hdul:
        matches = [h for h in hdul if h.name == "SCI" and h.header.get("SOURCEID") == source_id]
        if len(matches) != 1:
            raise ValueError("Native exposure does not identify exactly one target slit")
        science = matches[0]
        version = science.header["EXTVER"]
        selected = [hdul[0].copy()] + [h.copy() for h in hdul[1:] if h.header.get("EXTVER") == version]
        required = {"SCI", "ERR", "DQ", "WAVELENGTH"}
        if not required.issubset({h.name for h in selected}):
            raise ValueError("Native slit lacks required SCI/ERR/DQ/WAVELENGTH")
        dq = np.asarray(hdul["DQ", version].data, dtype=np.uint32)
        wave = np.asarray(hdul["WAVELENGTH", version].data, dtype=float)
        sci = np.asarray(science.data, dtype=float)
        err = np.asarray(hdul["ERR", version].data, dtype=float)
        valid = np.isfinite(wave) & (wave > 0) & np.isfinite(sci) & np.isfinite(err) & (err > 0)
        valid &= (dq & 3) == 0
        summary = {
            "source_id": source_id, "source_ra_deg": science.header["SRCRA"],
            "source_dec_deg": science.header["SRCDEC"], "slit_id": science.header["SLITID"],
            "shape": list(sci.shape), "calibration_version": hdul[0].header.get("CAL_VER"),
            "crds_context": hdul[0].header.get("CRDS_CTX"),
            "source_type_upstream": science.header.get("SRCTYPE"),
            "exposure_time_s": hdul[0].header.get("EFFEXPTM"), "science_bunit": science.header.get("BUNIT"),
            "pixels": int(sci.size), "dq_nonzero": int(np.sum(dq != 0)),
            "dq_do_not_use": int(np.sum((dq & 1) != 0)), "dq_saturated": int(np.sum((dq & 2) != 0)),
            "finite_positive_error_wavelength_and_dq_usable": int(np.sum(valid)),
            "retained_extensions": [h.name for h in selected[1:]],
            "input_receipt": input_receipt,
            "interpretation": "One native-grid official calibrated exposure; upstream EXTENDED source treatment differs from DJA point-source pathloss",
        }
    output_fits.parent.mkdir(parents=True, exist_ok=True)
    fits.HDUList(selected).writeto(output_fits, overwrite=True)
    receipt = {**summary, "kind": "derived_native_calibrated_target_slit_not_independent_full_reduction",
               "bytes": output_fits.stat().st_size,
               "sha256": hashlib.sha256(output_fits.read_bytes()).hexdigest()}
    output_fits.with_name(output_fits.name + ".provenance.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("acquire")
    fetch.add_argument("--output", type=Path, required=True)
    derive = sub.add_parser("derive-resolution")
    derive.add_argument("--input", type=Path, required=True)
    derive.add_argument("--output", type=Path, required=True)
    slit = sub.add_parser("extract-native-slit")
    slit.add_argument("--input", type=Path, required=True)
    slit.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "acquire":
        result = acquire(args.output)
    elif args.command == "derive-resolution":
        result = derive_point_resolution(args.input, args.output)
    else:
        result = extract_native_slit(args.input, args.output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
