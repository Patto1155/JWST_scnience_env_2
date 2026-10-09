# Science OS Documentation

See **[NORTH_STAR.md](NORTH_STAR.md)** for the vision and goals of Science OS.

For scientific claims, start with [the current verified status](TAKEOVER_STATUS.md) and [consolidated research report](FINAL_RESEARCH_REPORT.md). The incoming PR29 status/report are preserved as historical snapshots.
It supersedes stronger historical claims where the original images, independent
controls or calibration have not been reproduced. [The current research protocol](RESEARCH_PROTOCOL.md)
defines evidence labels, role ownership and the frozen environment.

## Architecture

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for detailed system architecture.
See **[JWST_DISCOVERY_ROADMAP.md](JWST_DISCOVERY_ROADMAP.md)** for the current JWST discovery milestones.
See **[JWST_DISCOVERY_INDEX.md](JWST_DISCOVERY_INDEX.md)** for the consolidated JWST discovery doc entrypoint.

- **Language**: Python 3.10+
- **Services**:
  - `core_api`: FastAPI service exposing tools, datasets, experiments, and runs via HTTP
  - `runner`: Experiment executor with two modes:
    - **Legacy Mode**: Predefined experiment steps (`ExperimentExecutor`)
    - **Agent Mode**: Autonomous scientific agent loop (`ScientificResearchAgent`)
- **Storage**:
  - SQLite (or Postgres) for:
    - tools (registry)
    - datasets (catalog)
    - experiments (definitions)
    - runs (executions with trajectory/history for agent runs)
  - Filesystem for artifacts (plots, JSON results, raw outputs)

## Core Principles

### Current Implementation
- Agents NEVER touch the filesystem directly
- Agents only interact through tools that call core_api endpoints
- Everything callable by an agent must be registered as a "Tool" in the registry
- Experiments are JSON/Pydantic specs describing a pipeline of tool invocations

### Autonomous Agent Mode (Implemented)
- **ScientificResearchAgent**: Autonomous agent loop (think → toolcall → observe → repeat)
- **Tools as data compressors**: Tools return summaries (stats, samples, plots), not raw datasets
- **Token-efficient**: Agent works with small JSON summaries, not full datasets
- **Reusability**: Same tools work across different scientific questions
- **Trajectory tracking**: Agent message history stored for debugging and analysis

### Supervisor Campaigns (Implemented)
- Cheap worker loops can be dispatched with `python discovery/supervisor_campaign.py`
- Worker runs can use low-cost models such as `qwen/qwen3-next-80b-a3b-thinking`
- Worker loops constrain their tool surface with `constraints.allowed_tools`
- Sessions persist GUI-ready telemetry in `event_stream.jsonl` and `live_state.json`
- Sessions also persist `session_manifest.json`, `operator_inbox.jsonl`, and `supervisor_outbox.jsonl`
- Top worker outputs can be escalated to a judge model for final ranking

See `docs/AGENT_PROMPTS.md` for agent behavior guidelines.

## Project Structure

```
science-os/
  core_api/          # FastAPI service
  runner/            # Experiment executor and ScientificResearchAgent
  tools/             # Registered tools (JWST, core, etc.)
  docs/              # Documentation
  infra/             # Infrastructure configs
```

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment (optional):
```bash
cp infra/config.example.env .env
# Edit .env with your settings if needed
```

3. Initialize database and register tools:
```bash
python run_startup.py
```

Or just start the API - it will auto-initialize on first run:
```bash
python run_api.py
```

Alternative:
```bash
uvicorn core_api.app:app --reload
```

4. The API will be available at:
- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- OpenAPI schema: http://localhost:8000/openapi.json

5. Try the example:
```bash
python examples/quickstart.py
```

6. Run a supervisor-driven campaign:
```bash
python discovery/build_universe_table.py
python discovery/supervisor_campaign.py --max-candidates 8
```

`build_universe_table.py` refreshes the candidate frontier, including:

- `research_output/highz_shortlist.json`
- `research_output/highz_validation_top10.json`
- `research_output/proposal_channel_summary.json`

The campaign then creates a session directory under `research_output/supervisor_sessions/<session_id>/`.
The most useful files are `event_stream.jsonl`, `live_state.json`, `session_manifest.json`, `worker_results.json`, and `judge_report.json`.

7. Open the lightweight supervisor GUI:
```bash
python discovery/supervisor_dashboard.py --open-browser
```

The browser dashboard is the primary GUI for supervisor campaigns. It shows:

- live worker state and event timeline
- proposal portfolio bucket and primary channel per worker
- structured worker detail cards
- proposal frontier summary from `proposal_channel_summary.json`

See [SUPERVISOR_GUI_GUIDE.md](../SUPERVISOR_GUI_GUIDE.md) for the full workflow.

## API Endpoints

- `GET /tools` - List all registered tools
- `GET /tools/{id}` - Get a specific tool
- `GET /datasets` - List all datasets
- `GET /datasets/{id}` - Get a specific dataset
- `GET /experiments` - List all experiment definitions
- `GET /experiments/{id}` - Get a specific experiment
- `GET /runs` - List all runs
- `GET /runs/{id}` - Get a specific run and its results
- `POST /runs` - Start a new experiment run

## Creating an Experiment Run

### Legacy Mode (Predefined Steps)

Example ExperimentSpec with predefined steps:

```json
{
  "objective": "Compute image statistics on JWST data",
  "datasets": ["jwst_ngc1234_f200w"],
  "steps": [
    {
      "tool_name": "image_statistics",
      "parameters": {
        "image_data": null
      }
    }
  ]
}
```

### Agent Mode (Autonomous)

Example ExperimentSpec for autonomous agent:

```json
{
  "objective": "Analyze the brightness distribution and identify interesting features in JWST image data",
  "datasets": ["jwst_ngc1234_f200w"],
  "steps": null,
  "constraints": {
    "max_steps": 20,
    "max_cost": 5.0
  }
}
```

The agent will autonomously decide which tools to call and when to finish.

To restrict the tool surface for a narrow worker loop, add:

```json
{
  "constraints": {
    "allowed_tools": ["candidate_evidence_bundle", "extract_photometry", "compute_color_index"]
  }
}
```

Post to `/runs` with:
```json
{
  "spec": { ... experiment spec ... }
}
```

## Development

See `docs/AGENT_RULES.md` for agent interaction rules and guidelines.

The [verified original-image photometry experiment](ORIGINAL_IMAGE_PHOTOMETRY.md)
documents the direct hash-verified image-manifest rerun and replayable compact
measurement artifacts. Exploratory proposals and physical dropout-screen survivors
are saved separately; neither output establishes astrophysical identity.



## Verified original-image workflow

See [ORIGINAL_IMAGE_ASTROMETRY.md](ORIGINAL_IMAGE_ASTROMETRY.md) for bounded
MAST acquisition, checksum/SCI/ERR/WHT readiness checks, optional catalog
registration, external released-source centroid validation and repeat-pair
reproduction. These are trusted coding/analysis CLIs, not new arbitrary-code
capabilities exposed to research agents.
* [Bounded follow-up data and actual deep-reference comparison](FOLLOWUP_DATA.md).

* [Nine native MoM exposures and rotating-star benchmarks](MOM_NATIVE_BATCH.md).

The next merged-baseline experiment is documented in
[ORIGINAL_REPEAT_TEST.md](ORIGINAL_REPEAT_TEST.md): additional original dithers,
matched-quadrant SMACS acquisition, covered same-filter persistence tests and
explicit additional conditional proposals.


The [current verified takeover status](TAKEOVER_STATUS.md) and
[full research report](FINAL_RESEARCH_REPORT.md) index the executed experiments,
merged PRs, reproducible inputs, uncertainty limits and next work.

[Independent SMACS repeat vetting](SMACS_INDEPENDENT_REPEAT.md) adds a distinct
native integration, hash/contributor guards, frozen-input reproduction and
held-out relative astrometry. It reports fixed-aperture persistence separately
from segmented-source association. These remain trusted operator CLIs.
