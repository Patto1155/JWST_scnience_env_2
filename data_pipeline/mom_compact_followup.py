"""Verify exact MoM wavecorr selection and compact independent CAPERS coverage."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.time import Time

from data_pipeline.mom_public_metadata import angular_separation_arcsec

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "data_sources/compact_followup"


def mapping_assignment(text, name):
    """Read a mapping assignment through AST; never execute fetched CRDS code."""
    assignments = [
        node.value
        for node in ast.parse(text).body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
    ]
    if len(assignments) != 1:
        raise ValueError("Mapping assignment is ambiguous")
    return assignments[0]


def select_wavecorr(text, exposure_type, observation_iso):
    selector = mapping_assignment(text, "selector")
    if not isinstance(selector, ast.Call) or not isinstance(selector.func, ast.Name):
        raise ValueError("Expected CRDS Match selector")
    if selector.func.id != "Match" or len(selector.args) != 1:
        raise ValueError("Unexpected matching selector")
    modes = selector.args[0]
    if not isinstance(modes, ast.Dict):
        raise ValueError("Expected exposure-mode dictionary")
    matches = [
        value
        for key, value in zip(modes.keys, modes.values, strict=True)
        if exposure_type in ast.literal_eval(key).split("|")
    ]
    if len(matches) != 1:
        raise ValueError("Exposure-mode selection is ambiguous")
    dated = matches[0]
    if not isinstance(dated, ast.Call) or not isinstance(dated.func, ast.Name):
        raise ValueError("Expected UseAfter selection")
    if dated.func.id != "UseAfter" or len(dated.args) != 1:
        raise ValueError("Unexpected dated selector")
    references = ast.literal_eval(dated.args[0])
    eligible = {
        date: reference for date, reference in references.items() if date <= observation_iso
    }
    if not eligible:
        raise ValueError("No applicable reference before observation")
    return eligible[max(eligible)]


def replay():
    receipt = json.loads((DIRECTORY / "receipt.json").read_text())
    total = 0
    for query in receipt["queries"]:
        if "path" in query:
            raw = (ROOT / query["path"]).read_bytes()
            if len(raw) != query["bytes"] or hashlib.sha256(raw).hexdigest() != query["sha256"]:
                raise ValueError("Compact pilot input differs from receipt")
            total += len(raw)
    if total != receipt["response_bytes"] or total > 4 * 1024**2:
        raise ValueError("Compact acquisition budget differs")
    if len(receipt["queries"]) > 8 or receipt["actual_elapsed_last_endpoint_s"] > 300:
        raise ValueError("Compact acquisition query/time budget exceeded")
    first = ROOT / "data_sources/public_metadata"
    pmap1535 = ast.literal_eval(
        mapping_assignment((first / "crds_context.response").read_text(), "selector")
    )
    pmap1596 = ast.literal_eval(
        mapping_assignment((DIRECTORY / "latest1596.response").read_text(), "selector")
    )
    imap1535 = ast.literal_eval(
        mapping_assignment((first / "crds_nirspec_imap.response").read_text(), "selector")
    )
    imap1596 = ast.literal_eval(
        mapping_assignment((DIRECTORY / "latest_nirspec.response").read_text(), "selector")
    )
    assert pmap1535["NIRSPEC"] == "jwst_nirspec_0432.imap"
    assert pmap1596["NIRSPEC"] == "jwst_nirspec_0444.imap"
    assert imap1535["WAVECORR"] == imap1596["WAVECORR"] == "jwst_nirspec_wavecorr_0005.rmap"
    identity = json.loads((ROOT / "research_output/mom_public_metadata_v1.json").read_text())
    capers = next(row for row in identity["released_extractions"] if row["program"] == "6368")
    mom = next(row for row in identity["released_extractions"] if row["program"] == "5224")
    observation = Time(mom["first_shutter_mjd"], format="mjd").iso
    selected = select_wavecorr(
        (DIRECTORY / "wavecorr0005.response").read_text(), "NRS_MSASPEC", observation
    )
    reference = (DIRECTORY / "applicable_wavecorr.response").read_bytes()
    pin = json.loads((ROOT / "data_sources/followup/mom_wavecorr_receipt.json").read_text())
    if selected != pin["filename"] or hashlib.sha256(reference).hexdigest() != pin["sha256"]:
        raise ValueError("Actual applicable reference differs from original pinned file")
    text_header = reference.split(b"\n...\n", 1)[0].decode("ascii")
    if "pedigree: DUMMY" not in text_header or "exposure: {type: NRS_MSASPEC}" not in text_header:
        raise ValueError("Applicable reference metadata differs")
    with fits.open(DIRECTORY / "capers_spec.fits", memmap=False) as hdul:
        slits = hdul["SLITS"].data
        spectrum = hdul["SPEC1D"].data
        header = hdul["SCI"].header
        if len(slits) != 18 or not np.all(slits["source_id"] == 102896):
            raise ValueError("Expected eighteen compact CAPERS contributors")
        if not np.all(slits["source_ra"] == capers["coordinates_deg"][0]):
            raise ValueError("CAPERS contributor RA differs")
        if not np.all(slits["source_dec"] == capers["coordinates_deg"][1]):
            raise ValueError("CAPERS contributor declination differs")
        roots = []
        for filename in slits["filename"]:
            match = re.fullmatch(
                r"(jw06368007001_\d{5}_\d{5})_nrs2_clear_prism_raw\.139\.6368_102896\.fits",
                str(filename),
            )
            if match is None:
                raise ValueError("Unexpected compact contributor identity")
            roots.append(match.group(1))
        if sorted(roots) != capers["source_shutter_exposure_roots"]:
            raise ValueError("Compact contributors differ from planned shutter catalog")
        if set(roots) & set(mom["source_shutter_exposure_roots"]):
            raise ValueError("CAPERS and MoM exposures overlap")
        valid = np.isfinite(spectrum["flux"]) & np.isfinite(spectrum["err"])
        valid &= (spectrum["err"] > 0) & (spectrum["npix"] > 0)
        units = {column.name: column.unit for column in hdul["SPEC1D"].columns}
        if units["wave"] != "um" or units["flux"] != "uJy" or units["err"] != "uJy":
            raise ValueError("Spectrum units differ")
        coverage = [float(spectrum["wave"][valid].min()), float(spectrum["wave"][valid].max())]
        settings = {
            key: header[key]
            for key in (
                "CAL_VER",
                "CAL_VCS",
                "CRDS_CTX",
                "CRDS_VER",
                "VERSION",
                "WEIGHT_TYPE",
                "WITHPATH",
                "PROFCEN",
                "PROFSIG",
                "YMIN1D",
                "YMAX1D",
            )
        }
        contributors = [str(value) for value in slits["filename"]]
        exptime = float(np.sum(slits["exposure_time"]))

    def line(rest, redshift):
        wavelength = rest * 1e-4 * (1 + redshift)
        return {
            "wavelength_um": wavelength,
            "inside_usable_range": coverage[0] <= wavelength <= coverage[1],
        }

    return {
        "schema_version": 1,
        "plan_revision": "4316293",
        "response_bytes": total,
        "new_selected_payload_bytes": total - len(reference),
        "pinned_reference_restoration_bytes": len(reference),
        "endpoint_count": len(receipt["queries"]),
        "elapsed_last_endpoint_s": receipt["actual_elapsed_last_endpoint_s"],
        "source_observation_iso": observation,
        "context_chains": {"1535": pmap1535["NIRSPEC"], "1596": pmap1596["NIRSPEC"]},
        "same_applicable_rmap": imap1535["WAVECORR"],
        "selected_reference": selected,
        "reference_sha256": hashlib.sha256(reference).hexdigest(),
        "pedigree": "DUMMY",
        "empirical_calibration_gained": False,
        "source_position_offset_arcsec": angular_separation_arcsec(
            *mom["coordinates_deg"], *capers["coordinates_deg"]
        ),
        "compact_source_id": 102896,
        "contributor_count": 18,
        "contributors": contributors,
        "contributor_roots_disjoint_from_MoM": True,
        "exposure_time_s": exptime,
        "usable_bins": int(valid.sum()),
        "usable_wavelength_range_um": coverage,
        "units": units,
        "settings": settings,
        "known_z14p44_UV_groups": {
            name: line(rest, 14.44)
            for name, rest in (
                ("NIV1486", 1486.5),
                ("CIV1549", 1549.5),
                ("HeII_OIII1654", 1654),
                ("NIII1750", 1750),
                ("CIII1908", 1908),
            )
        },
        "weak_catalog_z6p13832_conditional_lines": {
            name: line(rest, 6.13832)
            for name, rest in (
                ("Halpha", 6562.8),
                ("NII6584", 6583.45),
                ("SII6717", 6716.44),
                ("SII6731", 6730.82),
            )
        },
        "pixtab_public_advertised_bytes": 4475520,
        "pixtab_acquired": False,
        "limits": [
            "No source-specific empirical wavelength or instrumental resolution calibration gained",
            "Old author extraction context1298 differs from current official CAL1535",
            "Author errors are diagonal; no independent nod coadds or full covariance acquired",
            "Position and disjoint contributor identity do not prove one astrophysical emitter",
            "A weak catalog redshift is not an established alternative identity",
            "Line locations are predictions only; no new spectral fit or detection reported",
            "PIXTAB is publicly accessible but exceeds this pilot allocation",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
