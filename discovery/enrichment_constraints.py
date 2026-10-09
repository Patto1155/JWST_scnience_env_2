"""Conditional clocks and conserved-element mixing; no line-to-abundance conversion.

All abundance ratios are by number. Stellar yields are input masses and are
divided by atomic mass before mixing. Marginal published endpoints are evaluated
as sensitivity cases, never as an independent-Gaussian likelihood or posterior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import astropy.units as u
from astropy.cosmology import Planck18, z_at_value

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data_sources/pilot/enrichment_benchmarks.json"
ATOMIC_MASS = {"h": 1.0, "he": 4.0, "c": 12.0, "n": 14.0, "o": 16.0}


def _finite(value: float, name: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def cosmic_age_myr(redshift: float) -> float:
    """Planck18 age including the preset's radiation and neutrino treatment."""
    if _finite(redshift, "redshift") < 0:
        raise ValueError("redshift must be nonnegative")
    return float(Planck18.age(redshift).to_value(u.Myr))


def time_budget_myr(observed_z: float, formation_z: float) -> float:
    if formation_z < observed_z:
        raise ValueError("formation must precede observation (formation_z >= observed_z)")
    return cosmic_age_myr(observed_z) - cosmic_age_myr(formation_z)


def required_formation_redshift(observed_z: float, duration_myr: float) -> float | None:
    """Minimum onset redshift for a total delay; None if older than the Universe."""
    if _finite(duration_myr, "duration_myr") < 0:
        raise ValueError("duration must be nonnegative")
    if duration_myr == 0:
        return observed_z
    onset_age = cosmic_age_myr(observed_z) - duration_myr
    if onset_age <= 0:
        return None
    return float(z_at_value(Planck18.age, onset_age * u.Myr, zmin=observed_z, zmax=10000))


def number_ratio(yields: dict[str, Any], numerator: str, denominator: str) -> float:
    """Convert published ejecta mass to a number ratio, using integer atomic masses."""
    a = float(yields[numerator])
    b = float(yields[denominator])
    if _finite(a, numerator) < 0 or _finite(b, denominator) <= 0:
        raise ValueError("nonnegative numerator and positive denominator required")
    return (a / ATOMIC_MASS[numerator]) / (b / ATOMIC_MASS[denominator])


def bracket_to_number_ratio(bracket: float, solar_log_ratio: float) -> float:
    return 10.0 ** (_finite(bracket, "bracket") + _finite(solar_log_ratio, "solar_log_ratio"))


def carbon_processing_fraction(target_nc: float, initial_nc: float) -> float:
    """Carbon nuclei fraction converted to N, holding initial C+N nuclei fixed.

    This is an algebraic endpoint, not a stellar yield. It excludes O processing,
    new primary CNO nuclei, dilution, and differential retention.
    """
    if not 0 <= _finite(initial_nc, "initial_nc") <= _finite(target_nc, "target_nc"):
        raise ValueError("target must be at least the nonnegative initial ratio")
    return (target_nc - initial_nc) / (1.0 + target_nc)


def required_halo_mass(stellar_mass_msun: float, stellar_baryon_efficiency: float) -> float:
    """Conditional baryon accounting; no halo mass function or prevalence claim.

    Efficiency is M_star/(f_b M_halo), with Planck18 cosmic f_b. This supposes
    initially cosmic baryon content, no extra baryon concentration, and ignores
    expelled gas, gas still present, and stellar mass returned to the ISM.
    """
    if _finite(stellar_mass_msun, "stellar_mass_msun") <= 0:
        raise ValueError("stellar mass must be positive")
    if not 0 < _finite(stellar_baryon_efficiency, "efficiency") <= 1:
        raise ValueError("efficiency must lie in (0, 1]")
    return stellar_mass_msun / (float(Planck18.Ob0 / Planck18.Om0) * stellar_baryon_efficiency)


def background_nuclei_per_msun(
    solar: dict[str, float],
    bracket_oh: float,
    bracket_co: float,
    bracket_nc: float,
    hydrogen_mass_fraction: float = 0.75,
) -> dict[str, float]:
    """Ambient nuclei in common M_sun/m_u units; composition is a stated scenario."""
    xh = _finite(hydrogen_mass_fraction, "hydrogen_mass_fraction")
    if not 0 < xh < 1:
        raise ValueError("hydrogen mass fraction must lie between zero and one")
    oh = 10 ** (solar["oxygen_12_log_o_h"] - 12 + _finite(bracket_oh, "bracket_oh"))
    co = bracket_to_number_ratio(bracket_co, solar["log_c_o"])
    nc = bracket_to_number_ratio(bracket_nc, solar["log_n_o"] - solar["log_c_o"])
    return {"h": xh, "o": xh * oh, "c": xh * oh * co, "n": xh * oh * co * nc}


def maximum_ambient_mass(
    yields: dict[str, Any],
    background: dict[str, float],
    target_nc: float,
    retention: float = 1.0,
) -> float | None:
    """Largest ambient mass enriched to target N/C by one retained ejecta.

    Requires target above the initial gas ratio. Returns None if even pure ejecta
    cannot reach the target. Equal retention multiplies every ejected element.
    The bound is for a gas parcel, not the total stellar or galaxy mass.
    """
    if not 0 <= _finite(retention, "retention") <= 1:
        raise ValueError("retention must be within [0, 1]")
    _finite(target_nc, "target_nc")
    nc_initial = background["n"] / background["c"]
    if target_nc <= nc_initial:
        raise ValueError("target must exceed initial ambient N/C")
    excess = float(yields["n"]) / 14 - target_nc * float(yields["c"]) / 12
    if excess <= 0 or retention == 0:
        return None
    return retention * excess / (background["c"] * (target_nc - nc_initial))


def mixture_abundances(
    yields: dict[str, Any],
    background: dict[str, float],
    ambient_mass: float,
    solar: dict[str, float],
    retention: float = 1.0,
) -> dict[str, float]:
    """Homogeneous, equal-retention mixing, including ejecta hydrogen."""
    if _finite(ambient_mass, "ambient_mass") < 0 or not 0 <= retention <= 1:
        raise ValueError("nonnegative mass and retention within [0, 1] required")
    nuclei = {
        element: ambient_mass * background[element]
        + retention * float(yields[element]) / ATOMIC_MASS[element]
        for element in ("h", "c", "n", "o")
    }
    if any(not math.isfinite(value) or value <= 0 for value in nuclei.values()):
        raise ValueError("mixed H/C/N/O nuclei must be finite and positive")
    log_nc = math.log10(nuclei["n"] / nuclei["c"])
    return {
        "log_n_c": log_nc,
        "bracket_n_c": log_nc - (solar["log_n_o"] - solar["log_c_o"]),
        "log_n_o": math.log10(nuclei["n"] / nuclei["o"]),
        "log_c_o": math.log10(nuclei["c"] / nuclei["o"]),
        "oxygen_12_log_o_h": 12 + math.log10(nuclei["o"] / nuclei["h"]),
    }


def run_constraints(input_path: Path = DEFAULT_INPUT) -> dict[str, Any]:
    raw = input_path.read_bytes()
    inputs = json.loads(raw)
    solar = inputs["solar_reference"]
    solar_log_nc = solar["log_n_o"] - solar["log_c_o"]
    mom = inputs["mom_z14_model_parameters"]
    redshift = mom["redshift"]["median"]
    z_endpoints = [redshift - mom["redshift"]["minus"], redshift + mom["redshift"]["plus"]]
    nc = mom["bracket_n_c"]
    nc_cases = [nc["median"] - nc["minus"], nc["median"], nc["median"] + nc["plus"]]
    oh = mom["bracket_o_h"]
    oh_cases = [oh["median"] - oh["minus"], oh["median"], oh["median"] + oh["plus"]]
    wr = inputs["wr_time_benchmarks"]
    times = [
        2.0,
        4.0,
        40.0,
        100.0,
        wr["shorter_total_history_myr"],
        150.0,
        wr["fiducial_total_history_myr"],
    ]
    age = cosmic_age_myr(redshift)
    clocks = {
        "cosmology": str(Planck18),
        "cosmic_age_myr": age,
        "redshift_endpoint_age_range_myr": sorted(map(cosmic_age_myr, z_endpoints)),
        "formation_grid": [
            {"formation_z": z, "available_myr": time_budget_myr(redshift, z)}
            for z in (20.0, 25.0, 30.0, 40.0)
        ],
        "delay_requirements": [
            {"delay_myr": t, "minimum_formation_z": required_formation_redshift(redshift, t)}
            for t in times
        ],
        "wr_fiducial_margin_if_formation_z20_myr": time_budget_myr(redshift, 20)
        - wr["fiducial_total_history_myr"],
        "wr_shorter_margin_if_formation_z20_myr": time_budget_myr(redshift, 20)
        - wr["shorter_total_history_myr"],
    }
    yield_ratios = []
    mixing = []
    for row in inputs["sms_yields"]["rows"]:
        log_nc = math.log10(number_ratio(row, "n", "c"))
        yield_ratios.append(
            {
                "initial_mass_msun": row["initial_mass"],
                "channel": row["channel"],
                "log_n_c": log_nc,
                "bracket_n_c": log_nc - solar_log_nc,
                "log_n_o": math.log10(number_ratio(row, "n", "o")),
                "log_c_o": math.log10(number_ratio(row, "c", "o")),
                "median_target_reachable_with_equal_retention": log_nc - solar_log_nc
                >= nc["median"],
            }
        )
        for oh_case in oh_cases:
            for co_background in (0.0, -0.65):
                for nc_background in (-0.6, 0.0):
                    background = background_nuclei_per_msun(
                        solar, oh_case, co_background, nc_background
                    )
                    for bracket_nc in nc_cases:
                        target = bracket_to_number_ratio(bracket_nc, solar_log_nc)
                        for retention in (0.1, 0.3, 1.0):
                            maximum = maximum_ambient_mass(row, background, target, retention)
                            mixed = (
                                None
                                if maximum is None
                                else mixture_abundances(row, background, maximum, solar, retention)
                            )
                            mixing.append(
                                {
                                    "initial_mass_msun": row["initial_mass"],
                                    "background_bracket_o_h": oh_case,
                                    "background_bracket_c_o": co_background,
                                    "background_bracket_n_c": nc_background,
                                    "retention": retention,
                                    "target_bracket_n_c": bracket_nc,
                                    "maximum_ambient_mass_msun": maximum,
                                    "mixture_at_maximum": mixed,
                                }
                            )
    rotating = []
    for row in inputs["rotating_models"]["rows"]:
        value = row["log_n_o"] - row["log_c_o"] - solar_log_nc
        rotating.append(
            {
                **row,
                "bracket_n_c_on_mom_solar_scale": value,
                "inside_published_marginal_nc_endpoints": nc_cases[0] <= value <= nc_cases[2],
            }
        )
    stellar_mass = mom["log_stellar_mass_msun"]
    mass_cases = [
        stellar_mass["median"] - stellar_mass["minus"],
        stellar_mass["median"],
        stellar_mass["median"] + stellar_mass["plus"],
    ]
    halo_budgets = [
        {
            "input_log_stellar_mass": mass,
            "stellar_baryon_efficiency": efficiency,
            "required_halo_mass_msun": required_halo_mass(10**mass, efficiency),
        }
        for mass in mass_cases
        for efficiency in (1.0, 0.1, 0.01)
    ]
    return {
        "schema_version": 1,
        "input_path": str(input_path.relative_to(ROOT))
        if input_path.is_relative_to(ROOT)
        else str(input_path),
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "status": "conditional_published_abundance_sensitivity_not_an_independent_measurement",
        "inference_guard": "No UV flux ratio is converted to elemental abundance; no likelihood, "
        "posterior model weights, or globally homogeneous gas assumption "
        "is fitted to the spectrum.",
        "solar_log_n_c": solar_log_nc,
        "published_bracket_n_c_cases": nc_cases,
        "published_n_c_number_cases": [bracket_to_number_ratio(x, solar_log_nc) for x in nc_cases],
        "carbon_to_nitrogen_conversion_cases": [
            {
                "target_bracket_n_c": x,
                "carbon_nuclei_fraction_processed": carbon_processing_fraction(
                    bracket_to_number_ratio(x, solar_log_nc), 10**solar_log_nc
                ),
            }
            for x in nc_cases
        ],
        "clocks": clocks,
        "pure_sms_ejecta": yield_ratios,
        "sms_mixing_sensitivity": mixing,
        "rotating_benchmarks": rotating,
        "conditional_halo_baryon_budgets": halo_budgets,
        "uncertainty": [
            "Published marginal endpoints are deterministic sensitivity inputs, not joint draws.",
            "Clock range propagates redshift endpoints only; cosmology is fixed to Planck18.",
            "Retention, ambient metallicity/composition, homogeneous mixing and hydrogen fraction "
            "are explicit unmeasured scenarios. No absolute emitting gas mass is measured.",
            "Published stellar yields have model systematics; four SMS values are not a grid "
            "from which arbitrary masses should be interpolated.",
        ],
        "primary_sources": [
            solar["source_url"],
            inputs["sms_yields"]["source_url"],
            inputs["sms_yields"]["original_yield_source_url"],
            wr["source_url"],
            inputs["vms_benchmark"]["source_url"],
            inputs["rotating_models"]["source_url"],
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_constraints(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "cosmic_age_myr": result["clocks"]["cosmic_age_myr"],
                "mixing_cases": len(result["sms_mixing_sensitivity"]),
            }
        )
    )


if __name__ == "__main__":
    main()
