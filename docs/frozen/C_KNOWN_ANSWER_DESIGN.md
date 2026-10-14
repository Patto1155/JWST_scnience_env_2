# C: prospective known-answer and calibration design

Frozen before any new spectrum/pixel/line-catalog outcome access. Existing audit
results and published literature were read; this is a known-answer verification,
not a blind astrophysical discovery. GOODS-N files/outcomes remain unopened.

## Hypotheses and inputs

1. Current CRDS selects an empirically pedigreed, applicable wavelength-zero-point
reference for MoM-z14's NRS_MSASPEC observation at 2025-04-14 (MJD60781.1628).
Read the current public context -> NIRSpec imap -> wavecorr rmap by literal AST
selection, then the selected ASDF header. Success requires non-DUMMY pedigree,
correct exposure applicability and explicit empirical provenance. An unchanged
DUMMY selection fails this upgrade hypothesis; never substitute a fixed-slit or
bright-object reference, alter historical receipts, or call a toy model empirical.

2. Recover the published [O III]5007 flux for GOODS-S JADES NIRSpec_ID10058975
(RA53.11243, DEC-27.77461, z9.433) from its original released G395M/F290LP v1.0
spectrum. Bunker et al., arXiv2306.02467v2 Table3, quotes
35.8 +/-0.8 in 1e-19 erg/s/cm2. This paper and MAST naming documentation are
literature/metadata read before freeze. Target chosen as the first entry of
published Table3, not by rerun residual. No replacements or target search.
Primary wavelength is vacuum5008.24 A, z fixed9.433, line-center fitting window
+/-0.015um; pixel-integrated Gaussian plus linear continuum, unconstrained signed
amplitude, center offset bound +/-0.003um, sigma bound0.2--3 native median bins.
Use released 5-pixel coadd FLUX/FLUX_ERR columns if present; otherwise original
release's documented main equivalent (record exact mapping). Use finite positive
errors only, retain invalid-bin counts. No altered aperture or window selected
according to closeness to published flux. Existing jades_balmer_pilot.fit_line
algorithm can be reused for this isolated line. Preserve fitted parameters,
conditioning/convergence, identity, units, bins, covariance and raw hash.

## Selection and access scope

Fetch only explicit goods-s-deephst-10058975 product(s), never a combined GOODS-N
catalogue. Prefer original v1.0 product to match paper. Product identifiers may
be resolved by MAST metadata/search before download; a missing original product
is an acquisition blockage, not permission to use an undeclared version.
Optional original s2d permits a fixed five-row sum with the documented released
point-source/pathloss correction, only if that operator is identifiable. Otherwise
record why it cannot certify a fresh 2D extraction. Raw-exposure end-to-end
reduction requires complete contributor identity, full required detector products
and references within the pilot cap, and compatible executable pipeline. Do not
claim a released coadd fit is detector-end-to-end. If metadata establishes that
complete raw acquisition exceeds the cap, do not download partial raw data and
report raw-end-to-end as unexecuted/unmet.

## Statistic, null, thresholds and multiplicity

Primary statistic delta=(recovered-published)/0.8 in the published1e-19 units.
Null: code's recovered flux is compatible with the published value at its quoted
uncertainty under the original-release data/model; report PASS/FAIL separately
at abs(delta)<=1 and <=2, requiring converged full-rank nonboundary fit and valid
units/coverage. Also report descriptive combined-error delta, clearly dependent
because the photons overlap; never treat it as independent corroboration.
One target, one primary line, one aperture/configuration: no multiplicity
correction needed. No maximum across variants. Calibration applicability and
raw-chain completion are separate requirements: agreement of a coadd fit alone
cannot certify the MoM wavelength calibration or source-specific noise coverage.
A failed numerical measurement does not permit window/target substitution.

## Budgets, artifacts, acceptance and stopping

Science body bytes including restorations <=300,000,000; metadata bodies
<=30,000,000. Bounded transfers record URL, timestamp, status, actual bytes,
SHA256 and failed bodies; stop at budget. Delete acquired raws after compact
reduction; never commit them. Outputs docs/KNOWN_ANSWER_TEST.md and
research_output/session_20261014/c_* JSON/compact receipts; implementation under
data_pipeline/session_known_answer.py and focused tests if needed. Acceptance:
python -m pytest tests/test_session_known_answer.py -q; documented acquisition
and replay CLI reproduce outcomes. Full quality gate is coordinator-owned.
Do not edit STATUS/CLAIM_LEDGER, grade, push, merge or open GOODS-N. List every
unrun chain and verification. Execute outcome access only after coordinator
confirms Phase1 gate green. Record freeze commit/time and first outcome access.
