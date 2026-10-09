"""Reproducible, assumption-labelled PRISM UV-line and extraction sensitivity.

This is a conditional GLS experiment, not a replacement for the published UNITE
posterior or an elemental-abundance measurement.  No network access at runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from astropy import units as u
from astropy.io import fits
from scipy.linalg import cholesky, solve_triangular
from scipy.special import ndtr

from .spectroscopy import _column

LINE_NAMES = ("NIV", "CIV", "HeII_OIII", "NIII", "CIII")
SOURCE_HASH = "42d95d348ebb55ca37eb31393b4603628ac13a4bca1f4f7f0ffba7b32d3125b1"
FWHM_TO_SIGMA = 2.354820045
C_KMS = 299792.458
# Vacuum line positions in Angstrom; weights within unresolved multiplets are
# assumptions, varied below. No density or temperature is inferred from them.
LINE_COMPONENTS = (
    ((1486.496,), (1.0,)),
    ((1548.204, 1550.781), (2.0, 1.0)),
    ((1640.42, 1660.809, 1666.15), (1.0, 1.0, 1.0)),
    ((1746.823, 1748.646, 1749.674, 1752.16, 1753.995), (1, 1, 1, 1, 1)),
    ((1906.683, 1908.734), (1.0, 1.0)),
)


@dataclass
class Extraction:
    """Flux and diagonal uncertainty in uJy, with an explicit validity mask."""

    name: str
    wave: np.ndarray
    flux: np.ndarray
    error: np.ndarray
    valid: np.ndarray
    notes: dict[str, Any]


def bin_edges(wave: np.ndarray) -> np.ndarray:
    """Edges from the full grid, never from a grid shortened by quality cuts."""
    wave = np.asarray(wave, dtype=float)
    if len(wave) < 3 or not np.all(np.isfinite(wave)) or np.any(np.diff(wave) <= 0):
        raise ValueError("A finite, strictly increasing full wavelength grid is required")
    mid = (wave[1:] + wave[:-1]) / 2
    return np.r_[wave[0] - (mid[0] - wave[0]), mid, wave[-1] + (wave[-1] - mid[-1])]


def read_resolution(path: Path) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    receipt = json.loads(Path(str(path) + ".provenance.json").read_text())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != receipt["sha256"]:
        raise ValueError("Resolution curve does not match its receipt")
    with fits.open(path, memmap=False) as h:
        wave = np.asarray(h[1].data["WAVELENGTH"], dtype=float)
        resolution = np.asarray(h[1].data["R"], dtype=float)
    if np.any(np.diff(wave) <= 0) or not np.all(np.isfinite(resolution) & (resolution > 0)):
        raise ValueError("Invalid resolution curve")
    return (
        wave,
        resolution,
        {
            "sha256": digest,
            "source_url": receipt["source_url"],
            "interpretation": "STScI/ETC fully illuminated 2.2-pixel resolution; Gaussian FWHM approximation",
            "source_specific_lsf_calibrated": False,
        },
    )


def extract_2d(
    wave: np.ndarray,
    science: np.ndarray,
    weight: np.ndarray,
    profile: np.ndarray,
    *,
    center: int,
    radius: int,
    method: str = "optimal",
) -> Extraction:
    """Extract already path-corrected, nod-differenced SCI using stored PROFILE.

    WHT is inverse variance, even though it inherits SCI's BUNIT header. Signed
    nod ghosts are retained in PROFILE, but the central aperture avoids them.
    No second subtraction of BACKGROUND or application of path_corr is valid.
    """
    if not (science.shape == weight.shape == profile.shape) or science.shape[1] != len(wave):
        raise ValueError("SCI/WHT/PROFILE shapes must agree with wavelength")
    if method not in ("optimal", "boxcar", "profile_plus_background"):
        raise ValueError("Unknown extraction method")
    if radius < 1 or center - radius < 0 or center + radius >= science.shape[0]:
        raise ValueError("Aperture falls outside the spatial array")
    rows = np.arange(center - radius, center + radius + 1)
    s, w, p = science[rows], weight[rows], profile[rows]
    good = np.isfinite(s) & np.isfinite(w) & (w > 0) & np.isfinite(p)
    wg = np.where(good, w, 0)
    sg = np.where(good, s, 0)
    pg = np.where(good, p, 0)
    # Coverage is computed against modeled aperture support before dropping pixels.
    total = np.sum(np.where(np.isfinite(p), np.abs(p), 0), axis=0)
    covered = np.sum(np.abs(pg), axis=0)
    coverage = np.divide(covered, total, out=np.zeros_like(total), where=total > 0)
    if method == "boxcar":
        denominator = pg.sum(axis=0)
        variance = np.sum(np.divide(1, w, out=np.zeros_like(w), where=good), axis=0)
        numerator = sg.sum(axis=0)
        flux = np.divide(
            numerator, denominator, out=np.full_like(denominator, np.nan), where=denominator > 0
        )
        error = np.divide(
            np.sqrt(variance),
            denominator,
            out=np.full_like(denominator, np.nan),
            where=denominator > 0,
        )
    else:
        pp = np.sum(wg * pg**2, axis=0)
        ps = np.sum(wg * pg * sg, axis=0)
        denominator, numerator, variance_numerator = pp, ps, pp
        if method == "profile_plus_background":
            pw = np.sum(wg * pg, axis=0)
            ww = wg.sum(axis=0)
            ss = np.sum(wg * sg, axis=0)
            denominator = pp * ww - pw**2
            numerator = ps * ww - pw * ss
            variance_numerator = ww
        flux = np.divide(
            numerator, denominator, out=np.full_like(denominator, np.nan), where=denominator > 0
        )
        if method == "optimal":
            error = np.sqrt(
                np.divide(
                    1, denominator, out=np.full_like(denominator, np.nan), where=denominator > 0
                )
            )
        else:
            error = np.sqrt(
                np.divide(
                    variance_numerator,
                    denominator,
                    out=np.full_like(denominator, np.nan),
                    where=denominator > 0,
                )
            )
    valid = (
        (coverage >= 0.95)
        & (good.sum(axis=0) >= 2)
        & np.isfinite(flux)
        & np.isfinite(error)
        & (error > 0)
    )
    return Extraction(
        f"2d_{method}_r{radius}",
        wave,
        flux,
        error,
        valid,
        {
            "center_row": center,
            "radius_pixels": radius,
            "quality_rule": "finite SCI/PROFILE, finite positive WHT, >=2 valid rows and >=95% modeled aperture support",
            "excluded_bins": int((~valid).sum()),
            "pathloss_applied_again": False,
            "background_subtracted_again": False,
            "errors": "Propagated WHT diagonal variance; spatial covariance unavailable",
        },
    )


def read_extractions(path: Path) -> tuple[list[Extraction], dict[str, Any]]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != SOURCE_HASH:
        raise ValueError("Source spectrum differs from verified baseline SHA256")
    with fits.open(path, memmap=False) as h:
        table = h["SPEC1D"]
        wave = _column(table, "wave", u.um)
        flux = _column(table, "flux", u.uJy)
        error = _column(table, "err", u.uJy)
        bin_edges(wave)
        valid = np.isfinite(flux) & np.isfinite(error) & (error > 0)
        reasons = {"finite_positive_error": int(valid.sum())}
        for name in ("npix", "profile_sum", "var_sum", "path_corr"):
            if name in table.columns.names:
                values = np.asarray(table.data[name], dtype=float)
                column_valid = np.isfinite(values) & (values > 0)
                valid &= column_valid
                reasons[name + "_excluded"] = int((~column_valid).sum())
        # Future files with flags need explicit handling; the actual product has none.
        for name in ("dq", "DQ"):
            if name in table.columns.names:
                valid &= table.data[name] == 0
        exts = [
            Extraction(
                "stored_pixel_table_1d",
                wave,
                flux,
                error,
                valid,
                {
                    "quality_masks": reasons,
                    "DQ_available": "DQ" in table.columns.names or "dq" in table.columns.names,
                    "quality_limitation": "Per-exposure DQ and PIXTAB are absent; reduction masks cannot be reconstructed",
                },
            )
        ]
        s, w, p = (np.array(h[n].data, dtype=float) for n in ("SCI", "WHT", "PROFILE"))
        center = int(round(table.header["YTRACE"]))
        exts += [
            extract_2d(wave, s, w, p, center=center, radius=r, method=m)
            for m, r in (
                ("optimal", 1),
                ("optimal", 2),
                ("optimal", 3),
                ("boxcar", 1),
                ("boxcar", 2),
                ("profile_plus_background", 3),
            )
        ]
        metadata = {
            "input_sha256": digest,
            "msaexp_version": table.header["VERSION"],
            "grating": table.header["GRATING"],
            "filter": table.header["FILTER"],
            "DQ_extension_available": "DQ" in h,
            "PIXTAB_available": "PIXTAB" in h,
            "WITHPATH": table.header["WITHPATH"],
            "extraction_reference": "https://github.com/gbrammer/msaexp/blob/e2b237b/msaexp/slit_combine.py",
            "extraction_conventions": [
                "SCI is nod-differenced and path-loss corrected before pseudo-drizzle",
                "WHT=1/propagated_variance; inherited BUNIT is not a weight unit",
                "BACKGROUND is a separate sky estimate, not an instruction for second subtraction",
                "SPEC1D is the preferred unresampled pixel-table fit; 2D re-extractions differ in weighting/resampling",
                "PROFILE retains signed negative nod ghosts; normalize only the chosen central aperture",
            ],
        }
    return exts, metadata


def line_matrix(
    wave: np.ndarray,
    resolution_wave: np.ndarray,
    resolution: np.ndarray,
    *,
    redshift: float = 14.44,
    intrinsic_fwhm: float = 0,
    lsf_scale: float = 1,
    blend: str = "equal_HeO",
    components: tuple | list | None = None,
) -> np.ndarray:
    """Bin-integrated Gaussian line densities per unit total line flux.

    Flux units are 1e-20 erg/s/cm2; model densities are those flux units / um.
    An LSF FWHM multiplier >1 broadens the official illuminated-aperture curve.
    Explicit components supply five (vacuum Angstrom wavelengths, weights)
    groups in LINE_NAMES order and are normalized without mutating the caller.
    """
    if lsf_scale <= 0 or intrinsic_fwhm < 0 or redshift <= 0:
        raise ValueError("Invalid line-shape parameters")
    if components is not None:
        if blend != "equal_HeO":
            raise ValueError("Explicit components conflict with named blend rewrite")
        if len(components) != len(LINE_NAMES):
            raise ValueError("Five line groups required for explicit components")
        for group in components:
            if len(group) != 2:
                raise ValueError("Components require wavelengths and weights")
            rests, weights = (np.asarray(value, dtype=float) for value in group)
            if (
                rests.ndim != 1
                or not len(rests)
                or weights.shape != rests.shape
                or not np.all(np.isfinite(rests) & (rests > 0))
                or not np.all(np.isfinite(weights) & (weights >= 0))
                or not np.isfinite(weights.sum())
                or weights.sum() <= 0
            ):
                raise ValueError("Finite positive wavelengths and nonnegative weights required")
    edges = bin_edges(wave)
    models = []
    groups = LINE_COMPONENTS if components is None else components
    for group, (rests, weights) in enumerate(groups):
        if group == 2 and blend == "HeII_only":
            weights = (1, 0, 0)
        elif group == 2 and blend == "OIII_only":
            weights = (0, 1, 2.5)
        if blend == "alternate_multiplets":
            if group == 0:
                rests, weights = (1483.321, 1486.496), (1, 1)
            elif group == 1:
                weights = (1, 1)
            elif group == 4:
                weights = (1.5, 1)
        weights = np.array(weights, dtype=float, copy=True)
        weights /= weights.sum()
        model = np.zeros(len(wave))
        for rest, amplitude in zip(rests, weights):
            center = rest * 1e-4 * (1 + redshift)
            r = np.interp(center, resolution_wave, resolution)
            fwhm = center * np.hypot(lsf_scale / r, intrinsic_fwhm / C_KMS)
            sigma = fwhm / FWHM_TO_SIGMA
            model += amplitude * np.diff(ndtr((edges - center) / sigma)) / np.diff(edges)
        models.append(model)
    return np.column_stack(models)


def covariance_matrix(errors: np.ndarray, indices: np.ndarray, rho: float) -> np.ndarray:
    """Specified AR(1) sensitivity, preserving original separation across masks."""
    if not 0 <= rho < 1 or not np.all(np.isfinite(errors) & (errors > 0)):
        raise ValueError("Invalid covariance inputs")
    corr = rho ** np.abs(indices[:, None] - indices[None, :])
    return errors[:, None] * corr * errors[None, :]


def fieller_set(
    nf: float, df: float, nv: float, dv: float, nd: float, delta_chi2: float
) -> dict[str, Any]:
    """Likelihood-ratio set for a ratio of two jointly Gaussian signed fluxes."""
    aa, bb, cc = (
        df**2 - delta_chi2 * dv,
        -2 * nf * df + 2 * delta_chi2 * nd,
        nf**2 - delta_chi2 * nv,
    )
    discriminant = bb**2 - 4 * aa * cc
    if discriminant < 0:
        return {"type": "all_real" if aa <= 0 else "empty"}
    if aa == 0:
        if bb == 0:
            return {"type": "all_real" if cc <= 0 else "empty"}
        return {
            "type": "half_line",
            "boundary": -cc / bb,
            "direction": "below" if bb > 0 else "above",
        }
    roots = sorted(
        ((-bb - np.sqrt(discriminant)) / (2 * aa), (-bb + np.sqrt(discriminant)) / (2 * aa))
    )
    if aa > 0:
        return {"type": "bounded", "interval": roots}
    return {"type": "two_unbounded_intervals", "excluded_open_interval": roots}


def fit_lines(
    extraction: Extraction,
    resolution_wave: np.ndarray,
    resolution: np.ndarray,
    *,
    redshift: float = 14.44,
    intrinsic_fwhm: float = 0,
    lsf_scale: float = 1,
    rho: float = 0,
    continuum_order: int = 1,
    blend: str = "equal_HeO",
) -> dict[str, Any]:
    wave = extraction.wave
    indices = np.flatnonzero(extraction.valid & (wave >= 2.15) & (wave <= 3.20))
    if len(indices) < 20:
        raise ValueError("Insufficient quality-masked bins in fixed UV fitting window")
    # 1 uJy = 1e-29 erg/s/cm2/Hz. Conversion is central-bin F_lambda per um.
    conversion = 2.99792458e5 / wave**2
    data = extraction.flux[indices] * conversion[indices]
    errors = extraction.error[indices] * conversion[indices]
    covariance = covariance_matrix(errors, indices, rho)
    chol = cholesky(covariance, lower=True)
    x = (wave - 2.675) / 0.525
    # A smooth polynomial in fnu, converted to flam, fitted with all lines.
    continuum = np.polynomial.legendre.legvander(x, continuum_order) * conversion[:, None] / 100
    lines = line_matrix(
        wave,
        resolution_wave,
        resolution,
        redshift=redshift,
        intrinsic_fwhm=intrinsic_fwhm,
        lsf_scale=lsf_scale,
        blend=blend,
    )
    design = np.column_stack((continuum, lines))
    a = solve_triangular(chol, design[indices], lower=True)
    y = solve_triangular(chol, data, lower=True)
    q, r = np.linalg.qr(a, mode="reduced")
    coeffs = np.linalg.solve(r, q.T @ y)
    inverse = np.linalg.inv(r)
    coeff_cov = inverse @ inverse.T
    residual = y - a @ coeffs
    nc = continuum_order + 1
    qc, _ = np.linalg.qr(a[:, :nc], mode="reduced")
    continuum_chi2 = float(np.sum((y - qc @ (qc.T @ y)) ** 2))
    fluxes = coeffs[nc:]
    flux_cov = coeff_cov[nc:, nc:]
    # Conditional Fieller set for (NIV+NIII)/(CIV+CIII); not N/C abundance.
    numerator = np.array([1, 0, 0, 1, 0.0])
    denominator = np.array([0, 1, 0, 0, 1.0])
    nf, df = float(numerator @ fluxes), float(denominator @ fluxes)
    nv, dv, nd = (
        float(numerator @ flux_cov @ numerator),
        float(denominator @ flux_cov @ denominator),
        float(numerator @ flux_cov @ denominator),
    )
    ratios = {}
    for sigma in (1.0, 1.95996398454):
        ratios[str(sigma)] = fieller_set(nf, df, nv, dv, nd, sigma**2)
    return {
        "extraction": extraction.name,
        "redshift": redshift,
        "intrinsic_fwhm_km_s": intrinsic_fwhm,
        "lsf_fwhm_multiplier": lsf_scale,
        "rho_assumed": rho,
        "continuum_fnu_polynomial_order": continuum_order,
        "blend_assumption": blend,
        "bins": len(indices),
        "dof": len(indices) - len(coeffs),
        "chi2": float(residual @ residual),
        "continuum_only_chi2": continuum_chi2,
        "delta_chi2_five_signed_line_groups": continuum_chi2 - float(residual @ residual),
        "line_flux_unit": "1e-20 erg s^-1 cm^-2",
        "lines": {
            n: {
                "flux": float(f),
                "conditional_sigma": float(np.sqrt(v)),
                "signed_conditional_flux_over_sigma": float(f / np.sqrt(v)),
            }
            for n, f, v in zip(LINE_NAMES, fluxes, np.diag(flux_cov))
        },
        "line_covariance": flux_cov.tolist(),
        "nitrogen_lines_over_carbon_lines": {
            "value": nf / df if df != 0 else None,
            "numerator_flux": nf,
            "denominator_flux": df,
            "fieller_normal_68_and_95_sets": ratios,
            "interpretation": "Observed integrated UV line-flux ratio; NOT elemental N/C",
        },
        "model_fnu_uJy": (design @ coeffs / conversion).tolist(),
    }


def redshift_scan(
    extraction: Extraction,
    rw: np.ndarray,
    rr: np.ndarray,
    *,
    rho: float = 0,
    null_draws: int = 1000,
) -> dict[str, Any]:
    """Profile tied redshift and width, and calibrate the stated scan under a null.

    Null simulations assume the same Gaussian covariance model as the fit. The
    statistic allows signed line amplitudes; it is not a new-detection claim.
    """
    grid = np.linspace(14.0, 15.0, 201)
    widths = (0.0, 300.0, 650.0)
    results = [
        fit_lines(extraction, rw, rr, redshift=float(z), intrinsic_fwhm=v, rho=rho)
        for z in grid
        for v in widths
    ]
    chi = np.array([r["chi2"] for r in results]).reshape(len(grid), len(widths))
    zidx, widx = np.unravel_index(np.argmin(chi), chi.shape)
    profile = chi.min(axis=1)
    acceptable = grid[profile <= chi.min() + 1]
    profile_intervals = {}
    for threshold in (1.0, 3.84145882069):
        selected = [
            (r, threshold - (r["chi2"] - chi.min()))
            for r in results
            if r["chi2"] <= chi.min() + threshold
        ]
        profile_intervals[str(threshold)] = {
            n: [
                min(
                    r["lines"][n]["flux"] - np.sqrt(budget) * r["lines"][n]["conditional_sigma"]
                    for r, budget in selected
                ),
                max(
                    r["lines"][n]["flux"] + np.sqrt(budget) * r["lines"][n]["conditional_sigma"]
                    for r, budget in selected
                ),
            ]
            for n in LINE_NAMES
        }
    # Cache whitened orthonormal line subspaces after removing nuisance continuum.
    indices = np.flatnonzero(
        extraction.valid & (extraction.wave >= 2.15) & (extraction.wave <= 3.20)
    )
    wave = extraction.wave
    conversion = 2.99792458e5 / wave**2
    chol = cholesky(
        covariance_matrix(extraction.error[indices] * conversion[indices], indices, rho), lower=True
    )
    continuum = (
        np.polynomial.legendre.legvander((wave - 2.675) / 0.525, 1) * conversion[:, None] / 100
    )
    ac = solve_triangular(chol, continuum[indices], lower=True)
    qc, _ = np.linalg.qr(ac, mode="reduced")
    projections = []
    for z in grid:
        for v in widths:
            a = solve_triangular(
                chol, line_matrix(wave, rw, rr, redshift=z, intrinsic_fwhm=v)[indices], lower=True
            )
            a -= qc @ (qc.T @ a)
            q, _ = np.linalg.qr(a, mode="reduced")
            projections.append(q.T)
    noise = np.random.default_rng(5224277193).normal(size=(len(indices), null_draws))
    maxima = np.zeros(null_draws)
    for projection in projections:
        maxima = np.maximum(maxima, np.sum((projection @ noise) ** 2, axis=0))
    observed = results[zidx * len(widths) + widx]["delta_chi2_five_signed_line_groups"]
    exceed = int(np.sum(maxima >= observed))
    return {
        "z_grid": grid.tolist(),
        "width_grid_km_s": list(widths),
        "profile_chi2": profile.tolist(),
        "best_fit": results[zidx * len(widths) + widx],
        "delta_chi2_1_profile_envelope_z": [float(acceptable.min()), float(acceptable.max())],
        "line_flux_profile_intervals_delta_chi2_1_and_3_84": profile_intervals,
        "profile_interval_interpretation": "Profiles over the stated tied z/width grid and all linear nuisance amplitudes; remains conditional on LSF, blends, continuum and covariance",
        "grid_boundary_best": bool(zidx in (0, len(grid) - 1) or widx in (0, len(widths) - 1)),
        "rho_assumed": rho,
        "conditional_null_scan": {
            "statistic": "Maximum continuum chi2 improvement from five signed UV groups across stated z/width grid",
            "draws": null_draws,
            "seed": 5224277193,
            "exceedances": exceed,
            "plus_one_p": (exceed + 1) / (null_draws + 1),
            "monte_carlo_resolution": 1 / (null_draws + 1),
            "null_max_quantiles_50_95_99": np.quantile(maxima, [0.5, 0.95, 0.99]).tolist(),
            "limitations": "Conditional Gaussian null only; no selection, continuum/model errors, unknown covariance or reduction systematics",
        },
    }


def run(spectrum: Path, resolution_path: Path, output: Path, null_draws: int) -> dict[str, Any]:
    exts, metadata = read_extractions(spectrum)
    rw, rr, resolution_metadata = read_resolution(resolution_path)
    scenarios = [fit_lines(e, rw, rr, rho=rho) for e in exts for rho in (0.0, 0.25, 0.5)]
    scenarios += [fit_lines(exts[0], rw, rr, lsf_scale=s) for s in (0.7, 1.3)]
    scenarios += [fit_lines(exts[0], rw, rr, intrinsic_fwhm=v) for v in (300.0, 650.0)]
    scenarios += [fit_lines(exts[0], rw, rr, continuum_order=d) for d in (0, 2, 3)]
    scenarios += [
        fit_lines(exts[0], rw, rr, blend=b)
        for b in ("HeII_only", "OIII_only", "alternate_multiplets")
    ]
    scans = [redshift_scan(exts[0], rw, rr, rho=rho, null_draws=null_draws) for rho in (0.0, 0.5)]
    report = {
        "schema_version": "mom_line_sensitivity_v1",
        "metadata": metadata,
        "resolution": resolution_metadata,
        "resolution_at_published_group_centers": {
            n: float(np.interp(np.average(rest, weights=w) * 1e-4 * 15.44, rw, rr))
            for n, (rest, w) in zip(LINE_NAMES, LINE_COMPONENTS)
        },
        "extractions": [dict(name=e.name, **e.notes) for e in exts],
        "fixed_published_redshift_scenarios": scenarios,
        "tied_redshift_width_scans": scans,
        "interpretation": [
            "Signed amplitudes avoid positivity/upper-limit truncation bias; negative estimates are retained",
            "Sigma and Fieller sets condition on z, width, continuum, multiplet ratios and the specified covariance",
            "rho is an assumed sensitivity parameter; there is no measured empirical spectral covariance matrix",
            "2D errors propagate the available weights; spatial covariance and raw exposure DQ are unavailable",
            "A Gaussian nominal illuminated-slit LSF is a baseline, not the calibrated point-source UNITE LSF",
            "Resolution scalings and blend choices are sensitivity scenarios, not posterior probabilities",
            "UV line ratios are not elemental ratios without density, temperature, ionization and emissivity modelling",
            "Alternative extracted spectra share all exposures and cannot be treated as independent confirmations",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--spectrum", type=Path, default=Path("data_sources/pilot/mom_z14_dja_v4.spec.fits")
    )
    parser.add_argument(
        "--resolution", type=Path, default=Path("data_sources/pilot/jwst_nirspec_prism_disp.fits")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("research_output/mom_z14_line_sensitivity.json")
    )
    parser.add_argument("--null-draws", type=int, default=1000)
    args = parser.parse_args()
    if args.null_draws < 100:
        parser.error("At least 100 null draws are required")
    run(args.spectrum, args.resolution, args.output, args.null_draws)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
