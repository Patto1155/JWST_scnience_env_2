"""Synthetic arithmetic controls; these fixtures are not physical model results."""

from copy import deepcopy

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.optimize import minimize_scalar

from tools.jwst.cloudy_observation_contrasts import (
    EXPECTED_LINES,
    GROUPS,
    NITROGEN_KEY,
    compare_family,
    screen,
    stage_ranges,
    validate_models,
)
from tools.jwst.observation_design import gaussian_gram


def synthetic_models():
    rows = []
    for environment in range(10):
        for nitrogen in (0, 1):
            values = np.ones(29)
            values[0:2] *= 1 + nitrogen
            values[7:12] *= 1 + 2 * nitrogen
            values[22:24] *= 1 + nitrogen
            rows.append(
                {
                    "id": f"synthetic_{environment}_{nitrogen}",
                    "parameters": {"synthetic_environment": environment, NITROGEN_KEY: nitrogen},
                    "intrinsic_line_values": values.tolist(),
                    "emergent_line_values": values.tolist(),
                    "zones": 1,
                    "convergence_summary": "Cloudy ends: SYNTHETIC UNIT TEST ONLY",
                    "actual_gas_abundances": {
                        "NITR": {"actual_printed_log_XH": -4.6 + nitrogen},
                        "CARB": {"actual_printed_log_XH": -4.0},
                        "OXYG": {"actual_printed_log_XH": -3.63},
                    },
                }
            )
    return rows


def synthetic_pilot():
    return {
        "cloudy_release": "C23.01",
        "ordinary_reference_log_NC": -0.60,
        "reference_log_CO": -0.37,
        "line_contract_version": 2,
        "complete_thermal_solution_per_composition": True,
        "intrinsic_line_unit": "erg s^-1 cm^-2; Cloudy intensity geometry",
        "line_wavelength_medium": [
            "air" if wave > 2000 else "vacuum" for _, wave in EXPECTED_LINES
        ],
        "lines": EXPECTED_LINES,
        "models": synthetic_models(),
    }


def test_incomplete_missing_wrong_contract_rejected():
    complete = synthetic_pilot()
    validate_models(complete)
    wrong = deepcopy(complete)
    wrong["models"] = wrong["models"][:-1]
    with pytest.raises(ValueError):
        validate_models(wrong)
    wrong = deepcopy(complete)
    wrong["models"][0]["intrinsic_line_values"] = wrong["models"][0]["intrinsic_line_values"][:-1]
    with pytest.raises(ValueError):
        validate_models(wrong)
    wrong = deepcopy(complete)
    wrong["line_wavelength_medium"] = ["vacuum"] * 29
    with pytest.raises(ValueError):
        validate_models(wrong)
    wrong = deepcopy(complete)
    wrong["models"][0]["actual_gas_abundances"]["NITR"]["actual_printed_log_XH"] = 0
    with pytest.raises(ValueError):
        validate_models(wrong)


def test_shape_contrast_matches_independent_spectrum_integral():
    rows = synthetic_models()
    indices = GROUPS["NIV"] + GROUPS["CIII"]
    waves = np.array([EXPECTED_LINES[i][1] for i in indices]) * 15.44 / 1e4
    gram = gaussian_gram(waves, 2700, 300)
    result = compare_family(rows, indices, gram, [0], "intrinsic_line_values")
    assert result["cross_environment_comparisons"] == 100
    assert len(result["matched_environment_pairs"]) == 10
    truth = np.array([2, 2, 1, 1]) / 6
    alt = np.ones(4) / 4
    sigma = waves * np.hypot(1 / 2700, 300 / 299792.458) / np.sqrt(8 * np.log(2))

    def shape(x, weights):
        return np.sum(
            weights * np.exp(-0.5 * ((x - waves) / sigma) ** 2) / (sigma * np.sqrt(2 * np.pi))
        )

    intervals = [(w - 12 * s, w + 12 * s) for w, s in zip(waves, sigma)]

    def integral(function):
        # Integrate one common encompassing interval with points at line centers.
        return quad(
            function,
            min(a for a, _ in intervals),
            max(b for _, b in intervals),
            points=waves.tolist(),
            epsabs=1e-9,
            limit=300,
        )[0]

    opt = minimize_scalar(
        lambda amp: integral(lambda x: (shape(x, truth) - amp * shape(x, alt)) ** 2),
        bounds=(0, 3),
        method="bounded",
    )
    information = opt.fun / integral(lambda x: shape(x, truth) ** 2)
    expected = np.sqrt(9 / information)
    assert result["closest_cross_environment"]["required_truth_matched_SNR"] == pytest.approx(
        expected, rel=1e-10
    )
    assert result["closest_cross_environment"]["profiled_alternative_amplitude"] == pytest.approx(
        opt.x, rel=1e-8
    )


def test_free_amplitude_removes_pure_scale_information():
    rows = synthetic_models()
    for row in rows:
        row["intrinsic_line_values"] = (
            np.ones(29) * (1 + row["parameters"][NITROGEN_KEY])
        ).tolist()
    indices = GROUPS["NIV"] + GROUPS["CIII"]
    waves = np.array([EXPECTED_LINES[i][1] for i in indices]) * 15.44 / 1e4
    result = compare_family(rows, indices, gaussian_gram(waves, 2700), [0], "intrinsic_line_values")
    assert result["closest_cross_environment"]["required_truth_matched_SNR"] is None
    assert result["closest_cross_environment"]["shape_information_fraction"] == pytest.approx(
        0, abs=1e-14
    )


def test_screen_matches_declared_upstream_power_law():
    waves = np.array([1500.0, 1900.0])
    expected = np.exp(-0.4 * np.log(10) * 0.5 * (waves / 1500) ** -1.2)
    assert np.allclose(screen(np.ones(2), waves, 0.5), expected, rtol=1e-14)
    with pytest.raises(ValueError):
        screen(np.ones(2), waves, -1)


def test_stage_convention_and_range_not_probabilities():
    output = stage_ranges(synthetic_models(), [0], "intrinsic_line_values")
    assert output[0]["ratio_to_CIII"]["0"] == {"minimum": 1.0, "maximum": 1.0}
    assert output[0]["ratio_to_CIII"]["1"] == {"minimum": 2.0, "maximum": 2.0}
    assert output[0]["finite_range_overlap"] is None
    assert output[1]["wavelength_medium"].startswith("Cloudy air")
    assert output[1]["finite_range_overlap"] == [2.5, 2.5]


def test_custom_CO_contract_not_unmodified_solar():
    wrong = deepcopy(synthetic_pilot())
    wrong["reference_log_CO"] = -0.26
    with pytest.raises(ValueError):
        validate_models(wrong)
    wrong = deepcopy(synthetic_pilot())
    wrong["models"][0]["actual_gas_abundances"]["OXYG"]["actual_printed_log_XH"] = -3.5
    with pytest.raises(ValueError):
        validate_models(wrong)


def test_actual_frozen_complete_forecast_contract():
    """Audit actual saved predictions; independent worker owns full numeric oracle."""
    import hashlib
    import json

    from tools.jwst.observation_design import ROOT

    model_path = ROOT / "research_output/mom_cloudy_pilot20_rate_v3.json"
    forecast_path = ROOT / "research_output/mom_cloudy_observation_contrasts.json"
    assert hashlib.sha256(model_path.read_bytes()).hexdigest() == (
        "7ef48626ddfb7c882d9725b17939c3a7752151de734e3ab4c46472b940127759"
    )
    pilot = json.loads(model_path.read_text())
    validate_models(pilot)
    output = json.loads(forecast_path.read_text())
    assert output["input_sha256"] == hashlib.sha256(model_path.read_bytes()).hexdigest()
    assert output["validated_merged_input_revision"] == ("6b44032b82e550ed0f740a56830deed296b5c4e9")
    assert len(output["cases"]) == 48
    assert output["composition_reference"]["unmodified_solar_pattern"] is False
    assert output["absolute_exposure_seconds"] is None
    assert output["matched_native_observations_used"] is False
    assert output["alternative_response_contracts_pooled"] is False
    identifiers = {model["id"] for model in pilot["models"]}
    for case in output["cases"]:
        assert case["cross_environment_comparisons"] == 100
        assert case["existing_attenuation_pairs_per_comparison"] == 9
        assert len(case["matched_environment_pairs"]) == 10
        assert case["finite_counts_are_probabilities"] is False
        for record in case["matched_environment_pairs"] + [case["closest_cross_environment"]]:
            assert record["enhanced_truth_model_id"] in identifiers
            assert record["ordinary_alternative_model_id"] in identifiers
            assert record["required_truth_matched_SNR"] ** 2 * record[
                "shape_information_fraction"
            ] == pytest.approx(9, rel=1e-12)
    def compare_ranges(saved, replayed):
        # Floating arithmetic can differ by one ULP across supported NumPy builds.
        # Keep labels, structure and missing-value contracts exact.
        if isinstance(saved, dict):
            assert saved.keys() == replayed.keys()
            for key in saved:
                compare_ranges(saved[key], replayed[key])
        elif isinstance(saved, list):
            assert len(saved) == len(replayed)
            for left, right in zip(saved, replayed):
                compare_ranges(left, right)
        elif isinstance(saved, float):
            assert replayed == pytest.approx(saved, rel=1e-12, abs=1e-15)
        else:
            assert saved == replayed

    for response in ("intrinsic_line_values", "emergent_line_values"):
        compare_ranges(
            output["extra_stage_ranges"][response],
            stage_ranges(pilot["models"], [0, 0.5, 1], response),
        )
