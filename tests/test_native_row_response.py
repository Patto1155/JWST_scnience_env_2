"""Independent row-bin, optical-profile and signed image response controls."""

import json
from pathlib import Path

import numpy as np
import pytest
from scipy.special import erf, ndtr

from tools.jwst.native_measurement_validation import (
    apply_signed_response,
    response,
    signed_response_coupling,
)
from tools.jwst.native_reduction import extract_columns, signed_profiles
from tools.jwst.native_row_response import (
    complete_row_wavelength,
    conditional_coverage_from_bias,
    row_source_design,
    signed_pixel_response,
)

ROOT = Path(__file__).resolve().parents[1]


def synthetic_rows(shear: float) -> list[dict]:
    rows, columns = 28, 128
    base = np.linspace(2.1, 3.3, columns)
    wave = base[None] + (np.arange(rows)[:, None] - 14) * shear
    data = []
    for trace in (8.0, 14.0, 20.0):
        data.append(
            {
                "wave": wave,
                "trace_seed": np.full(columns, trace),
                "sigma_refined": 0.8,
                "science": np.zeros_like(wave),
                "variance": np.ones_like(wave),
                "good": np.ones_like(wave, dtype=bool),
                "point_pathloss": np.full_like(wave, 0.8),
                "group": "03",
            }
        )
    return data


def physical_components():
    return [([1486.496], [1]), ([1549.0], [1]), ([1654.0], [1]), ([1750.0], [1]), ([1908.0], [1])]


def test_full_grid_row_completion_retains_missing_position_and_linear_spacing():
    wave = np.linspace(2.1, 3.3, 60)
    altered = wave.copy()
    altered[:3] = np.nan
    altered[-4:] = np.nan
    altered[15] = np.nan
    assert np.allclose(complete_row_wavelength(altered), wave, atol=1e-14)
    with pytest.raises(ValueError, match="insufficient"):
        complete_row_wavelength(np.array([np.nan, 2.0, 3.0]))
    with pytest.raises(ValueError, match="strictly increasing"):
        complete_row_wavelength(np.array([3.0, 2.0, 1.0]))


def test_no_row_shear_is_exact_scalar_signed_response_limit():
    data = synthetic_rows(0)
    selected = np.arange(128)
    rw, r = np.array([0.5, 6.0]), np.array([200.0, 200.0])
    components = physical_components()
    _, operators, _ = extract_columns(data, signed_profiles(data, 0.8, 0))
    full = row_source_design(data, rw, r, components, 0.8, 0)
    actual = signed_pixel_response(data, full, operators, selected)
    q = signed_response_coupling(data, operators, selected, 0.8, 0)
    scalar = apply_signed_response(response(data, selected, rw, r, components), q)
    assert np.allclose(actual, scalar, atol=1e-14)


def test_sheared_single_line_matches_independent_erf_pixel_image():
    data = synthetic_rows(0.003)
    selected = np.arange(128)
    rw, r = np.array([0.5, 6.0]), np.array([200.0, 200.0])
    components = physical_components()
    _, operators, _ = extract_columns(data, signed_profiles(data, 0.8, 0))
    actual = signed_pixel_response(
        data, row_source_design(data, rw, r, components, 0.8, 0), operators, selected
    )
    truth = np.array([0, 0, 20, 0, 0, 0, 0.0])
    predicted = actual @ truth
    center = 1486.496e-4 * 15.44
    spectral_sigma = center / 200 / 2.354820045
    positive = []
    yy = np.arange(28)[:, None]
    for d in data:
        trace = d["trace_seed"][None]
        profile = 0.5 * (
            erf((yy + 0.5 - trace) / (0.8 * np.sqrt(2)))
            - erf((yy - 0.5 - trace) / (0.8 * np.sqrt(2)))
        )
        wave = d["wave"]
        mid = (wave[:, 1:] + wave[:, :-1]) / 2
        edges = np.column_stack([2 * wave[:, 0] - mid[:, 0], mid, 2 * wave[:, -1] - mid[:, -1]])
        density = np.diff(ndtr((edges - center) / spectral_sigma), axis=1) / np.diff(edges, axis=1)
        positive.append(20 * density / (2.99792458e5 / wave**2) * profile * 0.8)
    pixel = []
    for i in range(3):
        pixel.append(positive[i] - (positive[(i + 1) % 3] + positive[(i + 2) % 3]) / 2)
    independent = np.sum(np.array(pixel) * operators, axis=1).T.reshape(-1)
    assert np.allclose(predicted, independent, atol=1e-14)
    q = signed_response_coupling(data, operators, selected, 0.8, 0)
    scalar = apply_signed_response(response(data, selected, rw, r, components), q)
    assert np.max(np.abs(scalar @ truth - independent)) > 1e-5
    # Corresponding row model recovers exact injected total without clipping.
    assert np.linalg.lstsq(actual, independent, rcond=None)[0][2] == pytest.approx(20, abs=1e-10)


def test_gaussian_coverage_bias_counterexample_and_committed_four_family_result():
    coverage = conditional_coverage_from_bias(np.array([0, 1, 10.0]), np.ones(3))
    assert coverage[0] == pytest.approx(0.95, abs=1e-12)
    assert 0.8 < coverage[1] < 0.85
    assert coverage[2] < 1e-12
    result = json.loads((ROOT / "research_output/mom_native_row_response.json").read_text())
    assert len(result["row_resolved_fits"]) == 4
    assert len(result["row_source_injection_controls"]) == 4
    assert len(result["held_out_rate_group_predictions"]) == 3
    assert result["new_download_bytes"] == 0
    assert result["native_source_specific_LSF_empirically_calibrated"] is False
    assert result["alternative_likelihoods_pooled"] is False
    for fit, control in zip(result["row_resolved_fits"], result["row_source_injection_controls"]):
        assert fit["scalar_flux_replay_max_difference"] < 1e-9
        assert np.allclose(
            control["row_recovered_fluxes"], control["injected_truth_fluxes"], atol=1e-10
        )
        assert max(abs(np.array(control["scalar_bias_over_conditional_sigma"]))) < 0.025
        assert control["image_vs_row_design_maximum_difference"] < 1e-14
        assert np.linalg.eigvalsh(fit["fit"]["flux_covariance"]).min() > 0
