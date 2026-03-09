"""Tests for supervisor-driven campaign helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from discovery.session_schemas import CandidateSummary, normalize_worker_report
from discovery.supervisor_campaign import (
    DEFAULT_ALLOWED_WORKER_TOOLS,
    WORKER_REPORT_PREFIX,
    build_worker_payload,
    build_worker_objective,
    extract_structured_worker_report,
    normalize_candidate_record,
    select_top_reports_for_judge,
    run_supervisor_campaign,
)
from discovery.telemetry import SessionTelemetry


def _sample_candidate() -> dict:
    return {
        "target": "GS-MEDIUM-HST",
        "source_id": 545,
        "position": {"x": 196.7365, "y": 1925.1874},
        "reference_dataset": "jwst_GS-MEDIUM-HST_F444W_demo",
        "f444_dataset": "jwst_GS-MEDIUM-HST_F444W_demo",
        "f090_dataset": "jwst_GS-MEDIUM-HST_F090W_demo",
        "f200_dataset": "jwst_GS-MEDIUM-HST_F200W_demo",
        "ratio_f090_f444": 0.0,
        "validation_score": 0.93,
        "validation_status": "keep",
        "red_snr_r3": 42.5,
        "coverage_fraction_r3": 1.0,
        "edge_distance_px": 120.0,
        "artifacts": [{"path": "research_output/visuals/demo.png"}],
        "primary_channel": "dropout_strict",
        "proposal_channels": ["dropout_strict", "morphology_extended_red"],
        "channel_scores": {"dropout_strict": 0.92, "morphology_extended_red": 0.55},
        "measurement_status_by_filter": {
            "F090W": "measured_nondetection",
            "F200W": "measured_detection",
            "F444W": "measured_detection",
        },
        "completeness_score": 1.0,
        "novelty_score": 0.55,
        "falsification_flags": [],
        "disqualifying_flags": [],
        "portfolio_bucket": "conservative",
    }


def test_build_worker_payload_uses_qwen_worker_model() -> None:
    """Worker payloads should stay narrow and model-selectable."""
    candidate = normalize_candidate_record(_sample_candidate())

    payload = build_worker_payload(
        candidate,
        worker_model="qwen/qwen3-next-80b-a3b-thinking",
        max_steps=7,
    )

    assert payload["spec"]["model"] == "qwen/qwen3-next-80b-a3b-thinking"
    assert payload["spec"]["datasets"] == [
        "jwst_GS-MEDIUM-HST_F444W_demo",
        "jwst_GS-MEDIUM-HST_F090W_demo",
        "jwst_GS-MEDIUM-HST_F200W_demo",
    ]
    constraints = payload["spec"]["constraints"]
    assert constraints["max_steps"] == 7
    assert constraints["strict_real_data"] is True
    assert constraints["allowed_tools"] == DEFAULT_ALLOWED_WORKER_TOOLS
    assert WORKER_REPORT_PREFIX in payload["spec"]["objective"]


def test_build_worker_objective_includes_proposal_provenance() -> None:
    """Workers should receive additive proposal metadata for falsification-first review."""
    candidate = normalize_candidate_record(_sample_candidate())

    objective = build_worker_objective(candidate)

    assert "primary_channel" in objective
    assert "dropout_strict" in objective
    assert "measurement_status_by_filter" in objective
    assert "falsify the primary proposal hypothesis first" in objective.lower()


def test_extract_structured_worker_report_from_findings_text() -> None:
    """Structured worker reports should be recoverable from final findings."""
    findings = (
        "Some preamble\n"
        f"{WORKER_REPORT_PREFIX}\n"
        '{"candidate_id":"GS-MEDIUM-HST:source:545","verdict":"promote",'
        '"confidence":0.8,"interestingness":0.9}'
    )

    report = extract_structured_worker_report(findings)

    assert report is not None
    assert report["candidate_id"] == "GS-MEDIUM-HST:source:545"
    assert report["verdict"] == "promote"
    assert report["confidence"] == 0.8


def test_session_telemetry_writes_live_state_events_and_manifest(tmp_path: Path) -> None:
    """Telemetry should maintain GUI-friendly state, manifest, and message channels."""
    telemetry = SessionTelemetry(
        tmp_path,
        session_id="session_demo",
        objective="demo objective",
        worker_model="qwen/qwen3-next-80b-a3b-thinking",
        judge_model="anthropic/claude-3.5-sonnet",
        base_url="http://localhost:8000",
    )
    telemetry.set_status("dispatching_workers")
    telemetry.register_worker(
        "GS-MEDIUM-HST:source:545",
        candidate=normalize_candidate_record(_sample_candidate()).to_summary(),
        status="queued",
    )
    telemetry.emit(
        "worker_submitted",
        agent="supervisor",
        role="assistant",
        content="Dispatched demo worker.",
        payload={"run_id": 101},
    )

    state = json.loads((tmp_path / "live_state.json").read_text(encoding="utf-8"))
    events = (tmp_path / "event_stream.jsonl").read_text(encoding="utf-8").splitlines()
    manifest = json.loads((tmp_path / "session_manifest.json").read_text(encoding="utf-8"))

    assert state["status"] == "dispatching_workers"
    assert "GS-MEDIUM-HST:source:545" in state["workers"]
    assert len(events) == 1
    assert manifest["status"] == "dispatching_workers"
    assert (tmp_path / "operator_inbox.jsonl").exists()
    assert (tmp_path / "supervisor_outbox.jsonl").exists()


def test_normalize_worker_report_fixes_candidate_id_mismatch() -> None:
    """Candidate identity mismatches should be normalized with explicit schema errors."""
    candidate = normalize_candidate_record(_sample_candidate())

    report = normalize_worker_report(
        {
            "candidate_id": "wrong",
            "target": candidate.target,
            "source_id": candidate.source_id,
            "verdict": "promote",
            "confidence": 1.2,
            "interestingness": -0.2,
            "key_metrics": {},
            "evidence_summary": ["demo"],
            "artifact_paths": [],
            "next_checks": [],
        },
        candidate=CandidateSummary.model_validate(candidate.to_summary()),
        task_id=candidate.candidate_id,
        run_id=10,
        run_status="completed",
        status_reason=None,
        status_hints=[],
        final_findings_text="demo",
        result_metrics={"successful_tool_calls": 4, "reflection_count": 1, "artifact_count": 2},
        schema_errors=[],
    )

    assert report.candidate_id == candidate.candidate_id
    assert report.confidence == 1.0
    assert report.interestingness == 0.0
    assert report.tool_call_count == 4
    assert report.schema_errors


def test_select_top_reports_for_judge_prefers_channel_diversity() -> None:
    """Judge selection should not be monopolized by a single primary channel."""
    reports = [
        {
            "candidate": {"primary_channel": "dropout_strict"},
            "supervisor_rank_score": 3.0,
        },
        {
            "candidate": {"primary_channel": "dropout_strict"},
            "supervisor_rank_score": 2.9,
        },
        {
            "candidate": {"primary_channel": "color_color_outlier"},
            "supervisor_rank_score": 2.5,
        },
    ]

    selected = select_top_reports_for_judge(reports, 2)

    assert len(selected) == 2
    assert {item["candidate"]["primary_channel"] for item in selected} == {
        "dropout_strict",
        "color_color_outlier",
    }


@patch("discovery.supervisor_campaign.call_openrouter")
@patch("discovery.supervisor_campaign.safe_get_json")
@patch("discovery.supervisor_campaign.safe_post_json")
def test_run_supervisor_campaign_survives_judge_failure(
    mock_post_json,
    mock_get_json,
    mock_call_openrouter,
    tmp_path: Path,
) -> None:
    """Worker results should survive even if the judge model fails."""
    candidate_path = tmp_path / "shortlist.json"
    candidate_path.write_text(json.dumps([_sample_candidate()]), encoding="utf-8")

    validate_response = {"valid": True, "issues": []}
    create_response = {"id": 123}
    mock_post_json.side_effect = [(validate_response, None), (create_response, None)]
    mock_get_json.return_value = (
        {
            "status": "completed",
            "status_reason": "completed_successfully",
            "status_hints": [],
            "trajectory": [
                {
                    "role": "agent",
                    "content": (
                        f"Final Findings: {WORKER_REPORT_PREFIX}"
                        '{"candidate_id":"GS-MEDIUM-HST:source:545","verdict":"promote",'
                        '"target":"GS-MEDIUM-HST","source_id":545,"confidence":0.8,'
                        '"interestingness":0.9,"key_metrics":{},"evidence_summary":["x"],'
                        '"artifact_paths":[],"next_checks":[]}'
                    ),
                }
            ],
            "result": {
                "status": "success",
                "summary_metrics": {
                    "successful_tool_calls": 3,
                    "reflection_count": 1,
                    "artifact_count": 0,
                },
            },
        },
        None,
    )
    mock_call_openrouter.side_effect = RuntimeError("judge offline")

    with patch("discovery.supervisor_campaign.SESSION_ROOT", tmp_path / "sessions"):
        summary = run_supervisor_campaign(
            objective="demo",
            candidate_file=str(candidate_path),
            max_candidates=1,
            worker_model="qwen/qwen3-next-80b-a3b-thinking",
            judge_model="anthropic/claude-3.5-sonnet",
            max_in_flight=1,
            worker_max_steps=4,
            top_k_judge=1,
            base_url="http://localhost:8000",
            poll_interval=0,
            skip_judge=False,
        )

    assert summary["status"] == "completed_with_errors"
    assert summary["judge_report_path"] is None
    assert summary["tool_call_count_total"] == 3
