import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import argparse

import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
p = args.output
r = {
    k.removeprefix("7496_"): v
    for k, v in json.loads((p / "jades_balmer_7496_fits.json").read_text())["results"].items()
}
windows = np.load(p / "jades_balmer_7496_windows.npz")


def read_window(key):
    return {x: windows[f"{key}_{x}"] for x in ("wave", "flux", "error", "model")}


fig, ax = plt.subplots(1, 3, figsize=(13, 4.3), layout="constrained")
for config, color, label in [
    ("f070lp-g140m", "#3366bb", "G140M: Hβ away from edge"),
    ("f170lp-g235m", "#d95c30", "G235M: Hβ at blue edge"),
]:
    x = read_window(f"7496_{config}_5pix_FLUX_Hb")
    ax[0].errorbar(x["wave"], x["flux"] * 10, x["error"] * 10, fmt=".", color=color, alpha=0.65)
    ax[0].plot(x["wave"], x["model"] * 10, color=color, label=label)
ax[0].axvline(1.69525, color="gray", ls=":", label="G235M finite data begins")
ax[0].set(
    xlim=(1.692, 1.706),
    xlabel="Observed wavelength (µm)",
    ylabel="Flux density (10⁻²¹ erg s⁻¹ cm⁻² Å⁻¹)",
    title="Released grating configurations disagree",
)
ax[0].legend(fontsize=8, loc="upper right")
x = read_window("7496_f170lp-g235m_5pix_FLUX_Ha")
ax[1].errorbar(x["wave"], x["flux"] * 10, x["error"] * 10, fmt=".", color="#d95c30")
ax[1].plot(x["wave"], x["model"] * 10, color="black")
ax[1].set(xlabel="Observed wavelength (µm)", title="Joint Hα + [N II] fit", xlim=(2.28, 2.31))
ha = r["f170lp-g235m_5pix_FLUX_Ha"]
points = []
for key, label in [
    ("f170lp-g235m_5pix_FLUX_Hb", "Own fit: G235M Hβ"),
    ("f070lp-g140m_5pix_FLUX_Hb", "Own fit: G140M Hβ"),
]:
    hb = r[key]
    ratio = ha["flux_1e20"] / hb["flux_1e20"]
    err = ratio * np.hypot(
        ha["diagonal_err_1e20"] / ha["flux_1e20"], hb["diagonal_err_1e20"] / hb["flux_1e20"]
    )
    points.append((label, ratio, err))
points += [
    (
        "Catalog: G235M 5pix",
        1.8532404923688615,
        1.8532404923688615 * np.hypot(8.112545198 / 657.257608, 15.45028251 / 354.653166),
    ),
    (
        "Catalog: PRISM blend",
        770.5969297038731 / 235.8186836159318,
        (770.5969297038731 / 235.8186836159318)
        * np.hypot(6.021754475175586 / 770.5969297038731, 9.499390607224024 / 235.8186836159318),
    ),
]
for i, (label, value, error) in enumerate(points):
    ax[2].errorbar(value, i, xerr=error, fmt="o", color="black")
ax[2].axvspan(2.65, 2.86, alpha=0.12, color="green")
ax[2].set(
    yticks=range(len(points)),
    yticklabels=[x[0] for x in points],
    xlabel="Hα/Hβ (PRISM includes [N II])",
    title="Physical anomaly fails configuration test",
    xlim=(1.4, 3.7),
)
ax[2].tick_params(axis="y", labelsize=8)
fig.suptitle(
    "JADES GOODS-S 7496, z = 2.493: released-spectra remeasurement rejects a catalog lead",
    fontsize=12,
)
fig.text(
    0.5,
    -0.03,
    (
        "Own fits use released coadds and diagonal reported errors; no calibration covariance. "
        "Aperture/nod variants share photons. Green band is a screening guide."
    ),
    ha="center",
    fontsize=8,
)
fig.savefig(p / "jades_balmer_7496_diagnostic.png", dpi=180, bbox_inches="tight")
fig.savefig(p / "jades_balmer_7496_diagnostic.pdf", bbox_inches="tight")
