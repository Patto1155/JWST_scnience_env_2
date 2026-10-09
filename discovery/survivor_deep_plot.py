"""Plot actual pinned stamps beside conditional multiband image-model diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
import numpy as np
from astropy.coordinates import SkyCoord

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from discovery.deep_reference_comparison import load_deep_cutout  # noqa: E402


def plot(input_dir: Path, report: Path, output: Path) -> None:
    result = json.loads(report.read_text())
    figure, axes = plt.subplots(3, 2, figsize=(10, 11), gridspec_kw={"width_ratios": [1, 2]})
    wavelengths = np.array([0.902, 1.154, 1.501, 1.989, 2.762, 3.568, 4.408])
    for index, source in enumerate(result["sources"]):
        bundle, _ = load_deep_cutout(input_dir / f"dja_{source['source_id']}_F444W.fits")
        x, y = bundle["wcs"].world_to_pixel(
            SkyCoord(source["ra_deg"], source["dec_deg"], unit="deg")
        )
        x, y = int(round(float(x))), int(round(float(y)))
        image = bundle["sci"][y - 20 : y + 21, x - 20 : x + 21]
        low, high = np.quantile(image, [0.05, 0.995])
        axes[index, 0].imshow(
            np.arcsinh((image - low) / (high - low) * 10),
            origin="lower",
            cmap="magma",
            extent=[-1.025, 1.025, -1.025, 1.025],
        )
        axes[index, 0].axhline(0, color="cyan", alpha=0.25)
        axes[index, 0].axvline(0, color="cyan", alpha=0.25)
        offset = source["competing_spatial_component"]["offset_from_selection_position_arcsec"]
        if offset is not None:
            axes[index, 0].plot(*offset, marker="+", color="cyan", ms=12)
        axes[index, 0].set_title(f"Source {source['source_id']}: actual F444W")
        axes[index, 0].set_xlabel("Grid offset (arcsec)")
        axes[index, 0].set_ylabel("Grid offset (arcsec)")
        flux = np.array([b["fixed_extended_fit"]["flux_njy"] for b in source["bands"]])
        noise = np.array([b["background_scaled_error_njy"] for b in source["bands"]])
        error = np.sqrt(noise**2 + (0.15 * flux) ** 2)
        ax = axes[index, 1]
        ax.errorbar(
            wavelengths,
            flux,
            error,
            fmt="o",
            color="black",
            capsize=3,
            label="Fixed spatial model; background + assumed 15% floor",
        )
        if offset is not None:
            companion = [b["fixed_extended_fit"]["companion_flux_njy"] for b in source["bands"]]
            ax.plot(wavelengths, companion, "s:", color="grey", label="Second spatial component")
        for family, style, color in [
            ("smooth_log_quadratic", "-", "tab:blue"),
            ("lyman_step_powerlaw", "--", "tab:red"),
            ("balmer4000_step_powerlaw", ":", "tab:green"),
        ]:
            model = source["phenomenological_continuum_sensitivity"][1]["families"][family]
            ax.plot(
                wavelengths,
                np.maximum(model["model_flux_njy"], 0.02),
                style,
                color=color,
                label=f"{family}: conditional chi2={model['chi2_conditional']:.1f}",
            )
        ax.set_yscale("log")
        ax.set_xlabel("Approximate passband pivot wavelength (micron)")
        ax.set_ylabel("Finite spatial-template flux (nJy)")
        ax.set_xticks(wavelengths, labels=result["bands"], rotation=40)
        ax.grid(alpha=0.2)
        ax.legend(fontsize=7)
    figure.suptitle("Deep GOODS hypotheses: observed images and conditional continuum diagnostics")
    figure.text(
        0.5,
        0.01,
        "Mosaics can contain selection exposures. Aligned modeled PSFs and Gaussian morphology "
        "are assumptions; source 98 remains spatially inadequate.\n"
        "Family parameters do not establish redshift. Error bars omit shape uncertainty. "
        "Each image has an independent asinh display scale.",
        ha="center",
        fontsize=8,
    )
    figure.tight_layout(rect=[0, 0.045, 1, 0.965])
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=150)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plot(args.input, args.report, args.output)


if __name__ == "__main__":
    main()
