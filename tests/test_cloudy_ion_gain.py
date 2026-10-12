"""Independent convex-solver checks and labeled synthetic arithmetic controls."""

import json

import numpy as np
import pytest
from scipy.optimize import nnls

from tools.jwst.cloudy_ion_gain import gain_discrimination
from tools.jwst.cloudy_observation_contrasts import (
    EXPECTED_LINES,
    GROUPS,
    compare_family,
)
from tools.jwst.observation_design import ROOT, gaussian_gram, read_nominal_curves


@pytest.mark.parametrize("half_width", [0, 0.1, 0.5, None])
def test_two_ion_cone_against_independent_whitened_nnls(half_width):
    rng = np.random.default_rng(385)
    for _ in range(12):
        a = rng.normal(size=(7, 7))
        gram = a.T @ a + np.eye(7)
        truth, alternative = rng.random(7), rng.random(7)
        truth /= truth.sum()
        alternative /= alternative.sum()
        result = gain_discrimination(gram, truth, alternative, 5, half_width)
        columns = np.zeros((7, 2))
        columns[:5, 0] = alternative[:5]
        columns[5:, 1] = alternative[5:]
        rays = (
            np.eye(2)
            if half_width is None
            else np.array([[1 - half_width, 1 + half_width], [1.0, 1.0]])
        )
        whiten = np.linalg.cholesky(gram).T
        _, residual_norm = nnls(whiten @ columns @ rays, whiten @ truth)
        expected = residual_norm**2 / (truth @ gram @ truth)
        assert result["shape_information_fraction"] == pytest.approx(expected, rel=2e-12, abs=2e-15)


def test_free_ion_amplitudes_remove_only_scale_difference():
    truth = np.array([3.0, 6.0, 1.0, 2.0]) / 12
    alternative = np.array([1.0, 2.0, 1.0, 2.0]) / 6
    fixed = gain_discrimination(np.eye(4), truth, alternative, 2, 0)
    free = gain_discrimination(np.eye(4), truth, alternative, 2, None)
    assert fixed["shape_information_fraction"] > 0.1
    assert free["shape_information_fraction"] < 1e-28
    assert free["required_truth_matched_SNR"] is None
    assert free["separation_status"] == "numerically_nonidentifiable"
    assert free["profiled_NIII_relative_gain"] == pytest.approx(3)
    changed = truth.copy()
    changed[:2] = changed[:2][::-1]
    assert (
        gain_discrimination(np.eye(4), changed, alternative, 2, None)["shape_information_fraction"]
        > 0.1
    )


def test_no_gain_case_reproduces_reviewed_finite_forecast():
    pilot = json.loads((ROOT / "research_output/mom_cloudy_pilot20_rate_v3.json").read_text())
    saved = json.loads((ROOT / "research_output/mom_cloudy_ion_gain.json").read_text())
    indices = GROUPS["NIII"] + GROUPS["CIII"]
    waves = np.array([EXPECTED_LINES[i][1] for i in indices]) * 15.44 / 1e4
    w, r = read_nominal_curves()["g235h"]
    gram = gaussian_gram(waves, np.interp(waves, w, r))
    for response in ("intrinsic_line_values", "emergent_line_values"):
        original = compare_family(pilot["models"], indices, gram, [0, 0.5, 1], response)
        cases = [c for c in saved["cases"] if c["response"] == response]
        no_gain = cases[0]["closest_cross_environment"]
        baseline = original["closest_cross_environment"]
        assert no_gain["required_truth_matched_SNR"] == pytest.approx(
            baseline["required_truth_matched_SNR"], rel=1e-12
        )
        assert no_gain["enhanced_truth_model_id"] == baseline["enhanced_truth_model_id"]
        assert no_gain["ordinary_alternative_model_id"] == baseline["ordinary_alternative_model_id"]
        fractions = [c["closest_cross_environment"]["shape_information_fraction"] for c in cases]
        assert all(x >= y for x, y in zip(fractions, fractions[1:]))
        assert cases[-1]["closest_cross_environment"]["required_truth_matched_SNR"] > 10000


@pytest.mark.parametrize("half_width", [-1, 1, float("nan")])
def test_invalid_bounds_rejected(half_width):
    with pytest.raises(ValueError):
        gain_discrimination(np.eye(2), np.ones(2) / 2, np.ones(2) / 2, 1, half_width)
