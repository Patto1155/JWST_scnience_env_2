"""Frozen optical state comparisons on independent ZTF facility photometry."""

import csv
import io
import json
from pathlib import Path

import numpy as np

from discovery.research5_time_scout import verified_bytes

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_output"
F = json.loads((OUT / "research5_time_optical_freeze.json").read_text())
SEED = 20261012


def rows(name):
    return list(csv.DictReader(io.StringIO(verified_bytes(f"{name}_ztf.csv").decode())))


def inwindows(t, windows):
    return any(lo <= t <= hi for lo, hi in windows)


def compare(a, wa, wb):
    va = [r for r in a if inwindows(r["mjd"], wa)]
    vb = [r for r in a if inwindows(r["mjd"], wb)]

    def bins(rs):
        ix = {}
        for r in rs:
            ix.setdefault(int(np.floor(r["mjd"] / 30)), []).append(r["mag"])
        return np.array([np.median(v) for _, v in sorted(ix.items())])

    x = bins(va)
    y = bins(vb)
    if len(x) < 3 or len(y) < 3:
        return {
            "a_obs": len(va),
            "b_obs": len(vb),
            "a_bins": len(x),
            "b_bins": len(y),
            "eligible": False,
        }
    rng = np.random.default_rng(SEED)
    samples = np.median(rng.choice(y, (10000, len(y))), axis=1) - np.median(
        rng.choice(x, (10000, len(x))), axis=1
    )
    return {
        "a_obs": len(va),
        "b_obs": len(vb),
        "a_bins": len(x),
        "b_bins": len(y),
        "contrast_b_minus_a": float(np.median(y) - np.median(x)),
        "ci95_conditional_30day": np.quantile(samples, [0.025, 0.975]).tolist(),
        "eligible": len(va) >= 15 and len(vb) >= 15,
        "a_median": float(np.median(x)),
        "b_median": float(np.median(y)),
    }


def quality_rows(data, g):
    good = []
    for r in data:
        try:
            t = float(r["mjd"])
            mag = float(r["mag"])
            err = float(r["magerr"])
            dt = (t - 57388.0) / 365.25
            ra = float(g["ra"]) + float(g["pmra"]) * dt / (
                3600000 * np.cos(np.deg2rad(float(g["dec"])))
            )
            dec = float(g["dec"]) + float(g["pmdec"]) * dt / 3600000
            sep = 3600 * np.hypot(
                (float(r["ra"]) - ra) * np.cos(np.deg2rad(dec)), float(r["dec"]) - dec
            )
            if (
                int(r["catflags"])
                or not 0 < err < 0.15
                or not np.all(np.isfinite([mag, err, t, sep]))
                or sep > 1
            ):
                continue
            good.append({**r, "mjd": t, "mag": mag, "magerr": err, "sep_arcsec": float(sep)})
        except ValueError:
            continue
    return good


def main():
    results = {}
    for name, c in [
        ("035034", F["primary"]),
        ("003201", F["secondary"][0]),
        ("203459", F["secondary"][1]),
    ]:
        data = rows(name)
        gaia = list(
            csv.DictReader(io.StringIO(verified_bytes(f"{name}_gaia_dr3_source.csv").decode()))
        )
        g = next(r for r in gaia if r["source_id"] == c["gaia_dr3_source_id"])
        good = quality_rows(data, g)
        wa = c.get("baseline_windows_mjd", c.get("ir_bright_windows_mjd"))
        wb = c.get("followup_windows_mjd", c.get("ir_faint_windows_mjd"))
        groups = {}
        for r in good:
            if r["filtercode"] != "zr":
                continue
            groups.setdefault(r["oid"], []).append(r)
        comparisons = {oid: compare(a, wa, wb) for oid, a in groups.items()}
        chosen = (
            max(groups, key=lambda oid: sum(inwindows(r["mjd"], wa + wb) for r in groups[oid]))
            if groups
            else None
        )
        results[name] = {
            "designation": c["designation"],
            "total_rows": len(data),
            "quality_identity_rows": len(good),
            "oid_comparisons": comparisons,
            "selected_oid": chosen,
            "selected_comparison": comparisons.get(chosen),
            "all_filter_counts": {
                band: sum(r["filtercode"] == band for r in good) for band in ["zg", "zr", "zi"]
            },
        }
        if name == "035034" and chosen:
            meta = groups[chosen][0]
            gs = [
                r
                for r in good
                if r["filtercode"] == "zg"
                and all(r[k] == meta[k] for k in ["field", "ccdid", "qid"])
            ]
            candidates = sorted(
                (abs(r["mjd"] - g["mjd"]), i, j)
                for i, r in enumerate(groups[chosen])
                for j, g in enumerate(gs)
                if abs(r["mjd"] - g["mjd"]) <= 1
            )
            used_r = set()
            used_g = set()
            pairs = []
            for dt, i, j in candidates:
                if i in used_r or j in used_g:
                    continue
                used_r.add(i)
                used_g.add(j)
                r = groups[chosen][i]
                g = gs[j]
                pairs.append({"mjd": (r["mjd"] + g["mjd"]) / 2, "mag": g["mag"] - r["mag"]})
            results[name]["g_minus_r_ancillary"] = compare(pairs, wa, wb)
            results[name]["g_minus_r_pairs"] = len(pairs)
            results[name]["individual_cycles"] = [
                compare(groups[chosen], [[58623, 59187]], [[58206, 58564]]),
                compare(groups[chosen], [[60082, 60283]], [[59660, 59968]]),
            ]
    (OUT / "research5_time_optical_results.json").write_text(
        json.dumps(results, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps(results, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
