#!/usr/bin/env python
"""
Easy-to-use discovery orchestration script.

Run deep discovery research sessions with a single command.
Optimized for trading tokens for insights.

Usage:
    python run_discovery.py                    # Run single deep discovery session
    python run_discovery.py --runs 3           # Run 3 independent sessions
    python run_discovery.py --steps 50         # Allow 50 steps per session (default: 30)
    python run_discovery.py --allow-dummy      # Disable strict real-data mode
    python run_discovery.py --objective "..."  # Custom research objective
"""

import argparse
import importlib.util
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from requests import RequestException

# Rich monitor availability (no direct import needed here).
RICH_AVAILABLE = importlib.util.find_spec("discovery_monitor") is not None

# Try to import stream printer
try:
    from stream_discovery_win import DiscoveryStreamer

    STREAM_AVAILABLE = True
except ImportError:
    STREAM_AVAILABLE = False


BASE_URL = os.getenv("SCIENCE_OS_API_BASE_URL", "http://localhost:8000").rstrip("/")

# Canonical discovery filters we want by default.
DISCOVERY_DATASET_TARGETS = [
    ("SMACS-J0723.3-7327", "F090W"),
    ("SMACS-J0723.3-7327", "F150W"),
    ("SMACS-J0723.3-7327", "F200W"),
    ("SMACS-J0723.3-7327", "F277W"),
    ("SMACS-J0723.3-7327", "F356W"),
    ("SMACS-J0723.3-7327", "F444W"),
    ("GS-MEDIUM-HST", "F090W"),
    ("GS-MEDIUM-HST", "F150W"),
    ("GS-MEDIUM-HST", "F200W"),
    ("GS-MEDIUM-HST", "F277W"),
    ("GS-MEDIUM-HST", "F356W"),
    ("GS-MEDIUM-HST", "F444W"),
]

DISCOVERY_MIN_SUCCESSFUL_TOOL_CALLS = 12
DISCOVERY_MIN_REFLECTIONS = 2

# Legacy aliases (kept as permissive fallback only when strict mode is disabled).
LEGACY_DEFAULT_DATASETS = [
    "SMACS-J0723.3-7327_F090W",
    "SMACS-J0723.3-7327_F150W",
    "SMACS-J0723.3-7327_F200W",
    "SMACS-J0723.3-7327_F277W",
    "SMACS-J0723.3-7327_F356W",
    "SMACS-J0723.3-7327_F444W",
    "GS-MEDIUM-HST_F090W",
    "GS-MEDIUM-HST_F150W",
    "GS-MEDIUM-HST_F200W",
    "GS-MEDIUM-HST_F277W",
    "GS-MEDIUM-HST_F356W",
    "GS-MEDIUM-HST_F444W",
]


class ApiContractError(RuntimeError):
    """Raised when the target API does not expose the required endpoint contract."""


def normalize_base_url(base_url: Optional[str]) -> str:
    """Normalize API base URLs so callers can pass values with or without a trailing slash."""
    return (base_url or BASE_URL).rstrip("/")


# ============================================================================
# DEFAULT RESEARCH OBJECTIVES (Deep Discovery Focus)
# ============================================================================

DEFAULT_OBJECTIVES = [
    # High-z Galaxy Discovery (Primary)
    """
    Discover high-redshift galaxy candidates in JWST data using comprehensive tool exploration.

    PRIMARY GOAL: Find new z>7 candidates beyond the existing 56 in highz_candidates.json

    APPROACH:
    1. Load existing candidates and analyze their properties systematically
    2. Test unconventional selection criteria (not just F090W dropout)
    3. Explore source-level clustering, morphological features, and multi-band colors
    4. Investigate anomaly catalog for potential missed candidates
    5. Cross-validate with multiple independent methods

    REQUIREMENTS:
    - Minimum 25 tool calls
    - Test at least 3 different high-z identification methods
    - Generate evidence bundles, field overviews, and color diagnostics
    - Quantify confidence levels for all candidates
    - Document what didn't work and why

    Be creative. Try weird hypotheses. Trade tokens for insights.
    """,
    # Systematic Analysis
    """
    Conduct systematic analysis of instrumental effects and data quality across JWST fields.

    INVESTIGATE:
    1. Spatial variations in background, noise, PSF quality
    2. Filter-dependent systematics
    3. Anomaly patterns (cosmic rays vs real sources)
    4. Aperture corrections and photometric biases with evidence panels

    Use quadrant analysis, source catalogs, evidence panels, and multi-aperture photometry.
    Minimum 20 tool calls.
    """,
    # Multi-Method Discovery
    """
    Test multiple independent high-z selection methods and compare results.

    METHODS TO TEST:
    1. Color dropout (F090W/F444W < threshold)
    2. Source-level peaks in red filters
    3. Color-color diagram selection
    4. Morphological compactness
    5. Spatial clustering with known candidates

    Cross-match results. Find consensus candidates (detected by 3+ methods) and save evidence bundles for the strongest ones.
    Minimum 30 tool calls.
    """,
]


# ============================================================================
# CORE FUNCTIONS
# ============================================================================


def load_discovery_prompt() -> str:
    """Load the comprehensive discovery prompt."""
    prompt_path = Path(__file__).parent / "memory_bank" / "DISCOVERY_PROMPT.md"

    if prompt_path.exists():
        with open(prompt_path, "r") as f:
            return f.read()
    else:
        print(f"[WARNING] Discovery prompt not found at {prompt_path}")
        return "Follow rigorous scientific method for high-z galaxy discovery."


def _pick_best_dataset_name(
    datasets: List[Dict[str, Any]],
    target: str,
    filter_name: str,
) -> Optional[str]:
    """Choose best matching dataset name (prefer i2d products)."""
    matches = []
    target_upper = target.upper()
    filter_upper = filter_name.upper()

    for ds in datasets:
        name = ds.get("name", "")
        metadata = ds.get("metadata") or {}
        ds_target = str(metadata.get("target", "")).upper()
        ds_filter = str(metadata.get("filter", "")).upper()

        if ds_target == target_upper and ds_filter == filter_upper:
            lname = name.lower()
            score = 0
            if "i2d" in lname:
                score += 100
            elif "_cal" in lname:
                score += 50
            elif "_crf" in lname:
                score += 25
            matches.append((score, name))

    if not matches:
        # Metadata may be incomplete for some records; fallback to name matching.
        for ds in datasets:
            name = ds.get("name", "")
            lname = name.lower()
            if target.lower() in lname and filter_name.lower() in lname:
                score = 0
                if "i2d" in lname:
                    score += 100
                elif "_cal" in lname:
                    score += 50
                elif "_crf" in lname:
                    score += 25
                matches.append((score, name))

    if not matches:
        return None

    matches.sort(reverse=True)
    return matches[0][1]


def resolve_default_discovery_datasets(
    strict_real_data: bool = True,
    *,
    base_url: str = BASE_URL,
) -> List[str]:
    """
    Resolve canonical dataset names for default discovery campaigns.

    In strict mode, this fails if required target/filter pairs cannot be mapped.
    """
    base_url = normalize_base_url(base_url)
    try:
        params: Dict[str, Any] = {"limit": 1000}
        if strict_real_data:
            params["strict_ready"] = True

        response = requests.get(
            f"{base_url}/datasets/",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        datasets = response.json().get("datasets", [])
    except Exception as e:
        if strict_real_data:
            raise RuntimeError(
                "Failed to fetch dataset catalog for strict discovery mode. "
                "Ensure API is running and datasets are registered."
            ) from e
        print(f"[WARNING] Could not resolve canonical datasets via API: {e}")
        print("[WARNING] Falling back to legacy alias dataset names")
        return LEGACY_DEFAULT_DATASETS

    resolved = []
    missing = []
    for target, filt in DISCOVERY_DATASET_TARGETS:
        name = _pick_best_dataset_name(datasets, target=target, filter_name=filt)
        if name:
            resolved.append(name)
        else:
            missing.append(f"{target}:{filt}")

    if missing and strict_real_data:
        raise ValueError(
            "Strict discovery mode requires real dataset mappings for all default "
            f"target/filter pairs. Missing: {', '.join(missing)}"
        )

    if missing:
        print(f"[WARNING] Missing default mappings: {', '.join(missing)}")

    return resolved if resolved else LEGACY_DEFAULT_DATASETS


def submit_discovery_run(
    objective: str,
    datasets: Optional[List[str]] = None,
    max_steps: int = 30,
    max_cost: float = 5.0,
    model: Optional[str] = None,
    strict_real_data: bool = True,
    perform_preflight: bool = True,
    *,
    base_url: str = BASE_URL,
) -> Dict:
    """
    Submit a discovery research run.

    Args:
        objective: Research objective (can include discovery prompt context)
        datasets: List of datasets to analyze
        max_steps: Maximum tool calls allowed
        max_cost: Maximum cost in USD
        model: LLM model to use (e.g., 'claude-3.5-sonnet', 'deepseek-v3.2')
        strict_real_data: Disable dummy fallback for JWST data loading

    Returns:
        Run metadata (id, status, etc.)
    """
    base_url = normalize_base_url(base_url)
    if datasets is None:
        datasets = resolve_default_discovery_datasets(
            strict_real_data=strict_real_data,
            base_url=base_url,
        )

    payload = build_discovery_run_payload(
        objective=objective,
        datasets=datasets,
        max_steps=max_steps,
        max_cost=max_cost,
        model=model,
        strict_real_data=strict_real_data,
    )

    print(f"\n{'=' * 80}")
    print("SUBMITTING DISCOVERY RUN")
    print(f"{'=' * 80}")
    print(f"Objective: {objective[:100]}...")
    print(f"Datasets: {len(datasets)} filters")
    print(f"Max steps: {max_steps}")
    print(f"Max cost: ${max_cost}")
    print(f"Strict real-data mode: {strict_real_data}")
    if model:
        print(f"Model: {model}")
    print(f"{'=' * 80}\n")

    if perform_preflight:
        validation = validate_run_preflight(payload, base_url=base_url)
        if not validation.get("valid", False):
            raise RuntimeError(
                "Run preflight validation failed:\n" + format_preflight_issues(validation)
            )

    response = requests.post(f"{base_url}/runs/", json=payload, timeout=30)
    response.raise_for_status()

    result = response.json()
    print(f"[OK] Run submitted: ID={result['id']}")
    return result


def check_run_status(run_id: int, *, base_url: str = BASE_URL) -> Dict:
    """Check the status of a run."""
    base_url = normalize_base_url(base_url)
    response = requests.get(f"{base_url}/runs/{run_id}", timeout=20)
    response.raise_for_status()
    return response.json()


def build_discovery_run_payload(
    objective: str,
    datasets: List[str],
    max_steps: int,
    max_cost: float,
    model: Optional[str],
    strict_real_data: bool,
) -> Dict[str, Any]:
    """Build canonical discovery run payload used for validate + queue."""
    discovery_prompt = load_discovery_prompt()
    full_objective = f"""{objective}

---
METHODOLOGY GUIDE:
{discovery_prompt}
"""
    payload: Dict[str, Any] = {
        "spec": {
            "objective": full_objective,
            "datasets": datasets,
            "steps": None,
            "constraints": {
                "max_steps": max_steps,
                "max_cost": max_cost,
                "strict_real_data": strict_real_data,
                "min_successful_tool_calls": DISCOVERY_MIN_SUCCESSFUL_TOOL_CALLS,
                "min_reflections": DISCOVERY_MIN_REFLECTIONS,
            },
        }
    }
    if model:
        payload["spec"]["model"] = model
    return payload


def validate_run_preflight(
    payload: Dict[str, Any],
    *,
    base_url: str = BASE_URL,
) -> Dict[str, Any]:
    """Validate a run payload before queueing."""
    base_url = normalize_base_url(base_url)
    try:
        response = requests.post(f"{base_url}/runs/validate", json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as exc:
        response = exc.response
        if response is not None and response.status_code in (404, 405):
            diagnostic = diagnose_validate_endpoint(base_url)
            if diagnostic:
                raise ApiContractError(diagnostic) from exc
        raise


def diagnose_validate_endpoint(base_url: str) -> Optional[str]:
    """Return an actionable diagnostics message when /runs/validate is unavailable."""
    try:
        response = requests.get(f"{base_url}/openapi.json", timeout=10)
        response.raise_for_status()
        paths = (response.json() or {}).get("paths", {})
    except Exception:
        return None

    validate_ops = paths.get("/runs/validate")
    if isinstance(validate_ops, dict) and "post" in validate_ops:
        return None

    sample_paths = ", ".join(sorted(paths.keys())[:8]) or "(none)"
    return (
        f"Incompatible API schema at {base_url}: expected POST /runs/validate, "
        "but that endpoint is not available. This usually means an older/stale API "
        "process is bound to the configured port. "
        "Remediation: stop the current service on that port and launch this repository's "
        "API (`python run_api.py`), then retry preflight. "
        f"Observed OpenAPI paths (sample): {sample_paths}"
    )


def format_preflight_issues(validation_payload: Dict[str, Any], *, limit: int = 8) -> str:
    """Format preflight failures into concise operator-readable text."""
    issues = validation_payload.get("issues", [])
    if not issues:
        return "No detailed issues were returned by /runs/validate."

    lines: List[str] = []
    for issue in issues[:limit]:
        dataset = issue.get("dataset")
        location = f" dataset={dataset}" if dataset else ""
        file_path = issue.get("file_path")
        file_text = f" path={file_path}" if file_path else ""
        hint = issue.get("hint")
        hint_text = f" | hint: {hint}" if hint else ""
        lines.append(
            f"- {issue.get('code', 'UNKNOWN')}: {issue.get('message', 'validation failure')}{location}{file_text}{hint_text}"
        )

    extra = len(issues) - len(lines)
    if extra > 0:
        lines.append(f"- ... and {extra} more issue(s)")
    return "\n".join(lines)


def _result_payload(run_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract nested result payload from a run response."""
    payload = run_data.get("result")
    return payload if isinstance(payload, dict) else {}


def _run_log_summary(run_data: Dict[str, Any]) -> str:
    """Return run log summary text."""
    return str(_result_payload(run_data).get("log_summary", "") or "")


def _run_error_text(run_data: Dict[str, Any]) -> str:
    """Return best available run error text."""
    payload = _result_payload(run_data)
    return str(payload.get("error") or run_data.get("error_message") or "")


def _count_tool_calls(log_summary: str) -> int:
    """Count tool execution lines for both executor and scientific-agent logs."""
    count = 0
    for line in (log_summary or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("Executing tool:") or stripped.startswith("Executing "):
            count += 1
    return count


def _is_strict_data_failure(text: str) -> bool:
    """Detect strict real-data loader/integrity failures from text."""
    normalized = (text or "").lower()
    markers = (
        "strict_data_load_failure",
        "strict real-data mode enabled",
        "dummy fallback is disabled",
        "no file_path in metadata",
        "could not load dataset",
    )
    return any(marker in normalized for marker in markers)


def _parse_iso_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO timestamps defensively (supports trailing Z)."""
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def wait_for_completion(
    run_ids: List[int],
    poll_interval: int = 5,
    timeout: int = 1800,
    verbose: bool = True,
    live_monitor: bool = True,
    stream_mode: bool = False,
    *,
    base_url: str = BASE_URL,
) -> List[Dict]:
    """
    Wait for multiple runs to complete.

    Args:
        run_ids: List of run IDs to monitor
        poll_interval: Seconds between status checks
        timeout: Maximum seconds to wait
        verbose: Print progress updates
        live_monitor: Use rich live dashboard (if available)
        stream_mode: Stream agent thinking in real-time (single run only)

    Returns:
        List of completed run data
    """
    base_url = normalize_base_url(base_url)
    # Stream mode - watch agent thinking live (single run only)
    if stream_mode and STREAM_AVAILABLE and len(run_ids) == 1:
        streamer = DiscoveryStreamer(run_ids[0], base_url=base_url)
        streamer.stream(poll_interval=poll_interval, timeout=timeout)
        return [check_run_status(run_ids[0], base_url=base_url)]

    # Rich monitor can hang on some Windows terminals; use text monitor for reliability.
    if live_monitor and RICH_AVAILABLE and verbose and not stream_mode:
        print(
            "[NOTE] Live dashboard disabled for reliability on this terminal; using text monitor."
        )

    # Fallback to simple text monitoring
    start_time = time.time()
    completed: Dict[int, Dict[str, Any]] = {}
    request_failures: Dict[int, int] = {}
    stuck_queue_notified: set[int] = set()

    if verbose:
        print(f"\n{'=' * 80}")
        print(f"MONITORING {len(run_ids)} DISCOVERY RUN(S)")
        print(f"{'=' * 80}\n")

    while len(completed) < len(run_ids):
        elapsed = time.time() - start_time
        if elapsed > timeout:
            print(f"\n[TIMEOUT] Timeout reached after {timeout}s")
            break

        for run_id in run_ids:
            if run_id in completed:
                continue

            try:
                data = check_run_status(run_id, base_url=base_url)
                request_failures[run_id] = 0
            except RequestException as req_error:
                request_failures[run_id] = request_failures.get(run_id, 0) + 1
                if verbose and request_failures[run_id] in (1, 3, 6):
                    print(
                        f"  [WARN] Run {run_id} status check failed "
                        f"({request_failures[run_id]}x): {req_error}"
                    )
                continue

            status = data.get("status")
            if status == "queued" and data.get("status_reason") == "stuck_queued":
                if run_id not in stuck_queue_notified:
                    stuck_queue_notified.add(run_id)
                    print(f"  [WARN] Run {run_id} appears stuck in queue.")
                    for hint in (data.get("status_hints") or [])[:3]:
                        print(f"    - {hint}")

            if status not in ("completed", "failed"):
                continue

            completed[run_id] = data
            if not verbose:
                continue

            started_dt = _parse_iso_timestamp(data.get("started_at") or data.get("created_at"))
            completed_dt = _parse_iso_timestamp(
                data.get("completed_at") or data.get("updated_at") or data.get("created_at")
            )
            duration = (
                (completed_dt - started_dt).total_seconds() if started_dt and completed_dt else 0.0
            )

            print(f"  Run {run_id}: {status.upper()} ({duration:.1f}s)")

            logs = _run_log_summary(data)
            tool_calls = _count_tool_calls(logs)
            if status == "completed":
                print(f"    - Tool calls: {tool_calls}")
                continue

            error = _run_error_text(data)
            if _is_strict_data_failure(error) or _is_strict_data_failure(logs):
                print("    - Strict data failure detected")
            for hint in (data.get("status_hints") or [])[:2]:
                print(f"    - Hint: {hint}")
            if error:
                print(f"    - Error: {error[:180]}")

        if len(completed) < len(run_ids):
            remaining = len(run_ids) - len(completed)
            if verbose and int(elapsed) % 30 == 0:
                print(f"  [WAIT] {remaining} run(s) still processing... ({elapsed:.0f}s elapsed)")
            time.sleep(poll_interval)

    if verbose:
        print(f"\n{'=' * 80}")
        print("ALL RUNS COMPLETED")
        print(f"{'=' * 80}\n")

    return [completed[rid] for rid in run_ids if rid in completed]


def save_results(
    results: List[Dict],
    output_file: Optional[str] = None,
) -> Path:
    """Save discovery results to JSON file."""
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"research_output/discovery_runs_{timestamp}.json"

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"[SAVED] Results saved to: {output_path}")
    return output_path


def print_summary(results: List[Dict]):
    """Print a summary of discovery results."""
    print(f"\n{'=' * 80}")
    print("DISCOVERY SESSION SUMMARY")
    print(f"{'=' * 80}\n")

    for i, result in enumerate(results, 1):
        print(f"Run {i} (ID={result['id']}):")
        print(f"  Status: {result['status']}")

        strict_enabled = bool(
            (result.get("spec", {}).get("constraints") or {}).get("strict_real_data", False)
        )
        print(f"  Strict real-data: {'enabled' if strict_enabled else 'disabled'}")

        if result["status"] == "completed":
            logs = _run_log_summary(result)
            tool_calls = _count_tool_calls(logs)
            print(f"  Tool calls: {tool_calls}")

            trajectory = result.get("trajectory", [])
            if trajectory:
                print(f"  Messages: {len(trajectory)}")

            if "Final Findings:" in logs:
                findings_start = logs.index("Final Findings:")
                findings = logs[findings_start : findings_start + 500]
                print(f"  Findings preview: {findings[:200]}...")

        elif result["status"] == "failed":
            logs = _run_log_summary(result)
            error = _run_error_text(result) or "Unknown error"
            if _is_strict_data_failure(error) or _is_strict_data_failure(logs):
                print("  Strict data failure detected")
            print(f"  Error: {error[:180]}...")

        print()

    print(f"{'=' * 80}\n")


def print_validation_summary(validations: List[Dict[str, Any]]) -> None:
    """Print summary for --dry-run-validate preflight mode."""
    print(f"\n{'=' * 80}")
    print("DISCOVERY PREFLIGHT SUMMARY")
    print(f"{'=' * 80}\n")
    for i, entry in enumerate(validations, 1):
        validation = entry.get("validation", {})
        print(f"Validation {i}:")
        print(f"  Strict real-data: {validation.get('strict_real_data')}")
        print(f"  Valid: {validation.get('valid')}")
        print(f"  Datasets: {len(entry.get('datasets', []))}")
        if not validation.get("valid", False):
            print("  Issues:")
            for line in format_preflight_issues(validation, limit=4).splitlines():
                print(f"    {line}")
        print()


# ============================================================================
# MAIN ORCHESTRATION
# ============================================================================


def run_discovery_session(
    num_runs: int = 1,
    max_steps: int = 30,
    objective: Optional[str] = None,
    datasets: Optional[List[str]] = None,
    save_output: bool = True,
    live_monitor: bool = True,
    model: Optional[str] = None,
    stream_mode: bool = False,
    strict_real_data: bool = True,
    dry_run_validate: bool = False,
    base_url: str = BASE_URL,
) -> List[Dict]:
    """
    Run a complete discovery session.

    Args:
        num_runs: Number of independent runs to execute
        max_steps: Maximum tool calls per run
        objective: Custom research objective (uses default if None)
        datasets: Custom dataset list (uses defaults if None)
        save_output: Whether to save results to file
        live_monitor: Use rich live dashboard (if available)
        model: LLM model to use (e.g., 'claude-3.5-sonnet', 'deepseek-v3.2')
        stream_mode: Stream agent thinking in real-time (single run only)
        strict_real_data: Disable dummy fallback for JWST data loading

    Returns:
        List of completed run results
    """
    base_url = normalize_base_url(base_url)
    # Select objectives
    if objective:
        objectives = [objective] * num_runs
    else:
        # Use default objectives (cycle if num_runs > len(defaults))
        objectives = [DEFAULT_OBJECTIVES[i % len(DEFAULT_OBJECTIVES)] for i in range(num_runs)]

    # Submit all runs (or run validation-only mode)
    run_ids = []
    validations: List[Dict[str, Any]] = []
    for i, obj in enumerate(objectives, 1):
        if dry_run_validate:
            print(f"\n[{i}/{num_runs}] Validating run payload...")
            run_datasets = datasets
            if run_datasets is None:
                run_datasets = resolve_default_discovery_datasets(
                    strict_real_data=strict_real_data,
                    base_url=base_url,
                )
            payload = build_discovery_run_payload(
                objective=obj,
                datasets=run_datasets,
                max_steps=max_steps,
                max_cost=5.0,
                model=model,
                strict_real_data=strict_real_data,
            )
            validation = validate_run_preflight(payload, base_url=base_url)
            validations.append(
                {
                    "objective": obj,
                    "datasets": run_datasets,
                    "validation": validation,
                }
            )
            if validation.get("valid", False):
                print("  [OK] Preflight passed")
            else:
                print("  [FAIL] Preflight failed")
                print(format_preflight_issues(validation))
            continue

        print(f"\n[{i}/{num_runs}] Submitting run...")
        result = submit_discovery_run(
            objective=obj,
            datasets=datasets,
            max_steps=max_steps,
            model=model,
            strict_real_data=strict_real_data,
            perform_preflight=True,
            base_url=base_url,
        )
        run_ids.append(result["id"])
        time.sleep(1)  # Small delay between submissions

    if dry_run_validate:
        print_validation_summary(validations)
        return validations

    # Wait for completion with live monitoring or streaming
    results = wait_for_completion(
        run_ids,
        poll_interval=2 if stream_mode else 5,
        timeout=1800,
        live_monitor=live_monitor,
        stream_mode=stream_mode,
        base_url=base_url,
    )

    # Save results
    if save_output:
        save_results(results)

    # Print summary
    print_summary(results)

    return results


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run deep discovery research sessions on JWST data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_discovery.py                      # Single run with defaults
  python run_discovery.py --runs 3             # Run 3 independent sessions
  python run_discovery.py --steps 50           # Allow 50 tool calls
  python run_discovery.py --allow-dummy        # Permit dummy fallback (not recommended)
  python run_discovery.py --dry-run-validate   # Validate strict preflight only
  python run_discovery.py --base-url http://127.0.0.1:8001 --dry-run-validate
  python run_discovery.py --objective "Find red galaxies"  # Custom objective
  python run_discovery.py --model deepseek-v3.2  # Use DeepSeek model
  python run_discovery.py --stream             # Watch agent thinking in real-time!
        """,
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of independent discovery runs (default: 1)",
    )

    parser.add_argument(
        "--steps",
        type=int,
        default=30,
        help="Maximum tool calls per run (default: 30, try 50+ for deep discovery)",
    )

    parser.add_argument(
        "--objective",
        type=str,
        default=None,
        help="Custom research objective (uses defaults if not specified)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM model to use (claude-3.5-sonnet, deepseek-v3.2, grok-4.1-fast, gemini-3-pro, gpt-5.1-codex-mini)",
    )

    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save results to file",
    )

    parser.add_argument(
        "--no-live",
        action="store_true",
        help="Disable live monitoring dashboard (use simple text output)",
    )

    parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream agent thinking in real-time (shows all responses, reflections, tool calls)",
    )

    parser.add_argument(
        "--allow-dummy",
        action="store_true",
        help="Allow dummy data fallback when real JWST data is missing (disables strict mode)",
    )

    parser.add_argument(
        "--dry-run-validate",
        action="store_true",
        help="Validate run payload(s) via POST /runs/validate without queueing execution",
    )

    parser.add_argument(
        "--base-url",
        type=str,
        default=BASE_URL,
        help=(f"Science OS API base URL (default: {BASE_URL}; env: SCIENCE_OS_API_BASE_URL)"),
    )

    args = parser.parse_args()

    # Validate stream mode (only works with single run)
    if args.stream and args.runs > 1:
        print("[WARNING] --stream only works with single runs. Setting --runs=1")
        args.runs = 1

    # Show rich availability
    if not args.no_live and not RICH_AVAILABLE and not args.stream:
        print("[NOTE] Rich library not available, using simple monitoring")
        print("   Install with: pip install rich\n")

    if args.stream and not STREAM_AVAILABLE:
        print("[NOTE] Stream mode not available (missing dependencies)")
        print("   Install with: pip install rich")
        print("   Falling back to live dashboard...\n")
        args.stream = False

    # Run discovery session
    try:
        results = run_discovery_session(
            num_runs=args.runs,
            max_steps=args.steps,
            objective=args.objective,
            save_output=not args.no_save,
            live_monitor=not args.no_live and not args.stream,
            model=args.model,
            stream_mode=args.stream,
            strict_real_data=not args.allow_dummy,
            dry_run_validate=args.dry_run_validate,
            base_url=args.base_url.rstrip("/"),
        )

        if args.dry_run_validate:
            passed = sum(
                1 for entry in results if (entry.get("validation") or {}).get("valid", False)
            )
            print("[COMPLETE] Discovery preflight validation complete!")
            print(f"   Valid payloads: {passed}/{args.runs}")
        else:
            print("[COMPLETE] Discovery session complete!")
            print(f"   Completed runs: {len(results)}/{args.runs}")

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Discovery session interrupted by user")
    except ApiContractError as e:
        print(f"\n\n[ERROR] Discovery session failed: {e}")
        raise SystemExit(2)
    except Exception as e:
        print(f"\n\n[ERROR] Discovery session failed: {e}")
        raise


if __name__ == "__main__":
    main()
