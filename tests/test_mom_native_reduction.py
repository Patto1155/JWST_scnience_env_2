"""Independent analytic/synthetic oracles for actual native-nod operations."""

import numpy as np
import pytest

from tools.jwst.line_sensitivity import line_matrix
from tools.jwst.native_reduction import (
    covariance_blocks,
    extract_columns,
    fit_native,
    gaussian_profile,
    mixing_matrix,
    point_conversion,
    recover_raw_variance,
    shared_extraction_covariance,
    signed_profiles,
)


def test_uniform_to_point_units_restore_before_correcting():
    area = 5e-13
    # MJy/sr -> uJy contributes 0.5. The UN/bar correction is already in SCI.
    conversion = point_conversion(area, np.array([0.8]), np.array([0.4]), np.array([0.75]))
    assert conversion[0] == pytest.approx(0.75)
    # A raw aperture sample of 4uJy, with point throughput0.4, generates the
    # uniform/barshadow product below. One conversion recovers4, not10.
    extended_sci = 4 * 0.4 / (area * 1e12 * 0.8 * 0.75)
    assert extended_sci * conversion[0] == pytest.approx(4)
    with pytest.raises(ValueError):
        point_conversion(0, np.ones(1), np.ones(1), np.ones(1))


def test_raw_variance_recovery_unequal_noise_oracle():
    raw = np.array([1.0, 4.0, 9.0])[:, None, None]
    matrix = mixing_matrix()
    post = np.einsum("ij,jrc->irc", matrix**2, raw)
    assert np.allclose(recover_raw_variance(post, matrix), raw)
    covariance = matrix @ np.diag(raw[:, 0, 0]) @ matrix.T
    assert np.linalg.matrix_rank(covariance) == 2
    # Shared background removes common signal; cannot invert SCI to raw rates.
    assert np.allclose(matrix @ np.ones(3), 0)
    assert np.any(covariance < 0)


def test_shared_covariance_matches_independent_monte_carlo():
    rng = np.random.default_rng(7342)
    raw = rng.uniform(0.5, 2, size=(3, 5, 2))
    operators = rng.normal(size=(3, 5, 2))
    matrix = mixing_matrix()
    analytic = shared_extraction_covariance(raw, operators, matrix)
    draws = rng.normal(size=(120000, 3, 5, 2)) * np.sqrt(raw)
    post = np.einsum("ij,tjrc->tirc", matrix, draws)
    extracted = np.sum(operators[None] * post, axis=2)
    for column in range(2):
        measured = np.cov(extracted[:, :, column], rowvar=False)
        expected = analytic[column]
        sigma = np.sqrt(
            (np.diag(expected)[:, None] * np.diag(expected)[None, :] + expected**2)
            / (len(draws) - 1)
        )
        assert np.all(np.abs(measured - expected) < 5 * sigma)
    # Counterexample: summing diagonal nod variances loses signed correlations.
    assert abs(analytic[0, 0, 1]) > 0.1


def test_signed_ghost_profile_recovers_flux_with_background_slope():
    rows, columns = 28, 50
    traces = [np.full(columns, center) for center in (12.0, 17.0, 7.0)]
    yy = (np.arange(rows)[:, None] - rows / 2) / rows
    flux_true = np.linspace(0.01, 0.08, columns)
    data = [
        {
            "trace_seed": t,
            "point_pathloss": np.full((rows, columns), 0.7),
            "science": np.zeros((rows, columns)),
            "variance": np.full((rows, columns), 0.01),
            "good": np.ones((rows, columns), dtype=bool),
            "group": "03",
        }
        for t in traces
    ]
    profiles = signed_profiles(data, 0.7, 0)
    for i, d in enumerate(data):
        d["science"] = profiles[i] * flux_true + 0.03 + 0.02 * yy
    recovered, operators, residuals = extract_columns(data, profiles)
    assert np.allclose(recovered, flux_true[None])
    assert np.allclose(residuals, 0, atol=1e-12)
    assert np.allclose(np.sum(operators * profiles, axis=1), 1)
    assert np.allclose(np.sum(operators, axis=1), 0, atol=1e-12)
    # Positive-only normalization omits negative ghosts and is a different model.
    assert np.any(profiles[0] < -0.1)


def test_subpixel_profile_integrates_to_one_without_renormalized_mask():
    profile = gaussian_profile(np.array([7.2, 0.0]), 0.8, 20)
    assert profile[:, 0].sum() == pytest.approx(1, abs=1e-10)
    assert profile[:, 1].sum() < 0.8
    with pytest.raises(ValueError):
        gaussian_profile(np.array([1.0]), 0, 20)


def test_impossible_variance_demix_is_reported_and_reconciled_conservatively():
    columns = 5
    post = np.array([1.0, 1.0, 9.0])
    data = [
        {
            "group": "03",
            "variance": np.full((8, columns), value),
            "wave": np.full((8, columns), 2.5),
            "good": np.ones((8, columns), bool),
        }
        for value in post
    ]
    operators = np.full((3, 8, columns), 1 / 8)
    covariance, metadata = covariance_blocks(data, operators)
    assert metadata["groups"][0]["negative_inferred_raw_pixels"] == 8 * columns
    assert np.all(np.linalg.eigvalsh(covariance) > -1e-12)
    assert np.all(np.diagonal(covariance, axis1=1, axis2=2) >= post / 8 - 1e-12)


def test_native_flux_gls_oracle_preserves_signed_lines_and_mask_bin_edges():
    rows, columns = 28, 80
    wave = np.linspace(2.1, 3.25, columns)
    truth = np.array([40.0, -8.0, 20.0, 5.0, 25.0])
    resolution_wave, resolution = np.array([1.0, 5.0]), np.array([100.0, 100.0])
    line_density = line_matrix(wave, resolution_wave, resolution)
    conversion = 2.99792458e5 / wave**2
    flux_true = line_density @ truth / conversion + 0.02 + 0.005 * (wave - 2.675) / 0.525
    data = [
        {
            "trace_seed": np.full(columns, center),
            "point_pathloss": np.full((rows, columns), 0.7),
            "science": np.zeros((rows, columns)),
            "variance": np.full((rows, columns), 0.0015),
            "wave": np.tile(wave, (rows, 1)),
            "good": np.ones((rows, columns), bool),
            "group": "03",
        }
        for center in (12.0, 17.0, 7.0)
    ]
    profiles = signed_profiles(data, 0.75, 0)
    for d, profile in zip(data, profiles):
        d["science"] = profile * flux_true + 0.03
    flux, operators, _ = extract_columns(data, profiles)
    covariance, _ = covariance_blocks(data, operators)
    selected = np.flatnonzero((wave > 2.15) & (wave < 3.2))
    selected = np.delete(selected, 12)  # Missing column must not change bin edges.
    fit = fit_native(data, flux, covariance, selected, resolution_wave, resolution)
    assert np.allclose(fit["fluxes"], truth, atol=1e-10)
    assert fit["conditional_chi2"] < 1e-20
    corr = np.array(fit["median_exposure_amplitude_correlation"])
    assert np.all(corr > 0)  # Extracted nod amplitudes reuse positive/negative ghosts.
