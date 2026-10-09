"""Science-facing failure cases, not just assertions mirroring implementation."""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from discovery.validation_audit import audit_injections, render_report
from discovery.validation_metrics import (
    audit_independence, binomial_rate, evaluate_external_validation,
    injection_metrics, roc_auc,
)
from discovery.artifact_classifier import _auc_fields, _metrics, _roc_auc
from discovery.artifact_classifier import render_report as classifier_report
from discovery.artifact_classifier import train

ROOT = Path(__file__).resolve().parents[2]


def test_zero_losses_is_not_zero_uncertainty():
    rate = binomial_rate(0, 27)
    assert rate["estimate"] == 0
    assert rate["lower"] == pytest.approx(0, abs=1e-15)
    assert rate["upper"] == pytest.approx(0.124555029741867, abs=1e-9)
    assert binomial_rate(27, 27)["lower"] > 0.87
    assert binomial_rate(0, 0)["status"] == "not_estimable"


@pytest.mark.parametrize("successes,trials", [(1, 0), (-1, 2), (1.0, 2), (True, 2)])
def test_invalid_binomial_counts_fail(successes, trials):
    with pytest.raises(ValueError):
        binomial_rate(successes, trials)


def test_unknown_classification_does_not_survive_and_detection_has_own_denominator():
    rows = [{"recovered": False, "rejected": None}] * 7 + [
        {"recovered": True, "rejected": False},
        {"recovered": True, "rejected": True},
        {"recovered": True, "rejected": None},
    ]
    m = injection_metrics(rows)
    assert m["detection_completeness"]["estimate"] == 0.3
    assert m["false_rejection_among_classified"]["estimate"] == 0.5
    assert m["end_to_end_completeness"]["estimate"] == 0.1
    assert m["unknown_survival_fraction_bounds"]["upper"] == 0.2
    with pytest.raises(ValueError):
        injection_metrics([{"recovered": False, "rejected": False}])


def test_auc_ties_and_single_class():
    assert roc_auc([0, 1], [0.5, 0.5])["value"] == 0.5
    assert roc_auc([0, 1, 1], [0.1, 0.9, 0.8])["value"] == 1
    assert roc_auc([0, 1], [0.9, 0.1])["value"] == 0
    result = roc_auc([0, 0], [0.1, 0.9])
    assert result["value"] is None and result["status"] == "not_estimable"
    assert _roc_auc(np.array([0, 1]), np.array([0.5, 0.5])) == 0.5
    assert _auc_fields(np.array([0]), np.array([0.5]))["roc_auc_reason"] == "requires both classes"
    with pytest.raises(ValueError):
        roc_auc([0, 1], [0.5, float("nan")])


def provenance(suffix, synthetic=False):
    result = {"source_id": "source-" + suffix, "sky_group_id": "group-" + suffix,
              "visit_id": "visit-" + suffix, "field_id": "field-" + suffix,
              "sample_kind": "synthetic" if synthetic else "real"}
    if synthetic:
        result.update(generator_id="generator-" + suffix, psf_id="psf-" + suffix)
    return result


@pytest.mark.parametrize("key", ["source_id", "sky_group_id", "visit_id", "field_id", "generator_id", "psf_id"])
def test_any_leakage_blocks_independence(key):
    a, b = provenance("a", True), provenance("b", True)
    b[key] = a[key]
    result = audit_independence([a], [b])
    assert not result["independent_validation_permitted"]
    assert result["status"] == "failed" and key in result["overlaps"]


def test_missing_provenance_and_empty_splits_are_unverified():
    assert audit_independence([{}], [{}])["status"] == "unverified"
    assert audit_independence([], [provenance("b")])["status"] == "unverified"
    a, b = provenance("a"), provenance("b")
    b["sample_kind"] = "invented"
    assert audit_independence([a], [b])["status"] == "unverified"
    assert audit_independence([provenance("a")], [provenance("b")])["status"] == "passed"


def test_real_only_external_test_reports_rejection_but_no_auc():
    payload = {"model_sha256": "a" * 64, "training_manifest_sha256": "b" * 64,
               "threshold": 0.5, "training": [provenance("a")],
               "validation": [dict(provenance("b"), label=0, artifact_score=0.1)]}
    result = evaluate_external_validation(payload)
    assert result["independence"]["status"] == "passed"
    assert result["roc_auc"]["status"] == "not_estimable"
    assert result["false_rejection_real_sources"]["trials"] == 1
    assert result["artifact_recall"]["status"] == "not_estimable"
    json.dumps(result, allow_nan=False)
    payload["model_sha256"] = "not a checksum"
    with pytest.raises(ValueError):
        evaluate_external_validation(payload)


def test_committed_f444w_outcomes_reproduce_weak_detection_and_uncertain_zero_loss():
    payload = json.loads((ROOT / "research_output/injection_recovery.json").read_text())
    result = audit_injections(payload)
    faint = result["filters"]["F444W"]["faint_point_sources"]
    assert faint["counts"]["injected"] == 119
    assert faint["counts"]["detected"] == 27
    assert faint["end_to_end_completeness"]["estimate"] == pytest.approx(27 / 119)
    assert faint["false_rejection_among_classified"]["successes"] == 0
    assert faint["false_rejection_among_classified"]["upper"] > 0.12
    payload["summaries"] = [{"overall": {"detection_completeness": 1.0}}]
    assert audit_injections(payload) == result
    with pytest.raises(ValueError):
        audit_injections({"summaries": payload["summaries"]})


def test_classifier_one_class_report_is_json_safe_and_renders():
    labels = np.zeros(3)
    scores = np.array([0.1, 0.2, 0.3])
    point = _metrics(labels, scores, 0.9)
    model = {"n_training_rows": 3, "n_artifacts": 0, "n_real": 3,
             "trained_on_filters": ["F444W"],
             "cross_validation": dict(_auc_fields(labels, scores), operating_points=[point]),
             "cross_filter_transfer": [{"trained_on": ["F277W"], "tested_on": "F444W",
                                        **_auc_fields(labels, scores), "at_threshold_0.9": point}],
             "coefficient_interpretation": {}}
    json.dumps(model, allow_nan=False)
    assert "not estimable" in classifier_report(model)


def test_actual_training_single_class_transfer_serializes_without_nan():
    model = train(ROOT / "research_output/artifact_characterization.json",
                  ROOT / "research_output/injected_point_sources.json")
    single = next(row for row in model["cross_filter_transfer"] if row["tested_on"] == "F444W")
    assert single["roc_auc"] is None
    assert single["roc_auc_status"] == "not_estimable"
    json.dumps(model, allow_nan=False)
    assert "not estimable" in classifier_report(model)


def test_cli_runs_without_fits_or_keys_and_writes_strict_json(tmp_path):
    output, report = tmp_path / "audit.json", tmp_path / "audit.md"
    result = subprocess.run([sys.executable, "-m", "discovery.validation_audit",
                             "--output", str(output), "--report", str(report)],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(), parse_constant=lambda x: pytest.fail(x))
    assert len(payload["input_sha256"]) == 64
    assert "27/119" in report.read_text()
