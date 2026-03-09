# Continuation Plan (Strict Discovery Ops)

Purpose: fastest safe handoff checklist for ongoing JWST discovery work.

If blocked, consult `memory_bank/HYPOTHESIS_BANK.md` for the next falsifiable check and `memory_bank/FAILURE_SIGNATURES.md` for symptom-driven triage.

## First 10 Minutes
1. Start API: `python run_api.py`
2. Smoke-check endpoints: `python scripts/smoke_api.py`
3. Confirm catalog/tool state:
- `curl -s http://localhost:8000/tools/`
- `curl -s "http://localhost:8000/datasets/?limit=20&strict_ready=true"`
- `curl -s http://localhost:8000/runs/?limit=5`
4. Validate before queueing strict runs:
- `POST /runs/validate` with full run payload

## Strict Mode Reality
- Strict no-dummy remains default in discovery workflows.
- Missing/invalid `metadata.file_path` is a hard integrity failure.
- Run queue path and execution path both enforce strict checks.
- Startup integrity audit quarantines invalid datasets and logs actionable details.

## API Behavior You Can Rely On
- `POST /runs/validate`: structured preflight issues + hints (`valid`, `issues`, legacy issue lists).
- `POST /runs`: uses same strict schema and rejects invalid strict payloads with HTTP 422.
- `GET /datasets?strict_ready=true`: returns only strict-integrity-ready datasets
  (valid `metadata.file_path`, non-quarantined).
- `GET /runs` and `GET /runs/{id}` now include:
- `status_reason`
- `status_hints`
- queued runs may report `stuck_queued` with remediation guidance.

## Discovery CLI Behavior
- `python run_discovery.py --dry-run-validate`:
- resolves canonical datasets
- calls `/runs/validate`
- reports strict issues without queueing
- `python run_discovery.py --base-url http://127.0.0.1:8001 ...`:
- targets a non-default API instance when `:8000` is occupied by a stale process
- Standard strict runs preflight before submit and print strict remediation hints on failure.
- Polling tolerates transient network/API errors and surfaces queued-stuck hints.

## Quality Gates
- Dev deps: `python -m pip install -r requirements-dev.txt`
- Full gate: `python scripts/quality_gate.py`
- Direct tests: `python -m pytest core_api/tests runner/tests -q`

## Current Risks / Follow-ups
1. Port collisions on `:8000` can block `run_api.py` startup (`WinError 10048`).
2. Existing catalog rows that remain quarantined require manual metadata repair before strict runs.
