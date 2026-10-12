"""Independent local-scan control and contemporaneous optical variability audit."""

from __future__ import annotations

import csv
import gzip
import io
import json
from pathlib import Path

import numpy as np
from astropy.io import ascii

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_output"


def ir_visits(path: Path) -> list[dict]:
    t = ascii.read(gzip.decompress(path.read_bytes()).decode(), format="ipac")
    flags = np.asarray(t["cc_flags"]).astype(str)
    valid = np.char.startswith(flags, "00") & (np.asarray(t["qual_frame"]) > 0)
    for band in ["w1", "w2"]:
        mag = np.ma.filled(t[band + "mpro"], np.nan)
        err = np.ma.filled(t[band + "sigmpro"], np.nan)
        chi = np.ma.filled(t[band + "rchi2"], np.nan)
        valid &= np.isfinite(mag) & (err > 0) & (err < 0.15) & (chi < 5)
    times = np.asarray(t["mjd"])[valid]
    mags = np.column_stack([np.asarray(t[c])[valid] for c in ["w1mpro", "w2mpro"]])
    order = np.argsort(times)
    times, mags = times[order], mags[order]
    groups = np.split(np.arange(len(times)), np.flatnonzero(np.diff(times) > 30) + 1)
    return [
        {
            "mjd": float(np.median(times[ix])),
            "n": len(ix),
            "w1": float(np.median(mags[ix, 0])),
            "w2": float(np.median(mags[ix, 1])),
        }
        for ix in groups
        if len(ix) >= 4
    ]


def main() -> None:
    target = ir_visits(OUT / "research5_time_035034_gator.tbl.gz")
    control = ir_visits(OUT / "research5_time_035030_control_gator.tbl.gz")
    matches = []
    for visit in target:
        ref = min(control, key=lambda row: abs(row["mjd"] - visit["mjd"]))
        if abs(ref["mjd"] - visit["mjd"]) <= 5:
            matches.append(
                {
                    "mjd": visit["mjd"],
                    "target_n": visit["n"],
                    "control_n": ref["n"],
                    "target_w1": visit["w1"],
                    "target_w2": visit["w2"],
                    "control_w1": ref["w1"],
                    "control_w2": ref["w2"],
                    "differential_w1": visit["w1"] - ref["w1"],
                    "differential_w2": visit["w2"] - ref["w2"],
                }
            )
    summary = {
        key + "_range": float(np.ptp([row[key] for row in matches]))
        for key in [
            "target_w1",
            "target_w2",
            "control_w1",
            "control_w2",
            "differential_w1",
            "differential_w2",
        ]
    }
    raw = list(
        csv.DictReader(
            io.StringIO(
                gzip.decompress((OUT / "research5_time_035034_ztf.csv.gz").read_bytes()).decode()
            )
        )
    )
    # Use the prospectively count-selected primary OID. Exact Gaia identity/cut
    # agreement was independently verified in research5_review_time.json.
    oid = json.loads((OUT / "research5_review_time.json").read_text())["optical"]["035034"][
        "selected_oid"
    ]
    rows = [
        r
        for r in raw
        if r["oid"] == oid
        and r["filtercode"] == "zr"
        and int(r["catflags"]) == 0
        and 0 < float(r["magerr"]) < 0.15
    ]
    mjd = np.array([float(r["mjd"]) for r in rows])
    mag = np.array([float(r["mag"]) for r in rows])
    gaia_rows = list(
        csv.DictReader(
            io.StringIO(
                gzip.decompress(
                    (OUT / "research5_time_035034_gaia_dr3_source.csv.gz").read_bytes()
                ).decode()
            )
        )
    )
    gaia = next(r for r in gaia_rows if r["source_id"] == "219690291611604480")
    years = (mjd - 57388.5) / 365.25
    expected_dec = float(gaia["dec"]) + float(gaia["pmdec"]) * years / 3.6e6
    expected_ra = float(gaia["ra"]) + float(gaia["pmra"]) * years / (
        3.6e6 * np.cos(np.deg2rad(float(gaia["dec"])))
    )
    ra = np.array([float(r["ra"]) for r in rows])
    dec = np.array([float(r["dec"]) for r in rows])
    separation = 3600 * np.hypot(
        (ra - expected_ra) * np.cos(np.deg2rad(expected_dec)), dec - expected_dec
    )
    good = np.isfinite(mjd) & np.isfinite(mag) & np.isfinite(separation) & (separation <= 1)
    mjd, mag = mjd[good], mag[good]
    labels = np.floor(mjd / 30).astype(int)
    medians = np.array([np.median(mag[labels == key]) for key in np.unique(labels)])
    aligned = []
    for visit in target:
        selected = abs(mjd - visit["mjd"]) <= 30
        if selected.sum() >= 3:
            aligned.append(
                {
                    "ir_mjd": visit["mjd"],
                    "ir_w1": visit["w1"],
                    "ir_w2": visit["w2"],
                    "optical_r_n": int(selected.sum()),
                    "optical_r_median": float(np.median(mag[selected])),
                }
            )
    result = {
        "scope": (
            "Independent local NEOWISE control plus post-frozen-test "
            "descriptive optical timing audit"
        ),
        "matched_visit_count": len(matches),
        "matched_visits": matches,
        "ranges": summary,
        "optical_oid": oid,
        "optical_30day_bin_count": len(medians),
        "optical_30day_median_range": float(np.ptp(medians)),
        "optical_30day_median_extrema": [float(medians.min()), float(medians.max())],
        "contemporaneous_ir_optical": aligned,
        "limits": (
            "Null frozen long-window median does not establish optical constancy or "
            "decoupling; scan control bounds common local effects, not target-specific "
            "ghost/blend; three postselected minima do not certify periodicity"
        ),
    }
    (OUT / "research5_review_time_control.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {
                "matched_visits": len(matches),
                **summary,
                "optical_30day_median_range": result["optical_30day_median_range"],
                "matched_ir_optical_visits": len(aligned),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
