"""Operational smoke checks for Science OS API."""

from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, Optional

import requests


EXPECTED_TOOL_NAMES = {
    "extract_photometry",
    "compute_color_index",
    "image_statistics",
    "brightness_distribution",
    "compare_images",
    "detect_sources",
    "candidate_evidence_bundle",
    "render_field_overview",
    "compute_mean",
}


def _get_json(base_url: str, path: str) -> Dict[str, Any]:
    response = requests.get(f"{base_url}{path}", timeout=20)
    response.raise_for_status()
    return response.json()


def _diagnose_validate_contract(base_url: str) -> Optional[str]:
    """Return a diagnostic message if POST /runs/validate is not advertised."""
    try:
        openapi = _get_json(base_url, "/openapi.json")
    except Exception:
        return None

    paths = openapi.get("paths", {})
    validate_ops = paths.get("/runs/validate")
    if isinstance(validate_ops, dict) and "post" in validate_ops:
        return None

    sample_paths = ", ".join(sorted(paths.keys())[:8]) or "(none)"
    return (
        f"Incompatible API schema at {base_url}: expected POST /runs/validate, "
        "but endpoint contract is missing. "
        "Likely cause: older/stale API process on this port. "
        "Remediation: stop stale service and run `python run_api.py` from this repo. "
        f"Observed OpenAPI paths (sample): {sample_paths}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check core API endpoints.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="API base URL (default: http://127.0.0.1:8000)",
    )
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    try:
        health = _get_json(base_url, "/health")
        tools = _get_json(base_url, "/tools")
        tool_names = {tool.get("name") for tool in tools.get("tools", [])}
        datasets = _get_json(base_url, "/datasets?limit=1000")
        strict_datasets = _get_json(base_url, "/datasets?limit=1000&strict_ready=true")
        runs = _get_json(base_url, "/runs")
        contract_issue = _diagnose_validate_contract(base_url)
        if contract_issue:
            raise RuntimeError(contract_issue)
        missing_tools = sorted(EXPECTED_TOOL_NAMES - tool_names)
        if missing_tools:
            raise RuntimeError(
                "Startup tool sync is missing expected tool registrations: "
                + ", ".join(missing_tools)
            )

        preflight_payload: Dict[str, Any] = {
            "spec": {
                "objective": "Smoke preflight",
                "datasets": [],
                "steps": None,
                "constraints": {"strict_real_data": False},
            }
        }
        validate_resp = requests.post(
            f"{base_url}/runs/validate",
            json=preflight_payload,
            timeout=20,
        )
        validate_resp.raise_for_status()
        validation = validate_resp.json()

        strict_rows = strict_datasets.get("datasets", [])
        if not strict_rows:
            raise RuntimeError(
                "No strict-ready datasets available from /datasets?strict_ready=true. "
                "Strict workflows cannot proceed until dataset integrity is repaired."
            )

        strict_preflight_payload: Dict[str, Any] = {
            "spec": {
                "objective": "Smoke strict preflight",
                "datasets": [strict_rows[0]["name"]],
                "steps": None,
                "constraints": {"strict_real_data": True},
            }
        }
        strict_validate_resp = requests.post(
            f"{base_url}/runs/validate",
            json=strict_preflight_payload,
            timeout=20,
        )
        strict_validate_resp.raise_for_status()
        strict_validation = strict_validate_resp.json()
        if not strict_validation.get("valid", False):
            raise RuntimeError(
                "Strict preflight failed for strict-ready dataset "
                f"{strict_rows[0]['name']}: issue_count={strict_validation.get('issue_count')}"
            )
    except Exception as exc:
        print(f"[SMOKE][FAIL] API smoke check failed: {exc}")
        return 1

    print("[SMOKE][OK] /health:", health)
    print("[SMOKE][OK] tools:", len(tools.get("tools", [])))
    print("[SMOKE][OK] datasets:", len(datasets.get("datasets", [])))
    print("[SMOKE][OK] strict-ready datasets:", len(strict_datasets.get("datasets", [])))
    print("[SMOKE][OK] runs:", len(runs.get("runs", [])))
    print(
        "[SMOKE][OK] /runs/validate:",
        {"valid": validation.get("valid"), "issues": validation.get("issue_count")},
    )
    print(
        "[SMOKE][OK] strict /runs/validate:",
        {"valid": strict_validation.get("valid"), "issues": strict_validation.get("issue_count")},
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
