# Calibrated-answers session — 14 October 2026

Awaiting cross-lineage audit. Baseline master85d8f17 / merged PR84. No claim is
promoted; every arm's gate remains unchanged. All six agents used isolated
worktrees and the lead integrated evidence and adjudicated state.

## Scientific verdicts

| Arm | Verdict | Evidence |
|---|---|---|
| Raw known-answer | Blocked: contributors, extraction operator and empirical prior unresolved; no raw reduction | CALIBRATED_KNOWN_ANSWER.md |
| Released-1D population |15GS training plus14/15GN confirmation; frozen descriptive northern prediction fails; published-error multiplier is not identifiable | CALIBRATED_KNOWN_ANSWER.md |
| MoM noise | Fresh signed ionic interval[0.10155,13.48043] includes ambient; frozen practical noise checks pass but prior/source/raw calibration remain conditional | MOM_CALIBRATED_CHALLENGE.md |
| SMACS | Original null failures reproduce;1704 planned injections unrun without measuredPSF; epoch metadata timeout | SMACS1043_COMPLETION.md |
| Pole YSO | Metadata eligibility not demonstrated; no science pilot or variability null | YSO_POLE_FEASIBILITY.md |
| Methods | Six documented inference failure modes and their limiting controls | METHODS_NOTE.md |

The revised known-answer threshold is a dated user-authorized amendment, not
a blind retrospective test. GOODS-N was opened only by B's sole confirmation
after committing the southern result and numerical prediction; southern
fallback spectra remain unopened. Lead review used northern aggregate receipts
only. Opposite B/C shift conventions and transported geometric-prior assumptions
do not provide interchangeable empirical calibration.

## Budgets and chronology

Final counters and limitations are in DATA_BUDGET.md. Science-body allowances
were not reset after failures or deletion. MoM code failures and repeated
acquisitions count against the fresh1.5GiB counter, not as independent repeats.

research_output/calibrated_20261014/lead_validation.json verifies original
freeze-before-access ordering and restoration of14 original commit refs from
freeze_history.bundle. The bundle excludes the existing master prerequisites
and preserves original author/committer times even when API publication uses
one new commit. Restore in a clone with master85d8f17 available:

```bash
git bundle verify research_output/calibrated_20261014/freeze_history.bundle
git fetch research_output/calibrated_20261014/freeze_history.bundle 'refs/session-freeze/*:refs/session-freeze/*'
```

freeze_history.json gives exact refs/hashes. Code fixes after data access retain
the predeclared operators/thresholds and failed receipts; no changed design is
represented as blind confirmation. The late D patch grid is a prospective,
unexecuted injection amendment informed by the known historical scene.

## Validation and next audit

Integrated quality gate exit0:841PASS,3explicit allow-listedSKIP,0FAIL, no new
lint diagnostics, ledger lint and mypy pass. Existing promotion negative-control
tests still reject missing controls. SKIP is not PASS. The exact log and lead
receipt are in research_output/calibrated_20261014/. Compact replays establish
computation only; a different model family must audit before merge.

The auditor should attack: (1) MoM signed covariance transport, wavelength-prior
mixture and approximate Fieller coverage; (2) JADES estimator/sign/width priors,
selection and shared-photon covariance behind the failed northern prediction;
(3) SMACS association/null gates and whether any proposed pointPSF or repeat
would actually address them. Check unknown-versus-zero YSO eligibility as well.

Not run/verified: raw known-answer recovery; empirical centring priors/source
coverage; exact non-Gaussian ratio coverage; SMACS measuredPSF/injections/new
epoch photometry; YSO science/ice-depth controls; G235H measurement; independent
astrophysical repeat; different-family audit. These arms stop this bounded
session with unresolved prerequisites rather than astrophysical rejection.
