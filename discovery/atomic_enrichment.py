"""Condition versioned stellar yields on covariant *ionic*, not elemental, data.

The atomic analysis measures R_ion = (N2+ + N3+) / (C2+ + C3+) under
homogeneous temperature/density and transfer assumptions. Elemental N/C is
R_ion * k, where k=f_C_observed/f_N_observed remains an uncalibrated nuisance.
This module profiles the measured two-component Gaussian against conditional
yield ceilings, preserving covariance and positive shared normalization. It
assigns neither mechanism probabilities nor calibrated ionization corrections.
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
    number_ratio,
    required_formation_redshift,
    time_budget_myr,
)
from tools.jwst.line_sensitivity import LINE_NAMES, fieller_set

ATOMIC_MASS = {"h": 1, "he": 4, "c": 12, "n": 14, "o": 16}
SIGMA_95 = 1.95996398454


def positive(value: float, name: str) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


def check_ionic_measurement(record: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    """Reject invalid covariance or an inconsistent cached ratio/Fieller summary."""
    x = np.asarray([record["scaled_numerator"], record["scaled_denominator"]], dtype=float)
    covariance = np.asarray(record["scaled_covariance"], dtype=float)
    if x.shape != (2,) or not np.all(np.isfinite(x)):
        raise ValueError("finite signed ionic numerator and denominator required")
    if covariance.shape != (2, 2) or not np.all(np.isfinite(covariance)):
        raise ValueError("finite 2x2 ionic covariance required")
    if not np.allclose(covariance, covariance.T, rtol=1e-10, atol=1e-12):
        raise ValueError("symmetric ionic covariance required")
    if np.min(np.linalg.eigvalsh(covariance)) <= 0:
        raise ValueError("positive definite ionic covariance required")
    ratio = x[0] / x[1] if x[1] != 0 else None
    if ratio is None:
        if record["value"] is not None:
            raise ValueError("cached ionic ratio disagrees with its signed measurements")
    elif record["value"] is None or not np.isclose(ratio, record["value"], rtol=1e-10):
        raise ValueError("cached ionic ratio disagrees with its signed measurements")
    expected = fieller_set(
        x[0], x[1], *[covariance[0, 0], covariance[1, 1], covariance[0, 1]], SIGMA_95**2
    )
    saved = record["conditional_gaussian_95_fieller_set"]
    if saved["type"] != expected["type"]:
        raise ValueError("cached Fieller topology disagrees with its measurements")
    for key in ("interval", "excluded_open_interval", "boundary"):
        if key in expected and (key not in saved or not np.allclose(saved[key], expected[key])):
            raise ValueError("cached Fieller set disagrees with its measurements")
    return x, covariance


def ray_profile(
    measurement: np.ndarray, precision: np.ndarray, direction: np.ndarray
) -> dict[str, Any]:
    """GLS fit of one ray with nonnegative common normalization, retaining covariance."""
    normalization = max(
        0.0, float(direction @ precision @ measurement) / float(direction @ precision @ direction)
    )
    prediction = normalization * direction
    residual = measurement - prediction
    return {
        "chi2": max(0.0, float(residual @ precision @ residual)),
        "normalization": normalization,
        "predicted_scaled_numerator_denominator": prediction.tolist(),
    }


def profile_ionic_ratio_interval(
    measurement: np.ndarray, covariance: np.ndarray, lower: float, upper: float
) -> dict[str, Any]:
    """Profile a convex abundance interval against the two-dimensional Gaussian.

    Limits are ionic ratios. Positive numerator and denominator model amplitudes
    share one fitted scale. Deviance is relative to the best positive-quadrant
    fit, not a posterior, Bayes factor, or universally calibrated test statistic.
    """
    lower = positive(lower, "lower ionic ratio")
    upper = positive(upper, "upper ionic ratio")
    if upper < lower:
        raise ValueError("ordered positive ratio interval required")
    covariance = np.asarray(covariance, dtype=float)
    measurement = np.asarray(measurement, dtype=float)
    if (
        measurement.shape != (2,)
        or not np.all(np.isfinite(measurement))
        or covariance.shape != (2, 2)
        or not np.all(np.isfinite(covariance))
        or not np.allclose(covariance, covariance.T)
        or np.min(np.linalg.eigvalsh(covariance)) <= 0
    ):
        raise ValueError("finite two-component measurement and positive covariance required")
    precision = np.linalg.inv(covariance)
    ratios = [lower, upper]
    if measurement[1] != 0:
        unconstrained = float(measurement[0] / measurement[1])
        if lower <= unconstrained <= upper:
            ratios.append(unconstrained)
    fits = [
        (ratio, ray_profile(measurement, precision, np.array([ratio, 1.0]))) for ratio in ratios
    ]
    ratio, fit = min(fits, key=lambda pair: pair[1]["chi2"])
    # Two axes and the exact interior optimum cover the nonnegative quadrant.
    unrestricted = [
        ray_profile(measurement, precision, np.array([1.0, 0.0])),
        ray_profile(measurement, precision, np.array([0.0, 1.0])),
    ]
    if np.all(measurement >= 0):
        unrestricted.append({"chi2": 0.0})
    positive_minimum = min(item["chi2"] for item in unrestricted)
    return {
        **fit,
        "best_ionic_ratio_in_interval": ratio,
        "positive_quadrant_minimum_chi2": positive_minimum,
        "conditional_profile_deviance": max(0.0, fit["chi2"] - positive_minimum),
        "ratio_interval": [lower, upper],
        "statistical_status": "conditional_gaussian_profile_not_mechanism_probability",
    }


def positive_bounded_interval(record: dict[str, Any]) -> list[float] | None:
    confidence = record["conditional_gaussian_95_fieller_set"]
    if confidence["type"] == "bounded" and confidence["interval"][0] > 0:
        return list(confidence["interval"])
    return None


def spectrum_fits(spectrum: dict[str, Any]) -> list[tuple[np.ndarray, np.ndarray]]:
    """Read fixed-baseline/native flux schemas without an optional atomic solver."""
    if "scenarios" in spectrum:
        fits = [scenario["fit"] for scenario in spectrum["scenarios"]]
    elif "nominal_reference_fit" in spectrum and "point_source_scenarios" in spectrum:
        fits = [spectrum["nominal_reference_fit"], spectrum["point_source_scenarios"][0]]
    else:
        raise ValueError("known fixed baseline or native spectrum-report schema required")
    outputs = []
    for fit in fits:
        if "line_covariance" in fit:
            order = list(fit["lines"])
            flux = np.array([fit["lines"][name]["flux"] for name in order], dtype=float)
            covariance = np.asarray(fit["line_covariance"], dtype=float)
        else:
            order = fit["line_order"]
            flux = np.asarray(fit["fluxes"], dtype=float)
            covariance = np.asarray(fit["flux_covariance"], dtype=float)
        if order != list(LINE_NAMES) or flux.shape != (5,) or not np.all(np.isfinite(flux)):
            raise ValueError("source fit requires the exact finite five-line flux vector")
        if covariance.shape != (5, 5) or not np.all(np.isfinite(covariance)):
            raise ValueError("source fit requires full finite five-line covariance")
        if not np.allclose(covariance, covariance.T) or np.min(np.linalg.eigvalsh(covariance)) <= 0:
            raise ValueError("source fit covariance must be symmetric and positive definite")
        outputs.append((flux, covariance))
    return outputs


def replay_ionic_operator(
    source_fit: tuple[np.ndarray, np.ndarray],
    emissivity: dict[str, float],
    saved_measurement: np.ndarray,
    saved_covariance: np.ndarray,
) -> None:
    """Independently verify lineage, not merely a self-consistent downstream receipt."""
    scale = positive(emissivity["CIII"], "CIII emissivity")
    operator = np.zeros((2, 5))
    for row, names in enumerate((("NIV", "NIII"), ("CIV", "CIII"))):
        for name in names:
            operator[row, LINE_NAMES.index(name)] = scale / positive(
                emissivity[name], f"{name} emissivity"
            )
    flux, covariance = source_fit
    if not np.allclose(
        operator @ flux, saved_measurement, rtol=1e-10, atol=1e-9
    ) or not np.allclose(
        operator @ covariance @ operator.T, saved_covariance, rtol=1e-10, atol=1e-9
    ):
        raise ValueError("ionic data do not replay from the referenced spectrum and atomic grid")


def stage_requirements(record: dict[str, Any], elemental_ceiling: float) -> dict[str, Any]:
    """Largest k allowing a fixed retained-yield ceiling; no prior on k is supplied."""
    elemental_ceiling = positive(elemental_ceiling, "elemental ceiling")
    bounds = positive_bounded_interval(record)
    point = record["value"]
    return {
        "largest_k_reaching_positive_ionic_point": elemental_ceiling / point
        if point is not None and point > 0
        else None,
        "largest_k_with_overlap_at_conditional_95_lower_endpoint": elemental_ceiling / bounds[0]
        if bounds
        else None,
        "equal_k_minimum_N_over_C_retention_ratio_at_point": point / elemental_ceiling
        if point is not None and point > 0
        else None,
        "equal_k_minimum_N_over_C_retention_ratio_at_95_lower_endpoint": bounds[0]
        / elemental_ceiling
        if bounds
        else None,
        "unbounded_or_signed_95_set": bounds is None,
    }


def retention_fractions(values: dict[str, float]) -> dict[str, float]:
    if set(values) != set(ATOMIC_MASS):
        raise ValueError("explicit H/He/C/N/O retention fractions required")
    if any(not math.isfinite(float(v)) or not 0 <= float(v) <= 1 for v in values.values()):
        raise ValueError("each retained element fraction must lie in [0, 1]")
    return {key: float(value) for key, value in values.items()}


def retained_mixture(
    yields: dict[str, float],
    background: dict[str, float],
    target_nc: float,
    retention: dict[str, float],
) -> dict[str, Any]:
    """Solve conserved nuclei for a parcel reaching a specified elemental N/C."""
    target_nc = positive(target_nc, "target N/C")
    retained = retention_fractions(retention)
    background = {key: float(value) for key, value in background.items()}
    if set(background) != set(ATOMIC_MASS) or any(
        not math.isfinite(v) or v <= 0 for v in background.values()
    ):
        raise ValueError("finite positive ambient H/He/C/N/O nuclei required")
    ejecta = {
        key: positive(yields[key], f"ejected {key}") * retained[key] / mass
        for key, mass in ATOMIC_MASS.items()
    }
    initial = background["n"] / background["c"]
    if target_nc <= initial:
        return {"status": "target_not_above_ambient_ratio", "ambient_mass_msun": None}
    excess = ejecta["n"] - target_nc * ejecta["c"]
    if excess <= 0:
        return {"status": "retained_ejecta_cannot_reach_target", "ambient_mass_msun": None}
    mass = excess / (background["c"] * (target_nc - initial))
    nuclei = {key: mass * background[key] + ejecta[key] for key in ATOMIC_MASS}
    return {
        "status": "reachable_conditionally",
        "ambient_mass_msun": mass,
        "elemental_N_over_C": nuclei["n"] / nuclei["c"],
        "log_C_over_O": math.log10(nuclei["c"] / nuclei["o"]),
        "log_N_over_O": math.log10(nuclei["n"] / nuclei["o"]),
        "oxygen_12_log_O_over_H": 12 + math.log10(nuclei["o"] / nuclei["h"]),
        "He_over_H": nuclei["he"] / nuclei["h"],
        "helium_HplusHe_mass_fraction": 4 * nuclei["he"] / (nuclei["h"] + 4 * nuclei["he"]),
    }


def mixture_scenarios(inputs: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    point, bounds = record["value"], positive_bounded_interval(record)
    values = [("point", point)]
    if bounds:
        values += [
            ("conditional_95_lower_endpoint", bounds[0]),
            ("conditional_95_upper_endpoint", bounds[1]),
        ]
    fractions = {
        "full_equal": dict.fromkeys(ATOMIC_MASS, 1.0),
        "tenth_equal": dict.fromkeys(ATOMIC_MASS, 0.1),
        "nitrogen_retention_third_of_carbon": {**dict.fromkeys(ATOMIC_MASS, 0.3), "n": 0.1},
        "nitrogen_retention_triple_carbon": {**dict.fromkeys(ATOMIC_MASS, 0.3), "n": 0.9},
        "nitrogen_retention_tenfold_carbon": {**dict.fromkeys(ATOMIC_MASS, 0.1), "n": 1.0},
    }
    solar = inputs["solar_reference"]
    records = []
    for row in inputs["sms_yields"]["rows"]:
        for carbon_oxygen in (0.0, -0.65):
            ambient = background_nuclei_per_msun(solar, -1.38, carbon_oxygen, 0.0)
            ambient["he"] = 0.25 / 4
            for k in (0.1, 0.3, 1.0, 3.0):
                for label, retention in fractions.items():
                    predictions = []
                    for point_label, ionic_nc in values:
                        if ionic_nc is None or ionic_nc <= 0:
                            predictions.append(
                                {"ionic_target": point_label, "status": "signed_or_undefined_point"}
                            )
                        else:
                            target = ionic_nc * k
                            predictions.append(
                                {
                                    "ionic_target": point_label,
                                    "target_elemental_N_over_C": target,
                                    **retained_mixture(row, ambient, target, retention),
                                }
                            )
                    records.append(
                        {
                            "initial_mass_msun": row["initial_mass"],
                            "ambient_bracket_C_over_O": carbon_oxygen,
                            "stage_fraction_ratio_k": k,
                            "retention_scenario": label,
                            "predictions": predictions,
                        }
                    )
    return {
        "assumptions": {
            "ambient_bracket_O_over_H": -1.38,
            "ambient_bracket_N_over_C": 0.0,
            "ambient_H_mass_fraction": 0.75,
            "ambient_He_mass_fraction": 0.25,
            "trace_metals_neglected_in_ambient_mass_closure": True,
            "retention_fractions": fractions,
        },
        "records": records,
        "interpretation": "Deterministic endpoint sensitivity, not posterior draws. "
        "k and retention unmeasured. Gas-phase C/O and He/H predictions are not ionic line ratios.",
    }


def run_comparison(
    ionic_path: Path, grid_path: Path, spectrum_path: Path, benchmark_path: Path = DEFAULT_INPUT
) -> dict[str, Any]:
    ionic = json.loads(ionic_path.read_text())
    grid = json.loads(grid_path.read_text())
    fits = spectrum_fits(json.loads(spectrum_path.read_text()))
    inputs = json.loads(benchmark_path.read_text())
    receipts = {
        name: {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for name, path in [
            ("ionic", ionic_path),
            ("atomic_grid", grid_path),
            ("spectrum", spectrum_path),
            ("benchmarks", benchmark_path),
        ]
    }
    if ionic["grid_sha256"] != receipts["atomic_grid"]["sha256"]:
        raise ValueError("ionic report does not use these exact atomic-grid bytes")
    if ionic["spectrum_sha256"] != receipts["spectrum"]["sha256"]:
        raise ValueError("ionic report does not use these exact spectrum-report bytes")
    if ionic["ion_fraction_correction_available"] or ionic["scenarios_are_independent_likelihoods"]:
        raise ValueError("this comparison requires explicit uncalibrated, shared-data scenarios")
    if not ionic["models"] or not grid["records"]:
        raise ValueError("nonempty atomic grid and spectrum model list required")
    grid_keys = {(r["temperature_K"], r["electron_density_cm3"]) for r in grid["records"]}
    if len(grid_keys) != len(grid["records"]) or len(ionic["models"]) != len(fits):
        raise ValueError("unique atomic-grid cells and matching spectrum families required")
    emissions = {
        (r["temperature_K"], r["electron_density_cm3"]): r["emissivity_erg_cm3_s"]
        for r in grid["records"]
    }
    families = []
    for index, model in enumerate(ionic["models"]):
        keys = [(r["temperature_K"], r["electron_density_cm3"]) for r in model["records"]]
        if len(keys) != len(set(keys)) or set(keys) != grid_keys:
            raise ValueError("each spectrum family must cover the exact unique atomic grid")
        comparisons = []
        rotating = []
        for record in model["records"]:
            observed = record["observed_two_stage_ionic_N_over_C"]
            x, covariance = check_ionic_measurement(observed)
            replay_ionic_operator(
                fits[index],
                emissions[(record["temperature_K"], record["electron_density_cm3"])],
                x,
                covariance,
            )
            for row in inputs["sms_yields"]["rows"]:
                ceiling = number_ratio(row, "n", "c")
                fixed = profile_ionic_ratio_interval(x, covariance, 10**-0.6, ceiling)
                comparisons.append(
                    {
                        "temperature_K": record["temperature_K"],
                        "electron_density_cm3": record["electron_density_cm3"],
                        "initial_mass_msun": row["initial_mass"],
                        "pure_equal_retention_elemental_N_over_C_ceiling": ceiling,
                        **stage_requirements(observed, ceiling),
                        "profile_if_k1_equal_retention_ambient_solar_NC": fixed,
                    }
                )
            for row in inputs["rotating_models"]["rows"]:
                ratio = 10 ** (row["log_n_o"] - row["log_c_o"])
                bounds = positive_bounded_interval(observed)
                rotating.append(
                    {
                        "temperature_K": record["temperature_K"],
                        "electron_density_cm3": record["electron_density_cm3"],
                        "scenario": row["scenario"],
                        "stellar_initial_z": row["z"],
                        "predicted_elemental_N_over_C": ratio,
                        "predicted_log_C_over_O": row["log_c_o"],
                        "predicted_log_C12_over_C13": row["log_c12_c13"],
                        "required_k_at_ionic_point": ratio / observed["value"]
                        if observed["value"] is not None and observed["value"] > 0
                        else None,
                        "conditional_95_required_k_interval": [ratio / bounds[1], ratio / bounds[0]]
                        if bounds
                        else None,
                        "profile_if_k1": profile_ionic_ratio_interval(x, covariance, ratio, ratio),
                    }
                )
        summaries = []
        for row in inputs["sms_yields"]["rows"]:
            group = [r for r in comparisons if r["initial_mass_msun"] == row["initial_mass"]]
            summary = {"initial_mass_msun": row["initial_mass"], "atomic_cells": len(group)}
            for key in (
                "largest_k_reaching_positive_ionic_point",
                "largest_k_with_overlap_at_conditional_95_lower_endpoint",
            ):
                values = [r[key] for r in group if r[key] is not None]
                summary[key + "_range"] = [min(values), max(values)] if values else None
            deviances = [
                r["profile_if_k1_equal_retention_ambient_solar_NC"]["conditional_profile_deviance"]
                for r in group
            ]
            summary["fixed_k1_equal_retention_profile_deviance_range"] = [
                min(deviances),
                max(deviances),
            ]
            summary["atomic_cells_exceeding_conditional_95_reference_deviance"] = sum(
                value > SIGMA_95**2 for value in deviances
            )
            summary["count_status"] = "deterministic_grid_count_not_probability"
            summaries.append(summary)
        reference = next(
            (
                r
                for r in model["records"]
                if r["temperature_K"] == 20000 and r["electron_density_cm3"] == 1000
            ),
            None,
        )
        rotator_summaries = []
        for row in inputs["rotating_models"]["rows"]:
            group = [
                r
                for r in rotating
                if r["scenario"] == row["scenario"] and r["stellar_initial_z"] == row["z"]
            ]
            deviations = [r["profile_if_k1"]["conditional_profile_deviance"] for r in group]
            rotator_summaries.append(
                {
                    "scenario": row["scenario"],
                    "stellar_initial_z": row["z"],
                    "predicted_log_C_over_O": row["log_c_o"],
                    "fixed_k1_profile_deviance_range": [min(deviations), max(deviations)],
                    "atomic_cells_exceeding_conditional_95_reference_deviance": sum(
                        value > SIGMA_95**2 for value in deviations
                    ),
                    "count_status": "deterministic_grid_count_not_probability",
                }
            )
        families.append(
            {
                "model_index": index,
                "model_label": model.get("model_label", f"atomic_model_{index}"),
                "extraction": model.get("extraction"),
                "resolution_family": model.get("resolution_family"),
                "reference_20000K_1000cm3_ionic_ratio": reference[
                    "observed_two_stage_ionic_N_over_C"
                ]
                if reference
                else None,
                "summaries": summaries,
                "cell_comparisons": comparisons,
                "selected_rotator_fixed_ratio_comparisons": rotating,
                "selected_rotator_summaries": rotator_summaries,
                "reference_20000K_1000cm3_mixing": mixture_scenarios(
                    inputs, reference["observed_two_stage_ionic_N_over_C"]
                )
                if reference
                else None,
            }
        )
    z = inputs["mom_z14_model_parameters"]["redshift"]["median"]
    histories = []
    wr, vms = inputs["wr_time_benchmarks"], inputs["vms_benchmark"]
    for label, duration, source in [
        ("LMC_like_VMS_nitrogen_release_benchmark", vms["timescale_myr_approx"], vms),
        ("transferred_WR_short_history", wr["shorter_total_history_myr"], wr),
        ("transferred_WR_fiducial_history", wr["fiducial_total_history_myr"], wr),
        ("illustrative_AGB_delay_assumption_lower_endpoint", wr["agb_delay_range_myr"][0], wr),
        ("illustrative_AGB_delay_assumption_upper_endpoint", wr["agb_delay_range_myr"][1], wr),
    ]:
        histories.append(
            {
                "history": label,
                "duration_myr": duration,
                "source_url": source["source_url"],
                "source_location": source["location"],
                "status": "transferred_or_illustrative_history_benchmark_not_MoM_lifetime_fit",
                "minimum_onset_redshift_Planck18": required_formation_redshift(z, duration),
                "margin_since_assumed_onset_z20_myr": time_budget_myr(z, 20.0) - duration,
            }
        )
    return {
        "schema_version": 1,
        "input_receipts": receipts,
        "ionic_operator_lineage_independently_replayed": True,
        "status": "atomic_informed_conditional_yield_constraints_not_mechanism_identification",
        "observational_target": "(N2+ + N3+) / (C2+ + C3+) in a shared homogeneous phase",
        "elemental_NC_identity": "elemental_NC = ionic_NC * k; k=f_C_observed/f_N_observed",
        "ion_fraction_ratio_k_calibrated": False,
        "families_are_independent_likelihoods": False,
        "assumptions": [
            "All atomic and extraction assumptions remain in force",
            "No resonant CIV transfer or stellar contribution correction supplied",
            "Fixed-k tests additionally assume gas shares the selected yield mixture",
            "Metal-bearing ambient gas N/C is solar for fixed-k ceiling profiles",
            "Pure equal-retention ceilings use four discrete 0.1-solar SMS models",
            "Signed Gaussian data retained; model normalization is nonnegative",
            "95 reference deviance is conditional one-ratio Gaussian sensitivity",
            "Atomic grid cells and extraction families are not independent trials",
        ],
        "spectrum_families": families,
        "formation_clocks": {
            "observed_redshift": z,
            "cosmology": "Astropy Planck18",
            "histories": histories,
            "yield_clock_link_identified": False,
            "interpretation": "Clock feasibility does not fit chemical yields. "
            "Selected SMS/rotator yields have no assigned complete formation history.",
        },
        "identified_mechanism_exclusions": [],
        "mechanism_probabilities": None,
        "remaining_discriminators": [
            "Calibrated photoionization stage fractions and CIV transfer",
            "Separated OIII/HeII with hydrogen lines, density and temperature",
            "Emitting gas mass and element-dependent retention",
            "Full stellar yield grids and complete formation histories",
            "Completeness-controlled galaxy population for cosmology",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ionic-report", type=Path, default=ROOT / "research_output/mom_ionic_fit.json"
    )
    parser.add_argument("--grid", type=Path, default=ROOT / "research_output/mom_atomic_grid.json")
    parser.add_argument(
        "--spectrum", type=Path, default=ROOT / "research_output/mom_z14_point_resolution.json"
    )
    parser.add_argument("--benchmarks", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "research_output/atomic_enrichment.json"
    )
    args = parser.parse_args()
    result = run_comparison(args.ionic_report, args.grid, args.spectrum, args.benchmarks)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "families": len(result["spectrum_families"]),
                "mechanisms_identified": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
