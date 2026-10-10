"""Independent actual-pixel photometry and photon-passband degeneracy audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales
from scipy.ndimage import map_coordinates, rotate
from scipy.optimize import minimize
from scipy.signal import convolve2d


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def independent_passband(path: Path, band: str) -> tuple:
    """Direct XML TABLEDATA parser, independent of author astropy passband loader."""
    root = ET.parse(path).getroot()
    params = {
        e.attrib.get("name"): e.attrib.get("value")
        for e in root.iter()
        if e.tag.split("}")[-1] == "PARAM"
    }
    if (params["filterID"], params["WavelengthUnit"], params["DetectorType"]) != (
        "JWST/NIRCam." + band,
        "Angstrom",
        "1",
    ):
        raise ValueError("Independent filter identity/units/photon convention differs")
    rows = [
        [float(td.text) for td in tr if td.tag.split("}")[-1] == "TD"]
        for tr in root.iter()
        if tr.tag.split("}")[-1] == "TR"
    ]
    table = np.array(rows)
    return table[:, 0] / 10000, table[:, 1]


def model_image(psf: np.ndarray, params: np.ndarray, scale: float) -> np.ndarray:
    """Independent spatial convolution and explicit bilinear coordinate map."""
    dx, dy, sigma, q, angle = params
    yy, xx = np.mgrid[: len(psf), : len(psf)] - len(psf) // 2
    if sigma:
        major = xx * np.cos(angle) + yy * np.sin(angle)
        minor = -xx * np.sin(angle) + yy * np.cos(angle)
        kernel = np.exp(-0.5 * ((major * scale / sigma) ** 2 + (minor * scale / (sigma * q)) ** 2))
        kernel /= kernel.sum()
        profile = convolve2d(psf, kernel, mode="same")
    else:
        profile = psf
    return map_coordinates(
        profile,
        [yy + len(psf) // 2 - dy / scale, xx + len(psf) // 2 - dx / scale],
        order=1,
        mode="constant",
        cval=0,
    )


def spatial_svd(data, error, template, mask, scale) -> tuple:
    yy, xx = np.mgrid[: len(data), : len(data)] - len(data) // 2
    valid = mask & np.isfinite(data) & np.isfinite(error) & (error > 0)
    basis = np.column_stack(
        (template[valid], np.ones(valid.sum()), xx[valid] * scale, yy[valid] * scale)
    )
    whitened = basis / error[valid, None]
    inverse = np.linalg.pinv(whitened, rcond=1e-14)
    coefficient = inverse @ (data[valid] / error[valid])
    covariance = inverse @ inverse.T
    residual = (data[valid] - basis @ coefficient) / error[valid]
    return coefficient, covariance, residual, valid


def audit(root: Path, directory: Path, deep: Path) -> dict:
    manifest_path = root / "data_sources/survivor46_medium/manifest.json"
    result_path = root / "research_output/survivor46_medium_v1.json"
    if sha(result_path) != "df00194c821bc3ff4b17ffd95c9fe7ba885c8f297f2bbdb636baf5da8f582eec":
        raise ValueError("Frozen ddcd23b medium-band artifact differs")
    photometry_path = root / "research_output/survivor_deep_model.json"
    manifest, saved = (json.loads(p.read_text()) for p in (manifest_path, result_path))
    input_pins = {}
    for where, products in (
        (directory, manifest["products"]),
        (deep, manifest["reused_deep_products"]),
    ):
        for p in products:
            path = where / p["filename"]
            if sha(path) != p["sha256"] or path.stat().st_size != p["expected_bytes"]:
                raise ValueError("Actual pixel/model bytes differ from frozen manifest")
            input_pins[p["filename"]] = sha(path)
    if sha(photometry_path) != manifest["photometry_sha256"]:
        raise ValueError("Fixed F444 morphology identity differs")
    image_path = directory / "dja_46_F410M.fits"
    with fits.open(image_path, memmap=False) as hdul:
        header = hdul[0].header.copy()
        science, weight = [np.asarray(h.data, float) for h in hdul]
    if (header["BUNIT"], header["FILTER"]) != ("10.0*nanoJansky", "F410M-CLEAR"):
        raise ValueError("Independent pixel unit/filter mismatch")
    wcs = WCS(header).celestial
    scale = float(np.sqrt(np.prod(proj_plane_pixel_scales(wcs) * 3600)))
    sky = SkyCoord(manifest["ra_deg"], manifest["dec_deg"], unit="deg")
    cx, cy = (float(v) for v in wcs.world_to_pixel(sky))
    x, y = round(cx), round(cy)
    data = science[y - 40 : y + 41, x - 40 : x + 41] * 10
    error = 10 / np.sqrt(weight[y - 40 : y + 41, x - 40 : x + 41])
    with fits.open(directory / "f410ma_v5.0_mpsf.fits") as hdul:
        hdu = next(h for h in hdul if h.data is not None and h.data.ndim == 2)
        raw = np.asarray(hdu.data, float)
        psf_scale = float(hdu.header["PIXELSCL"])
    raw /= raw.sum()
    # Independently integrate intersections of input/output angular pixel boxes.
    old_centers = (np.arange(len(raw)) - (len(raw) - 1) / 2) * psf_scale
    new_centers = (np.arange(81) - 40) * scale
    left = np.maximum(new_centers[:, None] - scale / 2, old_centers[None, :] - psf_scale / 2)
    right = np.minimum(new_centers[:, None] + scale / 2, old_centers[None, :] + psf_scale / 2)
    overlap = np.maximum(right - left, 0) / psf_scale
    psf = overlap @ raw @ overlap.T
    source = next(
        s for s in json.loads(photometry_path.read_text())["sources"] if s["source_id"] == 46
    )
    fixed = np.array(source["f444_morphology"]["extended"]["params"])
    with fits.open(deep / "dja_46_F444W.fits") as hdul:
        old_wcs = WCS(hdul[0].header).celestial
        wide_header = hdul[0].header.copy()
    old_x, old_y = (float(v) for v in old_wcs.world_to_pixel(sky))
    old_scale = float(np.sqrt(np.prod(proj_plane_pixel_scales(old_wcs) * 3600)))
    fixed[:2] += np.array(
        [
            (cx - x) * scale - (old_x - round(old_x)) * old_scale,
            (cy - y) * scale - (old_y - round(old_y)) * old_scale,
        ]
    )
    yy, xx = np.mgrid[:81, :81] - 40
    radius = np.hypot(xx, yy) * scale
    fits_review = []
    fiducial = None
    for fit in saved["signed_fixed_models"]:
        local_psf = (
            psf
            if fit["modeled_psf_rotation_deg"] == 0
            else rotate(
                psf,
                fit["modeled_psf_rotation_deg"],
                reshape=False,
                order=1,
                mode="constant",
                cval=0,
            )
        )
        template = model_image(local_psf, fixed, scale)
        answer = spatial_svd(data, error, template, radius <= fit["radius_arcsec"], scale)
        flux_error = abs(answer[0][0] - fit["flux_njy"])
        sigma_error = abs(np.sqrt(answer[1][0, 0]) - fit["diagonal_error_njy"])
        chi2_error = abs(answer[2] @ answer[2] - fit["chi2_diagonal"])
        if flux_error > 1e-7 or sigma_error > 1e-7 or chi2_error > 1e-5:
            raise ValueError("Independent finite-PSF/SVD fit differs")
        fits_review.append(
            {
                "radius": fit["radius_arcsec"],
                "rotation": fit["modeled_psf_rotation_deg"],
                "flux_error_njy": float(flux_error),
                "sigma_error_njy": float(sigma_error),
                "chi2_error": float(chi2_error),
            }
        )
        if fit["radius_arcsec"] == 0.65 and fit["modeled_psf_rotation_deg"] == 0:
            fiducial = answer
    coefficient, uncertainty, residual, valid = fiducial
    radial_residual = radius[valid]
    core_fraction = float(np.sum(residual[radial_residual <= 0.2] ** 2) / np.sum(residual**2))

    def centroid_score(offsets):
        params = fixed.copy()
        params[:2] = offsets
        result = spatial_svd(data, error, model_image(psf, params, scale), radius <= 0.65, scale)
        return float(result[2] @ result[2])

    centroid = minimize(
        centroid_score,
        fixed[:2],
        method="Nelder-Mead",
        options={"xatol": 1e-9, "fatol": 1e-8, "maxiter": 500},
    )

    # Independent WCS-centre spherical apertures with direct nJy conversion.
    gy, gx = np.mgrid[y - 25 : y + 26, x - 25 : x + 26]
    separations = wcs.pixel_to_world(gx, gy).separation(sky).arcsec
    pixel_data = science[gy, gx] * 10
    pixel_variance = 100 / weight[gy, gx]
    aperture_reviews = []
    for row in saved["aperture_background_sensitivity"]:
        ap = separations <= row["radius_arcsec"]
        ann = (separations >= row["annulus_arcsec"][0]) & (separations <= row["annulus_arcsec"][1])
        flux = np.sum(pixel_data[ap]) - np.mean(pixel_data[ann]) * ap.sum()
        variance = (
            np.sum(pixel_variance[ap])
            + ap.sum() ** 2 * np.sum(pixel_variance[ann]) / ann.sum() ** 2
        )
        if abs(flux - row["flux_njy"]) > 1e-7 or abs(
            np.sqrt(variance) - row["diagonal_error_njy"]
        ) > 1e-7:
            raise ValueError("Independent actual-pixel aperture differs")
        aperture_reviews.append(
            {
                "radius": row["radius_arcsec"],
                "annulus": row["annulus_arcsec"],
                "flux_njy": float(flux),
                "diagonal_sigma_njy": float(np.sqrt(variance)),
            }
        )

    wm, tm = independent_passband(directory / "svo_F410M.xml", "F410M")
    ww, tw = independent_passband(deep / "svo_F444W.xml", "F444W")
    wavelengths = np.linspace(3.7, 5.0, 1301)
    dm, dw = np.trapezoid(tm / wm, wm), np.trapezoid(tw / ww, ww)
    im, iw = (
        np.interp(wavelengths, wm, tm, left=0, right=0),
        np.interp(wavelengths, ww, tw, left=0, right=0),
    )
    ratios = np.divide(im * dw, iw * dm, out=np.full_like(im, np.nan), where=iw > 0)
    measured_ratio = coefficient[0] / saved["f444_frozen_njy"]
    match = (
        (iw > 0.05 * tw.max())
        & np.isfinite(ratios)
        & (abs(ratios - measured_ratio) < 0.15 * measured_ratio)
    )
    matched = wavelengths[match]
    if not np.allclose(
        matched, saved["single_narrow_line_response_sensitivity"]["matched_wavelengths_micron"]
    ):
        raise ValueError("Independent photon filter-overlap counterexample differs")
    line_center = float(np.median(matched))
    fine = np.linspace(line_center - 0.005, line_center + 0.005, 10001)
    line = np.exp(-0.5 * ((fine - line_center) / 0.0001) ** 2)
    # f_lambda narrow-line photon counts have lambda*T response; a constant-fnu
    # AB denominator is integral(T/lambda). Common c/h constants cancel.
    line_ratio = (
        np.trapezoid(line * fine * np.interp(fine, wm, tm), fine)
        / dm
        / (np.trapezoid(line * fine * np.interp(fine, ww, tw), fine) / dw)
    )
    medium_contributors = {str(header[k]) for k in header if k.startswith("FLT")}
    wide_contributors = {str(wide_header[k]) for k in wide_header if k.startswith("FLT")}
    return {
        "schema_version": 1,
        "author_science_commit": "ddcd23b",
        "declared_plan_commit": "4e766b6",
        "author_result_sha256": sha(result_path),
        "manifest_sha256": sha(manifest_path),
        "actual_input_hashes": input_pins,
        "frozen_photometry_sha256": sha(photometry_path),
        "independent_pixel_center": [cx, cy],
        "independent_finite_PSF_retained_fraction": float(psf.sum()),
        "six_independent_spatial_SVD_fits": fits_review,
        "independent_pixel_aperture_background_checks": aperture_reviews,
        "independent_Nelder_Mead_centroid_arcsec": centroid.x.tolist(),
        "independent_centroid_displacement_arcsec": float(np.linalg.norm(centroid.x - fixed[:2])),
        "author_centroid_difference_arcsec": float(
            np.linalg.norm(
                centroid.x - saved["conditional_centroid_diagnostic"]["free_position_arcsec"]
            )
        ),
        "fraction_fiducial_diagonal_chi2_within_0p2arcsec": core_fraction,
        "F410_model_flux_span_njy": [
            min(f["flux_njy"] for f in saved["signed_fixed_models"]),
            max(f["flux_njy"] for f in saved["signed_fixed_models"]),
        ],
        "ratio_is_calibrated_measurement_interval": False,
        "independent_conditional_f410_over_f444": float(measured_ratio),
        "independent_single_line_overlap_window_micron": [
            float(matched.min()),
            float(matched.max()),
        ],
        "prescribed_overlap_tolerance_fraction": 0.15,
        "explicit_narrow_line_center_micron": line_center,
        "independently_integrated_narrow_line_band_ratio": float(line_ratio),
        "shared_exact_contributors": sorted(medium_contributors & wide_contributors),
        "approval_scope": (
            "Positive adjacent-band counterpart, conditional finite-PSF fits "
            "and overlapping-line degeneracy"
        ),
        "limitations": [
            (
                "Model residual/core structure dominates formal background-only errors; "
                "no precise calibrated flux ratio"
            ),
            "No independent visit/calibration merely because filters have disjoint filenames",
            (
                "Single-line overlap window uses prescribed tolerance, "
                "not confidence or redshift interval"
            ),
            "No source identity, proper motion, empirical PSF or stellar/galaxy classification",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "input", "deep", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.root, args.input, args.deep), indent=2) + "\n")


if __name__ == "__main__":
    main()
