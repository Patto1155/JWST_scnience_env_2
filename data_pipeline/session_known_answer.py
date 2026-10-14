"""Frozen single-line JADES known-answer check; never a raw detector reduction."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import astropy.units as u
import numpy as np
import requests
from astropy.io import fits

from data_pipeline.mom_compact_followup import mapping_assignment, select_wavecorr
from tools.jwst.jades_balmer_pilot import fit_line

TARGET = 10058975
REST_A = 5008.24
REDSHIFT = 9.433
PUBLISHED = 35.8
PUBLISHED_ERROR = 0.8


def audit_crds(output: Path) -> dict:
    """Acquire current applicability metadata, fail closed on DUMMY pedigree."""
    receipts = []

    def get(url: str) -> bytes:
        entry = {"url": url, "started_utc": datetime.now(timezone.utc).isoformat()}
        with requests.get(url, stream=True, timeout=60) as response:
            chunks = []
            count = 0
            for chunk in response.iter_content(65536):
                count += len(chunk)
                if count + sum(r["bytes"] for r in receipts) > 30_000_000:
                    raise ValueError("Metadata budget exceeded")
                chunks.append(chunk)
            raw = b"".join(chunks)
            entry.update(
                status=response.status_code,
                bytes=count,
                sha256=hashlib.sha256(raw).hexdigest(),
            )
            receipts.append(entry)
            response.raise_for_status()
        return raw

    base = "https://jwst-crds.stsci.edu/unchecked_get/"
    home = get("https://jwst-crds.stsci.edu/")
    match = re.search(rb"Latest References.*?jwst_(\d+)\.pmap", home, re.S)
    if match is None:
        raise ValueError("Cannot resolve current advertised CRDS context")
    context = f"jwst_{match.group(1).decode()}.pmap"
    pmap = get(base + "mappings/jwst/" + context).decode()
    imap = ast.literal_eval(mapping_assignment(pmap, "selector"))["NIRSPEC"]
    imap_text = get(base + "mappings/jwst/" + imap).decode()
    rmap = ast.literal_eval(mapping_assignment(imap_text, "selector"))["WAVECORR"]
    rmap_text = get(base + "mappings/jwst/" + rmap).decode()
    reference = select_wavecorr(rmap_text, "NRS_MSASPEC", "2025-04-14 03:54:25")
    raw = get(base + "references/jwst/" + reference)
    header = raw.split(b"\n...\n", 1)[0].decode("ascii")
    dummy = "pedigree: DUMMY" in header
    result = {
        "context": context,
        "imap": imap,
        "rmap": rmap,
        "mode": "NRS_MSASPEC",
        "observation_date": "2025-04-14",
        "selected_reference": reference,
        "reference_sha256": hashlib.sha256(raw).hexdigest(),
        "dummy": dummy,
        "empirical_upgrade_gained": False,
        "upgrade_status": "FAIL_DUMMY" if dummy else "REQUIRES_EMPIRICAL_PROVENANCE_REVIEW",
        "reference_header": header,
        "mappings": {context: pmap, imap: imap_text, rmap: rmap_text},
        "acquisition": receipts,
        "total_body_bytes": sum(r["bytes"] for r in receipts),
    }
    output.write_text(json.dumps(result, indent=2) + "\n")
    return result


def catalogue_reference(path: Path) -> dict:
    """Read exact predeclared south target; reject any mixed/held-out catalogue."""
    if "goods-s" not in path.name or "goods-n" in path.name:
        raise ValueError("GOODS-S-only catalogue required")
    with fits.open(path, memmap=False) as hdul:
        observations = hdul["Obs_info"].data
        if set(observations["Field"]) != {"GS"}:
            raise ValueError("GOODS-S-only catalogue required; sealed field present")
        selected = np.flatnonzero(
            (observations["NIRSpec_ID"] == TARGET)
            & (observations["TIER"] == "goods-s-deephst")
        )
        if len(selected) != 1:
            raise ValueError("Exact target/tier metadata selection is not unique")
        index = int(selected[0])
        obs = observations[index]
        flux_hdu = hdul["R1000_5pix"]
        row = flux_hdu.data[index]
        if row["Unique_ID"] != obs["Unique_ID"]:
            raise ValueError("Published flux row identity differs")
        configuration = str(row["O3_5007_filter"])
        if configuration != "g395m_f290lp":
            raise ValueError("Frozen configuration differs from published line configuration")
        unit = u.Unit(flux_hdu.columns["O3_5007_flux"].unit)
        flux_unit = 1e-19 * u.erg / u.s / u.cm**2
        factor = (1 * unit / flux_unit).to_value(u.dimensionless_unscaled)
        return {
            "target": TARGET,
            "tier": "goods-s-deephst",
            "unique_id": str(obs["Unique_ID"]),
            "row_index": index,
            "redshift": float(obs["z_Spec"]),
            "configuration": configuration,
            "flux_1e19": float(row["O3_5007_flux"] * factor),
            "error_1e19": float(row["O3_5007_flux_err"] * factor),
            "catalogue_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "catalogue_unit": str(unit),
            "RA": float(obs["RA_TARG"]),
            "DEC": float(obs["DEC_TARG"]),
        }


def compare(
    flux_1e19: float,
    error_1e19: float,
    *,
    valid: bool,
    published: float = PUBLISHED,
    published_error: float = PUBLISHED_ERROR,
) -> dict:
    """Published-error comparisons; shared-photon errors are not independent."""
    if not np.isfinite(flux_1e19 + error_1e19) or error_1e19 <= 0:
        raise ValueError("Finite flux and positive fit error required")
    if not np.isfinite(published + published_error) or published_error <= 0:
        raise ValueError("Finite published value and positive quoted error required")
    delta = (flux_1e19 - published) / published_error
    return {
        "published_flux_1e19": published,
        "published_error_1e19": published_error,
        "recovered_flux_1e19": flux_1e19,
        "recovered_diagonal_error_1e19": error_1e19,
        "delta_published_sigma": delta,
        "pass_1sigma": bool(valid and abs(delta) <= 1),
        "pass_2sigma": bool(valid and abs(delta) <= 2),
        "pass_combined_2sigma_amendment": bool(
            valid and abs(flux_1e19 - published) / np.hypot(published_error, error_1e19) < 2
        ),
        "descriptive_delta_combined_errors": float(
            (flux_1e19 - published) / np.hypot(published_error, error_1e19)
        ),
        "combined_error_caveat": "Shared photons; covariance unknown, not independent evidence",
    }


def normalized_table(data, columns) -> dict:
    """Convert physically declared SI/cgs columns, rejecting unspecified units."""
    units = {column.name.upper(): column.unit for column in columns}
    result = {}
    for key, expected in (
        ("WAVELENGTH", u.um),
        ("FLUX", u.erg / u.s / u.cm**2 / u.AA),
        ("FLUX_ERR", u.erg / u.s / u.cm**2 / u.AA),
    ):
        if units.get(key) is None:
            raise ValueError(f"Undeclared unit for {key}")
        result[key] = (np.asarray(data[key], dtype=float) * u.Unit(units[key])).to_value(expected)
    return result


def measure(table: dict, reference: dict | None = None) -> dict:
    redshift = REDSHIFT if reference is None else reference["redshift"]
    published = PUBLISHED if reference is None else reference["flux_1e19"]
    published_error = PUBLISHED_ERROR if reference is None else reference["error_1e19"]
    result, _ = fit_line(table, REST_A, redshift, window=0.015)
    output = {
        "target": TARGET,
        "redshift": redshift,
        "vacuum_rest_angstrom": REST_A,
        "frozen_window_um": 0.015,
        "scope": "Released 1D recovery; raw detector end-to-end NOT executed",
        "fit": result,
    }
    if result["covariance_valid"]:
        output["comparison"] = compare(
            result["flux_1e20"] / 10,
            result["diagonal_err_1e20"] / 10,
            valid=True,
            published=published,
            published_error=published_error,
        )
    else:
        output["comparison"] = {"pass_1sigma": False, "pass_2sigma": False}
    return output


def original_fits(path: Path, version: str = "v1.0") -> tuple[dict, dict]:
    """Read only explicitly selected GOODS-S original-release target."""
    if (
        "goods-s" not in path.name
        or str(TARGET) not in path.name
        or f"_{version}_" not in path.name
    ):
        raise ValueError("Frozen original GOODS-S target identity required")
    with fits.open(path, memmap=False) as hdul:
        extension = "EXTRACT5PIX1D" if "EXTRACT5PIX1D" in hdul else "EXTRACT1D"
        hdu = hdul[extension]
        header = hdul[0].header
        if (
            str(header.get("TARGET")) != str(TARGET)
            or header.get("FILTER") != "F290LP"
            or header.get("GRATING") != "G395M"
            or abs(header.get("RA", 0) - 53.11243) > 0.2 / 3600
            or abs(header.get("DEC", 0) + 27.77461) > 0.2 / 3600
        ):
            raise ValueError("Frozen target/configuration FITS header identity differs")
        # Original DR1 uses its documented main extraction, not a chosen variant.
        table = normalized_table(hdu.data, hdu.columns)
        identity = {
            "name": path.name,
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "extension": extension,
            "units": {c.name: c.unit for c in hdu.columns},
            "primary_header": dict(header),
        }
    return table, identity


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fits", type=Path)
    source.add_argument("--replay", type=Path)
    source.add_argument("--catalogue", type=Path)
    source.add_argument("--audit-crds", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--save-input", type=Path)
    parser.add_argument("--reference", type=Path)
    args = parser.parse_args()
    if args.audit_crds:
        audit_crds(args.output)
        return
    if args.catalogue:
        args.output.write_text(json.dumps(catalogue_reference(args.catalogue), indent=2) + "\n")
        return
    if args.fits:
        table, identity = original_fits(args.fits, "v2.0" if args.reference else "v1.0")
        if args.save_input:
            np.savez_compressed(args.save_input, **table)
    else:
        with np.load(args.replay, allow_pickle=False) as compact:
            table = {key: np.array(compact[key]) for key in ("WAVELENGTH", "FLUX", "FLUX_ERR")}
        identity = {
            "replay": str(args.replay),
            "bytes": args.replay.stat().st_size,
            "sha256": hashlib.sha256(args.replay.read_bytes()).hexdigest(),
            "scope": "Compact released-1D input replay; not fresh raw data or independent evidence",
        }
    reference = json.loads(args.reference.read_text()) if args.reference else None
    report = measure(table, reference)
    report["input"] = identity
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
