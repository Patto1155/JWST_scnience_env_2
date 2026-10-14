"""Metered acquisition for the prospectively frozen GS population half."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import astropy.units as u
import numpy as np
import requests
from astropy.io import fits

from data_pipeline.calibrated_population import marginal_fit, pull_summary
from data_pipeline.session_known_answer import normalized_table


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(draw: Path, half: str, output: Path, used: int, freeze: str) -> dict:
    selected = json.loads(draw.read_text())
    receipts, results = [], []
    output.parent.mkdir(parents=True, exist_ok=True)
    training_ids = {r["unique_id"] for r in selected["training"]}
    report = {
        "freeze_commit": freeze,
        "half": half,
        "starting_bytes": used,
        "receipts": receipts,
        "results": results,
        "raw_calibration": "UNMET",
        "field": selected.get("field", "GS"),
    }
    for n, row in enumerate(selected[half]):
        entry = dict(row)
        results.append(entry)
        if half == "heldout" and row["unique_id"] in training_ids:
            entry["error"] = "Source reused across halves; frozen exclusion"
            continue
        tier, target = row["unique_id"].rsplit("_", 1)
        grating, filt = row["configuration"].split("_")
        config = f"{filt}-{grating}"
        name = f"hlsp_jades_jwst_nirspec_{tier}-{int(target):08d}_{config}_v2.0_x1d.fits"
        field_folder = "goods-n" if tier.startswith("goods-n-") else "goods-s"
        url = f"https://archive.stsci.edu/hlsps/jades/dr4/{field_folder}/spectra/{config}/{tier}/{name}"
        r = {"url": url, "started_utc": now(), "bytes": 0, "head_body_bytes": 0}
        receipts.append(r)
        path = Path("/tmp") / ("b_cal_" + name)
        try:
            h = requests.head(url, timeout=(8, 12))
            r["head_status"] = h.status_code
            h.raise_for_status()
            size = int(h.headers["Content-Length"])
            r["reserved_bytes"] = size
            r["disk_free_bytes"] = shutil.disk_usage("/tmp").free
            if used + size > 300_000_000 or r["disk_free_bytes"] - size < 5_000_000_000:
                raise ValueError("Budget/disk preflight failed")
            with requests.get(url, stream=True, timeout=(8, 20)) as response:
                r["status"] = response.status_code
                with path.open("wb") as f:
                    for chunk in response.iter_content(65536):
                        r["bytes"] += len(chunk)
                        used += len(chunk)
                        if r["bytes"] > size:
                            raise ValueError("Response exceeds reservation; received bytes charged")
                        f.write(chunk)
                response.raise_for_status()
            r["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            with fits.open(path) as hdul:
                if (
                    int(hdul[0].header["TARGET"]) != int(target)
                    or hdul[0].header["FILTER"].lower() != filt
                    or hdul[0].header["GRATING"].lower() != grating
                ):
                    raise ValueError("Header target/configuration mismatch")
                table = normalized_table(hdul["EXTRACT5PIX1D"].data, hdul["EXTRACT5PIX1D"].columns)
            fit = marginal_fit(table, row["rest_a"], row["z"])
            entry["fit"] = fit
            factor = (u.Unit(row["unit"]) / (1e-20 * u.erg / u.s / u.cm**2)).to(
                u.dimensionless_unscaled
            )
            entry["pull"] = float(
                (fit["flux_1e20"] - row["published_flux"] * factor)
                / np.hypot(fit["error_1e20"], row["published_error"] * factor)
            )
            compact = output.parent / f"{output.stem}_{n:02d}_spectrum.npz"
            np.savez_compressed(compact, **table)
            entry["compact"] = str(compact)
        except Exception as exc:
            entry["error"] = repr(exc)
            r["error"] = repr(exc)
        finally:
            path.unlink(missing_ok=True)
            r["completed_utc"] = now()
            r["raw_deleted"] = True
            report["total_bytes"] = used
            report["summary"] = pull_summary([x["pull"] for x in results if "pull" in x])
            output.write_text(json.dumps(report, indent=2) + "\n")
            print(half, n + 1, "OK" if "pull" in entry else entry.get("error"), flush=True)
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--draw", type=Path, required=True)
    p.add_argument("--half", choices=["training", "heldout"], required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--used", type=int, required=True)
    p.add_argument("--freeze", required=True)
    args = p.parse_args()
    run(args.draw, args.half, args.output, args.used, args.freeze)


if __name__ == "__main__":
    main()
