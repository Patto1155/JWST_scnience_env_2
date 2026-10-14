# Science OS Agent Rules

This document defines rules for how LLM agents interact with this system.

Current scientific state lives only in `docs/STATUS.md` and `docs/CLAIM_LEDGER.md`.
The lead researcher owns those files; subagents submit evidence and proposed grades
without editing them. Code-changing subagents use isolated worktrees. Every task
names inputs, output path, acceptance command, exclusions and "list what you did
not run". Freeze hypothesis, data selection, statistic, null, threshold and
multiplicity correction in a commit before downloading or opening new outcome
data. An edited-after-access design is void; GOODS-N remains sealed.

Null-control, injection-recovery and independent-repeat or holdout artifacts are
required before Candidate/Validated promotion. Shared-model reviewer agreement
is not corroboration: independence comes from different epochs, instruments,
reductions or held-out fields, or a different provider when an OpenRouter key is
available. Runtime tool-call/reflection minima default to zero and are opt-in;
scientific stopping depends on evidence and declared budgets, not activity.

**See [NORTH_STAR.md](NORTH_STAR.md) for the vision of autonomous research agents.**

---

## 1. Global Principles

1. Agents **never** touch the filesystem directly.
2. Agents **never** create or modify Python modules, tools, or infrastructure.
3. Agents **only** interact with the system via tools that call the `core_api`.
4. If something is not in the Tool Registry, Dataset Catalog, or Experiment / Run catalog, then it does not exist from the agent's point of view.
5. Persistent capabilities must be added as tools by humans or trusted coding agents, then registered.
6. **Tools are data compressors**: tools return summaries (statistics, samples, plots), not raw datasets.

---

## 2. Coding Agent Rules

Role: build and maintain the Science OS codebase.

The filesystem/tool restrictions in sections 1 and 3 describe sandboxed runtime
research workers. Trusted coding agents conducting an explicitly authorized
repository takeover may implement scientific modules, tests, acquisition tools
and reports directly. They must preserve the runtime sandbox boundary and label
actual data, model products, synthetic controls and unexecuted experiments.

Trusted coding agents may run the hash-verified imaging reproduction described in
`ORIGINAL_IMAGE_PHOTOMETRY.md`. Its direct manifest CLI is an operator/coding-agent
workflow, not an additional filesystem capability for runtime research agents.

**Allowed:**
- Create and modify source code under `core_api/`, `runner/`, `tools/`, and `docs/`
- Define and evolve DB schemas, Pydantic models, FastAPI routers, and runner behavior

**Must:**
- Keep `docs/README.md` and `docs/AGENT_RULES.md` up to date with architectural changes
- Maintain clear boundaries:
  - `core_api` is the HTTP facade and catalog
  - `runner` executes experiments, including the autonomous `ScientificResearchAgent`
  - `tools/*` are pure Python functions registered into the Tool Registry
- Use type hints and small, focused modules
- Add tests when introducing new core behaviors or schemas

**Must NOT:**
- Hardcode random JWST specifics into the core API
- Expose raw file paths to agents
- Allow agents to submit arbitrary Python code for execution

---

## 3. Research Agent Rules

**Current State:** agents can still design predefined `ExperimentSpec` JSON objects.

**North Star Goal:** agents operate autonomously in a loop (`think -> toolcall -> observe -> repeat`) to answer natural language questions.

### Current Behavior (Experiment Planner)

Role: design and run scientific experiments using existing tools and datasets.

**Must:**
- Discover capabilities via tools such as `list_tools`, `list_datasets`, `list_experiments`, and `list_runs`
- Express experiments as `ExperimentSpec` JSON objects
- Use only registered tools and listed datasets
- Aim for clearly interpretable numerical outputs

**Must NOT:**
- Invent tool names or datasets
- Request arbitrary code execution
- Attempt to create or modify tools

### Autonomous Research Agent (Implemented)

**Workflow:** `think -> decide -> toolcall -> observe -> repeat`

The `ScientificResearchAgent` class in `runner/scientific_agent.py` implements the autonomous loop:

1. **Think**: the LLM analyzes the objective and current state
2. **Decide**: it chooses the next action (`tool_call`, `reflect`, or `finish`)
3. **Toolcall**: the agent invokes tools via the sandbox
4. **Observe**: tool results are summarized and added to history
5. **Repeat**: continue until a finish decision or `max_steps`

**Key principles:**
- Prefer sampling over full datasets
- Work with summaries, not raw data
- Generate plots or evidence artifacts when useful
- Report uncertainty and limitations
- Stop when the frozen question is answered, a prerequisite fails or limits are reached

**Usage:** create a run with `spec.steps = None` or an empty list to enable agent mode.

### Supervisor Campaigns (Implemented)

Supervisor campaigns orchestrate many narrow worker runs and optionally escalate top worker outputs to a judge model.

This layer should:
- Dispatch worker runs through the existing `/runs` API
- Keep worker objectives narrow and structured
- Restrict cheap workers with `constraints.allowed_tools` when they only need a small tool surface
- Persist session telemetry as `event_stream.jsonl` and `live_state.json`
- Persist `session_manifest.json`, `operator_inbox.jsonl`, and `supervisor_outbox.jsonl` as the stable local GUI/control boundary
- Track per-worker tool usage for resource accounting; it is not evidence quality
- Treat worker `promote` and judge `escalate` as queueing statistical-gate review only
- Persist `statistical_gate_queue.json`; never let runtime workers or judges change scientific grades
- Avoid giving worker agents direct filesystem authority beyond registered tools

If something is missing:
- Clearly describe the missing capability in natural language for a human or coding agent

---

## 4. Repair / Execution Agent Rules

Role: make failing experiments succeed with minimal changes.

**Must:**
- Read `RunResult`, logs, and errors
- Identify root cause briefly
- Propose a corrected `ExperimentSpec` with minimal edits
- Respect available tool schemas and dataset metadata

**Must NOT:**
- Redefine the scientific objective just to make the run pass
- Introduce new tools or dependencies
- Hide or downplay actual failures

If the experiment is impossible:
- Explicitly state why
- Suggest what is required to make it possible

---

## 5. Human Operator Rules

- Approve or reject new tools before they are registered
- Periodically review the tool registry for redundancy
- Periodically review experiment and run catalogs for patterns of failure or drift
