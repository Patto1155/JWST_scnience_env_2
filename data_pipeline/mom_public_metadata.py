"""Replay the bounded public MoM archive inventory from hashed metadata only."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "data_sources/public_metadata"


def angular_separation_arcsec(ra, dec, other_ra, other_dec):
    """Great-circle separation using the stable haversine expression."""
    a, b, c, d = map(math.radians, (ra, dec, other_ra, other_dec))
    h = math.sin((d - b) / 2) ** 2 + math.cos(b) * math.cos(d) * math.sin((c - a) / 2) ** 2
    return math.degrees(2 * math.asin(math.sqrt(min(1.0, max(0.0, h))))) * 3600


def verify_responses(directory=DIRECTORY):
    receipt = json.loads((directory / "receipt.json").read_text())
    total = 0
    for query in receipt["queries"]:
        if "path" not in query:
            continue
        raw = (directory / Path(query["path"]).name).read_bytes()
        if len(raw) != query["bytes"] or hashlib.sha256(raw).hexdigest() != query["sha256"]:
            raise ValueError("Metadata response differs from accepted receipt")
        total += len(raw)
    if total != receipt["response_bytes"] or total > receipt["cap_bytes"]:
        raise ValueError("Response budget arithmetic differs")
    if len(receipt["queries"]) > receipt["endpoint_cap"]:
        raise ValueError("Query endpoint budget exceeded")
    return receipt


def replay(directory=DIRECTORY):
    receipt = verify_responses(directory)

    def raw(name):
        return (directory / (name + ".response")).read_text()

    source = (150.0933255, 2.2731627)
    extraction = list(csv.DictReader(io.StringIO(raw("author_extractions"))))
    shutters = list(csv.DictReader(io.StringIO(raw("author_slits"))))
    position = json.loads(raw("mast_position"))
    headers = json.loads((directory / "cached_cal_headers.json").read_text())
    pin = json.loads((ROOT / "data_sources/followup/mom_native_inventory.json").read_text())
    rate = json.loads((ROOT / "data_sources/followup/mom_rate_noise_manifest.json").read_text())
    expected = {p["filename"].removesuffix("_cal.fits") for p in pin["products"]}
    if expected != {p["filename"].removesuffix("_rate.fits") for p in rate["products"]}:
        raise ValueError("Pinned CAL/RATE exposure identities differ")
    for header in headers["headers"]:
        if header["calibration"]["CRDS_CTX"] != "jwst_1535.pmap":
            raise ValueError("Cached calibration context differs")
        if header["targets"] != [
            {
                "source_id": 277193,
                "source_ra": source[0],
                "source_dec": source[1],
                "source_type": "EXTENDED",
            }
        ]:
            raise ValueError("Cached source identity differs")
    released = []
    for row in extraction:
        program = row["file"].split("_")[-2]
        selected = [
            r
            for r in shutters
            if r["program"] == program
            and r["source_id"] == row["srcid"]
            and r["is_source"] == "True"
        ]
        roots = sorted({r["root"].removesuffix("_nrs1") for r in selected})
        baseline_roots = {r.removesuffix("_nrs2") for r in expected}
        released.append(
            {
                "file": row["file"],
                "source_id": row["srcid"],
                "program": program,
                "coordinates_deg": [float(row["ra"]), float(row["dec"])],
                "offset_arcsec": angular_separation_arcsec(
                    *source, float(row["ra"]), float(row["dec"])
                ),
                "version": row["version"],
                "catalog_grade": row["grade"],
                "catalog_redshift_not_new_fit": float(row["z"]),
                "released_range_um": [float(row["wmin"]), float(row["wmax"])],
                "exposure_time_s": float(row["exptime"]),
                "source_shutter_exposure_roots": roots,
                "disjoint_from_baseline_exposure_roots": not bool(set(roots) & baseline_roots),
                "source_shutter_time_sum_s": sum(float(r["exptime"]) for r in selected),
                "first_shutter_mjd": min(float(r["expstart"]) for r in selected),
                "geometry_scope": "Planned shutter/source metadata; no empirical trace placement",
            }
        )
    names = ("disperser", "pathloss", "photom", "wavecorr", "wavelengthrange")
    imap = raw("crds_nirspec_imap")
    home = raw("crds_home")
    mappings = {}
    for name in names:
        pattern = rf"jwst_nirspec_{name}_\d+\.rmap"
        baseline = sorted(set(re.findall(pattern, imap)))
        latest = sorted(set(re.findall(pattern, home)))
        mappings[name] = {
            "context_1535_imap": baseline,
            "latest_page": latest,
            "listed_names_match": baseline == latest,
        }
    products = {}
    for name in ("mast_mom_products", "mast_capers_products", "mast_program"):
        obj = json.loads(raw(name))
        products[name] = {
            "status": obj["status"],
            "paging": obj["paging"],
            "complete_pagination": obj["paging"]["pagesFiltered"] == 1,
            "public_cal_rate_metadata": [
                r
                for r in obj["data"]
                if r.get("dataRights") == "PUBLIC"
                and r.get("productSubGroupDescription") in ("CAL", "RATE")
            ],
        }
    return {
        "schema_version": 1,
        "snapshot_date_utc": receipt["snapshot_date_utc"],
        "plan_revision": "630351b",
        "response_bytes": receipt["response_bytes"],
        "endpoint_count": len(receipt["queries"]),
        "summed_active_query_runtime_s": sum(
            q["elapsed_end_s"] - q["elapsed_start_s"] for q in receipt["queries"]
        ),
        "cumulative_query_phase_clock_s": receipt["runtime_s"],
        "cached_CAL_hash_verified_count": headers["CAL_actual_hash_verified_count"],
        "CAL_RATE_manifest_identity_count": len(expected),
        "released_extractions": released,
        "mast_position_paging": position["paging"],
        "executed_footprint_rows": [r for r in position["data"] if r["t_min"] is not None],
        "footprint_null_time_row_count": sum(r["t_min"] is None for r in position["data"]),
        "footprint_null_time_programs": sorted(
            {r["proposal_id"] for r in position["data"] if r["t_min"] is None}
        ),
        "public_product_samples_and_program_page": products,
        "relevant_reference_mapping_names": mappings,
        "current_CAL_reference": "jwst_nirspec_wavecorr_0004.asdf",
        "public_reference_metadata_dummy": "pedigree: DUMMY" in raw("crds_wavecorr_metadata"),
        "query_failures": [q for q in receipt["queries"] if q.get("status") != 200],
        "remaining_accessible_work": [
            "Query wavecorr0005.rmap selector actually linked by context1535 and latest1596",
            "Paginate product inventories and acquire only source-relevant CAPERS slit metadata",
            "Verify CAPERS wavelength coverage and detector assignment before UV likelihood use",
            "Check NIRCam grism source spectra; footprint coverage does not establish a detection",
        ],
        "limits": [
            "No full FITS downloaded or new spectral measurement made",
            "CAPERS positional coincidence does not establish astrophysical identity or redshift",
            "Null-time PUBLIC footprint records do not establish executed observations",
            "Matching rmap names do not prove unchanged selected references",
            "Current DUMMY wavecorr remains a sensitivity model, not empirical calibration",
            "Product/program samples are incompletely paginated; not an exhaustive archive census",
            "CRDS homepage response is capped; only observed entries support claims",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
