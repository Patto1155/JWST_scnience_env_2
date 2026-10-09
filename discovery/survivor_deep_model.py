"""PSF-aware deep imaging diagnostics for three frozen GOODS hypotheses.

This tests finite point/extended image models and filter-integrated phenomenological
continuum families.  It does not implement a calibrated stellar-population SED,
photometric-redshift posterior, or independent observing-epoch confirmation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import warnings
from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io.votable import parse_single_table
from astropy.stats import sigma_clipped_stats
from astropy.wcs.utils import proj_plane_pixel_scales
from photutils.segmentation import detect_sources
from scipy.ndimage import binary_dilation, rotate, shift
from scipy.optimize import differential_evolution, minimize
from scipy.signal import fftconvolve

from data_pipeline.survivor_deep_data import MANIFEST, verify_pinned
from discovery.deep_reference_comparison import load_deep_cutout, measurement
from discovery.psf_noise import overlap_resample, verified_template
from tools.jwst.flux_calibration import flux_density_factors
from tools.jwst.photometry import extract_photometry

BANDS = ("F090W", "F115W", "F150W", "F200W", "F277W", "F356W", "F444W")
FIT_RADIUS = 0.65
MODEL_HALF_WIDTH = 2.0


def elliptical_gaussian(size: int, sigma: float, q: float, angle: float) -> np.ndarray:
    """Unit-flux intrinsic Gaussian; sigma is major-axis standard deviation in pixels."""
    if size % 2 != 1 or size < 3 or sigma < 0 or not 0.2 <= q <= 1:
        raise ValueError("Invalid intrinsic Gaussian")
    kernel = np.zeros((size, size))
    if sigma == 0:
        kernel[size // 2, size // 2] = 1
        return kernel
    yy, xx = np.mgrid[:size, :size] - size // 2
    ca, sa = np.cos(angle), np.sin(angle)
    major, minor = ca * xx + sa * yy, -sa * xx + ca * yy
    kernel = np.exp(-0.5 * ((major / sigma) ** 2 + (minor / (q * sigma)) ** 2))
    return kernel / kernel.sum()


def image_template(psf: np.ndarray, scale: float, params: np.ndarray) -> np.ndarray:
    """Convolve finite PSF without renormalizing lost wings, then bilinear subpixel shift."""
    dx, dy, sigma_arcsec, q, angle = params
    kernel = elliptical_gaussian(psf.shape[0], sigma_arcsec / scale, q, angle)
    extended = fftconvolve(psf, kernel, mode="same") if sigma_arcsec else psf
    return shift(extended, (dy / scale, dx / scale), order=1, mode="constant", cval=0)


def linear_fit(
    data: np.ndarray,
    error: np.ndarray,
    template: np.ndarray,
    mask: np.ndarray,
    scale: float,
    companion: np.ndarray | None = None,
) -> dict:
    """Signed total-template flux plus a local background plane, exact diagonal covariance."""
    if not (data.shape == error.shape == template.shape == mask.shape):
        raise ValueError("Inconsistent image-model dimensions")
    yy, xx = np.mgrid[: data.shape[0], : data.shape[1]] - data.shape[0] // 2
    valid = mask & np.isfinite(data) & np.isfinite(error) & (error > 0)
    if valid.sum() < 20:
        raise ValueError("Too few covered model pixels")
    columns = [template[valid], np.ones(valid.sum()), xx[valid] * scale, yy[valid] * scale]
    if companion is not None:
        if companion.shape != data.shape or not np.isfinite(companion).all():
            raise ValueError("Invalid spatial companion template")
        columns.append(companion[valid])
    design = np.column_stack(columns)
    weighted = design / error[valid, None]
    fisher = weighted.T @ weighted
    if np.linalg.matrix_rank(fisher) != len(columns):
        raise ValueError("Image model is not identifiable on covered pixels")
    covariance = np.linalg.inv(fisher)
    operator = covariance @ (design.T / error[valid] ** 2)
    coefficient = operator @ data[valid]
    residual = (data[valid] - design @ coefficient) / error[valid]
    result = {
        "flux_njy": float(coefficient[0]),
        "diagonal_error_njy": float(np.sqrt(covariance[0, 0])),
        "background_njy_per_pixel": float(coefficient[1]),
        "background_gradient_njy_per_pixel_per_arcsec": coefficient[2:4].tolist(),
        "chi2_diagonal": float(residual @ residual),
        "pixels": int(valid.sum()),
        "dof_linear": int(valid.sum() - len(columns)),
        "template_flux_fraction_in_fit": float(template[valid].sum()),
    }
    if companion is not None:
        result.update(
            companion_flux_njy=float(coefficient[4]),
            companion_diagonal_error_njy=float(np.sqrt(covariance[4, 4])),
            target_companion_flux_covariance_njy2=float(covariance[0, 4]),
        )
    return result


def stamp(
    bundle: dict, ra: float, dec: float, half: int, x: int | None = None, y: int | None = None
) -> tuple[np.ndarray, np.ndarray, float, tuple[float, float]]:
    scale = float(np.sqrt(np.prod(proj_plane_pixel_scales(bundle["wcs"]) * 3600)))
    xp, yp = bundle["wcs"].world_to_pixel(SkyCoord(ra, dec, unit="deg"))
    cx, cy = int(round(float(xp))) if x is None else x, int(round(float(yp))) if y is None else y
    if (
        min(cx, cy) < half
        or cx + half >= bundle["sci"].shape[1]
        or cy + half >= bundle["sci"].shape[0]
    ):
        raise ValueError("Requested model stamp lacks complete grid coverage")
    yy, xx = np.mgrid[cy - half : cy + half + 1, cx - half : cx + half + 1]
    factor = flux_density_factors(bundle, xx, yy)
    if factor["status"] != "calibrated":
        raise ValueError("Deep model requires physical flux calibration")
    conversion = factor["factor_jy"] * 1e9
    data = bundle["sci"][yy, xx] * conversion
    error = bundle["err"][yy, xx] * conversion
    return data, error, scale, ((float(xp) - cx) * scale, (float(yp) - cy) * scale)


def fit_mask(size: int, scale: float) -> np.ndarray:
    yy, xx = np.mgrid[:size, :size] - size // 2
    return np.hypot(xx, yy) * scale <= FIT_RADIUS


def morphology(
    data: np.ndarray,
    error: np.ndarray,
    psf: np.ndarray,
    scale: float,
    phase: tuple[float, float],
    companion: np.ndarray | None = None,
) -> dict:
    mask = fit_mask(len(data), scale)

    def score(params: np.ndarray) -> float:
        return linear_fit(data, error, image_template(psf, scale, params), mask, scale, companion)[
            "chi2_diagonal"
        ]

    initial = np.array([*phase, 0.10, 0.7, 0.0])
    bounds = [
        (phase[0] - 0.15, phase[0] + 0.15),
        (phase[1] - 0.15, phase[1] + 0.15),
        (0.0, 0.35),
        (0.2, 1.0),
        (-np.pi, np.pi),
    ]
    extended = minimize(
        score,
        initial,
        method="Powell",
        bounds=bounds,
        options={"maxiter": 80, "xtol": 1e-5, "ftol": 1e-6},
    )

    def point_score(offsets: np.ndarray) -> float:
        return score(np.array([*offsets, 0.0, 1.0, 0.0]))

    point = minimize(point_score, np.array(phase), method="Powell", bounds=bounds[:2])
    pp = np.array([*point.x, 0.0, 1.0, 0.0])
    ep = extended.x
    return {
        "extended": {
            "params": ep.tolist(),
            "optimizer_success": bool(extended.success),
            **linear_fit(data, error, image_template(psf, scale, ep), mask, scale, companion),
        },
        "point": {
            "params": pp.tolist(),
            "optimizer_success": bool(point.success),
            **linear_fit(data, error, image_template(psf, scale, pp), mask, scale, companion),
        },
        "delta_chi2_point_minus_extended_diagonal": float(point.fun - extended.fun),
        "interpretation": (
            "Conditional shape diagnostic, not calibrated significance: "
            "PSF mismatch, neighbors and correlated pixels remain"
        ),
    }


def blank_operator_noise(
    bundle: dict,
    psf: np.ndarray,
    params: np.ndarray,
    scale: float,
    half: int,
    companion: np.ndarray | None = None,
) -> dict:
    """Apply the actual flux+plane fit operator to disjoint source-masked background sites."""
    valid = bundle["validity_mask"]
    _, med, scatter = sigma_clipped_stats(bundle["sci"][valid], sigma=3)
    segmentation = detect_sources(
        np.where(valid, bundle["sci"] - med, 0), 2 * scatter, npixels=5, mask=~valid
    )
    source = np.zeros(valid.shape, bool) if segmentation is None else segmentation.data > 0
    excluded = binary_dilation(source, iterations=4) | ~valid
    fit_half = int(np.ceil(FIT_RADIUS / scale)) + 1
    separation = 2 * fit_half + 2
    mask = fit_mask(2 * half + 1, scale)
    blank_params = np.array([0.0, 0.0, *params[2:]])
    template = image_template(psf, scale, blank_params)
    values, normalized = [], []
    for y in range(half + 1, valid.shape[0] - half - 1, separation):
        for x in range(half + 1, valid.shape[1] - half - 1, separation):
            local = excluded[y - half : y + half + 1, x - half : x + half + 1]
            if np.any(local[mask]):
                continue
            data, error, _, _ = stamp(bundle, 0, 0, half, x=x, y=y)
            fitted = linear_fit(data, error, template, mask, scale, companion)
            values.append(fitted["flux_njy"])
            normalized.append(fitted["flux_njy"] / fitted["diagonal_error_njy"])
    if len(values) < 20:
        return {
            "status": "insufficient_disjoint_blank_models",
            "count": len(values),
            "robust_sigma_njy": None,
            "diagonal_scale_factor": None,
        }
    values, normalized = np.array(values), np.array(normalized)

    def robust(a):
        return float(1.4826 * np.median(np.abs(a - np.median(a))))

    return {
        "status": "measured_conditional_background_operator_scatter",
        "count": len(values),
        "robust_sigma_njy": robust(values),
        "ordinary_sigma_njy": float(values.std(ddof=1)),
        "median_flux_njy": float(np.median(values)),
        "diagonal_scale_factor": robust(normalized),
        "normalized_range": [float(normalized.min()), float(normalized.max())],
        "limitation": (
            "Local source-mask/depth assumptions; not source shot-noise variance "
            "or calibrated Gaussian-tail probability"
        ),
    }


def read_passband(path: Path, band: str) -> tuple[np.ndarray, np.ndarray]:
    votable = parse_single_table(path)
    parameters = {p.name: p.value for p in votable.params}
    if (
        parameters.get("filterID") != "JWST/NIRCam." + band
        or parameters.get("WavelengthUnit") != "Angstrom"
        or parameters.get("DetectorType") != "1"
    ):
        raise ValueError("Passband identity, wavelength unit or photon detector mismatch")
    table = votable.to_table()
    wave = np.asarray(table["Wavelength"], float) / 10000
    throughput = np.asarray(table["Transmission"], float)
    if (
        len(wave) < 20
        or np.any(np.diff(wave) <= 0)
        or np.any(throughput < 0)
        or not np.all(np.isfinite(wave + throughput))
        or np.max(throughput) <= 0
    ):
        raise ValueError("Invalid versioned photon throughput: " + band)
    return wave, throughput


def band_average(wave: np.ndarray, throughput: np.ndarray, fnu: np.ndarray) -> float:
    """Photon-counting AB-equivalent fnu: integral(fnu T dλ/λ)/integral(T dλ/λ)."""
    return float(
        np.trapezoid(fnu * throughput / wave, wave) / np.trapezoid(throughput / wave, wave)
    )


def continuum_shape(
    passbands: list[tuple[np.ndarray, np.ndarray]], family: str, params: np.ndarray
) -> np.ndarray:
    output = []
    for wave, throughput in passbands:
        logwave = np.log(wave / 2.0)
        if family == "smooth_log_quadratic":
            spectrum = np.exp(params[0] * logwave + params[1] * logwave**2)
        elif family == "lyman_step_powerlaw":
            redshift, slope = params
            spectrum = (wave / 2) ** slope * (wave >= 0.1216 * (1 + redshift))
        elif family == "balmer4000_step_powerlaw":
            redshift, blue_slope, red_slope, jump = params
            pivot = 0.4 * (1 + redshift)
            spectrum = np.where(
                wave < pivot, (wave / pivot) ** blue_slope / jump, (wave / pivot) ** red_slope
            )
        elif family == "blackbody":
            temperature = params[0]
            spectrum = wave**-3 / np.expm1(14387.769 / (wave * temperature))
            spectrum /= 2**-3 / np.expm1(14387.769 / (2 * temperature))
        else:
            raise ValueError("Unknown continuum family")
        output.append(band_average(wave, throughput, spectrum))
    return np.array(output)


def fit_continuum(
    flux: np.ndarray,
    error: np.ndarray,
    passbands: list[tuple[np.ndarray, np.ndarray]],
    floor: float,
) -> dict:
    """Coarse phenomenological falsification; no SED library or calibrated evidence ratio."""
    covariance = np.diag(error**2 + (floor * np.abs(flux)) ** 2) + 0.03**2 * np.outer(flux, flux)
    inverse = np.linalg.inv(covariance)
    families = {
        "smooth_log_quadratic": [(-6, 8), (-8, 8)],
        "lyman_step_powerlaw": [(6.0, 20.0), (-6, 8)],
        "balmer4000_step_powerlaw": [(0.3, 6), (-6, 8), (-6, 8), (1, 20)],
        "blackbody": [(250, 12000)],
    }
    rows = {}
    for family, bounds in families.items():

        def evaluate(params: np.ndarray, full: bool = False):
            shape = continuum_shape(passbands, family, params)
            denominator = shape @ inverse @ shape
            if denominator <= 0:
                return 1e100
            amplitude = max(0.0, float(shape @ inverse @ flux / denominator))
            model = amplitude * shape
            residual = flux - model
            chi2 = float(residual @ inverse @ residual)
            return (amplitude, model, chi2) if full else chi2

        trials = [
            differential_evolution(
                evaluate, bounds, seed=seed, popsize=12, maxiter=160, tol=1e-7, polish=True
            )
            for seed in ((914, 57, 291) if family == "balmer4000_step_powerlaw" else (914,))
        ]
        fit = min(trials, key=lambda fit: fit.fun)
        amplitude, model, chi2 = evaluate(fit.x, True)
        rows[family] = {
            "parameters": fit.x.tolist(),
            "amplitude_njy": amplitude,
            "model_flux_njy": model.tolist(),
            "chi2_conditional": chi2,
            "dof_nominal": len(flux) - len(bounds) - 1,
            "bounds": [list(b) for b in bounds],
            "optimizer_success": bool(fit.success),
            "numerical_search": (
                "Best of three seeded searches for discontinuous 4000 step, "
                "one search for other families; global optimality not proved"
            ),
        }
    return {
        "independent_fractional_floor": floor,
        "shared_fractional_calibration_term": 0.03,
        "flux_covariance_njy2": covariance.tolist(),
        "families": rows,
        "interpretation": (
            "Conditional minimum chi2 over explicit coarse families. "
            "Parameters are not physical redshift estimates; "
            "no calibrated likelihood-ratio or posterior."
        ),
    }


def run(directory: Path, output: Path) -> dict:
    inventory = json.loads(MANIFEST.read_text())
    products = inventory["products"]
    for product in products:
        verify_pinned(directory / product["filename"], product)
    passbands = [read_passband(directory / f"svo_{band}.xml", band) for band in BANDS]
    model_inputs = {}
    for band in BANDS:
        suffix = band.lower() + ("a" if band in BANDS[4:] else "")
        path = directory / f"{suffix}_v5.0_mpsf.fits"
        if not path.exists():
            path = Path("data_sources/pilot") / path.name
        model_inputs[band] = verified_template(path, band)
    rows = []
    for source_id in (98, 254, 46):
        selected = next(p for p in products if p.get("source_id") == source_id)
        ra, dec = selected["ra_deg"], selected["dec_deg"]
        inputs = {}
        for band in BANDS:
            bundle, provenance = load_deep_cutout(directory / f"dja_{source_id}_{band}.fits")
            scales = proj_plane_pixel_scales(bundle["wcs"]) * 3600
            if max(scales) / min(scales) > 1.001:
                raise ValueError("Current finite PSF model requires locally isotropic grid")
            scale = float(np.sqrt(np.prod(scales)))
            half = int(np.ceil(MODEL_HALF_WIDTH / scale))
            data, error, scale, phase = stamp(bundle, ra, dec, half)
            raw_psf, psf_provenance = model_inputs[band]
            psf = overlap_resample(
                raw_psf, psf_provenance["input_scale_arcsec"], scale, 2 * half + 1
            )
            inputs[band] = (bundle, provenance, data, error, scale, phase, half, psf)
        f444 = inputs["F444W"]
        shapes = morphology(f444[2], f444[3], f444[7], f444[4], f444[5])
        f150 = inputs["F150W"]
        yy, xx = np.mgrid[: len(f150[2]), : len(f150[2])] - len(f150[2]) // 2
        inner = np.hypot(xx, yy) * f150[4] <= 0.65
        peak_index = np.unravel_index(
            np.argmax(np.where(inner, f150[2] / f150[3], -np.inf)), f150[2].shape
        )
        peak_offset = np.array([xx[peak_index] * f150[4], yy[peak_index] * f150[4]]) - f150[5]
        companion_offset = None
        deblended_shape = None
        if np.linalg.norm(peak_offset) > 0.25 and f150[2][peak_index] / f150[3][peak_index] > 10:
            companion_offset = peak_offset
            companion_params = np.array([*(np.array(f444[5]) + peak_offset), 0.03, 1.0, 0.0])
            deblended_shape = morphology(
                f444[2],
                f444[3],
                f444[7],
                f444[4],
                f444[5],
                image_template(f444[7], f444[4], companion_params),
            )
        # Relative centroid offset is transferred on sky; each mosaic's own phase remains.
        selected_shape = shapes if deblended_shape is None else deblended_shape
        f444_params = np.array(selected_shape["extended"]["params"])
        offset = f444_params[:2] - f444[5]
        measured = []
        for band in BANDS:
            bundle, provenance, data, error, scale, phase, half, psf = inputs[band]
            params = f444_params.copy()
            params[:2] = np.array(phase) + offset
            companion = (
                None
                if companion_offset is None
                else image_template(
                    psf, scale, np.array([*(np.array(phase) + companion_offset), 0.03, 1.0, 0.0])
                )
            )
            fitted = linear_fit(
                data,
                error,
                image_template(psf, scale, params),
                fit_mask(len(data), scale),
                scale,
                companion,
            )
            point = linear_fit(
                data,
                error,
                image_template(psf, scale, np.array([*params[:2], 0.0, 1.0, 0.0])),
                fit_mask(len(data), scale),
                scale,
                companion,
            )
            noise = blank_operator_noise(bundle, psf, params, scale, half, companion)
            aperture_sensitivity = []
            for radius in (0.15, 0.2, 0.3):
                aperture = extract_photometry(
                    bundle,
                    ra_deg=ra,
                    dec_deg=dec,
                    aperture_radius_arcsec=radius,
                    background_annulus_inner_radius_arcsec=0.4,
                    background_annulus_outer_radius_arcsec=0.6,
                )
                aperture_sensitivity.append(
                    {
                        "radius_arcsec": radius,
                        "flux_njy": aperture["background_subtracted_flux_jy"] * 1e9,
                        "diagonal_error_njy": aperture["flux_error_jy"] * 1e9,
                    }
                )

            # Free local centroid at fixed shape is a crowding/registration diagnostic.
            def centroid_score(position):
                trial = params.copy()
                trial[:2] = position
                return linear_fit(
                    data,
                    error,
                    image_template(psf, scale, trial),
                    fit_mask(len(data), scale),
                    scale,
                    companion,
                )["chi2_diagonal"]

            centroid = minimize(
                centroid_score,
                params[:2],
                method="Powell",
                bounds=[(p - 0.1, p + 0.1) for p in params[:2]],
            )
            spatial_sensitivity = []
            for fit_radius in (0.35, 0.5, FIT_RADIUS):
                yy, xx = np.mgrid[: len(data), : len(data)] - len(data) // 2
                local_mask = np.hypot(xx, yy) * scale <= fit_radius
                local_fit = linear_fit(
                    data, error, image_template(psf, scale, params), local_mask, scale, companion
                )
                spatial_sensitivity.append(
                    {"fit_radius_arcsec": fit_radius, "psf_rotation_deg": 0, **local_fit}
                )
            rotated_psf = rotate(psf, 30, reshape=False, order=1, mode="constant", cval=0)
            rotated_fit = linear_fit(
                data,
                error,
                image_template(rotated_psf, scale, params),
                fit_mask(len(data), scale),
                scale,
                companion,
            )
            spatial_sensitivity.append(
                {"fit_radius_arcsec": FIT_RADIUS, "psf_rotation_deg": 30, **rotated_fit}
            )
            if noise["diagonal_scale_factor"] is None:
                uncertainty = None
            else:
                # Background-only empirical scale must not reduce formal total errors.
                uncertainty = fitted["diagonal_error_njy"] * max(
                    1.0, noise["diagonal_scale_factor"]
                )
            provenance.pop("contributors")
            contributors = [
                str(bundle["header"][k]) for k in bundle["header"] if k.startswith("FLT")
            ]
            measured.append(
                {
                    "filter": band,
                    "image": provenance,
                    "contributor_count": len(contributors),
                    "contributor_sha256": hashlib.sha256(
                        "\n".join(contributors).encode()
                    ).hexdigest(),
                    "pixel_scale_arcsec": scale,
                    "fixed_extended_fit": fitted,
                    "same_centroid_point_fit": point,
                    "empirical_background": noise,
                    "background_scaled_error_njy": uncertainty,
                    "aperture_sensitivity": aperture_sensitivity,
                    "spatial_model_sensitivity": spatial_sensitivity,
                    "free_band_centroid_offset_from_fixed_arcsec": (
                        centroid.x - params[:2]
                    ).tolist(),
                    "free_centroid_chi2_diagonal": float(centroid.fun),
                    "matched_0p2arcsec_aperture": measurement(bundle, ra_deg=ra, dec_deg=dec),
                    "psf": model_inputs[band][1],
                }
            )
        flux = np.array([m["fixed_extended_fit"]["flux_njy"] for m in measured])
        errors = [m["background_scaled_error_njy"] for m in measured]
        continuum = (
            []
            if any(e is None for e in errors)
            else [fit_continuum(flux, np.array(errors), passbands, floor) for floor in (0.05, 0.15)]
        )
        rows.append(
            {
                "source_id": source_id,
                "ra_deg": ra,
                "dec_deg": dec,
                "f444_morphology": shapes,
                "bands": measured,
                "competing_spatial_component": {
                    "offset_from_selection_position_arcsec": (
                        None if companion_offset is None else companion_offset.tolist()
                    ),
                    "fixed_intrinsic_sigma_arcsec": (
                        0.03 if companion_offset is not None else None
                    ),
                    "f444_two_component_model": deblended_shape,
                    "interpretation": (
                        "F150 highest-SNR peak within .65 arcsec, "
                        ">10 pixel SNR and offset >.25 arcsec selects second spatial template; "
                        "no foreground/associated-galaxy assignment"
                    ),
                },
                "phenomenological_continuum_sensitivity": continuum,
            }
        )
    result = {
        "schema_version": 1,
        "evidence_kind": "actual_pinned_deep_mosaics_conditional_image_and_continuum_models",
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "selection_catalog_sha256": inventory["selection_catalog_sha256"],
        "bands": BANDS,
        "fit_radius_arcsec": FIT_RADIUS,
        "sources": rows,
        "assumptions": [
            "Finite JADES modeled PSFs on DAWN mosaics; aligned axes assumed, not calibrated.",
            "F444 Gaussian shape fixes band flux operators; local planes and companions fitted.",
            "Morphology chi2 is descriptive; blanks measure covariance and confusion.",
            "SVO nominal photon throughput; no detector-specific time-dependent correction.",
            "SED assumed floors: independent 5%/15%, common 3%, plus background-scaled errors.",
        ],
        "limits": [
            "Deep mosaics may include selection exposures; no independent-repeat or completeness.",
            "Gaussian morphology, blending, aligned PSF and finite wings limit physical fluxes.",
            "No physical stellar population, dust, nebular emission or realistic IGM transfer.",
            "Family parameters are not redshifts; no whole astrophysical class is excluded.",
            "Background scatter cannot replace source shot-noise and selection-tail calibration.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = run(args.input, args.output)
    print(
        json.dumps(
            {s["source_id"]: s["f444_morphology"]["extended"]["params"] for s in result["sources"]}
        )
    )


if __name__ == "__main__":
    main()
