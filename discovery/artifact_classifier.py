"""Single-image artifact classifier trained on the repeat-exposure truth set.

Repeat-exposure vetting is the gold standard, but it is unavailable exactly
where it is most needed: this archive has no F444W repeat pair, and SMACS J0723
has no repeat coverage in any filter. Every candidate ever selected by this
pipeline sits in a band that cannot be self-vetoed.

This module closes that gap. `artifact_characterization.py` produces a labelled
set - sources confirmed present in two independent exposures, and events present
in only one - and morphology separates the two cleanly. Fitting a classifier to
those labels gives a rejector that works on a **single image**, with no repeat
coverage at all.

Features, chosen to be interpretable rather than maximally predictive:

- ``psf_ratio``  - source FWHM divided by the filter's diffraction-limited PSF
  FWHM. Normalizing by wavelength is what lets a model fit on F277W/F356W be
  applied to F444W without refitting.
- ``sharpness``  - peak pixel over total segment flux. A cosmic ray deposits
  charge in a few pixels; an optical source is spread by the PSF.
- ``log_area``   - log10 of the segment area in pixels.
- ``ellipticity``- separates round snowballs from elongated tracks.

Logistic regression is fitted by Newton-Raphson in numpy. The model is small,
inspectable, and its coefficients are written to JSON so a classification can be
reproduced without refitting.

Run:
    python discovery/artifact_classifier.py --train
    python discovery/artifact_classifier.py --train --report
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from discovery.validation_metrics import roc_auc

RESEARCH_DIR = Path("research_output")
DEFAULT_TRUTH = RESEARCH_DIR / "artifact_characterization.json"
DEFAULT_POINT_SOURCES = RESEARCH_DIR / "injected_point_sources.json"
DEFAULT_MODEL = RESEARCH_DIR / "artifact_classifier.json"
DEFAULT_REPORT = RESEARCH_DIR / "ARTIFACT_CLASSIFIER.md"

FEATURE_NAMES = ["psf_ratio", "sharpness", "log_area", "ellipticity"]

# JWST aperture diameter, metres, and NIRCam long-wave pixel scale.
TELESCOPE_DIAMETER_M = 6.5
LONGWAVE_PIXEL_SCALE = 0.063
SHORTWAVE_PIXEL_SCALE = 0.031

# Pivot wavelengths in microns for the NIRCam filters this pipeline uses.
FILTER_WAVELENGTH_MICRON = {
    "F070W": 0.704, "F090W": 0.901, "F115W": 1.154, "F140M": 1.404,
    "F150W": 1.501, "F162M": 1.626, "F182M": 1.845, "F200W": 1.990,
    "F210M": 2.093, "F250M": 2.503, "F277W": 2.786, "F300M": 2.996,
    "F335M": 3.365, "F356W": 3.563, "F360M": 3.621, "F410M": 4.092,
    "F430M": 4.280, "F444W": 4.421, "F460M": 4.624, "F480M": 4.834,
}

SHORTWAVE_FILTERS = {
    "F070W", "F090W", "F115W", "F140M", "F150W", "F150W2",
    "F162M", "F164N", "F182M", "F187N", "F200W", "F210M", "F212N",
}


def psf_fwhm_pixels(filter_name: str) -> Optional[float]:
    """Diffraction-limited PSF FWHM in pixels for a NIRCam filter.

    1.025 lambda/D in radians, converted to arcsec and divided by the pixel
    scale of the relevant detector. Normalizing measured widths by this is what
    makes a model fitted at one wavelength transferable to another.
    """
    name = str(filter_name).upper()
    wavelength = FILTER_WAVELENGTH_MICRON.get(name)
    if wavelength is None:
        return None
    fwhm_arcsec = 1.025 * (wavelength * 1e-6 / TELESCOPE_DIAMETER_M) * 206264.806247
    scale = SHORTWAVE_PIXEL_SCALE if name in SHORTWAVE_FILTERS else LONGWAVE_PIXEL_SCALE
    return float(fwhm_arcsec / scale)


def build_features(
    source: Dict[str, Any],
    filter_name: str,
) -> Optional[List[float]]:
    """Turn one detection record into the feature vector, or None if incomplete."""
    psf = psf_fwhm_pixels(filter_name)
    fwhm = source.get("fwhm_pixels")
    sharpness = source.get("sharpness")
    area = source.get("area_pixels")
    ellipticity = source.get("ellipticity")
    if psf is None or None in (fwhm, sharpness, area, ellipticity):
        return None
    if not all(np.isfinite(float(v)) for v in (fwhm, sharpness, area, ellipticity)):
        return None
    if float(area) <= 0 or psf <= 0:
        return None
    return [
        float(fwhm) / psf,
        float(sharpness),
        math.log10(float(area)),
        float(ellipticity),
    ]


def _standardize(matrix: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Zero-mean, unit-variance columns; returns the transform for reuse."""
    mean = matrix.mean(axis=0)
    scale = matrix.std(axis=0)
    scale[scale == 0] = 1.0
    return (matrix - mean) / scale, mean, scale


def fit_logistic(
    features: np.ndarray,
    labels: np.ndarray,
    *,
    l2: float = 1.0,
    iterations: int = 100,
) -> np.ndarray:
    """Fit logistic regression by Newton-Raphson with an L2 penalty.

    The penalty keeps the fit stable when a feature is nearly separating, which
    `sharpness` very nearly is.
    """
    design = np.hstack([np.ones((features.shape[0], 1)), features])
    weights = np.zeros(design.shape[1])
    penalty = l2 * np.eye(design.shape[1])
    penalty[0, 0] = 0.0  # never penalize the intercept

    for _ in range(iterations):
        prediction = 1.0 / (1.0 + np.exp(-design @ weights))
        gradient = design.T @ (labels - prediction) - penalty @ weights
        variance = np.clip(prediction * (1.0 - prediction), 1e-9, None)
        hessian = -(design.T * variance) @ design - penalty
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError:
            break
        weights = weights - step
        if np.max(np.abs(step)) < 1e-8:
            break
    return weights


def predict_probability(weights: np.ndarray, features: np.ndarray) -> np.ndarray:
    """Artifact probability for standardized feature rows."""
    design = np.hstack([np.ones((features.shape[0], 1)), features])
    return 1.0 / (1.0 + np.exp(-design @ weights))


def _metrics(labels: np.ndarray, scores: np.ndarray, threshold: float) -> Dict[str, Any]:
    """Purity and completeness of the artifact class at one threshold."""
    flagged = scores >= threshold
    true_positive = int(np.sum(flagged & (labels == 1)))
    false_positive = int(np.sum(flagged & (labels == 0)))
    false_negative = int(np.sum(~flagged & (labels == 1)))
    return {
        "threshold": float(threshold),
        "n_flagged": int(np.sum(flagged)),
        "artifact_purity": float(true_positive / (true_positive + false_positive))
        if (true_positive + false_positive)
        else None,
        "artifact_completeness": float(true_positive / (true_positive + false_negative))
        if (true_positive + false_negative)
        else None,
        "real_sources_lost": int(false_positive),
        "real_source_loss_fraction": float(false_positive / int(np.sum(labels == 0)))
        if np.sum(labels == 0) else None,
    }


def _roc_auc(labels: np.ndarray, scores: np.ndarray) -> Optional[float]:
    """Tie-aware AUC; a one-class test has no estimable ROC curve."""
    return roc_auc(labels.tolist(), scores.tolist())["value"]


def _auc_fields(labels: np.ndarray, scores: np.ndarray) -> Dict[str, Any]:
    result = roc_auc(labels.tolist(), scores.tolist())
    return {"roc_auc": result["value"], "roc_auc_status": result["status"],
            "roc_auc_reason": result["reason"]}


def _metric_text(value: Optional[float], *, percent: bool = False) -> str:
    """Render legacy NaN and undefined metrics without claiming a measurement."""
    if value is None or not math.isfinite(float(value)):
        return "not estimable"
    return f"{100 * value:.1f}%" if percent else f"{value:.3f}"


def sky_groups(
    coordinates: np.ndarray,
    tolerance_arcsec: float = 0.3,
) -> np.ndarray:
    """Assign one group id per sky position, joining detections within tolerance.

    A source detected while searching exposure A and the same source detected
    while searching exposure B are two rows describing one object. Splitting them
    across folds would put the same galaxy in training and test, so they are
    grouped by sky position and the whole group moves together.
    """
    order = np.lexsort((coordinates[:, 0], coordinates[:, 1]))
    group_of = np.full(len(coordinates), -1, dtype=int)
    next_group = 0
    tolerance_deg = tolerance_arcsec / 3600.0

    for index in order:
        if group_of[index] != -1:
            continue
        ra, dec = coordinates[index]
        # Declination is sorted, so only a narrow band can match.
        near = np.abs(coordinates[:, 1] - dec) <= tolerance_deg
        cos_dec = max(math.cos(math.radians(float(dec))), 1e-6)
        near &= np.abs(coordinates[:, 0] - ra) * cos_dec <= tolerance_deg
        near &= group_of == -1
        group_of[near] = next_group
        next_group += 1
    return group_of


def cross_validate(
    features: np.ndarray,
    labels: np.ndarray,
    *,
    groups: Optional[np.ndarray] = None,
    folds: int = 5,
    seed: int = 0,
) -> Dict[str, Any]:
    """K-fold cross-validated scores, so quoted purity is out-of-sample.

    When ``groups`` is supplied the split is group-aware: every detection of one
    sky object lands in the same fold.
    """
    rng = np.random.default_rng(seed)
    if groups is None:
        fold_ids = np.array_split(rng.permutation(len(labels)), folds)
    else:
        unique = np.unique(groups)
        shuffled = rng.permutation(unique)
        assignment = {g: i % folds for i, g in enumerate(shuffled)}
        fold_of = np.array([assignment[g] for g in groups])
        fold_ids = [np.where(fold_of == f)[0] for f in range(folds)]
    out_of_sample = np.zeros(len(labels))

    for fold in fold_ids:
        if len(fold) == 0:
            continue
        mask = np.ones(len(labels), dtype=bool)
        mask[fold] = False
        train_features, mean, scale = _standardize(features[mask])
        weights = fit_logistic(train_features, labels[mask])
        out_of_sample[fold] = predict_probability(weights, (features[fold] - mean) / scale)

    return {
        **_auc_fields(labels, out_of_sample),
        "operating_points": [
            _metrics(labels, out_of_sample, threshold)
            for threshold in (0.5, 0.7, 0.9, 0.95)
        ],
        "out_of_sample_scores": out_of_sample,
    }


def _filter_of(record: Dict[str, Any], summaries: List[Dict[str, Any]]) -> Optional[str]:
    """Recover which filter a source record belongs to from the pair summaries."""
    for summary in summaries:
        if record["epoch_a"] in summary["epochs"] and record["epoch_b"] in summary["epochs"]:
            return summary["filter"]
    return None


def _filter_of_detection(
    record: Dict[str, Any], summaries: List[Dict[str, Any]]
) -> Optional[str]:
    """Recover the filter for a consolidated detection row."""
    for summary in summaries:
        if record["epoch_a"] in summary["epochs"]:
            return summary["filter"]
    return None


def load_training_set(
    path: Path,
    point_sources: Optional[Path] = None,
) -> Tuple[np.ndarray, np.ndarray, List[str], np.ndarray, List[str]]:
    """Build the feature matrix and labels from the characterization output.

    Trains on the consolidated per-detection rows, never the raw per-pair
    comparisons. With several exposures of a field the same detection is judged
    repeatedly, and using those rows directly would put one source in both the
    training and test folds and inflate every score.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    summaries = payload["summaries"]
    detections = payload.get("detections")
    if not detections:
        raise ValueError(
            f"{path} has no consolidated detections. Re-run artifact_characterization.py."
        )

    rows: List[List[float]] = []
    labels: List[int] = []
    filters: List[str] = []
    coordinates: List[List[float]] = []
    visits: List[str] = []
    for record in detections:
        filter_name = _filter_of_detection(record, summaries)
        if filter_name is None:
            continue
        features = build_features(record, filter_name)
        if features is None:
            continue
        rows.append(features)
        labels.append(1 if record["consensus"] == "artifact" else 0)
        filters.append(filter_name)
        coordinates.append([float(record["ra"]), float(record["dec"])])
        # jw<program><obs><visit>_... - the observation id identifies the visit.
        visits.append(str(record["epoch_a"])[:14])
    # Injected point sources supply the class the repeat-exposure truth set lacks.
    # A deep extragalactic field contains almost no real unresolved sources, so
    # without these "compact" separates the classes as well as "cosmic ray" does
    # and the fit takes the shortcut. Each carries a unique sky group so it never
    # shares a fold with anything else.
    n_injected = 0
    if point_sources and point_sources.exists():
        injected = json.loads(point_sources.read_text(encoding="utf-8"))
        for index, record in enumerate(injected):
            features = build_features(record, str(record.get("filter") or ""))
            if features is None:
                continue
            rows.append(features)
            labels.append(0)
            filters.append(str(record["filter"]))
            # Off-sky sentinel coordinates keep each injection in its own group.
            coordinates.append([-999.0 - index * 1e-3, -89.0])
            visits.append("injected")
            n_injected += 1

    return (
        np.asarray(rows, dtype=float),
        np.asarray(labels, dtype=float),
        filters,
        np.asarray(coordinates, dtype=float),
        visits,
    )


def train(path: Path, point_sources: Optional[Path] = None) -> Dict[str, Any]:
    """Fit the classifier and cross-validate it."""
    features, labels, filters, coordinates, visits = load_training_set(path, point_sources)
    if len(labels) == 0:
        raise ValueError(f"No usable training rows in {path}")

    groups = sky_groups(coordinates)
    validation = cross_validate(features, labels, groups=groups)
    standardized, mean, scale = _standardize(features)
    weights = fit_logistic(standardized, labels)

    # Held-out transfer check: fit on one filter, score the other. This is the
    # closest available proxy for applying the model to F444W, where no repeat
    # pair exists to validate against.
    transfer: List[Dict[str, Any]] = []
    unique_filters = sorted(set(filters))
    filter_array = np.asarray(filters)
    if len(unique_filters) > 1:
        for held_out in unique_filters:
            train_mask = filter_array != held_out
            test_mask = ~train_mask
            if train_mask.sum() < 20 or test_mask.sum() < 20:
                continue
            train_std, fold_mean, fold_scale = _standardize(features[train_mask])
            fold_weights = fit_logistic(train_std, labels[train_mask])
            scores = predict_probability(
                fold_weights, (features[test_mask] - fold_mean) / fold_scale
            )
            transfer.append(
                {
                    "trained_on": [f for f in unique_filters if f != held_out],
                    "tested_on": held_out,
                    **_auc_fields(labels[test_mask], scores),
                    "at_threshold_0.9": _metrics(labels[test_mask], scores, 0.9),
                }
            )

    visits = list(visits)
    # Held-out visit: train on one visit, score another. Detector state, background
    # and pointing all change between visits, so this is a harder and more honest
    # test than a random split.
    visit_transfer: List[Dict[str, Any]] = []
    visit_array = np.asarray(visits)
    for held_out in sorted(set(visits)):
        train_mask = visit_array != held_out
        test_mask = ~train_mask
        if train_mask.sum() < 50 or test_mask.sum() < 50:
            continue
        train_std, fold_mean, fold_scale = _standardize(features[train_mask])
        fold_weights = fit_logistic(train_std, labels[train_mask])
        scores = predict_probability(
            fold_weights, (features[test_mask] - fold_mean) / fold_scale
        )
        visit_transfer.append(
            {
                "held_out_visit": held_out,
                "n_test": int(test_mask.sum()),
                **_auc_fields(labels[test_mask], scores),
                "at_threshold_0.5": _metrics(labels[test_mask], scores, 0.5),
            }
        )

    n_injected = int(sum(1 for v in visits if v == "injected"))
    return {
        "feature_names": FEATURE_NAMES,
        "n_injected_point_sources": n_injected,
        "n_sky_groups": int(len(np.unique(groups))),
        "held_out_visit": visit_transfer,
        "standardization": {"mean": mean.tolist(), "scale": scale.tolist()},
        "weights": weights.tolist(),
        "n_training_rows": int(len(labels)),
        "n_artifacts": int(labels.sum()),
        "n_real": int((labels == 0).sum()),
        "trained_on_filters": unique_filters,
        "cross_validation": {
            "roc_auc": validation["roc_auc"],
            "roc_auc_status": validation["roc_auc_status"],
            "roc_auc_reason": validation["roc_auc_reason"],
            "operating_points": validation["operating_points"],
        },
        "cross_filter_transfer": transfer,
        "coefficient_interpretation": dict(
            zip(FEATURE_NAMES, [float(w) for w in weights[1:]])
        ),
    }


def classify(
    model: Dict[str, Any],
    sources: Sequence[Dict[str, Any]],
    filter_name: str,
) -> List[Optional[float]]:
    """Artifact probability for each detection in a single image.

    Sources with incomplete morphology return None rather than a fabricated
    score - the same discipline the rest of this pipeline now follows.
    """
    mean = np.asarray(model["standardization"]["mean"], dtype=float)
    scale = np.asarray(model["standardization"]["scale"], dtype=float)
    weights = np.asarray(model["weights"], dtype=float)

    results: List[Optional[float]] = []
    usable_rows: List[List[float]] = []
    usable_positions: List[int] = []
    for index, source in enumerate(sources):
        features = build_features(source, filter_name)
        results.append(None)
        if features is not None:
            usable_rows.append(features)
            usable_positions.append(index)

    if usable_rows:
        scores = predict_probability(
            weights, (np.asarray(usable_rows, dtype=float) - mean) / scale
        )
        for position, score in zip(usable_positions, scores):
            results[position] = float(score)
    return results


def residual_contamination(
    model: Dict[str, Any],
    truth_summaries: List[Dict[str, Any]],
    threshold: float = 0.5,
) -> Optional[Dict[str, Any]]:
    """What the classifier actually buys, in the units that matter.

    Applying a rejector with known completeness to a population with a measured
    artifact fraction gives the residual contamination. Stating it this way
    keeps the answer honest: a large relative improvement can still leave a
    search unusable in absolute terms.
    """
    point = next(
        (p for p in model["cross_validation"]["operating_points"]
         if abs(p["threshold"] - threshold) < 1e-9),
        None,
    )
    if (point is None or not truth_summaries
            or point["artifact_completeness"] is None
            or point["real_source_loss_fraction"] is None):
        return None

    fractions = [s["single_epoch_fraction"] for s in truth_summaries
                 if s.get("single_epoch_fraction") is not None]
    densities = [s["artifact_density_per_arcmin2_per_exposure"] for s in truth_summaries
                 if s.get("artifact_density_per_arcmin2_per_exposure") is not None]
    ratios = [s["contamination_forecast"]["artifacts_per_genuine_highz_source"]
              for s in truth_summaries if s.get("contamination_forecast")]
    if not fractions:
        return None

    survival = 1.0 - point["artifact_completeness"]
    before = float(np.mean(fractions))
    real_kept = 1.0 - point["real_source_loss_fraction"]
    # Fraction of the surviving catalog that is still an artifact.
    after = (before * survival) / max(before * survival + (1.0 - before) * real_kept, 1e-12)
    return {
        "threshold": threshold,
        "artifact_fraction_before": before,
        "artifact_fraction_after": float(after),
        "improvement_factor": float(before / after) if after > 0 else None,
        "real_source_loss_fraction": point["real_source_loss_fraction"],
        "artifact_density_after_per_arcmin2": (
            float(np.mean(densities) * survival) if densities else None
        ),
        "artifacts_per_highz_source_after": (
            float(np.mean(ratios) * survival) if ratios else None
        ),
    }


def render_report(model: Dict[str, Any]) -> str:
    """Render the model card."""
    lines = [
        "# Single-Image Artifact Classifier",
        "",
        "Fitted to the repeat-exposure truth set from",
        "`artifact_characterization.py`. The point is to reject detector artifacts",
        "in images that have **no repeat coverage** - which is every band this",
        "pipeline actually selects candidates in.",
        "",
        f"- Training rows: **{model['n_training_rows']}** "
        f"({model['n_artifacts']} artifacts, {model['n_real']} real sources, "
        f"of which {model.get('n_injected_point_sources', 0)} are injected point sources)",
        f"- Filters: {', '.join(model['trained_on_filters'])}",
        f"- Cross-validated ROC AUC: **{_metric_text(model['cross_validation']['roc_auc'])}**",
        "",
        "## Operating points (5-fold, out-of-sample)",
        "",
        "| threshold | flagged | artifact purity | artifact completeness | real sources lost |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    for point in model["cross_validation"]["operating_points"]:
        lines.append(
            f"| {point['threshold']:.2f} | {point['n_flagged']} | "
            f"{_metric_text(point['artifact_purity'])} | {_metric_text(point['artifact_completeness'])} | "
            f"{point['real_sources_lost']} ({_metric_text(point['real_source_loss_fraction'], percent=True)}) |"
        )

    lines += [
        "",
        "## Cross-filter transfer",
        "",
        "Fitted on one filter and scored on the other. This is the closest proxy",
        "available for applying the model to F444W, where no repeat pair exists.",
        "",
        "| trained on | tested on | ROC AUC | purity @0.9 | completeness @0.9 |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in model["cross_filter_transfer"]:
        point = row["at_threshold_0.9"]
        lines.append(
            f"| {', '.join(row['trained_on'])} | {row['tested_on']} | "
            f"{_metric_text(row['roc_auc'])} | {_metric_text(point['artifact_purity'])} | "
            f"{_metric_text(point['artifact_completeness'])} |"
        )

    lines += [
        "",
        "## Coefficients",
        "",
        "Positive weight pushes toward *artifact*. Features are standardized, so",
        "magnitudes are comparable.",
        "",
        "| feature | weight |",
        "| --- | ---: |",
    ]
    for name, weight in model["coefficient_interpretation"].items():
        lines.append(f"| `{name}` | {weight:+.3f} |")

    residual = model.get("residual_contamination")
    if residual:
        lines += [
            "",
            "## What this actually buys",
            "",
            f"At threshold {residual['threshold']:.2f}, applied to a population with the",
            f"measured **{100 * residual['artifact_fraction_before']:.1f}%** artifact",
            f"fraction, the surviving catalog is **{100 * residual['artifact_fraction_after']:.1f}%**",
            f"artifacts - a {residual['improvement_factor']:.1f}x improvement, at the cost of",
            f"{100 * residual['real_source_loss_fraction']:.1f}% of real sources.",
            "",
        ]
        if residual.get("artifacts_per_highz_source_after") is not None:
            lines += [
                f"For a dropout search that is **~{residual['artifacts_per_highz_source_after']:.0f}",
                "artifacts per genuine high-redshift source**, down from ~1200. That is a",
                "large relative gain and still a hopeless absolute number. The classifier is",
                "a mitigation for images that have no repeat coverage; it is not a substitute",
                "for deep mosaics with cross-dither rejection, and nothing here makes",
                "single-exposure dropout searching viable.",
                "",
            ]

    lines += [
        "",
        "## Limits",
        "",
        "- Sky-group folds and held-out visits are internal diagnostic checks.",
        "  Shared fields or injection generators/PSFs are not independent external",
        "  validation. Legacy training rows lack complete provenance; use the gate",
        "  in `validation_metrics.py` before claiming independent performance.",
        "- ROC AUC requires both classes. Real-only synthetic-source tests can",
        "  estimate rejection, but their AUC is explicitly not estimable.",
        "- Fitted on NIRCam long-wave imaging only. `psf_ratio` normalizes by the",
        "  diffraction-limited FWHM so the model transfers across wavelength, but",
        "  short-wave detectors sample the PSF differently and should be validated",
        "  separately before the model is trusted there.",
        "- The truth labels come from a 5.65-9.55 hour baseline. That is long",
        "  enough to be certain about cosmic rays and far too short to distinguish",
        "  a genuine fast transient from an artifact. The model learns *detector",
        "  event*, not *not astrophysical*.",
        "- It is a rejector, not a detector. A high score is grounds to drop a",
        "  candidate; a low score is not evidence that a source is real.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    """Train the classifier and write the model plus its report card."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth", type=Path, default=DEFAULT_TRUTH)
    parser.add_argument(
        "--point-sources",
        type=Path,
        default=DEFAULT_POINT_SOURCES,
        help="Injected point-source rows to add as known-real training examples.",
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--train", action="store_true", help="Fit and persist the model.")
    args = parser.parse_args()

    if not args.truth.exists():
        print(f"No truth set at {args.truth}. Run artifact_characterization.py first.")
        return 1

    model = train(args.truth, args.point_sources)
    truth_summaries = json.loads(args.truth.read_text(encoding="utf-8")).get("summaries", [])
    model["residual_contamination"] = residual_contamination(model, truth_summaries)
    if args.train:
        args.model.parent.mkdir(parents=True, exist_ok=True)
        args.model.write_text(json.dumps(model, indent=2, allow_nan=False), encoding="utf-8")
        args.report.write_text(render_report(model), encoding="utf-8")

    print(f"Trained on {model['n_training_rows']} rows "
          f"({model['n_artifacts']} artifacts, {model['n_real']} real, "
          f"{model.get('n_injected_point_sources', 0)} of them injected point sources)")
    print(f"Cross-validated ROC AUC: {_metric_text(model['cross_validation']['roc_auc'])}")
    for point in model["cross_validation"]["operating_points"]:
        print(
            f"  threshold {point['threshold']:.2f}: "
            f"purity={_metric_text(point['artifact_purity'])} "
            f"completeness={_metric_text(point['artifact_completeness'])} "
            f"real lost={point['real_sources_lost']}"
        )
    for row in model["cross_filter_transfer"]:
        print(f"  filter transfer -> {row['tested_on']}: ROC AUC {_metric_text(row['roc_auc'])}")
    for row in model.get("held_out_visit", []):
        print(
            f"  held-out visit {row['held_out_visit']}: ROC AUC {_metric_text(row['roc_auc'])} "
            f"(n={row['n_test']})"
        )
    residual = model.get("residual_contamination")
    if residual:
        print(
            f"  residual artifact fraction: "
            f"{100 * residual['artifact_fraction_before']:.1f}% -> "
            f"{100 * residual['artifact_fraction_after']:.1f}% "
            f"({residual['improvement_factor']:.1f}x), "
            f"losing {100 * residual['real_source_loss_fraction']:.1f}% of real sources"
        )
    if args.train:
        print(f"Model written to {args.model}, report to {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
