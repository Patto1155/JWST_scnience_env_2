"""Independent accepted public-metadata identities, geometry and local CAL review."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assignment(text, name):
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise ValueError("Required public mapping assignment missing: " + name)


def audit(root, cal_directory):
    directory = root / "data_sources/public_metadata"
    receipt_path = directory / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    report_path = root / "research_output/mom_public_metadata_v1.json"
    report = json.loads(report_path.read_text())
    response_pins = []
    total = 0
    for row in receipt["queries"]:
        path = root / row["path"]
        raw = path.read_bytes()
        assert len(raw) == row["bytes"] and digest(path) == row["sha256"]
        total += len(raw)
        response_pins.append({"id": row["id"], "bytes": len(raw), "sha256": digest(path)})
    assert len(response_pins) == 12 and total == receipt["response_bytes"] == 470251
    durations = [row["elapsed_end_s"] - row["elapsed_start_s"] for row in receipt["queries"]]
    assert 0 < sum(durations) <= receipt["runtime_s"] <= receipt["query_seconds_cap"]
    assert abs(report["summed_active_query_runtime_s"] - sum(durations)) < 1e-9

    def text(name):
        return (directory / (name + ".response")).read_text()

    baseline = json.loads((root / "data_sources/followup/mom_native_inventory.json").read_text())
    cached = json.loads((directory / "cached_cal_headers.json").read_text())
    cached_rows = {row["filename"]: row for row in cached["headers"]}
    source_position = SkyCoord(150.0933255 * u.deg, 2.2731627 * u.deg)
    calibration = []
    roots = set()
    for row in baseline["products"]:
        path = cal_directory / row["filename"]
        assert path.stat().st_size == row["expected_bytes"]
        assert digest(path) == row["sha256"] == cached_rows[row["filename"]]["sha256"]
        with fits.open(path, memmap=False) as hdul:
            primary = hdul[0].header
            header = cached_rows[row["filename"]]
            assert all(primary.get(key) == value for key, value in header["calibration"].items())
            assert all(primary.get(key) == value for key, value in header["references"].items())
            targets = [
                h.header for h in hdul if h.name == "SCI" and h.header.get("SOURCEID") == 277193
            ]
            assert len(targets) == 1
            assert targets[0]["SRCRA"] == source_position.ra.deg
            assert targets[0]["SRCDEC"] == source_position.dec.deg
            assert targets[0]["SRCTYPE"] == "EXTENDED"
            assert primary["CRDS_CTX"] == "jwst_1535.pmap"
            assert primary["R_WAVCOR"].endswith("jwst_nirspec_wavecorr_0004.asdf")
            calibration.append(
                {
                    "filename": path.name,
                    "sha256": digest(path),
                    "context": primary["CRDS_CTX"],
                    "wavecorr": primary["R_WAVCOR"],
                }
            )
        roots.add(re.sub(r"_nrs[12]_cal\.fits$", "", row["filename"]))
    assert len(calibration) == len(roots) == 9
    extraction = list(csv.DictReader(io.StringIO(text("author_extractions"))))
    shutters = list(csv.DictReader(io.StringIO(text("author_slits"))))
    capers = next(row for row in extraction if row["srcid"] == "102896")
    selected = [
        row
        for row in shutters
        if row["program"] == "6368" and row["source_id"] == "102896" and row["is_source"] == "True"
    ]
    counts = Counter(re.sub(r"_nrs[12]$", "", row["root"]) for row in selected)
    assert len(counts) == len(selected) == 18 and set(counts.values()) == {1}
    assert not roots.intersection(counts)
    source_times = sum(float(row["exptime"]) for row in selected)
    assert abs(source_times - 17069.004) < 1e-9
    position = SkyCoord(float(capers["ra"]) * u.deg, float(capers["dec"]) * u.deg)
    separation = source_position.separation(position).arcsec
    released = next(row for row in report["released_extractions"] if row["source_id"] == "102896")
    assert abs(separation - released["offset_arcsec"]) < 1e-8
    assert released["source_shutter_exposure_roots"] == [root + "" for root in sorted(counts)]
    assert abs(released["source_shutter_time_sum_s"] - source_times) < 1e-9
    # Separately verify source-level archive records and executed/null-time distinction.
    position_response = json.loads(text("mast_position"))
    paging = position_response["paging"]
    assert paging["pagesFiltered"] == 1 and len(position_response["data"]) == 35
    timed = [row for row in position_response["data"] if row["t_min"] is not None]
    nulls = [row for row in position_response["data"] if row["t_min"] is None]
    assert len(timed) == 6 and len(nulls) == 29
    public = next(
        row for row in timed if row["obs_id"] == "jw06368-o007_s000102896_nirspec_clear-prism"
    )
    mom = next(
        row for row in timed if row["obs_id"] == "jw05224-o004_s000277193_nirspec_clear-prism"
    )
    assert public["dataRights"] == "PUBLIC" and public["t_min"] > mom["t_max"]
    uv_um = np.array([1483.32, 1486.50, 1548.19, 1640.41, 1750, 1908.73]) * 15.44 / 1e4
    assert uv_um.max() < float(capers["wmin"])
    for name in ("mast_mom_products", "mast_capers_products", "mast_program"):
        assert json.loads(text(name))["paging"]["pagesFiltered"] > 1
    pmap = assignment(text("crds_context"), "selector")
    assert pmap["NIRSPEC"] == "jwst_nirspec_0432.imap"
    imap = assignment(text("crds_nirspec_imap"), "selector")
    mapping_checks = {}
    for key in ("disperser", "pathloss", "photom", "wavecorr", "wavelengthrange"):
        mapped = imap[key.upper()]
        assert mapped in text("crds_home")
        mapping_checks[key] = mapped
    assert mapping_checks["wavecorr"] == "jwst_nirspec_wavecorr_0005.rmap"
    assert "pedigree: DUMMY" in text("crds_wavecorr_metadata")
    return {
        "schema_version": 1,
        "report_sha256": digest(report_path),
        "receipt_sha256": digest(receipt_path),
        "actual_response_pins": response_pins,
        "actual_CAL_headers_and_hashes": calibration,
        "independent_summed_active_query_seconds": sum(durations),
        "recorded_cumulative_query_phase_seconds": receipt["runtime_s"],
        "timing_scope": "Cumulative query phase; does not measure whole workflow wall time.",
        "CAPERS_unique_source_exposure_roots": sorted(counts),
        "CAPERS_source_time_s": source_times,
        "independent_SkyCoord_offset_arcsec": separation,
        "public_executed_CAPERS_source_record": public,
        "timed_records": len(timed),
        "null_time_records": len(nulls),
        "context_1535_mapping_names_present_in_capped_latest_page": mapping_checks,
        "nitrogen_carbon_UV_coverage_at_assumed_z14p44": False,
        "scope": "Metadata/actual cached headers only. Positional coincidence is not identity; "
        "catalog fit is not a new redshift; selector applicability and pixels await followup. "
        "No independent acquisition or new spectral measurement.",
    }


def compact_audit(root, cal_directory):
    directory = root / "data_sources/compact_followup"
    receipt_path = directory / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    report_path = root / "research_output/mom_compact_followup_v1.json"
    report = json.loads(report_path.read_text())
    pins = []
    total = 0
    for row in receipt["queries"]:
        if "path" not in row:
            assert row["method"] == "HEAD" and row["bytes"] == 0
            continue
        path = root / row["path"]
        assert path.stat().st_size == row["bytes"] and digest(path) == row["sha256"]
        total += row["bytes"]
        pins.append({"id": row["id"], "sha256": digest(path), "bytes": row["bytes"]})
    assert len(receipt["queries"]) == 7 and total == 718228
    assert total == receipt["response_bytes"] <= receipt["cap_bytes"]
    actual_active = sum(row["elapsed_end_s"] - row["elapsed_start_s"] for row in receipt["queries"])
    assert abs(actual_active - receipt["summed_active_query_runtime_s"]) < 1e-10
    assert receipt["actual_elapsed_last_endpoint_s"] < receipt["runtime_cap_s"]
    latest = assignment((directory / "latest1596.response").read_text(), "selector")
    imap = assignment((directory / "latest_nirspec.response").read_text(), "selector")
    assert latest["NIRSPEC"] == "jwst_nirspec_0444.imap"
    assert imap["WAVECORR"] == "jwst_nirspec_wavecorr_0005.rmap"
    mapping = ast.parse((directory / "wavecorr0005.response").read_text())
    selectors = [
        n.value
        for n in mapping.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "selector" for t in n.targets)
    ]
    assert len(selectors) == 1
    matched = selectors[0]
    assert isinstance(matched, ast.Call) and isinstance(matched.func, ast.Name)
    assert matched.func.id == "Match" and len(matched.args) == 1 and not matched.keywords
    modes = matched.args[0]
    assert isinstance(modes, ast.Dict)
    branches = {}
    for key, value in zip(modes.keys, modes.values, strict=True):
        assert isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
        assert value.func.id == "UseAfter" and len(value.args) == 1 and not value.keywords
        branches[ast.literal_eval(key)] = ast.literal_eval(value.args[0])
    assert branches["NRS_MSASPEC"] == {"2015-11-01 00:00:00": "jwst_nirspec_wavecorr_0004.asdf"}
    with fits.open(cal_directory / "jw05224004001_03101_00002_nrs2_cal.fits") as hdul:
        observed = hdul[0].header["DATE-OBS"] + " " + hdul[0].header["TIME-OBS"]
        assert observed >= "2015-11-01 00:00:00"
    chosen = branches["NRS_MSASPEC"][
        max(date for date in branches["NRS_MSASPEC"] if date <= observed)
    ]
    assert chosen == report["selected_reference"]
    reference = directory / "applicable_wavecorr.response"
    historical_pin = json.loads(
        (root / "data_sources/followup/mom_wavecorr_receipt.json").read_text()
    )
    assert digest(reference) == historical_pin["sha256"] == report["reference_sha256"]
    assert reference.stat().st_size == 16453
    yaml = reference.read_bytes().split(b"\n...\n", 1)[0].decode("ascii")
    assert "pedigree: DUMMY" in yaml and "filename: jwst_nirspec_wavecorr_0002.asdf" in yaml
    with fits.open(directory / "capers_spec.fits") as hdul:
        slits = hdul["SLITS"].data
        assert len(slits) == 18 and np.all(slits["source_id"] == 102896)
        assert np.all(slits["source_ra"] == 150.0933178)
        assert np.all(slits["source_dec"] == 2.2731591)
        assert set(slits["detector"]) == {"NRS2"}
        roots = [
            re.fullmatch(
                r"(jw06368007001_\d{5}_\d{5})_nrs2_clear_prism_raw"
                r"\.139\.6368_102896\.fits",
                str(name),
            ).group(1)
            for name in slits["filename"]
        ]
        assert len(set(roots)) == 18
        shutters = list(
            csv.DictReader((root / "data_sources/public_metadata/author_slits.response").open())
        )
        planned = {
            re.sub(r"_nrs[12]$", "", row["root"])
            for row in shutters
            if row["program"] == "6368"
            and row["source_id"] == "102896"
            and row["is_source"] == "True"
        }
        assert set(roots) == planned
        times = float(slits["exposure_time"].sum())
        assert abs(times - 17069.004) < 1e-9
        assert len({name.split("_")[1] for name in roots}) == 6
        spec = hdul["SPEC1D"].data
        good = (
            np.isfinite(spec["flux"])
            & np.isfinite(spec["err"])
            & (spec["err"] > 0)
            & (spec["npix"] > 0)
        )
        assert len(spec) == 473 and good.sum() == 195
        coverage = [float(spec["wave"][good].min()), float(spec["wave"][good].max())]
        assert coverage == report["usable_wavelength_range_um"]
        units = {column.name: column.unit for column in hdul["SPEC1D"].columns}
        assert units["wave"] == "um" and units["flux"] == units["err"] == "uJy"
        assert all(hdul["SCI"].header[key] == value for key, value in report["settings"].items())
    assert receipt["new_selected_payload_bytes"] == total - reference.stat().st_size == 701775
    assert (
        next(q for q in receipt["queries"] if q["id"] == "capers_pixtab_head")["headers"][
            "Content-Length"
        ]
        == "4475520"
    )
    assert not report["pixtab_acquired"]
    return {
        "schema_version": 1,
        "report_sha256": digest(report_path),
        "receipt_sha256": digest(receipt_path),
        "actual_input_pins": pins,
        "exact_exposure_mode": "NRS_MSASPEC",
        "actual_CAL_observation_ISO": observed,
        "selected_reference": chosen,
        "same_historical_reference_SHA256": digest(reference),
        "pedigree": "DUMMY",
        "actual_unique_NRS2_roots": sorted(roots),
        "actual_source_time_s": times,
        "actual_usable_bins": int(good.sum()),
        "actual_usable_wavelength_range_um": coverage,
        "units": units,
        "independent_summed_active_query_seconds": actual_active,
        "new_selected_body_transfer_bytes": 701775,
        "pinned_reference_restoration_bytes_separate": 16453,
        "scope": "Actual compact FITS, contributors and selected reference identities; "
        "no new line fit, raw reduction, empirical calibration or source identity.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--cal-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    reviewer = compact_audit if args.compact else audit
    args.output.write_text(json.dumps(reviewer(args.root, args.cal_directory), indent=2) + "\n")


if __name__ == "__main__":
    main()
