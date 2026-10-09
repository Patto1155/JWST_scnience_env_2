"""Independent exact-covariance controls for the empirical blank-aperture method.

The scientific null here is known: stationary Gaussian pixels produced by a
specified finite convolution kernel.  It is not a simulation of actual JWST sky.
The exact variance follows by composing the aperture operator with that kernel,
rather than reconstructing covariance from the method under review.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.signal import convolve2d, fftconvolve

from discovery.psf_noise import blank_aperture_report


def aperture_operator(radius_arcsec: float = 0.189, scale_arcsec: float = 0.063) -> np.ndarray:
    """Independent explicit integer-center aperture minus mean-annulus operator."""
    yy, xx = np.mgrid[-12:13, -12:13]
    distance = np.sqrt(xx**2 + yy**2) * scale_arcsec
    aperture = distance <= radius_arcsec
    annulus = (distance >= 2 * radius_arcsec) & (distance <= (10 / 3) * radius_arcsec)
    return aperture.astype(float) - annulus * aperture.sum() / annulus.sum()


def exact_noise_multiplier(operator: np.ndarray, kernel: np.ndarray) -> float:
    """Sigma(A K epsilon)/sigma_diagonal(A), for unit-variance filtered pixels.

    A's signed annulus coefficients are retained. Constant sky modes cancel;
    autocovariance need not increase variance when negative lobes are present.
    """
    if not np.isfinite(kernel).all() or np.sum(kernel**2) <= 0:
        raise ValueError("Kernel must be finite and nonzero")
    kernel = kernel / np.sqrt(np.sum(kernel**2))
    composed = convolve2d(operator, kernel, mode="full")
    return float(np.sqrt(np.sum(composed**2) / np.sum(operator**2)))


def run_controls() -> dict[str, Any]:
    operator = aperture_operator()
    kernels = {
        "white": np.ones((1, 1)),
        "positive_neighbor_covariance": np.outer([1, 2, 1], [1, 2, 1]),
        "negative_neighbor_covariance": np.outer([-1, 2, -1], [-1, 2, -1]),
    }
    trials = []
    for seed in range(80000, 80006):
        white = np.random.default_rng(seed).normal(size=(768, 768))
        for name, kernel in kernels.items():
            expected = exact_noise_multiplier(operator, kernel)
            kernel = kernel / np.sqrt(np.sum(kernel**2))
            image = fftconvolve(white, kernel, mode="same")
            report = blank_aperture_report(
                {"sci": image, "err": np.ones(image.shape), "header": {"BUNIT": "nJy"}},
                radii=(0.189,),
                pixel_scale_arcsec=0.063,
                mask=np.zeros(image.shape, dtype=bool),
                synthetic=True,
                seed=731 + seed - 80000,
                bootstrap=100,
            )["apertures"][0]
            interval = report["noise_multiplier_block_bootstrap_95"]
            trials.append(
                {
                    "kind": name,
                    "seed": seed,
                    "apertures": report["n_apertures"],
                    "exact_multiplier": expected,
                    "measured_robust_multiplier": report["noise_multiplier"],
                    "block_bootstrap_95": interval,
                    "interval_contains_exact": interval[0] <= expected <= interval[1],
                }
            )
    summaries = {}
    for name in kernels:
        selected = [r for r in trials if r["kind"] == name]
        summaries[name] = {
            "exact_multiplier": selected[0]["exact_multiplier"],
            "measured_range": [
                min(r["measured_robust_multiplier"] for r in selected),
                max(r["measured_robust_multiplier"] for r in selected),
            ],
            "interval_contains_exact_count": sum(r["interval_contains_exact"] for r in selected),
            "trials": len(selected),
        }
    return {
        "schema_version": 1,
        "synthetic_control": True,
        "independent_oracle": "exact convolution of signed aperture operator and known kernel",
        "geometry": {
            "radius_arcsec": 0.189,
            "scale_arcsec": 0.063,
            "annulus_factors": [2, 10 / 3],
            "mask": "explicit empty mask",
        },
        "image_shape": [768, 768],
        "summaries": summaries,
        "trials": trials,
        "limits": [
            "Six realizations are not a calibrated estimate of 95% interval coverage.",
            "Synthetic covariance is known; actual JWST covariance, sources and backgrounds "
            "are not.",
            "Uncertainty multipliers may be below one; off-diagonal covariance does not imply "
            "inflation.",
            "This oracle excludes source-mask selection, heteroscedastic ERR and source Poisson "
            "variance.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("research_output/adversarial_noise_controls.json")
    )
    args = parser.parse_args()
    result = run_controls()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result["summaries"]))


if __name__ == "__main__":
    main()
