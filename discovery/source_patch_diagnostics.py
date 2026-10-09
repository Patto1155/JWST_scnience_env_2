"""Local point-template/background dissection of the persistent SMACS 1043 patch.

Finite JADES PSFs, background families and signed linear amplitudes are
conditional local models. Residual-cluster intervals do not calibrate an
astrophysical flux posterior, morphology, source identity or photometric redshift.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import astropy.units as u
from astropy.coordinates import SkyCoord

from discovery.empirical_imaging_controls import valid_pixels
from discovery.image_photometry_rerun import load_selection_measurements, sha256_file
from discovery.psf_noise import overlap_resample, read_image, verified_template
from tools.jwst.flux_calibration import celestial_wcs, flux_density_factors
from tools.jwst.photometry import extract_photometry


def background_basis(x: np.ndarray, y: np.ndarray, degree: int) -> np.ndarray:
    if degree not in (0, 1, 2):
        raise ValueError("bounded background degree must be 0, 1 or 2")
    columns = [np.ones(x.shape)]
    if degree >= 1:
        columns += [x, y]
    if degree >= 2:
        columns += [x * x, x * y, y * y]
    return np.stack(columns, axis=-1)


def linear_fit(
    data: np.ndarray,
    error: np.ndarray,
    psf: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    valid: np.ndarray,
    *,
    degree: int,
    cluster_width: float = 0.2,
) -> dict[str, Any]:
    """Signed amplitude and grouped residual sandwich, with source-excluded control.

    Diagonal ERR defines the objective. Correlated residual groups diagnose its
    sensitivity; neither objective differences nor intervals are calibrated
    detection probabilities. The control background sees no central r<0.3 pixels.
    """
    if not np.isfinite(cluster_width) or cluster_width <= 0:
        raise ValueError("residual cluster width must be positive and finite")
    if not (data.shape == error.shape == psf.shape == x.shape == y.shape == valid.shape):
        raise ValueError("local fit arrays must agree")
    valid = valid & np.isfinite(data) & np.isfinite(error) & (error > 0)
    valid &= np.isfinite(psf) & np.isfinite(x) & np.isfinite(y)
    polynomial = background_basis(x, y, degree)
    design = np.column_stack([psf[valid], polynomial[valid]])
    if int(valid.sum()) < 5 * design.shape[1]:
        return {"status": "insufficient_valid_fit_pixels"}
    weighted = design / error[valid, None]
    observations = data[valid] / error[valid]
    coefficients, _, rank, _ = np.linalg.lstsq(weighted, observations, rcond=None)
    if rank < design.shape[1]:
        return {"status": "rank_deficient"}
    bread = np.linalg.inv(weighted.T @ weighted)
    residual = observations - weighted @ coefficients
    groups = np.column_stack(
        [np.floor(x[valid] / cluster_width), np.floor(y[valid] / cluster_width)]
    )
    unique, group_index = np.unique(groups, axis=0, return_inverse=True)
    meat = np.zeros(bread.shape)
    for group in range(len(unique)):
        score = weighted[group_index == group].T @ residual[group_index == group]
        meat += np.outer(score, score)
    adjustment = (
        len(unique) / (len(unique) - 1) * (len(residual) - 1) / (len(residual) - design.shape[1])
    )
    sandwich = bread @ meat @ bread * adjustment
    sigma = float(np.sqrt(max(sandwich[0, 0], 0)))
    background = np.sum(polynomial * coefficients[1:], axis=-1)
    source_excluded = valid & (np.hypot(x, y) >= 0.3)
    background_design = polynomial[source_excluded] / error[source_excluded, None]
    off_coefficients, _, off_rank, _ = np.linalg.lstsq(
        background_design, data[source_excluded] / error[source_excluded], rcond=None
    )
    if off_rank < polynomial.shape[-1]:
        return {"status": "rank_deficient_off_source_background"}
    off_background = np.sum(polynomial * off_coefficients, axis=-1)
    weights = psf[valid] / error[valid] ** 2
    offsource_amplitude = float(
        np.sum(weights * (data - off_background)[valid]) / np.sum(psf[valid] * weights)
    )
    core = (np.hypot(x, y) <= 0.18873115150197345) & valid
    return {
        "status": "fit",
        "signed_point_amplitude_njy": float(coefficients[0]),
        "formal_diagonal_sigma_njy": float(np.sqrt(bread[0, 0])),
        "residual_cluster_sigma_njy": sigma,
        "conditional_residual_cluster_95_njy": [
            float(coefficients[0] - 1.96 * sigma),
            float(coefficients[0] + 1.96 * sigma),
        ],
        "source_excluded_background_point_amplitude_njy": offsource_amplitude,
        "source_excluded_background_core_aperture_njy": float(
            np.sum((data - off_background)[core])
        ),
        "joint_background_core_aperture_njy": float(np.sum((data - background)[core])),
        "fitted_background_core_sum_njy": float(np.sum(background[core])),
        "source_excluded_background_core_sum_njy": float(np.sum(off_background[core])),
        "cluster_width_arcsec": cluster_width,
        "clusters": len(unique),
        "fit_pixels": int(valid.sum()),
        "parameters": design.shape[1],
        "diagonal_objective_chi2": float(residual @ residual),
        "background_coefficients": coefficients[1:].tolist(),
        "confidence_scope": "normal approximation with grouped observed residuals; background/PSF families remain assumptions",
    }


def fit_patch(
    bundle: dict[str, Any],
    coordinate: SkyCoord,
    template: np.ndarray,
    template_scale: float,
    neighbour_coordinates: SkyCoord,
    *,
    halfwidth: float,
    degree: int,
    psf_width: float = 1,
    cluster_width: float = 0.2,
) -> dict[str, Any]:
    wcs = celestial_wcs(bundle)
    x, y = [float(v) for v in wcs.world_to_pixel(coordinate)]
    scale = float(np.sqrt(abs(np.linalg.det(wcs.pixel_scale_matrix))) * 3600)
    half = int(np.ceil(halfwidth / scale))
    iy, ix = round(y), round(x)
    yy, xx = np.mgrid[-half : half + 1, -half : half + 1]
    gx, gy = xx + ix, yy + iy
    height, width = np.shape(bundle["sci"])
    if np.any(gx < 0) or np.any(gy < 0) or np.any(gx >= width) or np.any(gy >= height):
        return {"status": "fit_window_off_image"}
    sky = wcs.pixel_to_world(gx, gy)
    east, north = coordinate.spherical_offsets_to(sky)
    east, north = east.arcsec, north.arcsec
    factor = flux_density_factors(bundle, gx, gy)
    if factor["status"] != "calibrated":
        raise ValueError("local model requires calibrated image")
    data = np.asarray(bundle["sci"])[gy, gx] * factor["factor_jy"] * 1e9
    error = np.asarray(bundle["err"])[gy, gx] * factor["factor_jy"] * 1e9
    valid = (
        valid_pixels(bundle)[gy, gx] & (np.abs(east) <= halfwidth) & (np.abs(north) <= halfwidth)
    )
    masked_neighbours = 0
    for neighbour in neighbour_coordinates:
        if coordinate.separation(neighbour).arcsec > np.sqrt(2) * halfwidth + 0.18:
            continue
        valid &= sky.separation(neighbour).arcsec > 0.18
        masked_neighbours += 1
    psf = overlap_resample(
        template, template_scale * psf_width, scale, 2 * half + 1, (x - ix, y - iy)
    )
    result = linear_fit(
        data, error, psf, east, north, valid, degree=degree, cluster_width=cluster_width
    )
    return {
        "halfwidth_arcsec": halfwidth,
        "background_degree": degree,
        "psf_width_factor": psf_width,
        "masked_neighbour_cores": masked_neighbours,
        "finite_point_template_model": True,
        **result,
    }


def render_native_view(panels: list[dict[str, Any]], path: Path) -> None:
    """Actual native pixels with independently scaled asinh brightness."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    figure, axes = plt.subplots(1, len(panels), figsize=(12, 3.4))
    for ax, panel in zip(axes, panels, strict=True):
        image = panel["image"]
        lo, hi = np.nanpercentile(image, [1, 99])
        stretched = np.arcsinh((image - lo) / (hi - lo) * 5)
        extent = panel["extent"]
        ax.imshow(stretched, origin="lower", cmap="magma", extent=extent)
        centre = panel["centre"]
        for radius, style in (
            (0.18873115150197345, "-"),
            (0.3774623030039469, "--"),
            (0.6291038383399116, "--"),
        ):
            ax.add_patch(
                Circle(centre, radius, fill=False, edgecolor="cyan", linestyle=style, linewidth=0.8)
            )
        ax.set_title(panel["title"])
        ax.set_xlabel("Native x offset (arcsec)")
    axes[0].set_ylabel("Native y offset (arcsec)")
    figure.suptitle(
        "SMACS1043: actual pixels; each panel scaled separately; cyan aperture/annulus", fontsize=10
    )
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def run(
    original_dir: Path, repeat_dir: Path, short_psf: Path, long_psf: Path, output: Path
) -> dict[str, Any]:
    catalog_dir = Path("research_output/smacs_matched_image_rerun")
    catalog = load_selection_measurements(
        catalog_dir / "selection_measurements.csv", catalog_dir / "selection_metadata.json"
    )
    replay = json.loads((catalog_dir / "compact_replay_verification.json").read_text())
    if sha256_file(catalog_dir / "selection_measurements.csv") != replay["selection_csv_sha256"]:
        raise ValueError("Frozen source positions differ")
    if sha256_file(catalog_dir / "selection_metadata.json") != replay["selection_metadata_sha256"]:
        raise ValueError("Frozen catalogue metadata differ")
    target = next(p for p in catalog if p["source_id"] == 1043)
    coordinate = SkyCoord(**target["sky_center"], unit="deg")
    sky = SkyCoord(
        [p["sky_center"]["ra"] for p in catalog],
        [p["sky_center"]["dec"] for p in catalog],
        unit="deg",
    )
    distances = coordinate.separation(sky).arcsec
    nearby = (distances > 0) & (distances < 4)
    neighbours = sky[nearby]
    inputs = json.loads(Path("data_sources/original_images_round3_matched_smacs.json").read_text())[
        "images"
    ]
    pins = [
        next(r for r in inputs if r["filter"] == band and "jw02736" in r["id"])
        for band in ("F090W", "F200W", "F444W")
    ]
    # F200 is the matching NRCA1 product, never the disjoint quarter.
    pins[1] = next(r for r in inputs if r["id"] == "jw02736001001_02105_00004_nrca1_i2d.fits")
    pins += [json.loads(Path("data_sources/smacs_repeat_images.json").read_text())["images"][1]]
    psf_pins = {
        r["filter"]: r["sha256"]
        for r in json.loads(Path("data_sources/native_psf_products.json").read_text())["products"]
    }
    psf_pins["F444W"] = "b74abf676cd57f272ada642a27fbb6a8fcb6e0181407357784d812c7f5fd6db2"
    reports, panels = [], []
    for index, pin in enumerate(pins):
        band = pin["filter"]
        path = (repeat_dir if index == 3 else original_dir) / pin["product_filename"]
        if sha256_file(path) != pin["sha256"]:
            raise ValueError("Observed image does not match frozen inventory")
        bundle = read_image(path)
        bundle["wcs"] = celestial_wcs(bundle)
        x, y = [float(v) for v in bundle["wcs"].world_to_pixel(coordinate)]
        scale = float(np.sqrt(abs(np.linalg.det(bundle["wcs"].pixel_scale_matrix))) * 3600)
        half = int(np.ceil(2 / scale))
        ix, iy = round(x), round(y)
        panels.append(
            {
                "image": bundle["sci"][iy - half : iy + half + 1, ix - half : ix + half + 1],
                "extent": [-half * scale, half * scale, -half * scale, half * scale],
                "centre": ((x - ix) * scale, (y - iy) * scale),
                "title": band + (" repeat" if index == 3 else " original"),
            }
        )
        template_path = (
            long_psf / "f444wa_v5.0_mpsf.fits"
            if band == "F444W"
            else short_psf / f"{band.lower()}_v5.0_mpsf.fits"
        )
        template, provenance = verified_template(template_path, band)
        if provenance["sha256"] != psf_pins[band]:
            raise ValueError("PSF model does not match frozen inventory")
        original_aperture = extract_photometry(
            bundle,
            ra_deg=coordinate.ra.deg,
            dec_deg=coordinate.dec.deg,
            aperture_radius_arcsec=0.18873115150197345,
            background_annulus_inner_radius_arcsec=0.3774623030039469,
            background_annulus_outer_radius_arcsec=0.6291038383399116,
        )
        fits = [
            fit_patch(
                bundle,
                coordinate,
                template,
                provenance["input_scale_arcsec"],
                neighbours,
                halfwidth=radius,
                degree=degree,
            )
            for radius in (0.45, 0.65, 1.0)
            for degree in (0, 1, 2)
        ]
        fits += [
            fit_patch(
                bundle,
                coordinate,
                template,
                provenance["input_scale_arcsec"],
                neighbours,
                halfwidth=0.65,
                degree=2,
                psf_width=width,
                cluster_width=cluster,
            )
            for width in (0.9, 1.0, 1.1)
            for cluster in (0.1, 0.3)
        ]
        # Freeze sign-blind geometrical comparison positions; these can contain
        # uncatalogued sources or diffraction structure and are not pure sky.
        controls = []
        for angle in np.arange(0, 360, 30):
            control = coordinate.directional_offset_by(float(angle) * u.deg, 2.8 * u.arcsec)
            if np.min(control.separation(sky).arcsec) <= 0.45:
                continue
            record = fit_patch(
                bundle,
                control,
                template,
                provenance["input_scale_arcsec"],
                sky[control.separation(sky).arcsec < 2],
                halfwidth=0.45,
                degree=2,
            )
            controls.append(
                {
                    "position_angle_deg": int(angle),
                    "ra": control.ra.deg,
                    "dec": control.dec.deg,
                    **record,
                }
            )
        reports.append(
            {
                "filter": band,
                "epoch": "repeat" if index == 3 else "reference",
                "product_filename": path.name,
                "sha256": pin["sha256"],
                "modeled_psf": provenance,
                "original_annulus_measurement": {
                    k: original_aperture[k]
                    for k in (
                        "background_subtracted_flux_jy",
                        "flux_error_jy",
                        "snr",
                        "background_mean",
                        "background_subtracted_flux",
                        "flux_jy",
                    )
                },
                "local_point_background_fits": fits,
                "geometrical_controls": controls,
            }
        )
        print(
            json.dumps(
                {
                    "filter": band,
                    "epoch": reports[-1]["epoch"],
                    "fit_amplitudes": [f.get("signed_point_amplitude_njy") for f in fits[:9]],
                }
            ),
            flush=True,
        )
    result = {
        "experiment": "observed SMACS1043 compact-patch and annulus-background anatomy",
        "source_id": 1043,
        "sky_center": target["sky_center"],
        "catalog_sha256": replay["selection_csv_sha256"],
        "nearby_frozen_proposals": [
            {
                "source_id": p["source_id"],
                "separation_arcsec": float(d),
                "sky_center": p["sky_center"],
            }
            for p, d in zip(catalog, distances, strict=True)
            if 0 < d < 4
        ],
        "images": reports,
        "limitations": [
            "Postselection anatomy of one nominated patch is not source recovery or contamination prevalence.",
            "JADES PSFs transported/aligned to SMACS are finite point-template assumptions.",
            "Signed point amplitudes are local model parameters, not certified galaxy total fluxes.",
            "Polynomial backgrounds cannot exactly remove structured diffraction spikes.",
            "Residual-cluster intervals are conditional approximations, not independently calibrated coverage.",
            "Neighbour masks use observed proposal positions; they do not identify every contaminant.",
            "Geometrical controls can include uncatalogued sources/structured background and share spatial noise.",
            "Persistent compact structure does not establish stellar/galaxy identity, redshift or high-z membership.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    figure_path = output.with_suffix(".png")
    render_native_view(panels, figure_path)
    result["actual_pixel_figure"] = {
        "filename": figure_path.name,
        "sha256": sha256_file(figure_path),
    }
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-dir", type=Path, required=True)
    parser.add_argument("--repeat-dir", type=Path, required=True)
    parser.add_argument("--short-psf", type=Path, required=True)
    parser.add_argument("--long-psf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.original_dir, args.repeat_dir, args.short_psf, args.long_psf, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
