# Discovery continuation — 12 October 2026

Goal: novel, defensible, noteworthy findings worth sharing. Scientific value,
not tests or infrastructure, determines whether a research direction continues.

Incoming local and connected GitHub master: `e272d516bc3ac5f2dc7f6f4897dc42097a3dfebe`.
Checkout was clean and no open PR was returned at session start. This campaign
continues the Library `JWST_Discovery_Handover.md` created after PR #81.

## Roles and rounds

GPT-6.1 Sol high specialists own baseline verification, JADES experimental
design, alternative-target literature/data feasibility, and independent review.
The coordinator selects experiments and integrates reviewed work. Scientific
authors are not their sole validators. Round one selects and freezes designs;
round two executes informative pilots; subsequent rounds challenge or extend
results only when a discriminating test exists.

GOODS-N outcomes must remain unopened until an independent reviewer accepts
the frozen selection, coverage, calibration and multiplicity treatment.
South-field exploratory results are labeled exploratory. Shared photons and
shared calibration are not independent replication. Novelty requires comparison
with primary literature, not absence of search results.

## Newly declared limits

Free public data only; no paid services or external-person contact. Each initial
pilot has at most 100,000,000 new response-body bytes and five minutes numerical
runtime per bounded run. Existing local data may be reused after identity checks.
Metadata transfers and failed requests are recorded where measurable. Any larger
allocation must be explicitly declared by the coordinator before acquisition;
past campaign allowances do not renew. Stop on inaccessible data, inadequate
discriminating power, failed input identity, or exhausted pilot budget.

The runtime-worker sandbox is unchanged. These are authorized trusted coding
agents acting under section 2 of `AGENT_RULES.md`.

## Executed rounds and current conclusion

1. Baseline: 22 focused tests, exact numerical replay of 40 retained JADES
   line fits, and identity verification of nine existing input products.
2. Design and execution: an independent reviewer accepted a 12-target
   GOODS-S paired-grating pilot. A separate CHIME/FRB Catalog 2 design froze
   quality cuts and a chronological replication gate before acquisition.
   Both frozen designs and the baseline were committed before the new results.
3. Adversarial follow-up: independent implementations checked target selection,
   measured JADES lines by direct integration, and reproduced the FRB screen.
   A subsequent FRB archive feasibility check asks whether higher-resolution
   data can resolve the documented blocker. No cuts were relaxed to rescue
   either pilot.

**No new astrophysical discovery is established.** The JADES Gaussian endpoint
is available for two lower-redshift and four interior-redshift targets, below
the frozen four-per-group gate. Independent integration also fails that gate
(three and five usable targets). Individual contrasts depend materially on
method, aperture or nod choice. Source 54611 retains a same-line configuration
contrast across the tested methods, opposite the earlier 7496 contrast; this is
a released-product measurement discrepancy, not an intrinsic physical anomaly.
See `RESEARCH4_REVIEW.md` and the JADES pilot report for numerical scope.

The FRB catalog has 5,045 component rows belonging to 4,539 events. Frozen cuts
retain 29 events across 19 repeating sources, at most four per source. No source
meets the six-event requirement, so neither implementation computes the planned
DM–scattering association. See `RESEARCH4_ALTERNATIVE_FEASIBILITY.md` and the
opportunity report. This does not constrain whether real plasma variations exist.

GOODS-N outcomes remain unopened. Do not promote selected-sample counts,
fit-error scores, methodological agreement or these feasibility failures as
novel physical discoveries. No independent exposure-level calibration was
obtained in this campaign.

## Fourth-round pivot allocation

After both initial pilots stopped, the coordinator allocated a fresh
160,000,000-byte scientific-data budget and ten minutes per numerical run
to a TARS/coeval-wide-pair feasibility and prediction pilot. The complete
136,182,994-byte compressed TARS table may be acquired only after a specific
literature-checked prediction and a usable small paired-star source table are
identified. The 13 GB sector catalog is excluded. The FRB cuts and its stopped
result are unchanged. Independent review precedes new scientific outcomes;
if no credible discrimination is available, record that reason and stop.

The fourth round stopped before that large acquisition. The small published
pair table contains 372 pairs; 207 meet the inspected parallax/G-band metadata
cuts, which neither verify TESS magnitude nor establish TARS overlap. Primary
literature already discusses the proposed rotation mass-order reversals and
sequence peaks/troughs. No independently motivated new period-band prediction
was identified. See `RESEARCH4_ROTATION_FEASIBILITY.md`. This is a novelty/design
stop, not a failed stellar-physics test or a claim that the whole topic is closed.

## Validation and next action

Full configured quality gate: **746 passed, three documented external-data
skips, no failures or errors**, plus direct strict lint/format checks of all
ten research4 Python modules/tests. Python files did not change during the gate.
`research_output/research4_validation.json` pins code and compressed evidence.
Independent numerical validation is separately retained: exact 576-integration
JADES compact replay, original-product identities, and identical 29-event FRB
selection from independently implemented readers. These are validation of the
reported experiments, not evidence of physical discovery.

First next action: read the portfolio and rotation-feasibility reports and
identify a **specific physical prediction plus an actually available independent
observable** before adding another catalog screen. Reopen FRB only with a
concrete repeated high-resolution data manifest; reopen the JADES group design
only with a new reviewed measurement contract and preserve unopened GOODS-N.
Do not rerun these stopped pilots, weaken their cuts, or promote source 54611
as a new physical object. A future conditional empirical pattern is acceptable
without unique causal identification, but it must add something beyond the
explicit prior literature and survive an independent test.

Publication note: the untouched CDS fixed-width table intentionally retains its
original trailing spaces. A post-decision Git whitespace check displayed some
raw rows, including rotation fields, to the coordinator. No rotation outcome
analysis or TARS acquisition followed; do not describe the stored rotation
table as a strictly blinded holdout for a future campaign. The earlier specialist
metadata-only inspection receipts describe their own pre-decision scope.
