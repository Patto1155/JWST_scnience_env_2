"""Checks for group resampling and committed paired-log numerical reproduction."""

import numpy as np

from data_pipeline.flux_deficit import fits, injection_summary, rows


def test_committed_training_regression_reproduces_prompt():
    result = fits(rows(), repetitions=30)
    assert result["n"] == result["objects"] == 29
    np.testing.assert_allclose(
        [result["models"]["1"]["a"], result["models"]["1"]["b"]],
        [-0.042276324615788625, -0.9613016545191906],
        atol=1e-12,
    )
    assert result["negative"] == 23


def test_background_object_bootstrap_does_not_treat_duplicates_as_independent():
    sample = [dict(unique_id="a", ratio=0.8), dict(unique_id="b", ratio=1.2)]
    original = injection_summary(sample)
    repeated = injection_summary(sample * 100)
    assert original["objects"] == repeated["objects"] == 2
    np.testing.assert_allclose(original["mean_ci95"], repeated["mean_ci95"])
    np.testing.assert_allclose(original["mean_ci95"], [0.8, 1.2])
