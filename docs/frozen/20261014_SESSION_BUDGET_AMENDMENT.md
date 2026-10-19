# Session budget and access amendment — 2026-10-14

This prospective amendment records the user's pre-authorized caps. Commit it
before any new scientific acquisition or outcome inspection. Original designs,
scientific gates, targets, controls and multiplicity remain untouched. A design
for any new measurement must independently be frozen and committed first.

| Arm | Science/reference response-body cap | Counter |
|---|---:|---|
| Raw known-answer | 1,073,741,824 bytes (1.0 GiB) | Fresh session counter |
| Population known-answer, released 1D spectra | 300,000,000 bytes (300 MB) | Fresh session counter |
| MoM noise | 1,610,612,736 bytes (1.5 GiB) | Fresh counter, range reads preferred |
| SMACS | 6,442,450,944 bytes (6 GiB) | Existing E2 cumulative counter |
| YSO | Metadata only until feasibility passes; then 500,000,000 bytes (500 MB) | Fresh session counter |

SMACS carries 5,826,074,168 bytes in conservative existing reservations,
leaving 616,376,776 bytes. Do not reset that counter after raw deletion. Actual
historical cumulative reads are 5,124,551,480 bytes; the conservative charge
still governs the remaining allowance. Evidence is
`research_output/session_20261014/e2_acquisition.json` and
`docs/SMACS1043_E2_INDEPENDENT_TEST.md`. This amendment does not authorize
reacquiring its full dark reference within the remaining allowance.

Reserve verified response lengths before transfer; count all newly transferred
science/reference bytes, retries and failed bodies. Range reads count bytes
actually transferred with retained request/reservation receipts. Unknown lengths
must be bounded before body access. If the cap would be exceeded, stop that arm,
report required bytes, and continue the others. Local replays of existing derived
artifacts consume no new transfer allowance and are not independent observations.
Keep metadata and software-transfer accounting separate and disclose incomplete
historical metering; never present an unmetered contribution as zero.

Maintain at least 5,000,000,000 bytes of free disk throughout acquisition and
reduction, a stricter floor than the historical E2 storage plan. Prefer /tmp for
large temporary bodies to avoid synchronized-workspace duplication. Delete raw
bodies after reduction and compact verification; never commit them. Deletion
does not refund transferred bytes. Existing 30 MB metadata limits stay binding
where a frozen design imposes them.

GOODS-N remains sealed except for Agent B's single confirmation step. Agent B
must first commit its GOODS-S result and frozen numerical GOODS-N prediction.
If no applicable published GOODS-N line-flux catalogue exists, do not open its
outcome data; use the prospectively frozen GOODS-S held-out half instead. No
other agent opens GOODS-N. Metadata feasibility checks must be distinguished
from outcome data access.

Record freeze commit and first access time in each arm's receipts. Every agent
supplies an append-only budget entry to the lead, who assembles DATA_BUDGET.md;
this avoids worktree ledger conflicts. Budget authorization never waives
null, injection or independent-repeat promotion requirements.
