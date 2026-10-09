"""Bounded modeled-PSF/synthetic-background stress test of the frozen pipeline.

This is not independent real-sky validation. No source is an observed star and
no detector artifacts are simulated. Runs use existing segmentation/morphology
and the frozen classifier, with a distinct Gaussian-convolution renderer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import warnings
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits
from scipy.signal import fftconvolve

from discovery.artifact_characterization import detect_with_morphology
from discovery.artifact_classifier import classify, psf_fwhm_pixels
from discovery.validation_metrics import injection_metrics

TARGET_SCALE_ARCSEC = 0.063
STAMP_SIZE = 61
DEFAULT_FLUXES = (30.0, 60.0, 120.0, 240.0)
DEFAULT_RADII = (0.0, 0.75, 1.5)
GENERATOR_ID = "external-psf-gaussian-intrinsic-overlap-v1"


def resample_kernel(kernel: np.ndarray, input_scale: float, output_scale: float,
                    size: int = STAMP_SIZE) -> tuple[np.ndarray, dict[str, float]]:
    """Pixel-overlap integration conserves discrete flux inside the output crop.

    Values are source flux fractions, not MJy/sr calibrated pixels. No cubic
    interpolation or clipping changes the source shape. Normalize *after* the
    bounded crop and explicitly report discarded wings.
    """
    kernel = np.asarray(kernel, dtype=float)
    if (kernel.ndim != 2 or any(n % 2 == 0 for n in kernel.shape) or size % 2 == 0
            or size <= 0 or not np.isfinite(kernel).all() or np.any(kernel < 0)
            or not np.isfinite([input_scale, output_scale]).all()
            or min(input_scale, output_scale) <= 0 or kernel.sum() <= 0):
        raise ValueError("require finite nonnegative odd-sized kernel and positive scales")

    def overlap(n: int) -> np.ndarray:
        old = (np.arange(n + 1) - n / 2) * input_scale
        new = (np.arange(size + 1) - size / 2) * output_scale
        return np.maximum(0.0, np.minimum(new[1:, None], old[None, 1:])
                          - np.maximum(new[:-1, None], old[None, :-1])) / input_scale

    resampled = overlap(kernel.shape[0]) @ kernel @ overlap(kernel.shape[1]).T
    raw_sum = float(kernel.sum())
    crop_sum = float(resampled.sum())
    if crop_sum <= 0:
        raise ValueError("PSF crop contains no flux")
    normalized = resampled / crop_sum
    yy, xx = np.mgrid[:size, :size] - size // 2
    return normalized, {"raw_sum": raw_sum,
                                 "retained_fraction": crop_sum / raw_sum,
                                 "input_scale_arcsec": float(input_scale),
                                 "target_scale_arcsec": float(output_scale),
                                 "centroid_offset_x_px": float(np.sum(xx * normalized)),
                                 "centroid_offset_y_px": float(np.sum(yy * normalized))}


def load_verified_psf(path: Path, filter_name: str) -> tuple[np.ndarray, dict[str, Any]]:
    raw = path.read_bytes()
    receipt = json.loads(path.with_name(path.name + ".provenance.json").read_text())
    checksum = hashlib.sha256(raw).hexdigest()
    if checksum != receipt["sha256"] or len(raw) != receipt["bytes"]:
        raise ValueError(f"PSF bytes differ from receipt: {path.name}")
    with fits.open(path) as hdus:
        hdu = next(hdu for hdu in hdus if hdu.data is not None and hdu.data.ndim == 2)
        if str(hdu.header.get("FILTER", "")).upper() != filter_name:
            raise ValueError("PSF FILTER does not match experiment filter")
        kernel, metadata = resample_kernel(hdu.data, float(hdu.header["PIXELSCL"]), TARGET_SCALE_ARCSEC)
    return kernel, {**metadata, "filter": filter_name, "sha256": checksum,
                    "requested_url": receipt["requested_url"], "resolved_url": receipt["resolved_url"],
                    "retrieved_utc": receipt["retrieved_utc"], "bytes": len(raw),
                    "origin": "official JADES DR5 modeled PSF; normalized shape, not stellar truth"}


def gaussian_kernel(sigma_pixels: float, size: int = STAMP_SIZE) -> np.ndarray:
    if sigma_pixels <= 0 or not np.isfinite(sigma_pixels):
        raise ValueError("Gaussian width must be finite and positive")
    y, x = np.mgrid[:size, :size] - size // 2
    kernel = np.exp(-(x*x + y*y) / (2*sigma_pixels*sigma_pixels))
    return kernel / kernel.sum()


def independent_stamp(psf: np.ndarray, radius: float) -> np.ndarray:
    """Use a Gaussian intrinsic profile, independent of the training Sersic code."""
    if radius < 0:
        raise ValueError("half-light radius cannot be negative")
    if radius == 0:
        return psf.copy()
    intrinsic = gaussian_kernel(radius / np.sqrt(2*np.log(2)), psf.shape[0])
    result = fftconvolve(psf, intrinsic, mode="same")
    result = np.maximum(result, 0.0)  # FFT roundoff only; kernels are nonnegative.
    return result / result.sum()


def run_cell(stamp: np.ndarray, filter_name: str, model: dict[str, Any], *,
             flux: float, radius: float, seed: int, batch: int, kind: str,
             warning_counts: dict[str, int] | None = None) -> list[dict[str, Any]]:
    """16 separated injections; background is paired by seed between kernel types."""
    if not np.isfinite(flux) or flux <= 0:
        raise ValueError("flux must be positive in units of per-pixel noise sigma")
    image = np.random.default_rng(seed).normal(0.0, 1.0, (320, 320))
    positions = [(x, y) for y in (48, 112, 176, 240) for x in (48, 112, 176, 240)]
    half = stamp.shape[0] // 2
    for x, y in positions:
        image[y-half:y+half+1, x-half:x+half+1] += flux*stamp
    bundle = {"sci": image, "validity_mask": np.ones(image.shape, bool)}
    # Capture library warnings as experiment metadata rather than thousands of
    # repeated terminal lines. Deprecations and no-detection warnings stay visible.
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        detections = detect_with_morphology(bundle)
        scores = classify(model, detections, filter_name)
    if warning_counts is not None:
        for warning in captured:
            key = f"{warning.category.__name__}: {warning.message}"
            warning_counts[key] = warning_counts.get(key, 0) + 1
    xy = np.asarray([(d["x"], d["y"]) for d in detections])
    rows = []
    used: set[int] = set()
    for index, (x, y) in enumerate(positions):
        row = {"source_id": f"{filter_name}-{kind}-{flux}-{radius}-{batch}-{index}",
               "paired_trial_id": f"{filter_name}-{flux}-{radius}-{batch}-{index}",
               "sample_kind": "synthetic", "generator_id": GENERATOR_ID,
               "kernel_kind": kind, "filter": filter_name, "injected_flux_noise_units": flux,
               "half_light_radius_px": radius, "background_seed": seed, "batch": batch,
               "recovered": False, "artifact_score": None, "rejected": None,
               "fwhm_pixels": None, "match_distance_px": None}
        if len(detections):
            distances = np.hypot(xy[:, 0]-x, xy[:, 1]-y)
            nearest = int(np.argmin(distances))
            if distances[nearest] <= 2.5:
                if nearest in used:
                    raise ValueError("a single detection matched multiple injections")
                used.add(nearest)
                score = scores[nearest]
                row.update(recovered=True, artifact_score=score,
                           rejected=None if score is None else score >= 0.5,
                           fwhm_pixels=detections[nearest]["fwhm_pixels"],
                           match_distance_px=float(distances[nearest]))
        rows.append(row)
    return rows


def run_experiment(psf_directory: Path, model_path: Path, *, batches: int = 2,
                   seed: int = 913, fluxes=DEFAULT_FLUXES, radii=DEFAULT_RADII) -> dict[str, Any]:
    if not 1 <= batches <= 10:
        raise ValueError("bounded experiment permits 1 to 10 batches per cell")
    model_raw = model_path.read_bytes()
    model = json.loads(model_raw)
    records, summary, provenance = [], [], []
    warning_counts: dict[str, int] = {}
    for filter_index, filter_name in enumerate(("F277W", "F356W", "F444W")):
        official, meta = load_verified_psf(psf_directory / f"{filter_name.lower()}a_v5.0_mpsf.fits", filter_name)
        provenance.append(meta)
        analytic = gaussian_kernel(psf_fwhm_pixels(filter_name) / np.sqrt(8*np.log(2)))
        for radius_index, radius in enumerate(radii):
            for flux_index, flux in enumerate(fluxes):
                for kind, psf in (("jades_dr5_modeled", official), ("analytic_gaussian", analytic)):
                    rows = []
                    stamp = independent_stamp(psf, radius)
                    for batch in range(batches):
                        paired_seed = seed + filter_index*10000 + radius_index*1000 + flux_index*100 + batch
                        rows.extend(run_cell(stamp, filter_name, model, flux=flux, radius=radius,
                                             seed=paired_seed, batch=batch, kind=kind,
                                             warning_counts=warning_counts))
                    records.extend(rows)
                    summary.append({"filter": filter_name, "kernel_kind": kind,
                                    "flux_noise_units": flux, "half_light_radius_px": radius,
                                    **injection_metrics(rows)})
    return {"experiment": "external modeled PSF stress diagnostic", "seed": seed,
            "model_sha256": hashlib.sha256(model_raw).hexdigest(), "threshold": 0.5,
            "generator_id": GENERATOR_ID, "psf_provenance": provenance,
            "software_versions": {name: version(name) for name in ("numpy", "scipy", "astropy", "photutils")},
            "code_sha256": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                            for name in ("external_psf_stress.py", "artifact_characterization.py", "artifact_classifier.py", "validation_metrics.py")},
            "pipeline_warning_counts": warning_counts,
            "batches_per_cell": batches, "n_trials": len(records),
            "independent_real_sky_validation": False,
            "limits": ["All injected sources and backgrounds are synthetic; PSFs are modeled JADES shapes.",
                       "Analytic Gaussian is a comparator, not the repo's empirical-PSF/Sersic training generator.",
                       "Training PSF provenance is incomplete; independence from training PSF cannot be certified.",
                       "No detector artifacts, correlated drizzle noise, source Poisson noise, crowding or sky coverage holes.",
                       "Classifier assumes 0.063 arcsec long-wave pixels; kernels are resampled to that exact scale.",
                       "Flux is total normalized-kernel flux in per-pixel background-noise units, not AB magnitude or measured SNR.",
                       "Wilson intervals are conditional diagnostics; 16 same-image trials share an estimated background threshold.",
                       "No AUC: the simulated truth contains only real-source equivalents.",
                       "All injection centers are integer pixels; subpixel phase sensitivity is not measured.",
                       "Crop wings and Gaussian intrinsic profiles differ from actual extended galaxies."],
            "summaries": summary, "trials": records}


def render_report(result: dict[str, Any]) -> str:
    lines = ["# External modeled-PSF stress experiment", "",
             "This exercises the actual segmentation/morphology and frozen classifier",
             "on independently rendered Gaussian-intrinsic sources in synthetic Gaussian noise.",
             "It is **not independent real-sky validation** and cannot establish survey completeness.", "",
             f"Trials: {result['n_trials']}; model SHA-256: `{result['model_sha256']}`.", "",
             "Flux is in total per-pixel background-noise units. Both kernels receive the",
             "same noise and positions within each cell. Brackets: conditional 95% Wilson interval.", "",
             "## Exploratory sensitivity findings", ""]
    for filter_name in ("F277W", "F356W", "F444W"):
        for flux in (60.0, 120.0):
            cells = [r for r in result["summaries"] if r["filter"] == filter_name
                     and r["half_light_radius_px"] == 0 and r["flux_noise_units"] == flux]
            if len(cells) == 2:
                modeled, gaussian = cells
                mc, gc = modeled["counts"], gaussian["counts"]
                if mc["detected"] != gc["detected"] or mc["accepted"] != gc["accepted"]:
                    lines.append(f"- {filter_name}, unresolved, flux {flux:g}: modeled kernel detects "
                                 f"{mc['detected']}/{mc['injected']} and accepts {mc['accepted']}; "
                                 f"Gaussian detects {gc['detected']}/{gc['injected']} and accepts {gc['accepted']}.")
    lines += ["", "These differences show kernel sensitivity in this synthetic setup. They are",
              "not measured astrophysical error rates or evidence that one kernel represents all sky sources.", "",
             "## Full grid", "",
             "| Filter | Radius px | Flux | Kernel | Detected/injected | Rejected/classified | Accepted/injected |",
             "| --- | ---: | ---: | --- | --- | --- | --- |"]
    for row in result["summaries"]:
        def rate(key):
            r = row[key]
            if r["estimate"] is None:
                return "not estimable"
            return f"{r['successes']}/{r['trials']} ({100*r['estimate']:.1f}%; {100*r['lower']:.1f}–{100*r['upper']:.1f}%)"
        lines.append(f"| {row['filter']} | {row['half_light_radius_px']} | {row['flux_noise_units']} | "
                     f"{row['kernel_kind']} | {rate('detection_completeness')} | "
                     f"{rate('false_rejection_among_classified')} | {rate('end_to_end_completeness')} |")
    lines += ["", "## PSF receipts and resampling", ""]
    for p in result["psf_provenance"]:
        lines.append(f"- {p['filter']}: `{p['sha256']}`; {p['input_scale_arcsec']:.9f} → "
                     f"{p['target_scale_arcsec']:.3f} arcsec/pixel; crop retains {100*p['retained_fraction']:.2f}% "
                     f"of template flux before normalization. [Source]({p['requested_url']}).")
    lines += ["", "## Software and captured warnings", "",
              ", ".join(f"{k}={v}" for k, v in result["software_versions"].items()), ""]
    lines += [f"- {count} × {message}" for message, count in result["pipeline_warning_counts"].items()]
    lines += ["", "## Limits", ""] + ["- " + x for x in result["limits"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--psf-directory", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=Path("research_output/artifact_classifier.json"))
    parser.add_argument("--batches", type=int, default=2)
    parser.add_argument("--seed", type=int, default=913)
    parser.add_argument("--output", type=Path, default=Path("research_output/external_psf_stress.json"))
    parser.add_argument("--report", type=Path, default=Path("research_output/EXTERNAL_PSF_STRESS.md"))
    args = parser.parse_args()
    result = run_experiment(args.psf_directory, args.model, batches=args.batches, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    args.report.write_text(render_report(result))
    print(f"Wrote {result['n_trials']} synthetic trials; independent real-sky validation: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
