# Failure Signatures (Agent Triage)

Purpose: map common symptoms to likely causes, the fastest confirmation step, and the first files worth reading.

## How To Use
- Match the symptom first.
- Run the confirmation command before editing code.
- Read only the listed files until you have a concrete root-cause hypothesis.

## API And Preflight

### Symptom: `405` or contract error for `POST /runs/validate`
- Likely cause: stale or older API process is bound to `:8000`.
- Confirm with:
```bash
python scripts/smoke_api.py --base-url http://127.0.0.1:8000
```
- Fast workaround:
```bash
python run_discovery.py --dry-run-validate --base-url http://127.0.0.1:8001
```
- Read first:
  - `scripts/smoke_api.py`
  - `run_discovery.py`
  - `run_api.py`

### Symptom: strict run returns HTTP `422`
- Likely cause: strict dataset integrity failure, unresolved dataset name, or quarantined row.
- Confirm with:
```bash
curl -s -X POST http://127.0.0.1:8001/runs/validate -H "Content-Type: application/json" -d "{\"spec\":{\"objective\":\"debug\",\"datasets\":[\"<dataset>\"],\"steps\":null,\"constraints\":{\"strict_real_data\":true}}}"
```
- Expected issue codes:
  - `STRICT_DATASETS_REQUIRED`
  - `STRICT_DATASET_NOT_FOUND`
  - `STRICT_DATASET_FILE_PATH_INVALID`
  - `STRICT_DATASET_FILE_MISSING`
  - `STRICT_DATASET_QUARANTINED`
- Read first:
  - `core_api/services/strict_validation.py`
  - `core_api/routers/runs.py`
  - `memory_bank/TOOL_RECIPES.md`

### Symptom: smoke check says no strict-ready datasets
- Likely cause: catalog rows are present but invalid, quarantined, or missing local files.
- Confirm with:
```bash
curl -s "http://127.0.0.1:8001/datasets/?limit=1000&strict_ready=true"
```
- Read first:
  - `core_api/services/catalog_service.py`
  - `core_api/services/strict_validation.py`
  - `core_api/startup.py`

## Discovery CLI

### Symptom: `run_discovery.py` fails before queueing
- Likely cause: preflight failure, stale API target, or default dataset resolution failure.
- Confirm with:
```bash
python run_discovery.py --dry-run-validate --no-live --base-url http://127.0.0.1:8001
```
- Read first:
  - `run_discovery.py`
  - `runner/tests/test_discovery_cli.py`
  - `memory_bank/CONTINUE_PLAN.md`

### Symptom: discovery CLI submits nothing in dry-run mode
- Likely cause: expected behavior; dry-run should call only `/runs/validate`.
- Confirm with:
```bash
python -m pytest runner/tests/test_discovery_cli.py -q
```
- Read first:
  - `runner/tests/test_discovery_cli.py`
  - `run_discovery.py`

## Run Execution

### Symptom: run stays `queued` too long
- Likely cause: background worker did not start, API restarted, or executor path failed early.
- Confirm with:
```bash
curl -s http://127.0.0.1:8001/runs/<run_id>
```
- Read for:
  - `status_reason`
  - `status_hints`
- Read first:
  - `core_api/services/run_service.py`
  - `core_api/routers/runs.py`
  - `run_api.py`

### Symptom: run fails with `STRICT_RUN_VALIDATION_FAILED`
- Likely cause: execution path revalidated a dataset and found strict integrity drift.
- Confirm with:
```bash
python -m pytest core_api/tests/test_strict_run_validation.py::test_execute_run_task_revalidates_strict_constraints -q
```
- Read first:
  - `core_api/routers/runs.py`
  - `core_api/services/strict_validation.py`

### Symptom: run "succeeds" but trajectory shows no tool calls
- Likely cause: agent prompt/parse loop ended too early or tool lookup was empty/misaligned.
- Confirm with:
```bash
python -m pytest runner/tests -q
```
- Read first:
  - `runner/scientific_agent.py`
  - `runner/executor.py`
  - `memory_bank/DISCOVERY_PROMPT.md`
  - `memory_bank/ENGINEERING_MEMORY.md`

### Symptom: run fails with `AGENT_MINIMUM_ACTIVITY_NOT_MET`
- Likely cause: model tried to `finish` before enough successful tool calls/reflections were recorded.
- Confirm with:
```bash
python -m pytest runner/tests/test_scientific_agent.py -q
```
- Read first:
  - `runner/scientific_agent.py`
  - `run_discovery.py`
  - `memory_bank/DISCOVERY_PROMPT.md`

## Data And Catalog

### Symptom: canonical dataset names do not resolve
- Likely cause: using legacy aliases instead of `/datasets` names, or target/filter metadata mismatch.
- Confirm with:
```bash
curl -s "http://127.0.0.1:8001/datasets/?limit=1000"
```
- Read first:
  - `run_discovery.py`
  - `core_api/routers/catalog.py`
  - `core_api/services/catalog_service.py`

### Symptom: dataset exists but strict mode still rejects it
- Likely cause: `metadata.file_path` is missing, path is stale, or row is quarantined.
- Confirm with:
```bash
python scripts/smoke_api.py --base-url http://127.0.0.1:8001
```
- Read first:
  - `core_api/services/strict_validation.py`
  - `core_api/startup.py`

## Research Prompt / Tooling Mismatch

### Symptom: agent prompt references tools that are not callable
- Likely cause: prompt drift relative to registered `/tools`.
- Confirm with:
```bash
curl -s http://127.0.0.1:8001/tools/
```
- Read first:
  - `memory_bank/DISCOVERY_PROMPT.md`
  - `memory_bank/TOOL_RECIPES.md`
  - `core_api/startup.py`

### Symptom: scientific findings look plausible but may be using dummy or invalid data
- Likely cause: non-strict execution or earlier loader fallback assumptions.
- Confirm with:
```bash
python run_discovery.py --dry-run-validate --base-url http://127.0.0.1:8001
```
- Read first:
  - `memory_bank/TOOL_RECIPES.md`
  - `core_api/services/strict_validation.py`
  - `runner/scientific_agent.py`

## Escalation Rule
- If a failure touches:
  - dataset integrity
  - run preflight
  - background execution
  - prompt/tool registry alignment
then update the relevant memory-bank doc after the fix so the next agent starts from the corrected operating model.
