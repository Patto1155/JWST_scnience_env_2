# Rotation continuation: bounded metadata and novelty gate

12 October 2026. **Stop before acquiring the 136 MB TARS catalog.** The
small paired-star table is real and accessible, but no distinct, independently
motivated empirical transition-band prediction was frozen in this session.
This decision is not an assertion that a new paired rotation result is
impossible, nor a requirement for universal causal identification.

The coordinator explicitly raised the rotation scientific-body ceiling to
160,000,000 bytes, with <=10 minutes of computation and no 13 GB sector-table
acquisition. Hence the earlier 100 MB cap no longer blocked this candidate.
The decision below rests on the scientific question, not the old budget.

## What data feasibility actually establishes

The independent reviewer retrieved and parsed only identity/photometric/
astrometric fields from the public Gruner et al. table:

* https://cdsarc.cds.unistra.fr/ftp/J/A+A/675/A180/ReadMe
* https://cdsarc.cds.unistra.fr/ftp/J/A+A/675/A180/tablec1.dat

Retained inputs are `data_sources/research4/rotation_pairs/ReadMe` and
`data_sources/research4/rotation_pairs/tablec1.dat`. The table is 249,984 bytes;
its 744 stars belong to 372 pairs. There are **287 pairs with both parallaxes
>2 mas**, and **207 also with both Gaia G<16**. This is a plausible distance/
brightness cohort, not an actual TARS overlap: Gaia G is not TESS T, and TARS
requires a detected and accepted period. Prot, Class and Agegroup outcomes
were not opened. The exact metadata hashes and measured screening counts are
in `research_output/research4_rotation_metadata_review.json`.

The current TARS v2 manifest was checked at
https://zenodo.org/api/records/19917941. The complete default detected-period
CSV ZIP is 136,182,994 bytes at
https://zenodo.org/api/records/19917941/files/tars_table_2.csv.zip/content.
Table 2 contains Gaia DR3 IDs, adopted periods/errors, multiplicity and
contamination flags, plus per-sector periods/probabilities/amplitudes. No body
of this product was acquired. The older 944,056-star release is not equivalent
to current v2's 1,046,317-star product.

## Exact primary novelty assessment

Primary papers were checked directly:

* Gruner et al., https://arxiv.org/html/2307.10836v1, introduction and sections
  4.1, 4.2.1–2, 4.3.1. Redder stars rotating faster are already discussed;
  coeval pairs are explicitly shown to follow the nonmonotonic peaks/troughs
  of older cluster sequences. The paper separates 38 discordant systems into
  29 hierarchical pairs and nine remaining outliers. The published Class and
  Agegroup fields use rotation outcomes and cannot define a blind parent.
* Boyle et al., https://arxiv.org/html/2603.05586v2, section VI.6.2. The
  extended intermediate-period gap at 5300–6200 K and the low-amplitude swath
  are already reported. The paper explicitly states that the cool-gap
  amplitude feature is compatible with both detection suppression and rapid
  spin-down. Sector repetition verifies signals but does not supply missing
  objects or an independent selection function.
* Janes, https://arxiv.org/abs/1612.00070, already considers wide-pair period
  gradients, faster cooler companions and the intermediate-period gap.

The explored idea was a conditional test of *signed mass-order reversals
concentrated near the period transition*, then replicated with independent
TESS photons. That could be meaningful without identifying a unique braking
mechanism. However, selecting an arbitrary 13–25-day versus 2–13-day band and
near-twin color interval now would define a new slice of the already-reported
nonmonotonic relation. No independently sourced narrow-band enrichment
prediction or physically defined contrast was established before outcomes.
Independent replication of the known generic inversion is not itself the
requested new physical finding.

The [independent review](RESEARCH4_ROTATION_FEASIBILITY_REVIEW.md) agreed that
the table supplies useful metadata but
no clear distinct empirical relation was justified today. Potential TARS
coverage was not inferred from all-sky survey branding. Neither the TARS
science body nor new period outcomes were downloaded to manufacture a test.

## Concrete next step and reopening gate

For this exact candidate, the next executable step is to write a scientific
prediction contract using an independent spin-evolution or magnetic-activity
source: specify a color/temperature boundary, predicted *signed* pair
contrast, control band and minimum effect, without consulting the retained
pair periods or TARS outcomes. Review whether it differs from the published
nonmonotonic sequence result. Only if that succeeds should the checked TARS
ZIP be acquired and exact integer Gaia DR3 IDs crossmatched to all original
pairs, with independent multiplicity/contamination flags and a fixed
minimum-cohort gate. Keep known Class/Agegroup labels out of selection.

If no new prediction can be justified, choose a different physical observable
or a newer population with an independent control, rather than automatically
replaying existing gyrochronology or building another platform. A magnetic
activity observable would be a different measurement; its public availability
and applicable prediction were not demonstrated here, so it is not an
immediately executable discovery claim.

This continuation produced a verified small-data feasibility result and a
specific pre-acquisition stop, not a rotation experiment or a physical null
result. No new rotation code/tests were added. No paid service or external
contact was used.
