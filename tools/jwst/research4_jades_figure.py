"""Visualize frozen pilot availability and method dependence, without significance."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    root = Path("research_output")
    author = json.loads((root / "research4_jades_pilot.json").read_text())
    reviewer = json.loads((root / "research4_review_integration.json").read_text())
    oracle = {x["unique_id"]: x for x in reviewer["targets"]}
    fig, axes = plt.subplots(1, 2, figsize=(12, 7), gridspec_kw={"width_ratios": [1, 2.5]})
    colors = ["#236b9d", "#c46e28"]
    groups = ["lower_z", "interior_z"]
    positions = np.arange(2)
    a = [author["groups"][g]["valid"] for g in groups]
    b = [reviewer["group_summaries"][g + "_5pix_FLUX_0.0035"]["positive_covered_n"] for g in groups]
    for shift, values, color, label in zip(
        (-0.18, 0.18), (a, b), colors, ("Gaussian", "Independent box")
    ):
        axes[0].bar(positions + shift, values, 0.34, color=color, label=label)
        for p, value in zip(positions + shift, values):
            axes[0].text(p, value + 0.12, f"{value}/6", ha="center", fontsize=10)
    axes[0].axhline(4, ls="--", color="gray", lw=1)
    axes[0].text(-0.4, 4.14, "Frozen minimum", fontsize=9, color="#555555")
    axes[0].set_xticks(positions, ["Lower z", "Interior z"])
    axes[0].set_ylim(0, 6.6)
    axes[0].set_ylabel("Positive, covered primary D available")
    axes[0].set_title("Both methods fail lower-z gate", loc="left", fontsize=12)
    axes[0].legend(loc="upper left", fontsize=9)
    labels = []
    for index, row in enumerate(author["targets"]):
        labels.append(row["unique_id"].split("_")[-1])
        box = oracle[row["unique_id"]]["contrasts"]["5pix_FLUX_0.0035"]["D"]
        for offset, value, color, marker in zip(
            (-0.12, 0.12), (row["differential_log_ratio"], box), colors, ("o", "s")
        ):
            if value is None:
                axes[1].scatter(3.0, index + offset, marker="x", color=color, alpha=0.6)
            else:
                axes[1].scatter(value, index + offset, marker=marker, color=color, s=40)
    axes[1].axvline(0, color="gray", lw=1)
    axes[1].axhline(5.5, color="gray", ls="--", lw=1)
    axes[1].set_yticks(range(12), labels)
    axes[1].invert_yaxis()
    axes[1].set_xlim(-2.9, 3.35)
    axes[1].set_xlabel("D = ln(Hβ235/Hβ140) − ln([O III]235/[O III]140)")
    axes[1].set_ylabel("Frozen NIRSpec target ID; upper six = lower z")
    axes[1].set_title("Conditional estimates depend on method", loc="left", fontsize=12)
    axes[1].text(
        0.94,
        0.98,
        "× unavailable",
        ha="center",
        va="top",
        transform=axes[1].transAxes,
        fontsize=8,
        color="#555555",
    )
    fig.suptitle("GOODS-S paired-grating pilot: stop; no group inference", fontsize=15)
    fig.text(
        0.08,
        0.03,
        "5-pixel, 3-nod primary; independent boxes ±0.0035 μm. "
        "Dots use shared photons; no calibrated uncertainty or population claim.",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.055, 1, 0.95))
    fig.savefig(root / "research4_jades_methods.png", dpi=170)
    fig.savefig(root / "research4_jades_methods.pdf")
    plt.close(fig)


if __name__ == "__main__":
    main()
