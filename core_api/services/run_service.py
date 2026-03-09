"""Run service - manages experiment runs."""

import os
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from ..models.runs import Run
from ..schemas.runs import RunCreate, RunResponse, RunResult
from ..schemas.experiments import ExperimentSpec


class RunService:
    """Service for managing runs."""

    _ALLOWED_STATUS_TRANSITIONS = {
        "queued": {"running", "failed"},
        "running": {"completed", "failed"},
        "completed": {"completed"},
        "failed": {"failed"},
    }

    @staticmethod
    def _utcnow() -> datetime:
        """Return timezone-aware UTC timestamp."""
        return datetime.now(timezone.utc)

    @staticmethod
    def _queued_stuck_seconds() -> int:
        """Return threshold for queued runs considered stuck."""
        try:
            return max(10, int(os.getenv("RUN_QUEUE_STUCK_SECONDS", "120")))
        except ValueError:
            return 120

    @staticmethod
    def _normalize_dt(dt: Optional[datetime]) -> Optional[datetime]:
        """Normalize naive datetimes to UTC to keep duration math safe."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @classmethod
    def _status_reason_and_hints(cls, db_run: Run) -> tuple[Optional[str], List[str]]:
        """Derive status reason and actionable hints for API responses."""
        hints: List[str] = []
        status = db_run.status

        if status == "queued":
            created_at = cls._normalize_dt(db_run.created_at)
            if created_at is None:
                return "queued_waiting_for_worker", [
                    "Run is queued but creation timestamp is missing; inspect DB integrity."
                ]

            queued_for = (cls._utcnow() - created_at).total_seconds()
            threshold = cls._queued_stuck_seconds()
            if queued_for >= threshold:
                hints.append(
                    f"Run has remained queued for {int(queued_for)}s (threshold={threshold}s)."
                )
                hints.append(
                    "Likely causes: API worker restart, background task failure, or no active executor."
                )
                hints.append(
                    "Check API logs and verify run_api.py is running with tool registry loaded."
                )
                return "stuck_queued", hints
            return "queued_waiting_for_worker", hints

        if status == "running":
            return "running_in_worker", hints

        if status == "completed":
            return "completed_successfully", hints

        if status == "failed":
            text = f"{db_run.error_message or ''}\n{(db_run.result or {}).get('error', '')}".lower()
            if "strict_run_validation_failed" in text or "strict_data_load_failure" in text:
                hints.append(
                    "Strict real-data integrity failed. Re-run POST /runs/validate and fix dataset metadata.file_path."
                )
                return "failed_strict_validation", hints
            return "failed_execution", hints

        return None, hints

    @classmethod
    def _hydrate_run_response(cls, db_run: Run) -> RunResponse:
        """Build API response with parsed JSON fields and status hints."""
        response = RunResponse.model_validate(db_run)
        if db_run.result:
            response.result = RunResult(**db_run.result)
        if db_run.trajectory:
            from ..schemas.runs import Message

            response.trajectory = [Message(**msg) for msg in db_run.trajectory]
        response.spec = ExperimentSpec(**db_run.spec)
        response.status_reason, response.status_hints = cls._status_reason_and_hints(db_run)
        return response

    @classmethod
    def _is_transition_allowed(cls, current: str, target: str) -> bool:
        """Validate run status transition."""
        if current == target:
            return True
        allowed_targets = cls._ALLOWED_STATUS_TRANSITIONS.get(current, {target})
        return target in allowed_targets

    @staticmethod
    def create_run(db: Session, run: RunCreate) -> RunResponse:
        """Create a new run."""
        db_run = Run(
            experiment_id=run.experiment_id,
            status="queued",
            spec=run.spec.model_dump(),
        )
        db.add(db_run)
        db.commit()
        db.refresh(db_run)
        return RunService._hydrate_run_response(db_run)

    @staticmethod
    def get_run(db: Session, run_id: int) -> Optional[RunResponse]:
        """Get a run by ID."""
        db_run = db.query(Run).filter(Run.id == run_id).first()
        if db_run:
            return RunService._hydrate_run_response(db_run)
        return None

    @staticmethod
    def update_run_status(
        db: Session,
        run_id: int,
        status: str,
        result: Optional[RunResult] = None,
        error_message: Optional[str] = None,
        trajectory: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[RunResponse]:
        """Update run status and result."""
        db_run = db.query(Run).filter(Run.id == run_id).first()
        if not db_run:
            return None

        if not RunService._is_transition_allowed(db_run.status, status):
            transition_note = (
                f"Invalid status transition requested: {db_run.status} -> {status}. "
                "Transition was force-applied for compatibility."
            )
            error_message = (
                f"{error_message}\n{transition_note}" if error_message else transition_note
            )

        db_run.status = status
        if status == "running" and not db_run.started_at:
            db_run.started_at = RunService._utcnow()
        elif status in ("completed", "failed"):
            if not db_run.started_at:
                db_run.started_at = RunService._utcnow()
            if not db_run.completed_at:
                db_run.completed_at = RunService._utcnow()

        if result:
            db_run.result = result.model_dump()
        if error_message:
            db_run.error_message = error_message
        if trajectory is not None:
            # Ensure trajectory is properly serialized (datetime -> string)
            serialized_trajectory = []
            for msg in trajectory:
                msg_dict = dict(msg)  # Make a copy
                # Convert datetime to ISO string if present
                if "timestamp" in msg_dict and msg_dict["timestamp"]:
                    if hasattr(msg_dict["timestamp"], "isoformat"):
                        msg_dict["timestamp"] = msg_dict["timestamp"].isoformat()
                serialized_trajectory.append(msg_dict)
            db_run.trajectory = serialized_trajectory

        db.commit()
        db.refresh(db_run)
        return RunService._hydrate_run_response(db_run)

    @staticmethod
    def append_to_trajectory(
        db: Session,
        run_id: int,
        messages: List[Dict[str, Any]],
    ) -> Optional[RunResponse]:
        """Append messages to run trajectory."""
        try:
            db_run = db.query(Run).filter(Run.id == run_id).first()
            if not db_run:
                return None

            # Ensure messages are properly serialized (datetime -> string)
            serialized_messages = []
            for msg in messages:
                msg_dict = dict(msg)  # Make a copy
                # Convert datetime to ISO string if present
                if "timestamp" in msg_dict and msg_dict["timestamp"]:
                    if hasattr(msg_dict["timestamp"], "isoformat"):
                        msg_dict["timestamp"] = msg_dict["timestamp"].isoformat()
                serialized_messages.append(msg_dict)

            current_trajectory = db_run.trajectory or []
            current_trajectory.extend(serialized_messages)
            db_run.trajectory = current_trajectory

            db.commit()
            db.refresh(db_run)
        except Exception:
            db.rollback()
            raise

        return RunService._hydrate_run_response(db_run)

    @staticmethod
    def list_runs(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        experiment_id: Optional[int] = None,
    ) -> List[RunResponse]:
        """List runs with optional filtering."""
        query = db.query(Run)

        if status:
            query = query.filter(Run.status == status)
        if experiment_id:
            query = query.filter(Run.experiment_id == experiment_id)

        runs = query.order_by(Run.created_at.desc()).offset(skip).limit(limit).all()

        result = []
        for db_run in runs:
            result.append(RunService._hydrate_run_response(db_run))

        return result
