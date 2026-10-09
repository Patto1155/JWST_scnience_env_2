"""Bridge measured flux covariance to explicit, uncalibrated chemistry nuisance factors.

No atomic emissivity grid is present. The effective factor Q in F_N/F_C = Q*(N/C)
is therefore not estimated; this experiment calculates what Q each *conditional*
abundance target would require, preserving the signed-flux Fieller uncertainty.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from discovery.enrichment_constraints import (
    DEFAULT_INPUT,
    ROOT,
    background_nuclei_per_msun,
    bracket_to_number_ratio,
    maximum_ambient_mass,
    mixture_abundances,
    number_ratio,
)
from tools.jwst.line_sensitivity import LINE_NAMES, fieller_set

DEFAULT_SPECTRUM_REPORT = ROOT / "research_output/mom_z14_line_sensitivity.json"
CONFIDENCE_SIGMA = 1.95996398454


def flux_ratio_from_covariance(
    scenario: dict[str, Any],
    numerator_names: tuple[str, ...],
    denominator_names: tuple[str, ...],
) -> dict[str, Any]:
    """Compute signed sums and their ratio from full fitted line covariance."""
    if list(scenario["lines"]) != list(LINE_NAMES):
        raise ValueError("line order must match the pinned fit schema/covariance order")
    flux = np.array([scenario["lines"][name]["flux"] for name in LINE_NAMES], dtype=float)
    cov = np.asarray(scenario["line_covariance"], dtype=float)
    if cov.shape != (len(LINE_NAMES), len(LINE_NAMES)):
        raise ValueError("missing or malformed full line covariance")
    if not np.all(np.isfinite(cov)) or not np.all(np.isfinite(flux)):
        raise ValueError("line fluxes and covariance must be finite")
    if not np.allclose(cov, cov.T) or np.min(np.linalg.eigvalsh(cov)) < -1e-8:
        raise ValueError("line covariance must be symmetric and positive semidefinite")
    if not set(numerator_names + denominator_names).issubset(LINE_NAMES):
        raise ValueError("unknown line name")
    num = np.array([name in numerator_names for name in LINE_NAMES], dtype=float)
    den = np.array([name in denominator_names for name in LINE_NAMES], dtype=float)
    if not np.any(num) or not np.any(den):
        raise ValueError("numerator and denominator need known lines")
    nf, df = float(num @ flux), float(den @ flux)
    nv, dv, nd = float(num @ cov @ num), float(den @ cov @ den), float(num @ cov @ den)
    return {
        "value": nf / df if df != 0 else None,
        "numerator_flux": nf,
        "denominator_flux": df,
        "numerator_variance": nv,
        "denominator_variance": dv,
        "numerator_denominator_covariance": nd,
        "conditional_gaussian_95_fieller_set": fieller_set(nf, df, nv, dv, nd, CONFIDENCE_SIGMA**2),
    }


def scale_fieller_set(ratio_set: dict[str, Any], positive_divisor: float) -> dict[str, Any]:
    """Preserve bounded, disconnected, unbounded, and signed sets under R/Q scaling."""
    if not math.isfinite(positive_divisor) or positive_divisor <= 0:
        raise ValueError("fixed abundance target must be finite and positive")
    result = dict(ratio_set)
    if "interval" in ratio_set:
        result["interval"] = [x / positive_divisor for x in ratio_set["interval"]]
    if "excluded_open_interval" in ratio_set:
        result["excluded_open_interval"] = [
            x / positive_divisor for x in ratio_set["excluded_open_interval"]
        ]
    if "boundary" in ratio_set:
        result["boundary"] = ratio_set["boundary"] / positive_divisor
    return result


def required_effective_factor(ratio: dict[str, Any], target_nc: float) -> dict[str, Any]:
    if not math.isfinite(target_nc) or target_nc <= 0:
        raise ValueError("target N/C must be finite and positive")
    return {
        "required_q_point": None if ratio["value"] is None else ratio["value"] / target_nc,
        "formal_conditional_q_95_set": scale_fieller_set(
            ratio["conditional_gaussian_95_fieller_set"], target_nc
        ),
        "note": "Q must be physically positive. Signed Gaussian set is not clipped or a "
        "positive-parameter posterior; a set crossing zero shows weak conditional information.",
    }


def marginal_compatibility(mixed: dict[str, float] | None, box: dict[str, list[float]]) -> bool:
    """Necessary endpoint compatibility only; these margins are not a joint credible region."""
    if mixed is None:
        return False
    return all(bounds[0] <= mixed[key] <= bounds[1] for key, bounds in box.items())


def mixing_compatibility(inputs: dict[str, Any]) -> dict[str, Any]:
    solar = inputs["solar_reference"]
    mom = inputs["mom_z14_model_parameters"]
    oh, co = mom["bracket_o_h"], mom["bracket_c_o"]
    box = {
        "oxygen_12_log_o_h": [
            solar["oxygen_12_log_o_h"] + oh["median"] - oh["minus"],
            solar["oxygen_12_log_o_h"] + oh["median"] + oh["plus"],
        ],
        "log_c_o": [
            solar["log_c_o"] + co["median"] - co["minus"],
            solar["log_c_o"] + co["median"] + co["plus"],
        ],
    }
    summaries = []
    solar_nc = solar["log_n_o"] - solar["log_c_o"]
    oh_cases = [oh["median"] - oh["minus"], oh["median"], oh["median"] + oh["plus"]]
    targets = [
        ("Cue_lower_marginal_endpoint", 0.27),
        ("Cue_median", 0.90),
        ("Cue_upper_marginal_endpoint", 1.19),
        ("separate_ionic_temperature_case_lower", 1.30),
        ("separate_ionic_temperature_case_upper", 1.70),
    ]
    for row in inputs["sms_yields"]["rows"]:
        for target_label, target_dex in targets:
            target = bracket_to_number_ratio(target_dex, solar_nc)
            tested, reachable, retained, gas_masses = 0, 0, 0, []
            for oh_case in oh_cases:
                for co_case in (0.0, -0.65):
                    for nc_case in (-0.6, 0.0):
                        background = background_nuclei_per_msun(solar, oh_case, co_case, nc_case)
                        for retention in (0.1, 0.3, 1.0):
                            tested += 1
                            mass = maximum_ambient_mass(row, background, target, retention)
                            if mass is None:
                                continue
                            reachable += 1
                            mixed = mixture_abundances(row, background, mass, solar, retention)
                            if marginal_compatibility(mixed, box):
                                retained += 1
                                gas_masses.append(mass)
            summaries.append(
                {
                    "initial_mass_msun": row["initial_mass"],
                    "target": target_label,
                    "target_bracket_n_c": target_dex,
                    "grid_cases": tested,
                    "n_c_reachable_cases": reachable,
                    "also_o_h_and_c_o_marginal_compatible_cases": retained,
                    "compatible_ambient_mass_range_msun": [min(gas_masses), max(gas_masses)]
                    if gas_masses
                    else None,
                }
            )
    # An optimistic nitrogen-only ceiling, not a fabricated carbon-free stellar yield.
    vms = inputs["vms_benchmark"]
    optimistic = []
    for co_case in (0.0, -0.65):
        background = background_nuclei_per_msun(solar, oh["median"], co_case, 0.0)
        target = bracket_to_number_ratio(0.9, solar_nc)
        mass = maximum_ambient_mass(
            {"n": vms["nitrogen_ejecta_per_star_msun_approx"], "c": 0.0}, background, target
        )
        optimistic.append(
            {
                "background_bracket_c_o": co_case,
                "optimistic_maximum_ambient_mass_msun_per_vms": mass,
            }
        )
    helium_examples = []
    # Approximate primordial He mass fraction, neglecting ambient trace metals.
    # This scenario is not inferred from the unresolved UV HeII/OIII blend.
    background = background_nuclei_per_msun(solar, oh["median"], -0.65, 0.0)
    for row in inputs["sms_yields"]["rows"]:
        for target_dex in (0.9, 1.7):
            target = bracket_to_number_ratio(target_dex, solar_nc)
            mass = maximum_ambient_mass(row, background, target)
            he_h = (
                None
                if mass is None
                else (mass * 0.25 / 4 + row["he"] / 4) / (mass * 0.75 + row["h"])
            )
            helium_examples.append(
                {
                    "initial_mass_msun": row["initial_mass"],
                    "target_bracket_n_c": target_dex,
                    "ambient_mass_msun": mass,
                    "mixed_he_h_number": he_h,
                }
            )
    return {
        "compatibility_box": box,
        "box_status": "necessary_marginal_endpoint_check_not_joint_confidence_or_likelihood",
        "counts_status": "deterministic_grid_choice_counts_not_model_weights_or_probabilities",
        "evaluated_at": "Each maximum ambient mass reaching the fixed N/C target",
        "sms_summaries": summaries,
        "conditional_helium_examples": {
            "background_he_h_number": 0.25 / 4 / 0.75,
            "assumptions": "Ambient [O/H]=-1.38, [C/O]=-0.65, [N/C]=0; equal full "
            "retention, homogeneous mixing, X_H=0.75, X_He=0.25 neglecting ambient trace metals.",
            "values": helium_examples,
            "inference_guard": "Predicted gas nuclei ratios only; HeII/OIII blend "
            "cannot measure them without hydrogen lines and ionization/emissivity modelling.",
        },
        "vms_optimistic_nitrogen_only_bounds": {
            "cases": optimistic,
            "nitrogen_per_star_msun_approx": 1.0,
            "timescale_myr_approx": 2.0,
            "assumptions": "LMC-like VMS estimate, full N retention, ignore coejected carbon "
            "and other sources; adding carbon lowers this ceiling. "
            "This is not a full N/C prediction.",
        },
    }


def run_identifiability(
    spectrum_path: Path, benchmark_path: Path = DEFAULT_INPUT
) -> dict[str, Any]:
    spectrum_bytes, benchmark_bytes = spectrum_path.read_bytes(), benchmark_path.read_bytes()
    spectrum, inputs = json.loads(spectrum_bytes), json.loads(benchmark_bytes)
    if spectrum["schema_version"] != "mom_line_sensitivity_v1":
        raise ValueError("unsupported spectrum report schema")
    solar = inputs["solar_reference"]
    solar_nc = solar["log_n_o"] - solar["log_c_o"]
    targets = [
        {"label": label, "status": status, "target_bracket_n_c": value}
        for label, status, value in (
            ("Cue_lower_endpoint", "published_conditional_inference", 0.27),
            ("Cue_median", "published_conditional_inference", 0.90),
            ("Cue_upper_endpoint", "published_conditional_inference", 1.19),
            ("ionic_temperature_lower_case", "separate_published_ionic_inference", 1.30),
            ("ionic_temperature_upper_case", "separate_published_ionic_inference", 1.70),
        )
    ]
    for row in inputs["sms_yields"]["rows"]:
        targets.append(
            {
                "label": f"SMS_{row['initial_mass']:g}_pure_ejecta",
                "status": "equal_retention_lower_ambient_n_c_mixing_ceiling",
                "target_bracket_n_c": math.log10(number_ratio(row, "n", "c")) - solar_nc,
            }
        )
    for row in inputs["rotating_models"]["rows"]:
        targets.append(
            {
                "label": f"rotation_{row['scenario']}_Z{row['z']:g}",
                "status": "selected_published_mixed_ism_prediction",
                "target_bracket_n_c": row["log_n_o"] - row["log_c_o"] - solar_nc,
            }
        )
    scenarios = []
    for index, scenario in enumerate(spectrum["fixed_published_redshift_scenarios"]):
        ratio = flux_ratio_from_covariance(scenario, ("NIV", "NIII"), ("CIV", "CIII"))
        scenarios.append(
            {
                "source_scenario_index": index,
                "extraction": scenario["extraction"],
                "rho_assumed": scenario["rho_assumed"],
                "lsf_fwhm_multiplier": scenario["lsf_fwhm_multiplier"],
                "intrinsic_fwhm_km_s": scenario["intrinsic_fwhm_km_s"],
                "continuum_order": scenario["continuum_fnu_polynomial_order"],
                "blend_assumption": scenario["blend_assumption"],
                "measured_sum_n_lines_over_sum_c_lines": ratio,
            }
        )
    if not scenarios:
        raise ValueError("need at least one spectrum scenario")
    nominal = scenarios[0]["measured_sum_n_lines_over_sum_c_lines"]
    for target in targets:
        nc = bracket_to_number_ratio(target["target_bracket_n_c"], solar_nc)
        q_values = [
            s["measured_sum_n_lines_over_sum_c_lines"]["value"] / nc
            for s in scenarios
            if s["measured_sum_n_lines_over_sum_c_lines"]["value"] is not None
        ]
        target.update(
            {
                "target_n_c_by_number": nc,
                "nominal_required_effective_factor": required_effective_factor(nominal, nc),
                "scenario_q_point_range": [min(q_values), max(q_values)],
            }
        )
    fixed_q = []
    for q in (0.2, 0.5, 1.0, 2.0):
        ratio = nominal["value"]
        fixed_q.append(
            {
                "q_assumed_unmeasured": q,
                "conditional_bracket_n_c_point": math.log10(ratio / q) - solar_nc,
                "formal_number_n_c_95_set": scale_fieller_set(
                    nominal["conditional_gaussian_95_fieller_set"], q
                ),
            }
        )
    stage_diagnostics = {
        "NIV_over_CIV": flux_ratio_from_covariance(
            spectrum["fixed_published_redshift_scenarios"][0], ("NIV",), ("CIV",)
        ),
        "NIII_over_CIII": flux_ratio_from_covariance(
            spectrum["fixed_published_redshift_scenarios"][0], ("NIII",), ("CIII",)
        ),
        "HeII_OIII_blend_over_CIII": flux_ratio_from_covariance(
            spectrum["fixed_published_redshift_scenarios"][0], ("HeII_OIII",), ("CIII",)
        ),
    }
    return {
        "schema_version": "chemistry_identifiability_v1",
        "source_sha256": {
            "spectrum_report": hashlib.sha256(spectrum_bytes).hexdigest(),
            "enrichment_benchmarks": hashlib.sha256(benchmark_bytes).hexdigest(),
        },
        "status": "line_measurements_and_conditional_nuisance_requirements_no_abundance_fit",
        "atomic_grid_available": False,
        "target_source_locations": {
            "Cue_and_separate_ionic_targets": "https://arxiv.org/html/2505.11263v2 "
            "physical-property table and Section 3.2.3; "
            "ionic range spans temperature cases, not a confidence interval",
            "numeric_yields_and_rotation": "Locations and versions pinned "
            "in enrichment_benchmarks.json",
        },
        "forward_relation": "sum(F_NIV,F_NIII)/sum(F_CIV,F_CIII) = Q_eff * number(N/C)",
        "effective_factor": "Uncalibrated abundance-weighted line emissivity/ion fraction factor; "
        "depends on density, temperature, radiation, geometry, transfer, and chemical cooling. "
        "It need not be constant across stellar/nebular models or abundance changes.",
        "nominal_definition": "First source scenario: stored 1D, specified illuminated LSF, "
        "fixed published z, diagonal pixel covariance. Not a preferred physical model.",
        "targets": targets,
        "spectrum_scenario_summaries": scenarios,
        "fixed_q_sensitivity_not_predictions": fixed_q,
        "nominal_ion_stage_and_blend_flux_diagnostics": stage_diagnostics,
        "mixing_joint_marginal_checks": mixing_compatibility(inputs),
        "unavailable_mechanism_predictions": {
            "WR": "The pinned time-history benchmark does not give a numerical N/C yield here.",
            "VMS": "Pinned approximate N yield lacks C/O; "
            "only an optimistic N-only budget is computed.",
        },
        "limits": [
            "Flux covariances condition on the source fit's extraction and nuisance choices; "
            "AR(1) correlations are assumed sensitivities, not empirically measured covariance.",
            "Alternative extractions share exposures "
            "and cannot be multiplied as independent likelihoods.",
            "Separate ionic [N/C]1.3-1.7 cases are temperature-model outcomes, "
            "not a new confidence interval "
            "or replacement for Cue's broad posterior.",
            "Physical positivity is not imposed on signed flux confidence sets; no abundance prior "
            "or posterior model probability is inferred.",
            "HeII and OIII remain blended; "
            "helium abundance or stellar HeII origin cannot be derived.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spectrum-report", type=Path, default=DEFAULT_SPECTRUM_REPORT)
    parser.add_argument("--benchmarks", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_identifiability(args.spectrum_report, args.benchmarks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "targets": len(result["targets"]),
                "spectral_scenarios": len(result["spectrum_scenario_summaries"]),
            }
        )
    )


if __name__ == "__main__":
    main()
