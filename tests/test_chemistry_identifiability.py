"""Ensure covariance and non-identifiability limits survive downstream chemistry summaries."""

import copy
import json

import numpy as np
import pytest

from discovery.chemistry_identifiability import (
    DEFAULT_SPECTRUM_REPORT,
    flux_ratio_from_covariance,
    marginal_compatibility,
    required_effective_factor,
    run_identifiability,
    scale_fieller_set,
)


@pytest.fixture
def nominal():
    return json.loads(DEFAULT_SPECTRUM_REPORT.read_text())["fixed_published_redshift_scenarios"][0]


def test_flux_covariance_reproduces_stored_fieller_result(nominal):
    computed = flux_ratio_from_covariance(nominal, ("NIV", "NIII"), ("CIV", "CIII"))
    stored = nominal["nitrogen_lines_over_carbon_lines"]
    assert computed["value"] == pytest.approx(stored["value"])
    assert computed["conditional_gaussian_95_fieller_set"]["interval"] == pytest.approx(
        stored["fieller_normal_68_and_95_sets"]["1.95996398454"]["interval"]
    )
    covariance = np.asarray(nominal["line_covariance"])
    assert computed["numerator_variance"] == pytest.approx(
        covariance[0, 0] + covariance[3, 3] + 2 * covariance[0, 3]
    )


def test_missing_covariance_and_ambiguous_order_are_rejected(nominal):
    altered = copy.deepcopy(nominal)
    altered["line_covariance"] = [[1.0]]
    with pytest.raises(ValueError):
        flux_ratio_from_covariance(altered, ("NIV",), ("CIV",))
    altered = copy.deepcopy(nominal)
    altered["lines"] = dict(reversed(list(nominal["lines"].items())))
    with pytest.raises(ValueError):
        flux_ratio_from_covariance(altered, ("NIV",), ("CIV",))
    with pytest.raises(ValueError):
        flux_ratio_from_covariance(nominal, ("NIV", "typo"), ("CIV",))


def test_nonphysical_covariance_is_rejected(nominal):
    altered = copy.deepcopy(nominal)
    altered["line_covariance"][0][0] = -100.0
    with pytest.raises(ValueError):
        flux_ratio_from_covariance(altered, ("NIV",), ("CIV",))


@pytest.mark.parametrize("value", [0.0, -1.0, float("inf"), float("nan")])
def test_invalid_n_c_target_is_rejected(value):
    with pytest.raises(ValueError):
        scale_fieller_set({"type": "all_real"}, value)


def test_signed_and_disconnected_sets_are_preserved():
    bounded = {"type": "bounded", "interval": [-0.2, 1.5]}
    assert scale_fieller_set(bounded, 2)["interval"] == [-0.1, 0.75]
    disconnected = {"type": "two_unbounded_intervals", "excluded_open_interval": [-1.0, 3.0]}
    assert scale_fieller_set(disconnected, 2)["excluded_open_interval"] == [-0.5, 1.5]
    assert scale_fieller_set({"type": "all_real"}, 2) == {"type": "all_real"}
    assert scale_fieller_set({"type": "half_line", "boundary": 4, "direction": "above"}, 2) == {
        "type": "half_line",
        "boundary": 2,
        "direction": "above",
    }


def test_factor_and_abundance_cannot_be_identified_separately(nominal):
    ratio = flux_ratio_from_covariance(nominal, ("NIV", "NIII"), ("CIV", "CIII"))
    q1 = required_effective_factor(ratio, 2.0)["required_q_point"]
    q2 = required_effective_factor(ratio, 10.0)["required_q_point"]
    assert q1 * 2 == pytest.approx(q2 * 10)
    assert q1 == pytest.approx(q2 * 5)


def test_weak_ion_stage_ratio_keeps_negative_endpoint(nominal):
    ratio = flux_ratio_from_covariance(nominal, ("NIII",), ("CIII",))
    assert ratio["conditional_gaussian_95_fieller_set"]["interval"][0] < 0


def test_marginal_box_is_only_endpoint_compatibility():
    box = {"log_c_o": [-1.13, -0.52], "oxygen_12_log_o_h": [6.77, 7.98]}
    assert marginal_compatibility({"log_c_o": -0.9, "oxygen_12_log_o_h": 7.33}, box)
    assert not marginal_compatibility({"log_c_o": -0.3, "oxygen_12_log_o_h": 7.33}, box)
    assert not marginal_compatibility(None, box)


def test_compact_actual_spectrum_guard_and_joint_counts():
    report = run_identifiability(DEFAULT_SPECTRUM_REPORT)
    assert report["atomic_grid_available"] is False
    assert len(report["spectrum_scenario_summaries"]) == 31
    assert "WR" in report["unavailable_mechanism_predictions"]
    cue = next(x for x in report["targets"] if x["label"] == "Cue_median")
    assert cue["nominal_required_effective_factor"]["required_q_point"] == pytest.approx(0.5209564)
    rows = report["mixing_joint_marginal_checks"]["sms_summaries"]
    median_rows = [x for x in rows if x["target"] == "Cue_median"]
    assert [x["also_o_h_and_c_o_marginal_compatible_cases"] for x in median_rows] == [0, 24, 12, 12]
    strong_rows = [x for x in rows if x["target"] == "separate_ionic_temperature_case_upper"]
    assert [x["n_c_reachable_cases"] for x in strong_rows] == [0, 36, 36, 0]
    assert [x["also_o_h_and_c_o_marginal_compatible_cases"] for x in strong_rows] == [0, 0, 12, 0]
    helium = report["mixing_joint_marginal_checks"]["conditional_helium_examples"]
    assert helium["background_he_h_number"] == pytest.approx(1 / 12)
    example = next(
        x
        for x in helium["values"]
        if x["initial_mass_msun"] == 50000 and x["target_bracket_n_c"] == 0.9
    )
    assert example["mixed_he_h_number"] > helium["background_he_h_number"]
    assert example["mixed_he_h_number"] == pytest.approx(
        (example["ambient_mass_msun"] * 0.25 / 4 + 2700 / 4)
        / (example["ambient_mass_msun"] * 0.75 + 5060)
    )
