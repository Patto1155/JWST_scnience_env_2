"""Show observed candidate variability and independent optical constraint."""

import csv
import io
import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from astropy.time import Time

from discovery.research5_time_followup import quality_rows
from discovery.research5_time_scout import verified_bytes

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_output"


def year(mjd):
    return Time(mjd, format="mjd").decimalyear


def main():
    d = json.loads((OUT / "research5_time_ir_exploration.json").read_text())
    f = json.loads((OUT / "research5_time_optical_freeze.json").read_text())["primary"]
    res = json.loads((OUT / "research5_time_optical_results.json").read_text())["035034"]
    t = d["research5_time_035034_gator.tbl.gz"]["visits"]
    c = d["research5_time_035030_control_gator.tbl.gz"]["visits"]
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    fig, axs = plt.subplots(
        3,
        1,
        figsize=(10.5, 9),
        sharex=True,
        constrained_layout=True,
        gridspec_kw={"height_ratios": [1.15, 0.8, 1.1]},
    )
    for band, color in [("w1", "#b3403f"), ("w2", "#874fa1")]:
        axs[0].plot(
            year([r["mjd"] for r in t]),
            [r[band] for r in t],
            "o-",
            color=color,
            label="NEOWISE " + band.upper(),
        )
    axs[0].invert_yaxis()
    axs[0].set_ylabel("Source magnitude")
    axs[0].legend(loc="upper right", ncol=2)
    axs[0].set_title(
        "DDE 54 / VarWISE J035034.07+353508.5: infrared recurrence and optical constraint",
        loc="left",
        weight="bold",
        fontsize=13,
    )
    for m in [56898.7, 58356.0, 59818.6]:
        axs[0].axvline(year(m), ls=":", lw=1, color=".4")
    axs[0].text(
        0.015,
        0.94,
        (
            "Approximate 1460-day spacing is exploratory; "
            "catalog 387.5-day period is flagged as suspect."
        ),
        transform=axs[0].transAxes,
        fontsize=9,
    )
    for band, color in [("w1", "#426da4"), ("w2", "#4b9b7e")]:
        axs[1].plot(
            year([r["mjd"] for r in c]),
            [r[band] for r in c],
            "o-",
            color=color,
            label="Local comparison " + band.upper(),
        )
    axs[1].set_ylim(13.16, 12.82)
    axs[1].set_ylabel("Comparison magnitude")
    axs[1].legend(loc="upper right", ncol=2, fontsize=9)
    axs[1].text(
        0.015,
        0.08,
        "AllWISE J035030.00+353453.7, 52 arcsec away; W1 visit range 0.05 mag.",
        transform=axs[1].transAxes,
        fontsize=9,
    )
    rr = list(csv.DictReader(io.StringIO(verified_bytes("035034_ztf.csv").decode())))
    gaia = list(csv.DictReader(io.StringIO(verified_bytes("035034_gaia_dr3_source.csv").decode())))[
        0
    ]
    z = [r for r in quality_rows(rr, gaia) if r["oid"] == res["selected_oid"]]
    axs[2].scatter(
        year([float(r["mjd"]) for r in z]),
        [float(r["mag"]) for r in z],
        s=5,
        color=".6",
        alpha=0.35,
        label="ZTF r single exposures",
    )
    bins = {}
    for r in z:
        bins.setdefault(int(np.floor(float(r["mjd"]) / 30)), []).append(
            (float(r["mjd"]), float(r["mag"]))
        )
    bz = np.array(
        [(np.median([v[0] for v in a]), np.median([v[1] for v in a])) for a in bins.values()]
    )
    axs[2].plot(year(bz[:, 0]), bz[:, 1], "o", ms=4, color="#2b527c", label="30-day medians")
    for label, windows, color in [
        ("IR faint windows", f["ir_faint_windows_mjd"], "#df9c90"),
        ("IR bright windows", f["ir_bright_windows_mjd"], "#91bfd1"),
    ]:
        for i, (lo, hi) in enumerate(windows):
            axs[2].axvspan(
                year(lo), year(hi), alpha=0.22, color=color, label=label if i == 0 else None
            )
    axs[2].set_ylim(19.75, 17.95)
    axs[2].set_ylabel("ZTF r magnitude")
    axs[2].set_xlabel("Year")
    axs[2].legend(loc="lower left", ncol=2, fontsize=9)
    axs[2].text(
        0.015,
        0.94,
        "Faint − bright r: −0.049 mag; conditional 30-day bootstrap 95% [−0.153, +0.094].",
        transform=axs[2].transAxes,
        fontsize=9,
    )
    for ax in axs:
        ax.grid(alpha=0.16)
    fig.savefig(OUT / "research5_time_primary.png", dpi=180)
    fig.savefig(OUT / "research5_time_primary.pdf")


if __name__ == "__main__":
    main()
