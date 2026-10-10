"""Independent literal-selector and actual compact FITS validation, without author code."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    receipt_path = ROOT / "data_sources/compact_followup/receipt.json"
    receipt = json.loads(receipt_path.read_text())
    hashes = {}
    for q in receipt["queries"]:
        if not q.get("path"):
            continue
        p = ROOT / q["path"]
        if q["status"] != 200 or p.stat().st_size != q["bytes"] or digest(p) != q["sha256"]:
            raise ValueError("archived input identity/response mismatch")
        hashes[q["path"]] = digest(p)
    base = ROOT / "data_sources/compact_followup"
    # Inspect literal AST selectors, never execute remote mapping files.
    tree = ast.parse((base / "wavecorr0005.response").read_text())
    call = next(
        n.value for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "selector"
    )
    modes = call.args[0]
    msa = next(v for k, v in zip(modes.keys, modes.values) if ast.literal_eval(k) == "NRS_MSASPEC")
    dates = ast.literal_eval(msa.args[0])
    selected = dates[max(t for t in dates if t <= "2025-04-16 03:54:27.628")]
    if selected != "jwst_nirspec_wavecorr_0004.asdf":
        raise ValueError("applicable literal reference changed")
    old = ROOT / "data_sources/followup" / selected
    ref = base / "applicable_wavecorr.response"
    if digest(old) != digest(ref) or b"pedigree: DUMMY" not in ref.read_bytes()[:2122]:
        raise ValueError("reference identity or DUMMY pedigree differs")
    chain = []
    for filename, key in (
        ("latest1596.response", "NIRSPEC"),
        ("latest_nirspec.response", "WAVECORR"),
    ):
        tree = ast.parse((base / filename).read_text())
        value = next(
            n.value
            for n in tree.body
            if isinstance(n, ast.Assign) and n.targets[0].id == "selector"
        )
        chain.append(ast.literal_eval(value)[key])
    if chain != ["jwst_nirspec_0444.imap", "jwst_nirspec_wavecorr_0005.rmap"]:
        raise ValueError("captured context1596 selector chain mismatch")
    path = base / "capers_spec.fits"
    mom = ROOT / "data_sources/pilot/mom_z14_dja_v4.spec.fits"
    with fits.open(path) as h, fits.open(mom) as original:
        t = h["SPEC1D"].data
        good = (
            np.isfinite(t["wave"])
            & np.isfinite(t["flux"])
            & np.isfinite(t["err"])
            & (t["err"] > 0)
            & (t["npix"] > 0)
        )

        def root(x):
            return re.search(r"jw\d{11}_\d{5}_\d{5}_nrs2", str(x)).group(0)

        roots = [root(x) for x in h["SLITS"].data["filename"]]
        inherited = [root(x) for x in original["SLITS"].data["filename"]]
        if (
            len(roots) != len(set(roots))
            or len(roots) != 18
            or not set(roots).isdisjoint(inherited)
        ):
            raise ValueError("contributor count/unique photon identity differs")
        rows = h["SLITS"].data
        if set(rows["source_id"]) != {102896} or set(rows["detector"]) != {"NRS2"}:
            raise ValueError("source/detector identity mismatch")
        if np.ptp(rows["source_ra"]) != 0 or np.ptp(rows["source_dec"]) != 0:
            raise ValueError("source position varies")
        separation = (
            SkyCoord(rows["source_ra"][0] * u.deg, rows["source_dec"][0] * u.deg)
            .separation(SkyCoord(150.0933255 * u.deg, 2.2731627 * u.deg))
            .arcsec
        )
        units = [h["SPEC1D"].columns[n].unit for n in ("wave", "flux", "err")]
        if units != ["um", "uJy", "uJy"]:
            raise ValueError("spectral units differ")
        exptime = float(rows["exposure_time"].sum())
        if abs(exptime - h["SCI"].header["EXPTIME"]) > 1e-9:
            raise ValueError("summed exposure time differs")
        lo, hi = float(t["wave"][good].min()), float(t["wave"][good].max())
    author = json.loads((ROOT / "research_output/mom_compact_followup_v1.json").read_text())
    if author["usable_bins"] != int(good.sum()) or author["usable_wavelength_range_um"] != [lo, hi]:
        raise ValueError("independent usable-pixel scope differs from author")
    uv_centers = (
        np.array([1483.321, 1486.496, 1548.204, 1550.781, 1640.42, 1750.0, 1906.683, 1908.734])
        * 1e-4
        * 15.44
    )
    if np.any((uv_centers >= lo) & (uv_centers <= hi)):
        raise ValueError("unexpected UV line coverage")
    return {
        "reviewed_commit": "ba99a31031deaa17ead2eb7cd95c40a31e25dbb8",
        "independent_code_calls_author_module": False,
        "passed": True,
        "inputs_sha256": hashes,
        "captured_context1596_selector_chain": chain,
        "applicable_reference": selected,
        "same_whole_reference_SHA256": digest(ref),
        "pedigree": "DUMMY",
        "exposure_roots_disjoint_MoM": True,
        "unique_NRS2_exposures": len(roots),
        "exposure_time_s": exptime,
        "source_position_offset_arcsec": float(separation),
        "usable_bins": int(good.sum()),
        "usable_wavelength_range_um": [lo, hi],
        "units": units,
        "UV_nitrogen_coverage_at_z14p44": False,
        "MgII_2796_2803_prediction_um": [2796.354 * 1e-4 * 15.44, 2803.531 * 1e-4 * 15.44],
        "scope": (
            "captured CRDS selector and actual compact FITS identity; "
            "no spectral fit or covariance reconstruction"
        ),
    }


def pixtab_gate(path: Path) -> dict:
    expected = "2c0d315274d0d0c74252f6d584e80636ae49e3a1361c0976216a366e8dbe6430"
    if path.stat().st_size != 4475520 or digest(path) != expected:
        raise ValueError("new CAPERS PIXTAB identity mismatch")
    with (
        fits.open(path) as h,
        fits.open(ROOT / "data_sources/compact_followup/capers_spec.fits") as s,
    ):
        table, hdr = h["PIXTAB"].data, h["PIXTAB"].header
        names = [
            "sci",
            "sky",
            "var_total",
            "var_rnoise",
            "wave",
            "dwave_dx",
            "yslit",
            "bar",
            "profile",
            "pathloss",
            "exposure_index",
            "exptime",
        ]
        if table.names != names or not all(np.all(np.isfinite(table[n])) for n in names):
            raise ValueError("unexpected table schema or nonfinite values")
        if len(table) != 46519 or not np.array_equal(
            np.unique(table["exposure_index"]), np.arange(18)
        ):
            raise ValueError("unexpected pixel count/exposure indices")
        if not np.all(table["pathloss"] > 0):
            raise ValueError("nonpositive pathloss")
        settings = {
            k: hdr[k] for k in ("VERSION", "WITHPATH", "PROFCEN", "PROFSIG", "YMIN1D", "YMAX1D")
        }
        if any(v != s["SPEC1D"].header[k] for k, v in settings.items()):
            raise ValueError("PIXTAB optimized extraction settings differ from SPEC")
        uv_count = int(np.sum((table["wave"] >= 2.15) & (table["wave"] <= 3.2)))
        if uv_count:
            raise ValueError("unexpected UV pixel coverage")
        return {
            "sha256": expected,
            "bytes": path.stat().st_size,
            "rows": len(table),
            "schema": names,
            "exposure_indices": np.unique(table["exposure_index"]).tolist(),
            "finite_fields": True,
            "positive_pathloss": True,
            "negative_profile_rows": int(np.sum(table["profile"] < 0)),
            "wave_um_minmax": [float(table["wave"].min()), float(table["wave"].max())],
            "UV_2p15_to_3p2_rows": uv_count,
            "settings": settings,
            "individual_raw_donor_pixel_mapping_available": False,
            "NRS1_companion_coverage_established": False,
            "scope": (
                "actual NRS2 author intermediate coverage gate; no spectral fit or full covariance"
            ),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pixtab", type=Path)
    args = parser.parse_args()
    result = run()
    if args.pixtab is not None:
        result["new_CAPERS_PIXTAB_coverage_gate"] = pixtab_gate(args.pixtab)
    (ROOT / "research_output/research2_compact_followup_review.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps({"passed": result["passed"], "usable_bins": result["usable_bins"]}))
