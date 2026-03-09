"""API-level strict run validation tests."""

from pathlib import Path
from datetime import timedelta, datetime, timezone
from uuid import uuid4

import numpy as np
import pytest
from astropy.io import fits
from fastapi.testclient import TestClient

from core_api.app import app
from core_api.db import SessionLocal
from core_api.models.datasets import Dataset
from core_api.models.runs import Run
from core_api.routers import runs as runs_router
from core_api.schemas.experiments import ExperimentSpec
from core_api.schemas.runs import RunCreate
from core_api.services.run_service import RunService


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def _insert_dataset(name: str, metadata: dict) -> None:
    """Insert a dataset row for strict-run validation tests."""
    db = SessionLocal()
    try:
        db.add(
            Dataset(
                name=name,
                description="strict validation test dataset",
                meta_data=metadata,
                tags=["test", "strict-validation"],
            )
        )
        db.commit()
    finally:
        db.close()


def _delete_dataset(name: str) -> None:
    """Delete dataset row by name."""
    db = SessionLocal()
    try:
        ds = db.query(Dataset).filter(Dataset.name == name).first()
        if ds is not None:
            db.delete(ds)
            db.commit()
    finally:
        db.close()


def _strict_run_payload(dataset_names: list[str]) -> dict:
    """Build a strict-mode run payload for API validation checks."""
    return {
        "spec": {
            "objective": "Strict validation test run",
            "datasets": dataset_names,
            "steps": [
                {
                    "tool_name": "image_statistics",
                    "parameters": {"image_data": dataset_names[0] if dataset_names else None},
                }
            ],
            "constraints": {"strict_real_data": True, "max_steps": 1},
        }
    }


def test_start_run_strict_rejects_unresolved_dataset(client: TestClient):
    """Strict runs should reject dataset names that do not exist in catalog."""
    missing_name = f"jwst_missing_{uuid4().hex}"

    response = client.post("/runs", json=_strict_run_payload([missing_name]))

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert missing_name in detail["unresolved_datasets"]


def test_start_run_strict_rejects_missing_file_path_metadata(client: TestClient):
    """Strict runs should reject datasets missing metadata.file_path."""
    dataset_name = f"jwst_missing_path_{uuid4().hex}"
    try:
        _insert_dataset(
            dataset_name,
            metadata={"target": "TEST", "filter": "F200W"},
        )

        response = client.post("/runs", json=_strict_run_payload([dataset_name]))

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert dataset_name in detail["datasets_missing_file_path"]
    finally:
        _delete_dataset(dataset_name)


def test_start_run_strict_rejects_nonexistent_file_path(client: TestClient):
    """Strict runs should reject mappings to paths that do not exist."""
    dataset_name = f"jwst_bad_path_{uuid4().hex}"
    fake_path = Path("C:/definitely_missing/does_not_exist.fits")
    try:
        _insert_dataset(
            dataset_name,
            metadata={"target": "TEST", "filter": "F200W", "file_path": str(fake_path)},
        )

        response = client.post("/runs", json=_strict_run_payload([dataset_name]))

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any(item.startswith(dataset_name) for item in detail["datasets_with_missing_files"])
    finally:
        _delete_dataset(dataset_name)


def test_start_run_strict_accepts_resolved_dataset_mapping(client: TestClient, tmp_path: Path):
    """Strict runs should be accepted when dataset mapping resolves to an existing file."""
    dataset_name = f"jwst_valid_path_{uuid4().hex}"
    dummy_file = tmp_path / "dummy.fits"
    fits.writeto(dummy_file, np.zeros((8, 8), dtype=float), overwrite=True)
    try:
        _insert_dataset(
            dataset_name,
            metadata={"target": "TEST", "filter": "F200W", "file_path": str(dummy_file)},
        )

        response = client.post("/runs", json=_strict_run_payload([dataset_name]))

        assert response.status_code == 201
        data = response.json()
        assert data["spec"]["constraints"]["strict_real_data"] is True
    finally:
        _delete_dataset(dataset_name)


def test_validate_run_endpoint_returns_structured_strict_errors(client: TestClient):
    """POST /runs/validate should return actionable strict issue details."""
    missing_name = f"jwst_missing_{uuid4().hex}"

    response = client.post("/runs/validate", json=_strict_run_payload([missing_name]))

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["strict_real_data"] is True
    assert data["issue_count"] >= 1
    assert missing_name in data["unresolved_datasets"]
    assert any(issue["code"] == "STRICT_DATASET_NOT_FOUND" for issue in data["issues"])


def test_execute_run_task_revalidates_strict_constraints(tmp_path: Path):
    """Execution path should fail loudly when strict datasets are invalid."""
    missing_file = tmp_path / "gone.fits"
    dataset_name = f"jwst_runtime_invalid_{uuid4().hex}"

    _insert_dataset(
        dataset_name,
        metadata={
            "target": "TEST",
            "filter": "F200W",
            "file_path": str(missing_file),
        },
    )

    spec = ExperimentSpec(
        objective="runtime strict preflight",
        datasets=[dataset_name],
        steps=[],
        constraints={"strict_real_data": True},
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
            "image_statistics": {
                "module_path": "tools.jwst.basic_stats",
                "function_name": "image_statistics",
            }
        },
    )

    db = SessionLocal()
    try:
        db_run = db.query(Run).filter(Run.id == run.id).first()
        assert db_run is not None
        assert db_run.status == "failed"
        assert "STRICT_RUN_VALIDATION_FAILED" in (db_run.error_message or "")
        assert "Execution preflight failed." in ((db_run.result or {}).get("log_summary", ""))
    finally:
        db.close()
        _delete_dataset(dataset_name)


def test_stuck_queued_run_exposes_reason_hints(client: TestClient):
    """Queued runs older than threshold should expose actionable status hints."""
    spec = ExperimentSpec(
        objective="queued hint test",
        datasets=[],
        steps=[],
        constraints={},
    )

    db = SessionLocal()
    try:
        run = RunService.create_run(db, RunCreate(spec=spec))
        db_run = db.query(Run).filter(Run.id == run.id).first()
        assert db_run is not None
        db_run.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        db.commit()
    finally:
        db.close()

    response = client.get(f"/runs/{run.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["status_reason"] == "stuck_queued"
    assert data["status_hints"]
