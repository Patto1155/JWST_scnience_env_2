"""Exploratory frozen CLASS cohort, Fe VII 6087 only; second line held out."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
from astropy.time import Time

from discovery.research5_spectral_pilot import CENTERS, load_verified, measure


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    folder = root / "research_output" / "research5_spectral"
    manifest = json.loads((folder / "cohort_frozen_manifest.json").read_text())
    records = {}
    receipts = [
        json.loads((folder / "J111855_spectra_receipt.json").read_text()),
        *json.loads((folder / "cohort_spectra_receipts.json").read_text()),
    ]
    for receipt in receipts:
        path = folder / receipt.get("filename", "J111855_spectra.json.gz")
        for row in load_verified(path, receipt)[1:]:
            records[row["sparcl_id"]] = row
    results = []
    for target in manifest["selected"]:
        baseline_mjd = int(target["baseline"]["MJD"])
        sdss_meta = [r for r in target["records"] if r["_dr"] == "SDSS-DR17"]
        baseline = min(
            sdss_meta,
            key=lambda r: abs(Time(r["dateobs_center"].replace("Z", "")).mjd - baseline_mjd),
        )
        redshift = baseline["redshift"]
        product_results = []
        for metadata in target["records"]:
            row = records[metadata["sparcl_id"]]
            variants = []
            for width in (8.0, 12.0, 16.0):
                for sideband in ((20.0, 40.0), (30.0, 60.0)):
                    variants.append(
                        {
                            "halfwidth": width,
                            "sideband": sideband,
                            "measurements": {
                                name: measure(
                                    row,
                                    center,
                                    width,
                                    sideband,
                                    advisory_sdss=metadata["_dr"] == "SDSS-DR17",
                                    redshift=redshift,
                                )
                                for name, center in CENTERS.items()
                            },
                        }
                    )
            product_results.append({"metadata": metadata, "variants": variants})
        base = next(
            r for r in product_results if r["metadata"]["sparcl_id"] == baseline["sparcl_id"]
        )
        desi = sorted(
            (r for r in product_results if r["metadata"]["_dr"] == "DESI-DR1"),
            key=lambda r: r["metadata"]["dateobs_center"],
        )
        pairs = []
        for other in desi:
            a = base["variants"][0]["measurements"]["FeVII6087"]
            b = other["variants"][0]["measurements"]["FeVII6087"]
            if a["status"] != "measured" or b["status"] != "measured":
                pairs.append({"desi_id": other["metadata"]["sparcl_id"], "status": "unavailable"})
                continue
            fa, sa = a["flux_1e17_erg_cm2_s"], a["error_1e17_erg_cm2_s"]
            fb, sb = b["flux_1e17_erg_cm2_s"], b["error_1e17_erg_cm2_s"]
            pairs.append(
                {
                    "desi_id": other["metadata"]["sparcl_id"],
                    "status": "measured",
                    "baseline_snr": a["snr"],
                    "desi_snr": b["snr"],
                    "raw_decline_sigma": (fa - fb) / np.hypot(sa, sb),
                    "raw_decline_lower_bound": fa / b["upper_bound_3sigma"],
                }
            )
        results.append(
            {
                "desi_targetid": target["desi_targetid"],
                "baseline": target["baseline"],
                "baseline_uuid": baseline["sparcl_id"],
                "systemic_z": redshift,
                "product_measurements": product_results,
                "raw_pairs": pairs,
            }
        )
    output = {
        "label": "exploratory discovery-line screen; raw ratios not aperture normalized",
        "n_objects": len(results),
        "heldout_5720": "unmeasured",
        "results": results,
    }
    destination = folder / "cohort_discovery_measurements.json.gz"
    with gzip.open(destination, "wt") as stream:
        json.dump(output, stream, indent=2, allow_nan=False)
    for row in results:
        p = row["raw_pairs"][0]
        if p["status"] == "measured" and p["baseline_snr"] >= 5:
            print(
                row["desi_targetid"],
                row["baseline"]["RAJ2000"],
                row["baseline"]["DEJ2000"],
                "baselineSNR",
                round(p["baseline_snr"], 2),
                "raw_decline_sigma",
                round(p["raw_decline_sigma"], 2),
                "factor_lower",
                round(p["raw_decline_lower_bound"], 2),
            )
    print("objects", len(results), "output", destination)


if __name__ == "__main__":
    main()
