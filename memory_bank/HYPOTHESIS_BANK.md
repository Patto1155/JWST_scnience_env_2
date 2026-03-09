# Hypothesis Bank (Agent Debug Loop)

Purpose: give coding agents concrete, falsifiable runtime hypotheses so they can debug by experiment instead of broad repo wandering.

## How To Use
1. Pick one hypothesis.
2. Run the exact command shown.
3. Compare the result to the expected signal.
4. If it fails, read the listed files before changing code.
5. Re-run the same command after the change.

Prefer cheap hypotheses first. Do not jump to long agent runs before the API, catalog, and preflight path are confirmed.

## Cheap Hypotheses

### H1: Isolated API health is good
- Claim: if this repo's API is started on `127.0.0.1:8001`, `python scripts/smoke_api.py --base-url http://127.0.0.1:8001` should pass.
- Why it matters: this is the fastest end-to-end check of routing, tool registry, dataset catalog, and strict preflight.
- Command:
```bash
python scripts/smoke_api.py --base-url http://127.0.0.1:8001
```
- Expected signal:
  - `/health` OK
  - `strict-ready datasets` greater than `0`
  - strict `/runs/validate` returns `valid: True`
- Read first if it fails:
  - `scripts/smoke_api.py`
  - `core_api/app.py`
  - `core_api/startup.py`
  - `core_api/routers/runs.py`

### H2: Strict dataset filtering is accurate
- Claim: `GET /datasets?strict_ready=true` should exclude rows with missing/invalid `metadata.file_path` or quarantine markers.
- Why it matters: strict discovery depends on this filter to avoid known-bad catalog rows.
- Command:
```bash
python -m pytest core_api/tests/test_api.py::test_datasets_endpoint_strict_ready_filter -q
```
- Expected signal:
  - test passes
- Read first if it fails:
  - `core_api/routers/catalog.py`
  - `core_api/services/catalog_service.py`
  - `core_api/services/strict_validation.py`

### H3: Strict preflight rejects bad datasets loudly
- Claim: unresolved datasets, missing `metadata.file_path`, and nonexistent file paths should all fail strict preflight with structured issues.
- Why it matters: silent acceptance here causes invalid runs later.
- Command:
```bash
python -m pytest core_api/tests/test_strict_run_validation.py -q
```
- Expected signal:
  - tests pass
  - failure codes include `STRICT_DATASET_NOT_FOUND`, `STRICT_DATASET_FILE_PATH_INVALID`, and `STRICT_DATASET_FILE_MISSING`
- Read first if it fails:
  - `core_api/services/strict_validation.py`
  - `core_api/routers/runs.py`
  - `core_api/tests/test_strict_run_validation.py`

### H4: Discovery CLI preflight uses the requested API base URL
- Claim: `python run_discovery.py --dry-run-validate --base-url http://127.0.0.1:8001` should hit the isolated API, not stale `:8000`.
- Why it matters: stale port collisions are common on this machine.
- Command:
```bash
python run_discovery.py --dry-run-validate --no-live --base-url http://127.0.0.1:8001
```
- Expected signal:
  - preflight summary prints `Valid payloads`
  - no stale-schema error for `:8000`
- Read first if it fails:
  - `run_discovery.py`
  - `runner/tests/test_discovery_cli.py`
  - `scripts/smoke_api.py`

## Medium-Cost Hypotheses

### H5: Queued runs surface actionable stuck status
- Claim: old queued runs should expose `status_reason=stuck_queued` and hints.
- Why it matters: agents need actionable observability when background execution stalls.
- Command:
```bash
python -m pytest core_api/tests/test_strict_run_validation.py::test_stuck_queued_run_exposes_reason_hints -q
```
- Expected signal:
  - test passes
  - hints mention worker/process health
- Read first if it fails:
  - `core_api/services/run_service.py`
  - `core_api/schemas/runs.py`

### H6: Agent-mode runs record real tool activity in trajectory
- Claim: a healthy agent run should append `role=tool` messages, not only user/agent text.
- Why it matters: "run succeeded" without tool calls is scientifically useless.
- Command:
```bash
python -m pytest runner/tests -q
```
- Expected signal:
  - agent tests pass
  - trajectory-related assertions stay green
- Read first if it fails:
  - `runner/scientific_agent.py`
  - `runner/executor.py`
  - `core_api/routers/runs.py`

## Expensive Hypotheses

### H7: Full strict discovery preflight is stable on current catalog
- Claim: current canonical SMACS + GS defaults should all validate in strict mode.
- Why it matters: this is the production precondition for autonomous discovery work.
- Command:
```bash
python run_discovery.py --runs 1 --dry-run-validate --no-live --base-url http://127.0.0.1:8001
```
- Expected signal:
  - strict preflight passes
  - default dataset count is 12
- Read first if it fails:
  - `run_discovery.py`
  - `memory_bank/TOOL_RECIPES.md`
  - `core_api/services/strict_validation.py`

### H8: Build pipeline still regenerates research artifacts
- Claim: deterministic discovery build should complete and write valid JSON artifacts.
- Why it matters: research outputs are still a major source of context for prompts and agent loops.
- Command:
```bash
python discovery/build_universe_table.py
```
- Expected signal:
  - command completes
  - updates `research_output/universe_table_summary.json`
  - updates `research_output/highz_candidates.json`
  - updates `research_output/anomaly_catalog.json`
- Read first if it fails:
  - `discovery/build_universe_table.py`
  - `memory_bank/ENGINEERING_MEMORY.md`

## Priority Order For New Agents
1. `H1`
2. `H4`
3. `H3`
4. `H2`
5. `H5`
6. Only then try broader runtime or scientific loops

## Notes
- Prefer `http://127.0.0.1:8001` when validating this repo locally; `:8000` may belong to a stale older API process.
- When a hypothesis fails, capture:
  - command
  - observed output
  - root-cause guess
  - exact files inspected
  - rerun result after fix
