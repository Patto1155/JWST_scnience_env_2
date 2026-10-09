"""Denominator-explicit validation metrics, independent of the detection stack.

Wilson intervals describe binomial sampling uncertainty conditional on the
supplied trials. They do not include image/PSF/model systematic uncertainty.
"""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any, Mapping, Sequence


def binomial_rate(successes: int, trials: int, confidence: float = 0.95) -> dict[str, Any]:
    """Return a rate and Wilson score interval; an empty denominator is undefined."""
    if type(successes) is not int or type(trials) is not int:
        raise ValueError("counts must be integers")
    if not 0 <= successes <= trials or not 0 < confidence < 1:
        raise ValueError("require 0 <= successes <= trials and 0 < confidence < 1")
    result = dict(successes=successes, trials=trials, confidence=confidence,
                  interval_method="wilson", estimate=None, lower=None, upper=None,
                  status="not_estimable", reason="zero denominator")
    if trials == 0:
        return result
    p = successes / trials
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    divisor = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / divisor
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / divisor
    result.update(estimate=p, lower=max(0.0, center - half), upper=min(1.0, center + half),
                  status="estimable", reason=None)
    return result


def injection_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Count each injected trial once, retaining unclassified detections as unknown.

    ``recovered`` is the legacy detector match flag. A detected row with a null
    ``rejected`` value has no classifier decision, so it must not be counted as
    surviving the artifact cut.
    """
    detected = rejected = accepted = 0
    for row in rows:
        if type(row.get("recovered")) is not bool:
            raise ValueError("each injection needs a boolean recovered flag")
        decision = row.get("rejected")
        if decision is not None and type(decision) is not bool:
            raise ValueError("rejected must be boolean or null")
        if not row["recovered"]:
            if decision is not None:
                raise ValueError("an undetected injection cannot have a classifier decision")
            continue
        detected += 1
        rejected += decision is True
        accepted += decision is False
    total = len(rows)
    unknown = detected - rejected - accepted
    return {
        "counts": {"injected": total, "detected": detected, "classified": accepted + rejected,
                   "accepted": accepted, "rejected": rejected, "unclassified": unknown,
                   "not_detected": total - detected},
        "detection_completeness": binomial_rate(detected, total),
        "classifier_survival_among_classified": binomial_rate(accepted, accepted + rejected),
        "false_rejection_among_classified": binomial_rate(rejected, accepted + rejected),
        "confirmed_survival_among_detected": binomial_rate(accepted, detected),
        "end_to_end_completeness": binomial_rate(accepted, total),
        "unknown_survival_fraction_bounds": {
            "lower": accepted / total if total else None,
            "upper": (accepted + unknown) / total if total else None,
            "meaning": "bounds if every unclassified detection fails or passes the cut",
        },
    }


def roc_auc(labels: Sequence[int], scores: Sequence[float]) -> dict[str, Any]:
    """Tie-aware rank AUC with an explicit single-class status; 1 means artifact."""
    if len(labels) != len(scores):
        raise ValueError("labels and scores must have equal lengths")
    if any(label not in (0, 1) for label in labels):
        raise ValueError("labels must be 0 (real) or 1 (artifact)")
    if any(not math.isfinite(float(score)) for score in scores):
        raise ValueError("scores must be finite")
    n_positive = sum(int(x) for x in labels)
    n_negative = len(labels) - n_positive
    result = {"value": None, "status": "not_estimable", "reason": "requires both classes",
              "n_artifacts": n_positive, "n_real": n_negative}
    if not n_positive or not n_negative:
        return result
    ordered = sorted(zip(scores, labels), key=lambda pair: pair[0])
    rank_sum = 0.0
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][0] == ordered[start][0]:
            end += 1
        average_rank = (start + 1 + end) / 2
        rank_sum += average_rank * sum(label for _, label in ordered[start:end])
        start = end
    value = (rank_sum - n_positive * (n_positive + 1) / 2) / (n_positive * n_negative)
    result.update(value=value, status="estimable", reason=None)
    return result


def audit_independence(training: Sequence[Mapping[str, Any]],
                       validation: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Check declared provenance, refusing independent-validation claims on leakage.

    Source/group identifiers must be stable across products. Synthetic records
    also declare generator and PSF identity. Unknown provenance is not proof of
    independence; shared fields/visits fail this intentionally strict external
    validation contract even when sky objects are disjoint.
    """
    common = ("source_id", "sky_group_id", "visit_id", "field_id")
    synthetic = ("generator_id", "psf_id")
    missing: list[dict[str, Any]] = []
    for split, rows in (("training", training), ("validation", validation)):
        for index, row in enumerate(rows):
            required = common
            if row.get("sample_kind") == "synthetic":
                required += synthetic
            absent = [key for key in required if row.get(key) in (None, "", "unknown")]
            if row.get("sample_kind") not in ("real", "synthetic"):
                absent.append("sample_kind (must be real or synthetic)")
            if absent:
                missing.append({"split": split, "row": index, "fields": absent})
    overlaps: dict[str, list[str]] = {}
    for key in common + synthetic:
        a = {str(r[key]) for r in training if r.get(key) not in (None, "", "unknown")
             and (key not in synthetic or r.get("sample_kind") == "synthetic")}
        b = {str(r[key]) for r in validation if r.get(key) not in (None, "", "unknown")
             and (key not in synthetic or r.get("sample_kind") == "synthetic")}
        if a & b:
            overlaps[key] = sorted(a & b)
    empty = not training or not validation
    status = "failed" if overlaps else "unverified" if missing or empty else "passed"
    return {"status": status, "independent_validation_permitted": status == "passed",
            "overlaps": overlaps, "missing_provenance": missing,
            "empty_split": empty, "n_training": len(training), "n_validation": len(validation),
            "scope": "declared provenance only; metadata accuracy requires external review"}


def evaluate_external_validation(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate scored rows against a frozen model and documented training manifest.

    This accepts existing predictions, never refits or tunes a threshold. AUC
    requires both classes but real-only stars can still constrain false rejection.
    """
    training = payload["training"]
    rows = payload["validation"]
    for key in ("model_sha256", "training_manifest_sha256"):
        value = payload.get(key, "")
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(f"{key} must be a lowercase SHA-256 digest")
    threshold = float(payload["threshold"])
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("threshold must be a finite probability")
    scores = [float(row["artifact_score"]) for row in rows]
    if any(not math.isfinite(s) or not 0 <= s <= 1 for s in scores):
        raise ValueError("artifact scores must be finite probabilities")
    labels = [row["label"] for row in rows]
    auc = roc_auc(labels, scores)
    real = [score for label, score in zip(labels, scores) if label == 0]
    artifacts = [score for label, score in zip(labels, scores) if label == 1]
    independence = audit_independence(training, rows)
    return {"independence": independence, "roc_auc": auc, "threshold": threshold,
            "model_sha256": payload["model_sha256"],
            "training_manifest_sha256": payload["training_manifest_sha256"],
            "false_rejection_real_sources": binomial_rate(sum(s >= threshold for s in real), len(real)),
            "artifact_recall": binomial_rate(sum(s >= threshold for s in artifacts), len(artifacts)),
            "claim": "external validation on declared provenance" if independence["independent_validation_permitted"]
                     else "diagnostic metrics only; independent validation not established"}
