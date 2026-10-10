"""Versioned native v2 nuisance, held-out and signed-operator validation.

Independent reduction alternative. Gaussian draws calibrate only the declared
measurement model; shared calibration and source-specific LSF remain unknown.
No old fit contract is changed, no competing likelihoods are pooled.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.linalg import cholesky, solve_triangular
from scipy.optimize import nnls
from scipy.stats import chi2

from tools.jwst.atomic_grid import ionic_ratio
from tools.jwst.composed_spectral_refit import (
    AMBIENT_IONIC_REFERENCE,
    WAVECORR_REPORT_SHA256,
    ratio_accepted,
)
from tools.jwst.line_sensitivity import LINE_NAMES, line_matrix, read_resolution
from tools.jwst.native_reduction import (
    ROOT,
    covariance_blocks,
    extract_columns,
    gaussian_profile,
    mixing_matrix,
    read_inputs,
    recover_raw_variance,
    sha256,
    signed_profiles,
)
from tools.jwst.native_wavecorr import load_wavecorr_replay
from tools.jwst.niv_doublet_refit import ATOMIC_V2_SHA256, COMPONENT_V2_SHA256
from tools.jwst.point_resolution import read_point_resolution


def source_wavelength(d: dict) -> np.ndarray:
    """Exact frozen fit convention, before masking and before bin edges."""
    trace = d.get("trace_refined", d["trace_seed"])
    profile = gaussian_profile(trace, d.get("sigma_refined", 0.75), d["wave"].shape[0])
    weights = np.sum(profile * d["good"], axis=0)
    wave = np.divide(
        np.sum(np.where(d["good"], d["wave"], 0) * profile, axis=0),
        weights,
        out=np.full_like(weights, np.nan),
        where=weights > 0,
    )
    finite = np.isfinite(wave)
    if finite.sum() < 3:
        raise ValueError("at least three finite native wavelength samples required")
    if not finite.all():
        where = np.flatnonzero(finite)
        wave = np.interp(np.arange(len(wave)), where, wave[finite])
        wave[: where[0]] = wave[where[0]] + (np.arange(where[0]) - where[0]) * (
            wave[where[1]] - wave[where[0]]
        )
        wave[where[-1] + 1 :] = wave[where[-1]] + (
            np.arange(where[-1] + 1, len(wave)) - where[-1]
        ) * (wave[where[-1]] - wave[where[-2]])
    if np.any(np.diff(wave) <= 0):
        raise ValueError("native wavelength samples must increase")
    return wave


def response(
    data: list[dict],
    selected: np.ndarray,
    rw: np.ndarray,
    resolution: np.ndarray,
    components: list,
    *,
    redshift: float = 14.44,
    intrinsic_fwhm: float = 0,
    continuum_order: int = 1,
    members: list[int] | None = None,
) -> np.ndarray:
    """Per-exposure bin-integrated responses, column-major source ordering."""
    if continuum_order not in (0, 1, 2):
        raise ValueError("declared continuum orders are zero through two")
    members = list(range(len(data))) if members is None else members
    designs = []
    for i in members:
        wave = source_wavelength(data[i])
        continuum = np.polynomial.legendre.legvander((wave - 2.675) / 0.525, continuum_order) / 100
        lines = line_matrix(
            wave,
            rw,
            resolution,
            redshift=redshift,
            intrinsic_fwhm=intrinsic_fwhm,
            components=components,
        )
        lines /= (2.99792458e5 / wave**2)[:, None]
        designs.append(np.column_stack([continuum, lines])[selected])
    return np.transpose(designs, (1, 0, 2)).reshape(
        len(selected) * len(members), continuum_order + 6
    )


def signed_response_coupling(
    data: list[dict], operators: np.ndarray, selected: np.ndarray, sigma: float, offset: float
) -> np.ndarray:
    """Source/ghost transfer through the actual frozen extraction operators.

    Each positive nod has its own source-centered wavelength response. The
    extracted amplitude includes all three signed contributors, whose spectral
    responses differ even on aligned detector-pixel wavelength grids.
    """
    positive = np.array(
        [
            gaussian_profile(d["trace_seed"] + offset, sigma, d["wave"].shape[0])
            * np.where(d["good"], d["point_pathloss"], 0)
            for d in data
        ]
    )
    coupling = np.zeros((len(selected), len(data), len(data)))
    for group in sorted({d["group"] for d in data}):
        members = [i for i, d in enumerate(data) if d["group"] == group]
        mixing = mixing_matrix()
        for ii, i in enumerate(members):
            for jj, j in enumerate(members):
                coupling[:, i, j] = mixing[ii, jj] * np.sum(
                    operators[i][:, selected] * positive[j][:, selected], axis=0
                )
    return coupling


def apply_signed_response(design: np.ndarray, coupling: np.ndarray) -> np.ndarray:
    """Transport source-bin response without interpolation or extra subtraction."""
    columns, count, other = coupling.shape
    if count != other or design.shape[0] != columns * count:
        raise ValueError("signed response dimensions differ from source design")
    return np.einsum("cij,cjk->cik", coupling, design.reshape(columns, count, -1)).reshape(
        design.shape
    )


def transported_covariance(
    blocks: np.ndarray,
    selected: np.ndarray,
    kernel: np.ndarray,
    noise_scale: float,
    members: list[int],
) -> np.ndarray:
    if noise_scale <= 0 or not np.isfinite(noise_scale):
        raise ValueError("positive finite variance scale required")
    local = blocks[selected][:, members][:, :, members]
    factors = np.array([cholesky(b, lower=True) for b in local])
    return (
        np.einsum("cae,cd,dbe->cadb", factors, kernel, factors).reshape(
            len(selected) * len(members), len(selected) * len(members)
        )
        * noise_scale
    )


def solve_measurement(design: np.ndarray, covariance: np.ndarray, values: np.ndarray) -> dict:
    """GLS with QR, retaining estimator for held-out/injection validation."""
    chol = cholesky(covariance, lower=True)
    a = solve_triangular(chol, design, lower=True)
    y = solve_triangular(chol, values, lower=True)
    q, r = np.linalg.qr(a, mode="reduced")
    if np.linalg.matrix_rank(r) < r.shape[0]:
        raise ValueError("measurement design is rank deficient")
    coefficients = np.linalg.solve(r, q.T @ y)
    inverse = np.linalg.inv(r)
    vc = inverse @ inverse.T
    whitened_estimator = inverse @ q.T
    estimator = solve_triangular(chol.T, whitened_estimator.T, lower=False).T
    residual = y - a @ coefficients
    return {
        "coefficients": coefficients,
        "covariance": vc,
        "estimator": estimator,
        "whitened_estimator": whitened_estimator,
        "chi2": float(residual @ residual),
        "dof": len(values) - len(coefficients),
    }


def serial_fit(solution: dict, emissivity: dict, continuum_order: int) -> dict:
    start = continuum_order + 1
    flux, cov = solution["coefficients"][start:], solution["covariance"][start:, start:]
    return {
        "line_order": list(LINE_NAMES),
        "line_contract_version": 2,
        "flux_units": "1e-20 erg s^-1 cm^-2",
        "fluxes": flux.tolist(),
        "flux_covariance": cov.tolist(),
        "conditional_chi2": solution["chi2"],
        "dof": solution["dof"],
        "continuum_coefficients": solution["coefficients"][:start].tolist(),
        "ionic_N_over_C": ionic_ratio(flux, cov, emissivity, ("NIV", "NIII"), ("CIV", "CIII")),
    }


def held_out_prediction(train: dict, test: dict) -> dict:
    """Predict independent exposure group, propagating trained line uncertainty.

    The test group has its own continuum; continuum is projected out, rather
    than confusing group continuum differences with line heterogeneity.
    """
    start = train["continuum_order"] + 1
    f = train["solution"]["coefficients"][start:]
    vf = train["solution"]["covariance"][start:, start:]
    a = test["design"][:, start:]
    predictive_cov = test["covariance"] + a @ vf @ a.T
    resid = test["values"] - a @ f
    c = cholesky(predictive_cov, lower=True)
    nuisance = solve_triangular(c, test["design"][:, :start], lower=True)
    y = solve_triangular(c, resid, lower=True)
    q, _ = np.linalg.qr(nuisance, mode="reduced")
    r = y - q @ (q.T @ y)
    statistic = float(r @ r)
    dof = len(y) - start
    return {
        "predictive_chi2": statistic,
        "dof": dof,
        "conditional_gaussian_tail_probability": float(chi2.sf(statistic, dof)),
        "training_line_covariance_propagated": True,
        "test_continuum_profiled": True,
        "empirical_prediction_coverage_calibrated": False,
    }


def declared_source(
    data: list[dict],
    rw: np.ndarray,
    r: np.ndarray,
    components: list,
    coefficients: np.ndarray,
    *,
    sigma: float,
    offset: float,
) -> np.ndarray:
    """Inject only a known source into already-differenced CAL coordinates.

    This constructs a *synthetic source difference* from known raw-nod positive
    sources. It does not subtract the CAL science a second time.
    """
    source = []
    for d in data:
        wave = source_wavelength(d)
        lines = line_matrix(wave, rw, r, components=components) / (2.99792458e5 / wave**2)[:, None]
        continuum = np.polynomial.legendre.legvander((wave - 2.675) / 0.525, 1) / 100
        spec = np.column_stack([continuum, lines]) @ coefficients
        profile = gaussian_profile(d["trace_seed"] + offset, sigma, d["science"].shape[0])
        # Invalid calibration rows have zero extraction weight. Mask their
        # synthetic response explicitly: IEEE 0 * NaN is still NaN.
        source.append(profile * np.where(d["good"], d["point_pathloss"], 0) * spec[None])
    source = np.asarray(source)
    diff = np.zeros_like(source)
    for group in sorted({d["group"] for d in data}):
        members = [i for i, d in enumerate(data) if d["group"] == group]
        diff[members] = np.einsum("ij,jrc->irc", mixing_matrix(), source[members])
    return diff


def raw_noise_components(data: list[dict], selected: np.ndarray) -> list[dict]:
    """Same explicit failed-demix reconciliation as frozen covariance contract."""
    result = []
    for group in sorted({d["group"] for d in data}):
        members = [i for i, d in enumerate(data) if d["group"] == group]
        post = np.array([data[i]["variance"][:, selected] for i in members])
        good = np.all(np.array([data[i]["good"][:, selected] for i in members]), axis=0)
        safe = np.where(np.isfinite(post), post, 0)
        raw = recover_raw_variance(safe, mixing_matrix())
        failed = np.any(raw <= 0, axis=0) & good
        for row, column in zip(*np.nonzero(failed)):
            scale = np.max(safe[:, row, column])
            raw[:, row, column] = (
                nnls(mixing_matrix() ** 2, safe[:, row, column] / scale)[0] * scale
            )
        raw = np.where(good[None], np.maximum(raw, 0), 0)
        remainder = np.maximum(safe - np.einsum("ij,jrc->irc", mixing_matrix() ** 2, raw), 0)
        result.append({"group": group, "members": members, "raw": raw, "remainder": remainder})
    return result


def injection_experiment(
    data: list[dict],
    selected: np.ndarray,
    rw: np.ndarray,
    r: np.ndarray,
    components: list,
    replay: dict,
    emissivity: dict,
    draws: int = 4000,
    seed: int = 5224277,
) -> dict:
    baseline = json.loads((ROOT / "research_output/mom_native_reduction.json").read_text())
    geometry = baseline["geometry"]
    profiles = signed_profiles(data, geometry["sigma_pixels"], geometry["offset_pixels"])
    flux, operators, _ = extract_columns(data, profiles, selected_columns=selected)
    blocks, _ = covariance_blocks(data, operators)
    if not np.allclose(flux[:, selected], replay["flux"][:, selected], rtol=0, atol=1e-12):
        raise ValueError("actual CAL extraction differs from frozen native likelihood")
    if not np.allclose(blocks[selected], replay["covariance_blocks"][selected], rtol=0, atol=1e-12):
        raise ValueError("actual CAL covariance differs from frozen shared-nod likelihood")
    design = response(data, selected, rw, r, components)
    members = list(range(len(data)))
    formal = transported_covariance(blocks, selected, np.eye(len(selected)), 1, members)
    dummy = np.zeros(len(selected) * len(data))
    legacy = solve_measurement(design, formal, dummy)
    coupling = signed_response_coupling(
        data, operators, selected, geometry["sigma_pixels"], geometry["offset_pixels"]
    )
    signed_design = apply_signed_response(design, coupling)
    sol = solve_measurement(signed_design, formal, dummy)
    # Deliberately declared faint line source; not fitted data or a discovery.
    truth = np.array([2.0, -0.5, 20.0, 15.0, 15.0, 5.0, 12.0])
    raw_components = raw_noise_components(data, selected)
    rng = np.random.default_rng(seed)
    noise_coefficients = []
    legacy_noise_coefficients = []
    for start in range(0, draws, 128):
        count = min(128, draws - start)
        extracted = np.zeros((count, len(data), len(selected)))
        for group in raw_components:
            raw = rng.normal(size=(count, *group["raw"].shape)) * np.sqrt(group["raw"])[None]
            nod = np.einsum("ij,tjrc->tirc", mixing_matrix(), raw)
            nod += rng.normal(size=nod.shape) * np.sqrt(group["remainder"])[None]
            ii = group["members"]
            extracted[:, ii] = np.sum(nod * operators[ii][:, :, selected][None], axis=2)
        values = extracted.transpose(0, 2, 1).reshape(count, -1)
        noise_coefficients.append(values @ sol["estimator"].T)
        legacy_noise_coefficients.append(values @ legacy["estimator"].T)
    noise_coefficients = np.concatenate(noise_coefficients)
    legacy_noise_coefficients = np.concatenate(legacy_noise_coefficients)
    empirical_cov = np.cov(noise_coefficients[:, 2:], rowvar=False)
    sig = np.sqrt(np.diag(sol["covariance"]))
    cases = []
    legacy_case = None
    for label, sigma, offset in (
        ("matched_signed_profile", geometry["sigma_pixels"], geometry["offset_pixels"]),
        ("injected_broader_sigma0p95", 0.95, geometry["offset_pixels"]),
        (
            "injected_trace_offset_plus0p10",
            geometry["sigma_pixels"],
            geometry["offset_pixels"] + 0.10,
        ),
    ):
        image = declared_source(data, rw, r, components, truth, sigma=sigma, offset=offset)
        measured = np.sum(image[:, :, selected] * operators[:, :, selected], axis=1).T.reshape(-1)
        recovered = sol["estimator"] @ measured
        if label == "matched_signed_profile":
            if not np.allclose(measured, signed_design @ truth, rtol=0, atol=1e-14):
                raise ValueError(
                    "independent pixel injection differs from signed spectral response"
                )
            wrong = legacy["estimator"] @ measured
            wrong_sig = np.sqrt(np.diag(legacy["covariance"]))
            legacy_case = {
                "response_contract": "Historical positive-source-centered spectral response",
                "truth_fluxes": truth[2:].tolist(),
                "noise_free_recovered_fluxes": wrong[2:].tolist(),
                "deterministic_flux_bias": (wrong[2:] - truth[2:]).tolist(),
                "conditional_95_marginal_coverage": np.mean(
                    np.abs(wrong[None] + legacy_noise_coefficients - truth[None])
                    <= 1.959963984540054 * wrong_sig[None],
                    axis=0,
                )[2:].tolist(),
                "cause": "Different positive/ghost source-centered wavelength responses were "
                "not transported through the signed extraction operator",
            }
        simulations = recovered[None] + noise_coefficients
        coverage = np.mean(
            np.abs(simulations - truth[None]) <= 1.959963984540054 * sig[None], axis=0
        )
        cases.append(
            {
                "name": label,
                "injected_sigma_pixels": sigma,
                "injected_offset_pixels": offset,
                "truth_fluxes": truth[2:].tolist(),
                "noise_free_recovered_fluxes": recovered[2:].tolist(),
                "deterministic_flux_bias": (recovered[2:] - truth[2:]).tolist(),
                "conditional_95_marginal_coverage": coverage[2:].tolist(),
                "coverage_binomial_standard_errors": np.sqrt(
                    coverage[2:] * (1 - coverage[2:]) / draws
                ).tolist(),
            }
        )
    # Empirical covariance coverage is a separate model closure check: draw
    # whitened measurement noise, *not* invented detector raw-noise covariance.
    empirical = transported_covariance(
        replay["spatial_covariance_blocks"],
        selected,
        replay["spectral_kernel"],
        replay["noise_scale_squared"],
        members,
    )
    esol = solve_measurement(signed_design, empirical, dummy)
    ecoef = rng.normal(size=(draws, len(dummy))) @ esol["whitened_estimator"].T
    esig = np.sqrt(np.diag(esol["covariance"]))
    ecoverage = np.mean(np.abs(ecoef[:, 2:]) <= 1.959963984540054 * esig[None, 2:], axis=0)
    target = sol["covariance"][2:, 2:]
    covariance_sampling_sigma = np.sqrt(
        (np.diag(target)[:, None] * np.diag(target)[None] + target**2) / (draws - 1)
    )
    return {
        "draws": draws,
        "seed": seed,
        "line_order": list(LINE_NAMES),
        "formal_pixel_noise_covariance_standardized_max_error": float(
            np.max(np.abs(empirical_cov - target) / covariance_sampling_sigma)
        ),
        "formal_pixel_noise_empirical_covariance": empirical_cov.tolist(),
        "formal_pixel_noise_expected_covariance": target.tolist(),
        "pixel_signed_operator_injections": cases,
        "legacy_response_matched_profile_failure": legacy_case,
        "signed_response_constant_spectrum_closure_max_error": float(
            np.max(np.abs(coupling.sum(axis=2) - 1))
        ),
        "empirical_transport_gaussian_95_coverage": ecoverage.tolist(),
        "source_poisson_recomputed": False,
        "empirical_unknown_noise_coverage_established": False,
        "scope": (
            "Formal detector-noise draws use actual masks/operators, logged triplet nod mixing "
            "and reconciled variances. Empirical transport draws validate declared measurement "
            "covariance only; frozen source-dependent variance is not "
            "brightness-calibrated coverage."
        ),
    }


def signed_baseline_fits(
    data: list[dict], wavecorr_path: Path, components: list, emissivity: dict
) -> dict:
    """Four revised fixed-nuisance fits and three point/original group predictions."""
    baseline = json.loads((ROOT / "research_output/mom_native_reduction.json").read_text())
    replay = load_wavecorr_replay(wavecorr_path, corrected=False)
    geometry = baseline["geometry"]
    profiles = signed_profiles(data, geometry["sigma_pixels"], geometry["offset_pixels"])
    _, operators, _ = extract_columns(data, profiles, selected_columns=replay["selected"])
    coupling = signed_response_coupling(
        data, operators, replay["selected"], geometry["sigma_pixels"], geometry["offset_pixels"]
    )
    rw, rr, _ = read_resolution(ROOT / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
    pw, pr, _ = read_point_resolution(
        ROOT / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    records, groups = [], []
    for corrected in (False, True):
        local = load_wavecorr_replay(wavecorr_path, corrected=corrected)
        selected = local["selected"]
        covariance = transported_covariance(
            local["spatial_covariance_blocks"],
            selected,
            local["spectral_kernel"],
            local["noise_scale_squared"],
            list(range(9)),
        )
        values = local["flux"][:, selected].T.reshape(-1)
        for family, w, r in (("nominal", rw, rr), ("generic_point", pw, pr)):
            direct = response(local["data"], selected, w, r, components)
            design = apply_signed_response(direct, coupling)
            solution = solve_measurement(design, covariance, values)
            records.append(
                {
                    "resolution_family": family,
                    "wavelength_hypothesis": "pinned_toy_prediction"
                    if corrected
                    else "original_native",
                    "noise_family": "empirical_rows_and_columns",
                    "fit": serial_fit(solution, emissivity, 1),
                    "spectral_response_contract": "Signed source-plus-ghost transport v1",
                    "redshift": 14.44,
                    "intrinsic_fwhm_kms": 0,
                    "continuum_order": 1,
                }
            )
            if not corrected and family == "generic_point":
                all_design = design.reshape(len(selected), 9, -1)
                for group, test_members in (
                    ("03", [0, 1, 2]),
                    ("05", [3, 4, 5]),
                    ("07", [6, 7, 8]),
                ):
                    train_members = [i for i in range(9) if i not in test_members]
                    train, test = {"continuum_order": 1}, {}
                    for target, members in ((train, train_members), (test, test_members)):
                        target["design"] = all_design[:, members].reshape(
                            len(selected) * len(members), -1
                        )
                        target["covariance"] = transported_covariance(
                            local["spatial_covariance_blocks"],
                            selected,
                            local["spectral_kernel"],
                            local["noise_scale_squared"],
                            members,
                        )
                        target["values"] = local["flux"][members][:, selected].T.reshape(-1)
                        target["solution"] = solve_measurement(
                            target["design"], target["covariance"], target["values"]
                        )
                    groups.append(
                        {
                            "held_out_group": group,
                            "training_exposures": train_members,
                            "test_exposures": test_members,
                            "training_fit": serial_fit(train["solution"], emissivity, 1),
                            "held_out_fit": serial_fit(test["solution"], emissivity, 1),
                            "prediction": held_out_prediction(train, test),
                        }
                    )
    return {
        "signed_forward_corrected_baseline_fits": records,
        "signed_forward_corrected_group_checks": groups,
        "legacy_sensitivity_scope": (
            "The preserved28 one-factor fits reproduce the historical positive-centered "
            "response; their model-forward bias is demonstrated by signed detector injections. "
            "Use the distinct signed-forward alternatives for this revised source model."
        ),
    }


def common_systematic_identifiability() -> dict:
    """A common unknown offset is exactly confounded with true line flux."""
    design = np.column_stack([np.ones(3), np.ones(3)])
    contrast = np.array([[1, -1, 0], [0, 1, -1]], float)
    return {
        "disjoint_rate_groups": 3,
        "source_plus_common_offset_design_rank": int(np.linalg.matrix_rank(design)),
        "parameters": 2,
        "group_contrast_response_to_common_offset": (contrast @ np.ones(3)).tolist(),
        "common_systematic_upper_bound_from_group_agreement": None,
        "scope": (
            "Three groups can check heterogeneity, but agreement cannot identify or bound "
            "a shared additive line-calibration offset without external information."
        ),
    }


def run(native_dir: Path | None = None, draws: int = 4000) -> dict:
    paths = {
        "wavecorr": ROOT / "research_output/mom_native_wavecorr.json",
        "atomic": ROOT / "research_output/mom_atomic_grid_niv_doublet_v2.json",
        "components": ROOT / "research_output/mom_multiplet_components_niv_doublet_v2.json",
    }
    for key, pin in (
        ("wavecorr", WAVECORR_REPORT_SHA256),
        ("atomic", ATOMIC_V2_SHA256),
        ("components", COMPONENT_V2_SHA256),
    ):
        if sha256(paths[key]) != pin:
            raise ValueError("input differs from independently pinned version2 baseline")
    atomic = json.loads(paths["atomic"].read_text())
    templates = json.loads(paths["components"].read_text())
    index = next(
        i
        for i, c in enumerate(atomic["records"])
        if c["temperature_K"] == 20000 and c["electron_density_cm3"] == 1000
    )
    emissivity = atomic["records"][index]["emissivity_erg_cm3_s"]
    components = [
        (g["vacuum_wavelengths_A"], g["normalized_weights"])
        for g in templates["records"][index]["components"]
    ]
    rw, rr, _ = read_resolution(ROOT / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
    pw, pr, _ = read_point_resolution(
        ROOT / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    composed = json.loads((ROOT / "research_output/mom_composed_spectral_refit.json").read_text())
    models = [
        ("baseline", 14.44, 0, 1),
        ("redshift14p40", 14.40, 0, 1),
        ("redshift14p48", 14.48, 0, 1),
        ("intrinsic300kms", 14.44, 300, 1),
        ("intrinsic1000kms", 14.44, 1000, 1),
        ("constant_continuum", 14.44, 0, 0),
        ("quadratic_continuum", 14.44, 0, 2),
    ]
    records = []
    groups = []
    replay_controls = []
    for corrected in (False, True):
        replay = load_wavecorr_replay(paths["wavecorr"], corrected=corrected)
        selected = replay["selected"]
        members = list(range(9))
        covariance = transported_covariance(
            replay["spatial_covariance_blocks"],
            selected,
            replay["spectral_kernel"],
            replay["noise_scale_squared"],
            members,
        )
        values = replay["flux"][:, selected].T.reshape(-1)
        for family, w, r in (("nominal", rw, rr), ("generic_point", pw, pr)):
            for label, z, width, order in models:
                design = response(
                    replay["data"],
                    selected,
                    w,
                    r,
                    components,
                    redshift=z,
                    intrinsic_fwhm=width,
                    continuum_order=order,
                )
                solution = solve_measurement(design, covariance, values)
                fit = serial_fit(solution, emissivity, order)
                record = {
                    "model": label,
                    "wavelength_hypothesis": "pinned_toy_prediction"
                    if corrected
                    else "original_native",
                    "resolution_family": family,
                    "redshift": z,
                    "intrinsic_fwhm_kms": width,
                    "continuum_order": order,
                    "noise_family": "empirical_rows_and_columns",
                    "fit": fit,
                }
                records.append(record)
                if label == "baseline":
                    previous = next(
                        a
                        for a in composed["alternatives"]
                        if a["wavelength_hypothesis"] == record["wavelength_hypothesis"]
                        and a["resolution_family"] == family
                        and a["noise_family"] == "empirical_rows_and_columns"
                    )["records"][index]["fit"]
                    df = float(np.max(np.abs(np.array(fit["fluxes"]) - previous["fluxes"])))
                    dc = float(
                        np.max(
                            np.abs(np.array(fit["flux_covariance"]) - previous["flux_covariance"])
                        )
                    )
                    if df > 1e-9 or dc > 1e-8:
                        raise ValueError("default response does not reproduce frozen composition")
                    replay_controls.append(
                        {
                            "resolution_family": family,
                            "wavelength_hypothesis": record["wavelength_hypothesis"],
                            "maximum_flux_difference": df,
                            "maximum_covariance_difference": dc,
                        }
                    )
            if not corrected:
                # These official CAL contributors are disjoint triplets. Do not
                # apply this independence claim to the author's pooled PIXTAB.
                for group, members_test in (
                    ("03", [0, 1, 2]),
                    ("05", [3, 4, 5]),
                    ("07", [6, 7, 8]),
                ):
                    train_members = [i for i in range(9) if i not in members_test]
                    train = {"continuum_order": 1}
                    test = {}
                    for target, indices in ((train, train_members), (test, members_test)):
                        target["design"] = response(
                            replay["data"], selected, w, r, components, members=indices
                        )
                        target["covariance"] = transported_covariance(
                            replay["spatial_covariance_blocks"],
                            selected,
                            replay["spectral_kernel"],
                            replay["noise_scale_squared"],
                            indices,
                        )
                        target["values"] = replay["flux"][indices][:, selected].T.reshape(-1)
                        target["solution"] = solve_measurement(
                            target["design"], target["covariance"], target["values"]
                        )
                    groups.append(
                        {
                            "resolution_family": family,
                            "held_out_group": group,
                            "training_exposures": train_members,
                            "test_exposures": members_test,
                            "training_fit": serial_fit(train["solution"], emissivity, 1),
                            "held_out_fit": serial_fit(test["solution"], emissivity, 1),
                            "prediction": held_out_prediction(train, test),
                        }
                    )
    original_point = [
        c
        for c in records
        if c["wavelength_hypothesis"] == "original_native"
        and c["resolution_family"] == "generic_point"
    ]
    budget = {
        "reference_conditional_NIV_sigma": float(
            np.sqrt(original_point[0]["fit"]["flux_covariance"][0][0])
        ),
        "one_factor_NIV_flux_range": [
            min(c["fit"]["fluxes"][0] for c in original_point),
            max(c["fit"]["fluxes"][0] for c in original_point),
        ],
        "one_factor_ionic_ratio_range": [
            min(c["fit"]["ionic_N_over_C"]["value"] for c in original_point),
            max(c["fit"]["ionic_N_over_C"]["value"] for c in original_point),
        ],
        "original_point_nuisance_cases_admitting_ionic_ambient_reference": sum(
            ratio_accepted(c["fit"]["ionic_N_over_C"], AMBIENT_IONIC_REFERENCE)
            for c in original_point
        ),
        "original_point_nuisance_cases": len(original_point),
        "range_is_calibration_interval": False,
        "common_calibration_systematic": common_systematic_identifiability(),
        "unquantified_inputs": [
            "source-specific LSF/along-dispersion geometry",
            "absolute wavelength assignment",
            "nonstationary noise and source Poisson separation",
            "He/O blend weights and C IV transfer",
            "ion fractions needed for elemental N/C",
        ],
        "model_families_pooled": False,
    }
    result = {
        "schema_version": 1,
        "starting_revision": "379ff35786aff31535335bbe7d1de114f91dd3c4",
        "inputs_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in paths.values()},
        "reference_atomic_cell": {"temperature_K": 20000, "electron_density_cm3": 1000},
        "nuisance_ranges_empirically_calibrated": False,
        "source_specific_LSF_calibrated": False,
        "alternative_likelihoods_pooled": False,
        "elemental_NC_identified": False,
        "baseline_replay_controls": replay_controls,
        "one_factor_sensitivity_fits": records,
        "held_out_rate_group_checks": groups,
        "uncertainty_budget": budget,
    }
    if native_dir is not None:
        data, metadata = read_inputs(
            native_dir, ROOT / "data_sources/pilot/mom_z14_dja_v4.spec.fits"
        )
        baseline = json.loads((ROOT / "research_output/mom_native_reduction.json").read_text())
        for d in data:
            d["trace_refined"] = d["trace_seed"] + baseline["geometry"]["offset_pixels"]
            d["sigma_refined"] = baseline["geometry"]["sigma_pixels"]
        replay = load_wavecorr_replay(paths["wavecorr"], corrected=False)
        result["actual_pixel_metadata"] = metadata
        result["actual_pixel_input_hashes"] = [
            {"filename": d["filename"], "sha256": d["sha256"]} for d in data
        ]
        result["signed_operator_injections"] = injection_experiment(
            data, replay["selected"], pw, pr, components, replay, emissivity, draws=draws
        )
        result.update(signed_baseline_fits(data, paths["wavecorr"], components, emissivity))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-dir", type=Path)
    parser.add_argument("--draws", type=int, default=4000)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "research_output/mom_native_measurement_validation.json",
    )
    args = parser.parse_args()
    if not 100 <= args.draws <= 4000:
        raise ValueError("bounded draws between100 and4000 required")
    result = run(args.native_dir, args.draws)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sensitivity_fits": len(result["one_factor_sensitivity_fits"]),
                "held_out_checks": len(result["held_out_rate_group_checks"]),
                "actual_pixel_injections": "signed_operator_injections" in result,
            }
        )
    )


if __name__ == "__main__":
    main()
