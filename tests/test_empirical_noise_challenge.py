"""Independent numerical checks for the frozen noise-control arithmetic."""

import numpy as np
import pytest

from tools.jwst.empirical_noise_challenge import (
    parity_calibration,
    reference_contrast,
    row_controls,
)


def test_unclipped_row_controls_use_err_once_and_lost_dof():
    values = np.arange(24, dtype=float)[None, None]
    controls = row_controls(values, np.full_like(values, 4), np.ones_like(values, dtype=bool))
    assert np.mean(controls**2) == pytest.approx(np.var(np.arange(24), ddof=1) / 4)
    assert abs(np.mean(controls)) < 1e-12
    assert np.max(controls) > 3  # no flux-dependent clipping


def test_wrong_heldout_noise_fails_without_influencing_training_scale():
    rng = np.random.default_rng(702)
    noise = rng.normal(size=(9, 12, 200))
    groups = ["03"] * 3 + ["05"] * 3 + ["07"] * 3
    normal = parity_calibration(noise, groups, np.arange(200))
    noise[:, 1::2] *= 3
    inflated = parity_calibration(noise, groups, np.arange(200))
    assert normal["control_diagnostics_pass"]
    assert not inflated["control_diagnostics_pass"]
    assert normal["training_scale_squared"] == inflated["training_scale_squared"]
    assert np.linalg.eigvalsh(normal["kernel"]).min() >= 0.1 - 1e-12
    assert not normal["source_coverage_empirically_certified"]


def test_no_controls_cannot_pass():
    with pytest.raises(ValueError, match="no eligible"):
        parity_calibration(np.full((9, 2, 20), np.nan), ["03"] * 9, np.arange(20))


def test_signed_direct_contrast_keeps_null_and_rejects_tight_alternative():
    reference = 10**-0.60
    assert reference_contrast(reference, 1, np.eye(2))["reference_admitted"]
    assert not reference_contrast(5, 1, np.eye(2) * 0.001)["reference_admitted"]
    assert reference_contrast(-0.1, 1, np.eye(2))["reference_admitted"]
    # Large denominator variance means a bounded positive ratio cannot be presumed.
    assert reference_contrast(1, 0, np.diag([1, 100]))["reference_admitted"]
