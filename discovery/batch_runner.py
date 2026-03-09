"""
Batch runner for scaling up scientific discovery runs.

This helper keeps strict real-data mode enabled by default and resolves
canonical datasets from the API catalog.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


BASE_URL = "http://localhost:8000"


def _resolve_default_datasets(limit: int = 6) -> List[str]:
    """Resolve strict-ready canonical datasets from /datasets."""
    response = requests.get(f"{BASE_URL}/datasets/", params={"limit": 1000}, timeout=20)
    response.raise_for_status()
    datasets = response.json().get("datasets", [])

    resolved: List[str] = []
    for ds in datasets:
        name = str(ds.get("name", ""))
        metadata = ds.get("metadata") or {}
        file_path = metadata.get("file_path")
        if not name.startswith("jwst_"):
            continue
        if not isinstance(file_path, str) or not file_path.strip():
            continue
        resolved.append(name)
        if len(resolved) >= limit:
            break

    if not resolved:
        raise RuntimeError(
            "No strict-ready canonical datasets found. "
            "Check GET /datasets and repair metadata.file_path."
        )
    return resolved


def submit_research_question(
    objective: str,
    datasets: Optional[List[str]] = None,
    constraints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Submit a single research question."""
    if datasets is None:
        datasets = _resolve_default_datasets()

    if constraints is None:
        constraints = {"max_steps": 15, "strict_real_data": True}

    payload = {
        "spec": {
            "objective": objective,
            "datasets": datasets,
            "steps": None,
            "constraints": constraints,
        }
    }

    response = requests.post(f"{BASE_URL}/runs/", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def check_run_status(run_id: int) -> Dict[str, Any]:
    """Check status of a run."""
    response = requests.get(f"{BASE_URL}/runs/{run_id}", timeout=20)
    response.raise_for_status()
    return response.json()


def wait_for_completion(
    run_ids: List[int],
    poll_interval: int = 5,
    timeout: int = 600,
) -> List[Dict[str, Any]]:
    """Wait for multiple runs to complete."""
    start_time = time.time()
    completed: Dict[int, Dict[str, Any]] = {}

    print(f"Monitoring {len(run_ids)} runs...")

    while len(completed) < len(run_ids):
        if time.time() - start_time > timeout:
            print(f"Timeout reached after {timeout}s")
            break

        for run_id in run_ids:
            if run_id in completed:
                continue

            try:
                data = check_run_status(run_id)
            except Exception as exc:
                print(f"  [WARN] Status check failed for run {run_id}: {exc}")
                continue

            if data["status"] in ["completed", "failed"]:
                completed[run_id] = data
                print(f"  Run {run_id}: {data['status']}")

        if len(completed) < len(run_ids):
            time.sleep(poll_interval)

    return [completed[rid] for rid in run_ids if rid in completed]


def batch_submit(questions: List[str], datasets: Optional[List[str]] = None) -> List[int]:
    """Submit multiple research questions and return run IDs."""
    print(f"Submitting {len(questions)} research questions...")
    run_ids: List[int] = []
    for i, question in enumerate(questions, 1):
        print(f"  [{i}/{len(questions)}] {question[:60]}...")
        result = submit_research_question(question, datasets)
        run_ids.append(result["id"])

    print(f"\n[OK] Submitted {len(run_ids)} runs")
    print(f"  Run IDs: {min(run_ids)} - {max(run_ids)}")
    return run_ids


def save_results(results: List[Dict[str, Any]], output_file: Optional[str] = None) -> Path:
    """Save results to JSON file."""
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"discovery/results_{timestamp}.json"

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n[OK] Results saved to {output_path}")
    return output_path


RESEARCH_CAMPAIGNS = {
    "photometry": [
        "What is the optimal aperture size for photometry in this field?",
        "Identify the 10 brightest sources and measure their photometry",
        "Is there a relationship between source brightness and position?",
        "Compare photometric measurements at different detector positions",
        "What is the photometric zero point for this observation?",
    ],
    "morphology": [
        "Identify extended vs point sources in the field",
        "What is the typical source size distribution?",
        "Are there any peculiar morphologies or asymmetries?",
        "Compare central concentration of different sources",
        "Detect and characterize any diffuse emission",
    ],
    "quality": [
        "Assess the overall image quality and signal-to-noise",
        "Identify any artifacts or detector issues",
        "Characterize the PSF across the field",
        "Is there evidence of saturation or nonlinearity?",
        "Compare noise levels in different regions",
    ],
    "systematic": [
        "Search for any systematic gradients across the detector",
        "Are there periodic patterns that could indicate instrumental effects?",
        "Compare statistics between different quadrants",
        "Identify any hot pixels or cosmic rays",
        "Assess flat-fielding quality",
    ],
}


def run_campaign(
    campaign_name: str, datasets: Optional[List[str]] = None
) -> Optional[List[Dict[str, Any]]]:
    """Run a predefined research campaign."""
    if campaign_name not in RESEARCH_CAMPAIGNS:
        print(f"Unknown campaign: {campaign_name}")
        print(f"Available: {list(RESEARCH_CAMPAIGNS.keys())}")
        return None

    questions = RESEARCH_CAMPAIGNS[campaign_name]
    print(f"\n{'=' * 80}")
    print(f"RESEARCH CAMPAIGN: {campaign_name.upper()}")
    print(f"{'=' * 80}")

    run_ids = batch_submit(questions, datasets)
    print("\nWaiting for results...")
    results = wait_for_completion(run_ids, poll_interval=3, timeout=600)
    output_file = f"discovery/{campaign_name}_results.json"
    save_results(results, output_file)
    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        run_campaign(sys.argv[1])
    else:
        print("Usage: python batch_runner.py [campaign_name]")
        print(f"Available campaigns: {list(RESEARCH_CAMPAIGNS.keys())}")
