"""Supervisor-driven discovery campaigns with worker/judge separation.

This module keeps the existing API/runner architecture intact and adds a thin
campaign supervisor that:
- dispatches many cheap autonomous worker runs,
- records a GUI-friendly event/state stream,
- aggregates structured worker reports, and
- optionally escalates the top results to a larger judge model.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core_api.config import LLM_API_KEY, LLM_API_URL, LLM_MODEL, OPENROUTER_API_KEY, get_model_slug
from discovery.session_schemas import (
    CandidateSummary,
    normalize_candidate_summary,
    normalize_judge_report,
    normalize_worker_report,
)
from discovery.telemetry import SessionTelemetry


DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_WORKER_MODEL = "qwen/qwen3-next-80b-a3b-thinking"
DEFAULT_WORKER_MAX_STEPS = 8
DEFAULT_MAX_IN_FLIGHT = 4
DEFAULT_TOP_K_JUDGE = 5
DEFAULT_POLL_INTERVAL = 5
WORKER_REPORT_PREFIX = "WORKER_REPORT_JSON:"
DEFAULT_ALLOWED_WORKER_TOOLS = [
    "candidate_evidence_bundle",
    "extract_photometry",
    "compute_color_index",
]
SESSION_ROOT = Path("research_output") / "supervisor_sessions"
DEFAULT_CANDIDATE_FILES = [
    Path("research_output/highz_shortlist.json"),
    Path("research_output/highz_validation_top10.json"),
    Path("research_output/highz_candidates.json"),
]


class CampaignError(RuntimeError):
    """Raised when a supervisor campaign cannot continue safely."""


@dataclass(frozen=True)
class CandidateRecord:
    """Structured view of a candidate passed to a worker run."""

    candidate_id: str
    target: str
    source_id: Optional[int]
    position: Dict[str, float]
    datasets: List[str]
    reference_dataset: str
    blue_dataset: Optional[str]
    mid_dataset: Optional[str]
    ratio_f090_f444: Optional[float]
    validation_score: float
    validation_status: Optional[str]
    red_snr_r3: Optional[float]
    coverage_fraction_r3: Optional[float]
    edge_distance_px: Optional[float]
    artifacts: List[str]
    primary_channel: Optional[str]
    proposal_channels: List[str]
    channel_scores: Dict[str, float]
    measurement_status_by_filter: Dict[str, str]
    completeness_score: float
    novelty_score: float
    falsification_flags: List[str]
    disqualifying_flags: List[str]
    portfolio_bucket: Optional[str]
    raw: Dict[str, Any]

    def to_summary(self) -> Dict[str, Any]:
        """Compact JSON-safe snapshot for telemetry and prompts."""
        return normalize_candidate_summary(
            {
            "candidate_id": self.candidate_id,
            "target": self.target,
            "source_id": self.source_id,
            "position": self.position,
            "datasets": self.datasets,
            "reference_dataset": self.reference_dataset,
            "blue_dataset": self.blue_dataset,
            "mid_dataset": self.mid_dataset,
            "ratio_f090_f444": self.ratio_f090_f444,
            "validation_score": self.validation_score,
            "validation_status": self.validation_status,
            "red_snr_r3": self.red_snr_r3,
            "coverage_fraction_r3": self.coverage_fraction_r3,
            "edge_distance_px": self.edge_distance_px,
            "artifacts": self.artifacts,
            "primary_channel": self.primary_channel,
            "proposal_channels": self.proposal_channels,
            "channel_scores": self.channel_scores,
            "measurement_status_by_filter": self.measurement_status_by_filter,
            "completeness_score": self.completeness_score,
            "novelty_score": self.novelty_score,
            "falsification_flags": self.falsification_flags,
            "disqualifying_flags": self.disqualifying_flags,
            "portfolio_bucket": self.portfolio_bucket,
            }
        ).model_dump()


def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def normalize_base_url(base_url: str) -> str:
    """Normalize API base URLs to omit the trailing slash."""
    return (base_url or DEFAULT_BASE_URL).rstrip("/")


def load_candidate_records(
    candidate_file: Optional[str],
    *,
    max_candidates: int,
) -> tuple[List[CandidateRecord], Path]:
    """Load and rank candidate records from the preferred artifact files."""
    candidate_path = Path(candidate_file) if candidate_file else None
    paths = [candidate_path] if candidate_path else DEFAULT_CANDIDATE_FILES

    chosen_path: Optional[Path] = None
    payload: Optional[List[Dict[str, Any]]] = None
    for path in paths:
        if path is None or not path.exists():
            continue
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, list) and loaded:
            chosen_path = path
            payload = loaded
            break

    if chosen_path is None or payload is None:
        searched = ", ".join(str(path) for path in paths if path is not None)
        raise CampaignError(
            "No candidate artifact file was available. "
            f"Tried: {searched}. Rebuild source outputs first."
        )

    candidates = [normalize_candidate_record(item) for item in payload]
    candidates.sort(key=_candidate_sort_key, reverse=True)
    return candidates[: max(max_candidates, 1)], chosen_path


def normalize_candidate_record(item: Dict[str, Any]) -> CandidateRecord:
    """Normalize a raw candidate JSON object into a typed record."""
    target = str(item.get("target") or "unknown-target")
    source_id = item.get("source_id")
    source_id = int(source_id) if source_id is not None else None
    position = item.get("position") or {}
    x = float(position.get("x") or 0.0)
    y = float(position.get("y") or 0.0)
    reference_dataset = str(
        item.get("reference_dataset")
        or item.get("f444_dataset")
        or item.get("reference")
        or ""
    )
    if not reference_dataset:
        raise CampaignError(f"Candidate is missing a reference dataset: {item}")

    datasets: List[str] = []
    for key in ("reference_dataset", "f444_dataset", "f090_dataset", "f200_dataset"):
        value = item.get(key)
        if isinstance(value, str) and value and value not in datasets:
            datasets.append(value)
    if reference_dataset not in datasets:
        datasets.insert(0, reference_dataset)

    artifacts: List[str] = []
    for key in ("evidence_output_path", "evidence_sidecar_path"):
        value = item.get(key)
        if isinstance(value, str) and value:
            artifacts.append(value)
    for artifact in item.get("artifacts") or []:
        if isinstance(artifact, dict):
            value = artifact.get("path")
        else:
            value = artifact
        if isinstance(value, str) and value and value not in artifacts:
            artifacts.append(value)

    candidate_id = f"{target}:source:{source_id if source_id is not None else 'na'}"
    return CandidateRecord(
        candidate_id=candidate_id,
        target=target,
        source_id=source_id,
        position={"x": x, "y": y},
        datasets=datasets,
        reference_dataset=reference_dataset,
        blue_dataset=_optional_string(item.get("f090_dataset")),
        mid_dataset=_optional_string(item.get("f200_dataset")),
        ratio_f090_f444=_optional_float(item.get("ratio_f090_f444")),
        validation_score=float(item.get("validation_score") or 0.0),
        validation_status=_optional_string(item.get("validation_status")),
        red_snr_r3=_optional_float(item.get("red_snr_r3")),
        coverage_fraction_r3=_optional_float(item.get("coverage_fraction_r3")),
        edge_distance_px=_optional_float(item.get("edge_distance_px")),
        artifacts=artifacts,
        primary_channel=_optional_string(item.get("primary_channel")),
        proposal_channels=[
            str(channel)
            for channel in (item.get("proposal_channels") or [])
            if isinstance(channel, str) and channel.strip()
        ],
        channel_scores={
            str(key): float(value)
            for key, value in (item.get("channel_scores") or {}).items()
            if isinstance(key, str)
        },
        measurement_status_by_filter={
            str(key): str(value)
            for key, value in (item.get("measurement_status_by_filter") or {}).items()
            if isinstance(key, str)
        },
        completeness_score=float(item.get("completeness_score") or 0.0),
        novelty_score=float(item.get("novelty_score") or 0.0),
        falsification_flags=[
            str(flag)
            for flag in (item.get("falsification_flags") or [])
            if isinstance(flag, str) and flag.strip()
        ],
        disqualifying_flags=[
            str(flag)
            for flag in (item.get("disqualifying_flags") or [])
            if isinstance(flag, str) and flag.strip()
        ],
        portfolio_bucket=_optional_string(item.get("portfolio_bucket")),
        raw=dict(item),
    )


def _optional_string(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _candidate_sort_key(candidate: CandidateRecord) -> tuple[float, float, float]:
    """Rank candidates conservatively for cheap-worker evaluation."""
    ratio_score = 0.0
    if candidate.ratio_f090_f444 is not None:
        ratio_score = max(0.0, min(1.0, (0.2 - candidate.ratio_f090_f444) / 0.2))
    snr = candidate.red_snr_r3 or 0.0
    return (candidate.validation_score, candidate.completeness_score, ratio_score + snr)


def build_worker_objective(candidate: CandidateRecord) -> str:
    """Build a narrow worker objective optimized for cheap autonomous loops."""
    comparison_datasets = [ds for ds in (candidate.blue_dataset, candidate.mid_dataset) if ds]
    artifact_text = ", ".join(candidate.artifacts) if candidate.artifacts else "none"
    return f"""
You are a low-cost autonomous discovery worker operating under a supervisor.
Evaluate exactly one JWST candidate and decide whether it is interesting enough
to escalate to an expensive judge model.

Candidate identity:
- candidate_id: {candidate.candidate_id}
- target: {candidate.target}
- source_id: {candidate.source_id}
- x: {candidate.position['x']:.3f}
- y: {candidate.position['y']:.3f}

Prior evidence:
- ratio_f090_f444: {candidate.ratio_f090_f444}
- validation_score: {candidate.validation_score:.4f}
- validation_status: {candidate.validation_status}
- red_snr_r3: {candidate.red_snr_r3}
- coverage_fraction_r3: {candidate.coverage_fraction_r3}
- edge_distance_px: {candidate.edge_distance_px}
- primary_channel: {candidate.primary_channel}
- proposal_channels: {json.dumps(candidate.proposal_channels, indent=2)}
- completeness_score: {candidate.completeness_score:.4f}
- novelty_score: {candidate.novelty_score:.4f}
- measurement_status_by_filter: {json.dumps(candidate.measurement_status_by_filter, indent=2)}
- falsification_flags: {json.dumps(candidate.falsification_flags, indent=2)}
- disqualifying_flags: {json.dumps(candidate.disqualifying_flags, indent=2)}
- known_artifacts: {artifact_text}

Allowed datasets for this worker:
{json.dumps(candidate.datasets, indent=2)}

Recommended plan:
1. Falsify the primary proposal hypothesis first using real measurements.
2. Use `candidate_evidence_bundle` for a fresh evidence panel at the exact source.
3. Re-check dropout-like behavior with `extract_photometry` in the blue and reference bands.
4. Use `compute_color_index` only if you have positive background-subtracted fluxes.
5. Prefer 3 to 5 successful tool calls total. Do not over-explore.

Finish rule:
- Promote only if the source still looks interesting after re-checking coverage, S/N, and artifacts.
- Reject or mark uncertain if evidence is weak, off-chip, low-coverage, or inconsistent.

When you finish, the findings string MUST begin with:
{WORKER_REPORT_PREFIX}

Immediately after that prefix, emit one JSON object with this schema:
{{
  "candidate_id": "{candidate.candidate_id}",
  "target": "{candidate.target}",
  "source_id": {json.dumps(candidate.source_id)},
  "verdict": "promote|hold|reject",
  "confidence": 0.0,
  "interestingness": 0.0,
  "key_metrics": {{
    "ratio_f090_f444": null,
    "red_snr_r3": null,
    "coverage_fraction_r3": null,
    "validation_score": {candidate.validation_score:.4f}
  }},
  "evidence_summary": ["short fact 1", "short fact 2"],
  "artifact_paths": [],
  "next_checks": ["check 1", "check 2"]
}}

The JSON object must be concise, valid, and fully self-contained.
Comparison datasets available for evidence panels:
{json.dumps(comparison_datasets, indent=2)}
""".strip()


def build_worker_payload(
    candidate: CandidateRecord,
    *,
    worker_model: str,
    max_steps: int,
    allowed_tools: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a worker run payload for the existing /runs API."""
    return {
        "spec": {
            "objective": build_worker_objective(candidate),
            "datasets": candidate.datasets,
            "steps": None,
            "constraints": {
                "max_steps": max_steps,
                "max_cost": 0.6,
                "strict_real_data": True,
                "min_successful_tool_calls": 3,
                "min_reflections": 1,
                "allowed_tools": list(allowed_tools or DEFAULT_ALLOWED_WORKER_TOOLS),
            },
            "model": worker_model,
        }
    }


def post_json(base_url: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST JSON and return the decoded response body."""
    response = requests.post(f"{base_url}{path}", json=payload, timeout=60)
    response.raise_for_status()
    return response.json()


def get_json(base_url: str, path: str) -> Dict[str, Any]:
    """GET JSON and return the decoded response body."""
    response = requests.get(f"{base_url}{path}", timeout=30)
    response.raise_for_status()
    return response.json()


def safe_post_json(base_url: str, path: str, payload: Dict[str, Any]) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """POST JSON and return either payload or an error string."""
    try:
        return post_json(base_url, path, payload), None
    except requests.RequestException as exc:
        return None, str(exc)


def safe_get_json(base_url: str, path: str) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """GET JSON and return either payload or an error string."""
    try:
        return get_json(base_url, path), None
    except requests.RequestException as exc:
        return None, str(exc)


def find_final_findings_text(run_payload: Dict[str, Any]) -> Optional[str]:
    """Extract the final findings string from a completed run payload."""
    for message in reversed(run_payload.get("trajectory") or []):
        content = message.get("content")
        if not isinstance(content, str):
            continue
        if content.startswith("Final Findings:"):
            return content[len("Final Findings:") :].strip()
    log_summary = ((run_payload.get("result") or {}).get("log_summary")) or ""
    if "Final Findings:" in log_summary:
        return log_summary.split("Final Findings:", 1)[1].strip()
    return None


def extract_first_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Extract the first JSON object from arbitrary text."""
    decoder = json.JSONDecoder()
    for index, char in enumerate(text or ""):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def extract_structured_worker_report(findings_text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse the structured worker report from final findings text."""
    if not findings_text:
        return None
    if WORKER_REPORT_PREFIX in findings_text:
        findings_text = findings_text.split(WORKER_REPORT_PREFIX, 1)[1].strip()
    return extract_first_json_object(findings_text)


def build_fallback_worker_report(
    candidate: CandidateRecord,
    run_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a deterministic fallback report if the worker output is malformed."""
    result = run_payload.get("result") or {}
    error_text = result.get("error") or run_payload.get("error_message")
    verdict = "reject" if run_payload.get("status") == "failed" else "hold"
    evidence_summary = ["Worker did not return a structured report."]
    if error_text:
        evidence_summary.append(str(error_text)[:180])
    return {
        "candidate_id": candidate.candidate_id,
        "target": candidate.target,
        "source_id": candidate.source_id,
        "verdict": verdict,
        "confidence": 0.2 if verdict == "hold" else 0.0,
        "interestingness": 0.2 if verdict == "hold" else 0.0,
        "key_metrics": {
            "ratio_f090_f444": candidate.ratio_f090_f444,
            "red_snr_r3": candidate.red_snr_r3,
            "coverage_fraction_r3": candidate.coverage_fraction_r3,
            "validation_score": candidate.validation_score,
        },
        "evidence_summary": evidence_summary,
        "artifact_paths": list(candidate.artifacts),
        "next_checks": ["Re-run candidate with a larger model before escalation."],
    }


def summarize_worker_for_state(
    run_payload: Dict[str, Any],
    report: Dict[str, Any],
) -> Dict[str, Any]:
    """Compact worker summary for live session state."""
    result = run_payload.get("result") or {}
    metrics = result.get("summary_metrics") or {}
    return {
        "run_status": run_payload.get("status"),
        "result_status": result.get("status"),
        "verdict": report.get("verdict"),
        "confidence": report.get("confidence"),
        "interestingness": report.get("interestingness"),
        "successful_tool_calls": metrics.get("successful_tool_calls"),
        "tool_call_count": metrics.get("successful_tool_calls"),
        "reflection_count": metrics.get("reflection_count"),
        "artifact_count": metrics.get("artifact_count"),
    }


def rank_worker_reports(worker_reports: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rank worker outputs for judge escalation."""
    verdict_bonus = {"promote": 1.0, "hold": 0.45, "reject": 0.0}

    def score(report: Dict[str, Any]) -> float:
        candidate = report.get("candidate") or {}
        disqualifying_flags = list(candidate.get("disqualifying_flags") or [])
        penalty = 0.20 if disqualifying_flags else 0.0
        return (
            0.35 * float(report.get("interestingness") or 0.0)
            + 0.30 * float(report.get("confidence") or 0.0)
            + 0.15 * float(candidate.get("validation_score") or 0.0)
            + 0.10 * float(candidate.get("completeness_score") or 0.0)
            + 0.10 * float(candidate.get("novelty_score") or 0.0)
            + verdict_bonus.get(str(report.get("verdict") or "hold"), 0.0)
            - penalty
        )

    ranked = [dict(item, supervisor_rank_score=score(item)) for item in worker_reports]
    ranked.sort(key=lambda item: float(item.get("supervisor_rank_score") or 0.0), reverse=True)
    return ranked


def select_top_reports_for_judge(
    ranked_reports: List[Dict[str, Any]],
    top_k: int,
) -> List[Dict[str, Any]]:
    """Select top judge candidates with light channel diversification."""
    if top_k <= 0:
        return []

    selected: List[Dict[str, Any]] = []
    seen_channels: set[str] = set()
    for report in ranked_reports:
        if len(selected) >= top_k:
            break
        candidate = report.get("candidate") or {}
        channel = str(candidate.get("primary_channel") or "")
        if channel and channel not in seen_channels:
            selected.append(report)
            seen_channels.add(channel)

    if len(selected) >= top_k:
        return selected[:top_k]

    selected_ids = {id(item) for item in selected}
    for report in ranked_reports:
        if len(selected) >= top_k:
            break
        if id(report) in selected_ids:
            continue
        selected.append(report)
        selected_ids.add(id(report))
    return selected


def call_openrouter(model: str, messages: List[Dict[str, str]]) -> str:
    """Call the configured LLM provider directly for judge/supervisor synthesis."""
    api_key = OPENROUTER_API_KEY or LLM_API_KEY
    if not api_key:
        raise CampaignError("LLM_API_KEY or OPENROUTER_API_KEY must be configured.")

    payload = {
        "model": get_model_slug(model),
        "messages": messages,
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    response = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=120)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def build_judge_prompt(
    objective: str,
    session_id: str,
    ranked_reports: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """Build a strict JSON judge prompt from top worker outputs."""
    system_prompt = """
You are a supervising scientific judge. Review worker reports from a JWST
discovery campaign and decide which candidates deserve expensive follow-up.

Return exactly one JSON object with this schema:
{
  "session_id": "...",
  "summary": "short paragraph",
  "top_candidates": [
    {
      "candidate_id": "...",
      "decision": "escalate|watch|discard",
      "priority": 1,
      "rationale": "short reason"
    }
  ],
  "campaign_recommendations": ["next step 1", "next step 2"]
}
""".strip()
    user_prompt = json.dumps(
        {
            "session_id": session_id,
            "objective": objective,
            "worker_reports": ranked_reports,
        },
        indent=2,
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def render_judge_markdown(judge_payload: Dict[str, Any]) -> str:
    """Render a compact markdown summary for human review."""
    lines = [
        f"# Supervisor Judge Report",
        "",
        f"Session: `{judge_payload.get('session_id')}`",
        "",
        judge_payload.get("summary") or "No summary returned.",
        "",
        "## Top Candidates",
    ]
    for item in judge_payload.get("top_candidates") or []:
        lines.append(
            f"- `{item.get('candidate_id')}`: {item.get('decision')} "
            f"(priority={item.get('priority')}) - {item.get('rationale')}"
        )
    lines.append("")
    lines.append("## Recommendations")
    for item in judge_payload.get("campaign_recommendations") or []:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def run_supervisor_campaign(
    *,
    objective: str,
    candidate_file: Optional[str],
    max_candidates: int,
    worker_model: str,
    judge_model: Optional[str],
    max_in_flight: int,
    worker_max_steps: int,
    top_k_judge: int,
    base_url: str,
    poll_interval: int,
    skip_judge: bool,
) -> Dict[str, Any]:
    """Run a full supervisor campaign and persist session artifacts."""
    base_url = normalize_base_url(base_url)
    candidates, source_path = load_candidate_records(candidate_file, max_candidates=max_candidates)
    session_id = f"supervisor_{utc_now_iso()}"
    session_dir = SESSION_ROOT / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    telemetry = SessionTelemetry(
        session_dir,
        session_id=session_id,
        objective=objective,
        worker_model=worker_model,
        judge_model=judge_model,
        base_url=base_url,
    )
    telemetry.set_artifact("candidate_source", str(source_path))
    telemetry.emit(
        "supervisor_message",
        agent="supervisor",
        role="assistant",
        content=(
            f"Loaded {len(candidates)} candidates from {source_path} and preparing "
            f"cheap worker runs with model {worker_model}."
        ),
        payload={"candidate_source": str(source_path)},
    )
    telemetry.set_status("dispatching_workers")

    pending = list(candidates)
    active: Dict[str, Dict[str, Any]] = {}
    completed_reports: List[Dict[str, Any]] = []
    judge_report_path: Optional[Path] = None
    judge_markdown_path: Optional[Path] = None

    def _current_terminal_status() -> str:
        return "completed_with_errors" if telemetry.state.get("session_errors") else "completed"

    def _write_summary() -> Dict[str, Any]:
        summary_payload: Dict[str, Any] = {
            "session_id": session_id,
            "objective": objective,
            "candidate_source": str(source_path),
            "worker_model": worker_model,
            "judge_model": judge_model,
            "status": telemetry.state.get("status"),
            "worker_count": len(completed_reports),
            "worker_results_path": str(worker_results_path),
            "judge_report_path": str(judge_report_path) if judge_report_path else None,
            "judge_markdown_path": str(judge_markdown_path) if judge_markdown_path else None,
            "session_errors": list(telemetry.state.get("session_errors") or []),
            "operator_inbox_path": str(telemetry.operator_inbox_path),
            "supervisor_outbox_path": str(telemetry.supervisor_outbox_path),
            "tool_call_count_total": sum(int(item.get("tool_call_count") or 0) for item in completed_reports),
        }
        summary_path = session_dir / "campaign_summary.json"
        summary_path.write_text(
            json.dumps(summary_payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        telemetry.set_artifact("summary", str(summary_path))
        return summary_payload

    while pending or active:
        while pending and len(active) < max(max_in_flight, 1):
            candidate = pending.pop(0)
            task_id = candidate.candidate_id
            payload = build_worker_payload(
                candidate,
                worker_model=worker_model,
                max_steps=worker_max_steps,
            )
            telemetry.register_worker(task_id, candidate=candidate.to_summary(), status="validating")
            validation, validation_error = safe_post_json(base_url, "/runs/validate", payload)
            if validation_error:
                telemetry.record_session_error(f"validation_request_failed:{task_id}:{validation_error}")
                telemetry.emit(
                    "worker_validation_error",
                    agent="supervisor",
                    role="assistant",
                    content=f"Skipping {task_id}; validation request failed.",
                    payload={"task_id": task_id, "error": validation_error},
                )
                telemetry.update_worker(
                    task_id,
                    status="validation_failed",
                    status_reason="validation_request_failed",
                    status_hints=[validation_error],
                    summary={"issues": [validation_error]},
                    schema_errors=[validation_error],
                    completed=True,
                )
                continue
            if not validation.get("valid", False):
                telemetry.emit(
                    "worker_validation_failed",
                    agent="supervisor",
                    role="assistant",
                    content=f"Skipping {task_id}; preflight validation failed.",
                    payload={"task_id": task_id, "issues": validation.get("issues", [])},
                )
                telemetry.update_worker(
                    task_id,
                    status="validation_failed",
                    summary={"issues": validation.get("issues", [])},
                    schema_errors=[str(issue.get("code")) for issue in validation.get("issues", [])],
                    completed=True,
                )
                continue

            created, submission_error = safe_post_json(base_url, "/runs/", payload)
            if submission_error:
                telemetry.record_session_error(f"worker_submission_failed:{task_id}:{submission_error}")
                telemetry.emit(
                    "worker_submission_failed",
                    agent="supervisor",
                    role="assistant",
                    content=f"Failed to submit worker for {task_id}.",
                    payload={"task_id": task_id, "error": submission_error},
                )
                telemetry.update_worker(
                    task_id,
                    status="submission_failed",
                    status_reason="worker_submission_failed",
                    status_hints=[submission_error],
                    schema_errors=[submission_error],
                    completed=True,
                )
                continue
            try:
                run_id = int(created["id"])
            except (KeyError, TypeError, ValueError) as exc:
                submission_error = f"Invalid run creation payload for {task_id}: {exc}"
                telemetry.record_session_error(submission_error)
                telemetry.update_worker(
                    task_id,
                    status="submission_failed",
                    status_reason="worker_submission_invalid_payload",
                    status_hints=[submission_error],
                    schema_errors=[submission_error],
                    completed=True,
                )
                continue
            active[task_id] = {"candidate": candidate, "run_id": run_id}
            telemetry.update_worker(task_id, status="queued", run_id=run_id)
            telemetry.emit(
                "worker_submitted",
                agent="supervisor",
                role="assistant",
                content=f"Dispatched worker for {task_id} as run {run_id}.",
                payload={"task_id": task_id, "run_id": run_id},
            )

        if not active:
            continue

        time.sleep(max(poll_interval, 1))

        finished_task_ids: List[str] = []
        for task_id, active_entry in list(active.items()):
            run_id = int(active_entry["run_id"])
            run_payload, poll_error = safe_get_json(base_url, f"/runs/{run_id}")
            if poll_error:
                telemetry.record_session_error(f"worker_poll_failed:{task_id}:{poll_error}")
                telemetry.emit(
                    "worker_poll_failed",
                    agent="supervisor",
                    role="assistant",
                    content=f"Polling failed for {task_id}; marking worker as failed.",
                    payload={"task_id": task_id, "run_id": run_id, "error": poll_error},
                )
                telemetry.update_worker(
                    task_id,
                    status="poll_failed",
                    status_reason="worker_poll_failed",
                    status_hints=[poll_error],
                    schema_errors=[poll_error],
                    completed=True,
                )
                finished_task_ids.append(task_id)
                continue
            status = str(run_payload.get("status") or "unknown")
            telemetry.update_worker(
                task_id,
                status=status,
                status_reason=run_payload.get("status_reason"),
                status_hints=run_payload.get("status_hints") or [],
            )

            if status not in {"completed", "failed"}:
                continue

            candidate = active_entry["candidate"]
            findings_text = find_final_findings_text(run_payload)
            parsed_report = extract_structured_worker_report(findings_text)
            schema_errors: List[str] = []
            if parsed_report is None:
                schema_errors.append("worker_report_missing_or_malformed")
                parsed_report = build_fallback_worker_report(candidate, run_payload)

            candidate_summary = CandidateSummary.model_validate(candidate.to_summary())
            result_metrics = ((run_payload.get("result") or {}).get("summary_metrics") or {})
            normalized_report = normalize_worker_report(
                parsed_report,
                candidate=candidate_summary,
                task_id=task_id,
                run_id=run_id,
                run_status=status,
                status_reason=run_payload.get("status_reason"),
                status_hints=run_payload.get("status_hints") or [],
                final_findings_text=findings_text,
                result_metrics=result_metrics,
                schema_errors=schema_errors,
            )
            completed_reports.append(normalized_report.model_dump())
            if normalized_report.schema_errors:
                telemetry.record_session_error(
                    f"worker_schema_issue:{task_id}:{';'.join(normalized_report.schema_errors)}"
                )

            telemetry.update_worker(
                task_id,
                status=status,
                summary=summarize_worker_for_state(run_payload, normalized_report.model_dump()),
                schema_errors=normalized_report.schema_errors,
                completed=True,
            )
            telemetry.emit(
                "worker_completed",
                agent="worker",
                role="assistant",
                content=(
                    f"Worker {task_id} finished with verdict={normalized_report.verdict} "
                    f"confidence={normalized_report.confidence} "
                    f"tool_calls={normalized_report.tool_call_count}."
                ),
                payload={
                    "task_id": task_id,
                    "run_id": run_id,
                    "verdict": normalized_report.verdict,
                    "confidence": normalized_report.confidence,
                    "tool_call_count": normalized_report.tool_call_count,
                },
            )
            finished_task_ids.append(task_id)

        for task_id in finished_task_ids:
            active.pop(task_id, None)

    ranked_reports = rank_worker_reports(completed_reports)
    worker_results_path = session_dir / "worker_results.json"
    worker_results_path.write_text(
        json.dumps(ranked_reports, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    telemetry.set_artifact("worker_results", str(worker_results_path))

    if skip_judge:
        telemetry.emit(
            "supervisor_message",
            agent="supervisor",
            role="assistant",
            content="Worker phase completed; judge phase was skipped by configuration.",
            payload={"worker_count": len(ranked_reports)},
        )
        telemetry.set_status(_current_terminal_status())
        return _write_summary()

    top_reports = select_top_reports_for_judge(ranked_reports, max(top_k_judge, 1))
    telemetry.set_status("running_judge")
    telemetry.emit(
        "judge_started",
        agent="supervisor",
        role="assistant",
        content=f"Escalating {len(top_reports)} worker reports to judge model {judge_model}.",
        payload={"top_k": len(top_reports)},
    )

    try:
        judge_response_text = call_openrouter(
            judge_model or LLM_MODEL,
            build_judge_prompt(objective, session_id, top_reports),
        )
        judge_schema_errors: List[str] = []
        parsed_judge_payload = extract_first_json_object(judge_response_text)
        if parsed_judge_payload is None:
            judge_schema_errors.append("judge_report_missing_json")
            parsed_judge_payload = {
                "session_id": session_id,
                "summary": judge_response_text,
                "top_candidates": [],
                "campaign_recommendations": [],
            }
        normalized_judge = normalize_judge_report(
            parsed_judge_payload,
            session_id=session_id,
            schema_errors=judge_schema_errors,
        )
        if normalized_judge.schema_errors:
            telemetry.record_session_error(
                f"judge_schema_issue:{';'.join(normalized_judge.schema_errors)}"
            )

        judge_report_path = session_dir / "judge_report.json"
        judge_report_path.write_text(
            json.dumps(normalized_judge.model_dump(), indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        judge_markdown_path = session_dir / "judge_report.md"
        judge_markdown_path.write_text(
            render_judge_markdown(normalized_judge.model_dump()),
            encoding="utf-8",
        )
        telemetry.set_artifact("judge_report", str(judge_report_path))
        telemetry.set_artifact("judge_markdown", str(judge_markdown_path))
        telemetry.emit(
            "judge_completed",
            agent="judge",
            role="assistant",
            content="Judge model returned a ranked escalation summary.",
            payload={"judge_report_path": str(judge_report_path)},
        )
    except Exception as exc:
        error_text = f"judge_failed:{exc}"
        telemetry.record_session_error(error_text)
        telemetry.emit(
            "judge_failed",
            agent="supervisor",
            role="assistant",
            content="Judge synthesis failed; worker outputs were still preserved.",
            payload={"error": str(exc)},
        )

    telemetry.set_status(_current_terminal_status())
    return _write_summary()


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for supervisor campaigns."""
    parser = argparse.ArgumentParser(
        description="Run a supervisor-driven JWST discovery campaign.",
    )
    parser.add_argument(
        "--objective",
        default="Triaging JWST high-z candidates with cheap workers before expensive review.",
        help="Supervisor campaign objective.",
    )
    parser.add_argument(
        "--candidate-file",
        default=None,
        help="Optional candidate JSON file. Falls back to research_output shortlist/top10/candidates.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=8,
        help="Maximum number of candidates to dispatch to cheap worker runs.",
    )
    parser.add_argument(
        "--worker-model",
        default=DEFAULT_WORKER_MODEL,
        help="Worker model used for cheap autonomous loops.",
    )
    parser.add_argument(
        "--judge-model",
        default=LLM_MODEL,
        help="Judge model used for final synthesis. Defaults to the repo LLM model.",
    )
    parser.add_argument(
        "--skip-judge",
        action="store_true",
        help="Run only the worker phase and skip judge synthesis.",
    )
    parser.add_argument(
        "--max-in-flight",
        type=int,
        default=DEFAULT_MAX_IN_FLIGHT,
        help="Maximum concurrent worker runs.",
    )
    parser.add_argument(
        "--worker-max-steps",
        type=int,
        default=DEFAULT_WORKER_MAX_STEPS,
        help="Maximum tool-using steps allowed per worker run.",
    )
    parser.add_argument(
        "--top-k-judge",
        type=int,
        default=DEFAULT_TOP_K_JUDGE,
        help="How many top worker reports to escalate to the judge.",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=DEFAULT_POLL_INTERVAL,
        help="Polling interval in seconds while monitoring worker runs.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Science OS API base URL.",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    summary = run_supervisor_campaign(
        objective=args.objective,
        candidate_file=args.candidate_file,
        max_candidates=args.max_candidates,
        worker_model=args.worker_model,
        judge_model=None if args.skip_judge else args.judge_model,
        max_in_flight=args.max_in_flight,
        worker_max_steps=args.worker_max_steps,
        top_k_judge=args.top_k_judge,
        base_url=args.base_url,
        poll_interval=args.poll_interval,
        skip_judge=args.skip_judge,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
