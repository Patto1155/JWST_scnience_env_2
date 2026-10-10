"""Hash-pinned CAPERS PIXTAB coverage gate; never fits or extracts flux."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from astropy.io import fits

from data_pipeline.mom_author_provenance import FIELDS
from data_pipeline.research_sources import fetch_product

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "data_sources/capers_coverage/receipt.json"


def counts(table, mask):
    data = table[mask]
    finite = np.ones(len(data), dtype=bool)
    for name in FIELDS:
        finite &= np.isfinite(data[name])
    usable = finite.copy()
    for name in ("var_total", "var_rnoise", "pathloss", "dwave_dx", "exptime"):
        usable &= data[name] > 0
    usable &= (data["profile"] != 0) & (data["yslit"] >= -3) & (data["yslit"] <= 3)
    ultraviolet = (data["wave"] >= 2.15) & (data["wave"] <= 3.2)
    return {
        "rows": len(data),
        "finite_all_fields_rows": int(finite.sum()),
        "usable_rows": int(usable.sum()),
        "uv_rows": int(ultraviolet.sum()),
        "usable_uv_rows": int((usable & ultraviolet).sum()),
        "negative_profile_rows": int((data["profile"] < 0).sum()),
        "zero_profile_rows": int((data["profile"] == 0).sum()),
        "positive_profile_rows": int((data["profile"] > 0).sum()),
        "positive_pathloss_rows": int((data["pathloss"] > 0).sum()),
        "wavelength_range_um": [float(data["wave"].min()), float(data["wave"].max())],
    }


def audit(path):
    start = perf_counter()
    receipt = json.loads(RECEIPT.read_text())
    raw = path.read_bytes()
    if len(raw) != receipt["bytes"] or hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
        raise ValueError("Pinned CAPERS PIXTAB differs")
    if hashlib.md5(raw).hexdigest() != receipt["single_part_etag_md5"]:
        raise ValueError("CAPERS whole-file ETag/MD5 differs")
    with fits.open(path, memmap=False) as hdul:
        if [h.name for h in hdul] != ["PRIMARY", "PIXTAB"]:
            raise ValueError("Unexpected CAPERS PIXTAB extension identity")
        table = hdul["PIXTAB"].data.copy()
        header = hdul["PIXTAB"].header.copy()
    if tuple(table.dtype.names) != FIELDS or len(table) != 46519:
        raise ValueError("Unexpected CAPERS PIXTAB schema")
    if not np.array_equal(np.unique(table["exposure_index"]), np.arange(18)):
        raise ValueError("Expected eighteen ordered PIXTAB exposure indices")
    spectrum = ROOT / "data_sources/compact_followup/capers_spec.fits"
    compact_receipt = json.loads((ROOT / "data_sources/compact_followup/receipt.json").read_text())
    spectrum_pin = next(q for q in compact_receipt["queries"] if q["id"] == "capers_spec")
    if hashlib.sha256(spectrum.read_bytes()).hexdigest() != spectrum_pin["sha256"]:
        raise ValueError("Associated compact CAPERS spectrum differs")
    with fits.open(spectrum, memmap=False) as hdul:
        slits = hdul["SLITS"].data.copy()
        settings = hdul["SCI"].header.copy()
    keys = ("VERSION", "PROFCEN", "PROFSIG", "YMIN1D", "YMAX1D", "WITHPATH")
    if any(header[key] != settings[key] for key in keys):
        raise ValueError("CAPERS compact spectrum/PIXTAB extraction settings differ")
    exposures, group_indices = [], {}
    for index, slit in enumerate(slits):
        filename = str(slit["filename"])
        if filename != settings[f"SFILE{index:03d}"]:
            raise ValueError("Associated compact ordered contributor identity differs")
        if not np.isclose(header[f"XPOS{index}"], slit["source_xpos"], atol=1e-7, rtol=0):
            raise ValueError("PIXTAB planned source position differs")
        selected = table["exposure_index"] == index
        if not np.all(table["exptime"][selected] == slit["exposure_time"]):
            raise ValueError("PIXTAB exposure duration differs")
        group = filename.split("_")[1][:2]
        group_indices.setdefault(group, []).append(index)
        exposures.append(
            {
                "exposure_index": index,
                "associated_spectrum_filename": filename,
                "group": group,
                "nod_position": int(slit["position_number"]),
                **counts(table, selected),
            }
        )
    groups = [
        {
            "group": group,
            "exposure_indices": indices,
            **counts(table, np.isin(table["exposure_index"], indices)),
        }
        for group, indices in sorted(group_indices.items())
    ]
    sky = [np.unique(table["sky"][table["exposure_index"] == i]) for i in range(18)]
    shared = [[int(len(np.intersect1d(a, b, assume_unique=True))) for b in sky] for a in sky]
    global_counts = counts(table, np.ones(len(table), dtype=bool))
    runtime = perf_counter() - start
    if runtime > 60:
        raise ValueError("Declared computation budget exceeded")
    return {
        "schema_version": 1,
        "plan_revision": "8286753",
        "input_pin": receipt,
        "settings": {key: header[key] for key in keys},
        "counts": global_counts,
        "nonfinite_rows_by_field": {
            name: int((~np.isfinite(table[name])).sum()) for name in FIELDS
        },
        "pathloss_range": [float(table["pathloss"].min()), float(table["pathloss"].max())],
        "exposures": exposures,
        "groups": groups,
        "group_count": len(groups),
        "exact_shared_sky_value_counts": shared,
        "analysis_runtime_s": runtime,
        "stopping_decision": "No UV rows: stop UV reduction/flux fitting on this intermediate",
        "limits": [
            "Missing UV coverage is not zero flux or a nitrogen upper limit",
            "PIXTAB has indices but no filenames or raw detector coordinates",
            "Index association uses pinned sibling SPEC ordering/settings/XPOS/exptime",
            "Repeated settings cannot independently prove unique group identity from PIXTAB alone",
            "Six distinct exposure groups are not independent author coadds",
            "Shared stored sky values are dependence witnesses, not full covariance",
            "NRS1 companion coverage remains unqueried; not claimed absent",
            "No empirical calibration, new flux fit, abundance or source identity established",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pixtab", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--acquire", action="store_true")
    args = parser.parse_args()
    if args.acquire and not args.pixtab.exists():
        receipt = json.loads(RECEIPT.read_text())
        fetch_product(
            {
                "id": "capers-pixtab",
                "url": receipt["url"],
                "expected_bytes": receipt["bytes"],
                "sha256": receipt["sha256"],
            },
            args.pixtab,
            max_bytes=receipt["cap_bytes"],
            timeout=60,
        )
    args.output.write_text(json.dumps(audit(args.pixtab), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
