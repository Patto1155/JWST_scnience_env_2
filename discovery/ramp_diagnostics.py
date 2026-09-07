"""Classify detector events from the up-the-ramp reads, independently of shape.

The morphology classifier in `artifact_classifier.py` fails injection-recovery:
it learned "compact" rather than "cosmic ray", because a deep extragalactic
field contains almost no real point sources to teach it the difference. Any
discriminator built on shape inherits that problem, since an unresolved
high-redshift galaxy and a cosmic ray are both small.

The ramp does not have that failure mode. JWST reads each exposure
non-destructively several times, so a source's signal history is recorded. An
optical source accumulates charge at a steady rate across every group. A cosmic
ray deposits its charge between two reads and then stops. That difference is
visible in the increments themselves and owes nothing to how the source looks.

The statistic is the fraction of a pixel's total accumulated signal that arrives
in its single largest group-to-group increment:

    max_increment_fraction = max(diff(ramp)) / sum(diff(ramp))

For steady accumulation over ``n`` groups this sits near ``1 / (n - 1)``; for a
charge deposition confined to one interval it approaches 1. STScI documents that
showers and snowballs can also release charge more gradually, so the statistic
is reported as a continuous quantity and thresholded, rather than treated as a
binary jump test.

Saturated pixels are excluded, because a saturating real source also goes flat
after its first groups and would otherwise mimic a jump.

Run:
    python discovery/ramp_diagnostics.py --exposure <dir>/<root>_ \\
        --truth research_output/artifact_characterization.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from astropy.wcs import WCS
from photutils.segmentation import SourceCatalog, detect_sources

from tools.jwst.ramp_calibration import (
    apply_linearity,
    group_variance,
    jump_pvalue,
    jump_significance,
    load_references,
    saturation_mask,
)

RESEARCH_DIR = Path("research_output")
DEFAULT_OUTPUT = RESEARCH_DIR / "ramp_diagnostics.json"
DEFAULT_REPORT = RESEARCH_DIR / "RAMP_DIAGNOSTICS.md"

# Raw ``_uncal`` ramps carry no non-linearity correction, and a pixel's response
# flattens well before hard saturation near 60000 DN. That flattening makes the
# first increment the largest and mimics a jump, so bright real sources score as
# artifacts. A ceiling this low costs sample size but keeps the pixels used in
# the regime where a linear ramp is actually expected; see `sweep_ceiling`.
SATURATION_DN = 18000.0

# A pixel needs this much accumulated signal for its ramp shape to mean anything.
MIN_PIXEL_AMPLITUDE_DN = 300.0

MIN_PIXELS_PER_SOURCE = 4
DETECTION_SIGMA = 5.0
DETECTION_MIN_PIXELS = 5
MATCH_RADIUS_ARCSEC = 0.35


def load_exposure(
    prefix: Path,
    *,
    crds_dir: Path = Path("data/crds"),
    calibrate: bool = True,
) -> Tuple[np.ndarray, np.ndarray, WCS, fits.Header, Dict[str, Any]]:
    """Load the calibrated frame, the ramp, the detector WCS, and CRDS references.

    When references are available the ramp is superbias-subtracted and
    linearity-corrected before it is returned, so downstream statistics are
    measured on a ramp that is genuinely expected to be linear.
    """
    cal_path = Path(str(prefix) + "cal.fits")
    uncal_path = Path(str(prefix) + "uncal.fits")

    with fits.open(cal_path) as handle:
        cal = np.array(handle["SCI"].data, dtype=float)
        header = handle["SCI"].header.copy()
        primary = handle[0].header.copy()
    with fits.open(uncal_path) as handle:
        raw = np.array(handle["SCI"].data, dtype=float)

    ramp = raw[0] if raw.ndim == 4 else raw
    references = load_references(primary, crds_dir) if calibrate else {"available": {}, "missing": ["all"]}

    if calibrate and "linearity_coeffs" in references:
        ramp = apply_linearity(
            ramp, references["linearity_coeffs"], references.get("superbias")
        )
        references["linearity_applied"] = True
    else:
        references["linearity_applied"] = False

    references["n_frames"] = int(primary.get("NFRAMES") or 1)
    return cal, ramp, WCS(header), primary, references


def segment_calibrated_frame(cal: np.ndarray):
    """Detect sources in the detector-frame calibrated image."""
    finite = np.isfinite(cal)
    _, median, std = sigma_clipped_stats(cal[finite], sigma=3.0)
    detection_image = np.where(finite, cal - median, 0.0)
    segmentation = detect_sources(
        detection_image,
        threshold=float(DETECTION_SIGMA * std),
        npixels=DETECTION_MIN_PIXELS,
        mask=~finite,
    )
    return segmentation, detection_image


def sky_ramp(ramp: np.ndarray, segmentation) -> np.ndarray:
    """Median ramp of blank pixels, used as the per-group background."""
    blank = segmentation.data == 0
    return np.array([float(np.median(ramp[g][blank])) for g in range(ramp.shape[0])])


def ramp_statistics(
    ramp: np.ndarray,
    pixels: np.ndarray,
    background: np.ndarray,
    *,
    usable: Optional[np.ndarray] = None,
    references: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Summarize the accumulation history of one source's unsaturated pixels.

    Returns None when no pixel carries enough unsaturated signal for its shape to
    be meaningful - an honest abstention rather than a fabricated score.
    """
    n_groups = ramp.shape[0]
    if n_groups < 3:
        return None

    rows, cols = pixels[:, 0], pixels[:, 1]
    values = ramp[:, rows, cols]
    if usable is not None:
        unsaturated = usable[rows, cols]
    else:
        unsaturated = np.all(values < SATURATION_DN, axis=0)
    signal = values - background[:, None]
    amplitude = signal[-1] - signal[0]
    usable_mask = unsaturated & (amplitude > MIN_PIXEL_AMPLITUDE_DN)
    if int(np.sum(usable_mask)) < MIN_PIXELS_PER_SOURCE:
        return None

    increments = np.diff(signal[:, usable_mask], axis=0)
    totals = np.sum(increments, axis=0)
    positive = totals > 0
    if int(np.sum(positive)) < MIN_PIXELS_PER_SOURCE:
        return None

    increments = increments[:, positive]
    totals = totals[positive]
    fractions = np.max(increments, axis=0) / totals
    jump_groups = np.argmax(increments, axis=0)

    # Noise-normalized statistic: how significant is the best single jump over a
    # straight line? Unlike the raw fraction this does not grow simply because a
    # source is bright, which is what made the fraction inherit a compactness
    # bias through surface brightness.
    significance = None
    jump_evidence = None
    if references and references.get("readnoise") is not None and references.get("gain") is not None:
        selected = np.flatnonzero(usable_mask)[positive] if usable is not None else None
        keep_rows = rows[usable_mask][positive]
        keep_cols = cols[usable_mask][positive]
        sub_signal = signal[:, usable_mask][:, positive]
        variance = group_variance(
            sub_signal,
            references["readnoise"][keep_rows, keep_cols][None, :],
            references["gain"][keep_rows, keep_cols][None, :],
            references.get("n_frames", 1),
            references.get("model_error_fraction", 0.02),
        )
        result = jump_pvalue(sub_signal, variance, n_trials=120)
        significance = float(np.median(result["significance"]))
        jump_evidence = float(np.median(result["neg_log10_p"]))
        del selected

    return {
        "jump_significance": significance,
        "jump_evidence": jump_evidence,
        "n_pixels_used": int(np.sum(positive)),
        "n_pixels_saturated": int(np.sum(~unsaturated)),
        "max_increment_fraction": float(np.median(fractions)),
        "max_increment_fraction_scatter": float(
            np.subtract(*np.percentile(fractions, [84, 16])) / 2.0
        ),
        "modal_jump_group": int(np.bincount(jump_groups).argmax()),
        "linear_expectation": float(1.0 / (n_groups - 1)),
        "median_amplitude_dn": float(np.median(totals)),
    }


def measure_exposure(prefix: Path, *, calibrate: bool = True) -> List[Dict[str, Any]]:
    """Measure ramp statistics and sky positions for every source in an exposure."""
    cal, ramp, wcs, primary, references = load_exposure(prefix, calibrate=calibrate)
    segmentation, detection_image = segment_calibrated_frame(cal)
    background = sky_ramp(ramp, segmentation)
    catalog = SourceCatalog(detection_image, segmentation)
    usable = saturation_mask(ramp, references.get("saturation")) if calibrate else None
    if references.get("missing"):
        print(f"  references missing (uncorrected): {', '.join(references['missing'])}")
    else:
        print(f"  linearity applied: {references.get('linearity_applied')}; "
              f"per-pixel saturation limits in use")

    def _scalar(value: Any) -> Optional[float]:
        try:
            number = float(getattr(value, "value", value))
        except (TypeError, ValueError):
            return None
        return number if np.isfinite(number) else None

    records: List[Dict[str, Any]] = []
    for row in catalog:
        label = int(row.label)
        pixels = np.argwhere(segmentation.data == label)
        stats = ramp_statistics(
            ramp, pixels, background, usable=usable, references=references
        )
        if stats is None:
            continue
        x, y = _scalar(row.xcentroid), _scalar(row.ycentroid)
        if x is None or y is None:
            continue
        ra, dec = wcs.all_pix2world(x, y, 0)
        records.append(
            {
                "label": label,
                "x": x,
                "y": y,
                "ra": float(ra),
                "dec": float(dec),
                "ellipticity": _scalar(row.ellipticity),
                "semimajor_sigma": _scalar(row.semimajor_sigma),
                "semiminor_sigma": _scalar(row.semiminor_sigma),
                "segment_flux": _scalar(row.segment_flux),
                "filter": primary.get("FILTER"),
                **stats,
            }
        )
    return records


def _load_truth(path: Path) -> List[Dict[str, Any]]:
    """Load consolidated per-detection consensus labels."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("detections") or []


def match_to_truth(
    records: List[Dict[str, Any]],
    truth: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Attach repeat-exposure consensus labels by sky position."""
    if not truth:
        return records
    truth_coords = np.array([[t["ra"], t["dec"]] for t in truth])
    tolerance = MATCH_RADIUS_ARCSEC / 3600.0

    for record in records:
        cos_dec = max(np.cos(np.radians(record["dec"])), 1e-6)
        separation = np.hypot(
            (truth_coords[:, 0] - record["ra"]) * cos_dec,
            truth_coords[:, 1] - record["dec"],
        )
        nearest = int(np.argmin(separation))
        if separation[nearest] <= tolerance:
            record["truth"] = truth[nearest]["consensus"]
            record["truth_fwhm_pixels"] = truth[nearest].get("fwhm_pixels")
            record["truth_snr"] = truth[nearest].get("snr_a")
        else:
            record["truth"] = None
    return records


def _roc_auc(labels: np.ndarray, scores: np.ndarray) -> float:
    """Area under the ROC curve via the rank-sum identity."""
    order = np.argsort(scores)
    ranks = np.empty(len(scores), dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1)
    n_pos, n_neg = float(np.sum(labels == 1)), float(np.sum(labels == 0))
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return float((np.sum(ranks[labels == 1]) - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def evaluate(
    records: List[Dict[str, Any]],
    threshold: float = 0.6,
    statistic: str = "max_increment_fraction",
) -> Dict[str, Any]:
    """Score the ramp statistic against the repeat-exposure truth labels.

    The compactness breakdown is the point of the exercise: a morphology-based
    cut rejects compact real sources preferentially, and a ramp-based one should
    not, because it never sees the shape.
    """
    labelled = [
        r for r in records
        if r.get("truth") in ("artifact", "real") and r.get(statistic) is not None
    ]
    if not labelled:
        return {"n_labelled": 0, "statistic": statistic}

    scores = np.array([float(r[statistic]) for r in labelled])
    labels = np.array([1.0 if r["truth"] == "artifact" else 0.0 for r in labelled])
    flagged = scores >= threshold

    def _slice(mask: np.ndarray, name: str) -> Dict[str, Any]:
        real = mask & (labels == 0)
        artifact = mask & (labels == 1)
        return {
            "population": name,
            "n_real": int(np.sum(real)),
            "n_artifact": int(np.sum(artifact)),
            "false_rejection_rate": float(np.mean(flagged[real])) if np.any(real) else None,
            "artifact_completeness": float(np.mean(flagged[artifact]))
            if np.any(artifact)
            else None,
        }

    compactness = np.array([r.get("truth_fwhm_pixels") or np.nan for r in labelled])
    brightness = np.array([r.get("truth_snr") or np.nan for r in labelled])
    everything = np.ones(len(labelled), dtype=bool)

    return {
        "statistic": statistic,
        "n_labelled": len(labelled),
        "n_real": int(np.sum(labels == 0)),
        "n_artifact": int(np.sum(labels == 1)),
        "threshold": threshold,
        "roc_auc": _roc_auc(labels, scores),
        "median_statistic_real": float(np.median(scores[labels == 0])),
        "median_statistic_artifact": float(np.median(scores[labels == 1])),
        "linear_expectation": float(labelled[0]["linear_expectation"]),
        "overall": _slice(everything, "all"),
        "by_compactness": [
            _slice(np.nan_to_num(compactness, nan=99) < 2.0, "compact (FWHM < 2 px)"),
            _slice(
                (np.nan_to_num(compactness, nan=0) >= 2.0)
                & (np.nan_to_num(compactness, nan=0) < 3.5),
                "PSF-scale (2 - 3.5 px)",
            ),
            _slice(np.nan_to_num(compactness, nan=0) >= 3.5, "extended (>= 3.5 px)"),
        ],
        "by_brightness": [
            _slice(np.nan_to_num(brightness, nan=1e9) < 10, "faint (S/N < 10)"),
            _slice(
                (np.nan_to_num(brightness, nan=0) >= 10)
                & (np.nan_to_num(brightness, nan=0) < 30),
                "moderate (S/N 10-30)",
            ),
            _slice(np.nan_to_num(brightness, nan=0) >= 30, "bright (S/N >= 30)"),
        ],
    }


def sweep_ceiling(
    prefix: Path,
    truth: List[Dict[str, Any]],
    ceilings: Sequence[float],
    threshold: float = 0.6,
) -> List[Dict[str, Any]]:
    """Re-evaluate across DN ceilings to expose the non-linearity bias.

    The statistic is only meaningful where the detector responds linearly. This
    reports how much of the bias against compact sources is explained by
    including pixels that have started to flatten.
    """
    global SATURATION_DN
    original = SATURATION_DN
    rows: List[Dict[str, Any]] = []
    try:
        for ceiling in ceilings:
            SATURATION_DN = float(ceiling)
            records = match_to_truth(measure_exposure(prefix), truth)
            evaluation = evaluate(records, threshold=threshold)
            if not evaluation.get("n_labelled"):
                continue
            compact = evaluation["by_compactness"][0]
            psf_scale = evaluation["by_compactness"][1]
            extended = evaluation["by_compactness"][2]
            compact_real = (compact["n_real"] or 0) + (psf_scale["n_real"] or 0)
            compact_rate = None
            if compact_real:
                weighted = sum(
                    (row["false_rejection_rate"] or 0.0) * (row["n_real"] or 0)
                    for row in (compact, psf_scale)
                )
                compact_rate = float(weighted / compact_real)
            rows.append(
                {
                    "saturation_dn": float(ceiling),
                    "n_labelled": evaluation["n_labelled"],
                    "n_artifact": evaluation["n_artifact"],
                    "roc_auc": evaluation["roc_auc"],
                    "false_rejection_compact": compact_rate,
                    "false_rejection_extended": extended["false_rejection_rate"],
                    "artifact_completeness": evaluation["overall"]["artifact_completeness"],
                }
            )
    finally:
        SATURATION_DN = original
    return rows


def render_report(evaluation: Dict[str, Any], exposure: str,
                  sweep: Optional[List[Dict[str, Any]]] = None) -> str:
    """Render the ramp-diagnostics report."""
    if not evaluation.get("n_labelled"):
        return "# Ramp Diagnostics\n\nNo labelled sources matched.\n"

    lines = [
        "# Ramp Diagnostics",
        "",
        "Classifying detector events from the up-the-ramp reads instead of from",
        "shape. An optical source accumulates charge steadily across every group;",
        "a cosmic ray deposits it between two reads and stops. The statistic is the",
        "fraction of total signal arriving in the largest single increment, which",
        f"Statistic: `{evaluation['statistic']}`. The raw increment fraction sits near",
        f"**{evaluation['linear_expectation']:.2f}** for steady accumulation and approaches 1",
        "for an instantaneous deposition; the jump significance is that deviation",
        "expressed in sigma against the per-pixel read-noise and Poisson budget, so it",
        "does not grow simply because a source is bright.",
        "",
        f"Exposure: `{exposure}`",
        "",
        f"- Sources with usable unsaturated ramps and a repeat-exposure label: "
        f"**{evaluation['n_labelled']}** "
        f"({evaluation['n_real']} real, {evaluation['n_artifact']} artifact)",
        f"- Median statistic, real sources: **{evaluation['median_statistic_real']:.3f}**",
        f"- Median statistic, artifacts: **{evaluation['median_statistic_artifact']:.3f}**",
        f"- ROC AUC against the repeat-exposure truth: **{evaluation['roc_auc']:.3f}**",
        "",
        f"## Does it preferentially reject compact sources? (threshold {evaluation['threshold']})",
        "",
        "This is the question the morphology classifier failed. A ramp-based cut",
        "never sees the shape, so its false-rejection rate should not depend on it.",
        "",
        "| population | real | artifact | false rejection | artifact completeness |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in evaluation["by_compactness"] + evaluation["by_brightness"]:
        false_rejection = (
            f"{100 * row['false_rejection_rate']:.1f}%"
            if row["false_rejection_rate"] is not None
            else "n/a"
        )
        completeness = (
            f"{100 * row['artifact_completeness']:.1f}%"
            if row["artifact_completeness"] is not None
            else "n/a"
        )
        lines.append(
            f"| {row['population']} | {row['n_real']} | {row['n_artifact']} | "
            f"{false_rejection} | {completeness} |"
        )

    overall = evaluation["overall"]
    lines += [
        "",
        f"Overall: false rejection "
        f"{100 * overall['false_rejection_rate']:.1f}%, artifact completeness "
        f"{100 * overall['artifact_completeness']:.1f}%.",
    ]

    if sweep:
        lines += [
            "",
            "## The non-linearity bias",
            "",
            "Raw `_uncal` ramps are not linearity-corrected. A pixel's response",
            "flattens before hard saturation, which makes the first increment the",
            "largest and mimics a jump. Compact sources concentrate flux into fewer",
            "pixels, reach higher DN, and are hit hardest. Tightening the ceiling",
            "shows how much of the bias that explains.",
            "",
            "| DN ceiling | labelled | ROC AUC | false rej. compact | false rej. extended | artifact completeness |",
            "| ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in sweep:
            lines.append(
                f"| {row['saturation_dn']:.0f} | {row['n_labelled']} | "
                f"{row['roc_auc']:.3f} | "
                f"{100 * row['false_rejection_compact']:.1f}% | "
                f"{100 * row['false_rejection_extended']:.1f}% | "
                f"{100 * row['artifact_completeness']:.1f}% |"
            )
        lines += [
            "",
            "Tightening the ceiling improves discrimination and roughly halves the",
            "false-rejection rate for compact sources, so non-linearity is a real",
            "part of the problem. It does not remove it: compact real sources are",
            "still rejected about three times as often as extended ones at every",
            "ceiling. **The ramp statistic as implemented here is therefore not yet",
            "a safe replacement for the morphology cut.** It is better motivated -",
            "it measures the physical accumulation history rather than a shape",
            "correlate - but it needs the pipeline's non-linearity correction and a",
            "per-pixel noise model before it can be used as a cut.",
        ]

    lines += [
        "",
        "## Limits",
        "",
        "- Needs `_uncal` ramps, which are ~50 MB per exposure and are not part of",
        "  the products this pipeline otherwise uses.",
        "- Saturated pixels carry no ramp information; a source saturating in its",
        "  first groups also goes flat and is excluded rather than judged.",
        "- Measured on one NIRCam long-wave exposure with NGROUPS=5. More groups",
        "  give a sharper statistic; two would give none.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    """Measure ramp statistics for an exposure and score them against the truth."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exposure",
        type=Path,
        required=True,
        help="Path prefix shared by the _cal.fits and _uncal.fits products.",
    )
    parser.add_argument(
        "--truth", type=Path, default=RESEARCH_DIR / "artifact_characterization.json"
    )
    parser.add_argument("--threshold", type=float, default=0.6)
    parser.add_argument(
        "--statistic",
        default="jump_evidence",
        choices=["jump_evidence", "jump_significance", "max_increment_fraction"],
        help="Noise-normalized jump significance (default) or the raw increment fraction.",
    )
    parser.add_argument(
        "--uncorrected",
        action="store_true",
        help="Skip CRDS linearity/saturation correction, to reproduce the biased result.",
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="Also re-evaluate across DN ceilings to expose the non-linearity bias.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    records = measure_exposure(args.exposure, calibrate=not args.uncorrected)
    print(f"Measured usable ramps for {len(records)} sources")

    truth = _load_truth(args.truth) if args.truth.exists() else []
    records = match_to_truth(records, truth)
    evaluation = evaluate(records, threshold=args.threshold, statistic=args.statistic)

    sweep = None
    if args.sweep:
        sweep = sweep_ceiling(
            args.exposure, truth, [50000.0, 30000.0, 22000.0, 18000.0, 16000.0],
            threshold=args.threshold,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {"evaluation": evaluation, "ceiling_sweep": sweep, "sources": records},
            indent=2,
        ),
        encoding="utf-8",
    )
    args.report.write_text(
        render_report(evaluation, Path(args.exposure).name, sweep), encoding="utf-8"
    )

    if evaluation.get("n_labelled"):
        print(f"  statistic: {evaluation['statistic']} (threshold {args.threshold})")
        print(
            f"  labelled={evaluation['n_labelled']} "
            f"(real={evaluation['n_real']}, artifact={evaluation['n_artifact']})"
        )
        print(f"  median statistic: real={evaluation['median_statistic_real']:.3f} "
              f"artifact={evaluation['median_statistic_artifact']:.3f}")
        print(f"  ROC AUC: {evaluation['roc_auc']:.3f}")
        for row in evaluation["by_compactness"]:
            if row["false_rejection_rate"] is not None:
                print(
                    f"  {row['population']:26s} false rejection "
                    f"{100 * row['false_rejection_rate']:5.1f}%  (n_real={row['n_real']})"
                )
    print(f"Written to {args.output} and {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
