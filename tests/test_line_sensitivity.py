"""Independent known-signal and uncertainty controls for the UV-line experiment."""

import numpy as np
import pytest

from tools.jwst.line_sensitivity import (
    C_KMS,
    Extraction,
    LINE_COMPONENTS,
    bin_edges,
    covariance_matrix,
    extract_2d,
    fieller_set,
    fit_lines,
    line_matrix,
)


def test_bin_integrated_line_flux_is_conserved():
    wave = np.linspace(2.15, 3.2, 500)
    edges = bin_edges(wave)
    matrix = line_matrix(wave, np.array([0.5, 6]), np.array([100, 100]))
    assert np.allclose(np.diff(edges) @ matrix, 1, atol=1e-10)
    with pytest.raises(ValueError, match="strictly increasing"):
        bin_edges(wave[::-1])


def test_independent_finely_integrated_known_fluxes_and_masked_bin():
    # Independent numerical quadrature of Gaussian profiles; does not call the
    # experiment's ndtr/bin integration to synthesize the known data.
    wave = np.linspace(2.15, 3.2, 320)
    edges = bin_edges(wave)
    fluxes = np.array([60.0, 40.0, 45.0, 25.0, 20.0])
    flam = np.zeros(len(wave))
    for j, (rests, weights) in enumerate(LINE_COMPONENTS):
        weights = np.array(weights) / np.sum(weights)
        for rest, fraction in zip(rests, weights):
            center = rest * 1e-4 * 15.44
            sigma = center / 100 / (2 * np.sqrt(2 * np.log(2)))
            for k in range(len(wave)):
                sub = np.linspace(edges[k], edges[k + 1], 301)
                gaussian = np.exp(-0.5 * ((sub - center) / sigma) ** 2) / (
                    np.sqrt(2 * np.pi) * sigma
                )
                flam[k] += (
                    fluxes[j] * fraction * np.trapezoid(gaussian, sub) / (edges[k + 1] - edges[k])
                )
    conversion = 2.99792458e5 / wave**2
    fnu = flam / conversion + 0.02 + 0.003 * (wave - 2.675) / 0.525
    valid = np.ones(len(wave), dtype=bool)
    valid[np.argmin(np.abs(wave - 1486.496 * 1e-4 * 15.44))] = False
    ext = Extraction("known", wave, fnu, np.full_like(wave, 0.0005), valid, {})
    result = fit_lines(ext, np.array([0.5, 6]), np.array([100, 100]))
    assert np.allclose([v["flux"] for v in result["lines"].values()], fluxes, rtol=2e-5)
    assert result["chi2"] < 1e-6


@pytest.mark.parametrize("method", ["optimal", "boxcar", "profile_plus_background"])
def test_2d_extraction_flux_and_propagated_error(method):
    wave = np.linspace(2, 3, 20)
    profile = np.tile(
        np.array([-0.2, 0, 0.1, 0.3, 0.4, 0.2, 0.02, 0, -0.2])[:, None], (1, len(wave))
    )
    source_flux = 0.03
    background = 0.007 if method == "profile_plus_background" else 0
    science = profile * source_flux + background
    weights = np.full_like(science, 1 / 0.005**2)
    ext = extract_2d(wave, science, weights, profile, center=4, radius=2, method=method)
    assert np.all(ext.valid)
    assert np.allclose(ext.flux, source_flux)
    p = profile[2:7, 0]
    if method == "optimal":
        expected = 0.005 / np.sqrt(p @ p)
    elif method == "boxcar":
        expected = 0.005 * np.sqrt(5) / p.sum()
    else:
        # Direct inverse of the two-parameter normal matrix validates background
        # nuisance propagation independently of the extractor's closed formula.
        design = np.column_stack([p, np.ones(5)])
        expected = np.sqrt(np.linalg.inv(design.T @ design / 0.005**2)[0, 0])
    assert np.allclose(ext.error, expected)


def test_masked_spatial_pixels_are_not_zero_flux_measurements():
    wave = np.linspace(2, 3, 20)
    profile = np.tile(np.array([0, 0.1, 0.3, 0.4, 0.2, 0.01, 0])[:, None], (1, len(wave)))
    science = profile * 0.03
    weights = np.full_like(science, 1 / 0.005**2)
    weights[3, 4] = np.nan
    ext = extract_2d(wave, science, weights, profile, center=3, radius=2)
    assert not ext.valid[4]
    assert np.allclose(ext.flux[ext.valid], 0.03)


def test_covariance_respects_missing_original_bins_and_is_positive_definite():
    errors = np.array([1.0, 2.0, 3.0])
    covariance = covariance_matrix(errors, np.array([0, 1, 4]), 0.5)
    assert covariance[1, 2] == pytest.approx(2 * 3 * 0.5**3)
    assert np.all(np.linalg.eigvalsh(covariance) > 0)
    with pytest.raises(ValueError, match="Invalid covariance"):
        covariance_matrix(errors, np.arange(3), 1.0)


def test_intrinsic_width_and_instrument_width_both_enter_model():
    wave = np.linspace(2.15, 3.2, 600)
    unresolved = line_matrix(wave, np.array([0.5, 6]), np.array([300, 300]))
    broadened = line_matrix(
        wave, np.array([0.5, 6]), np.array([300, 300]), intrinsic_fwhm=C_KMS / 300
    )
    assert broadened[:, 0].max() < unresolved[:, 0].max()
    assert np.allclose(np.diff(bin_edges(wave)) @ broadened, 1)


def test_weak_denominator_keeps_unbounded_ratio_uncertainty():
    result = fieller_set(10, 0.1, 1, 10, 0, 3.84)
    assert result["type"] == "two_unbounded_intervals"
    # Exact degeneracy must not divide by zero or return NaN endpoints.
    assert fieller_set(0, 0, 1, 0, 0, 1)["type"] == "all_real"
