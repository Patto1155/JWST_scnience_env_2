"""Run minimal lint/type/test quality gates."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHECK_TARGETS = [
    "core_api/routers/runs.py",
    "core_api/services/strict_validation.py",
    "core_api/services/run_service.py",
    "run_discovery.py",
    "discovery/batch_runner.py",
    "scripts/smoke_api.py",
]
SCIENCE_LINT_TARGETS = [
    "discovery/psf_noise.py",
    "runner/tests/test_psf_noise.py",
    "data_pipeline/original_images.py",
    "tools/jwst/astrometry.py",
    "discovery/external_astrometry.py",
    "tests/test_external_astrometry.py",
    "discovery/image_photometry_rerun.py",
    "tools/jwst/common_coverage.py",
    "tests/test_image_photometry_rerun.py",
    "tools/jwst/photometry.py",
    "tools/jwst/flux_calibration.py",
    "tools/jwst/dropout.py",
    "discovery/build_universe_table.py",
    "discovery/proposal_channels.py",
    "discovery/multi_epoch.py",
    "tests/test_multi_epoch_physical.py",
    "tools/jwst/spectroscopy.py",
    "tools/jwst/visualization.py",
    "tools/jwst/fits_loader.py",
    "core_api/startup.py",
    "discovery/external_psf_stress.py",
    "discovery/validation_audit.py",
    "discovery/validation_metrics.py",
    "data_pipeline/research_sources.py",
    "data_pipeline/reference_cohorts.py",
    "tests/test_spectrum_reference.py",
]


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _run_step(name: str, cmd: list[str]) -> bool:
    print(f"[QUALITY] {name}: {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"[QUALITY][FAIL] {name} (exit={result.returncode})", flush=True)
        return False
    print(f"[QUALITY][OK] {name}", flush=True)
    return True


def main() -> int:
    ok = True

    if not _module_available("ruff") or not _module_available("mypy"):
        print(
            "[QUALITY][FAIL] Missing dev dependencies. "
            "Install with: python -m pip install -r requirements-dev.txt",
            flush=True,
        )
        return 1

    ok &= _run_step(
        "ruff-check",
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--select",
            "E9,F",
            *CHECK_TARGETS,
            *SCIENCE_LINT_TARGETS,
        ],
    )
    ok &= _run_step(
        "ruff-format-check",
        [sys.executable, "-m", "ruff", "format", "--check", *CHECK_TARGETS],
    )
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
    ok &= _run_step(
        "pytest",
        [sys.executable, "-m", "pytest", "-q"],
    )

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
