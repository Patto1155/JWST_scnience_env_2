"""Tests for the lightweight supervisor dashboard helpers."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib import request

from discovery.supervisor_dashboard import (
    append_operator_message,
    build_session_payload,
    list_sessions,
    load_events,
    make_handler,
    resolve_session_dir,
)


def _write_session(root: Path, session_id: str, *, status: str, updated_at: str) -> Path:
    session_dir = root / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "live_state.json").write_text(
        json.dumps(
            {
                "session_id": session_id,
                "status": status,
                "objective": f"objective for {session_id}",
                "worker_model": "qwen/qwen3-next-80b-a3b-thinking",
                "judge_model": "anthropic/claude-3.5-sonnet",
                "base_url": "http://localhost:8000",
                "created_at": updated_at,
                "updated_at": updated_at,
                "latest_event_at": None,
                "supervisor_thread": [],
                "workers": {},
                "artifacts": {},
                "operator_state": {
                    "inbox_count": 0,
                    "outbox_count": 0,
                    "latest_operator_message": None,
                },
                "manifest_path": str(session_dir / "session_manifest.json"),
                "session_errors": [],
            }
        ),
        encoding="utf-8",
    )
    return session_dir


def test_list_sessions_returns_empty_for_missing_root(tmp_path: Path) -> None:
    """Dashboard helpers should handle a missing session root cleanly."""
    assert list_sessions(tmp_path / "missing") == []


def test_list_sessions_sorts_by_recency(tmp_path: Path) -> None:
    """Newest session should appear first."""
    _write_session(tmp_path, "older", status="completed", updated_at="2026-03-08T10:00:00+00:00")
    _write_session(tmp_path, "newer", status="running", updated_at="2026-03-08T11:00:00+00:00")

    sessions = list_sessions(tmp_path)

    assert [item["session_id"] for item in sessions] == ["newer", "older"]
    assert sessions[0]["status"] == "running"


def test_load_events_applies_after_and_limit(tmp_path: Path) -> None:
    """Event loading should support incremental polling semantics."""
    session_dir = _write_session(
        tmp_path,
        "demo",
        status="running",
        updated_at="2026-03-08T11:00:00+00:00",
    )
    event_path = session_dir / "event_stream.jsonl"
    rows = [
        {"ts": "t1", "event_type": "one", "agent": "supervisor", "content": "a"},
        {"ts": "t2", "event_type": "two", "agent": "worker", "content": "b"},
        {"ts": "t3", "event_type": "three", "agent": "judge", "content": "c"},
    ]
    event_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    events = load_events(session_dir, after=1, limit=1)

    assert len(events) == 1
    assert events[0]["seq"] == 3
    assert events[0]["event_type"] == "three"


def test_build_session_payload_uses_latest_session_by_default(tmp_path: Path) -> None:
    """The dashboard payload helpers should work with the latest resolved session."""
    _write_session(tmp_path, "older", status="completed", updated_at="2026-03-08T10:00:00+00:00")
    latest = _write_session(tmp_path, "latest", status="running", updated_at="2026-03-08T12:00:00+00:00")
    (latest / "event_stream.jsonl").write_text(
        json.dumps({"ts": "t1", "event_type": "worker_submitted", "agent": "supervisor", "content": "demo"}) + "\n",
        encoding="utf-8",
    )

    resolved = resolve_session_dir(None, tmp_path)
    payload = build_session_payload(resolved)

    assert resolved is not None
    assert resolved.name == "latest"
    assert payload["state"]["session_id"] == "latest"
    assert payload["events"][0]["seq"] == 1


def test_append_operator_message_updates_inbox_and_state(tmp_path: Path) -> None:
    """Operator notes should append to the inbox and update live state metadata."""
    session_dir = _write_session(
        tmp_path,
        "latest",
        status="running",
        updated_at="2026-03-08T12:00:00+00:00",
    )

    message = append_operator_message(session_dir, author="operator", content="Pause after current worker.")
    state = json.loads((session_dir / "live_state.json").read_text(encoding="utf-8"))
    inbox_rows = (session_dir / "operator_inbox.jsonl").read_text(encoding="utf-8").splitlines()

    assert message["author"] == "operator"
    assert state["operator_state"]["inbox_count"] == 1
    assert state["operator_state"]["latest_operator_message"]["content"] == "Pause after current worker."
    assert len(inbox_rows) == 1


def test_dashboard_post_endpoint_writes_operator_inbox(tmp_path: Path) -> None:
    """POST /api/operator_message should append to the operator inbox file."""
    from http.server import ThreadingHTTPServer

    session_dir = _write_session(
        tmp_path,
        "latest",
        status="running",
        updated_at="2026-03-08T12:00:00+00:00",
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(tmp_path))
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    try:
        payload = json.dumps(
            {"session_id": "latest", "author": "operator", "content": "Watch candidate 545 closely."}
        ).encode("utf-8")
        req = request.Request(
            f"http://127.0.0.1:{server.server_port}/api/operator_message",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))
    finally:
        thread.join(timeout=5)
        server.server_close()

    inbox_rows = (session_dir / "operator_inbox.jsonl").read_text(encoding="utf-8").splitlines()
    assert body["ok"] is True
    assert len(inbox_rows) == 1
