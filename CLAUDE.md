# Verification-first JWST research

Purpose: test bounded astrophysical hypotheses on public, identity-verified data.
No new astrophysical result has survived verification in this repository as of
2026-10-14. Reversing unsupported claims is a correct scientific outcome.

## Start and health check

Read `docs/STATUS.md`, `docs/CLAIM_LEDGER.md`, `FINDINGS.md`, `HANDOVER.md`
(especially the ending 2026-10-09 correction), `docs/RESEARCH_PROTOCOL.md`,
`docs/AGENT_RULES.md` and `docs/RESEARCH5_REVIEW.md` before research.

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python scripts/quality_gate.py
```

In an activated environment the health command is `python scripts/quality_gate.py`.
**SKIP is not PASS.** Only the explicit data-absent skip allow-list is permitted;
a green software gate does not validate astrophysical measurements or missing data.

## Scientific state and promotion

Only `docs/STATUS.md` and `docs/CLAIM_LEDGER.md` track current scientific state.
Everything else is an evidence artifact, protocol, implementation guide or
historical record. The lead researcher owns both state files and every grade;
subagents never edit them. Grades are exactly **Validated**, **Candidate**,
**Unconfirmed lead**, **Null**, **Rejected**, **Superseded**. Describe conditional,
blocked or unresolved scope in the ledger, never invent additional grades.

A row at Candidate or Validated requires existing null-control, injection-recovery
and independent-repeat or holdout artifacts addressing that particular claim.
File existence alone does not validate a control. `scripts/lint_ledger.py` checks
the promotion contract; the lead judges whether the artifacts meet it. Worker
`promote` and judge `escalate` mean **queue for the statistical gate**, never a
scientific grade change. Tool-call and reflection minima default to zero and
are opt-in; do not manufacture activity or a positive conclusion.

## Freeze before look

Commit the hypothesis, data selection, statistic, null, threshold and multiplicity
correction before downloading or opening new outcome data. Record the commit and
access receipt. A design edited after data access is void; report exploratory
changes separately and freeze a genuinely independent future test. No agent
opens GOODS-N; it is a sealed holdout. Agents may write its future protocol.
Known historical outcomes may motivate designs but cannot be claimed as blind
confirmation. Distinguish metadata feasibility work from outcome inspection.

## Data and independence

Pilots are <=300 MB and selected original imaging <=1.5 GiB, with the more specific
allocations in `docs/RESEARCH5_CAMPAIGN.md` binding unless the user explicitly
authorizes a separately frozen budget amendment recorded in the session protocol. Account for bytes before
transfer, enforce download caps, preserve product identities, hashes and compact
receipts, reduce then delete raw downloads. Never commit raw downloads. Disk is
a fixed allowance. Missing coverage is missing data, never zero flux or an upper
limit. A line ratio is not an elemental abundance; assumptions and uncertainties
must remain explicit.

Same-model-lineage reviewer agreement is not corroboration. Seek different
epochs, instruments, reductions or held-out fields, or a different provider when
`OPENROUTER_API_KEY` is available. Do not print credentials. Shared photons remain
shared observations even when independent implementations agree.

## Delegation and delivery

Code-changing agents use isolated worktrees. Every subagent prompt names inputs,
output path, acceptance command, exclusions and **list what you did not run**.
Freeze Phase 2 designs before outcome access. Calibration known-answer results
gate spectroscopy. The lead verifies claims, integrates accepted changes and
creates one session PR. Report grade changes with evidence first, infrastructure
second, and not-run/not-verified work last. No row is promoted by an LLM opinion.
