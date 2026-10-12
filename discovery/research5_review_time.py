"""Independent VarWISE visit/astrometry audit and frozen ZTF contrast replay."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from astropy.io import ascii

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_output"


def load_csv(path: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(gzip.decompress(path.read_bytes()).decode())))


def compare(rows: list[dict], baseline: list, followup: list) -> dict:
    def within(t, windows):
        return any(lo <= t <= hi for lo, hi in windows)

    def aggregate(windows):
        selected = [r for r in rows if within(r["mjd"], windows)]
        labels = np.array([int(r["mjd"] // 30) for r in selected])
        values = np.array([r["mag"] for r in selected])
        medians = np.array([np.median(values[labels == key]) for key in np.unique(labels)])
        return len(selected), medians

    na, a = aggregate(baseline)
    nb, b = aggregate(followup)
    result = {
        "baseline_obs": na,
        "followup_obs": nb,
        "baseline_bins": len(a),
        "followup_bins": len(b),
        "eligible": na >= 15 and nb >= 15 and len(a) >= 3 and len(b) >= 3,
    }
    if len(a) < 3 or len(b) < 3:
        return result
    rng = np.random.default_rng(20261012)
    draw_b = np.median(rng.choice(b, size=(10000, len(b))), axis=1)
    draw_a = np.median(rng.choice(a, size=(10000, len(a))), axis=1)
    result.update(
        contrast=float(np.median(b) - np.median(a)),
        conditional_bin_ci95=np.quantile(draw_b - draw_a, [0.025, 0.975]).tolist(),
    )
    return result


def main() -> None:
    frozen = json.loads((OUT / "research5_time_optical_freeze.json").read_text())
    optical = {}
    inputs = {}
    for name, target in [
        ("035034", frozen["primary"]),
        ("003201", frozen["secondary"][0]),
        ("203459", frozen["secondary"][1]),
    ]:
        ztf = OUT / f"research5_time_{name}_ztf.csv.gz"
        gaia = OUT / f"research5_time_{name}_gaia_dr3_source.csv.gz"
        inputs[ztf.name] = hashlib.sha256(ztf.read_bytes()).hexdigest()
        inputs[gaia.name] = hashlib.sha256(gaia.read_bytes()).hexdigest()
        source = next(x for x in load_csv(gaia) if x["source_id"] == target["gaia_dr3_source_id"])
        raw = load_csv(ztf)
        good = []
        for row in raw:
            try:
                mjd, mag, error = (float(row[k]) for k in ["mjd", "mag", "magerr"])
                # Gaia J2016.0 epoch: half-day difference from author has negligible astrometry.
                years = (mjd - 57388.5) / 365.25
                expected_dec = float(source["dec"]) + float(source["pmdec"]) * years / 3.6e6
                expected_ra = float(source["ra"]) + float(source["pmra"]) * years / (
                    3.6e6 * np.cos(np.deg2rad(float(source["dec"])))
                )
                separation = 3600 * np.hypot(
                    (float(row["ra"]) - expected_ra) * np.cos(np.deg2rad(expected_dec)),
                    float(row["dec"]) - expected_dec,
                )
                if (
                    int(row["catflags"]) == 0
                    and 0 < error < 0.15
                    and separation <= 1
                    and np.all(np.isfinite([mjd, mag, error, separation]))
                ):
                    good.append({**row, "mjd": mjd, "mag": mag})
            except ValueError:
                continue
        baseline = target.get("baseline_windows_mjd", target.get("ir_bright_windows_mjd"))
        followup = target.get("followup_windows_mjd", target.get("ir_faint_windows_mjd"))
        groups = {}
        for row in good:
            if row["filtercode"] == "zr":
                groups.setdefault(row["oid"], []).append(row)

        def in_states(row):
            return any(lo <= row["mjd"] <= hi for lo, hi in baseline + followup)

        chosen = max(groups, key=lambda key: sum(in_states(row) for row in groups[key]))
        optical[name] = {
            "raw_rows": len(raw),
            "quality_identity_rows": len(good),
            "selected_oid": chosen,
            "oid_comparisons": {
                key: compare(rows, baseline, followup) for key, rows in groups.items()
            },
        }
        if name == "035034":
            optical[name]["cycles"] = [
                compare(groups[chosen], [a], [b]) for a, b in zip(baseline, followup, strict=True)
            ]
    path = OUT / "research5_time_035034_gator.tbl.gz"
    inputs[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    table = ascii.read(gzip.decompress(path.read_bytes()).decode(), format="ipac")
    arr = {
        key: np.ma.filled(table[key], np.nan).astype(float)
        for key in [
            "mjd",
            "ra",
            "dec",
            "w1mpro",
            "w2mpro",
            "w1sigmpro",
            "w2sigmpro",
            "w1rchi2",
            "w2rchi2",
            "qual_frame",
        ]
    }
    reference = np.char.startswith(np.asarray(table["cc_flags"]).astype(str), "00")
    reference &= arr["qual_frame"] > 0
    for band in ["w1", "w2"]:
        reference &= np.isfinite(arr[band + "mpro"])
        reference &= (arr[band + "sigmpro"] > 0) & (arr[band + "sigmpro"] < 0.15)
        reference &= arr[band + "rchi2"] < 5
    moon = np.asarray(table["moon_masked"]).astype(str) == "00"
    policies = {
        "author_reference": reference,
        "moon_clear_best_frame": reference & moon & (arr["qual_frame"] == 10),
        "moon_clear_best_frame_chi2_lt2": reference
        & moon
        & (arr["qual_frame"] == 10)
        & (arr["w1rchi2"] < 2)
        & (arr["w2rchi2"] < 2),
    }
    # Visit boundaries are selected from timestamps alone and reused across policies.
    order = np.argsort(arr["mjd"])
    bounds = np.r_[0, np.flatnonzero(np.diff(arr["mjd"][order]) > 30) + 1, len(order)]
    gaia = next(
        x
        for x in load_csv(OUT / "research5_time_035034_gaia_dr3_source.csv.gz")
        if x["source_id"] == frozen["primary"]["gaia_dr3_source_id"]
    )
    visits = {}
    for policy, accepted in policies.items():
        rows = []
        for lo, hi in zip(bounds[:-1], bounds[1:], strict=True):
            indices = order[lo:hi][accepted[order[lo:hi]]]
            if len(indices) < 4:
                continue
            mjd = float(np.median(arr["mjd"][indices]))
            years = (mjd - 57388.5) / 365.25
            ra = float(gaia["ra"]) + float(gaia["pmra"]) * years / (
                3.6e6 * np.cos(np.deg2rad(float(gaia["dec"])))
            )
            dec = float(gaia["dec"]) + float(gaia["pmdec"]) * years / 3.6e6
            dx = (arr["ra"][indices] - ra) * np.cos(np.deg2rad(dec)) * 3600
            dy = (arr["dec"][indices] - dec) * 3600
            rows.append(
                {
                    "mjd": mjd,
                    "n": len(indices),
                    "w1": float(np.median(arr["w1mpro"][indices])),
                    "w2": float(np.median(arr["w2mpro"][indices])),
                    "w1_minus_w2": float(
                        np.median(arr["w1mpro"][indices] - arr["w2mpro"][indices])
                    ),
                    "centroid_dx_arcsec": float(np.median(dx)),
                    "centroid_dy_arcsec": float(np.median(dy)),
                    "w1_chi2_median": float(np.median(arr["w1rchi2"][indices])),
                    "w2_chi2_median": float(np.median(arr["w2rchi2"][indices])),
                    "annual_phase_days": float((mjd - 51544.5) % 365.25),
                }
            )
        visits[policy] = {"accepted_rows": int(accepted.sum()), "visits": rows}
    receipt = {
        "scope": (
            "Independent readers, frozen optical contrast, exploratory IR artifact challenge; no GN"
        ),
        "limits": (
            "Conditional30day-bin bootstrap does not prove independent cycles; "
            "infrared policies are post-exploration robustness diagnostics, "
            "not new discovery tests"
        ),
        "input_gzip_sha256": inputs,
        "optical": optical,
        "infrared": visits,
    }
    (OUT / "research5_review_time.json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {
                name: result["oid_comparisons"][result["selected_oid"]]
                for name, result in optical.items()
            },
            indent=2,
        )
    )
    print(
        json.dumps(
            {
                name: {"accepted_rows": result["accepted_rows"], "visits": len(result["visits"])}
                for name, result in visits.items()
            }
        )
    )


if __name__ == "__main__":
    main()
