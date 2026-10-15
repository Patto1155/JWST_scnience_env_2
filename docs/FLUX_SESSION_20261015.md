# Flux-deficit session, 15 October 2026

Awaiting cross-lineage audit. No scientific grade changes.

The handover's numerical pattern reproduces on 29 committed comparisons, but
its causal interpretations are hypotheses. The field difference is associated
with catalogue S/N; neither a pure S/N cause nor a field cause is established.
The fitter is signed, correcting the incoming positivity premise.

PR85 was open, unmerged, at head `685d457` when this work began. The session
branches from `research/calibrated-answers-20261014`, with a stacked PR against
that branch. Historical failed predictions and old evidence remain unchanged.
The user authorized the attached workflow and its new B/C/D/E allowances;
older sealed-GOODS-N statements do not prohibit the requested committed-data
reanalysis. No new northern data were acquired.

## Evidence map

- [Diagnosis](FLUX_DEFICIT_DIAGNOSIS.md): regression, object bootstrap,
  signed injection control, frozen primary and pre-fit secondary amendment.
- [Holdout](FLUX_HOLDOUT.md): 15 per-row predictions frozen; zero successful
  spectrum opens because the first proxy CONNECT failed with403.
- [Independent selection](INDEPENDENT_LINE_SELECTION.md): frozen different-line
  sampling and synthetic covariance sensitivity; no fresh catalogue or spectra.
- [Other arms](FLUX_OTHER_ARMS.md): unvalidated MoM extrapolation, unresolved
  G235H archive availability, and the bounded SMACS PSF prerequisite stop.
- [Methods note](METHODS_NOTE.md): noisy selection, partial photon sharing,
  post-hoc criteria and injection controls for released JADES products.

## Budget and disposition

| Arm | Authorized cap | New response-body bytes | Disposition |
| --- | ---: | ---: | --- |
| A | 0 | 0 | Committed JSON and real-background synthetic line injections |
| B | 322,122,547 | 0 | First HEAD denied; 15 southern outcomes unopened |
| C | 1,073,741,824 | 0 | Catalogue HEAD denied; no 30-row empirical test |
| D | 1,073,741,824 if triggered | 0 | Trigger unresolved without B/C; deferred |
| E science | 1,073,741,824 if public | 0 | No science acquisition or empirical PSF |
| E metadata | 10,000,000 working bound | 0 | MAST CONNECT denied |

Counts describe application bodies, excluding TLS/proxy overhead and software
dependency/git transport. No raw science bodies were created. Free disk stayed
above5GB (about29GB at integration). Existing historical download charges are
preserved, not reset or counted as fresh transfers.

## Review and limits

A same-lineage read-only code challenge identified unimplemented future B
paired-law and intercept bootstrap criteria. These were completed in `d508fb8`
after the denied preflight, before any spectrum access; no frozen scientific
criterion changed. They remain unexecuted on real holdout data. Two safeguard
tests verify committed-prediction enforcement and no retry/GET after denial.
The challenge also identified arithmetic injection means versus exponentiated
log predictions as different estimands; the report retains the frozen primary
and labels the comparison heuristic. This review is not independent lineage or
independent astrophysical corroboration.

The H1-dependent raw-known-answer closure and H2-dependent fitter repair are
both deferred because neither cause is established. An unbiased comparison
target would use selection on independently validated noise (with cross-line
covariance checked), a complete externally selected cohort retaining signed
nondetections, or independently generated truth under a validated instrument
and extraction model. Current released-data agreement cannot replace raw
end-to-end calibration.

Not run / not verified: empirical B/C causal discrimination; real holdout law
preference and intercept; D continuum/product/pathloss/Jacobian tests; exhaustive
current G235H inventory or acquisition; SMACS empirical PSF/injections;
raw-known-answer chain or fitter repair; calibrated MoM extrapolation;
independent astrophysical repeat; independent model-family audit. The complete
C metered acquisition/real-residual runner remains unimplemented. All scientific
freeze/access clocks are locally asserted, not independently timestamped.

## Integrated validation and history

The integrated quality gate exits0: **850 PASS, 3 exact allow-listed SKIP,
0 failures/errors**, zero new lint diagnostics, mypy and ledger lint pass.
The skips are the two absent native visual-runner archives and absent pinned
Cue weights; they provide no pixel validation. The complete gate log and
`lead_validation.json` are in `research_output/flux_deficit_20261015/`.
The final scientific code matches the gated revision; subsequent edits are
provenance/report artifacts only.

`freeze_history.bundle` preserves all original worker branches and their
prediction/secondary-amendment commits, alongside integrated history. Its
prerequisite is PR85 head `685d457`. The bundle verifies and restores in a
fresh bare repository seeded only with that prerequisite and ancestors.
Lead checks verify unchanged frozen artifact bytes, strict commit-before-access
ordering for A primary/secondary and B/C predictions, and unchanged operator
hash. E has its own checked receipt. The regression replay differs from the
original system-environment freeze by at most2.7e-15 after research-lock
alignment. The injection process overlapped dependency alignment, so exact
loaded injection dependency versions are not attested. The failed edge-window
results therefore do not certify numerical stability or exact-lock replay.
