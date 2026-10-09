"""Independent covariance oracles and sparse-control counterexamples."""

import numpy as np
import pytest

from tools.jwst.native_reduction import mixing_matrix, shared_extraction_covariance
from tools.jwst.native_spatial_covariance import (
    below_break_control,
    spatial_moments,
    stationary_spatial_kernel,
)


def test_spatial_shared_covariance_matches_raw_field_draws():
    rng = np.random.default_rng(18473)
    rows, columns, trials = 9, 2, 90000
    covariance = 0.25 ** np.abs(np.arange(rows)[:, None] - np.arange(rows)[None])
    raw_variance = rng.uniform(0.5, 2, (3, rows, columns))
    operators = rng.normal(size=(3, rows, columns))
    mixing = mixing_matrix()
    expected = shared_extraction_covariance(raw_variance, operators, mixing, covariance)
    for column in range(columns):
        raw = np.empty((trials, 3, rows))
        for nod in range(3):
            standard_error = np.sqrt(raw_variance[nod, :, column])
            field_covariance = standard_error[:, None] * covariance * standard_error[None, :]
            raw[:, nod] = rng.normal(size=(trials, rows)) @ np.linalg.cholesky(field_covariance).T
        post = np.einsum("ij,tjr->tir", mixing, raw)
        samples = np.sum(post * operators[:, :, column][None], axis=2)
        measured = np.cov(samples, rowvar=False)
        diagonal = np.diag(expected[column])
        sigma = np.sqrt(
            (diagonal[:, None] * diagonal[None, :] + expected[column] ** 2) / (trials - 1)
        )
        assert np.all(np.abs(measured - expected[column]) < 5 * sigma)
        assert np.linalg.eigvalsh(expected[column]).min() > 0


def test_identity_spatial_kernel_is_original_diagonal_operator():
    rng = np.random.default_rng(382)
    raw, operators = rng.uniform(0.1, 2, (3, 7, 3)), rng.normal(size=(3, 7, 3))
    original = shared_extraction_covariance(raw, operators, mixing_matrix())
    identity = shared_extraction_covariance(raw, operators, mixing_matrix(), np.eye(7))
    assert np.allclose(original, identity, rtol=1e-12, atol=1e-12)


def test_positive_row_covariance_can_raise_or_lower_operator_variance():
    rows = 12
    raw = np.ones((3, rows, 1))
    kernel = 0.4 ** np.abs(np.arange(rows)[:, None] - np.arange(rows)[None])
    positive = np.ones((3, rows, 1))
    alternating = positive * ((-1.0) ** np.arange(rows))[None, :, None]
    for operator, direction in [(positive, "larger"), (alternating, "smaller")]:
        diagonal = shared_extraction_covariance(raw, operator, mixing_matrix())[0, 0, 0]
        correlated = shared_extraction_covariance(raw, operator, mixing_matrix(), kernel)[0, 0, 0]
        assert correlated > diagonal if direction == "larger" else correlated < diagonal


def test_noisy_spatial_moments_have_explicit_psd_shrinkage():
    kernel, metadata = stationary_spatial_kernel([1.0, 0.9, -0.9, 0.9], 28, taper=False)
    assert metadata["minimum_eigenvalue_before_guard"] < 0
    assert metadata["identity_shrinkage_to_min_eigenvalue0p1"] > 0
    assert np.linalg.eigvalsh(kernel).min() == pytest.approx(0.1)
    assert np.allclose(np.diag(kernel), 1)
    with pytest.raises(ValueError):
        stationary_spatial_kernel([0.8, 0.1], 28)


def test_missing_spatial_pairs_are_not_zero_covariance_evidence():
    controls = np.full((3, 28, 70), np.nan)
    controls[:, 4] = np.random.default_rng(744).normal(size=(3, 70))
    with pytest.raises(ValueError, match="no observed control pairs"):
        spatial_moments(controls)


def test_below_break_operator_control_rejects_empty_ensemble():
    wave = np.linspace(1.1, 1.75, 50)
    data = [{"wave": np.tile(wave, (28, 1))} for _ in range(9)]
    flux = np.zeros((9, 50))
    blocks = np.tile(np.eye(9), (50, 1, 1))
    control = below_break_control(data, flux, blocks, 2.2)
    assert control["normalized_rms"] == 0
    assert control["positive_formal_above3_count"] == 0
    assert np.allclose(control["shared_formal_sigma_uJy"], 1 / 3)
    for d in data:
        d["wave"] += 1
    with pytest.raises(ValueError, match="Insufficient source-operator"):
        below_break_control(data, flux, blocks, 2.2)
