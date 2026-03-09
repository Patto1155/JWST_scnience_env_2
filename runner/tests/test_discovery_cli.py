"""Tests for discovery CLI validation mode."""

from typing import Any, Dict

import run_discovery


class _DummyResponse:
    """Minimal response stub for requests monkeypatching."""

    def __init__(self, payload: Dict[str, Any], status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> Dict[str, Any]:
        return self._payload


def test_run_discovery_dry_run_validate_does_not_queue_runs(monkeypatch):
    """--dry-run-validate flow should call /runs/validate only."""
    calls = []

    monkeypatch.setattr(
        run_discovery,
        "resolve_default_discovery_datasets",
        lambda strict_real_data=True, base_url=run_discovery.BASE_URL: [
            "jwst_test_a",
            "jwst_test_b",
        ],
    )
    monkeypatch.setattr(
        run_discovery,
        "load_discovery_prompt",
        lambda: "Test discovery prompt.",
    )

    def fake_post(url: str, json: Dict[str, Any], timeout: int = 0):
        calls.append(url)
        if url.endswith("/runs/validate"):
            return _DummyResponse(
                {
                    "valid": True,
                    "strict_real_data": True,
                    "checked_datasets": json["spec"]["datasets"],
                    "tool_count": 5,
                    "issue_count": 0,
                    "issues": [],
                    "hints": [],
                    "unresolved_datasets": [],
                    "datasets_missing_file_path": [],
                    "datasets_with_missing_files": [],
                    "quarantined_datasets": [],
                }
            )
        raise AssertionError(f"Unexpected endpoint called in dry-run mode: {url}")

    monkeypatch.setattr(run_discovery.requests, "post", fake_post)

    results = run_discovery.run_discovery_session(
        num_runs=2,
        max_steps=2,
        objective="dry-run check",
        save_output=False,
        live_monitor=False,
        strict_real_data=True,
        dry_run_validate=True,
    )

    assert len(results) == 2
    assert all((entry.get("validation") or {}).get("valid") for entry in results)
    assert calls
    assert all(url.endswith("/runs/validate") for url in calls)


def test_run_discovery_dry_run_validate_uses_custom_base_url(monkeypatch):
    """Validation mode should honor an explicit API base URL."""
    calls = []
    resolved_base_urls = []

    def fake_resolver(
        strict_real_data: bool = True,
        base_url: str = run_discovery.BASE_URL,
    ):
        resolved_base_urls.append(base_url)
        return ["jwst_test_a"]

    monkeypatch.setattr(run_discovery, "resolve_default_discovery_datasets", fake_resolver)
    monkeypatch.setattr(run_discovery, "load_discovery_prompt", lambda: "Test discovery prompt.")

    def fake_post(url: str, json: Dict[str, Any], timeout: int = 0):
        calls.append(url)
        return _DummyResponse(
            {
                "valid": True,
                "strict_real_data": True,
                "checked_datasets": json["spec"]["datasets"],
                "tool_count": 1,
                "issue_count": 0,
                "issues": [],
                "hints": [],
                "unresolved_datasets": [],
                "datasets_missing_file_path": [],
                "datasets_with_missing_files": [],
                "quarantined_datasets": [],
            }
        )

    monkeypatch.setattr(run_discovery.requests, "post", fake_post)

    results = run_discovery.run_discovery_session(
        num_runs=1,
        max_steps=2,
        objective="dry-run custom base url",
        save_output=False,
        live_monitor=False,
        strict_real_data=True,
        dry_run_validate=True,
        base_url="http://127.0.0.1:8001/",
    )

    assert len(results) == 1
    assert resolved_base_urls == ["http://127.0.0.1:8001"]
    assert calls == ["http://127.0.0.1:8001/runs/validate"]


def test_build_discovery_run_payload_includes_minimum_activity_constraints(monkeypatch):
    """Discovery payload should enforce prompt-aligned activity minimums."""
    monkeypatch.setattr(run_discovery, "load_discovery_prompt", lambda: "Prompt")

    payload = run_discovery.build_discovery_run_payload(
        objective="check payload",
        datasets=["jwst_test_a"],
        max_steps=30,
        max_cost=5.0,
        model=None,
        strict_real_data=True,
    )

    constraints = payload["spec"]["constraints"]
    assert constraints["min_successful_tool_calls"] == 12
    assert constraints["min_reflections"] == 2
