# Engineering Memory (Science OS)

Last updated: 2026-03-07
Audience: coding agents working on this repository.

## System Shape
- API: `core_api/` (runs, tools, datasets, experiments)
- Runner: `runner/` (`ScientificResearchAgent`, sandbox execution)
- Tooling: `tools/` (JWST + core stats)
- Deterministic catalog builder: `discovery/build_universe_table.py`
- Monitoring UI: `discovery_monitor.py`

## What Is Working Reliably
- Dataset registration from FITS files with metadata in DB.
- Strict dataset filtering and preflight validation for canonical `jwst_*` datasets.
- `run_discovery.py` can target isolated API instances via `--base-url` / `SCIENCE_OS_API_BASE_URL`.
- Discovery payloads now enforce minimum agent activity (`12` successful tool calls, `2` reflections).
- Deterministic build pipeline producing:
- `research_output/universe_table_summary.json`
- `research_output/highz_candidates.json`
- `research_output/anomaly_catalog.json`
- `research_output/RESEARCH_MEMORY.md`
- `research_output/RESEARCH_REPORT.md`

## What Is Not Reliable Yet
- Prompt instructions and registry are misaligned (prompt references unregistered tools).
- Loader fallback to dummy data can hide dataset lookup problems.
- Deep discovery runs now fail if minimum activity is not met, but tool quality/coverage still depends on prompt and registry alignment.

## Current Data Snapshot (from existing artifacts)
- Universe table entries: 150
- High-z candidates: 56
- Anomalies: 56
- High-z entries are concentrated in two targets: `SMACS-J0723.3-7327` and `GS-MEDIUM-HST`.

## Implementation Risks
1. Silent dummy fallback contaminates scientific conclusions.
2. NaN handling is inconsistent in tool code paths.
3. Candidate list lacks spatial deduplication.
4. Monitoring and summary logs can underreport real behavior.

## Priority Backlog For Code Agents
1. Data integrity
- Add strict mode in loader to error on missing real data.
- Add dataset alias resolver or remove alias defaults.
- Add provenance field in tool outputs (`source`: db/filesystem/dummy).

2. Agent execution reliability
- Enforce single action per model message in parser or prompt.
- Improve trajectory write pattern to avoid duplicate appends.

3. Tooling completeness
- Register missing core tools if needed by prompts (`compute_median`, `compute_std`, `correlation`, plotting helpers).
- Align prompt documents with actual `/tools` registry after each change.

4. Scientific quality controls
- Add NaN-safe processing in JWST tools.
- Add optional local background subtraction to photometry.
- Add candidate clustering/dedup in build pipeline.

5. Observability
- Fix `run_discovery.py` tool-call log counting string mismatch.
- Improve monitor extraction of findings and reflection counts.

## Validation Checklist After Any Change
- API starts cleanly: `python run_api.py`
- `/tools` and `/datasets` endpoints return expected entries.
- `python discovery/build_universe_table.py` completes.
- `research_output/` artifacts regenerate with valid JSON.
- At least one agent run performs real tool calls (verify trajectory contains `role=tool`).

## Files To Keep In Sync
- `memory_bank/TOOL_RECIPES.md`
- `memory_bank/CONTINUE_PLAN.md`
- `memory_bank/DISCOVERY_PROMPT.md`
- `memory_bank/HYPOTHESIS_BANK.md`
- `memory_bank/FAILURE_SIGNATURES.md`
- `docs/ARCHITECTURE.md` and `docs/AGENT_RULES.md` when behavior changes materially.
