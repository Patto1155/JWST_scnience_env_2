"""Algebraic and provenance guards for the conditional enrichment experiment."""

import json
import math

import pytest

from discovery.enrichment_constraints import (
    DEFAULT_INPUT,
    background_nuclei_per_msun,
    bracket_to_number_ratio,
    carbon_processing_fraction,
    cosmic_age_myr,
    maximum_ambient_mass,
    mixture_abundances,
    number_ratio,
    required_formation_redshift,
    required_halo_mass,
    run_constraints,
    time_budget_myr,
)


@pytest.fixture
def inputs():
    return json.loads(DEFAULT_INPUT.read_text())


def test_number_ratios_are_not_mass_ratios(inputs):
    row = inputs["sms_yields"]["rows"][0]
    assert number_ratio(row, "n", "c") == pytest.approx(17 / 9.91 * 12 / 14)
    assert number_ratio(row, "n", "c") != pytest.approx(17 / 9.91)


def test_published_solar_scale_matches_dex_definition(inputs):
    solar = inputs["solar_reference"]
    solar_log_nc = solar["log_n_o"] - solar["log_c_o"]
    assert solar_log_nc == pytest.approx(-0.6)
    assert bracket_to_number_ratio(0.9, solar_log_nc) == pytest.approx(10**0.3)


def test_mixing_root_closes_element_budget_and_retention_scaling(inputs):
    solar = inputs["solar_reference"]
    row = inputs["sms_yields"]["rows"][1]
    background = background_nuclei_per_msun(solar, -1.38, 0.0, 0.0)
    target = bracket_to_number_ratio(0.9, -0.6)
    mass = maximum_ambient_mass(row, background, target)
    assert mass is not None and mass > 0
    mixed = mixture_abundances(row, background, mass, solar)
    assert mixed["bracket_n_c"] == pytest.approx(0.9)
    assert maximum_ambient_mass(row, background, target, 0.1) == pytest.approx(mass * 0.1)
    assert mixture_abundances(row, background, mass * 0.1, solar, 0.1) == pytest.approx(mixed)
    # Adding twice as much background lowers N/C; no arbitrary ratio can result.
    assert mixture_abundances(row, background, mass * 2, solar)["bracket_n_c"] < 0.9


def test_low_sms_yield_cannot_reach_published_median(inputs):
    background = background_nuclei_per_msun(inputs["solar_reference"], -1.38, 0.0, 0.0)
    row = inputs["sms_yields"]["rows"][0]
    assert maximum_ambient_mass(row, background, 10**0.3) is None
    assert maximum_ambient_mass(row, background, 10**-0.33) is not None


def test_pristine_dilution_preserves_metal_metal_ratio(inputs):
    row = inputs["sms_yields"]["rows"][1]
    pristine = {"h": 0.75, "c": 0.0, "n": 0.0, "o": 0.0}
    small = mixture_abundances(row, pristine, 1000, inputs["solar_reference"])
    large = mixture_abundances(row, pristine, 10000, inputs["solar_reference"])
    assert small["bracket_n_c"] == pytest.approx(large["bracket_n_c"])
    assert small["log_c_o"] == pytest.approx(large["log_c_o"])
    assert small["oxygen_12_log_o_h"] > large["oxygen_12_log_o_h"]


def test_carbon_processing_conserves_c_plus_n_nuclei():
    initial = 10**-0.6
    target = 10**0.3
    fraction = carbon_processing_fraction(target, initial)
    assert 0 < fraction < 1
    assert (initial + fraction) / (1 - fraction) == pytest.approx(target)
    assert carbon_processing_fraction(initial, initial) == 0


def test_clocks_distinguish_formation_prior_from_cosmic_age():
    assert 280 < cosmic_age_myr(14.44) < 285
    assert 104 < time_budget_myr(14.44, 20) < 106
    assert time_budget_myr(14.44, 20) < 204 < cosmic_age_myr(14.44)
    onset = required_formation_redshift(14.44, 204)
    assert onset is not None and 34 < onset < 36
    assert time_budget_myr(14.44, onset) == pytest.approx(204, abs=1e-4)
    assert required_formation_redshift(14.44, 400) is None


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1])
def test_invalid_clock_inputs_are_rejected(bad):
    with pytest.raises(ValueError):
        cosmic_age_myr(bad)


def test_halo_budget_scales_with_mass_and_inverse_efficiency():
    minimum = required_halo_mass(10**8.1, 1.0)
    assert 7.9e8 < minimum < 8.1e8
    assert required_halo_mass(10**8.1, 0.1) == pytest.approx(minimum * 10)
    with pytest.raises(ValueError):
        required_halo_mass(1e8, 1.1)


def test_reversed_formation_and_mixing_inputs_rejected(inputs):
    with pytest.raises(ValueError):
        time_budget_myr(14.44, 10)
    row = inputs["sms_yields"]["rows"][1]
    background = background_nuclei_per_msun(inputs["solar_reference"], -1.38, 0.0, 0.0)
    with pytest.raises(ValueError):
        maximum_ambient_mass(row, background, 0.1)
    with pytest.raises(ValueError):
        maximum_ambient_mass(row, background, 2, retention=1.01)


def test_full_report_exposes_conditional_inputs_not_posteriors():
    result = run_constraints()
    assert "not_an_independent_measurement" in result["status"]
    assert len(result["input_sha256"]) == 64
    assert len(result["sms_mixing_sensitivity"]) == 432
    assert all(math.isfinite(row["bracket_n_c"]) for row in result["pure_sms_ejecta"])
    # Transferred rotating models overlap the broad interval but do not hit its median.
    assert all(
        row["inside_published_marginal_nc_endpoints"] for row in result["rotating_benchmarks"]
    )
    assert max(
        row["bracket_n_c_on_mom_solar_scale"] for row in result["rotating_benchmarks"]
    ) == pytest.approx(0.73)
