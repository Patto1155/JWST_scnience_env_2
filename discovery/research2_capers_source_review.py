"""Independent actual source-specific CAPERS X1D/S2D coordinate coverage oracle."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
from astropy.io import fits

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SOURCE = {
    "SOURCEID": 102896,
    "SRCRA": 150.0933178,
    "SRCDEC": 2.2731591,
    "SRCTYPE": "POINT",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pixel_gate(wave, science, error, weight, context, dq=None):
    """Coordinates before flags; signed context planes indicate support by nonzero bits."""
    wave = np.asarray(wave)
    if not all(np.asarray(x).shape == wave.shape for x in (science, error, weight)):
        raise ValueError("pixel coordinate/array shape mismatch")
    if context.shape[1:] != wave.shape:
        raise ValueError("context shape mismatch")
    uv = np.isfinite(wave) & (wave >= 2.15) & (wave <= 3.2)
    finite = np.isfinite(wave) & np.isfinite(science) & np.isfinite(error)
    supported = finite & (error > 0) & (weight > 0) & np.any(context != 0, axis=0)
    return {
        "pixels": int(wave.size),
        "finite_wavelength_pixels": int(np.isfinite(wave).sum()),
        "uv_wavelength_pixels_before_quality_cuts": int(uv.sum()),
        "finite_science_error_wavelength_pixels": int(finite.sum()),
        "positive_error_weight_context_supported_pixels": int(supported.sum()),
        "uv_supported_pixels_before_dq": int((uv & supported).sum()),
        "dq_array_present": dq is not None,
        "uv_supported_pixels_after_supplied_dq": None
        if dq is None
        else int((uv & supported & ((dq & 1) == 0)).sum()),
    }


def run():
    hashes = {}
    for filename in (
        "data_sources/capers_companion/receipt.json",
        "data_sources/capers_s2d/receipt.json",
    ):
        receipt = json.loads((ROOT / filename).read_text())
        records = receipt.get("queries", [receipt])
        for q in records:
            if not q.get("path") and "queries" in receipt:
                continue
            name = q.get("path", "data_sources/capers_s2d/source_s2d.fits")
            p = ROOT / name
            if q["status"] != 200 or p.stat().st_size != q["bytes"] or digest(p) != q["sha256"]:
                raise ValueError("archived source input identity mismatch")
            hashes[name] = digest(p)
    association_path = ROOT / "data_sources/capers_companion/source_association.json"
    asn = json.loads(association_path.read_text())
    if len(asn["products"]) != 1 or asn["products"][0]["name"] != (
        "jw06368-o007_{source_id}_nirspec_clear-prism"
    ):
        raise ValueError("unexpected source association product")
    members = asn["products"][0]["members"]
    science = sorted(m["expname"] for m in members if m["exptype"] == "science")
    if len(members) != 44 or len(science) != len(set(science)) or len(science) != 36:
        raise ValueError("unexpected source-association science membership")
    detector_counts = {d: sum(f"_{d}_cal.fits" in x for x in science) for d in ("nrs1", "nrs2")}
    if detector_counts != {"nrs1": 18, "nrs2": 18}:
        raise ValueError("both-detector source association missing")
    x1d_path = ROOT / "data_sources/capers_companion/source_x1d.fits"
    s2d_path = ROOT / "data_sources/capers_s2d/source_s2d.fits"
    with fits.open(x1d_path) as x, fits.open(s2d_path) as s:
        for h, ext in ((x, "EXTRACT1D"), (s, "SCI")):
            if any(h[ext].header[k] != v for k, v in EXPECTED_SOURCE.items()):
                raise ValueError("actual source coordinates/type/identity mismatch")
            if (h[0].header["CAL_VER"], h[0].header["CRDS_CTX"], h[0].header["DETECTOR"]) != (
                "3.0.0",
                "jwst_1584.pmap",
                "MULTIPLE",
            ):
                raise ValueError("calibration context/detector mismatch")
            if h[0].header["ASNTABLE"] != "jw06368-o007_20260920t075233_spec3_00001_asn.json":
                raise ValueError("source association identity mismatch")
        table = x["EXTRACT1D"].data
        units = {n: x["EXTRACT1D"].columns[n].unit for n in ("WAVELENGTH", "FLUX", "FLUX_ERROR")}
        if units != {"WAVELENGTH": "um", "FLUX": "Jy", "FLUX_ERROR": "Jy"}:
            raise ValueError("X1D units inconsistent")
        wave = table["WAVELENGTH"]
        uv = np.isfinite(wave) & (wave >= 2.15) & (wave <= 3.2)
        good = (
            np.isfinite(wave)
            & np.isfinite(table["FLUX"])
            & np.isfinite(table["FLUX_ERROR"])
            & (table["FLUX_ERROR"] > 0)
            & (table["NPIXELS"] > 0)
            & ((table["DQ"] & 1) == 0)
        )
        gap = np.argmax(np.diff(wave))
        xcoverage = {
            "rows": len(table),
            "usable_rows": int(good.sum()),
            "uv_rows": int(uv.sum()),
            "usable_uv_rows": int((uv & good).sum()),
            "largest_adjacent_gap_um": [float(wave[gap]), float(wave[gap + 1])],
        }
        hdr_members = sorted(str(f) for f in s["HDRTAB"].data["FILENAME"])
        if hdr_members != science:
            raise ValueError("actual S2D contributors differ from source ASN science")
        swave = s["WAVELENGTH"].data
        if swave.shape != (31, 277) or not np.array_equal(
            swave, np.broadcast_to(wave.astype(swave.dtype), swave.shape)
        ):
            raise ValueError("S2D wavelength grid not explicitly X1D micron grid")
        grid_error = float(np.max(np.abs(swave - wave)))
        raw_asdf = s["ASDF"].data["ASDF_METADATA"][0].tobytes().split(b"\xd3BLK")[0].decode("utf8")
        spectral = re.search(r"spectral_frame-.*?\n(.*?)\n        name: slit_frame", raw_asdf, re.S)
        if (
            spectral is None
            or "axes_names: [wavelength]" not in spectral.group(1)
            or ("unit: [!unit/unit-1.0.0 um]" not in spectral.group(1))
        ):
            raise ValueError("embedded spectral frame does not declare micron wavelength")
        if "source: fits:WAVELENGTH,1" not in raw_asdf:
            raise ValueError("ASDF model wavelength not mapped to actual WAVELENGTH HDU")
        if s["WAVELENGTH"].header.get("BUNIT") is not None or "DQ" in s:
            raise ValueError("expected explicit missing wavelength BUNIT/DQ scope changed")
        if s["SCI"].header["BUNIT"] != "MJy" or s["ERR"].header["BUNIT"] != "MJy":
            raise ValueError("S2D SCI/ERR unit mismatch")
        scoverage = pixel_gate(swave, s["SCI"].data, s["ERR"].data, s["WHT"].data, s["CON"].data)
    author_x = json.loads((ROOT / "research_output/capers_companion_coverage_v1.json").read_text())
    author_s = json.loads((ROOT / "research_output/capers_s2d_coverage_v1.json").read_text())
    if xcoverage["uv_rows"] or scoverage["uv_wavelength_pixels_before_quality_cuts"]:
        raise ValueError("unexpected actual product UV coordinate support")
    for key in ("rows", "usable_rows", "uv_rows", "usable_uv_rows"):
        if author_x["coverage"][key] != xcoverage[key]:
            raise ValueError("independent X1D pixel counts disagree")
    if author_s["coverage"] != scoverage:
        raise ValueError("independent S2D pixel counts disagree")
    return {
        "reviewed_companion_commit": "a768eb3",
        "reviewed_S2D_commit": "db0e170",
        "passed": True,
        "calls_author_analysis_functions": False,
        "inputs_sha256": hashes,
        "source": EXPECTED_SOURCE,
        "association_members": 44,
        "science_contributors": 36,
        "detector_science_counts": detector_counts,
        "actual_S2D_HDRTAB_matches_source_ASN": True,
        "X1D_units": units,
        "S2D_spectral_frame_units": "um",
        "S2D_SCI_ERR_units": "MJy",
        "S2D_wavelength_BUNIT": None,
        "X1D_S2D_wavelength_max_difference_um": grid_error,
        "X1D_coverage": xcoverage,
        "S2D_coverage": scoverage,
        "rejected_explanation": (
            "UV absence is solely an official X1D quality/extraction-mask omission"
        ),
        "scope": (
            "these exact pipeline source X1D/S2D products; no raw detector absence, "
            "flux limit or new observing necessity"
        ),
    }


if __name__ == "__main__":
    result = run()
    (ROOT / "research_output/research2_capers_source_review.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps({"passed": result["passed"], "S2D_coverage": result["S2D_coverage"]}))
