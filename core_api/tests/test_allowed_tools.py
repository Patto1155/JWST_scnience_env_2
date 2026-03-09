"""Tests for allowed_tools constraint handling."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from core_api.app import app
from core_api.db import SessionLocal
from core_api.schemas.experiments import ExperimentSpec
from core_api.schemas.runs import RunCreate
from core_api.services.run_service import RunService
from core_api.routers import runs as runs_router
from runner.result_schema import RunResult


def test_validate_run_rejects_empty_allowed_tools() -> None:
    """Preflight should reject empty allowed_tools constraints."""
    client = TestClient(app)

    response = client.post(
        "/runs/validate",
        json={
            "spec": {
                "objective": "allowed tools test",
                "datasets": [],
                "steps": [],
                "constraints": {"allowed_tools": []},
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert any(issue["code"] == "RUN_ALLOWED_TOOLS_EMPTY" for issue in payload["issues"])


def test_validate_run_rejects_unknown_allowed_tool() -> None:
    """Preflight should reject unknown tool names inside allowed_tools."""
    client = TestClient(app)

    response = client.post(
        "/runs/validate",
        json={
            "spec": {
                "objective": "allowed tools test",
                "datasets": [],
                "steps": [],
                "constraints": {"allowed_tools": ["not_a_real_tool"]},
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert any(issue["code"] == "RUN_ALLOWED_TOOL_UNKNOWN" for issue in payload["issues"])


@patch("core_api.routers.runs.ScientificResearchAgent")
def test_execute_run_task_filters_tool_visibility_for_agent(mock_agent_cls) -> None:
    """Execution should only expose allowed tools to the scientific agent."""
    mock_agent = mock_agent_cls.return_value
    mock_agent.run.return_value = (
        RunResult(status="success", summary_metrics={}, artifacts=[], log_summary=""),
        [],
    )

    spec = ExperimentSpec(
        objective="filter tool visibility",
        datasets=[],
        steps=[],
        constraints={"allowed_tools": ["extract_photometry"]},
    )
    db = SessionLocal()
    try:
        run = RunService.create_run(db, RunCreate(spec=spec))
    finally:
        db.close()

    runs_router._execute_run_task(
        run_id=run.id,
        spec=spec,
        tool_lookup={
            "extract_photometry": {"module_path": "tools.jwst.photometry", "function_name": "extract_photometry"},
            "compute_color_index": {"module_path": "tools.jwst.photometry", "function_name": "compute_color_index"},
        },
        tool_metadata={
            "extract_photometry": {"description": "ok"},
            "compute_color_index": {"description": "hidden"},
        },
    )

    kwargs = mock_agent_cls.call_args.kwargs
    assert set(kwargs["tool_lookup"].keys()) == {"extract_photometry"}
    assert set(kwargs["tool_metadata"].keys()) == {"extract_photometry"}
