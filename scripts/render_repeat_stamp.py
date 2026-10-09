"""Render hash-verified native-band stamps around one repeat-tested proposal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import astropy.units as u
import matplotlib
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.nddata import Cutout2D
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales
from matplotlib.colors import AsinhNorm

from data_pipeline.original_images import verify_image

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("repeat_manifest", type=Path)
    parser.add_argument("original_manifest", type=Path)
    parser.add_argument("--source-id", type=int, default=1043)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    source = next(s for s in report["sources"] if s["source_id"] == args.source_id)
    products = json.loads(args.repeat_manifest.read_text())["images"]
    originals = json.loads(args.original_manifest.read_text())["images"]
    for band in ("F090W", "F200W"):
        products.append(
            next(
                p
                for p in originals
                if p["filter"] == band
                and p["target"] == "SMACS-J0723.3-7327"
                and "_nrca1_" in p["product_filename"]
            )
        )
    for product in products:
        verify_image(product["path"], product)
    for result, product in zip(report["images"], products[:2], strict=True):
        if result["sha256"] != product["sha256"]:
            raise ValueError("repeat report and image manifest hashes disagree")
    sky = SkyCoord(source["sky_center"]["ra"] * u.deg, source["sky_center"]["dec"] * u.deg)
    fig, axes = plt.subplots(1, 4, figsize=(12, 3.5))
    labels = ["F444W reference", "F444W distinct integration", "F090W", "F200W"]
    for ax, product, label in zip(axes, products, labels, strict=True):
        with fits.open(product["path"]) as hdul:
            cut = Cutout2D(hdul["SCI"].data, sky, 3 * u.arcsec, wcs=WCS(hdul["SCI"].header))
            values = cut.data[np.isfinite(cut.data)]
            norm = AsinhNorm(
                linear_width=max(np.percentile(values, 90) - np.percentile(values, 10), 0.01),
                vmin=np.percentile(values, 5),
                vmax=np.percentile(values, 99),
            )
            ax.imshow(cut.data, origin="lower", cmap="gray", norm=norm)
            x, y = cut.wcs.world_to_pixel(sky)
            scale = np.mean(proj_plane_pixel_scales(cut.wcs)) * 3600
            radius = report["aperture"]["aperture_radius_arcsec"] / scale
            ax.add_patch(plt.Circle((x, y), radius, fill=False, color="tab:red", lw=1.2))
            ax.set_title(label, fontsize=9)
            ax.set_xticks([])
            ax.set_yticks([])
    fig.suptitle(
        f"SMACS proposal {args.source_id}: fixed 0.1887 arcsec aperture; 3 arcsec native stamps",
        fontsize=10,
    )
    fig.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
