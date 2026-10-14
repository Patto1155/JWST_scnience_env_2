"""Frozen conditional released-1D estimator agreement, never raw validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from astropy.io import fits
from scipy.special import logsumexp, ndtr
from scipy.stats import kstest

LINES = (("O3_5007", 5008.24), ("HBaB_4861", 4862.68), ("HBaG_4340", 4341.68))


def select(path: Path, field: str = "GS") -> dict:
    with fits.open(path) as h:
        obs, lines = h["Obs_info"].data, h["R1000_5pix"].data
        if field not in {"GS", "GN"} or set(obs["Field"]) != {field}:
            raise ValueError("Explicit single frozen field required; reject mixed catalogues")
        if not np.array_equal(obs["Unique_ID"], lines["Unique_ID"]):
            raise ValueError("Catalogue identity mismatch")
        rows = []
        for i in np.argsort(obs["Unique_ID"]):
            for name, rest in LINES:
                f, e = float(lines[f"{name}_flux"][i]), float(lines[f"{name}_flux_err"][i])
                z = float(obs["z_Spec"][i])
                config = str(lines[f"{name}_filter"][i])
                if (
                    np.isfinite(f + e + z)
                    and e > 0
                    and f > 0
                    and z > 0
                    and 5 <= f / e <= 30
                    and 0.7 <= rest * (1 + z) / 10000 <= 5.3
                    and config in {"g140m_f070lp", "g140m_f100lp", "g235m_f170lp", "g395m_f290lp"}
                ):
                    rows.append(
                        {
                            "unique_id": str(obs["Unique_ID"][i]),
                            "line": name,
                            "rest_a": rest,
                            "z": z,
                            "configuration": config,
                            "published_flux": f,
                            "published_error": e,
                            "unit": h["R1000_5pix"].columns[f"{name}_flux"].unit,
                        }
                    )
        if len(rows) < 30:
            raise ValueError(f"Only {len(rows)} eligible lines, need 30")
        idx = np.random.Generator(np.random.PCG64(20261014)).choice(len(rows), 30, replace=False)
        return {
            "field": field,
            "seed": 20261014,
            "eligible": len(rows),
            "training": [rows[i] for i in idx[:15]],
            "heldout": [rows[i] for i in idx[15:]],
            "scope": "Conditional shared-photon estimator agreement",
        }


def marginal_fit(table: dict, rest_a: float, z: float) -> dict:
    w, y, e = (np.asarray(table[key], float) for key in ("WAVELENGTH", "FLUX", "FLUX_ERR"))
    center = rest_a * (1 + z) / 10000
    dw = float(np.median(np.diff(w)))
    good = (abs(w - center) < 0.015) & np.isfinite(y + e) & (e > 0)
    x, y, e = w[good], y[good] / 1e-20, e[good] / 1e-20
    if len(x) < 8 or dw <= 0:
        raise ValueError("Insufficient finite bins or unordered wavelengths")
    u, weights = np.polynomial.legendre.leggauss(41)
    means, variances, logs = [], [], []
    for delta, prior in zip(-0.25 + u, weights / 2):
        for width in np.linspace(0.2, 3, 41) * dw:
            line = (
                ndtr((x + dw / 2 - center - delta * dw) / width)
                - ndtr((x - dw / 2 - center - delta * dw) / width)
            ) / (dw * 10000)
            design = np.column_stack((np.ones(len(x)), (x - center) / 0.015, line)) / e[:, None]
            precision = design.T @ design
            sign, logdet = np.linalg.slogdet(precision)
            if sign <= 0 or np.linalg.matrix_rank(design) != 3:
                continue
            cov = np.linalg.inv(precision)
            mean = cov @ design.T @ (y / e)
            chi2 = float(np.sum((design @ mean - y / e) ** 2))
            means.append(mean[2])
            variances.append(cov[2, 2])
            logs.append(-chi2 / 2 - logdet / 2 + np.log(prior / 41))
    if not logs:
        raise ValueError("No identifiable marginal nodes")
    prob = np.exp(np.array(logs) - logsumexp(logs))
    means = np.array(means)
    flux = float(prob @ means)
    variance = float(prob @ (np.array(variances) + (means - flux) ** 2))
    return {
        "flux_1e20": flux,
        "error_1e20": float(np.sqrt(variance)),
        "bins": len(x),
        "nodes": len(logs),
        "assumed_prior": "delta=-0.25+Uniform[-1,1] pixels",
        "scope": "Conditional diagonal-noise marginalization; not calibrated population coverage",
    }


def pull_summary(pulls: list[float]) -> dict:
    p = np.asarray(pulls, float)
    if len(p) < 12:
        return {"usable": len(p), "gate": "FAIL_TOO_FEW", "error_scale_identified": False}
    test = kstest(p, "norm")
    return {
        "usable": len(p),
        "gate": "DESCRIPTIVE_ONLY",
        "mean": float(p.mean()),
        "sd": float(p.std(ddof=1)),
        "ks_d": float(test.statistic),
        "ks_p": float(test.pvalue),
        "error_scale_identified": False,
        "caveat": (
            "Shared photons, unknown covariance, different estimators and S/N selection; "
            "SD is not published-error scale"
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--select", type=Path)
    source.add_argument("--replay", type=Path)
    p.add_argument("--field", choices=["GS", "GN"], default="GS")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.replay:
        report = json.loads(args.replay.read_text())
        replay = []
        for row in report["results"]:
            if "fit" not in row:
                continue
            with np.load(row["compact"], allow_pickle=False) as arrays:
                table = {key: arrays[key] for key in ("WAVELENGTH", "FLUX", "FLUX_ERR")}
                fit = marginal_fit(table, row["rest_a"], row["z"])
            replay.append(
                {
                    "unique_id": row["unique_id"],
                    "line": row["line"],
                    "maximum_numeric_difference": max(
                        abs(fit[k] - row["fit"][k]) for k in ("flux_1e20", "error_1e20")
                    ),
                }
            )
        result = {"scope": "Same-photon compact numerical replay", "rows": replay}
    else:
        result = select(args.select, args.field)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
