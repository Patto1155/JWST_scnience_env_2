"""Conditional assembly predictions from a quoted model-dependent stellar mass.

This separates model-dependent mass input, explicit histories/retention inputs,
and resulting SFR/clock/baryon accounting. It supplies a selection-forward
contract, not a galaxy population likelihood or a cosmological anomaly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
from astropy.cosmology import Planck18

from discovery.enrichment_constraints import (
    DEFAULT_INPUT,
    ROOT,
    cosmic_age_myr,
    required_formation_redshift,
    time_budget_myr,
)

DEFAULT_SCENARIOS = ROOT / "data_sources/pilot/formation_scenarios.json"
DEFAULT_ENRICHMENT = ROOT / "research_output/atomic_enrichment_native.json"


def finite(value: float, name: str, positive: bool = False) -> float:
    value = float(value)
    if not math.isfinite(value) or (value <= 0 if positive else value < 0):
        raise ValueError(f"{name} must be finite and {'positive' if positive else 'nonnegative'}")
    return value


def history_parameters(duty: float, returned: float, tau_myr: float | None) -> None:
    if not 0 < finite(duty, "duty", positive=True) <= 1:
        raise ValueError("duty must lie in (0, 1]")
    if not 0 <= finite(returned, "returned fraction") < 1:
        raise ValueError("returned fraction must lie in [0, 1)")
    if tau_myr is not None:
        finite(tau_myr, "rising e-fold time", positive=True)


def quoted_mass_as_surviving(quoted_msun: float, returned: float, convention: str) -> float:
    mass = finite(quoted_msun, "quoted stellar mass", True)
    history_parameters(1.0, returned, None)
    if convention == "current_surviving":
        return mass
    if convention == "cumulative_formed":
        return mass * (1 - returned)
    raise ValueError("explicit current_surviving or cumulative_formed convention required")


def envelope_integral_years(duration_myr: float, tau_myr: float | None) -> float:
    """Integral of exp((t-T)/tau), normalized to today's active SFR envelope."""
    duration = finite(duration_myr, "duration", positive=True)
    if tau_myr is None:
        return duration * 1e6
    tau = finite(tau_myr, "rising e-fold time", positive=True)
    return tau * (-math.expm1(-duration / tau)) * 1e6


def required_active_sfr(
    surviving_mass_msun: float,
    duration_myr: float,
    duty: float = 1.0,
    returned: float = 0.0,
    tau_myr: float | None = None,
) -> dict[str, float]:
    """Use M_surv=(1-R)*duty*SFR_active_now*integral(envelope)."""
    mass = finite(surviving_mass_msun, "surviving stellar mass", positive=True)
    history_parameters(duty, returned, tau_myr)
    duration = finite(duration_myr, "duration", positive=True)
    formed = mass / (1 - returned)
    active = formed / (duty * envelope_integral_years(duration, tau_myr))
    return {
        "formed_stellar_mass_msun": formed,
        "required_current_active_sfr_msun_per_year": active,
        "current_time_averaged_sfr_msun_per_year": duty * active,
        "history_mean_sfr_msun_per_year": formed / (duration * 1e6),
        "active_sfr_at_onset_msun_per_year": active
        if tau_myr is None
        else active * math.exp(-duration / tau_myr),
    }


def required_duration_myr(
    surviving_mass_msun: float,
    active_sfr_msun_per_year: float,
    duty: float = 1.0,
    returned: float = 0.0,
    tau_myr: float | None = None,
) -> float | None:
    """Invert the same history; None means even its infinite-time mass is too small."""
    mass = finite(surviving_mass_msun, "surviving stellar mass", positive=True)
    sfr = finite(active_sfr_msun_per_year, "active SFR", positive=True)
    history_parameters(duty, returned, tau_myr)
    equivalent_years = mass / ((1 - returned) * duty * sfr)
    if tau_myr is None:
        return equivalent_years / 1e6
    fraction_of_asymptotic_mass = equivalent_years / (tau_myr * 1e6)
    if fraction_of_asymptotic_mass >= 1:
        return None
    return -tau_myr * math.log1p(-fraction_of_asymptotic_mass)


def averaged_sfr_and_halfmass(
    current_active_sfr: float,
    duration_myr: float,
    duty: float,
    tau_myr: float | None,
) -> dict[str, float]:
    """Trailing-window means and half-formed-mass lookback under the same envelope."""
    active = finite(current_active_sfr, "active SFR", True)
    duration = finite(duration_myr, "duration", True)
    history_parameters(duty, 0.0, tau_myr)
    means = {
        f"sfr_last_{window}_myr_msun_per_year": duty
        * active
        * envelope_integral_years(min(window, duration), tau_myr)
        / (window * 1e6)
        for window in (5, 50)
    }
    halfmass = (
        duration / 2
        if tau_myr is None
        else -tau_myr * math.log1p(0.5 * math.expm1(-duration / tau_myr))
    )
    return {**means, "halfmass_lookback_myr": halfmass}


def marginal_sed_endpoint_checks(
    prediction: dict[str, float], benchmarks: dict[str, Any]
) -> dict[str, Any]:
    checks = {
        key: value["median"] - value["minus"] <= prediction[key] <= value["median"] + value["plus"]
        for key, value in benchmarks.items()
        if isinstance(value, dict)
    }
    return {
        "individual_marginal_endpoint_checks": checks,
        "inside_all_marginal_endpoint_intervals": all(checks.values()),
        "is_joint_confidence_or_model_likelihood": False,
    }


def closed_parcel_budget(
    surviving_mass_msun: float,
    remaining_gas_msun: float = 0.0,
    returned: float = 0.0,
    outflow_per_formed_mass: float = 0.0,
    initial_available_baryon_fraction: float = 1.0,
) -> dict[str, float]:
    """Conserved closed-parcel mass with recycling, permanent wind loss and no inflow.

    M_initial_gas = M_surv + M_remaining + eta*M_formed. The return R changes
    the cumulative formed mass, not the surviving stellar mass counted twice.
    This necessary accounting condition is not a measured halo mass or a
    sufficient gas-cooling/star-formation calculation.
    """
    mass = finite(surviving_mass_msun, "surviving stellar mass", positive=True)
    gas = finite(remaining_gas_msun, "remaining gas")
    eta = finite(outflow_per_formed_mass, "outflow per formed mass")
    history_parameters(1.0, returned, None)
    retained = finite(initial_available_baryon_fraction, "available baryon fraction", True)
    if retained > 1:
        raise ValueError("initial available cosmic baryon fraction cannot exceed one")
    formed = mass / (1 - returned)
    wind_loss = eta * formed
    initial_gas = mass + gas + wind_loss
    cosmic_baryon_fraction = float(Planck18.Ob0 / Planck18.Om0)
    return {
        "cumulative_formed_stellar_mass_msun": formed,
        "permanently_lost_wind_mass_msun": wind_loss,
        "minimum_initial_gas_mass_msun": initial_gas,
        "minimum_halo_mass_msun_under_closed_allowance": initial_gas
        / (cosmic_baryon_fraction * retained),
        "cosmic_baryon_fraction_Planck18": cosmic_baryon_fraction,
    }


def selection_forward_counts(
    parent_expected_counts: np.ndarray,
    observable_phase_probability: np.ndarray,
    response: np.ndarray,
) -> np.ndarray:
    """Map externally supplied parent counts through phase and selection/scatter.

    Each response column is a subprobability distribution over selected bins;
    missing probability denotes a missed parent. This operator supplies no halo
    mass function, survey volume, calibrated phase probabilities or completeness.
    UV afterglow means a time duty fraction is generally not the observable phase
    probability. Contamination must enter as separately modeled selected counts.
    """
    parent = np.asarray(parent_expected_counts, dtype=float)
    phase = np.asarray(observable_phase_probability, dtype=float)
    operator = np.asarray(response, dtype=float)
    if (
        parent.ndim != 1
        or phase.shape != parent.shape
        or operator.ndim != 2
        or operator.shape[1] != len(parent)
        or len(parent) == 0
    ):
        raise ValueError("aligned nonempty parent/phase vectors and selection matrix required")
    if any(not np.all(np.isfinite(x)) for x in (parent, phase, operator)):
        raise ValueError("finite parent counts, phase probabilities and selection required")
    if (
        np.any(parent < 0)
        or np.any(phase < 0)
        or np.any(phase > 1)
        or np.any(operator < 0)
        or np.any(operator.sum(axis=0) > 1 + 1e-12)
    ):
        raise ValueError("nonnegative counts and subprobability phase/selection operators required")
    return operator @ (parent * phase)


def polluter_mass_budget(
    ambient_gas_msun: float,
    ambient_mass_per_event_msun: float,
    initial_polluter_mass_msun: float,
    surviving_stellar_mass_msun: float,
    returned: float,
) -> dict[str, float | int]:
    """Event-equivalent lower mass cost conditional on a fixed retained mixed yield."""
    gas = finite(ambient_gas_msun, "polluted ambient mass", True)
    per_event = finite(ambient_mass_per_event_msun, "ambient mass per event", True)
    initial = finite(initial_polluter_mass_msun, "polluter initial mass", True)
    stellar = finite(surviving_stellar_mass_msun, "surviving stellar mass", True)
    history_parameters(1.0, returned, None)
    equivalents = gas / per_event
    formed = stellar / (1 - returned)
    return {
        "required_event_equivalents": equivalents,
        "whole_events_with_at_least_this_budget": math.ceil(equivalents),
        "required_initial_polluter_mass_msun_event_equivalent": equivalents * initial,
        "initial_polluter_mass_fraction_of_formed_stars_event_equivalent": equivalents
        * initial
        / formed,
    }


def run_predictions(
    benchmarks: Path = DEFAULT_INPUT,
    scenarios_path: Path = DEFAULT_SCENARIOS,
    enrichment_path: Path = DEFAULT_ENRICHMENT,
) -> dict[str, Any]:
    inputs = json.loads(benchmarks.read_text())
    assumptions = json.loads(scenarios_path.read_text())
    enrichment = json.loads(enrichment_path.read_text())
    if (
        enrichment["input_receipts"]["benchmarks"]["sha256"]
        != hashlib.sha256(benchmarks.read_bytes()).hexdigest()
    ):
        raise ValueError("formation and enrichment must use the same versioned benchmark bytes")
    mom = inputs["mom_z14_model_parameters"]
    log_mass = mom["log_stellar_mass_msun"]
    masses = [
        log_mass["median"] - log_mass["minus"],
        log_mass["median"],
        log_mass["median"] + log_mass["plus"],
    ]
    z = mom["redshift"]["median"]
    windows = [
        {
            "type": "specified_formation_onset",
            "formation_redshift": onset,
            "duration_myr": time_budget_myr(z, onset),
        }
        for onset in assumptions["formation_onset_redshifts"]
    ]
    windows += [
        {
            "type": "counterfactual_complete_recent_assembly",
            "formation_redshift": None,
            "duration_myr": duration,
        }
        for duration in assumptions["recent_complete_assembly_windows_myr"]
    ]
    histories = []
    for convention, dex, window, tau, duty, returned in product(
        assumptions["quoted_mass_conventions"],
        masses,
        windows,
        assumptions["rising_sfr_efold_myr"],
        assumptions["time_duty_fractions"],
        assumptions["effective_returned_mass_fractions"],
    ):
        surviving = quoted_mass_as_surviving(10**dex, returned, convention)
        predicted = required_active_sfr(surviving, window["duration_myr"], duty, returned, tau)
        timed = averaged_sfr_and_halfmass(
            predicted["required_current_active_sfr_msun_per_year"],
            window["duration_myr"],
            duty,
            tau,
        )
        histories.append(
            {
                "log_quoted_stellar_mass_msun": dex,
                "quoted_mass_convention_assumed": convention,
                "surviving_stellar_mass_assumed_msun": surviving,
                **window,
                "rising_efold_myr": tau,
                "time_duty_fraction": duty,
                "effective_returned_fraction": returned,
                **predicted,
                **timed,
                "published_sed_marginal_checks": marginal_sed_endpoint_checks(
                    timed, assumptions["published_model_sfr_and_halfmass_benchmarks"]
                ),
            }
        )
    inverse = []
    for convention, tau, duty, sfr in product(
        assumptions["quoted_mass_conventions"],
        assumptions["rising_sfr_efold_myr"],
        assumptions["inverse_duty_fractions"],
        assumptions["inverse_active_sfr_msun_per_year"],
    ):
        returned = assumptions["inverse_returned_mass_fraction"]
        surviving = quoted_mass_as_surviving(10 ** log_mass["median"], returned, convention)
        duration = required_duration_myr(surviving, sfr, duty, returned, tau)
        inverse.append(
            {
                "quoted_mass_convention_assumed": convention,
                "active_sfr_msun_per_year_assumed": sfr,
                "rising_efold_myr_assumed": tau,
                "time_duty_fraction_assumed": duty,
                "effective_returned_fraction_assumed": returned,
                "required_duration_myr": duration,
                "asymptotic_history_can_build_mass": duration is not None,
                "fits_assumed_onset_z20_budget": duration is not None
                and duration <= time_budget_myr(z, 20.0),
                "minimum_onset_redshift_if_history_feasible": None
                if duration is None
                else required_formation_redshift(z, duration),
            }
        )
    baryons = []
    for convention, dex, returned, eta, retained, gas in product(
        assumptions["quoted_mass_conventions"],
        masses,
        assumptions["effective_returned_mass_fractions"],
        assumptions["permanently_lost_outflow_mass_per_formed_stellar_mass"],
        assumptions["initial_available_cosmic_baryon_fractions"],
        assumptions["remaining_gas_mass_msun"],
    ):
        surviving = quoted_mass_as_surviving(10**dex, returned, convention)
        budget = closed_parcel_budget(surviving, gas, returned, eta, retained)
        baryons.append(
            {
                "log_quoted_stellar_mass_msun": dex,
                "quoted_mass_convention_assumed": convention,
                "surviving_stellar_mass_assumed_msun": surviving,
                "effective_returned_fraction": returned,
                "wind_mass_per_formed_stellar_mass": eta,
                "initial_available_baryon_fraction": retained,
                "remaining_gas_mass_msun_assumed": gas,
                **budget,
                "hypothetical_halo_accounting_tests": [
                    {
                        "halo_mass_msun_assumed": halo,
                        "required_fraction_of_available_initial_baryons": budget[
                            "minimum_halo_mass_msun_under_closed_allowance"
                        ]
                        / halo,
                        "accounting_feasible": halo
                        >= budget["minimum_halo_mass_msun_under_closed_allowance"],
                    }
                    for halo in assumptions["hypothetical_halo_masses_msun"]
                ],
            }
        )
    family = next(
        model
        for model in enrichment["spectrum_families"]
        if model["resolution_family"] == "point_empirical_offtrace_transport"
    )
    mixture = family["reference_20000K_1000cm3_mixing"]
    polluters = []
    for row in mixture["records"]:
        if (
            row["stage_fraction_ratio_k"] != assumptions["polluter_stage_fraction_ratio_k"]
            or row["ambient_bracket_C_over_O"] != assumptions["polluter_ambient_bracket_C_over_O"]
            or row["retention_scenario"] not in assumptions["polluter_retention_scenarios"]
        ):
            continue
        point = next(
            prediction for prediction in row["predictions"] if prediction["ionic_target"] == "point"
        )
        for convention, gas in product(
            assumptions["quoted_mass_conventions"],
            assumptions["hypothetical_polluted_ambient_gas_masses_msun"],
        ):
            returned = assumptions["inverse_returned_mass_fraction"]
            surviving = quoted_mass_as_surviving(10 ** log_mass["median"], returned, convention)
            budget = (
                None
                if point["ambient_mass_msun"] is None
                else polluter_mass_budget(
                    gas, point["ambient_mass_msun"], row["initial_mass_msun"], surviving, returned
                )
            )
            polluters.append(
                {
                    "initial_polluter_mass_msun": row["initial_mass_msun"],
                    "quoted_mass_convention_assumed": convention,
                    "retention_scenario": row["retention_scenario"],
                    "hypothetical_ambient_gas_msun": gas,
                    "mixture_reaches_conditional_target": budget is not None,
                    "budget": budget,
                }
            )
    control = selection_forward_counts(
        np.ones(2), np.array([0.1, 0.5]), np.array([[0.3, 0.1], [0.2, 0.4]])
    )
    ionic_reference = family["reference_20000K_1000cm3_ionic_ratio"]
    confidence = ionic_reference["conditional_gaussian_95_fieller_set"]
    ambient_ionic_ratio = 10**-0.6 / assumptions["polluter_stage_fraction_ratio_k"]
    ambient_within_conditional_set = (
        None
        if confidence["type"] != "bounded"
        else (confidence["interval"][0] <= ambient_ionic_ratio <= confidence["interval"][1])
    )
    return {
        "schema_version": 1,
        "status": "conditional_history_predictions_not_population_or_cosmology_inference",
        "input_receipts": {
            label: {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for label, path in [
                ("published_benchmarks", benchmarks),
                ("explicit_scenarios", scenarios_path),
                ("native_enrichment", enrichment_path),
            ]
        },
        "model_dependent_observational_input": {
            "source_url": mom["source_url"],
            "source_location": mom["location"],
            "quoted_log_stellar_mass_msun": log_mass,
            "mass_convention_identified": False,
            "mass_convention_provenance": assumptions["mass_convention_provenance"],
            "alternative_histories_refit_to_stellar_SED": False,
            "redshift": mom["redshift"],
            "endpoints_status": "marginal_sensitivity_not_joint_posterior",
        },
        "assumptions": assumptions,
        "clock": {
            "cosmology": "Astropy Planck18",
            "cosmic_age_at_median_z_myr": cosmic_age_myr(z),
            "since_assumed_z20_onset_myr": time_budget_myr(z, 20.0),
        },
        "history_predictions": histories,
        "inverse_history_tests": inverse,
        "closed_parcel_baryon_budgets": baryons,
        "conditional_sms_mass_budgets": {
            "ionic_reference": ionic_reference,
            "ambient_only_ionic_ratio_at_assumed_k": ambient_ionic_ratio,
            "ambient_only_ratio_inside_reference_conditional_95_set": (
                ambient_within_conditional_set
            ),
            "positive_minimum_polluter_mass_fraction_established": False,
            "stage_fraction_ratio_k_assumed": assumptions["polluter_stage_fraction_ratio_k"],
            "ambient_composition_assumptions": mixture["assumptions"],
            "records": polluters,
            "guard": "Unmeasured gas mass and stage/retention assumptions; event-equivalent "
            "budget does not prove polluter formation or constrain its IMF. Whole event "
            "rounding needs dilution/retention adjustment to match an exact ratio.",
        },
        "selection_forward_contract": {
            "operator": "lambda_selected = response @ (lambda_parent * p_observable_phase) "
            "+ lambda_contamination",
            "calibrated_population_inputs_available": False,
            "time_duty_equals_observable_phase_probability": False,
            "synthetic_dimensionless_operator_control": {
                "arbitrary_parent_units": [1.0, 1.0],
                "phase_probabilities": [0.1, 0.5],
                "selection_scatter_response": [[0.3, 0.1], [0.2, 0.4]],
                "selected_unit_weights": control.tolist(),
                "is_observed_population": False,
            },
            "required_external_inputs": [
                "Versioned halo abundance, volume, field variance and lensing",
                "Stellar/gas assembly, IMF, metallicity, dust and age-dependent return",
                "UV/nebular emission kernels and phase distribution, including afterglow",
                "Magnitude/size/SED/position selection and bin-scatter calibration",
                "Contamination likelihood and independent source validation",
            ],
            "testable_contract": "Competing cosmologies must predict the same selected observables "
            "under versioned astrophysical/measurement nuisance models. Use joint "
            "field likelihoods or posterior predictive tests after calibration.",
        },
        "rejected_astrophysical_mechanisms": [],
        "cosmology_probabilities": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmarks", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--enrichment", type=Path, default=DEFAULT_ENRICHMENT)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "research_output/formation_predictions.json"
    )
    args = parser.parse_args()
    result = run_predictions(args.benchmarks, args.scenarios, args.enrichment)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "histories": len(result["history_predictions"]),
                "population_likelihood_available": False,
            }
        )
    )


if __name__ == "__main__":
    main()
