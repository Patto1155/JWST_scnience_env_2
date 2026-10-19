"""Frozen arm-C selection and synthetic sensitivity; no network operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from astropy.io import fits
from scipy.stats import binomtest

REST = {"O3_5007": 5008.24, "HBaB_4861": 4862.68}
CONFIGS = {"g140m_f070lp", "g140m_f100lp", "g235m_f170lp", "g395m_f290lp"}
DIRECTIONS = (("O3_5007", "HBaB_4861"), ("HBaB_4861", "O3_5007"))
SEED = 20261015


def catalog_records(path: Path) -> list[dict]:
    """Read catalog selection data only; preserve invalid target comparisons."""
    with fits.open(path) as hdul:
        obs, lines = hdul["Obs_info"].data, hdul["R1000_5pix"].data
        if set(obs["Field"]) != {"GS"}:
            raise ValueError("Require single GS catalog; GOODS-N excluded")
        if not np.array_equal(obs["Unique_ID"], lines["Unique_ID"]):
            raise ValueError("Catalog identity mismatch")
        result = []
        for i in range(len(obs)):
            record = {"unique_id": str(obs["Unique_ID"][i]), "field": "GS",
                      "z": float(obs["z_Spec"][i]), "lines": {}}
            for name in REST:
                record["lines"][name] = {
                    "flux": float(lines[f"{name}_flux"][i]),
                    "error": float(lines[f"{name}_flux_err"][i]),
                    "configuration": str(lines[f"{name}_filter"][i]),
                    "unit": hdul["R1000_5pix"].columns[f"{name}_flux"].unit,
                }
            result.append(record)
    return result


def select(records: list[dict], excluded: set[str]) -> dict:
    """Alternate directional draws; target flux and error never enter eligibility."""
    rng = np.random.Generator(np.random.PCG64(SEED))
    pools = []
    identities = [r["unique_id"] for r in records]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate catalog object identity")
    for selector, target in DIRECTIONS:
        eligible = []
        for row in sorted(records, key=lambda r: r["unique_id"]):
            if row["field"] != "GS" or not row["unique_id"].startswith("goods-s-"):
                continue
            z = row["z"]
            if row["unique_id"] in excluded or not np.isfinite(z) or z <= 0:
                continue
            s, t = row["lines"][selector], row["lines"][target]
            if not np.isfinite(s["flux"]) or not np.isfinite(s["error"]) or s["error"] <= 0:
                continue
            if not 5 <= s["flux"] / s["error"] <= 30:
                continue
            if any(row["lines"][n]["configuration"] not in CONFIGS or
                   not 0.7 <= REST[n] * (1 + z) / 10000 <= 5.3
                   for n in (selector, target)):
                continue
            eligible.append({"unique_id": row["unique_id"], "selector_line": selector,
                             "selector_snr": s["flux"] / s["error"], "line": target,
                             "rest_a": REST[target], "z": z,
                             "published_flux": t["flux"], "published_error": t["error"],
                             "configuration": t["configuration"], "unit": t.get("unit")})
        pools.append([eligible[i] for i in rng.permutation(len(eligible))])
    chosen, used = [], set(excluded)
    for _ in range(15):
        for pool in pools:
            available = next((r for r in pool if r["unique_id"] not in used), None)
            if available is None:
                raise ValueError("Fewer than 30 disjoint eligible objects; no replacement design")
            chosen.append(available)
            used.add(available["unique_id"])
    return {"field": "GS", "seed": SEED, "eligible_by_direction": [len(p) for p in pools],
            "rows": chosen, "scope": "Different-line selection; independence unverified"}


def summarize(rows: list[dict], a: float, b: float, repeats: int = 10000) -> dict:
    """Object bootstrap on paired comparisons, without a combined-error pull."""
    ids = [r["unique_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("One row per unique object required for object bootstrap")
    pairs, snrs = [], []
    for row in rows:
        f, p, e = (np.nan if row.get(key) is None else row[key]
                   for key in ("fit_flux", "published_flux", "published_error"))
        if np.isfinite(f) and np.isfinite(p) and f > 0 and p > 0:
            pairs.append(np.log(f / p))
            snrs.append(p / e if np.isfinite(e) and e > 0 else np.nan)
    y, snr = np.asarray(pairs), np.asarray(snrs)
    result = {"selected": len(rows), "positive_pairs": len(y),
              "omitted_log_pairs": len(rows) - len(y), "decision": "INCONCLUSIVE",
              "scope": "Positive-pair descriptive; selection covariance unresolved"}
    if len(y) < 2:
        return result
    rng = np.random.default_rng(SEED)
    draws = rng.integers(0, len(y), size=(repeats, len(y)))
    result.update(median_log_ratio=float(np.median(y)), sd=float(np.std(y, ddof=1)),
                  mad=float(np.median(abs(y - np.median(y)))),
                  median_ci95=np.quantile(np.median(y[draws], axis=1), [.025, .975]).tolist(),
                  median_minus_a_ci975=np.quantile(np.median(y[draws], axis=1) - a,
                                                  [.0125, .9875]).tolist())
    nonzero = y[y != a]
    result["sign_test_p"] = (float(binomtest(int(np.sum(nonzero > a)), len(nonzero)).pvalue)
                             if len(nonzero) else 1.0)
    valid = np.isfinite(snr) & (snr > 0)
    x, v = 1 / snr[valid], y[valid]
    result["model_pairs"] = len(v)
    result["A_extrapolation_pairs"] = int(np.sum(valid & ((snr < 5) | (snr > 30))))
    if len(v) < 3 or np.ptp(x) == 0:
        return result
    result["slope"] = float(np.polyfit(x, v, 1)[0])
    result["rss_H1_minus_H2"] = float(np.sum((v - a)**2 - (v - a - b*x)**2))
    sample = rng.integers(0, len(v), size=(repeats, len(v)))
    slopes, contrasts = [], []
    for indices in sample:
        xx, yy = x[indices], v[indices]
        if np.ptp(xx) > 0:
            slopes.append(float(np.polyfit(xx, yy, 1)[0]))
        contrasts.append(float(np.sum((yy - a)**2 - (yy - a - b*xx)**2)))
    result["slope_ci975"] = np.quantile(slopes, [.0125, .9875]).tolist()
    result["rss_contrast_ci975"] = np.quantile(contrasts, [.0125, .9875]).tolist()
    return result


def covariance_sensitivity(n: int = 10000) -> dict:
    """Synthetic only: latent log-flux and cross-line measurement noise correlation."""
    rng = np.random.default_rng(SEED)
    cells = []
    for physical in (0., .5, .9):
        for rho in (-.5, -.25, 0., .25, .5):
            latent = rng.multivariate_normal([0., 0.], [[1., physical], [physical, 1.]], n)
            truth = 7 * np.exp(.7 * latent)
            noise = rng.multivariate_normal([0., 0.], [[1., rho], [rho, 1.]], n)
            published = truth + noise
            refit = truth[:, 1] + rng.standard_normal(n)
            chosen = (published[:, 0] >= 5) & (published[:, 0] <= 30)
            valid = chosen & (published[:, 1] > 0) & (refit > 0)
            cells.append({"noise_rho": rho, "latent_logflux_rho": physical,
                          "simulated": n, "selected": int(chosen.sum()),
                          "invalid_log_pairs": int(np.sum(chosen & ~valid)),
                          "median_log_ratio": float(np.median(np.log(refit[valid] /
                                                                    published[valid, 1])))})
    return {"scope": "Synthetic sensitivity, not source covariance measurement",
            "seed": SEED, "cells": cells}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--old-draw", type=Path)
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.synthetic:
        result = covariance_sensitivity()
    elif args.catalog and args.old_draw:
        old = json.loads(args.old_draw.read_text())
        excluded = {r["unique_id"] for half in ("training", "heldout") for r in old[half]}
        result = select(catalog_records(args.catalog), excluded)
    else:
        parser.error("Use --synthetic or both --catalog and --old-draw")
    # Catalog nondetections remain explicit missing values, never zero or selection cuts.
    def finite_json(value):
        if isinstance(value, dict):
            return {key: finite_json(item) for key, item in value.items()}
        if isinstance(value, list):
            return [finite_json(item) for item in value]
        if isinstance(value, float) and not np.isfinite(value):
            return None
        return value

    args.output.write_text(json.dumps(finite_json(result), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
