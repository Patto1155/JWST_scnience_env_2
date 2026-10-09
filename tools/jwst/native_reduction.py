"""Independent, native-column MoM-z14 extraction with shared-nod covariance.

This is not a reconstruction of the author's unavailable PIXTAB.  It starts from
the official, already nod-subtracted CAL products and never subtracts nods twice.
The point-source hypothesis, continuum spatial profile and covariance transport
are explicit, falsifiable assumptions, not a calibrated abundance measurement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits
from scipy.linalg import cholesky, solve_triangular
from scipy.optimize import nnls
from scipy.special import ndtr

from .line_sensitivity import (
    LINE_NAMES,
    SOURCE_HASH,
    fieller_set,
    line_matrix,
    read_resolution,
)
from .point_resolution import read_point_resolution

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "data_sources/followup/mom_native_inventory.json"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256")
    return digest.hexdigest()


def point_conversion(
    pixel_area: float, uniform: np.ndarray, point: np.ndarray, bar: np.ndarray
) -> np.ndarray:
    """Convert UNIFORM/barshadow-corrected MJy/sr to POINT-calibrated uJy.

    Undo the existing uniform pathloss and extended-only barshadow correction,
    then apply point pathloss once.  MJy/sr * sr * 1e12 = uJy.
    """
    if not np.isfinite(pixel_area) or pixel_area <= 0:
        raise ValueError("Positive nominal pixel solid angle required")
    return pixel_area * 1e12 * uniform * bar / point


def mixing_matrix(count: int = 3) -> np.ndarray:
    if count < 2:
        raise ValueError("At least two nods needed")
    return np.eye(count) - (1 - np.eye(count)) / (count - 1)


def recover_raw_variance(post_variance: np.ndarray, mixing: np.ndarray) -> np.ndarray:
    """Invert diagonal variance propagation, not the singular SCI subtraction.

    For three nods D_i=V_i+(V_j+V_k)/4.  This does not recover the missing
    common background signal or assume that post-subtraction nods are independent.
    """
    return np.linalg.solve(mixing**2, post_variance.reshape(len(mixing), -1)).reshape(
        post_variance.shape
    )


def shared_extraction_covariance(
    raw_variance: np.ndarray, operators: np.ndarray, mixing: np.ndarray
) -> np.ndarray:
    """Same-column covariance from shared raw nod pixels and extraction weights."""
    count, _, columns = operators.shape
    result = np.zeros((columns, count, count))
    for i in range(count):
        for j in range(count):
            shared = np.einsum("k,krc->rc", mixing[i] * mixing[j], raw_variance)
            result[:, i, j] = np.sum(operators[i] * operators[j] * shared, axis=0)
    return result


def gaussian_profile(trace: np.ndarray, sigma: float, rows: int) -> np.ndarray:
    if sigma <= 0:
        raise ValueError("Positive spatial sigma required")
    yy = np.arange(rows)[:, None]
    return ndtr((yy + 0.5 - trace) / sigma) - ndtr((yy - 0.5 - trace) / sigma)


def read_inputs(native_dir: Path, spectrum: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if sha256(spectrum) != SOURCE_HASH:
        raise ValueError("Source spectrum differs from pinned identity")
    inventory = json.loads(INVENTORY.read_text())
    with fits.open(spectrum) as hdul:
        rows = hdul["SLITS"].data.copy()
    expected = {p["source_slits_filename"]: p for p in inventory["products"]}
    if len(rows) != 9 or set(map(str, rows["filename"])) != set(expected):
        raise ValueError("Exactly the pinned nine unique exposures are required")
    data = []
    for row in rows:
        pin = expected[str(row["filename"])]
        path = native_dir / pin["filename"]
        if path.stat().st_size != pin["expected_bytes"] or sha256(path) != pin["sha256"]:
            raise ValueError("Native CAL bytes differ from pinned inventory")
        with fits.open(path, memmap=False) as hdul:
            sci = next(
                h for h in hdul if h.name == "SCI" and h.header.get("SRCNAME") == "5224_277193"
            )
            version, header, primary = sci.header["EXTVER"], sci.header, hdul[0].header
            arrays = {
                name: np.asarray(hdul[name, version].data, dtype=float).copy()
                for name in ("SCI", "ERR", "WAVELENGTH", "PATHLOSS_PS", "PATHLOSS_UN", "BARSHADOW")
            }
            if any(array.shape != (28, 423) for array in arrays.values()):
                raise ValueError("Pinned native target arrays must all have shape28x423")
            origin = (int(header["SLTSTRT1"]), int(header["SLTSTRT2"]))
            if origin != (440, 1293):
                raise ValueError("Native detector origin differs from pinned shared-pixel geometry")
            wave_unit = hdul["WAVELENGTH", version].header.get("BUNIT")
            if wave_unit not in (None, "um", "micron", "microns"):
                raise ValueError("Unsupported native wavelength units")
            finite_wave = arrays["WAVELENGTH"][np.isfinite(arrays["WAVELENGTH"])]
            if not np.all((finite_wave > 0.3) & (finite_wave < 6.0)):
                raise ValueError("Native wavelength range inconsistent with micron contract")
            if primary["CAL_VER"] != "2.0.1" or primary["DETECTOR"] != "NRS2":
                raise ValueError("Unsupported native calibration version/detector")
            dq = np.asarray(hdul["DQ", version].data, dtype=np.uint32)
            text = hdul["ASDF"].data["ASDF_METADATA"][0].tobytes().decode("utf-8", errors="replace")
        if (
            header["SRCTYPE"],
            header["PTHLOSS"],
            header["BARSHDW"],
            primary["S_BKDSUB"],
            header["BUNIT"],
        ) != ("EXTENDED", "UNIFORM", True, "COMPLETE", "MJy/sr"):
            raise ValueError("Unsupported calibration state: conversion would double-correct")
        if abs(header["SRCRA"] - 150.0933255) > 1e-7 or abs(header["SRCDEC"] - 2.2731627) > 1e-7:
            raise ValueError("Native source identity mismatch")
        match = re.search(r"Step bkg_subtract running with args.*?\[(.*?)\]\)", text, re.S)
        if match is None:
            raise ValueError("Actual embedded background contributor log required")
        contributors = re.findall(r"jw\d{11}_\d{5}_\d{5}_nrs2_rate\.fits", match.group(1))
        if len(contributors) != 2 or len(set(contributors)) != 2:
            raise ValueError("Expected two distinct logged background contributors")
        # The versioned author's SLITS base polynomial is a geometry seed, not
        # their optimized trace/extraction. Transform its old cutout coordinates.
        columns = arrays["SCI"].shape[1]
        old_x = np.arange(columns) + header["SLTSTRT1"] - row["xstart"]
        xi = (old_x - row["xsize"] / 2) / row["xsize"]
        trace = np.polyval([row["trace_c0"], row["trace_c1"], row["trace_c2"]], xi)
        trace += row["ystart"] - header["SLTSTRT2"]
        good = (
            ((dq & 3) == 0)
            & np.isfinite(arrays["SCI"])
            & np.isfinite(arrays["ERR"])
            & (arrays["ERR"] > 0)
        )
        for name in ("WAVELENGTH", "PATHLOSS_PS", "PATHLOSS_UN", "BARSHADOW"):
            good &= np.isfinite(arrays[name]) & (arrays[name] > 0)
        conversion = point_conversion(
            header["PIXAR_SR"], arrays["PATHLOSS_UN"], arrays["PATHLOSS_PS"], arrays["BARSHADOW"]
        )
        # Undo point pathloss here so all nod subtractions share a detector-pixel
        # calibration. Its source-dependent response enters the profile model.
        common_conversion = conversion * arrays["PATHLOSS_PS"]
        data.append(
            {
                "filename": path.name,
                "sha256": pin["sha256"],
                "group": primary["VISITGRP"],
                "nod": int(row["position_number"]),
                "background_contributors": contributors,
                "science": arrays["SCI"] * common_conversion,
                "variance": (arrays["ERR"] * common_conversion) ** 2,
                "point_pathloss": arrays["PATHLOSS_PS"],
                "wave": arrays["WAVELENGTH"],
                "trace_seed": trace,
                "good": good,
                "pixel_area_sr": header["PIXAR_SR"],
                "source_xpos": header["SRCXPOS"],
                "source_ypos": header["SRCYPOS"],
                "detector_origin": origin,
                "point_conversion_uv_median": float(
                    np.nanmedian(
                        conversion[(arrays["WAVELENGTH"] > 2.15) & (arrays["WAVELENGTH"] < 3.2)]
                    )
                ),
            }
        )
    for group in sorted({d["group"] for d in data}):
        members = [d for d in data if d["group"] == group]
        if sorted(d["nod"] for d in members) != [1, 2, 3]:
            raise ValueError("Complete three-nod groups required")
        rates = {d["filename"].replace("_cal", "_rate") for d in members}
        for d in members:
            if set(d["background_contributors"]) != rates - {
                d["filename"].replace("_cal", "_rate")
            }:
                raise ValueError("Unexpected contributor incidence; covariance model invalid")
        common_good = np.all(np.array([d["good"] for d in members]), axis=0)
        for d in members:
            if not np.allclose(
                d["wave"][common_good], members[0]["wave"][common_good], rtol=0, atol=2e-6
            ):
                raise ValueError(
                    "Nod native wavelength grids do not align on shared detector pixels"
                )
        for d in members:
            d["good"] &= common_good
    return data, {
        "source_spectrum_sha256": SOURCE_HASH,
        "native_inventory_sha256": sha256(INVENTORY),
        "calibration": (
            "official 2.0.1 / jwst_1535.pmap; EXTENDED/UNIFORM/barshadow; already nod-subtracted"
        ),
        "native_geometry_seed": (
            "versioned SLITS base polynomial; transformed old/new cutout "
            "origins; independently refined off UV lines"
        ),
        "point_lsf_empirically_calibrated": False,
        "wavelength_unit_contract": (
            "Pinned JWST2.0.1 WAVELENGTH values in microns; BUNIT absent in exact originals; "
            "reject conflicting labels/range and misaligned detector grids"
        ),
    }


def signed_profiles(data: list[dict], sigma: float, offset: float) -> np.ndarray:
    profiles = np.array(
        [
            gaussian_profile(d["trace_seed"] + offset, sigma, d["science"].shape[0])
            * d["point_pathloss"]
            for d in data
        ]
    )
    result = np.zeros_like(profiles)
    for i, d in enumerate(data):
        members = [j for j, other in enumerate(data) if other["group"] == d["group"]]
        result[i] = profiles[i] - sum(profiles[j] for j in members if j != i) / 2
    return result


def extract_columns(
    data: list[dict],
    profiles: np.ndarray,
    background_order: int = 1,
    selected_columns: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Linear profile+nuisance extraction on unchanged detector columns."""
    shape = profiles.shape
    flux, operators = np.full((shape[0], shape[2]), np.nan), np.zeros(shape)
    residuals = np.full(shape, np.nan)
    yy = (np.arange(shape[1]) - shape[1] / 2) / shape[1]
    for i, d in enumerate(data):
        for column in range(shape[2]) if selected_columns is None else selected_columns:
            valid = d["good"][:, column]
            if valid.sum() < 8:
                continue
            design = np.column_stack(
                [profiles[i, :, column]] + [yy**order for order in range(background_order + 1)]
            )
            weighted = design[valid] / np.sqrt(d["variance"][valid, column, None])
            if np.linalg.matrix_rank(weighted) != weighted.shape[1]:
                continue
            inverse = np.linalg.inv(weighted.T @ weighted)
            coefficient = (
                inverse
                @ weighted.T
                @ (d["science"][valid, column] / np.sqrt(d["variance"][valid, column]))
            )
            operators[i, valid, column] = (inverse @ weighted.T)[0] / np.sqrt(
                d["variance"][valid, column]
            )
            flux[i, column] = coefficient[0]
            residuals[i, valid, column] = (
                d["science"][valid, column] - design[valid] @ coefficient
            ) / np.sqrt(d["variance"][valid, column])
    return flux, operators, residuals


def fit_geometry(data: list[dict]) -> dict[str, Any]:
    # No tested UV-line samples enter geometry selection. Red continuum only.
    offset_grid, sigma_grid = np.linspace(-0.6, 0.6, 13), np.linspace(0.45, 1.15, 15)
    trials = []
    continuum_columns = np.flatnonzero(
        np.any((data[0]["wave"] > 3.35) & (data[0]["wave"] < 4.45), axis=0)
    )
    for sigma in sigma_grid:
        for offset in offset_grid:
            profile = signed_profiles(data, float(sigma), float(offset))
            _, _, residuals = extract_columns(data, profile, selected_columns=continuum_columns)
            selection = np.array([(d["wave"] > 3.35) & (d["wave"] < 4.45) for d in data])
            trials.append(
                (float(np.nansum(residuals[selection] ** 2)), float(sigma), float(offset))
            )
    best = min(trials)
    accepted = [t for t in trials if t[0] <= best[0] + 2.30]
    return {
        "sigma_pixels": best[1],
        "offset_pixels": best[2],
        "diagonal_spatial_chi2": best[0],
        "continuum_window_um": [3.35, 4.45],
        "tested_uv_lines_excluded": True,
        "conditional_delta_chi2_2p3_grid_envelope_sigma": [
            min(t[1] for t in accepted),
            max(t[1] for t in accepted),
        ],
        "conditional_delta_chi2_2p3_grid_envelope_offset": [
            min(t[2] for t in accepted),
            max(t[2] for t in accepted),
        ],
        "grid_boundary_best": best[1] in (sigma_grid[0], sigma_grid[-1])
        or best[2] in (offset_grid[0], offset_grid[-1]),
        "interpretation": (
            "Conditional Gaussian spatial illumination under shared-nod profile "
            "model; not spectral LSF calibration or independent confidence "
            "region"
        ),
    }


def covariance_blocks(data: list[dict], operators: np.ndarray) -> tuple[np.ndarray, dict]:
    count, _, columns = operators.shape
    covariance = np.zeros((columns, count, count))
    records = []
    for group in sorted({d["group"] for d in data}):
        members = [i for i, d in enumerate(data) if d["group"] == group]
        post = np.array([data[i]["variance"] for i in members])
        good = np.all(np.array([data[i]["good"] for i in members]), axis=0)
        # The official diagonal variance may include unequal flat/Poisson terms;
        # negative recovered components invalidate that pixel's analytic model.
        safe_post = np.where(np.isfinite(post), post, 0)
        raw = recover_raw_variance(safe_post, mixing_matrix())
        negative = np.any(raw <= 0, axis=0) & good
        # Actual CAL variances falsify an exact linear demix in some pixels.
        # Reconcile with a nonnegative least-squares model, then add independent
        # diagonal remainder wherever it otherwise underestimates observed ERR.
        for row, column in zip(*np.nonzero(negative)):
            values = safe_post[:, row, column]
            scale = np.max(values)
            raw[:, row, column] = nnls(mixing_matrix() ** 2, values / scale)[0] * scale
        raw = np.where(good[None], np.maximum(raw, 0), 0)
        local = shared_extraction_covariance(raw, operators[members], mixing_matrix())
        predicted_post = np.einsum("ij,jrc->irc", mixing_matrix() ** 2, raw)
        remainder = np.maximum(safe_post - predicted_post, 0)
        for ii in range(len(members)):
            local[:, ii, ii] += np.sum(operators[members[ii]] ** 2 * remainder[ii], axis=0)
        for ii, i in enumerate(members):
            for jj, j in enumerate(members):
                covariance[:, i, j] = local[:, ii, jj]
        records.append(
            {
                "group": group,
                "mixing": mixing_matrix().tolist(),
                "common_usable_pixels": int(good.sum()),
                "negative_inferred_raw_pixels": int(negative.sum()),
                "negative_uv_window_pixels": int(
                    np.sum(
                        negative
                        & (data[members[0]]["wave"] > 2.15)
                        & (data[members[0]]["wave"] < 3.20)
                    )
                ),
                "variance_reconciliation": (
                    "Nonnegative least squares at failed pixels; positive independent "
                    "diagonal remainder; never silently clip negative raw variances"
                ),
                "assumption": (
                    "Linear mean-background variance approximate; independent "
                    "pre-subtraction rate pixels; flat/reference/clipping terms not "
                    "separately known"
                ),
            }
        )
    return covariance, {
        "groups": records,
        "cross_group_shared_calibration_covariance_measured": False,
    }


def empirical_noise(
    data: list[dict], geometry: dict, selected: np.ndarray
) -> tuple[np.ndarray, dict]:
    """Estimate stationary spectral correlations from off-source raw CAL pixels.

    Whole source/negative-ghost trace union is excluded. Three groups, overlapping
    row controls and wavelengths are not an independent calibration ensemble.
    """
    traces = np.array([d["trace_seed"] + geometry["offset_pixels"] for d in data])
    yy = np.arange(data[0]["science"].shape[0])[:, None]
    blank = np.all(np.abs(yy[None] - traces[:, None, :]) > 2.5, axis=0)
    records, all_controls = [], []
    for d in data:
        selected_mask = np.zeros(d["good"].shape[1], dtype=bool)
        selected_mask[selected] = True
        mask = blank & d["good"] & selected_mask[None]
        normalized = d["science"] / np.sqrt(d["variance"])
        # Remove each control row's UV-window constant; this estimator does not
        # subtract source samples or mask by positive/negative flux.
        control = np.full_like(normalized, np.nan)
        for row in range(len(control)):
            good = mask[row]
            if good.sum() >= 20:
                control[row, good] = normalized[row, good] - np.mean(normalized[row, good])
        valid = np.isfinite(control)
        records.append(
            {
                "filename": d["filename"],
                "off_trace_pixels": int(valid.sum()),
                "off_trace_rows": int(np.any(valid, axis=1).sum()),
                "normalized_rms": float(np.sqrt(np.nanmean(control**2))),
            }
        )
        all_controls.append(control)
    controls = np.array(all_controls)
    scale2 = float(np.nanmean(controls**2))
    shared_records = []
    jackknife_scale2 = []
    for group in sorted({d["group"] for d in data}):
        members = [i for i, d in enumerate(data) if d["group"] == group]
        local = controls[members].reshape(3, -1)
        valid = np.all(np.isfinite(local), axis=0)
        shared_records.append(
            {
                "group": group,
                "shared_control_pixels": int(valid.sum()),
                "measured_same_pixel_nod_correlation": np.corrcoef(local[:, valid]).tolist(),
            }
        )
        others = [i for i, d in enumerate(data) if d["group"] != group]
        jackknife_scale2.append(float(np.nanmean(controls[others] ** 2)))
    lags, pairs = [1.0], []
    for lag in range(1, 4):
        a, b = controls[:, :, :-lag], controls[:, :, lag:]
        valid = np.isfinite(a) & np.isfinite(b)
        pairs.append(int(valid.sum()))
        lags.append(float(np.mean(a[valid] * b[valid]) / scale2))
    spatial_lags, spatial_pairs = [1.0], []
    for lag in range(1, 4):
        a, b = controls[:, :-lag, :], controls[:, lag:, :]
        valid = np.isfinite(a) & np.isfinite(b)
        spatial_pairs.append(int(valid.sum()))
        spatial_lags.append(float(np.mean(a[valid] * b[valid]) / scale2))
    separation = np.abs(selected[:, None] - selected[None, :])
    # A compact tapered kernel is an explicit transport model for measured lags.
    kernel = np.zeros_like(separation, dtype=float)
    for lag, value in enumerate(lags):
        kernel[separation == lag] = value * (1 - lag / 4)
    minimum = float(np.linalg.eigvalsh(kernel).min())
    shrinkage = max(0.0, (0.10 - minimum) / (1 - minimum)) if minimum < 0.10 else 0.0
    kernel = (1 - shrinkage) * kernel + shrinkage * np.eye(len(kernel))
    return kernel, {
        "controls": records,
        "pooled_scale_squared": scale2,
        "leave_one_group_out_scale_squared_range": [min(jackknife_scale2), max(jackknife_scale2)],
        "observed_same_pixel_nod_correlations": shared_records,
        "measured_lag_correlations_0_to_3": lags,
        "lag_pair_counts": pairs,
        "measured_spatial_lag_correlations_0_to_3": spatial_lags,
        "spatial_lag_pair_counts": spatial_pairs,
        "spatial_correlations_in_source_covariance": False,
        "stationary_kernel_taper": "Bartlett through lag3; zero beyond3",
        "identity_shrinkage_to_minimum_eigenvalue_0p1": shrinkage,
        "kernel_minimum_eigenvalue": float(np.linalg.eigvalsh(kernel).min()),
        "scope": (
            "Measured off-source+negative-ghost-union controls, conditional "
            "stationary transport to source extraction; correlated nods/rows "
            "are not independent draws; no calibrated interval"
        ),
    }


def fit_native(
    data: list[dict],
    flux: np.ndarray,
    blocks: np.ndarray,
    selected: np.ndarray,
    resolution_wave: np.ndarray,
    resolution: np.ndarray,
    *,
    kernel: np.ndarray | None = None,
    noise_scale: float = 1,
    members: list[int] | None = None,
    wavelength_offset_pixels: float = 0,
) -> dict:
    if members is None:
        members = list(range(len(data)))
    observed, designs = [], []
    for i in members:
        trace = data[i].get("trace_refined", data[i]["trace_seed"])
        profile = gaussian_profile(
            trace, data[i].get("sigma_refined", 0.75), data[i]["science"].shape[0]
        )
        good = data[i]["good"]
        wavelength_weight = np.sum(profile * good, axis=0)
        wave = np.divide(
            np.sum(np.where(good, data[i]["wave"], 0) * profile, axis=0),
            wavelength_weight,
            out=np.full_like(wavelength_weight, np.nan),
            where=wavelength_weight > 0,
        )
        wave += wavelength_offset_pixels * np.gradient(wave)
        # Preserve native full-grid bin edges; no interpolation of science data.
        finite = np.isfinite(wave)
        if not np.all(finite):
            wave = np.interp(np.arange(len(wave)), np.flatnonzero(finite), wave[finite])
            locations = np.flatnonzero(finite)
            left_slope = wave[locations[1]] - wave[locations[0]]
            right_slope = wave[locations[-1]] - wave[locations[-2]]
            wave[: locations[0]] = (
                wave[locations[0]] + (np.arange(locations[0]) - locations[0]) * left_slope
            )
            wave[locations[-1] + 1 :] = (
                wave[locations[-1]]
                + (np.arange(locations[-1] + 1, len(wave)) - locations[-1]) * right_slope
            )
        # Edge rows can have zero wavelength; source columns in the fixed UV
        # window must be finite/strictly ordered before constructing templates.
        if np.any(np.diff(wave) <= 0):
            raise ValueError("Native source wavelength grid not strictly ordered")
        conversion = 2.99792458e5 / wave**2
        continuum = np.polynomial.legendre.legvander((wave - 2.675) / 0.525, 1) / 100
        lines = line_matrix(wave, resolution_wave, resolution) / conversion[:, None]
        designs.append(np.column_stack([continuum, lines])[selected])
        observed.append(flux[i, selected])
    # Column-major ordering permits a source-exposure covariance block per column.
    design = np.transpose(designs, (1, 0, 2)).reshape(-1, 7)
    values = np.array(observed).T.reshape(-1)
    local_blocks = blocks[selected][:, members][:, :, members]
    factors = np.array([cholesky(block, lower=True) for block in local_blocks])
    count = len(members)
    if kernel is None:
        kernel = np.eye(len(selected))
    covariance = (
        np.einsum("cae,cd,dbe->cadb", factors, kernel, factors).reshape(len(values), len(values))
        * noise_scale
    )
    chol = cholesky(covariance, lower=True)
    a = solve_triangular(chol, design, lower=True)
    y = solve_triangular(chol, values, lower=True)
    q, r = np.linalg.qr(a, mode="reduced")
    coefficients = np.linalg.solve(r, q.T @ y)
    inverse = np.linalg.inv(r)
    coefficient_covariance = inverse @ inverse.T
    residual = y - a @ coefficients
    line_flux, line_cov = coefficients[2:], coefficient_covariance[2:, 2:]
    nvec, cvec = np.array([1, 0, 0, 1, 0]), np.array([0, 1, 0, 0, 1])
    nf, cf = float(nvec @ line_flux), float(cvec @ line_flux)
    result = {
        "line_order": list(LINE_NAMES),
        "flux_units": "1e-20 erg s^-1 cm^-2",
        "fluxes": line_flux.tolist(),
        "flux_covariance": line_cov.tolist(),
        "lines": {
            name: {"flux": float(line_flux[j]), "conditional_sigma": float(np.sqrt(line_cov[j, j]))}
            for j, name in enumerate(LINE_NAMES)
        },
        "conditional_chi2": float(residual @ residual),
        "dof": len(values) - 7,
        "native_columns": len(selected),
        "exposure_indices": members,
        "redshift_fixed": 14.44,
        "intrinsic_width_fixed_kms": 0,
        "wavelength_offset_pixels_assumed": wavelength_offset_pixels,
        "nitrogen_carbon_line_flux_ratio": nf / cf,
        "ratio_fieller_95": fieller_set(
            nf,
            cf,
            float(nvec @ line_cov @ nvec),
            float(cvec @ line_cov @ cvec),
            float(nvec @ line_cov @ cvec),
            3.84145882069,
        ),
        "covariance_dimension": len(values),
        "empirical_stationary_noise_scale_squared": noise_scale,
        "continuum_coefficients_uJy_times100": coefficients[:2].tolist(),
        "interpretation": (
            "Signed UV group fluxes under source/profile/LSF/covariance "
            "assumptions; no elemental abundance or independent detection claim"
        ),
    }
    if count > 1:
        diagonal = np.sqrt(np.diagonal(local_blocks, axis1=1, axis2=2))
        corr = local_blocks / diagonal[:, :, None] / diagonal[:, None, :]
        result["median_exposure_amplitude_correlation"] = np.median(corr, axis=0).tolist()
    return result


def run(native_dir: Path, spectrum: Path, output: Path) -> dict:
    data, metadata = read_inputs(native_dir, spectrum)
    geometry = fit_geometry(data)
    for d in data:
        d["trace_refined"] = d["trace_seed"] + geometry["offset_pixels"]
        d["sigma_refined"] = geometry["sigma_pixels"]
    profiles = signed_profiles(data, geometry["sigma_pixels"], geometry["offset_pixels"])
    flux, operators, _ = extract_columns(data, profiles)
    blocks, covariance_metadata = covariance_blocks(data, operators)
    wave = np.nanmedian(data[0]["wave"], axis=0)
    # Use physical wavelength window and coverage only, never source flux/SNR.
    selected = np.flatnonzero(
        (wave > 2.15)
        & (wave < 3.20)
        & np.all(np.isfinite(flux), axis=0)
        & np.all(np.diagonal(blocks, axis1=1, axis2=2) > 0, axis=1)
    )
    if len(selected) < 20:
        raise ValueError("Insufficient native UV-column support")
    kernel, noise = empirical_noise(data, geometry, selected)
    rw, rr, resolution_meta = read_resolution(
        ROOT / "data_sources/pilot/jwst_nirspec_prism_disp.fits"
    )
    pw, pr, point_meta = read_point_resolution(
        ROOT / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    scenarios = []
    for label, wave_r, r, use_kernel, scale in [
        ("nominal_shared_formal", rw, rr, None, 1),
        ("point_shared_formal", pw, pr, None, 1),
        ("nominal_empirical_offtrace_transport", rw, rr, kernel, noise["pooled_scale_squared"]),
        ("point_empirical_offtrace_transport", pw, pr, kernel, noise["pooled_scale_squared"]),
    ]:
        scenarios.append(
            {
                "name": label,
                "fit": fit_native(
                    data, flux, blocks, selected, wave_r, r, kernel=use_kernel, noise_scale=scale
                ),
            }
        )
    splits = []
    for kind in ("group", "nod"):
        for value in sorted({d[kind] for d in data}):
            members = [i for i, d in enumerate(data) if d[kind] == value]
            splits.append(
                {
                    "kind": kind,
                    "value": value,
                    "fit": fit_native(
                        data,
                        flux,
                        blocks,
                        selected,
                        pw,
                        pr,
                        kernel=kernel,
                        noise_scale=noise["pooled_scale_squared"],
                        members=members,
                    ),
                    "independence": (
                        "Disjoint group RATE inputs; shared reference calibration remains"
                    )
                    if kind == "group"
                    else (
                        "Different nod products reuse the same group RATE backgrounds; not "
                        "independent"
                    ),
                }
            )
    sensitivities = []
    for offset in (-0.25, 0.25):
        sensitivities.append(
            {
                "name": "point_wavelength_shift",
                "assumed_shift_pixels": offset,
                "fit": fit_native(
                    data,
                    flux,
                    blocks,
                    selected,
                    pw,
                    pr,
                    kernel=kernel,
                    noise_scale=noise["pooled_scale_squared"],
                    wavelength_offset_pixels=offset,
                ),
            }
        )
    for sigma, offset, order in [
        (0.65, 0.2, 1),
        (0.95, 0.2, 1),
        (0.8, 0.1, 1),
        (0.8, 0.3, 1),
        (0.8, 0.2, 0),
    ]:
        changed_profiles = signed_profiles(data, sigma, offset)
        changed_flux, changed_operators, _ = extract_columns(data, changed_profiles, order)
        changed_blocks, _ = covariance_blocks(data, changed_operators)
        for d in data:
            d["trace_refined"], d["sigma_refined"] = d["trace_seed"] + offset, sigma
        sensitivities.append(
            {
                "name": "point_spatial_extraction_sensitivity",
                "assumed_spatial_sigma_pixels": sigma,
                "assumed_trace_offset_pixels": offset,
                "residual_background_polynomial_order": order,
                "noise_controls": (
                    "Baseline off-trace transport frozen; alternatives are sensitivities, "
                    "not posterior draws"
                ),
                "fit": fit_native(
                    data,
                    changed_flux,
                    changed_blocks,
                    selected,
                    pw,
                    pr,
                    kernel=kernel,
                    noise_scale=noise["pooled_scale_squared"],
                ),
            }
        )
    for d in data:
        d["trace_refined"], d["sigma_refined"] = (
            d["trace_seed"] + geometry["offset_pixels"],
            geometry["sigma_pixels"],
        )
    group_fits = [s["fit"] for s in splits if s["kind"] == "group"]
    inverse_covariances = [np.linalg.inv(np.array(s["flux_covariance"])) for s in group_fits]
    common_covariance = np.linalg.inv(sum(inverse_covariances))
    common_flux = common_covariance @ sum(
        precision @ np.array(s["fluxes"]) for precision, s in zip(inverse_covariances, group_fits)
    )
    consistency_chi2 = sum(
        float(
            (np.array(s["fluxes"]) - common_flux)
            @ precision
            @ (np.array(s["fluxes"]) - common_flux)
        )
        for precision, s in zip(inverse_covariances, group_fits)
    )
    serial_metadata = [
        {
            k: d[k]
            for k in (
                "filename",
                "sha256",
                "group",
                "nod",
                "background_contributors",
                "pixel_area_sr",
                "source_xpos",
                "source_ypos",
                "detector_origin",
                "point_conversion_uv_median",
            )
        }
        for d in data
    ]
    result = {
        "schema_version": 1,
        "metadata": metadata,
        "exposures": serial_metadata,
        "geometry": geometry,
        "covariance": covariance_metadata,
        "empirical_noise": noise,
        "resolution": {"nominal": resolution_meta, "generic_point": point_meta},
        "selected_native_columns": selected.tolist(),
        "selected_reference_wave_um": wave[selected].tolist(),
        "scenarios": scenarios,
        "group_and_nod_splits": splits,
        "sensitivities": sensitivities,
        "conditional_group_line_consistency": {
            "chi2": consistency_chi2,
            "dof": 10,
            "common_five_fluxes": common_flux.tolist(),
            "scope": (
                "Three groups with separate continuum fits and disjoint RATE inputs; "
                "conditional on covariances; cross-group calibration not measured"
            ),
        },
        "limitations": [
            "Independent CAL-column reduction, not exact author PIXTAB reconstruction",
            (
                "Source spatial geometry refined from continuum; source-specific "
                "spectral LSF/wavecorr not calibrated"
            ),
            (
                "Point-source uniform/barshadow restoration and stored pathloss are "
                "hypotheses; finite source size remains"
            ),
            (
                "Analytic shared-nod variance plus empirical stationary off-trace "
                "transport is not an independently calibrated posterior"
            ),
            (
                "Only three groups; common references and flat/background "
                "calibration across groups remain unmeasured"
            ),
            (
                "Unresolved blended groups and multiplet assumptions remain; UV "
                "flux ratio is not elemental N/C"
            ),
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    replay_path = output.with_suffix(".npz")
    np.savez_compressed(
        replay_path,
        flux=flux[:, selected],
        covariance_blocks=blocks[selected],
        spectral_kernel=kernel,
        selected_columns=selected,
        native_wave=np.array([d["wave"] for d in data]),
        native_good=np.array([d["good"] for d in data]),
        trace=np.array([d["trace_refined"] for d in data]),
        sigma=np.array([geometry["sigma_pixels"]]),
        noise_scale_squared=np.array([noise["pooled_scale_squared"]]),
    )
    result["compact_native_replay"] = {
        "filename": replay_path.name,
        "sha256": sha256(replay_path),
        "bytes": replay_path.stat().st_size,
        "contents": (
            "Source flux amplitudes, native wavelengths/masks, formal shared-column "
            "covariance and empirical spectral kernel; no raw SCI pixels"
        ),
    }
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def replay_report(report_path: Path) -> dict:
    """Numerically replay four main fits without raw pixels; not recalibration."""
    report = json.loads(report_path.read_text())
    receipt = report["compact_native_replay"]
    path = report_path.parent / receipt["filename"]
    if sha256(path) != receipt["sha256"] or path.stat().st_size != receipt["bytes"]:
        raise ValueError("Compact native replay bytes differ from report")
    with np.load(path, allow_pickle=False) as replay:
        selected = replay["selected_columns"]
        native_wave, native_good = replay["native_wave"], replay["native_good"]
        flux = np.full((9, native_wave.shape[2]), np.nan)
        flux[:, selected] = replay["flux"]
        blocks = np.zeros((native_wave.shape[2], 9, 9))
        blocks[selected] = replay["covariance_blocks"]
        kernel, scale = replay["spectral_kernel"], float(replay["noise_scale_squared"][0])
        data = [
            {
                "science": np.empty(wave.shape),
                "wave": wave,
                "good": good,
                "trace_refined": trace,
                "trace_seed": trace,
                "sigma_refined": float(replay["sigma"][0]),
            }
            for wave, good, trace in zip(native_wave, native_good, replay["trace"])
        ]
    rw, rr, _ = read_resolution(ROOT / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
    pw, pr, _ = read_point_resolution(
        ROOT / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    comparisons = []
    for index, (wave_r, r, transport, noise_scale) in enumerate(
        [(rw, rr, None, 1), (pw, pr, None, 1), (rw, rr, kernel, scale), (pw, pr, kernel, scale)]
    ):
        fit = fit_native(
            data, flux, blocks, selected, wave_r, r, kernel=transport, noise_scale=noise_scale
        )
        original = report["scenarios"][index]["fit"]
        difference = float(np.max(np.abs(np.array(fit["fluxes"]) - original["fluxes"])))
        covariance_difference = float(
            np.max(np.abs(np.array(fit["flux_covariance"]) - original["flux_covariance"]))
        )
        if difference > 1e-10 or covariance_difference > 1e-9:
            raise ValueError("Native compact fits do not reproduce saved science result")
        comparisons.append(
            {
                "scenario": report["scenarios"][index]["name"],
                "maximum_flux_difference": difference,
                "maximum_covariance_difference": covariance_difference,
            }
        )
    return {
        "replay_sha256": receipt["sha256"],
        "comparisons": comparisons,
        "scope": (
            "Compact numerical replay of derived amplitudes/covariance, "
            "not raw-pixel rerun or calibration validation"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--native-dir", type=Path)
    inputs.add_argument("--replay-report", type=Path)
    parser.add_argument(
        "--spectrum", type=Path, default=ROOT / "data_sources/pilot/mom_z14_dja_v4.spec.fits"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.replay_report:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(replay_report(args.replay_report), indent=2) + "\n")
    else:
        run(args.native_dir, args.spectrum, args.output)


if __name__ == "__main__":
    main()
