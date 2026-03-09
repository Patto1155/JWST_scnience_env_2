# Agent Prompts and Behavior Guidelines

## System Prompt

`ScientificResearchAgent` uses a system prompt that:

- frames the agent as an autonomous scientist
- lists available tools and datasets
- requires structured JSON actions
- emphasizes reflection between observations
- expects evidence-backed conclusions rather than vague summaries

The current action types are:

```json
{"action": "tool_call", "tool_name": "tool_name", "parameters": {...}}
```

```json
{"action": "reflect", "thoughts": "What did this observation change?"}
```

```json
{"action": "finish", "findings": "Evidence-backed conclusions"}
```

## Parsing Rules

The parser is intentionally defensive:

- if a response contains multiple JSON actions, it prefers `tool_call` over `reflect` over `finish`
- if a finish payload still contains embedded action JSON or obvious future-tense execution plans, the finish is blocked
- natural-language fallbacks still exist, but structured JSON is strongly preferred

This matters for small or cheap models, which often mix planning prose with one or more executable JSON snippets in the same response.

## Behavior Guidelines

### Tool Selection

- start broad, then narrow
- avoid repeating identical calls without a reason
- use tool outputs to choose the next experiment
- for supervisor worker loops, keep the tool surface narrow with `constraints.allowed_tools`

### Narrow Worker Pattern

The default supervisor worker tool set is:

- `candidate_evidence_bundle`
- `extract_photometry`
- `compute_color_index`

Cheap worker models should not be given the entire registry unless there is a specific reason.

### Finish Conditions

The agent should finish only when:

- it has real tool observations
- it has reflected enough to interpret those observations
- it is not merely restating a plan for future execution

### Uncertainty Reporting

When findings remain uncertain:

- say what was observed
- say what is still ambiguous
- distinguish between evidence and inference
- suggest the next check explicitly

## Constraints and Guardrails

Important constraints include:

- `max_steps`
- `max_cost`
- `min_successful_tool_calls`
- `min_reflections`
- `allowed_tools`

When constraints are reached, the agent should finish gracefully with the best available evidence, or fail clearly if minimum activity requirements were not met.
