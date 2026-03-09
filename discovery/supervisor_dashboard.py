#!/usr/bin/env python
"""Lightweight local GUI for supervisor campaign sessions.

The dashboard reads `live_state.json` and `event_stream.jsonl` from
`research_output/supervisor_sessions/*` and serves a small browser UI.
It intentionally has no non-stdlib runtime dependencies.
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from discovery.session_schemas import LiveSessionState, OperatorMessage
from discovery.supervisor_campaign import SESSION_ROOT


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _read_json(path: Path, default: Any) -> Any:
    """Read a JSON file if it exists; otherwise return `default`."""
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Atomically write a JSON payload."""
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    temp_path.replace(path)


def append_operator_message(
    session_dir: Path,
    *,
    author: str,
    content: str,
) -> Dict[str, Any]:
    """Append one operator message and update live state metadata."""
    content = (content or "").strip()
    if not content:
        raise ValueError("Operator message content cannot be empty.")

    state_path = session_dir / "live_state.json"
    state = _read_json(state_path, {})
    if not state:
        raise FileNotFoundError(f"Missing live state for session: {session_dir}")

    message = OperatorMessage(
        ts=state.get("updated_at") or "",
        author=author.strip() or "operator",
        role="operator",
        content=content,
        session_id=state.get("session_id"),
    )
    if not message.ts:
        from datetime import UTC, datetime

        message.ts = datetime.now(UTC).isoformat()

    inbox_path = session_dir / "operator_inbox.jsonl"
    with inbox_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(message.model_dump(), ensure_ascii=True) + "\n")

    operator_state = state.setdefault("operator_state", {})
    operator_state["inbox_count"] = int(operator_state.get("inbox_count") or 0) + 1
    operator_state.setdefault("outbox_count", 0)
    operator_state["latest_operator_message"] = message.model_dump()

    validated_state = LiveSessionState.model_validate(state).model_dump()
    _write_json(state_path, validated_state)
    return message.model_dump()


def list_sessions(session_root: Path = SESSION_ROOT) -> List[Dict[str, Any]]:
    """Return known supervisor sessions sorted by recency."""
    if not session_root.exists():
        return []

    sessions: List[Dict[str, Any]] = []
    for child in session_root.iterdir():
        if not child.is_dir():
            continue
        state = _read_json(child / "live_state.json", {})
        sessions.append(
            {
                "session_id": state.get("session_id") or child.name,
                "status": state.get("status") or "unknown",
                "objective": state.get("objective") or "",
                "created_at": state.get("created_at"),
                "updated_at": state.get("updated_at"),
                "path": str(child),
            }
        )

    sessions.sort(
        key=lambda item: (
            item.get("updated_at") or "",
            item.get("created_at") or "",
            item.get("session_id") or "",
        ),
        reverse=True,
    )
    return sessions


def resolve_session_dir(
    session_id: Optional[str],
    session_root: Path = SESSION_ROOT,
) -> Optional[Path]:
    """Resolve a session directory by id, defaulting to the newest session."""
    sessions = list_sessions(session_root)
    if not sessions:
        return None

    if not session_id:
        return Path(sessions[0]["path"])

    candidate = session_root / session_id
    if candidate.exists() and candidate.is_dir():
        return candidate
    return None


def load_live_state(session_dir: Path) -> Dict[str, Any]:
    """Load the live state snapshot for one session."""
    return _read_json(session_dir / "live_state.json", {})


def load_events(
    session_dir: Path,
    *,
    after: int = 0,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """Load recent events, adding a stable 1-based sequence number."""
    event_path = session_dir / "event_stream.jsonl"
    if not event_path.exists():
        return []

    events: List[Dict[str, Any]] = []
    with event_path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            if index <= max(after, 0):
                continue
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event["seq"] = index
            events.append(event)

    if limit > 0 and len(events) > limit:
        events = events[-limit:]
    return events


def build_session_payload(
    session_dir: Path,
    *,
    event_after: int = 0,
    event_limit: int = 200,
) -> Dict[str, Any]:
    """Build the dashboard payload for one session."""
    state = load_live_state(session_dir)
    return {
        "state": state,
        "events": load_events(session_dir, after=event_after, limit=event_limit),
    }


def _send_json(handler: BaseHTTPRequestHandler, payload: Dict[str, Any], status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _send_html(handler: BaseHTTPRequestHandler, html: str) -> None:
    body = html.encode("utf-8")
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def render_dashboard_html() -> str:
    """Return the single-page dashboard HTML."""
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Supervisor Dashboard</title>
  <style>
    :root {
      --bg: #f4efe5;
      --panel: #fffaf0;
      --panel-strong: #f7f0de;
      --ink: #1f2937;
      --muted: #6b7280;
      --accent: #0f766e;
      --accent-soft: #d9f3ef;
      --line: #d6cbb6;
      --ok: #166534;
      --warn: #a16207;
      --bad: #991b1b;
      --mono: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
      --sans: "Segoe UI", "Helvetica Neue", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background:
        radial-gradient(circle at top left, #fff6d8 0, transparent 25%),
        radial-gradient(circle at bottom right, #d7efe8 0, transparent 30%),
        var(--bg);
      color: var(--ink);
      font-family: var(--sans);
    }
    .page {
      max-width: 1500px;
      margin: 0 auto;
      padding: 24px;
    }
    .header {
      display: grid;
      grid-template-columns: 1.3fr 0.7fr;
      gap: 16px;
      margin-bottom: 16px;
    }
    .panel {
      background: rgba(255, 250, 240, 0.92);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: 0 18px 40px rgba(58, 42, 18, 0.08);
      padding: 18px;
      backdrop-filter: blur(8px);
    }
    .hero h1 {
      margin: 0 0 8px;
      font-size: 32px;
      line-height: 1.05;
      letter-spacing: -0.03em;
    }
    .hero p {
      margin: 0;
      color: var(--muted);
      max-width: 70ch;
    }
    .session-picker {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    textarea {
      width: 100%;
      min-height: 96px;
      resize: vertical;
      font: inherit;
      border-radius: 12px;
      border: 1px solid var(--line);
      padding: 10px 12px;
      background: white;
      color: var(--ink);
    }
    select, button {
      font: inherit;
      border-radius: 12px;
      border: 1px solid var(--line);
      padding: 10px 12px;
      background: white;
      color: var(--ink);
    }
    button {
      background: var(--accent);
      color: white;
      border-color: var(--accent);
      cursor: pointer;
    }
    .status-line {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 12px;
    }
    .pill {
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--panel-strong);
      border: 1px solid var(--line);
      font-size: 13px;
    }
    .layout {
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 16px;
    }
    .stack {
      display: grid;
      gap: 16px;
    }
    .section-title {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--muted);
      margin-bottom: 10px;
      font-weight: 700;
    }
    .workers {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }
    .workers th, .workers td {
      text-align: left;
      padding: 10px 8px;
      border-bottom: 1px solid rgba(214, 203, 182, 0.7);
      vertical-align: top;
    }
    .workers th { color: var(--muted); font-weight: 700; }
    .workers tr { cursor: pointer; }
    .workers tr:hover, .workers tr.active { background: rgba(15, 118, 110, 0.08); }
    .events {
      display: grid;
      gap: 10px;
      max-height: 70vh;
      overflow: auto;
      padding-right: 4px;
    }
    .event {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      background: white;
    }
    .event-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin-bottom: 8px;
      font-size: 12px;
      color: var(--muted);
      font-family: var(--mono);
    }
    .event-agent {
      color: var(--accent);
      font-weight: 700;
    }
    .event-content {
      white-space: pre-wrap;
      line-height: 1.4;
    }
    .codebox {
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      font-family: var(--mono);
      font-size: 12px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      max-height: 48vh;
      overflow: auto;
    }
    .muted { color: var(--muted); }
    .status-running { color: var(--warn); }
    .status-completed { color: var(--ok); }
    .status-failed, .status-reject { color: var(--bad); }
    .status-promote { color: var(--ok); }
    .status-hold { color: var(--warn); }
    .bucket-conservative { color: var(--ok); font-weight: 600; }
    .bucket-alternative { color: #6d28d9; font-weight: 600; }
    .bucket-novelty { color: #b45309; font-weight: 600; }
    .bucket-edge_exploration { color: var(--muted); font-style: italic; }
    .channel-tag {
      display: inline-block;
      padding: 2px 7px;
      border-radius: 6px;
      font-size: 11px;
      background: var(--accent-soft);
      color: var(--accent);
      font-weight: 600;
    }
    .refresh-ts { font-size: 11px; color: var(--muted); font-family: var(--mono); }
    .detail-section { margin-bottom: 14px; }
    .detail-section h4 {
      margin: 0 0 6px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--muted);
    }
    .detail-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 4px 16px;
      font-size: 13px;
    }
    .detail-grid .label { color: var(--muted); }
    .detail-grid .value { font-family: var(--mono); font-size: 12px; }
    .flag-list { display: flex; flex-wrap: wrap; gap: 4px; }
    .flag-bad {
      display: inline-block;
      padding: 2px 6px;
      border-radius: 6px;
      font-size: 11px;
      background: #fee2e2;
      color: var(--bad);
    }
    .flag-warn {
      display: inline-block;
      padding: 2px 6px;
      border-radius: 6px;
      font-size: 11px;
      background: #fef3c7;
      color: var(--warn);
    }
    .detail-raw {
      margin-top: 8px;
      font-size: 11px;
      cursor: pointer;
      color: var(--accent);
    }
    .detail-raw-content {
      display: none;
      font-family: var(--mono);
      font-size: 11px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      max-height: 30vh;
      overflow: auto;
      margin-top: 6px;
      padding: 8px;
      background: #f9f7f2;
      border-radius: 8px;
    }
    @media (max-width: 1100px) {
      .header, .layout { grid-template-columns: 1fr; }
      .events { max-height: none; }
    }
  </style>
</head>
<body>
  <div class="page">
    <div class="header">
      <div class="panel hero">
        <h1>Supervisor Agent Dashboard</h1>
        <p>Watch cheap worker loops and the supervisor discussion in real time. This UI reads session telemetry from disk, so it stays simple and decoupled from the execution stack.</p>
        <div class="status-line" id="session-meta"></div>
      </div>
      <div class="panel session-picker">
        <div class="section-title">Session</div>
        <select id="session-select"></select>
        <div style="display:flex; gap:10px; align-items:center;">
          <button id="refresh-button">Refresh Now</button>
          <span id="refresh-ts" class="refresh-ts"></span>
        </div>
        <div class="muted" id="session-summary">No session loaded.</div>
      </div>
    </div>

    <div id="proposal-summary-row" class="panel" style="margin-bottom:16px; display:none;">
      <div class="section-title">Proposal Frontier</div>
      <div id="proposal-summary" style="display:flex; flex-wrap:wrap; gap:16px;"></div>
    </div>

    <div class="layout">
      <div class="stack">
        <div class="panel">
          <div class="section-title">Workers</div>
          <table class="workers">
            <thead>
              <tr>
                <th>Task</th>
                <th>Status</th>
                <th>Verdict</th>
                <th>Channel</th>
                <th>Bucket</th>
                <th>Confidence</th>
                <th>Interestingness</th>
              </tr>
            </thead>
            <tbody id="worker-table-body"></tbody>
          </table>
        </div>
        <div class="panel">
          <div class="section-title">Selected Worker</div>
          <div id="worker-detail" class="codebox">Select a worker row.</div>
        </div>
      </div>

      <div class="stack">
        <div class="panel">
          <div class="section-title">Operator Hook</div>
          <textarea id="operator-message" placeholder="Leave a note for the future supervisor control loop."></textarea>
          <div style="display:flex; gap:10px; margin-top:10px;">
            <button id="operator-send">Send To Inbox</button>
          </div>
          <div class="muted" id="operator-status" style="margin-top:10px;">No operator message sent.</div>
        </div>
        <div class="panel">
          <div class="section-title">Supervisor + Worker Timeline</div>
          <div id="events" class="events"></div>
        </div>
      </div>
    </div>
  </div>

  <script>
    const state = {
      sessionId: null,
      sessions: [],
      lastEventSeq: 0,
      selectedWorkerId: null,
      pollHandle: null,
    };

    function escapeHtml(text) {
      return String(text ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }

    function statusClass(value) {
      const text = String(value || "").toLowerCase();
      if (text.includes("complete") || text === "promote" || text === "escalate") return "status-completed";
      if (text.includes("running") || text.includes("queue") || text === "hold" || text === "watch") return "status-running";
      if (text.includes("fail") || text === "reject" || text === "discard") return "status-failed";
      return "";
    }

    function bucketClass(value) {
      const text = String(value || "").toLowerCase();
      if (text === "conservative") return "bucket-conservative";
      if (text === "alternative") return "bucket-alternative";
      if (text === "novelty") return "bucket-novelty";
      if (text === "edge_exploration") return "bucket-edge_exploration";
      return "";
    }

    function channelLabel(value) {
      if (!value) return "-";
      return String(value).replace(/_/g, " ");
    }

    async function getJson(url) {
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    }

    async function loadSessions(preferredSessionId = null) {
      const payload = await getJson("/api/sessions");
      state.sessions = payload.sessions || [];
      const select = document.getElementById("session-select");
      select.innerHTML = "";
      for (const session of state.sessions) {
        const option = document.createElement("option");
        option.value = session.session_id;
        option.textContent = `${session.session_id} (${session.status})`;
        select.appendChild(option);
      }

      const fromUrl = new URLSearchParams(window.location.search).get("session_id");
      const target = preferredSessionId || fromUrl || state.sessionId || (state.sessions[0] && state.sessions[0].session_id);
      if (target) {
        state.sessionId = target;
        select.value = target;
        const currentUrl = new URL(window.location.href);
        currentUrl.searchParams.set("session_id", target);
        history.replaceState({}, "", currentUrl);
      }
    }

    function renderSessionHeader(liveState) {
      const meta = document.getElementById("session-meta");
      const summary = document.getElementById("session-summary");
      const workers = Object.values(liveState.workers || {});
      const completed = workers.filter(item => String(item.status).toLowerCase() === "completed").length;
      const failed = workers.filter(item => String(item.status).toLowerCase() === "failed").length;
      meta.innerHTML = `
        <div class="pill"><strong>Session</strong> ${escapeHtml(liveState.session_id || "")}</div>
        <div class="pill"><strong>Status</strong> <span class="${statusClass(liveState.status)}">${escapeHtml(liveState.status || "unknown")}</span></div>
        <div class="pill"><strong>Worker Model</strong> ${escapeHtml(liveState.worker_model || "")}</div>
        <div class="pill"><strong>Judge Model</strong> ${escapeHtml(liveState.judge_model || "none")}</div>
        <div class="pill"><strong>Workers</strong> ${workers.length}</div>
        <div class="pill"><strong>Completed</strong> ${completed}</div>
        <div class="pill"><strong>Failed</strong> ${failed}</div>
        <div class="pill"><strong>Inbox</strong> ${escapeHtml(liveState.operator_state?.inbox_count ?? 0)}</div>
        <div class="pill"><strong>Outbox</strong> ${escapeHtml(liveState.operator_state?.outbox_count ?? 0)}</div>
      `;
      summary.textContent = liveState.objective || "No objective available.";
      const latestOperator = liveState.operator_state?.latest_operator_message;
      if (latestOperator) {
        document.getElementById("operator-status").textContent =
          `Latest operator note (${latestOperator.author} @ ${latestOperator.ts}): ${latestOperator.content}`;
      }
    }

    function renderWorkers(liveState) {
      const tbody = document.getElementById("worker-table-body");
      const workers = Object.values(liveState.workers || {});
      workers.sort((a, b) => String(a.task_id).localeCompare(String(b.task_id)));
      tbody.innerHTML = "";

      if (!workers.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="muted">No workers yet.</td></tr>`;
        document.getElementById("worker-detail").textContent = "Select a worker row.";
        return;
      }

      if (!state.selectedWorkerId || !workers.some(item => item.task_id === state.selectedWorkerId)) {
        state.selectedWorkerId = workers[0].task_id;
      }

      for (const worker of workers) {
        const tr = document.createElement("tr");
        if (worker.task_id === state.selectedWorkerId) tr.classList.add("active");
        const summary = worker.summary || {};
        const cand = worker.candidate || {};
        const primaryChannel = cand.primary_channel || "";
        const bucket = cand.portfolio_bucket || "";
        tr.innerHTML = `
          <td>${escapeHtml(worker.task_id)}</td>
          <td><span class="${statusClass(worker.status)}">${escapeHtml(worker.status || "unknown")}</span></td>
          <td><span class="${statusClass(summary.verdict)}">${escapeHtml(summary.verdict || "-")}</span></td>
          <td>${primaryChannel ? `<span class="channel-tag">${escapeHtml(channelLabel(primaryChannel))}</span>` : "-"}</td>
          <td><span class="${bucketClass(bucket)}">${escapeHtml(bucket || "-")}</span></td>
          <td>${escapeHtml(summary.confidence ?? "-")}</td>
          <td>${escapeHtml(summary.interestingness ?? "-")}</td>
        `;
        tr.addEventListener("click", () => {
          state.selectedWorkerId = worker.task_id;
          renderWorkers(liveState);
        });
        tbody.appendChild(tr);
      }

      const selected = workers.find(item => item.task_id === state.selectedWorkerId) || workers[0];
      renderWorkerDetail(selected);
    }

    function renderWorkerDetail(worker) {
      const el = document.getElementById("worker-detail");
      const cand = worker.candidate || {};
      const summary = worker.summary || {};
      const channels = (cand.proposal_channels || []).map(c => `<span class="channel-tag">${escapeHtml(channelLabel(c))}</span>`).join(" ");
      const dqFlags = (cand.disqualifying_flags || []).map(f => `<span class="flag-bad">${escapeHtml(f)}</span>`).join("");
      const falseFlags = (cand.falsification_flags || []).map(f => `<span class="flag-warn">${escapeHtml(f)}</span>`).join("");

      const filterStatuses = Object.entries(cand.measurement_status_by_filter || {})
        .map(([f, s]) => `<span class="label">${escapeHtml(f)}</span><span class="value">${escapeHtml(s)}</span>`)
        .join("");

      el.innerHTML = `
        <div class="detail-section">
          <h4>Candidate</h4>
          <div class="detail-grid">
            <span class="label">ID</span><span class="value">${escapeHtml(cand.candidate_id || worker.task_id)}</span>
            <span class="label">Target</span><span class="value">${escapeHtml(cand.target || "-")}</span>
            <span class="label">Source</span><span class="value">${escapeHtml(cand.source_id ?? "-")}</span>
            <span class="label">Ref Dataset</span><span class="value">${escapeHtml(cand.reference_dataset || "-")}</span>
          </div>
        </div>
        <div class="detail-section">
          <h4>Proposal</h4>
          <div class="detail-grid">
            <span class="label">Primary Channel</span><span class="value"><span class="channel-tag">${escapeHtml(channelLabel(cand.primary_channel))}</span></span>
            <span class="label">Bucket</span><span class="value"><span class="${bucketClass(cand.portfolio_bucket)}">${escapeHtml(cand.portfolio_bucket || "-")}</span></span>
            <span class="label">Completeness</span><span class="value">${(cand.completeness_score ?? 0).toFixed(2)}</span>
            <span class="label">Novelty</span><span class="value">${(cand.novelty_score ?? 0).toFixed(2)}</span>
          </div>
          <div style="margin-top:6px">${channels || "<span class='muted'>no channels</span>"}</div>
        </div>
        <div class="detail-section">
          <h4>Scores</h4>
          <div class="detail-grid">
            <span class="label">Verdict</span><span class="value ${statusClass(summary.verdict)}">${escapeHtml(summary.verdict || "-")}</span>
            <span class="label">Confidence</span><span class="value">${escapeHtml(summary.confidence ?? "-")}</span>
            <span class="label">Interestingness</span><span class="value">${escapeHtml(summary.interestingness ?? "-")}</span>
            <span class="label">Ratio F090/F444</span><span class="value">${cand.ratio_f090_f444 != null ? Number(cand.ratio_f090_f444).toFixed(4) : "-"}</span>
            <span class="label">Red SNR r3</span><span class="value">${cand.red_snr_r3 != null ? Number(cand.red_snr_r3).toFixed(1) : "-"}</span>
          </div>
        </div>
        ${filterStatuses ? `<div class="detail-section"><h4>Filter Measurability</h4><div class="detail-grid">${filterStatuses}</div></div>` : ""}
        ${dqFlags || falseFlags ? `<div class="detail-section"><h4>Flags</h4><div class="flag-list">${dqFlags}${falseFlags}</div></div>` : ""}
        <div class="detail-raw" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === 'block' ? 'none' : 'block'">Show raw JSON</div>
        <div class="detail-raw-content">${escapeHtml(JSON.stringify(worker, null, 2))}</div>
      `;
    }

    function renderEvents(events) {
      const container = document.getElementById("events");
      if (!events.length) {
        container.innerHTML = `<div class="muted">No events yet.</div>`;
        return;
      }
      container.innerHTML = events.map(event => `
        <div class="event">
          <div class="event-meta">
            <span>#${escapeHtml(event.seq)}</span>
            <span class="event-agent">${escapeHtml(event.agent)}</span>
            <span>${escapeHtml(event.event_type)}</span>
            <span>${escapeHtml(event.ts)}</span>
          </div>
          <div class="event-content">${escapeHtml(event.content)}</div>
        </div>
      `).join("");
    }

    async function loadProposalSummary() {
      try {
        const data = await getJson("/api/proposal_summary");
        const container = document.getElementById("proposal-summary");
        const row = document.getElementById("proposal-summary-row");
        if (data.error) { row.style.display = "none"; return; }
        row.style.display = "";
        const buckets = data.shortlist_bucket_counts || data.portfolio_bucket_counts || {};
        const channels = data.shortlist_channel_counts || data.candidate_channel_counts || {};
        container.innerHTML = `
          <div>
            <div style="font-size:12px;color:var(--muted);margin-bottom:4px;">Candidates</div>
            <div style="font-size:24px;font-weight:700;">${data.candidate_count ?? "?"}</div>
            <div style="font-size:12px;color:var(--muted);">Shortlist: ${data.shortlist_count ?? "?"}</div>
          </div>
          <div>
            <div style="font-size:12px;color:var(--muted);margin-bottom:4px;">Buckets</div>
            ${Object.entries(buckets).map(([k,v]) => `<div><span class="${bucketClass(k)}">${escapeHtml(k)}</span> <span style="font-family:var(--mono);font-size:12px;">${v}</span></div>`).join("")}
          </div>
          <div>
            <div style="font-size:12px;color:var(--muted);margin-bottom:4px;">Channels</div>
            ${Object.entries(channels).map(([k,v]) => `<div><span class="channel-tag">${escapeHtml(channelLabel(k))}</span> <span style="font-family:var(--mono);font-size:12px;">${v}</span></div>`).join("")}
          </div>
        `;
      } catch { /* no summary available */ }
    }

    async function refreshSession() {
      if (!state.sessionId) return;
      const payload = await getJson(`/api/session?session_id=${encodeURIComponent(state.sessionId)}&after=0&limit=250`);
      renderSessionHeader(payload.state || {});
      renderWorkers(payload.state || {});
      renderEvents(payload.events || []);
      const latest = (payload.events || []).at(-1);
      state.lastEventSeq = latest ? Number(latest.seq || 0) : 0;
      const ts = new Date().toLocaleTimeString();
      document.getElementById("refresh-ts").textContent = `Last updated: ${ts}`;
    }

    async function initialize() {
      await loadSessions();
      if (!state.sessionId) return;
      await refreshSession();
      loadProposalSummary();
      document.getElementById("session-select").addEventListener("change", async (event) => {
        state.sessionId = event.target.value;
        state.lastEventSeq = 0;
        await refreshSession();
      });
      document.getElementById("refresh-button").addEventListener("click", refreshSession);
      document.getElementById("operator-send").addEventListener("click", async () => {
        const content = document.getElementById("operator-message").value.trim();
        if (!content || !state.sessionId) return;
        const response = await fetch("/api/operator_message", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: state.sessionId, author: "operator", content }),
        });
        if (!response.ok) {
          document.getElementById("operator-status").textContent = `Failed to append operator note: HTTP ${response.status}`;
          return;
        }
        document.getElementById("operator-message").value = "";
        await refreshSession();
      });
      state.pollHandle = setInterval(refreshSession, 2000);
    }

    initialize().catch((error) => {
      document.getElementById("session-summary").textContent = `Dashboard failed to load: ${error.message}`;
    });
  </script>
</body>
</html>
"""


def make_handler(session_root: Path):
    """Create a request handler bound to a specific session root."""

    class SupervisorDashboardHandler(BaseHTTPRequestHandler):
        """Serve the dashboard HTML plus session JSON endpoints."""

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)

            if parsed.path == "/":
                _send_html(self, render_dashboard_html())
                return

            if parsed.path == "/api/sessions":
                _send_json(self, {"sessions": list_sessions(session_root)})
                return

            if parsed.path == "/api/session":
                session_id = _first(query.get("session_id"))
                session_dir = resolve_session_dir(session_id, session_root=session_root)
                if session_dir is None:
                    _send_json(
                        self,
                        {"error": "session_not_found", "session_id": session_id},
                        status=404,
                    )
                    return
                after = int(_first(query.get("after"), "0"))
                limit = int(_first(query.get("limit"), "200"))
                _send_json(
                    self,
                    build_session_payload(session_dir, event_after=after, event_limit=limit),
                )
                return

            if parsed.path == "/api/proposal_summary":
                summary_path = ROOT / "research_output" / "proposal_channel_summary.json"
                summary = _read_json(summary_path, None)
                if summary is None:
                    _send_json(self, {"error": "no_proposal_summary"}, status=404)
                else:
                    _send_json(self, summary)
                return

            _send_json(self, {"error": "not_found", "path": parsed.path}, status=404)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/api/operator_message":
                _send_json(self, {"error": "not_found", "path": parsed.path}, status=404)
                return

            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                content_length = 0
            raw_body = self.rfile.read(max(content_length, 0))
            try:
                payload = json.loads(raw_body.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                _send_json(self, {"error": "invalid_json"}, status=400)
                return

            session_id = payload.get("session_id")
            author = payload.get("author") or "operator"
            content = payload.get("content") or ""
            session_dir = resolve_session_dir(session_id, session_root=session_root)
            if session_dir is None:
                _send_json(self, {"error": "session_not_found", "session_id": session_id}, status=404)
                return

            try:
                message = append_operator_message(session_dir, author=author, content=content)
            except ValueError as exc:
                _send_json(self, {"error": "invalid_message", "detail": str(exc)}, status=400)
                return
            except FileNotFoundError as exc:
                _send_json(self, {"error": "live_state_missing", "detail": str(exc)}, status=404)
                return

            _send_json(self, {"ok": True, "message": message}, status=201)

    return SupervisorDashboardHandler


def _first(values: Optional[List[str]], default: Optional[str] = None) -> Optional[str]:
    """Return the first query parameter value or a default."""
    if values:
        return values[0]
    return default


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the dashboard server."""
    parser = argparse.ArgumentParser(
        description="Run the lightweight GUI for supervisor sessions.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind host.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Bind port.")
    parser.add_argument(
        "--session-root",
        default=str(SESSION_ROOT),
        help="Root directory containing supervisor session folders.",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Optional session id to preselect in the browser.",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the dashboard URL in the default browser after startup.",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    session_root = Path(args.session_root)
    handler = make_handler(session_root)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    target_url = f"http://{args.host}:{args.port}/"
    if args.session_id:
        target_url += f"?session_id={args.session_id}"

    print(f"Supervisor dashboard serving at {target_url}")
    if args.open_browser:
        webbrowser.open(target_url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down supervisor dashboard.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
