"""Independent small covariance oracles and versioned scientific receipt guards."""

import json

import numpy as np
import pytest

from tools.jwst.native_rate_noise import donor_covariance, load_rate_noise_replay
from tools.jwst.native_reduction import ROOT


def test_target_only_variance_requires_donor_noise_and_gain_transport():
    raw = np.array([1.0, 4.0, 9.0])[:, None, None]
    gains = np.array([2.0, 3.0, 4.0])[:, None, None]
    operators = np.ones((3, 1, 1))
    flat = np.array([0.1, 0.2, 0.3])[:, None, None]
    # Explicit independent Jacobian: signed detector DN/s to extracted uJy.
    jacobian = np.array([[2.0, -1.0, -1.0], [-1.5, 3.0, -1.5], [-2.0, -2.0, 4.0]])
    expected = jacobian @ np.diag([1.0, 4.0, 9.0]) @ jacobian.T + np.diag([0.1, 0.2, 0.3])
    actual = donor_covariance(raw, gains, operators, flat)[0]
    np.testing.assert_allclose(actual, expected, rtol=1e-14)
    assert actual[0, 0] == pytest.approx(17.1)
    assert actual[0, 0] > gains[0, 0, 0] ** 2 * raw[0, 0, 0] + flat[0, 0, 0]
    assert np.linalg.eigvalsh(actual).min() > 0


def test_spatial_correlations_have_explicit_raw_pixel_oracle():
    raw = np.array([[1.0, 4.0], [9.0, 16.0], [25.0, 36.0]])[:, :, None]
    gains = np.ones_like(raw)
    operators = np.array([[1.0, 2.0], [3.0, -1.0], [0.5, 2.0]])[:, :, None]
    flat = np.zeros_like(raw)
    spatial = np.array([[1.0, 0.2], [0.2, 1.0]])
    # Build all six raw-pixel random variables before any signed subtraction.
    mix = np.array([[1.0, -0.5, -0.5], [-0.5, 1.0, -0.5], [-0.5, -0.5, 1.0]])
    jacobian = np.concatenate([mix[:, k, None] * operators[:, :, 0] for k in range(3)], axis=1)
    covariance = np.zeros((6, 6))
    for k in range(3):
        sd = np.sqrt(raw[k, :, 0])
        covariance[k * 2 : k * 2 + 2, k * 2 : k * 2 + 2] = sd[:, None] * spatial * sd[None, :]
    np.testing.assert_allclose(
        donor_covariance(raw, gains, operators, flat, spatial)[0],
        jacobian @ covariance @ jacobian.T,
    )


def test_actual_nine_rate_receipt_rejects_historical_demix_contract():
    report = json.loads((ROOT / "research_output/mom_native_rate_noise.json").read_text())
    assert len(report["RATE_CAL_checks"]) == 9
    assert report["primary_source_stub"] == {
        "data": [8.0],
        "dq": [4],
        "err": [3.0],
        "var_poisson": [5.0],
        "var_rnoise": [4.0],
    }
    assert max(x["total_error_max_relative_difference"] for x in report["RATE_CAL_checks"]) < 2e-6
    assert max(x["equal_half_SCI_closure_max_CAL_sigma"] for x in report["groups"]) < 1e-4
    assert (
        report["empirical_noise_after_donor_normalization"]["pooled_scale_squared"]
        < report["historical_empirical_scale_squared"]
    )


def test_new_covariance_api_retains_identical_selection_and_separate_contracts():
    path = ROOT / "research_output/mom_native_rate_noise.json"
    formal = load_rate_noise_replay(path, empirical=False)
    empirical = load_rate_noise_replay(path)
    np.testing.assert_array_equal(formal["selected"], empirical["selected"])
    assert formal["noise_scale_squared"] == 1
    assert empirical["noise_scale_squared"] > 1
    assert formal["noise_contract_version"] == 3
    for blocks in (formal["covariance_blocks"], empirical["covariance_blocks"]):
        assert np.linalg.eigvalsh(blocks[formal["selected"]]).min() > 0


def test_signal_gain_ratios_follow_same_signed_operator_as_noise():
    from tools.jwst.native_rate_noise import rate_signed_response

    data = [{"group": "03"} for _ in range(3)]
    positive = np.array([2.0, 3.0, 5.0]).reshape(3, 1, 1, 1)
    gain = np.array([2.0, 3.0, 4.0]).reshape(3, 1, 1)
    actual = rate_signed_response(data, positive, gain, np.ones((3, 1, 1)), np.array([0]))[:, 0]
    # Source in target-calibrated units is first mapped back to each RATE DN/s.
    raw = np.array([1.0, 1.0, 1.25])
    expected = np.array(
        [
            2.0 * (raw[0] - (raw[1] + raw[2]) / 2),
            3.0 * (raw[1] - (raw[0] + raw[2]) / 2),
            4.0 * (raw[2] - (raw[0] + raw[1]) / 2),
        ]
    )
    np.testing.assert_allclose(actual, expected)
