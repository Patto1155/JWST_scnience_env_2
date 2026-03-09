"""Session telemetry utilities for supervisor-driven discovery campaigns.

The telemetry format is intentionally simple:
- ``event_stream.jsonl`` is append-only and suitable for tailing in a future GUI.
- ``live_state.json`` is a compact snapshot of the current session state.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Optional

from discovery.session_schemas import (
    LiveSessionState,
    OperatorMessage,
    SessionManifest,
    SessionWorkerState,
)


def _utc_now_iso() -> str:
    """Return a UTC ISO-8601 timestamp string."""
    return datetime.now(UTC).isoformat()


class SessionTelemetry:
    """Persist campaign events and a compact live session state."""

    def __init__(
        self,
        session_dir: Path,
        *,
        session_id: str,
        objective: str,
        worker_model: str,
        judge_model: Optional[str],
        base_url: str,
    ) -> None:
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.event_path = self.session_dir / "event_stream.jsonl"
        self.state_path = self.session_dir / "live_state.json"
        self.manifest_path = self.session_dir / "session_manifest.json"
        self.operator_inbox_path = self.session_dir / "operator_inbox.jsonl"
        self.supervisor_outbox_path = self.session_dir / "supervisor_outbox.jsonl"

        now = _utc_now_iso()
        self._state: Dict[str, Any] = {
            "session_id": session_id,
            "objective": objective,
            "worker_model": worker_model,
            "judge_model": judge_model,
            "base_url": base_url,
            "status": "initializing",
            "created_at": now,
            "updated_at": now,
            "latest_event_at": None,
            "supervisor_thread": [],
            "workers": {},
            "artifacts": {},
            "operator_state": {
                "inbox_count": 0,
                "outbox_count": 0,
                "latest_operator_message": None,
            },
            "manifest_path": str(self.manifest_path),
            "session_errors": [],
        }
        self._manifest: Dict[str, Any] = {
            "session_id": session_id,
            "objective": objective,
            "worker_model": worker_model,
            "judge_model": judge_model,
            "base_url": base_url,
            "created_at": now,
            "updated_at": now,
            "status": "initializing",
            "candidate_source": None,
            "worker_results_path": None,
            "judge_report_path": None,
            "judge_markdown_path": None,
            "summary_path": None,
            "event_stream_path": str(self.event_path),
            "live_state_path": str(self.state_path),
            "operator_inbox_path": str(self.operator_inbox_path),
            "supervisor_outbox_path": str(self.supervisor_outbox_path),
            "worker_count": 0,
            "completed_workers": 0,
            "failed_workers": 0,
            "completed_with_errors": False,
            "session_errors": [],
        }
        self.operator_inbox_path.touch(exist_ok=True)
        self.supervisor_outbox_path.touch(exist_ok=True)
        self._write_state()

    @property
    def state(self) -> Dict[str, Any]:
        """Expose the mutable state snapshot."""
        return self._state

    def set_status(self, status: str) -> None:
        """Update the session status."""
        self._state["status"] = status
        self._manifest["status"] = status
        self._touch_state()

    def set_artifact(self, name: str, relative_path: str) -> None:
        """Register an output artifact in the session snapshot."""
        self._state["artifacts"][name] = relative_path
        manifest_key_map = {
            "candidate_source": "candidate_source",
            "worker_results": "worker_results_path",
            "judge_report": "judge_report_path",
            "judge_markdown": "judge_markdown_path",
            "summary": "summary_path",
        }
        manifest_key = manifest_key_map.get(name)
        if manifest_key is not None:
            self._manifest[manifest_key] = relative_path
        self._touch_state()

    def record_session_error(self, message: str) -> None:
        """Persist a session-level error without aborting the session."""
        if message not in self._state["session_errors"]:
            self._state["session_errors"].append(message)
        if message not in self._manifest["session_errors"]:
            self._manifest["session_errors"].append(message)
        self._manifest["completed_with_errors"] = True
        self._touch_state()

    def register_worker(
        self,
        task_id: str,
        *,
        candidate: Dict[str, Any],
        run_id: Optional[int] = None,
        status: str = "pending",
    ) -> None:
        """Create or replace a worker entry in the live snapshot."""
        self._state["workers"][task_id] = {
            "task_id": task_id,
            "run_id": run_id,
            "status": status,
            "candidate": candidate,
            "submitted_at": _utc_now_iso() if run_id is not None else None,
            "completed_at": None,
            "status_reason": None,
            "status_hints": [],
            "summary": None,
            "schema_errors": [],
        }
        self._touch_state()

    def update_worker(
        self,
        task_id: str,
        *,
        status: Optional[str] = None,
        run_id: Optional[int] = None,
        status_reason: Optional[str] = None,
        status_hints: Optional[list[str]] = None,
        summary: Optional[Dict[str, Any]] = None,
        schema_errors: Optional[list[str]] = None,
        completed: bool = False,
    ) -> None:
        """Patch a worker entry with new run metadata."""
        worker = self._state["workers"].setdefault(task_id, {"task_id": task_id})
        if status is not None:
            worker["status"] = status
        if run_id is not None:
            worker["run_id"] = run_id
            worker.setdefault("submitted_at", _utc_now_iso())
        if status_reason is not None:
            worker["status_reason"] = status_reason
        if status_hints is not None:
            worker["status_hints"] = list(status_hints)
        if summary is not None:
            worker["summary"] = summary
        if schema_errors is not None:
            worker["schema_errors"] = list(schema_errors)
        if completed:
            worker["completed_at"] = _utc_now_iso()
        self._touch_state()

    def emit(
        self,
        event_type: str,
        *,
        agent: str,
        role: str,
        content: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append an event to the JSONL stream and mirror it into live state."""
        timestamp = _utc_now_iso()
        event = {
            "ts": timestamp,
            "event_type": event_type,
            "agent": agent,
            "role": role,
            "content": content,
            "payload": payload or {},
        }
        with self.event_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=True) + "\n")

        if role == "assistant" and agent in {"supervisor", "judge"}:
            supervisor_message = OperatorMessage(
                ts=timestamp,
                author=agent,
                role="supervisor",
                content=content,
                session_id=self._state["session_id"],
            )
            with self.supervisor_outbox_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(supervisor_message.model_dump(), ensure_ascii=True) + "\n")
            self._state["operator_state"]["outbox_count"] += 1

        self._state["latest_event_at"] = timestamp
        self._state["updated_at"] = timestamp
        # Keep the thread compact so a future GUI can load state quickly.
        thread = self._state["supervisor_thread"]
        thread.append(event)
        if len(thread) > 200:
            del thread[:-200]
        self._write_state()

    def _touch_state(self) -> None:
        """Refresh timestamps and persist the snapshot."""
        now = _utc_now_iso()
        self._state["updated_at"] = now
        self._manifest["updated_at"] = now
        self._manifest["worker_count"] = len(self._state["workers"])
        workers = list(self._state["workers"].values())
        self._manifest["completed_workers"] = sum(1 for worker in workers if worker.get("completed_at"))
        self._manifest["failed_workers"] = sum(
            1 for worker in workers if str(worker.get("status") or "").lower() in {"failed", "validation_failed", "submission_failed", "poll_failed"}
        )
        self._write_state()

    def _write_state(self) -> None:
        """Atomically write the live state snapshot."""
        validated_workers: Dict[str, Any] = {}
        for task_id, worker in self._state["workers"].items():
            if isinstance(worker.get("candidate"), dict):
                validated_workers[task_id] = SessionWorkerState.model_validate(worker).model_dump()
        state_payload = {
            **self._state,
            "workers": validated_workers,
        }
        state_payload = LiveSessionState.model_validate(state_payload).model_dump()
        manifest_payload = SessionManifest.model_validate(self._manifest).model_dump()

        temp_path = self.state_path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(state_payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        temp_path.replace(self.state_path)
        manifest_temp_path = self.manifest_path.with_suffix(".tmp")
        manifest_temp_path.write_text(
            json.dumps(manifest_payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        manifest_temp_path.replace(self.manifest_path)

    def append_operator_message(self, author: str, content: str) -> Dict[str, Any]:
        """Append a GUI-originated operator message into the session inbox."""
        message = OperatorMessage(
            ts=_utc_now_iso(),
            author=author,
            role="operator",
            content=content,
            session_id=self._state["session_id"],
        )
        with self.operator_inbox_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(message.model_dump(), ensure_ascii=True) + "\n")
        self._state["operator_state"]["inbox_count"] += 1
        self._state["operator_state"]["latest_operator_message"] = message.model_dump()
        self._touch_state()
        return message.model_dump()
