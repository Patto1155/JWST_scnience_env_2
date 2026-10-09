"""Detector calibration for raw JWST up-the-ramp data.

Raw ``_uncal`` ramps are uncorrected. Measuring accumulation history on them
directly produces a bias that looks astrophysical but is not: a pixel's response
flattens well before hard saturation, which makes its first group-to-group
increment the largest and mimics an instantaneous charge deposition. Compact
sources concentrate flux into fewer pixels, reach high signal first, and are
penalised hardest - so an uncorrected ramp statistic rejects compact real
sources exactly like a morphology cut does, by a different route.

This module applies the same corrections the JWST Detector1 pipeline applies
before its jump step, using the CRDS reference files the exposure header names:

- superbias subtraction, since the linearity polynomial is defined on
  bias-subtracted counts
- the per-pixel linearity polynomial
- per-pixel saturation limits, rather than one global DN ceiling
- read noise and gain, so a ramp deviation can be expressed as a significance
  rather than a raw fraction

Reference files are read directly; the ``jwst`` package is not required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from astropy.io import fits

DEFAULT_CRDS_DIR = Path("data/crds")

# Reference-file keywords in the calibrated product's primary header.
REFERENCE_KEYWORDS = {
    "linearity": "R_LINEAR",
    "saturation": "R_SATURA",
    "readnoise": "R_READNO",
    "gain": "R_GAIN",
    "superbias": "R_SUPERB",
}


def reference_filename(header: fits.Header, kind: str) -> Optional[str]:
    """Return the bare CRDS filename the exposure was processed with."""
    value = header.get(REFERENCE_KEYWORDS[kind])
    if not value or value == "N/A":
        return None
    return str(value).split("/")[-1]


def load_references(
    header: fits.Header,
    crds_dir: Path = DEFAULT_CRDS_DIR,
) -> Dict[str, Any]:
    """Load whichever CRDS references are present on disk.

    Missing references are reported rather than silently skipped, so a caller
    never mistakes partially-corrected data for corrected data.
    """
    loaded: Dict[str, Any] = {"available": {}, "missing": []}
    for kind in REFERENCE_KEYWORDS:
        name = reference_filename(header, kind)
        if not name:
            loaded["missing"].append(kind)
            continue
        path = crds_dir / name
        if not path.exists():
            loaded["missing"].append(kind)
            continue
        with fits.open(path) as handle:
            if kind == "linearity":
                loaded["linearity_coeffs"] = np.array(handle["COEFFS"].data, dtype=float)
            else:
                loaded[kind] = np.array(handle["SCI"].data, dtype=float)
        loaded["available"][kind] = name
    return loaded


def apply_linearity(
    ramp: np.ndarray,
    coefficients: np.ndarray,
    superbias: Optional[np.ndarray],
) -> np.ndarray:
    """Apply the CRDS linearity polynomial to a raw ramp.

    The correction is the polynomial ``sum_i c_i * x^i`` evaluated on
    bias-subtracted counts, matching the pipeline's linearity step. The bias is
    added back afterwards so the output stays on a DN scale comparable with the
    input.
    """
    bias = superbias if superbias is not None else 0.0
    bias = np.nan_to_num(bias, nan=0.0)

    # CRDS flags unusable pixels with NaN coefficients. Leave those pixels
    # uncorrected (identity) rather than propagating NaN through the ramp; the
    # saturation mask and per-pixel noise model handle them downstream.
    coefficients = np.asarray(coefficients, dtype=float).copy()
    bad = ~np.all(np.isfinite(coefficients), axis=0)
    if np.any(bad):
        coefficients[:, bad] = 0.0
        coefficients[1, bad] = 1.0

    corrected = np.empty_like(ramp)
    for group in range(ramp.shape[0]):
        x = ramp[group] - bias
        accumulator = np.zeros_like(x)
        for order in range(coefficients.shape[0] - 1, -1, -1):
            accumulator = accumulator * x + coefficients[order]
        corrected[group] = accumulator + bias
    return corrected


def saturation_mask(
    ramp: np.ndarray,
    saturation: Optional[np.ndarray],
    *,
    fraction: float = 0.8,
    fallback_dn: float = 40000.0,
) -> np.ndarray:
    """Boolean mask of pixels whose whole ramp stays in the trustworthy range.

    Per-pixel limits from CRDS replace a single global ceiling. The fraction
    keeps a margin below the hard limit, where the linearity polynomial is fitted
    and reliable.
    """
    if saturation is None:
        limit = np.full(ramp.shape[-2:], fallback_dn, dtype=float)
    else:
        limit = np.asarray(saturation, dtype=float) * float(fraction)
    limit = np.where(np.isfinite(limit), limit, fallback_dn)
    return np.all(ramp < limit[None, :, :], axis=0)


# Read noise and Poisson alone do not describe a real ramp. Residual
# non-linearity, inter-pixel capacitance, correlated read noise and the scalar
# background estimate all leave signal-proportional residuals. Without a term for
# them the chi-squared of a bright source explodes purely because its formal
# errors are tiny, and the statistic re-acquires the brightness - and therefore
# compactness - bias it was built to remove.
# Empirically this floor does not help: it lowers discrimination without
# reducing the bias, because the residual bias is statistical rather than
# systematic. Kept at zero and exposed so the finding stays reproducible.
DEFAULT_MODEL_ERROR_FRACTION = 0.0


def group_variance(
    signal_dn: np.ndarray,
    readnoise_dn: np.ndarray,
    gain: np.ndarray,
    n_frames: int,
    model_error_fraction: float = DEFAULT_MODEL_ERROR_FRACTION,
) -> np.ndarray:
    """Per-group variance in DN^2: read noise, Poisson, and a model-error floor.

    A group is the average of ``n_frames`` reads, so its read-noise term scales
    down accordingly. The Poisson term is the accumulated signal in electrons
    converted back to DN^2. The fractional term represents everything the first
    two do not describe.
    """
    read_term = np.square(readnoise_dn) / max(int(n_frames), 1)
    poisson_term = np.clip(signal_dn, 0.0, None) / np.where(gain > 0, gain, np.nan)
    systematic_term = np.square(float(model_error_fraction) * np.clip(signal_dn, 0.0, None))
    return read_term + np.nan_to_num(poisson_term, nan=0.0) + systematic_term


def jump_significance(
    signal: np.ndarray,
    variance: np.ndarray,
) -> Dict[str, np.ndarray]:
    """Significance of the best single jump over a straight-line ramp.

    Compares a linear accumulation model against linear-plus-one-step by their
    chi-squared difference, so the output is in sigma and does not grow simply
    because a source is bright. That is the property the raw increment fraction
    lacked, and the reason it inherited a brightness - and therefore a
    compactness - bias.

    ``signal`` and ``variance`` are (n_groups, n_pixels).
    """
    n_groups, n_pixels = signal.shape
    groups = np.arange(n_groups, dtype=float)
    weights = 1.0 / np.clip(variance, 1e-12, None)

    def _weighted_chi2(design: np.ndarray) -> np.ndarray:
        """Weighted least squares for every pixel at once via normal equations."""
        # design (n_groups, n_terms); weights and signal (n_groups, n_pixels).
        normal = np.einsum("gi,gn,gj->nij", design, weights, design)
        target = np.einsum("gi,gn,gn->ni", design, weights, signal)
        # Ridge nudge keeps the 3-term fit solvable when a pixel's weights are
        # nearly degenerate; it is far below the noise scale.
        normal = normal + 1e-10 * np.eye(design.shape[1])[None, :, :]
        coefficients = np.linalg.solve(normal, target[:, :, None])[:, :, 0]
        total = np.einsum("gn,gn,gn->n", weights, signal, signal)
        return np.clip(total - np.einsum("ni,ni->n", coefficients, target), 0.0, None)

    linear_design = np.vstack([groups, np.ones(n_groups)]).T
    chi2_linear = _weighted_chi2(linear_design)

    best_chi2 = np.full(n_pixels, np.inf)
    best_group = np.zeros(n_pixels, dtype=int)
    for jump_at in range(1, n_groups):
        design = np.vstack([groups, (groups >= jump_at).astype(float), np.ones(n_groups)]).T
        chi2 = _weighted_chi2(design)
        improved = chi2 < best_chi2
        best_chi2 = np.where(improved, chi2, best_chi2)
        best_group = np.where(improved, jump_at, best_group)

    delta_chi2 = np.clip(chi2_linear - best_chi2, 0.0, None)
    return {
        "significance": np.sqrt(delta_chi2),
        "chi2_linear": chi2_linear,
        "chi2_jump": best_chi2,
        "jump_group": best_group,
        "linear_fit": linear_design @ np.linalg.solve(
            np.einsum("gi,gn,gj->nij", linear_design, weights, linear_design)
            + 1e-10 * np.eye(2)[None, :, :],
            np.einsum("gi,gn,gn->ni", linear_design, weights, signal)[:, :, None],
        )[:, :, 0].T,
    }


def jump_pvalue(
    signal: np.ndarray,
    variance: np.ndarray,
    *,
    n_trials: int = 200,
    seed: int = 0,
) -> Dict[str, np.ndarray]:
    """Calibrate the jump statistic against its own null distribution.

    The best-of-several-positions search means the statistic is not chi-distributed
    with one degree of freedom: fitting an extra free parameter to a short, noisy
    ramp buys apparent significance by chance. That look-elsewhere effect scales
    with noise, so an uncalibrated threshold rejects faint sources preferentially -
    which, since faint sources here are mostly compact, reappears as a compactness
    bias.

    The null is generated per pixel by parametric bootstrap: take the fitted
    linear ramp, add noise drawn from that pixel's own variance, and measure how
    often the statistic exceeds the observed value.
    """
    observed = jump_significance(signal, variance)
    rng = np.random.default_rng(seed)
    baseline = observed["linear_fit"]

    exceedances = np.zeros(signal.shape[1], dtype=float)
    for _ in range(n_trials):
        synthetic = baseline + rng.normal(0.0, np.sqrt(np.clip(variance, 1e-12, None)))
        null = jump_significance(synthetic, variance)["significance"]
        exceedances += (null >= observed["significance"]).astype(float)

    # Additive smoothing keeps p from collapsing to exactly zero at finite trials.
    pvalue = (exceedances + 1.0) / (n_trials + 1.0)
    return {
        "significance": observed["significance"],
        "pvalue": pvalue,
        "neg_log10_p": -np.log10(np.clip(pvalue, 1e-12, None)),
        "jump_group": observed["jump_group"],
    }
