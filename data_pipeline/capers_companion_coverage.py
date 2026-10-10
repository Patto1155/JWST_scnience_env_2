"""Verify complete source-association metadata and official X1D coverage."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from astropy.io import fits

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "data_sources/capers_companion"


def spectrum_counts(table):
    wave = table["WAVELENGTH"]
    uv = np.isfinite(wave) & (wave >= 2.15) & (wave <= 3.2)
    valid = np.isfinite(wave) & np.isfinite(table["FLUX"])
    valid &= np.isfinite(table["FLUX_ERROR"]) & (table["FLUX_ERROR"] > 0)
    valid &= (table["NPIXELS"] > 0) & ((table["DQ"] & 3) == 0)
    return {
        "rows": len(table),
        "usable_rows": int(valid.sum()),
        "uv_rows": int(uv.sum()),
        "usable_uv_rows": int((uv & valid).sum()),
        "nonpositive_npixels_rows": int((table["NPIXELS"] <= 0).sum()),
    }


def replay():
    receipt = json.loads((DIRECTORY / "receipt.json").read_text())
    total = 0
    for query in receipt["queries"]:
        raw = (ROOT / query["path"]).read_bytes()
        if len(raw) != query["bytes"] or hashlib.sha256(raw).hexdigest() != query["sha256"]:
            raise ValueError("Companion coverage input differs from receipt")
        total += len(raw)
    if total != receipt["response_bytes"] or total > 2097152:
        raise ValueError("Companion byte accounting differs")
    if len(receipt["queries"]) > 8 or receipt["actual_elapsed_last_endpoint_s"] > 300:
        raise ValueError("Companion endpoint/time budget exceeded")
    first = ROOT / "data_sources/public_metadata/mast_capers_products.response"
    first_pin = next(
        q
        for q in json.loads((first.parent / "receipt.json").read_text())["queries"]
        if q["id"] == "mast_capers_products"
    )
    if hashlib.sha256(first.read_bytes()).hexdigest() != first_pin["sha256"]:
        raise ValueError("Reused source-association page1 differs")
    pages = [first] + [DIRECTORY / f"products_page{page}.response" for page in range(2, 8)]
    rows = []
    for page, path in enumerate(pages, start=1):
        obj = json.loads(path.read_text())
        paging = obj["paging"]
        if (
            obj["status"] != "COMPLETE"
            or paging["page"] != page
            or paging["rowsTotal"] != 630
            or paging["rowsFiltered"] != 630
            or paging["pagesFiltered"] != 7
            or len(obj["data"]) != paging["rows"]
        ):
            raise ValueError("Source-association pagination differs")
        rows.extend(obj["data"])
    if len(rows) != 630 or {r["parent_obsid"] for r in rows} != {266381037}:
        raise ValueError("Source-association product identity differs")
    products = {}
    for row in rows:
        filename = row["productFilename"]
        if filename in products:
            old = products[filename]
            if any(old[k] != row[k] for k in ("dataURI", "size", "dataRights")):
                raise ValueError("Duplicate archive product identity differs")
        products[filename] = row
    x1d = receipt["selected_source_product"]
    if products[x1d["productFilename"]] != x1d or x1d["dataRights"] != "PUBLIC":
        raise ValueError("Selected exact source product differs")
    association = json.loads((DIRECTORY / "source_association.json").read_text())
    if association["asn_id"] != "o007" or association["program"] != "06368":
        raise ValueError("Association program/observation identity differs")
    source_product = association["products"][0]
    obs_id = source_product["name"].replace("{source_id}", "s000102896")
    if obs_id != x1d["obs_id"]:
        raise ValueError("Association/source-product identity differs")
    science = [m["expname"] for m in source_product["members"] if m["exptype"] == "science"]
    roots = {name.removesuffix("_nrs1_cal.fits").removesuffix("_nrs2_cal.fits") for name in science}
    compact = json.loads((ROOT / "research_output/mom_compact_followup_v1.json").read_text())
    expected = {name.split("_nrs2_")[0] for name in compact["contributors"]}
    if roots != expected or len(set(science)) != 36:
        raise ValueError("Association contains unexpected scientific contributors")
    with fits.open(DIRECTORY / "source_x1d.fits", memmap=False) as hdul:
        primary = hdul[0].header
        extension = hdul["EXTRACT1D"].header
        if (
            extension["SOURCEID"] != 102896
            or extension["SRCRA"] != 150.0933178
            or extension["SRCDEC"] != 2.2731591
        ):
            raise ValueError("Official source spectrum identity differs")
        if primary["ASNTABLE"] != receipt["association_product"]["productFilename"]:
            raise ValueError("Actual spectrum association provenance differs")
        units = {column.name: column.unit for column in hdul["EXTRACT1D"].columns}
        if units["WAVELENGTH"] != "um" or units["FLUX"] != "Jy" or units["FLUX_ERROR"] != "Jy":
            raise ValueError("Official spectrum units differ")
        table = hdul["EXTRACT1D"].data.copy()
        wave = table["WAVELENGTH"]
        if not np.isfinite(wave).all() or not (np.diff(wave) > 0).all():
            raise ValueError("Spectrum wavelength coordinate invalid")
        jump = int(np.argmax(np.diff(wave)))
        provenance = {
            key: primary[key]
            for key in (
                "CAL_VER",
                "CRDS_CTX",
                "CRDS_VER",
                "ASNTABLE",
                "ASNPOOL",
                "DETECTOR",
                "EXP_TYPE",
                "FILTER",
                "GRATING",
                "S_WAVCOR",
                "R_WAVCOR",
                "R_EXTR1D",
            )
        }
        source = {
            key: extension[key]
            for key in (
                "SOURCEID",
                "SRCRA",
                "SRCDEC",
                "SRCTYPE",
                "DETECTOR",
                "SLITID",
            )
        }
    return {
        "schema_version": 1,
        "plan_revision": "2e8478f",
        "response_bytes": total,
        "endpoint_count": len(receipt["queries"]),
        "restoration_bytes": 0,
        "elapsed_last_endpoint_s": receipt["actual_elapsed_last_endpoint_s"],
        "summed_active_query_runtime_s": receipt["summed_active_query_runtime_s"],
        "association_product_rows": len(rows),
        "unique_product_filenames": len(products),
        "association_science_members": science,
        "science_members_count": 36,
        "nrs1_science_members": sum("_nrs1_" in name for name in science),
        "nrs2_science_members": sum("_nrs2_" in name for name in science),
        "target_acquisition_member_count": len(source_product["members"]) - len(science),
        "source": source,
        "provenance": provenance,
        "units": units,
        "coverage": spectrum_counts(table),
        "wavelength_endpoint_range_um": [float(wave.min()), float(wave.max())],
        "largest_adjacent_gap_um": [float(wave[jump]), float(wave[jump + 1])],
        "public_source_S2D": products["jw06368-o007_s000102896_nirspec_clear-prism_s2d.fits"],
        "stopping_decision": "No UV samples in exact official combined-source X1D; no flux fit",
        "limits": [
            "Both detectors are associated; footprint coverage alone was not used",
            "Combined source X1D does not label every sample by contributor/detector",
            "No UV samples do not establish zero UV flux or an upper limit",
            "Associated S2D and lower-stage source geometry remain accessible and unqueried",
            "New observing time is not yet established as necessary",
            "Pipeline resampling, extraction and full covariance are not independently reproduced",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
