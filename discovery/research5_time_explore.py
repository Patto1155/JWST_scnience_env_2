"""Exploratory per-visit NEOWISE summaries; no optical outcomes."""

import json
from io import BytesIO
from pathlib import Path

import numpy as np
from astropy.table import Table

from discovery.research5_time_scout import verified_bytes

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_output"


def main():
    results = {}
    for p in sorted(OUT.glob("research5_time_*_gator.tbl.gz")):
        t = Table.read(
            BytesIO(verified_bytes(p.name.removeprefix("research5_time_").removesuffix(".gz"))),
            format="ascii.ipac",
        )
        flags = np.asarray(t["cc_flags"]).astype(str)
        q = np.asarray(t["qual_frame"])
        mask = (
            (np.char.startswith(flags, "00"))
            & (q > 0)
            & (~np.ma.getmaskarray(t["w1mpro"]))
            & (~np.ma.getmaskarray(t["w2mpro"]))
        )
        mask &= (np.ma.filled(t["w1sigmpro"], 999) < 0.15) & (
            np.ma.filled(t["w2sigmpro"], 999) < 0.15
        )
        mask &= (np.ma.filled(t["w1rchi2"], 999) < 5) & (np.ma.filled(t["w2rchi2"], 999) < 5)
        for key in ["w1mpro", "w2mpro", "mjd", "ra", "dec"]:
            mask &= np.isfinite(np.ma.filled(t[key], np.nan))
        mask &= (np.ma.filled(t["w1sigmpro"], 0) > 0) & (np.ma.filled(t["w2sigmpro"], 0) > 0)
        a = t[mask]
        a.sort("mjd")
        ix = np.r_[0, np.flatnonzero(np.diff(a["mjd"]) > 30) + 1, len(a)]
        visits = []
        for lo, hi in zip(ix[:-1], ix[1:], strict=True):
            v = a[lo:hi]
            if len(v) < 4:
                continue
            w1 = np.asarray(v["w1mpro"])
            w2 = np.asarray(v["w2mpro"])
            visits.append(
                {
                    "mjd": float(np.median(v["mjd"])),
                    "n": len(v),
                    "w1": float(np.median(w1)),
                    "w2": float(np.median(w2)),
                    "color": float(np.median(w1 - w2)),
                    "ra": float(np.median(v["ra"])),
                    "dec": float(np.median(v["dec"])),
                }
            )
        results[p.name] = {"raw_rows": len(t), "good_rows": len(a), "visits": visits}
    (OUT / "research5_time_ir_exploration.json").write_text(
        json.dumps(results, indent=2, allow_nan=False) + "\n"
    )
    for k, v in results.items():
        print(k, "raw/good=", v["raw_rows"], v["good_rows"])
        for row in v["visits"]:
            print(row)


if __name__ == "__main__":
    main()
