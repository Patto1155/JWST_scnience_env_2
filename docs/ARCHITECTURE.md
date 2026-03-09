# Science OS Architecture

## Overview

Science OS is an autonomous research stack for LLM-powered scientific experimentation. The system supports:

1. **Legacy Mode**: predefined experiment steps
2. **Agent Mode**: the autonomous `ScientificResearchAgent`
3. **Supervisor Mode**: many narrow worker runs plus optional judge synthesis

## System Layers

### 1. API Layer (`core_api/`)

- FastAPI routers for runs, tools, experiments, and datasets
- Pydantic schemas for request/response validation
- Services such as `RunService` and strict dataset validation
- SQLAlchemy models for persistent state

### 2. Execution Layer (`runner/`)

- `ExperimentExecutor`: predefined-step execution
- `ScientificResearchAgent`: autonomous tool-using loop
- `Sandbox`: isolated tool execution

### 3. Discovery Layer (`discovery/`)

- `build_universe_table.py`: deterministic JWST candidate generation
- `supervisor_campaign.py`: cheap-worker / judge orchestration
- `telemetry.py`: local session state, event stream, manifest, inbox, and outbox persistence
- `supervisor_dashboard.py`: lightweight local GUI backed by session files

### 4. Tools Layer (`tools/`)

- Core statistics and visualization helpers
- JWST-specific tools for photometry, source detection, and evidence rendering
- Token-efficient outputs so agents work with summaries rather than raw arrays

## Data Flow

### Legacy Mode

`POST /runs` with predefined steps:

1. `RunService.create_run()`
2. background task `_execute_run_task()`
3. `ExperimentExecutor.run_experiment()`
4. `Sandbox.execute_tool()` for each step
5. `RunService.update_run_status()`

### Agent Mode

`POST /runs` without steps:

1. `RunService.create_run()`
2. background task `_execute_run_task()`
3. `ScientificResearchAgent.run()`
4. repeated LLM decide -> toolcall / reflect / finish loop
5. `RunService.update_run_status()` with result and trajectory

### Supervisor Mode

`python discovery/supervisor_campaign.py`:

1. load deterministic JWST candidate artifacts
2. build narrow worker payloads
3. restrict worker-visible tools with `constraints.allowed_tools`
4. validate and submit worker runs through `/runs`
5. poll worker runs, normalize structured reports, and rank results
6. optionally escalate top results to a judge model
7. persist `event_stream.jsonl`, `live_state.json`, `session_manifest.json`, `operator_inbox.jsonl`, `supervisor_outbox.jsonl`, and result artifacts

## Key Components

### ScientificResearchAgent

The autonomous agent maintains:
- message history
- step count and cost estimate
- minimum activity gates
- tool-result artifact tracking

The parser now prefers executable actions over premature finish payloads when a model mixes natural language with multiple JSON snippets.

### Narrow Worker Runs

Cheap supervisor workers should only see a small, high-signal tool surface. The current default worker tool set is:

- `candidate_evidence_bundle`
- `extract_photometry`
- `compute_color_index`

This is enforced through `spec.constraints.allowed_tools`.

### Session Telemetry

Each supervisor session persists:

- `event_stream.jsonl`: append-only timeline
- `live_state.json`: validated snapshot for the GUI
- `session_manifest.json`: stable session metadata
- `operator_inbox.jsonl`: future GUI-to-supervisor write boundary
- `supervisor_outbox.jsonl`: supervisor/judge messages for later conversational GUIs

### Worker Results

Normalized worker result records track:

- verdict, confidence, and interestingness
- schema errors or fallback reasons
- `tool_call_count`
- `reflection_count`
- artifact count

## Extension Points

### Adding New Tools

1. Implement the tool under `tools/`
2. Register it via startup or API
3. Add metadata so agents can discover and use it

### Changing Agent Behavior

- edit `runner/scientific_agent.py` for system prompt or parser changes
- adjust allowed tool sets in `discovery/supervisor_campaign.py`
- evolve schemas in `discovery/session_schemas.py`

### Future Supervisor Control

The current GUI hook is provision-only. The future control loop should consume `operator_inbox.jsonl` and append replies or decisions to `supervisor_outbox.jsonl` without breaking the existing file contract.
