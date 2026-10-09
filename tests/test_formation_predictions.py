"""Conservation, inverse histories and selection controls, not empirical calibration."""

import json
import math

import numpy as np
import pytest
from scipy.integrate import quad
from test_atomic_enrichment import assert_replay_close

from discovery.enrichment_constraints import ROOT, required_halo_mass, time_budget_myr
from discovery.formation_predictions import (
    averaged_sfr_and_halfmass,
    closed_parcel_budget,
    envelope_integral_years,
    polluter_mass_budget,
    quoted_mass_as_surviving,
    required_active_sfr,
    required_duration_myr,
    run_predictions,
    selection_forward_counts,
)


@pytest.mark.parametrize(
    "duration,tau,duty,returned",
    [
        (105.0, None, 1.0, 0.4),
        (105.0, 10.0, 0.1, 0.4),
        (4.0, 30.0, 0.5, 0.7),
        (10.0, 100.0, 1.0, 0.0),
    ],
)
def test_sfr_history_closes_mass_using_independent_numerical_integral(
    duration, tau, duty, returned
):
    stellar_mass = 10**8.1
    predicted = required_active_sfr(stellar_mass, duration, duty, returned, tau)
    active = predicted["required_current_active_sfr_msun_per_year"]
    # Integrate the actual time envelope, independently of its closed-form helper.
    formed = (
        quad(
            lambda t: duty * active * (1.0 if tau is None else math.exp((t - duration) / tau)),
            0.0,
            duration,
        )[0]
        * 1e6
    )
    assert (1 - returned) * formed == pytest.approx(stellar_mass, rel=1e-12)
    recovered = required_duration_myr(stellar_mass, active, duty, returned, tau)
    assert recovered == pytest.approx(duration, rel=1e-10)


def test_constant_history_unit_conversion_and_duty_scaling():
    continuous = required_active_sfr(1e8, 100.0, 1.0, 0.5)
    intermittent = required_active_sfr(1e8, 100.0, 0.1, 0.5)
    assert continuous["required_current_active_sfr_msun_per_year"] == 2.0
    assert intermittent["required_current_active_sfr_msun_per_year"] == 20.0
    assert (
        continuous["history_mean_sfr_msun_per_year"]
        == intermittent["history_mean_sfr_msun_per_year"]
        == 2.0
    )
    assert envelope_integral_years(100.0, 1e12) == pytest.approx(100e6, rel=1e-10)


def test_rising_history_infinite_time_ceiling_is_not_a_finite_onset():
    assert required_duration_myr(1e8, 10.0, 1.0, 0.0, 10.0) is None  # Exact asymptote.
    assert required_duration_myr(1e8, 5.0, 1.0, 0.0, 10.0) is None
    finite = required_duration_myr(1e8, 20.0, 1.0, 0.0, 10.0)
    assert finite == pytest.approx(10 * math.log(2))
    # Earlier formation cannot repair a fixed-present-SFR exponential ceiling.
    assert required_duration_myr(10**8.1, 10.0, 1.0, 0.4, 10.0) is None


def test_both_quoted_mass_conventions_are_explicit_and_conserved():
    assert quoted_mass_as_surviving(1e8, 0.4, "current_surviving") == 1e8
    assert quoted_mass_as_surviving(1e8, 0.4, "cumulative_formed") == 6e7
    history = required_active_sfr(
        quoted_mass_as_surviving(1e8, 0.4, "cumulative_formed"), 100.0, 1.0, 0.4
    )
    assert history["formed_stellar_mass_msun"] == 1e8
    assert history["required_current_active_sfr_msun_per_year"] == 1.0
    with pytest.raises(ValueError):
        quoted_mass_as_surviving(1e8, 0.4, "unspecified")


def test_trailing_means_and_halfmass_match_independent_history_integrals():
    prediction = averaged_sfr_and_halfmass(10.0, 105.0, 0.5, 5.0)
    for window in (5, 50):
        integral = quad(lambda lookback: 0.5 * 10 * math.exp(-lookback / 5), 0.0, window)[0]
        assert prediction[f"sfr_last_{window}_myr_msun_per_year"] == pytest.approx(
            integral / window
        )
    total = quad(lambda lookback: math.exp(-lookback / 5), 0.0, 105.0)[0]
    half = quad(lambda lookback: math.exp(-lookback / 5), 0.0, prediction["halfmass_lookback_myr"])[
        0
    ]
    assert half == pytest.approx(total / 2, rel=1e-12)
    recent = averaged_sfr_and_halfmass(10.0, 4.0, 1.0, None)
    assert recent["sfr_last_5_myr_msun_per_year"] == 8.0
    assert recent["sfr_last_50_myr_msun_per_year"] == 0.8
    assert recent["halfmass_lookback_myr"] == 2.0
    assert averaged_sfr_and_halfmass(10.0, 100.0, 1.0, 1e12)[
        "halfmass_lookback_myr"
    ] == pytest.approx(50.0)


def test_longer_available_history_lowers_required_constant_sfr():
    young = required_active_sfr(10**8.1, 4.0, 1.0, 0.4)
    z20 = required_active_sfr(10**8.1, time_budget_myr(14.44, 20.0), 1.0, 0.4)
    z30 = required_active_sfr(10**8.1, time_budget_myr(14.44, 30.0), 1.0, 0.4)
    assert (
        young["required_current_active_sfr_msun_per_year"]
        > z20["required_current_active_sfr_msun_per_year"]
        > z30["required_current_active_sfr_msun_per_year"]
    )
    assert young["required_current_active_sfr_msun_per_year"] == pytest.approx(52.45522549)


def test_recycled_mass_is_not_counted_twice_in_closed_gas_budget():
    no_return = closed_parcel_budget(1e8, returned=0.0)
    large_return = closed_parcel_budget(1e8, returned=0.7)
    assert no_return["minimum_initial_gas_mass_msun"] == 1e8
    assert large_return["minimum_initial_gas_mass_msun"] == 1e8
    assert no_return["minimum_halo_mass_msun_under_closed_allowance"] == pytest.approx(
        required_halo_mass(1e8, 1.0)
    )
    assert (
        large_return["cumulative_formed_stellar_mass_msun"]
        > no_return["cumulative_formed_stellar_mass_msun"]
    )


def test_closed_parcel_conserves_surviving_returned_gas_and_permanent_wind_mass():
    actual = closed_parcel_budget(
        1e8,
        remaining_gas_msun=2e8,
        returned=0.5,
        outflow_per_formed_mass=3.0,
        initial_available_baryon_fraction=0.3,
    )
    assert actual["cumulative_formed_stellar_mass_msun"] == 2e8
    assert actual["permanently_lost_wind_mass_msun"] == 6e8
    assert actual["minimum_initial_gas_mass_msun"] == 9e8
    assert actual["minimum_halo_mass_msun_under_closed_allowance"] == pytest.approx(
        9e8 / actual["cosmic_baryon_fraction_Planck18"] / 0.3
    )


@pytest.mark.parametrize(
    "duty,returned,tau",
    [
        (0.0, 0.0, None),
        (1.1, 0.0, None),
        (1.0, 1.0, None),
        (1.0, -0.1, None),
        (1.0, 0.0, 0.0),
        (1.0, 0.0, float("nan")),
    ],
)
def test_invalid_physical_history_inputs_are_rejected(duty, returned, tau):
    with pytest.raises(ValueError):
        required_active_sfr(1e8, 100.0, duty, returned, tau)
    with pytest.raises(ValueError):
        required_duration_myr(1e8, 1.0, duty, returned, tau)


def test_selection_forward_keeps_non_detection_and_bin_scatter():
    parent, phase = np.array([10.0, 20.0]), np.array([0.1, 0.5])
    response = np.array([[0.3, 0.1], [0.2, 0.4]])
    selected = selection_forward_counts(parent, phase, response)
    assert selected == pytest.approx([1.3, 4.2])
    assert selected.sum() == pytest.approx(5.5)
    assert selected.sum() < (parent * phase).sum()
    assert selection_forward_counts(parent, phase, np.eye(2)) == pytest.approx(parent * phase)
    assert selection_forward_counts(parent, np.zeros(2), response) == pytest.approx([0.0, 0.0])


@pytest.mark.parametrize(
    "parent,phase,response",
    [
        ([-1.0], [0.5], [[0.5]]),
        ([1.0], [1.1], [[0.5]]),
        ([1.0], [0.5], [[0.7], [0.7]]),
        ([1.0], [0.5], [[-0.1]]),
        ([1.0], [0.5], [[float("nan")]]),
        ([1.0, 2.0], [0.5], [[0.5]]),
    ],
)
def test_uncalibrated_or_invalid_population_operator_inputs_cannot_be_certified(
    parent, phase, response
):
    with pytest.raises(ValueError):
        selection_forward_counts(np.array(parent), np.array(phase), np.array(response))


def test_polluter_budget_scales_with_gas_and_retained_yield_without_claiming_events():
    one = polluter_mass_budget(1e6, 1e5, 5e4, 1e8, 0.5)
    tenth_retention = polluter_mass_budget(1e6, 1e4, 5e4, 1e8, 0.5)
    assert one["required_event_equivalents"] == 10.0
    assert one["initial_polluter_mass_fraction_of_formed_stars_event_equivalent"] == 0.0025
    assert tenth_retention["required_event_equivalents"] == 100.0
    assert (
        tenth_retention["initial_polluter_mass_fraction_of_formed_stars_event_equivalent"] == 0.025
    )


def test_actual_report_preserves_model_dependence_and_no_cosmology_ranking():
    report = run_predictions()
    assert len(report["history_predictions"]) == 720
    assert len(report["closed_parcel_baryon_budgets"]) == 216
    assert len(report["inverse_history_tests"]) == 80
    assert (
        report["model_dependent_observational_input"]["quoted_log_stellar_mass_msun"]["median"]
        == 8.1
    )
    assert report["model_dependent_observational_input"]["endpoints_status"] == (
        "marginal_sensitivity_not_joint_posterior"
    )
    assert report["rejected_astrophysical_mechanisms"] == []
    assert report["cosmology_probabilities"] is None
    assert report["model_dependent_observational_input"]["mass_convention_identified"] is False
    assert (
        report["model_dependent_observational_input"]["alternative_histories_refit_to_stellar_SED"]
        is False
    )
    assert (
        report["conditional_sms_mass_budgets"][
            "ambient_only_ratio_inside_reference_conditional_95_set"
        ]
        is True
    )
    assert (
        report["conditional_sms_mass_budgets"][
            "positive_minimum_polluter_mass_fraction_established"
        ]
        is False
    )
    assert report["selection_forward_contract"]["calibrated_population_inputs_available"] is False
    assert (
        report["selection_forward_contract"]["time_duty_equals_observable_phase_probability"]
        is False
    )
    assert report["selection_forward_contract"]["synthetic_dimensionless_operator_control"][
        "selected_unit_weights"
    ] == pytest.approx([0.08, 0.22])
    assert all(len(item["sha256"]) == 64 for item in report["input_receipts"].values())
    saved = json.loads((ROOT / "research_output/formation_predictions.json").read_text())
    assert_replay_close(report, saved)
