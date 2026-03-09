"""Typed session schemas and normalization helpers for supervisor campaigns."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _coerce_score(value: Any) -> float:
    """Clamp score-like values into the inclusive [0, 1] range."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, numeric))


class CandidatePosition(BaseModel):
    """Pixel position for a candidate summary."""

    x: float = 0.0
    y: float = 0.0


class CandidateSummary(BaseModel):
    """Compact candidate payload used across supervisor artifacts."""

    model_config = ConfigDict(extra="ignore")

    candidate_id: str
    target: str
    source_id: Optional[int] = None
    position: CandidatePosition = Field(default_factory=CandidatePosition)
    datasets: List[str] = Field(default_factory=list)
    reference_dataset: str
    blue_dataset: Optional[str] = None
    mid_dataset: Optional[str] = None
    ratio_f090_f444: Optional[float] = None
    validation_score: float = 0.0
    validation_status: Optional[str] = None
    red_snr_r3: Optional[float] = None
    coverage_fraction_r3: Optional[float] = None
    edge_distance_px: Optional[float] = None
    artifacts: List[str] = Field(default_factory=list)
    primary_channel: Optional[str] = None
    proposal_channels: List[str] = Field(default_factory=list)
    channel_scores: Dict[str, float] = Field(default_factory=dict)
    measurement_status_by_filter: Dict[str, str] = Field(default_factory=dict)
    completeness_score: float = 0.0
    novelty_score: float = 0.0
    falsification_flags: List[str] = Field(default_factory=list)
    disqualifying_flags: List[str] = Field(default_factory=list)
    portfolio_bucket: Optional[str] = None


class WorkerKeyMetrics(BaseModel):
    """Key quantitative checks produced by a worker."""

    ratio_f090_f444: Optional[float] = None
    red_snr_r3: Optional[float] = None
    coverage_fraction_r3: Optional[float] = None
    validation_score: Optional[float] = None


class WorkerReport(BaseModel):
    """Structured normalized worker report."""

    model_config = ConfigDict(extra="ignore")

    candidate_id: str
    target: str
    source_id: Optional[int] = None
    verdict: Literal["promote", "hold", "reject"] = "hold"
    confidence: float = 0.0
    interestingness: float = 0.0
    key_metrics: WorkerKeyMetrics = Field(default_factory=WorkerKeyMetrics)
    evidence_summary: List[str] = Field(default_factory=list)
    artifact_paths: List[str] = Field(default_factory=list)
    next_checks: List[str] = Field(default_factory=list)

    @field_validator("confidence", "interestingness", mode="before")
    @classmethod
    def _clamp_score(cls, value: Any) -> float:
        return _coerce_score(value)


class WorkerResultRecord(WorkerReport):
    """Persisted worker result with run/session metadata."""

    task_id: str
    run_id: int
    candidate: CandidateSummary
    final_findings_text: Optional[str] = None
    run_status: str
    status_reason: Optional[str] = None
    status_hints: List[str] = Field(default_factory=list)
    result_metrics: Dict[str, Any] = Field(default_factory=dict)
    tool_call_count: int = 0
    reflection_count: int = 0
    artifact_count: int = 0
    supervisor_rank_score: float = 0.0
    schema_errors: List[str] = Field(default_factory=list)


class JudgeTopCandidate(BaseModel):
    """One judge decision entry."""

    candidate_id: str
    decision: Literal["escalate", "watch", "discard"] = "watch"
    priority: int = 1
    rationale: str


class JudgeReport(BaseModel):
    """Structured judge output."""

    model_config = ConfigDict(extra="ignore")

    session_id: str
    summary: str
    top_candidates: List[JudgeTopCandidate] = Field(default_factory=list)
    campaign_recommendations: List[str] = Field(default_factory=list)
    schema_errors: List[str] = Field(default_factory=list)


class SessionWorkerSummary(BaseModel):
    """Compact worker summary for live state."""

    run_status: Optional[str] = None
    result_status: Optional[str] = None
    verdict: Optional[str] = None
    confidence: float = 0.0
    interestingness: float = 0.0
    successful_tool_calls: int = 0
    reflection_count: int = 0
    artifact_count: int = 0

    @field_validator("confidence", "interestingness", mode="before")
    @classmethod
    def _clamp_score(cls, value: Any) -> float:
        return _coerce_score(value)


class SessionWorkerState(BaseModel):
    """One worker entry in live state."""

    task_id: str
    run_id: Optional[int] = None
    status: str = "pending"
    candidate: CandidateSummary
    submitted_at: Optional[str] = None
    completed_at: Optional[str] = None
    status_reason: Optional[str] = None
    status_hints: List[str] = Field(default_factory=list)
    summary: Optional[SessionWorkerSummary] = None
    schema_errors: List[str] = Field(default_factory=list)


class OperatorMessage(BaseModel):
    """Append-only operator/supervisor message entry."""

    ts: str
    author: str
    role: Literal["operator", "supervisor"]
    content: str
    session_id: Optional[str] = None


class OperatorState(BaseModel):
    """GUI-related operator message metadata."""

    inbox_count: int = 0
    outbox_count: int = 0
    latest_operator_message: Optional[OperatorMessage] = None


class LiveSessionState(BaseModel):
    """Validated live session snapshot."""

    model_config = ConfigDict(extra="ignore")

    session_id: str
    objective: str
    worker_model: str
    judge_model: Optional[str] = None
    base_url: str
    status: str
    created_at: str
    updated_at: str
    latest_event_at: Optional[str] = None
    supervisor_thread: List[Dict[str, Any]] = Field(default_factory=list)
    workers: Dict[str, SessionWorkerState] = Field(default_factory=dict)
    artifacts: Dict[str, str] = Field(default_factory=dict)
    operator_state: OperatorState = Field(default_factory=OperatorState)
    manifest_path: Optional[str] = None
    session_errors: List[str] = Field(default_factory=list)


class SessionManifest(BaseModel):
    """Stable session manifest for local GUI and later control hooks."""

    session_id: str
    objective: str
    worker_model: str
    judge_model: Optional[str] = None
    base_url: str
    created_at: str
    updated_at: str
    status: str
    candidate_source: Optional[str] = None
    worker_results_path: Optional[str] = None
    judge_report_path: Optional[str] = None
    judge_markdown_path: Optional[str] = None
    summary_path: Optional[str] = None
    event_stream_path: Optional[str] = None
    live_state_path: Optional[str] = None
    operator_inbox_path: Optional[str] = None
    supervisor_outbox_path: Optional[str] = None
    worker_count: int = 0
    completed_workers: int = 0
    failed_workers: int = 0
    completed_with_errors: bool = False
    session_errors: List[str] = Field(default_factory=list)


def normalize_candidate_summary(candidate: Dict[str, Any]) -> CandidateSummary:
    """Validate and normalize candidate summary payloads."""
    return CandidateSummary.model_validate(candidate)


def normalize_worker_report(
    report: Dict[str, Any],
    *,
    candidate: CandidateSummary,
    task_id: str,
    run_id: int,
    run_status: str,
    status_reason: Optional[str],
    status_hints: List[str],
    final_findings_text: Optional[str],
    result_metrics: Dict[str, Any],
    schema_errors: Optional[List[str]] = None,
    supervisor_rank_score: float = 0.0,
) -> WorkerResultRecord:
    """Normalize one worker result record."""
    errors = list(schema_errors or [])
    sanitized = dict(report)
    if sanitized.get("candidate_id") != candidate.candidate_id:
        errors.append(
            "worker_report_candidate_id_mismatch:"
            f" expected={candidate.candidate_id} actual={sanitized.get('candidate_id')}"
        )
        sanitized["candidate_id"] = candidate.candidate_id
    sanitized.setdefault("target", candidate.target)
    sanitized.setdefault("source_id", candidate.source_id)
    sanitized.setdefault("key_metrics", {})

    record = WorkerResultRecord.model_validate(
        {
            **sanitized,
            "task_id": task_id,
            "run_id": run_id,
            "candidate": candidate.model_dump(),
            "final_findings_text": final_findings_text,
            "run_status": run_status,
            "status_reason": status_reason,
            "status_hints": list(status_hints),
            "result_metrics": dict(result_metrics or {}),
            "tool_call_count": int(result_metrics.get("successful_tool_calls") or 0),
            "reflection_count": int(result_metrics.get("reflection_count") or 0),
            "artifact_count": int(result_metrics.get("artifact_count") or 0),
            "supervisor_rank_score": float(supervisor_rank_score or 0.0),
            "schema_errors": errors,
        }
    )
    return record


def normalize_judge_report(
    payload: Dict[str, Any],
    *,
    session_id: str,
    schema_errors: Optional[List[str]] = None,
) -> JudgeReport:
    """Validate and normalize judge payloads."""
    normalized = dict(payload or {})
    errors = list(schema_errors or [])
    if normalized.get("session_id") != session_id:
        errors.append(
            f"judge_report_session_id_mismatch: expected={session_id} actual={normalized.get('session_id')}"
        )
        normalized["session_id"] = session_id
    normalized.setdefault("summary", "No summary returned.")
    normalized.setdefault("top_candidates", [])
    normalized.setdefault("campaign_recommendations", [])
    normalized["schema_errors"] = errors
    return JudgeReport.model_validate(normalized)
