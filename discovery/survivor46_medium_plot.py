"""Actual source46 F410 pixel/model/residual and conditional band comparison."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from astropy.io.votable import parse_single_table
from matplotlib.colors import AsinhNorm

from discovery.deep_reference_comparison import load_deep_cutout
from discovery.psf_noise import overlap_resample, verified_template
from discovery.survivor_deep_model import image_template, stamp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("input", "deep", "report", "photometry", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    source = next(
        s for s in json.loads(args.photometry.read_text())["sources"] if s["source_id"] == 46
    )
    bundle, _ = load_deep_cutout(args.input / "dja_46_F410M.fits")
    data, error, scale, phase = stamp(bundle, source["ra_deg"], source["dec_deg"], 40)
    raw, p = verified_template(args.input / "f410ma_v5.0_mpsf.fits", "F410M")
    psf = overlap_resample(raw, p["input_scale_arcsec"], scale, 81)
    params = np.array(report["frozen_f444_morphology_in_medium_pixel_phase"])
    fitted = next(
        x
        for x in report["signed_fixed_models"]
        if x["radius_arcsec"] == 0.65 and x["modeled_psf_rotation_deg"] == 0
    )
    yy, xx = np.mgrid[:81, :81] - 40
    model = (
        fitted["flux_njy"] * image_template(psf, scale, params) + fitted["background_njy_per_pixel"]
    )
    gx, gy = fitted["background_gradient_njy_per_pixel_per_arcsec"]
    model += scale * (gx * xx + gy * yy)
    fig = plt.figure(figsize=(10, 6.5), layout="constrained")
    grid = fig.add_gridspec(2, 3)
    crop = np.s_[20:61, 20:61]
    norm = AsinhNorm(linear_width=1, vmin=-1, vmax=max(data[crop].max(), model[crop].max()))
    for i, (label, array) in enumerate(
        [
            ("Actual F410M", data),
            ("Finite modeled PSF + plane", model),
            ("Residual (nJy/pixel)", data - model),
        ]
    ):
        ax = fig.add_subplot(grid[0, i])
        image = ax.imshow(
            array[crop],
            origin="lower",
            extent=np.array([-20.5, 20.5, -20.5, 20.5]) * scale,
            norm=norm if i < 2 else None,
            cmap="magma" if i < 2 else "RdBu_r",
            vmin=-5 if i == 2 else None,
            vmax=5 if i == 2 else None,
        )
        ax.set_title(label, fontsize=11)
        ax.set_xlabel("Arcsec from rounded center")
        colorbar = fig.colorbar(image, ax=ax, shrink=0.8)
        if i < 2:
            colorbar.set_ticks([-1, 0, 1, 10])
            colorbar.set_ticklabels(["−1", "0", "1", "10"])
    ax = fig.add_subplot(grid[1, :])
    pivots = []
    flux = []
    for band in source["bands"]:
        name = band["filter"]
        table = parse_single_table(args.deep / f"svo_{name}.xml")
        params = {p.name: p.value for p in table.params}
        pivots.append(float(params["WavelengthPivot"]) / 10000)
        flux.append(band["fixed_extended_fit"]["flux_njy"])
    ax.errorbar(
        pivots,
        flux,
        yerr=np.sqrt(
            np.diag(
                np.array(
                    source["phenomenological_continuum_sensitivity"][1]["flux_covariance_njy2"]
                )
            )
        ),
        fmt="o",
        label="Frozen seven bands; background errors + assumed floors",
    )
    table = parse_single_table(args.input / "svo_F410M.xml")
    params = {p.name: p.value for p in table.params}
    pivot = float(params["WavelengthPivot"]) / 10000
    ax.errorbar(
        [pivot],
        [report["fiducial_f410_njy"]],
        yerr=[
            np.sqrt(
                report["fiducial_background_scaled_diagonal_error_njy"] ** 2
                + report["fiducial_f410_njy"] ** 2 * (0.15**2 + 0.03**2)
            )
        ],
        fmt="s",
        color="crimson",
        label="New F410M; background error + assumed floors",
    )
    ax.set_yscale("log")
    ax.set_xlabel("Nominal filter pivot wavelength (micron)")
    ax.set_ylabel("Conditional template flux (nJy)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.2)
    ax.set_title(
        "Adjacent medium band is bright; PSF residuals prevent precision classification",
        fontsize=11,
    )
    fig.savefig(args.output, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
