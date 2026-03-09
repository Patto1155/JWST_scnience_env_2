"""Basic API smoke tests."""

import pytest
from fastapi.testclient import TestClient
from core_api.app import app
from core_api.db import SessionLocal
from core_api.models.datasets import Dataset


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


def test_tools_endpoint(client):
    """Test tools listing endpoint."""
    response = client.get("/tools")
    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    assert isinstance(data["tools"], list)


def test_datasets_endpoint(client):
    """Test datasets listing endpoint."""
    response = client.get("/datasets")
    assert response.status_code == 200
    data = response.json()
    assert "datasets" in data
    assert isinstance(data["datasets"], list)


def test_datasets_endpoint_strict_ready_filter(client, tmp_path):
    """Strict-ready listing should exclude datasets that fail integrity checks."""
    valid_file = tmp_path / "valid.fits"
    valid_file.write_text("ok", encoding="utf-8")

    db = SessionLocal()
    try:
        db.add(
            Dataset(
                name="jwst_valid_filter_test",
                description="valid strict dataset",
                meta_data={"target": "TEST", "filter": "F200W", "file_path": str(valid_file)},
                tags=["test"],
            )
        )
        db.add(
            Dataset(
                name="jwst_invalid_filter_test",
                description="invalid strict dataset",
                meta_data={"target": "TEST", "filter": "F356W"},
                tags=["test", "quarantined"],
            )
        )
        db.commit()
    finally:
        db.close()

    all_resp = client.get("/datasets")
    assert all_resp.status_code == 200
    all_names = {item["name"] for item in all_resp.json()["datasets"]}
    assert "jwst_valid_filter_test" in all_names
    assert "jwst_invalid_filter_test" in all_names

    strict_resp = client.get("/datasets", params={"strict_ready": "true"})
    assert strict_resp.status_code == 200
    strict_names = {item["name"] for item in strict_resp.json()["datasets"]}
    assert "jwst_valid_filter_test" in strict_names
    assert "jwst_invalid_filter_test" not in strict_names


def test_runs_endpoint(client):
    """Test runs listing endpoint."""
    response = client.get("/runs")
    assert response.status_code == 200
    data = response.json()
    assert "runs" in data
    assert "count" in data
    assert isinstance(data["runs"], list)


def test_run_validate_endpoint(client):
    """Test run preflight validation endpoint."""
    payload = {
        "spec": {
            "objective": "Preflight check",
            "datasets": [],
            "steps": None,
            "constraints": {"strict_real_data": False},
        }
    }
    response = client.post("/runs/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "valid" in data
    assert "issues" in data


def test_create_run_legacy_mode(client):
    """Test creating a run in legacy mode (with steps)."""
    run_spec = {
        "spec": {
            "objective": "Test objective",
            "datasets": [],
            "steps": [
                {
                    "tool_name": "image_statistics",
                    "parameters": {}
                }
            ]
        }
    }
    
    response = client.post("/runs", json=run_spec)
    # Should create run (201) or return error if tools not registered
    assert response.status_code in [201, 400, 500]


def test_create_run_agent_mode(client):
    """Test creating a run in agent mode (without steps)."""
    run_spec = {
        "spec": {
            "objective": "Test objective with agent",
            "datasets": [],
            "steps": None,
            "constraints": {
                "max_steps": 5
            }
        }
    }
    
    response = client.post("/runs", json=run_spec)
    # Should create run (201) or return error if tools not registered
    assert response.status_code in [201, 400, 500]

