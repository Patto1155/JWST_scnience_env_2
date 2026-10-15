"""One-shot southern confirmation using frozen paired-log predictions."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import requests
from astropy.io import fits
from scipy.stats import binomtest

from data_pipeline.calibrated_population import marginal_fit
from data_pipeline.calibrated_population_run import now
from data_pipeline.session_known_answer import normalized_table

CAP = int(0.3 * 2**30)


def run(prediction: Path, output: Path) -> None:
    frozen = json.loads(prediction.read_text())
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    relative = prediction.as_posix()
    committed = subprocess.check_output(["git", "show", f"{commit}:{relative}"])
    if committed != prediction.read_bytes():
        raise ValueError("Prediction must be committed unchanged before access")
    marker = output.with_suffix(".access.json")
    receipt = {"freeze_commit": commit, "started_utc": now(), "opening_sessions": 1}
    with marker.open("x") as stream:
        json.dump(receipt, stream, indent=2)
    report = {**receipt, "cap_bytes": CAP, "body_bytes": 0, "rows": [], "receipts": []}
    output.write_text(json.dumps(report, indent=2) + "\n")
    for index, row in enumerate(frozen["rows"]):
        tier, target = row["unique_id"].rsplit("_", 1)
        grating, filt = row["configuration"].split("_")
        config = f"{filt}-{grating}"
        name = f"hlsp_jades_jwst_nirspec_{tier}-{int(target):08d}_{config}_v2.0_x1d.fits"
        url = f"https://archive.stsci.edu/hlsps/jades/dr4/goods-s/spectra/{config}/{tier}/{name}"
        transfer = {"url": url, "started_utc": now(), "body_bytes": 0}
        report["receipts"].append(transfer)
        raw = output.parent / "holdout_raw.fits"
        try:
            with requests.head(url, timeout=(8, 15), allow_redirects=True) as response:
                transfer["head_status"] = response.status_code
                transfer["proxy_error"] = response.headers.get("x-proxy-error")
                response.raise_for_status()
                size = int(response.headers["Content-Length"])
            transfer["reserved_bytes"] = size
            transfer["disk_free_bytes"] = shutil.disk_usage(output.parent).free
            if report["body_bytes"] + size > CAP:
                raise ValueError(f"Arm cap: next body requires {size} bytes")
            if transfer["disk_free_bytes"] - size < 5_000_000_000:
                raise ValueError("5 GB disk floor")
            with requests.get(url, stream=True, timeout=(8, 25)) as response:
                transfer["get_status"] = response.status_code
                with raw.open("wb") as stream:
                    for chunk in response.iter_content(65536):
                        transfer["body_bytes"] += len(chunk)
                        report["body_bytes"] += len(chunk)
                        if transfer["body_bytes"] > size or report["body_bytes"] > CAP:
                            raise ValueError("Overlength response charged; stopping")
                        stream.write(chunk)
                response.raise_for_status()
            transfer["sha256"] = hashlib.sha256(raw.read_bytes()).hexdigest()
            with fits.open(raw) as hdul:
                if (int(hdul[0].header["TARGET"]) != int(target)
                        or hdul[0].header["FILTER"].lower() != filt
                        or hdul[0].header["GRATING"].lower() != grating):
                    raise ValueError("Product identity mismatch")
                table = normalized_table(hdul["EXTRACT5PIX1D"].data,
                                         hdul["EXTRACT5PIX1D"].columns)
            fit = marginal_fit(table, row["rest_a"], row["z"])
            compact = output.parent / f"b_heldout_{index:02d}.npz"
            np.savez_compressed(compact, **table)
            result = {**row, "fit": fit, "compact": str(compact)}
            result["log_ratio"] = (float(np.log(fit["flux_1e20"] / row["published_flux"]))
                                   if fit["flux_1e20"] > 0 else None)
            report["rows"].append(result)
        except Exception as exc:
            transfer["error"] = str(exc)
            report["stop"] = "Access/preflight/measurement failure; no retries or replacements"
            break
        finally:
            raw.unlink(missing_ok=True)
            transfer["raw_deleted"] = True
            transfer["completed_utc"] = now()
            output.write_text(json.dumps(report, indent=2) + "\n")
    y = np.array([r["log_ratio"] for r in report["rows"] if r["log_ratio"] is not None])
    if len(y) == 15:
        rng = np.random.default_rng(20261015)
        boot = rng.choice(y, (20000, len(y)), replace=True)
        report["summary"] = {
            "median_ratio": float(np.exp(np.median(y))),
            "median_ratio_ci": np.exp(np.quantile(np.median(boot, axis=1), [.025, .975])).tolist(),
            "sd": float(y.std(ddof=1)),
            "mad": float(np.median(abs(y - np.median(y)))),
            "sign_p": float(binomtest(int((y < 0).sum()), len(y)).pvalue),
        }
        indices = rng.integers(len(y), size=(20000, len(y)))
        snr = np.array([r["snr"] for r in frozen["rows"]])
        losses = []
        for power, law in enumerate(("inverse_snr", "inverse_snr_squared"), start=1):
            residual = y - np.array([r[law] for r in frozen["rows"]])
            sampled = residual[indices].mean(axis=1)
            design = np.column_stack((np.ones(len(y)), snr ** (-power)))
            coefficients = np.linalg.lstsq(design, y, rcond=None)[0]
            bootstrap = np.array([
                np.linalg.lstsq(design[ix], y[ix], rcond=None)[0] for ix in indices
            ])
            losses.append(residual**2)
            report["summary"][law] = {
                "sse": float(residual @ residual), "residual_mean": float(residual.mean()),
                "residual_mean_ci": np.quantile(sampled, [.025, .975]).tolist(),
                "refit_intercept": float(coefficients[0]),
                "refit_intercept_ci": np.quantile(bootstrap[:, 0], [.025, .975]).tolist(),
            }
        difference = losses[0] - losses[1]
        interval = np.quantile(difference[indices].mean(axis=1), [.025, .975])
        report["summary"]["paired_mean_squared_error_difference"] = float(difference.mean())
        report["summary"]["paired_difference_ci"] = interval.tolist()
        report["summary"]["decisive_preference"] = (
            "inverse_snr_squared" if interval[0] > 0 else
            "inverse_snr" if interval[1] < 0 else "unresolved"
        )
    else:
        report["verdict"] = "NOT_EVALUABLE: frozen minimum 15 usable paired log ratios unmet"
    output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prediction", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.prediction, args.output)
