"""Independent physical covariance counterexamples and alternate optimizer controls."""

import numpy as np
import pytest
from scipy.optimize import nnls

from discovery.continuation_final_review import (
    active_set_raw_variance,
    latent_nod_covariance,
    patch_fit_oracle,
)


def test_nonnegative_raw_demix_matches_separate_nnls_on_unequal_variances():
    matrix = np.full((3, 3), 0.25)
    np.fill_diagonal(matrix, 1)
    rng = np.random.default_rng(7353)
    for observed in np.exp(rng.uniform(-4, 4, (50, 3))):
        expected = nnls(matrix, observed / observed.max())[0] * observed.max()
        assert active_set_raw_variance(observed) == pytest.approx(expected, rel=1e-10, abs=1e-10)


def test_nonlocal_row_covariance_survives_shared_nod_subtraction():
    spatial = np.array([[1, 0.4], [0.4, 1]])
    operators = np.array([[1, 0], [0, 1], [0.5, 0.5]])
    covariance = latent_nod_covariance(np.ones((3, 2)), np.zeros((3, 2)), operators, spatial)
    assert covariance == pytest.approx(
        np.array(
            [
                [1.5, -0.3, -0.525],
                [-0.3, 1.5, -0.525],
                [-0.525, -0.525, 1.05],
            ]
        )
    )
    diagonal_only = latent_nod_covariance(np.ones((3, 2)), np.zeros((3, 2)), operators, np.eye(2))
    assert abs(diagonal_only[0, 1] - covariance[0, 1]) > 0.2


def test_latent_covariance_rejects_nan_negative_variance_or_bad_kernel():
    raw = np.ones((3, 2))
    for invalid in (raw * np.nan, -raw):
        with pytest.raises(ValueError):
            latent_nod_covariance(invalid, raw, raw, np.eye(2))
    for invalid in (np.array([[1, 2], [2, 1]]), np.eye(2) * 2):
        with pytest.raises(ValueError):
            latent_nod_covariance(raw, raw, raw, invalid)


def test_independent_patch_oracle_preserves_signed_quadratic_signal():
    y, x = np.mgrid[-0.65:0.651:0.025, -0.65:0.651:0.025]
    psf = np.exp(-(x * x + y * y) / (2 * 0.045**2))
    psf /= psf.sum()
    background = 5 + x - 2 * y + 2 * x * x + x * y - 3 * y * y
    for amplitude in (-35.0, 35.0):
        fit = patch_fit_oracle(
            amplitude * psf + background,
            np.ones_like(x),
            psf,
            x,
            y,
            np.ones_like(x, dtype=bool),
            2,
            0.2,
        )
        assert fit["signed_point_amplitude_njy"] == pytest.approx(amplitude, abs=1e-10)
        assert fit["source_excluded_background_point_amplitude_njy"] == pytest.approx(
            amplitude, abs=1e-6
        )
