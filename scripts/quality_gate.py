"""Discover Python lint targets, run tests, and reject unapproved skips."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LINT_BASELINE = PROJECT_ROOT / "scripts" / "lint_baseline.json"
# Exact test identities and their only acceptable data-absence reasons.
# SKIP remains unexecuted coverage; this allow-list never makes it a PASS.
VISUAL_TEST_MODULE = "runner.tests.test_jwst_visual_tools."
ARCHIVE_MISSING_REASON = "Local JWST archive not provisioned:"
CUE_MISSING_REASON = "set JWST_CUE_ARCHIVE to independently pinned Cue v0.1 archive"
ALLOWED_SKIPS = {
    VISUAL_TEST_MODULE
    + "test_real_jwst_visual_tools_generate_catalog_evidence_and_overview": ARCHIVE_MISSING_REASON,
    VISUAL_TEST_MODULE
    + "test_build_universe_table_pipeline_returns_source_level_candidate_artifacts": (
        ARCHIVE_MISSING_REASON
    ),
    "tests.test_cue_grid.test_author_numpy_forward_replay_on_actual_pinned_weights": (
        CUE_MISSING_REASON
    ),
}


def _run_step(name: str, cmd: list[str]) -> bool:
    print(f"[QUALITY] {name}: {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    print(f"[QUALITY][{'OK' if result.returncode == 0 else 'FAIL'}] {name}", flush=True)
    return result.returncode == 0


def diagnostic_key(item: dict, root: Path) -> str:
    """Line content fingerprints survive line moves but never new file paths."""
    path = Path(item["filename"])
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    lines = path.read_text(encoding="utf-8").splitlines()
    line = item["location"]["row"]
    source = lines[line - 1] if line <= len(lines) else ""
    return json.dumps([relative, item["code"], item["message"], source], ensure_ascii=True)


def new_diagnostics(items: list[dict], baseline: list[str], root: Path) -> list[str]:
    """Reject added occurrences even when the diagnostic text is already known."""
    remaining = Counter(baseline)
    added = []
    for item in items:
        key = diagnostic_key(item, root)
        if remaining[key]:
            remaining[key] -= 1
        else:
            added.append(key)
    return added


def check_discovered_lint() -> bool:
    """Ruff discovers the whole tree; preexisting debt is explicitly recorded."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--select",
            "E,F,I",
            "--output-format",
            "json",
            ".",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        print(f"[QUALITY][FAIL] Ruff execution: {result.stderr}")
        return False
    baseline = json.loads(LINT_BASELINE.read_text(encoding="utf-8"))
    added = new_diagnostics(json.loads(result.stdout), baseline["diagnostics"], PROJECT_ROOT)
    for diagnostic in added:
        print(f"[QUALITY][FAIL] New lint diagnostic: {diagnostic}")
    print(
        f"[QUALITY] Whole-tree lint: {len(added)} new diagnostics; "
        f"{len(baseline['diagnostics'])} recorded legacy occurrences"
    )
    return not added


def check_pytest_skips(report: Path) -> bool:
    """Audit JUnit output, including xfails, by exact identity and reason."""
    if not report.is_file():
        print("[QUALITY][FAIL] Pytest did not produce a JUnit report")
        return False
    cases = list(ET.parse(report).getroot().iter("testcase"))
    failures = sum(case.find("failure") is not None for case in cases)
    errors = sum(case.find("error") is not None for case in cases)
    skipped = sum(case.find("skipped") is not None for case in cases)
    passed = len(cases) - failures - errors - skipped
    print(
        f"[QUALITY] Pytest totals: {len(cases)} tests; {passed} PASS; "
        f"{failures} failures; {errors} errors; {skipped} SKIP (not PASS)"
    )
    ok = True
    for case in cases:
        skip = case.find("skipped")
        if skip is None:
            continue
        identity = f"{case.attrib.get('classname', '')}.{case.attrib.get('name', '')}"
        reason = skip.attrib.get("message", "")
        allowed_reason = ALLOWED_SKIPS.get(identity)
        if allowed_reason is None or not reason.startswith(allowed_reason):
            print(f"[QUALITY][FAIL] Unapproved SKIP: {identity}: {reason}")
            ok = False
        else:
            print(f"[QUALITY][SKIP; NOT PASS] {identity}: {reason}")
    return ok


def main() -> int:
    if any(importlib.util.find_spec(name) is None for name in ("ruff", "mypy", "pytest")):
        print(
            "[QUALITY][FAIL] Install dev dependencies: "
            "python -m pip install -r requirements-dev.txt",
            flush=True,
        )
        return 1
    ok = check_discovered_lint()
    ok &= _run_step("claim-ledger", [sys.executable, "scripts/lint_ledger.py"])
    ok &= _run_step(
        "mypy",
        [
            sys.executable,
            "-m",
            "mypy",
            "--follow-imports=silent",
            "--ignore-missing-imports",
            "--no-strict-optional",
            "--disable-error-code=import-untyped",
            "run_discovery.py",
            "discovery/batch_runner.py",
            "scripts/smoke_api.py",
        ],
    )
    with tempfile.TemporaryDirectory(prefix="jwst-quality-") as folder:
        report = Path(folder) / "pytest.xml"
        ok &= _run_step("pytest", [sys.executable, "-m", "pytest", "-q", f"--junitxml={report}"])
        ok &= check_pytest_skips(report)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
