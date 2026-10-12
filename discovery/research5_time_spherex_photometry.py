"""Exploratory narrow-channel SPHEREx photometry; no synthetic W1 by interpolation."""

import gzip
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from photutils.psf import ImagePSF

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_output"


def measure(path):
    receipt = json.loads(path.with_suffix(".receipt.json").read_text())
    body = gzip.decompress(path.read_bytes())
    if hashlib.sha256(body).hexdigest() != receipt["cutout_sha256"]:
        raise ValueError("Cutout input identity failed")
    with fits.open(io.BytesIO(body), checksum=True) as h:
        meta = receipt["metadata"]
        mjd = float(meta["t_min"])
        dt = (mjd - 57388) / 365.25
        ra = 57.64197830092 + 3.373 * dt / (3600000 * np.cos(np.deg2rad(35.58569174346)))
        dec = 35.58569174346 - 4.526 * dt / 3600000
        sky = WCS(h["IMAGE"].header, fobj=h).celestial
        x, y = sky.all_world2pix(ra, dec, 0)
        ep = h["EPSF"].data
        xorig = x + h["IMAGE"].header["ORIGX0"]
        yorig = y + h["IMAGE"].header["ORIGY0"]
        zone = int(np.argmin(np.hypot(ep["XCENTER"] - xorig, ep["YCENTER"] - yorig)))
        psf = ImagePSF(
            ep["EPSF"][zone], oversampling=(h["EPSF"].header["OVSMPY"], h["EPSF"].header["OVSMPX"])
        )
        image = h["IMAGE"].data.astype(float)
        variance = h["VARIANCE"].data.astype(float)
        flags = h["FLAGS"].data.astype(np.int64)
        yy, xx = np.indices(image.shape)
        kernel = psf.evaluate(xx, yy, 1, x, y)
        kernel = kernel / np.sum(kernel)
        benign = 0
        for key, value in h["FLAGS"].header.items():
            if key.startswith("MSKN") and value in ["SOURCE", "FULLSAMPLE"]:
                benign |= int(h["FLAGS"].header["MSKM" + key[4:]])
        mask = (
            np.isfinite(image)
            & np.isfinite(variance)
            & (variance > 0)
            & ((flags & ~benign) == 0)
            & (np.hypot(xx - x, yy - y) <= 4)
        )
        psf_good = float(np.sum(np.abs(kernel[mask])) / np.sum(np.abs(kernel)))
        edge_margin = float(min(x, y, image.shape[1] - 1 - x, image.shape[0] - 1 - y))
        # Source-local Jacobian including sky SIP distortion, radian^2/pixel.
        wx = sky.all_pix2world([[x + 0.5, y], [x - 0.5, y], [x, y + 0.5], [x, y - 0.5]], 0)
        dx = (
            np.array([(wx[0, 0] - wx[1, 0]) * np.cos(np.deg2rad(dec)), wx[0, 1] - wx[1, 1]])
            * np.pi
            / 180
        )
        dy = (
            np.array([(wx[2, 0] - wx[3, 0]) * np.cos(np.deg2rad(dec)), wx[2, 1] - wx[3, 1]])
            * np.pi
            / 180
        )
        unit = float(abs(np.linalg.det(np.stack([dx, dy]))) * 1e9)
        spectral = WCS(h["IMAGE"].header, fobj=h, key="W")
        # Spectral TAB WCS must bypass unrelated celestial SIP coefficients.
        wavelength, width = map(float, spectral.wcs_pix2world([[x, y]], 0)[0])
        fits_out = {}
        for mode in ["constant", "plane"]:
            cols = [kernel[mask], np.ones(np.sum(mask))]
            if mode == "plane":
                cols += [(xx - x)[mask], (yy - y)[mask]]
            design = np.stack(cols, axis=1)
            weight = 1 / variance[mask]
            information = design.T @ (weight[:, None] * design)
            if len(weight) <= len(cols) or np.linalg.matrix_rank(information) < len(cols):
                fits_out[mode] = {"eligible": False}
                continue
            covariance = np.linalg.inv(information)
            coef = covariance @ (design.T @ (weight * image[mask]))
            res = image[mask] - design @ coef
            chi2 = float(np.sum(weight * res**2) / (len(weight) - len(cols)))
            fits_out[mode] = {
                "flux_mjy": float(coef[0] * unit),
                "sigma_mjy": float(np.sqrt(covariance[0, 0] * max(1, chi2)) * unit),
                "reduced_chi2": chi2,
                "eligible": psf_good >= 0.8 and edge_margin >= 4,
                "n_pixels": len(weight),
            }
        return {
            "file": path.name,
            "mjd": mjd,
            "wavelength_um": wavelength,
            "channel_width_um": width,
            "xy_cutout": [float(x), float(y)],
            "psf_zone_within_trim": zone,
            "psf_original_zone": receipt.get("epsf_original_indices", list(range(len(ep))))[zone],
            "good_psf_fraction": psf_good,
            "edge_margin_pixels": edge_margin,
            "pixel_unit_mjy_per_mjysr": unit,
            "fits": fits_out,
            "interpretation": (
                "actual narrow-channel measurements; never direct WISEW1 "
                "magnitudes or independent visit replication"
            ),
        }


def main():
    rows = [measure(p) for p in sorted(OUT.glob("research5_time_spherex_[0-9][0-9][0-9].fits.gz"))]
    (OUT / "research5_time_spherex_photometry.json").write_text(
        json.dumps(rows, indent=2, allow_nan=False) + "\n"
    )
    for r in rows:
        print(r["file"], r["wavelength_um"], r["good_psf_fraction"], r["fits"])


if __name__ == "__main__":
    main()
