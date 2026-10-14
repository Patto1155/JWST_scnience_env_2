# Data budget ledger — session 2026-10-14

Caps are frozen in `docs/frozen/20261014_SESSION_BUDGET_AMENDMENT.md`.
Bytes here count science/reference response bodies; metadata is separately
identified in each receipt. Zero means no new response-body access by the
amendment author, not a certification that historical transport was zero.
Agents append dated receipt-backed entries via the lead; preserve earlier rows.

| Arm | Cap (bytes) | Bytes used / conservative charge | Receipt path |
|---|---:|---:|---|
| Raw known-answer | 1,073,741,824 | 0 new at amendment freeze | Pending Agent B acquisition receipt |
| Population known-answer | 300,000,000 | 0 new at amendment freeze | Pending Agent B acquisition receipt |
| MoM noise | 1,610,612,736 | 0 on fresh counter at amendment freeze | Pending Agent C acquisition receipt |
| SMACS | 6,442,450,944 | 5,826,074,168 cumulative conservative reservations | `research_output/session_20261014/e2_acquisition.json` |
| YSO | Metadata only, then 500,000,000 if gate passes | 0 new at amendment freeze | Pending Agent E metadata/acquisition receipt |

SMACS historical actual cumulative reads: 5,124,551,480 bytes; conservative
remaining allowance: 616,376,776 bytes. Historical charges remain charged after
raw deletion. All other arms begin fresh counters as explicitly authorized.

## Append-only session receipts

No new acquisition was performed by Agent A. Each appended row must identify
arm, time, freeze commit, body bytes, cumulative charged bytes, receipt path,
reservation/failed-transfer treatment and any unmetered metadata limitation.

Agent C, 2026-10-14: first access2026-10-14T04:14:42.622019+00:00 follows
freeze43a2b84 and allowanceefe2f43. Fresh MoM counter recorded1,446,220,352
accepted body bytes; cumulative conservative charge**1,446,243,400 /
1,610,612,736**. Four unfinished and four error-finished header requests retain23,048bytes
of conservative charges; successful run itself480,060,288bytes with complete metering.
Three complete acquisitions include two implementation failures; none counts
as independent astrophysical repeat. No extra CLI metadata transfer. Literature
web-search provider transport is unmetered. Receipt
`research_output/calibrated_20261014/c_acquisition_summary.json` links all attempts.
Raw full-CAL memory bodies and RATE caches were closed after reduction; no newly
acquired FITS bodies or reference files are committed.

Final lead-integrated entries (2026-10-14; source freeze/access chronology in each receipt):

| Arm | Cap bytes | Final charge | Receipt |
|---|---:|---:|---|
| Raw known-answer | 1,073,741,824 | 0 science; 1,110 direct metadata | research_output/calibrated_20261014/b_aggregate_verdict.json |
| Population known-answer | 300,000,000 | 113,178,240 science | research_output/calibrated_20261014/b_aggregate_verdict.json |
| MoM noise | 1,610,612,736 | 1,446,243,400 conservative; 1,446,220,352 received | research_output/calibrated_20261014/c_acquisition_summary.json |
| SMACS | 6,442,450,944 | 5,826,074,168 cumulative; 0 new science/metadata | research_output/calibrated_20261014/d_budget_fragment.json |
| YSO | 30,000,000 metadata; conditional 500,000,000 science | 7,261,777 metadata; 0 science | research_output/calibrated_20261014/e_budget_manifest.json |
| Amendments / methods | No acquisition | 0 | docs/frozen/20261014_SESSION_BUDGET_AMENDMENT.md; docs/METHODS_NOTE.md |

No charge is reset by raw deletion. All scientific counters remain below caps.
Web/source-provider transport is unmetered and excluded from certified direct-body
subtotals; software-package transfers are separate. SMACS has 616,376,776 bytes
remaining; MoM has 164,369,336 bytes remaining. No further acquisition is planned.
