"""Runs router - endpoints for experiment runs."""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from runner.executor import run_experiment
from runner.scientific_agent import ScientificResearchAgent

from ..db import get_db
from ..models.tools import Tool
from ..schemas.experiments import ExperimentSpec
from ..schemas.runs import (
    RunCreate,
    RunList,
    RunResponse,
    RunResult,
    RunValidationResponse,
)
from ..services.run_service import RunService
from ..services.strict_validation import (
    STRICT_VALIDATION_ERROR_CODE,
    validate_strict_run_spec,
)

router = APIRouter(prefix="/runs", tags=["runs"])


def _get_tool_lookup(db: Session) -> Dict[str, Dict[str, str]]:
    """Build tool lookup dictionary from database."""
    tools = db.query(Tool).all()
    return {
        tool.name: {
            "module_path": tool.module_path,
            "function_name": tool.function_name,
        }
        for tool in tools
    }


def _get_tool_metadata(db: Session) -> Dict[str, Dict[str, Any]]:
    """Build tool metadata dictionary from database."""
    tools = db.query(Tool).all()
    return {
        tool.name: {
            "description": tool.description,
            "input_schema": tool.input_schema,
            "output_schema": tool.output_schema,
            "tags": tool.tags or [],
        }
        for tool in tools
    }


def _build_preflight_payload(
    db: Session,
    spec: ExperimentSpec,
    *,
    tool_lookup: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Build structured preflight validation payload for run creation."""
    if tool_lookup is None:
        tool_lookup = _get_tool_lookup(db)

    strict_validation = validate_strict_run_spec(db, spec)
    payload = strict_validation.to_payload()
    tool_lookup, allowed_tool_issues = _filter_tool_lookup_for_spec(spec, tool_lookup)

    payload["tool_count"] = len(tool_lookup)
    issues = list(payload.get("issues", []))
    issues.extend(allowed_tool_issues)
    if not tool_lookup:
        issues.append(
            {
                "code": "RUN_PRECONDITION_NO_TOOLS",
                "message": "No tools are registered in the system.",
                "dataset": None,
                "file_path": None,
                "hint": "Register tools via startup or /tools before queueing runs.",
                "severity": "error",
            }
        )

    payload["issues"] = issues
    payload["issue_count"] = len(issues)
    payload["valid"] = payload.get("valid", False) and bool(tool_lookup)
    return payload


def _allowed_tools_from_spec(spec: ExperimentSpec) -> Optional[list[str]]:
    """Extract a normalized allowed_tools list from run constraints."""
    constraints = spec.constraints or {}
    raw_value = constraints.get("allowed_tools")
    if raw_value is None:
        return None
    if not isinstance(raw_value, list):
        return []

    normalized: list[str] = []
    for item in raw_value:
        if not isinstance(item, str):
            continue
        tool_name = item.strip()
        if tool_name and tool_name not in normalized:
            normalized.append(tool_name)
    return normalized


def _filter_tool_lookup_for_spec(
    spec: ExperimentSpec,
    tool_lookup: Dict[str, Dict[str, str]],
) -> tuple[Dict[str, Dict[str, str]], list[Dict[str, Any]]]:
    """Filter tool lookup based on allowed_tools constraint."""
    allowed_tools = _allowed_tools_from_spec(spec)
    if allowed_tools is None:
        return tool_lookup, []

    if not allowed_tools:
        return {}, [
            {
                "code": "RUN_ALLOWED_TOOLS_EMPTY",
                "message": "constraints.allowed_tools must contain at least one registered tool name.",
                "dataset": None,
                "file_path": None,
                "hint": "Provide a non-empty allowed_tools list or omit the constraint.",
                "severity": "error",
            }
        ]

    unknown_tools = [tool_name for tool_name in allowed_tools if tool_name not in tool_lookup]
    issues: list[Dict[str, Any]] = []
    if unknown_tools:
        issues.extend(
            {
                "code": "RUN_ALLOWED_TOOL_UNKNOWN",
                "message": f"Allowed tool is not registered: {tool_name}",
                "dataset": None,
                "file_path": None,
                "hint": "Remove unknown tool names or register them before queueing the run.",
                "severity": "error",
            }
            for tool_name in unknown_tools
        )

    filtered_lookup = {
        tool_name: tool_lookup[tool_name] for tool_name in allowed_tools if tool_name in tool_lookup
    }
    return filtered_lookup, issues


def _filter_tool_metadata_for_spec(
    spec: ExperimentSpec,
    tool_metadata: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Filter tool metadata based on allowed_tools constraint."""
    allowed_tools = _allowed_tools_from_spec(spec)
    if allowed_tools is None:
        return tool_metadata
    return {
        tool_name: tool_metadata[tool_name]
        for tool_name in allowed_tools
        if tool_name in tool_metadata
    }


def _raise_for_invalid_preflight(payload: Dict[str, Any]) -> None:
    """Raise standardized HTTP errors for invalid preflight payloads."""
    if payload.get("valid", False):
        return

    issues = payload.get("issues", [])
    has_strict_issue = any(str(issue.get("code", "")).startswith("STRICT_") for issue in issues)

    if has_strict_issue:
        detail = dict(payload)
        detail["code"] = STRICT_VALIDATION_ERROR_CODE
        detail["message"] = (
            "Strict real-data validation failed. "
            "Fix dataset catalog integrity issues before queueing the run."
        )
        raise HTTPException(status_code=422, detail=detail)

    raise HTTPException(
        status_code=400,
        detail={
            "code": "RUN_PRECONDITION_FAILED",
            "message": "Run cannot be queued until preflight checks pass.",
            "preflight": payload,
        },
    )


@router.get("/", response_model=RunList)
def list_runs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    experiment_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """List all runs."""
    runs = RunService.list_runs(
        db, skip=skip, limit=limit, status=status, experiment_id=experiment_id
    )
    return RunList(runs=runs, count=len(runs))


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: int, db: Session = Depends(get_db)):
    """Get a specific run by ID."""
    run = RunService.get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/validate", response_model=RunValidationResponse)
def validate_run(
    run: RunCreate,
    db: Session = Depends(get_db),
):
    """Preflight validation endpoint before queueing runs."""
    tool_lookup = _get_tool_lookup(db)
    payload = _build_preflight_payload(db, run.spec, tool_lookup=tool_lookup)
    return RunValidationResponse.model_validate(payload)


def _execute_run_task(
    run_id: int,
    spec: ExperimentSpec,
    tool_lookup: Dict[str, Dict[str, str]],
    tool_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
):
    """Background task to execute a run."""
    import sys

    from dotenv import load_dotenv

    from ..db import SessionLocal
    from ..services.run_service import RunService

    load_dotenv()
    print(f"[BACKGROUND TASK] Starting run {run_id}", file=sys.stderr, flush=True)

    db = SessionLocal()
    try:
        tool_lookup, allowed_tool_issues = _filter_tool_lookup_for_spec(spec, tool_lookup)
        tool_metadata = _filter_tool_metadata_for_spec(spec, tool_metadata or {})
        if allowed_tool_issues:
            error_text = "RUN_ALLOWED_TOOLS_INVALID: allowed_tools constraint failed."
            log_summary = (
                "Execution preflight failed.\n"
                f"{error_text}\n{json.dumps({'issues': allowed_tool_issues}, indent=2)}"
            )
            RunService.update_run_status(
                db,
                run_id,
                "failed",
                result=RunResult(
                    status="failed",
                    error=error_text,
                    log_summary=log_summary,
                ),
                error_message=error_text,
            )
            return

        strict_validation = validate_strict_run_spec(db, spec)
        if not strict_validation.valid:
            strict_detail = strict_validation.to_http_error_detail()
            error_text = (
                f"{STRICT_VALIDATION_ERROR_CODE}: "
                "Strict constraints failed during execution preflight."
            )
            log_summary = (
                f"Execution preflight failed.\n{error_text}\n{json.dumps(strict_detail, indent=2)}"
            )
            RunService.update_run_status(
                db,
                run_id,
                "failed",
                result=RunResult(
                    status="failed",
                    error=error_text,
                    log_summary=log_summary,
                ),
                error_message=error_text,
            )
            return

        print(
            f"[BACKGROUND TASK] Updating status to running for run {run_id}",
            file=sys.stderr,
            flush=True,
        )
        RunService.update_run_status(db, run_id, "running")
        print("[BACKGROUND TASK] Status updated to running", file=sys.stderr, flush=True)

        import os

        work_dir = Path(os.getenv("RUNNER_WORK_DIR", "./runner_work"))

        if spec.steps is None or len(spec.steps) == 0:
            print(
                f"[BACKGROUND TASK] Starting Scientific Research Agent for run {run_id}",
                file=sys.stderr,
                flush=True,
            )
            print(
                f"[BACKGROUND TASK] Objective: {spec.objective}",
                file=sys.stderr,
                flush=True,
            )
            print(
                f"[BACKGROUND TASK] Tool lookup keys: {list(tool_lookup.keys())}",
                file=sys.stderr,
                flush=True,
            )

            agent = ScientificResearchAgent(
                work_dir=work_dir,
                tool_lookup=tool_lookup,
                tool_metadata=tool_metadata,
                model=spec.model,
            )

            def update_trajectory(messages):
                try:
                    serialized_messages = []
                    for msg in messages:
                        msg_dict = msg if isinstance(msg, dict) else msg.model_dump()
                        if "timestamp" in msg_dict and msg_dict["timestamp"]:
                            if hasattr(msg_dict["timestamp"], "isoformat"):
                                msg_dict["timestamp"] = msg_dict["timestamp"].isoformat()
                        serialized_messages.append(msg_dict)
                    RunService.append_to_trajectory(db, run_id, serialized_messages)
                    print(
                        f"[BACKGROUND TASK] Updated trajectory with {len(serialized_messages)} messages",
                        file=sys.stderr,
                        flush=True,
                    )
                except Exception as e:
                    print(
                        f"[BACKGROUND TASK] Error updating trajectory: {e}",
                        file=sys.stderr,
                        flush=True,
                    )
                    print(
                        f"[BACKGROUND TASK] Traceback: {traceback.format_exc()}",
                        file=sys.stderr,
                        flush=True,
                    )
                    try:
                        db.rollback()
                    except Exception:
                        pass

            print("[BACKGROUND TASK] Calling agent.run()...", file=sys.stderr, flush=True)
            result, trajectory = agent.run(
                objective=spec.objective,
                datasets=spec.datasets,
                constraints=spec.constraints or {},
                trajectory_callback=update_trajectory,
                model=spec.model,
            )
            print(
                f"[BACKGROUND TASK] Agent completed with status: {result.status}",
                file=sys.stderr,
                flush=True,
            )

            if trajectory:
                serialized_trajectory = []
                for msg in trajectory:
                    msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else msg
                    if "timestamp" in msg_dict and msg_dict["timestamp"]:
                        if hasattr(msg_dict["timestamp"], "isoformat"):
                            msg_dict["timestamp"] = msg_dict["timestamp"].isoformat()
                    serialized_trajectory.append(msg_dict)

                try:
                    db.rollback()
                except Exception:
                    pass

                RunService.update_run_status(
                    db,
                    run_id,
                    "completed" if result.status == "success" else "failed",
                    result=result,
                    error_message=result.error,
                    trajectory=serialized_trajectory,
                )
            else:
                RunService.update_run_status(
                    db,
                    run_id,
                    "completed" if result.status == "success" else "failed",
                    result=result,
                    error_message=result.error,
                )
        else:
            result = run_experiment(spec, tool_lookup, work_dir=work_dir)
            status = "completed" if result.status == "success" else "failed"
            RunService.update_run_status(
                db,
                run_id,
                status,
                result=result,
                error_message=result.error,
            )
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"[BACKGROUND TASK] ERROR in run {run_id}: {e}", file=sys.stderr, flush=True)
        print(f"[BACKGROUND TASK] Traceback:\n{error_trace}", file=sys.stderr, flush=True)

        try:
            db.rollback()
        except Exception:
            pass

        error_result = RunResult(
            status="failed",
            error=str(e),
            log_summary=f"Execution exception: {str(e)}\n{error_trace}",
        )
        try:
            RunService.update_run_status(
                db,
                run_id,
                "failed",
                result=error_result,
                error_message=str(e),
            )
            print(
                f"[BACKGROUND TASK] Marked run {run_id} as failed",
                file=sys.stderr,
                flush=True,
            )
        except Exception as update_error:
            print(
                f"[BACKGROUND TASK] ERROR: Failed to update run status: {update_error}",
                file=sys.stderr,
                flush=True,
            )
            print(f"[BACKGROUND TASK] Original error: {e}", file=sys.stderr, flush=True)
            print(f"[BACKGROUND TASK] Traceback:\n{error_trace}", file=sys.stderr, flush=True)
    finally:
        db.close()


@router.post("/", response_model=RunResponse, status_code=201)
def start_run(
    run: RunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start a new experiment run.

    Supports two modes:
    - Legacy mode: spec.steps is provided (predefined steps)
    - Agent mode: spec.steps is None or empty (autonomous agent)
    """
    try:
        tool_lookup = _get_tool_lookup(db)
        tool_metadata = _get_tool_metadata(db)

        preflight = _build_preflight_payload(db, run.spec, tool_lookup=tool_lookup)
        _raise_for_invalid_preflight(preflight)

        db_run = RunService.create_run(db, run)

        background_tasks.add_task(
            _execute_run_task,
            run_id=db_run.id,
            spec=run.spec,
            tool_lookup=tool_lookup,
            tool_metadata=tool_metadata,
        )
        return db_run
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"{str(e)}\n{traceback.format_exc()}",
        )
