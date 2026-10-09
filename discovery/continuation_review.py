"""Independent pixel, covariance and denominator audits for continuation products.

No continuation measurement module is imported. The direct pixel oracle uses
local celestial Jacobians instead of the production spherical-polygon operator.
Its aperture/background variants are model sensitivity, not extra observations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS

PINNED_REPEAT = {
    "jw02736001001_02105_00004_nrcalong_i2d.fits": "0226bb8a980aa2770bb6e57e0f91812bbbe247358f0ae80611a788a5827e1b92",
    "jw02736001001_02105_00003_nrcalong_i2d.fits": "d06747dc62974e2e008b0a6e1f30c4864b1527e64218e73e210e97582e8aff8f",
}
GROUPS = ("NIV", "CIV", "HeII_OIII", "NIII", "CIII")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def direct_pixels(path: Path, position: dict, radius: float, inner: float, outer: float) -> dict:
    """Independent tangent-Jacobian Jy integration over actual spherical masks."""
    with fits.open(path) as hdul:
        science = hdul["SCI"].data
        error = hdul["ERR"].data
        weight = hdul["WHT"].data
        if hdul["SCI"].header["BUNIT"] != "MJy/sr":
            raise ValueError("this independent oracle requires calibrated MJy/sr")
        wcs = WCS(hdul["SCI"].header).celestial
        center = SkyCoord(position["ra"], position["dec"], unit="deg")
        cx, cy = wcs.world_to_pixel(center)
        xx, yy = np.meshgrid(
            np.arange(int(cx) - 15, int(cx) + 16), np.arange(int(cy) - 15, int(cy) + 16)
        )
        coords = wcs.pixel_to_world(xx, yy)
        distance = coords.separation(center).arcsec
        valid = (
            np.isfinite(science[yy, xx])
            & np.isfinite(error[yy, xx])
            & (error[yy, xx] > 0)
            & (weight[yy, xx] > 0)
        )
        aperture = (distance <= radius) & valid
        annulus = (distance >= inner) & (distance <= outer) & valid
        # Independent finite celestial Jacobian around each pixel centre.
        xm = coords.spherical_offsets_to(wcs.pixel_to_world(xx - 0.5, yy))
        xp = coords.spherical_offsets_to(wcs.pixel_to_world(xx + 0.5, yy))
        ym = coords.spherical_offsets_to(wcs.pixel_to_world(xx, yy - 0.5))
        yp = coords.spherical_offsets_to(wcs.pixel_to_world(xx, yy + 0.5))
        dx = [xp[i].rad - xm[i].rad for i in (0, 1)]
        dy = [yp[i].rad - ym[i].rad for i in (0, 1)]
        jy = 1e6 * np.abs(dx[0] * dy[1] - dx[1] * dy[0])
        values, errors = science[yy, xx], error[yy, xx]
        bg = float(np.mean(values[annulus]))
        flux = float(np.sum((values[aperture] - bg) * jy[aperture]))
        variance = (
            np.sum((errors[aperture] * jy[aperture]) ** 2)
            + np.sum(jy[aperture]) ** 2 * np.sum(errors[annulus] ** 2) / annulus.sum() ** 2
        )
        east, north = center.spherical_offsets_to(coords)
        sector_fluxes = []
        for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
            sector = annulus & (east.arcsec * sx >= 0) & (north.arcsec * sy >= 0)
            sector_bg = float(np.mean(values[sector]))
            sector_fluxes.append(float(np.sum((values[aperture] - sector_bg) * jy[aperture])))
        return {
            "radius_arcsec": radius,
            "flux_jy": flux,
            "diagonal_error_jy": float(np.sqrt(variance)),
            "aperture_pixels": int(aperture.sum()),
            "annulus_pixels": int(annulus.sum()),
            "background_sector_fluxes_jy": sector_fluxes,
        }


def repeat_oracle(manifest: dict, repeat: dict) -> dict:
    row = next(r for r in repeat["sources"] if r["source_id"] == 1043)
    position = row["sky_center"]
    radii = (0.10, 0.15, 0.18873115150197345, 0.25, 0.30)
    images = []
    for product in manifest["images"]:
        path = Path(product["path"])
        if digest(path) != PINNED_REPEAT.get(path.name):
            raise ValueError("actual repeat bytes disagree with independent reviewer pins")
        records = [
            direct_pixels(path, position, r, 0.3774623030039469, 0.6291038383399116) for r in radii
        ]
        images.append({"filename": path.name, "sha256": digest(path), "records": records})
    errors = [
        abs(image["records"][2]["flux_jy"] / row[key]["background_subtracted_flux_jy"] - 1)
        for image, key in zip(images, ("reference", "repeat"), strict=True)
    ]
    if max(errors) > 2e-5:
        raise ValueError("independent Jy oracle and recorded spherical-polygon flux disagree")
    ratios = [
        images[1]["records"][i]["flux_jy"] / images[0]["records"][i]["flux_jy"]
        for i in range(len(radii))
    ]
    return {
        "source_id": 1043,
        "images": images,
        "local_Jacobian_vs_polygon_max_relative_error": max(errors),
        "repeat_reference_ratio_by_radius": ratios,
        "background_sectors_order": ["NE", "NW", "SW", "SE"],
        "scope": "Fixed-sky aperture/background sensitivity. Same photons; no identity, deblend or independent likelihood.",
    }


def independent_tail_audit(full: list) -> list:
    output = []
    for image in full:
        for aperture in image["blanks"]["apertures"]:
            rows = aperture["measurements"]
            raw = np.array([r["net_flux"] / r["diagonal_sigma"] for r in rows])
            folds = np.array([sum(map(int, r["spatial_block"].split(":"))) % 2 for r in rows])
            z = np.empty(len(raw))
            for fold in (0, 1):
                train = raw[folds != fold]
                location = np.median(train)
                scale = 1.4826 * np.median(np.abs(train - location))
                z[folds == fold] = (raw[folds == fold] - location) / scale
            counts = [int((z >= 5).sum()), int((z <= -5).sum())]
            saved = [t["events"] for t in aperture["heldout_tails"]["tails"] if t["threshold"] == 5]
            if counts != saved:
                raise ValueError("held-out signed tail counts disagree")
            ap = np.array([r["aperture_flux"] for r in rows])
            background = np.array([r["background_contribution"] for r in rows])
            observed = float(np.var(ap - background, ddof=1))
            matrix = np.cov(ap, background)
            identity = float(matrix[0, 0] + matrix[1, 1] - 2 * matrix[0, 1])
            output.append(
                {
                    "band": image["band"],
                    "mask": image["mask_label"],
                    "radius_arcsec": aperture["radius_arcsec"],
                    "n": len(rows),
                    "signed_5sigma_counts": counts,
                    "covariance_identity_relative_error": abs(identity / observed - 1),
                    "zero_event_two_sided95_upper_independent_assumption": 1
                    - 0.025 ** (1 / len(rows)),
                }
            )
    return output


def fieller_oracle(n: float, d: float, vn: float, vd: float, cov: float) -> list:
    z2 = 1.95996398454**2
    coefficients = [d * d - z2 * vd, -2 * n * d + 2 * z2 * cov, n * n - z2 * vn]
    roots = np.sort(np.roots(coefficients))
    if coefficients[0] <= 0 or not np.isreal(roots).all():
        raise ValueError("this independent numeric oracle is only for observed bounded cases")
    return roots.real.tolist()


def ionic_oracle(spectrum: dict, grid: dict) -> list:
    cell = next(
        r
        for r in grid["records"]
        if r["temperature_K"] == 20000 and r["electron_density_cm3"] == 1000
    )
    epsilon = cell["emissivity_erg_cm3_s"]
    output = []
    for fit in (spectrum["nominal_reference_fit"], spectrum["point_source_scenarios"][0]):
        flux = np.array([fit["lines"][k]["flux"] for k in GROUPS])
        covariance = np.array(fit["line_covariance"])
        a = np.array([1 / epsilon[k] if k in ("NIV", "NIII") else 0 for k in GROUPS])
        b = np.array([1 / epsilon[k] if k in ("CIV", "CIII") else 0 for k in GROUPS])
        op = np.vstack((a, b)) * epsilon["CIII"]
        num, den = op @ flux
        full = op @ covariance @ op.T
        diagonal = op @ np.diag(np.diag(covariance)) @ op.T
        output.append(
            {
                "ionic_ratio": float(num / den),
                "full_covariance_95": fieller_oracle(num, den, full[0, 0], full[1, 1], full[0, 1]),
                "incorrect_independent_lines_sensitivity_95": fieller_oracle(
                    num, den, diagonal[0, 0], diagonal[1, 1], diagonal[0, 1]
                ),
                "scaled_N_C_covariance": full.tolist(),
                "elemental_abundance_identified": False,
            }
        )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat-manifest", type=Path, required=True)
    parser.add_argument("--repeat-result", type=Path, required=True)
    parser.add_argument("--blank-samples", type=Path, required=True)
    parser.add_argument("--spectrum", type=Path, required=True)
    parser.add_argument("--atomic-grid", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = {k: v for k, v in vars(args).items() if k != "output"}
    data = {k: json.loads(v.read_text()) for k, v in paths.items()}
    result = {
        "schema_version": 1,
        "inputs_sha256": {k: digest(v) for k, v in paths.items()},
        "source1043_independent_pixel_oracle": repeat_oracle(
            data["repeat_manifest"], data["repeat_result"]
        ),
        "independent_tail_and_covariance_audit": independent_tail_audit(data["blank_samples"]),
        "independent_ionic_covariance_audit": ionic_oracle(data["spectrum"], data["atomic_grid"]),
    }
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
