"""Frozen MoM noise-control challenge; arithmetic does not certify transport.

No outcome selection or scientific promotion occurs in this module. Row parity
splits observed controls deterministically; correlated rows/nods are not an
independent calibration ensemble. Callers must preserve raw-data provenance.
"""

from __future__ import annotations

import numpy as np


def row_controls(science: np.ndarray, variance: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Normalize without flux clipping, remove constants, adjust lost row dof."""
    if science.shape != variance.shape or science.shape != mask.shape or science.ndim != 3:
        raise ValueError("aligned exposure, spatial-row, spectral-column arrays required")
    valid = mask & np.isfinite(science) & np.isfinite(variance) & (variance > 0)
    result = np.full_like(science, np.nan, dtype=float)
    for exposure in range(science.shape[0]):
        for row in range(science.shape[1]):
            selected = valid[exposure, row]
            count = int(selected.sum())
            if count >= 20:
                values = science[exposure, row, selected] / np.sqrt(
                    variance[exposure, row, selected]
                )
                result[exposure, row, selected] = (values - values.mean()) * np.sqrt(
                    count / (count - 1)
                )
    return result


def parity_calibration(controls: np.ndarray, groups: list[str], columns: np.ndarray) -> dict:
    """Frozen even-row training, odd-row diagnostic and tapered spectral kernel."""
    if controls.ndim != 3 or len(groups) != len(controls) or len(columns) != controls.shape[2]:
        raise ValueError("controls, exposure-group labels and selected columns must align")
    training = controls[:, ::2]
    heldout = controls[:, 1::2]
    if not np.isfinite(training).any():
        raise ValueError("no eligible training controls")
    scale = float(np.nanmean(training**2))
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("nonpositive calibration scale")
    lags, counts = [1.0], []
    for lag in range(1, 4):
        # Native column gaps never become fictitious adjacent wavelength pairs.
        a, b = training[:, :, :-lag], training[:, :, lag:]
        valid = (
            np.isfinite(a) & np.isfinite(b) & (columns[lag:] - columns[:-lag] == lag)[None, None]
        )
        counts.append(int(valid.sum()))
        if not valid.any():
            raise ValueError("insufficient spectral-lag pairs")
        lags.append(float(np.mean(a[valid] * b[valid]) / scale))
    separation = np.abs(columns[:, None] - columns[None, :])
    kernel = np.zeros_like(separation, dtype=float)
    for lag, correlation in enumerate(lags):
        kernel[separation == lag] = correlation * (1 - lag / 4)
    minimum = float(np.linalg.eigvalsh(kernel).min())
    shrink = max(0.0, (0.1 - minimum) / (1 - minimum)) if minimum < 0.1 else 0.0
    kernel = (1 - shrink) * kernel + shrink * np.eye(len(columns))
    records = []
    for group in sorted(set(groups)):
        members = [i for i, value in enumerate(groups) if value == group]
        observed = heldout[members]
        finite = np.isfinite(observed)
        if finite.any():
            ratio = float(np.mean(observed[finite] ** 2) / scale)
            mean = float(np.mean(observed[finite]) / np.sqrt(scale))
        else:
            ratio, mean = None, None
        passed = int(finite.sum()) >= 100 and ratio is not None and 0.70 <= ratio <= 1.30
        passed = passed and mean is not None and abs(mean) <= 0.20
        others = [i for i, value in enumerate(groups) if value != group]
        records.append(
            {
                "group": group,
                "heldout_pixels": int(finite.sum()),
                "variance_ratio": ratio,
                "standardized_mean": mean,
                "passes_frozen_diagnostic": passed,
                "leave_one_group_out_training_scale_squared": float(
                    np.nanmean(training[others] ** 2)
                )
                if others and np.isfinite(training[others]).any()
                else None,
            }
        )
    spatial = {}
    for step in (1, 2):
        a, b = training[:, :-step], training[:, step:]
        finite = np.isfinite(a) & np.isfinite(b)
        spatial[str(2 * step)] = {
            "pair_count": int(finite.sum()),
            "correlation": float(np.mean(a[finite] * b[finite]) / scale) if finite.any() else None,
        }
    return {
        "training_scale_squared": scale,
        "spectral_lag_correlations": lags,
        "spectral_pair_counts": counts,
        "kernel": kernel,
        "shrinkage": shrink,
        "groups": records,
        "even_row_spatial_lags": spatial,
        "control_diagnostics_pass": len(records) == 3
        and all(x["passes_frozen_diagnostic"] for x in records),
        "source_coverage_empirically_certified": False,
    }


def reference_contrast(numerator: float, denominator: float, covariance: np.ndarray) -> dict:
    """Independent Fieller-reference membership via the signed direct contrast."""
    covariance = np.asarray(covariance, dtype=float)
    if covariance.shape != (2, 2) or not np.isfinite(covariance).all():
        raise ValueError("finite numerator/denominator 2x2 covariance required")
    if not np.allclose(covariance, covariance.T) or np.linalg.eigvalsh(covariance).min() < 0:
        raise ValueError("symmetric positive-semidefinite covariance required")
    reference = 10**-0.60
    weights = np.array([1.0, -reference])
    variance = float(weights @ covariance @ weights)
    delta = numerator - reference * denominator
    threshold = 1.95996398454**2 * variance
    return {
        "reference": reference,
        "signed_contrast": delta,
        "contrast_variance": variance,
        "reference_admitted": bool(delta**2 <= threshold),
        "test_family_size": 1,
        "familywise_alpha": 0.05,
        "elemental_inference": False,
    }
