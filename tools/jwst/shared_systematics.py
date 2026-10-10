"""Few-group identifiability and conditional known-spectrum coverage diagnostics.

The compact arrays contain extracted measurements, not detector pixels. Shared
perturbations below are prescribed counterexamples, never measured calibration
distributions. Physical N IV version 2 and historical reductions are unchanged.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from scipy.linalg import block_diag, cho_factor, cho_solve
from scipy.stats import chi2, norm

from discovery.continuation_review import digest
from discovery.continuation_wavecorr_review import bin_design, source_waves
from tools.jwst.point_resolution import read_point_resolution

ROOT = Path(__file__).resolve().parents[2]
REFERENCE_KEY = ("original_native", "generic_point", "empirical_rows_and_columns")


def gls(design: np.ndarray, covariance: np.ndarray, values: np.ndarray) -> tuple:
    """Normal-equation oracle independent of production spectral QR fitting."""
    if not np.isfinite(design).all() or not np.isfinite(values).all():
        raise ValueError("Finite design and observations required")
    factor = cho_factor(covariance, lower=True)
    precision_design = cho_solve(factor, design)
    information = design.T @ precision_design
    parameter_covariance = np.linalg.inv(information)
    operator = parameter_covariance @ precision_design.T
    coefficient = operator @ values
    residual = values - design @ coefficient
    statistic = float(residual @ cho_solve(factor, residual))
    return coefficient, parameter_covariance, operator, statistic


def assumed_coverage(relative_sigma: float, draws: int, seed: int) -> dict:
    """Gaussian common-mode uncertainty omitted/included in a scalar interval.

    One normal draw is the projected native independent measurement noise; a
    second is one shared amplitude, not a separate draw for each RATE group.
    Linear GLS makes this projection exactly equivalent to a full-spectrum
    injection, without generating hundreds of MB of redundant pixel surrogates.
    """
    if not np.isfinite(relative_sigma) or relative_sigma < 0 or draws < 1000:
        raise ValueError("Nonnegative prescribed systematic sigma and >=1000 draws required")
    rng = np.random.default_rng(seed)
    error = rng.normal(size=draws) + relative_sigma * rng.normal(size=draws)
    z = norm.ppf(0.975)
    omitted = float(np.mean(np.abs(error) <= z))
    included = float(np.mean(np.abs(error) <= z * np.sqrt(1 + relative_sigma**2)))
    exact = float(2 * norm.cdf(z / np.sqrt(1 + relative_sigma**2)) - 1)
    return {
        "prescribed_common_sigma_over_conditional_sigma": relative_sigma,
        "draws": draws,
        "seed": seed,
        "omitted_systematic_exact_95_coverage": exact,
        "omitted_systematic_simulated_95_coverage": omitted,
        "simulation_binomial_standard_error": float(np.sqrt(exact * (1 - exact) / draws)),
        "included_systematic_simulated_95_coverage": included,
        "included_systematic_exact_95_coverage": 0.95,
        "distribution_measured": False,
    }


def equal_variance_scale_interval(group_count: int) -> list[float]:
    """Idealized Gaussian SD interval relative to observed sample SD.

    This is an information limit illustration, not a fit to heterogeneous native
    group fluxes and not an interval on the unconstrained global shared mode.
    """
    if group_count < 2:
        raise ValueError("At least two groups required")
    dof = group_count - 1
    return [float(np.sqrt(dof / chi2.ppf(p, dof))) for p in (0.975, 0.025)]


def run(root: Path, draws: int = 100000) -> dict:
    started = time.perf_counter()
    output_dir = root / "research_output"
    composed_path = output_dir / "mom_composed_spectral_refit.json"
    if digest(composed_path) != "fd14eb0028016c7c66c09cdae74a6474416e11c6a29003103e274887ab0fdc50":
        raise ValueError("Historical composed experiment must remain frozen")
    composed = json.loads(composed_path.read_text())
    wave_path = output_dir / "mom_native_wavecorr.json"
    wave_report = json.loads(wave_path.read_text())
    compact = output_dir / wave_report["compact_replay"]["filename"]
    components_path = output_dir / "mom_multiplet_components_niv_doublet_v2.json"
    pins = {
        wave_path: composed["input_wavecorr_report_sha256"],
        compact: composed["compact_replay_receipt"]["sha256"],
        components_path: composed["components_v2_sha256"],
    }
    if any(digest(path) != pin for path, pin in pins.items()):
        raise ValueError("Frozen composed experiment inputs differ")
    reference = next(
        a
        for a in composed["alternatives"]
        if (a["wavelength_hypothesis"], a["resolution_family"], a["noise_family"]) == REFERENCE_KEY
    )
    saved = next(
        r
        for r in reference["records"]
        if (r["temperature_K"], r["electron_density_cm3"]) == (20000, 1000)
    )["fit"]
    template = next(
        r
        for r in json.loads(components_path.read_text())["records"]
        if (r["temperature_K"], r["electron_density_cm3"]) == (20000, 1000)
    )
    with np.load(compact, allow_pickle=False) as archive:
        arrays = {key: archive[key].copy() for key in archive.files}
    waves = source_waves(
        arrays["native_wave"], arrays["native_good"], arrays["trace"], arrays["sigma"][0]
    )
    rw, rr, resolution = read_point_resolution(
        root / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    components = [
        (g["vacuum_wavelengths_A"], g["normalized_weights"]) for g in template["components"]
    ]
    if components[0][0] != [1483.321, 1486.496] or saved["line_contract_version"] != 2:
        raise ValueError("Physical total-N IV version 2 required")
    design = bin_design(waves, arrays["selected_columns"], rw, rr, components)
    factor = block_diag(*[np.linalg.cholesky(b) for b in arrays["spatial_covariance_blocks"]])
    covariance = (factor @ np.kron(arrays["spectral_kernel"], np.eye(9))) @ factor.T
    covariance *= arrays["noise_scale_squared"][0]
    values = arrays["flux"].T.ravel()
    coefficient, pcov, operator, fit_chi2 = gls(design, covariance, values)
    flux_error = float(np.max(abs(coefficient[2:] - saved["fluxes"])))
    covariance_error = float(np.max(abs(pcov[2:, 2:] - saved["flux_covariance"])))
    if flux_error > 1e-8 or covariance_error > 1e-8:
        raise ValueError(
            f"Independent native likelihood reproduction failed: {flux_error}, {covariance_error}"
        )

    native_path = output_dir / "mom_native_reduction.json"
    if digest(native_path) != "88e3cdbf5b7759eaad84dc21ead0974c38f392292d71ce605fa0f5b5951637ec":
        raise ValueError("Historical group identity/control report must remain frozen")
    native = json.loads(native_path.read_text())
    exposures = native["exposures"]
    groups = sorted({e["group"] for e in exposures})
    if len(groups) != 3 or len(exposures) != 9:
        raise ValueError("Exactly three complete RATE groups required")
    group_records = []
    common_direction = np.zeros(7)
    common_direction[2] = np.sqrt(pcov[2, 2])
    injection = design @ common_direction
    group_responses = []
    for group in groups:
        member_indices = [i for i, e in enumerate(exposures) if e["group"] == group]
        heldout = np.flatnonzero(np.tile(np.isin(np.arange(9), member_indices), len(values) // 9))
        training = np.setdiff1d(np.arange(len(values)), heldout)
        subsets = []
        responses = []
        for indices in (heldout, training):
            answer, uncertainty, response, _ = gls(
                design[indices], covariance[np.ix_(indices, indices)], values[indices]
            )
            subsets.append((answer, uncertainty))
            responses.append(response @ injection[indices])
        (test, test_cov), (train, train_cov) = subsets
        difference = test[2:] - train[2:]
        difference_covariance = test_cov[2:, 2:] + train_cov[2:, 2:]
        predictive_chi2 = float(difference @ np.linalg.solve(difference_covariance, difference))
        # Cross-group measurement noise is conditionally zero; global calibration
        # uncertainty would cancel from this group-versus-training contrast.
        cross_covariance = covariance[np.ix_(heldout, training)]
        if np.max(abs(cross_covariance)) > 1e-18:
            raise ValueError("Declared independent RATE groups have cross-noise terms")
        group_responses.append(responses[0])
        group_records.append(
            {
                "heldout_group": group,
                "exposure_indices": member_indices,
                "group_fluxes": test[2:].tolist(),
                "group_conditional_sigmas": np.sqrt(np.diag(test_cov)[2:]).tolist(),
                "other_two_groups_fluxes": train[2:].tolist(),
                "heldout_minus_training_five_flux_chi2": predictive_chi2,
                "conditional_degrees_of_freedom": 5,
                "conditional_gaussian_tail_probability": float(chi2.sf(predictive_chi2, 5)),
                "common_mode_cancellation_max_absolute_error": float(
                    np.max(abs(responses[0] - responses[1]))
                ),
            }
        )
    contrast = np.eye(3) - np.ones((3, 3)) / 3
    null_error = float(np.max(abs(contrast @ np.asarray(group_responses))))
    residual_error = float(np.max(abs(injection - design @ (operator @ injection))))
    coverage = [assumed_coverage(s, draws, 52241444) for s in (0, 0.5, 1, 2)]
    if any(
        abs(
            c["omitted_systematic_exact_95_coverage"]
            - c["omitted_systematic_simulated_95_coverage"]
        )
        > 5 * c["simulation_binomial_standard_error"]
        for c in coverage
    ):
        raise ValueError("Synthetic coverage differs from closed-form projection")
    return {
        "schema_version": 1,
        "input_sha256": {
            str(p.relative_to(root)): digest(p) for p in (*pins, composed_path, native_path)
        },
        "question": "Can three RATE groups calibrate a common line-like systematic?",
        "method_scope": (
            "Extracted-likelihood numerical reproduction and prescribed linear injections; "
            "no raw pixels"
        ),
        "line_contract_version": 2,
        "reference": {
            "wavelength": REFERENCE_KEY[0],
            "resolution": resolution,
            "noise": REFERENCE_KEY[2],
            "temperature_K": 20000,
            "electron_density_cm3": 1000,
        },
        "independent_reference_reproduction": {
            "maximum_flux_absolute_error": flux_error,
            "maximum_covariance_absolute_error": covariance_error,
            "chi2_absolute_error": abs(fit_chi2 - saved["conditional_chi2"]),
            "NIV_total_flux": float(coefficient[2]),
            "NIV_conditional_sigma": float(np.sqrt(pcov[2, 2])),
        },
        "heldout_group_diagnostics": group_records,
        "shared_mode_identifiability": {
            "prescribed_mode": (
                "One globally shared N IV-template amplitude; not inferred calibration"
            ),
            "one_conditional_sigma_amplitude_flux_units": float(common_direction[2]),
            "source_residual_response_max_absolute_error_uJy": residual_error,
            "group_contrast_response_max_absolute_error_flux_units": null_error,
            "group_contrast_rank": int(np.linalg.matrix_rank(contrast)),
            "global_shared_mode_information_from_group_contrasts": 0,
            "degeneracy": (
                "A line-shaped global residual is exactly confounded with its astrophysical flux"
            ),
        },
        "prescribed_gaussian_common_mode_coverage": coverage,
        "idealized_independent_equal_variance_group_sigma_interval": {
            "groups": 3,
            "degrees_of_freedom": 2,
            "95_population_sigma_over_sample_sigma": equal_variance_scale_interval(3),
            "applied_to_native_heteroscedastic_groups": False,
            "bounds_global_common_systematic": False,
        },
        "offsource_controls_already_measured": {
            "pooled_variance_scale_squared": native["empirical_noise"]["pooled_scale_squared"],
            "leave_one_group_out_scale_squared_range": native["empirical_noise"][
                "leave_one_group_out_scale_squared_range"
            ],
            "scope": (
                "Historical same-pixel controls; "
                "do not measure source-specific pathloss/wavelength/LSF"
            ),
        },
        "runtime_seconds": time.perf_counter() - started,
        "new_download_bytes": 0,
        "limitations": [
            "Gaussian common-mode amplitudes are assumed sensitivity scales, not empirical priors",
            "Coverage is for signed N IV total flux at fixed physical templates, not elemental N/C",
            (
                "Exact template-aligned mode demonstrates a worst-case identifiable limitation, "
                "not its occurrence"
            ),
            (
                "This compact replay neither reproduces detector calibration "
                "nor author extraction settings"
            ),
            (
                "Off-source spatial controls and three exposure groups cannot "
                "resolve every shared calibration mode"
            ),
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--draws", type=int, default=100000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.root, args.draws)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
