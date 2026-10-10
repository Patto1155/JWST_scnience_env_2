"""Independent quadrature/linear-algebra checks of conditional design contracts."""

import json

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.optimize import minimize_scalar

from tools.jwst.observation_design import (
    C_KM_S,
    FWHM_TO_SIGMA,
    ROOT,
    exposure_scale,
    gaussian_gram,
    read_nominal_curves,
    run,
    shape_discrimination,
)


@pytest.mark.parametrize("width", [0, 300, 1000])
def test_gram_independent_integral(width):
    wave = np.array([2.943918552, 2.947085296])
    resolving = np.array([3500.0, 3600.0])
    sigma = wave / FWHM_TO_SIGMA * np.hypot(1 / resolving, width / C_KM_S)
    low, high = wave.min() - 12 * sigma.max(), wave.max() + 12 * sigma.max()
    actual = gaussian_gram(wave, resolving, width)
    for i in range(2):
        for j in range(2):

            def product(x):
                left = np.exp(-0.5 * ((x - wave[i]) / sigma[i]) ** 2) / (
                    sigma[i] * np.sqrt(2 * np.pi)
                )
                right = np.exp(-0.5 * ((x - wave[j]) / sigma[j]) ** 2) / (
                    sigma[j] * np.sqrt(2 * np.pi)
                )
                return left * right

            independent = quad(product, low, high, epsabs=1e-9, points=wave.tolist())[0]
            assert actual[i, j] == pytest.approx(independent, rel=2e-10, abs=1e-10)


def test_profile_matches_independent_optimizer():
    gram = gaussian_gram(np.array([2.29, 2.295]), 1000, 300)
    truth, alt = np.array([0.6, 0.4]), np.array([0.2, 0.8])
    result = shape_discrimination(gram, truth, alt)
    minimize = minimize_scalar(
        lambda a: (truth - a * alt) @ gram @ (truth - a * alt), bounds=(0, 3), method="bounded"
    )
    expected = minimize.fun / (truth @ gram @ truth)
    assert result["shape_information_fraction"] == pytest.approx(expected, rel=1e-12)
    assert result["required_truth_matched_SNR"] ** 2 * expected == pytest.approx(9)
    assert shape_discrimination(gram, truth, truth)["required_truth_matched_SNR"] is None


def test_exposure_scaling_and_floor():
    assert exposure_scale(20, 5) == 16
    assert exposure_scale(20, 5, 30) == pytest.approx(28.8)
    assert exposure_scale(20, 5, 20) is None
    assert exposure_scale(20, 5, 10) is None
    with pytest.raises(ValueError):
        exposure_scale(0, 5)


@pytest.mark.parametrize(
    "wave,res,width",
    [([-1, 2], 1000, 0), ([2, 3], 0, 0), ([2, 3], 1000, -1), ([2, np.nan], 1000, 0)],
)
def test_bad_response_contract(wave, res, width):
    with pytest.raises(ValueError):
        gaussian_gram(np.array(wave), res, width)


def test_actual_primary_curves_units_and_nominal_range():
    curves = read_nominal_curves()
    assert set(curves) == {"g235m", "g235h", "g395m", "g395h"}
    for wavelength, resolution in curves.values():
        assert np.all(np.diff(wavelength) > 0)
        assert np.all(resolution > 500)
    data = run()
    assert len(data["response_cases"]) == 36
    assert all(
        case["mode"].startswith("g235") for case in data["response_cases"] if case["group"] == "NIV"
    )
    assert all(
        case["mode"].startswith("g235")
        for case in data["response_cases"]
        if case["group"] == "HeII_OIII"
    )
    assert data["exposure_scaling_example"]["absolute_seconds"] is None
    assert not next(row for row in data["additional_stage_targets"] if row["ion"] == "Hbeta")[
        "inside_nominal_NIRSpec_0p6_5p3"
    ]
    for group in ("NIV", "CIII"):
        family = [r for r in data["response_cases"] if r["group"] == group and r["mode"] == "g235h"]
        narrow = next(r for r in family if r["intrinsic_fwhm_km_s"] == 0)
        broad = next(r for r in family if r["intrinsic_fwhm_km_s"] == 1000)
        assert (
            broad["density_contrast"]["required_truth_matched_SNR"]
            > narrow["density_contrast"]["required_truth_matched_SNR"]
        )


def test_pinned_replay():
    saved = json.loads((ROOT / "research_output/mom_observation_design.json").read_text())
    def compare(actual, expected):
        if isinstance(expected, dict):
            assert actual.keys() == expected.keys()
            for key in expected:
                compare(actual[key], expected[key])
        elif isinstance(expected, list):
            assert len(actual) == len(expected)
            for left, right in zip(actual, expected, strict=True):
                compare(left, right)
        elif isinstance(expected, float):
            # Cross-platform eigensolvers differ at floating-point roundoff.
            # Preserve structure and metadata exactly, scientific values tightly.
            assert actual == pytest.approx(expected, rel=2e-10, abs=1e-12)
        else:
            assert actual == expected

    compare(run(), saved)
