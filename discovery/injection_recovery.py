"""Injection-recovery test: what does the artifact cut cost the science sample?

A ROC AUC measured on the repeat-exposure truth set does not answer the question
that matters. That truth set's "real" class is dominated by bright, resolved,
comfortably detected galaxies. The sources a high-redshift search is actually
looking for are faint and compact - which is precisely what a cosmic ray looks
like. A classifier can post an excellent AUC while quietly deleting exactly the
population you care about, and cross-filter transfer does not test for this
either.

So this module measures it directly. Synthetic sources spanning brightness, size
and surface brightness are injected into a real image, the complete detection ->
morphology -> classification chain is run over the result, and recovery is
measured before and after the cut. Because the injected truth is known, the
false-rejection rate can be reported as a function of magnitude and size, and
separately for sources placed next to bright neighbours - the regime where the
background annulus already failed once.

The empirical PSF is built from bright compact sources in the image itself, so
the injected sources carry the same optics, resampling and noise as real ones.

Run:
    python discovery/injection_recovery.py --filter F444W --image <path_i2d.fits>
    python discovery/injection_recovery.py --auto
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from astropy.convolution import convolve_fft
from astropy.modeling.models import Sersic2D
from astropy.stats import sigma_clipped_stats
from scipy.ndimage import shift as subpixel_shift

from discovery.artifact_characterization import detect_with_morphology
from discovery.artifact_classifier import build_features, classify
from tools.jwst.fits_loader import _load_fits_bundle_from_path
from tools.jwst.photometry import extract_photometry

RESEARCH_DIR = Path("research_output")
DEFAULT_MODEL = RESEARCH_DIR / "artifact_classifier.json"
DEFAULT_OUTPUT = RESEARCH_DIR / "injection_recovery.json"
DEFAULT_REPORT = RESEARCH_DIR / "INJECTION_RECOVERY.md"

PSF_STAMP_HALF = 12
MATCH_RADIUS_PIXELS = 2.5
REJECT_THRESHOLD = 0.5

# Injected half-light radii in pixels. 0 means a pure point source, which is the
# regime an unresolved high-redshift galaxy occupies.
INJECTED_RADII_PIXELS = [0.0, 0.75, 1.5, 3.0]

# Target signal-to-noise values for the injected grid, spanning the detection
# limit up to comfortably bright.
INJECTED_TARGET_SNR = [5.0, 8.0, 12.0, 20.0, 40.0, 100.0]

APERTURE_RADIUS = 3.0


def build_empirical_psf(
    image: np.ndarray,
    sources: List[Dict[str, Any]],
    *,
    max_stars: int = 40,
) -> Optional[np.ndarray]:
    """Median-stack bright compact sources into a normalized empirical PSF.

    Using the image's own PSF means injected sources carry the same optics and
    resampling kernel as the real ones, which a Gaussian approximation would not.
    """
    candidates = [
        s for s in sources
        if s.get("fwhm_pixels") and s.get("ellipticity") is not None
        and s["fwhm_pixels"] < 3.0 and s["ellipticity"] < 0.25
        and (s.get("area_pixels") or 0) > 8
    ]
    candidates.sort(key=lambda s: -(s.get("peak_value") or 0.0))

    stamps: List[np.ndarray] = []
    half = PSF_STAMP_HALF
    for source in candidates[: max_stars * 3]:
        x, y = source["x"], source["y"]
        xi, yi = int(round(x)), int(round(y))
        if xi < half or yi < half or xi >= image.shape[1] - half or yi >= image.shape[0] - half:
            continue
        stamp = image[yi - half: yi + half + 1, xi - half: xi + half + 1].astype(float)
        if not np.isfinite(stamp).all():
            continue
        stamp = subpixel_shift(stamp, (yi - y, xi - x), order=3, mode="nearest")
        total = float(np.sum(stamp))
        if total <= 0:
            continue
        stamps.append(stamp / total)
        if len(stamps) >= max_stars:
            break

    if len(stamps) < 5:
        return None
    psf = np.median(np.asarray(stamps), axis=0)
    psf[psf < 0] = 0.0
    return psf / float(np.sum(psf))


def render_source(psf: np.ndarray, half_light_radius: float, size: int = 41) -> np.ndarray:
    """Render one injected source: a point source, or a Sersic disc, PSF-convolved."""
    if half_light_radius <= 0:
        model = np.zeros((size, size))
        model[size // 2, size // 2] = 1.0
    else:
        y, x = np.mgrid[:size, :size]
        sersic = Sersic2D(
            amplitude=1.0,
            r_eff=half_light_radius,
            n=1.0,
            x_0=size // 2,
            y_0=size // 2,
            ellip=0.0,
            theta=0.0,
        )
        model = np.asarray(sersic(x, y), dtype=float)

    convolved = convolve_fft(model, psf, normalize_kernel=True, allow_huge=True)
    total = float(np.sum(convolved))
    return convolved / total if total > 0 else convolved


def _add_stamp(image: np.ndarray, stamp: np.ndarray, x: float, y: float) -> None:
    """Add a rendered stamp into the image in place, clipped at the edges."""
    half = stamp.shape[0] // 2
    xi, yi = int(round(x)), int(round(y))
    y0, y1 = max(yi - half, 0), min(yi + half + 1, image.shape[0])
    x0, x1 = max(xi - half, 0), min(xi + half + 1, image.shape[1])
    sy0, sx0 = y0 - (yi - half), x0 - (xi - half)
    image[y0:y1, x0:x1] += stamp[sy0: sy0 + (y1 - y0), sx0: sx0 + (x1 - x0)]


def aperture_noise(bundle: Dict[str, Any]) -> float:
    """Flux uncertainty in one r=3 px aperture, from the ERR extension.

    The measured SNR is set by the pipeline's own error array, not by the pixel
    scatter of the science image, so calibrating injected fluxes against the
    image RMS badly underestimates the flux needed to reach a given SNR.
    """
    n_pixels = int(np.sum(_aperture_mask(2 * PSF_STAMP_HALF + 1)))
    err = bundle.get("err")
    mask = np.asarray(bundle["validity_mask"], dtype=bool)
    if err is not None:
        err = np.asarray(err, dtype=float)
        if err.shape == mask.shape:
            typical = float(np.nanmedian(err[mask & np.isfinite(err)]))
            if np.isfinite(typical) and typical > 0:
                return typical * float(np.sqrt(n_pixels))
    _, _, std = sigma_clipped_stats(np.asarray(bundle["sci"], float)[mask], sigma=3.0)
    return float(std) * float(np.sqrt(n_pixels))


def _aperture_mask(size: int) -> np.ndarray:
    """Boolean r=3 px aperture mask centred in a size x size stamp."""
    half = size // 2
    yy, xx = np.mgrid[:size, :size]
    return (xx - half) ** 2 + (yy - half) ** 2 <= APERTURE_RADIUS ** 2


def calibrate_flux_scale(
    bundle: Dict[str, Any],
    stamp: np.ndarray,
    positions: Sequence[Tuple[float, float]],
    aperture_sigma: float,
) -> Optional[float]:
    """Measure how much aperture SNR one unit of injected flux actually buys.

    Predicting SNR from the error array alone gets the answer wrong by a large
    factor, because `extract_photometry` adds a background-scatter term and the
    drizzled noise is correlated. Rather than model that, inject a trial source
    at known flux, measure it through the real photometry code, and read the
    slope off. Self-correcting, and it makes the size axis honest: an extended
    source is automatically given the extra flux it needs.
    """
    enclosed = float(np.sum(stamp[_aperture_mask(stamp.shape[0])]))
    if enclosed <= 0:
        return None
    trial_flux = 50.0 * aperture_sigma / enclosed

    base = np.asarray(bundle["sci"], dtype=float)
    slopes: List[float] = []
    for x, y in positions:
        image = base.copy()
        _add_stamp(image, stamp * trial_flux, x, y)
        probe = dict(bundle)
        probe["sci"] = image
        measurement = extract_photometry(
            image_data=probe, x=x, y=y,
            aperture_radius=APERTURE_RADIUS,
            background_annulus_inner_radius=6.0,
            background_annulus_outer_radius=10.0,
        )
        snr = measurement.get("snr")
        if snr is not None and np.isfinite(snr) and snr > 0:
            slopes.append(float(snr) / trial_flux)

    if not slopes:
        return None
    return float(np.median(slopes))


def flux_for_target_snr(target_snr: float, snr_per_unit_flux: float) -> float:
    """Total flux giving the requested measured aperture SNR."""
    if snr_per_unit_flux <= 0:
        return 0.0
    return float(target_snr / snr_per_unit_flux)


def _bright_neighbour_positions(
    sources: List[Dict[str, Any]],
    count: int,
    rng: np.random.Generator,
    shape: Tuple[int, int],
) -> List[Tuple[float, float]]:
    """Positions 8-20 px from a bright source, to probe the crowded regime."""
    bright = sorted(
        [s for s in sources if s.get("peak_value")],
        key=lambda s: -s["peak_value"],
    )[:200]
    positions: List[Tuple[float, float]] = []
    attempts = 0
    while len(positions) < count and attempts < count * 40 and bright:
        attempts += 1
        anchor = bright[rng.integers(len(bright))]
        angle = rng.uniform(0, 2 * np.pi)
        radius = rng.uniform(8.0, 20.0)
        x = anchor["x"] + radius * np.cos(angle)
        y = anchor["y"] + radius * np.sin(angle)
        if 40 < x < shape[1] - 40 and 40 < y < shape[0] - 40:
            positions.append((float(x), float(y)))
    return positions


def run_injection(
    bundle: Dict[str, Any],
    filter_name: str,
    model: Dict[str, Any],
    *,
    batches: int = 6,
    per_batch: int = 120,
    crowded_fraction: float = 0.3,
    seed: int = 0,
) -> List[Dict[str, Any]]:
    """Inject synthetic sources in batches and record what survives each stage."""
    rng = np.random.default_rng(seed)
    base_image = np.asarray(bundle["sci"], dtype=float)
    valid_mask = np.asarray(bundle["validity_mask"], dtype=bool)

    baseline_sources = detect_with_morphology(bundle)
    psf = build_empirical_psf(base_image, baseline_sources)
    if psf is None:
        raise ValueError("Could not build an empirical PSF from this image")

    aperture_sigma = aperture_noise(bundle)
    stamps = {r: render_source(psf, r) for r in INJECTED_RADII_PIXELS}

    # Positions of pre-existing sources. An injection landing on one of them is
    # blended, not undetected, so isolated placements avoid them and the crowded
    # sample targets them deliberately.
    existing = (
        np.asarray([[s["x"], s["y"]] for s in baseline_sources])
        if baseline_sources
        else np.empty((0, 2))
    )

    def _is_clear(x: float, y: float, radius: float = 7.0) -> bool:
        if len(existing) == 0:
            return True
        return bool(np.min(np.hypot(existing[:, 0] - x, existing[:, 1] - y)) > radius)

    # Calibrate the flux/SNR relation once per source size, on blank sky.
    calibration_positions: List[Tuple[float, float]] = []
    attempts = 0
    while len(calibration_positions) < 8 and attempts < 2000:
        attempts += 1
        x = float(rng.uniform(60, base_image.shape[1] - 60))
        y = float(rng.uniform(60, base_image.shape[0] - 60))
        if _is_clear(x, y, radius=20.0) and valid_mask[int(round(y)), int(round(x))]:
            calibration_positions.append((x, y))

    snr_per_flux: Dict[float, float] = {}
    for radius, stamp in stamps.items():
        slope = calibrate_flux_scale(bundle, stamp, calibration_positions, aperture_sigma)
        if slope is None:
            raise ValueError(f"Flux calibration failed for r_eff={radius}")
        snr_per_flux[radius] = slope

    results: List[Dict[str, Any]] = []
    for batch in range(batches):
        image = base_image.copy()
        n_crowded = int(per_batch * crowded_fraction)
        crowded = _bright_neighbour_positions(
            baseline_sources, n_crowded, rng, base_image.shape
        )
        n_random = per_batch - len(crowded)
        random_positions: List[Tuple[float, float]] = []
        attempts = 0
        while len(random_positions) < n_random and attempts < n_random * 60:
            attempts += 1
            x = float(rng.uniform(40, base_image.shape[1] - 40))
            y = float(rng.uniform(40, base_image.shape[0] - 40))
            if _is_clear(x, y):
                random_positions.append((x, y))
        placements = [(p, False) for p in random_positions] + [(p, True) for p in crowded]

        injected: List[Dict[str, Any]] = []
        for (x, y), is_crowded in placements:
            if not valid_mask[int(round(y)), int(round(x))]:
                continue
            radius = float(INJECTED_RADII_PIXELS[rng.integers(len(INJECTED_RADII_PIXELS))])
            target_snr = float(INJECTED_TARGET_SNR[rng.integers(len(INJECTED_TARGET_SNR))])
            stamp = stamps[radius]
            flux = flux_for_target_snr(target_snr, snr_per_flux[radius])
            _add_stamp(image, stamp * flux, x, y)
            injected.append(
                {
                    "x": x,
                    "y": y,
                    "half_light_radius_px": radius,
                    "target_snr": target_snr,
                    "injected_flux": flux,
                    "near_bright_neighbour": is_crowded,
                }
            )

        injected_bundle = dict(bundle)
        injected_bundle["sci"] = image
        detections = detect_with_morphology(injected_bundle)
        if detections:
            scores = classify(model, detections, filter_name)
        else:
            scores = []

        detection_xy = np.asarray([[d["x"], d["y"]] for d in detections]) if detections else None
        for record in injected:
            outcome = {**record, "batch": batch, "recovered": False,
                       "measured_snr": None, "artifact_score": None,
                       "rejected": None, "fwhm_pixels": None, "sharpness": None}
            if detection_xy is not None:
                distance = np.hypot(
                    detection_xy[:, 0] - record["x"], detection_xy[:, 1] - record["y"]
                )
                nearest = int(np.argmin(distance))
                if distance[nearest] <= MATCH_RADIUS_PIXELS:
                    detection = detections[nearest]
                    photometry = extract_photometry(
                        image_data=injected_bundle,
                        x=detection["x"],
                        y=detection["y"],
                        aperture_radius=APERTURE_RADIUS,
                        background_annulus_inner_radius=6.0,
                        background_annulus_outer_radius=10.0,
                    )
                    score = scores[nearest]
                    outcome.update(
                        {
                            "recovered": True,
                            "measured_snr": photometry.get("snr"),
                            "artifact_score": score,
                            "rejected": (score is not None and score >= REJECT_THRESHOLD),
                            "fwhm_pixels": detection.get("fwhm_pixels"),
                            "sharpness": detection.get("sharpness"),
                        }
                    )
            results.append(outcome)
    return results


def _rate(subset: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Recovery and false-rejection rates for one slice of the injected grid."""
    total = len(subset)
    recovered = [r for r in subset if r["recovered"]]
    rejected = [r for r in recovered if r["rejected"]]
    return {
        "n_injected": total,
        "n_recovered": len(recovered),
        "detection_completeness": float(len(recovered) / total) if total else None,
        "n_falsely_rejected": len(rejected),
        # The headline: of the real sources the detector found, what fraction
        # does the artifact cut throw away?
        "false_rejection_rate": float(len(rejected) / len(recovered)) if recovered else None,
        "net_completeness": float((len(recovered) - len(rejected)) / total) if total else None,
    }


def summarize(results: List[Dict[str, Any]], filter_name: str) -> Dict[str, Any]:
    """Aggregate injection outcomes overall and sliced by size, SNR and crowding."""
    by_snr = {}
    for snr in INJECTED_TARGET_SNR:
        subset = [r for r in results if r["target_snr"] == snr]
        if subset:
            by_snr[str(snr)] = _rate(subset)

    by_radius = {}
    for radius in INJECTED_RADII_PIXELS:
        subset = [r for r in results if r["half_light_radius_px"] == radius]
        if subset:
            by_radius[str(radius)] = _rate(subset)

    point_faint = [
        r for r in results
        if r["half_light_radius_px"] == 0.0 and r["target_snr"] <= 8.0
    ]

    measured = [
        (r["target_snr"], r["measured_snr"])
        for r in results
        if r["recovered"] and r["measured_snr"] is not None
    ]
    calibration = {}
    for snr in INJECTED_TARGET_SNR:
        values = [m for t, m in measured if t == snr]
        if values:
            calibration[str(snr)] = {
                "n": len(values),
                "median_measured_snr": float(np.median(values)),
            }

    return {
        "filter": filter_name,
        "overall": _rate(results),
        "snr_calibration": calibration,
        "by_target_snr": by_snr,
        "by_half_light_radius_px": by_radius,
        "near_bright_neighbour": _rate([r for r in results if r["near_bright_neighbour"]]),
        "isolated": _rate([r for r in results if not r["near_bright_neighbour"]]),
        # The population a high-redshift search lives on, called out explicitly.
        "faint_point_sources": _rate(point_faint),
    }


def render_report(summaries: List[Dict[str, Any]]) -> str:
    """Render the injection-recovery report."""
    lines = [
        "# Injection-Recovery: what the artifact cut costs",
        "",
        "Synthetic sources spanning brightness, size and surface brightness were",
        "injected into real JWST exposures and put through the complete detection,",
        "morphology and classification chain. Because the truth is known, this",
        "measures directly what a ROC AUC cannot: how many real galaxies the",
        "artifact cut deletes, and which ones.",
        "",
        "`false rejection` is the fraction of **detected, genuinely real** injected",
        f"sources that the classifier flags as artifacts at threshold {REJECT_THRESHOLD}.",
        "",
    ]
    for summary in summaries:
        overall = summary["overall"]
        lines += [
            f"## {summary['filter']}",
            "",
            f"- Injected: **{overall['n_injected']}**",
            f"- Detected: **{overall['n_recovered']}** "
            f"({100 * overall['detection_completeness']:.1f}%)",
            f"- Falsely rejected by the classifier: **{overall['n_falsely_rejected']}** "
            f"({100 * overall['false_rejection_rate']:.1f}% of detected)",
            "",
            "| injected S/N | detected | false rejection | net completeness |",
            "| ---: | ---: | ---: | ---: |",
        ]
        for snr, row in summary["by_target_snr"].items():
            lines.append(
                f"| {float(snr):.0f} | {100 * row['detection_completeness']:.0f}% | "
                f"{100 * row['false_rejection_rate']:.1f}% | "
                f"{100 * row['net_completeness']:.0f}% |"
                if row["false_rejection_rate"] is not None
                else f"| {float(snr):.0f} | {100 * row['detection_completeness']:.0f}% | n/a | n/a |"
            )

        lines += [
            "",
            "| half-light radius (px) | detected | false rejection | net completeness |",
            "| ---: | ---: | ---: | ---: |",
        ]
        for radius, row in summary["by_half_light_radius_px"].items():
            lines.append(
                f"| {float(radius):.2f} | {100 * row['detection_completeness']:.0f}% | "
                f"{100 * row['false_rejection_rate']:.1f}% | "
                f"{100 * row['net_completeness']:.0f}% |"
                if row["false_rejection_rate"] is not None
                else f"| {float(radius):.2f} | {100 * row['detection_completeness']:.0f}% | n/a | n/a |"
            )

        crowded = summary["near_bright_neighbour"]
        isolated = summary["isolated"]
        faint_point = summary["faint_point_sources"]
        if summary.get("snr_calibration"):
            lines += [
                "",
                "Calibration check - injected target versus median measured aperture S/N:",
                "",
                "| target S/N | median measured S/N | n |",
                "| ---: | ---: | ---: |",
            ]
            for target, row in summary["snr_calibration"].items():
                lines.append(
                    f"| {float(target):.0f} | {row['median_measured_snr']:.1f} | {row['n']} |"
                )

        lines += [
            "",
            "| population | detected | false rejection |",
            "| --- | ---: | ---: |",
        ]
        for label, row in (
            ("isolated", isolated),
            ("within 8-20 px of a bright source", crowded),
            ("**unresolved and faint (S/N <= 8, r_e = 0)**", faint_point),
        ):
            if row["false_rejection_rate"] is None:
                continue
            lines.append(
                f"| {label} | {100 * row['detection_completeness']:.0f}% | "
                f"{100 * row['false_rejection_rate']:.1f}% |"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    """Run injection-recovery over the requested images."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, action="append", default=None)
    parser.add_argument("--filter", action="append", default=None)
    parser.add_argument("--auto", action="store_true")
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--batches", type=int, default=6)
    parser.add_argument("--per-batch", type=int, default=120)
    args = parser.parse_args()

    if not args.model.exists():
        print(f"No model at {args.model}. Run artifact_classifier.py --train first.")
        return 1
    model = json.loads(args.model.read_text(encoding="utf-8"))

    targets: List[Tuple[str, Path]] = []
    if args.image and args.filter and len(args.image) == len(args.filter):
        targets = list(zip(args.filter, args.image))
    elif args.auto:
        seen: Dict[str, Path] = {}
        for path in sorted(args.data_root.rglob("*_i2d.fits")):
            bundle = _load_fits_bundle_from_path(str(path))
            filter_name = str(
                (bundle.get("primary_header") or {}).get("FILTER") or ""
            ).upper()
            if filter_name and filter_name not in seen:
                seen[filter_name] = path
        targets = sorted(seen.items())

    if not targets:
        print("No target images. Use --auto or matching --filter/--image pairs.")
        return 1

    summaries: List[Dict[str, Any]] = []
    everything: Dict[str, List[Dict[str, Any]]] = {}
    for filter_name, path in targets:
        print(f"Injecting into {filter_name}: {path.name}")
        bundle = _load_fits_bundle_from_path(str(path))
        results = run_injection(
            bundle, filter_name, model,
            batches=args.batches, per_batch=args.per_batch,
        )
        summary = summarize(results, filter_name)
        summaries.append(summary)
        everything[filter_name] = results
        overall = summary["overall"]
        faint = summary["faint_point_sources"]
        print(
            f"  injected={overall['n_injected']} detected={overall['n_recovered']} "
            f"false-rejection={100 * overall['false_rejection_rate']:.1f}%"
        )
        if faint["false_rejection_rate"] is not None:
            print(
                f"  faint unresolved (S/N<=8, r_e=0): "
                f"false-rejection={100 * faint['false_rejection_rate']:.1f}% "
                f"of {faint['n_recovered']} detected"
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"summaries": summaries, "injections": everything}, indent=2),
        encoding="utf-8",
    )
    args.report.write_text(render_report(summaries), encoding="utf-8")
    print(f"\nWritten to {args.output} and {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
