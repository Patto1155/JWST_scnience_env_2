# Claim ledger

Verified 2026-10-14 audit realignment; the lead researcher owns all grades.
This is the sole current claim ledger.
Repository-relative paths below identify existing evidence. Fixed scale: Validated /
Candidate / Unconfirmed lead / Null / Rejected / Superseded. Candidate and Validated
require claim-specific null, injection and independent-repeat/holdout artifacts.
A dash means no sufficient control is asserted. Historical artifacts are not rerun
results; verified source-document scope is preserved.

| Finding | Grade | Evidence | Null control | Injection recovery | Independent repeat/holdout | Scope |
| --- | --- | --- | --- | --- | --- | --- |
| DDE 54 four-year recurrence / SPHEREx W1 state | Unconfirmed lead | docs/RESEARCH5_CAMPAIGN.md; docs/RESEARCH5_REVIEW.md; docs/RESEARCH5_SPHEREX_REVIEW.md | — | — | — | Historical source-specific IR modulation is supported, but the frozen W1 contract fails coverage/two-visit requirements. A narrowband point is not a W1 state; a known variable is not a new object. |
| DDE 54 frozen optical median-state contrast | Null | docs/RESEARCH5_REVIEW.md | — | — | — | Faint-minus-bright r contrast -0.04890065 mag; conditional 30-day-bin interval [-0.15284,+0.09383]. Applies only to frozen long windows, not optical constancy. |
| CLASS J111855 intrinsic coronal fading | Unconfirmed lead | docs/RESEARCH5_REVIEW.md; docs/RESEARCH5_SPECTRAL.md | — | — | — | Original narrow-control gate failed; baseline flags, weak comparison lines, spatial sampling and covariance remain. Exploratory 5720 diagnostic cannot pass the original gate. |
| KIC 8164262 mode evolution | Null | docs/RESEARCH5_CAMPAIGN.md; docs/RESEARCH5_STELLAR_REVIEW.md | — | — | — | Eight TESS sectors extend the amplitude baseline; no robust physical evolution survives background/centroid sensitivity. Null is not proof of permanent amplitude constancy. |
| CHIME FRB temporal-plasma association | Unconfirmed lead | docs/RESEARCH4_CAMPAIGN.md; research_output/research4_frb_results.json; research_output/research4_frb_review.json | — | — | — | Stopped: 29 qualifying events across 19 sources, at most four per source, so the six-event/six-source gate fails before covariance. No association was tested; do not grade this as a statistical null. |
| JADES GOODS-S 7496 physical Balmer anomaly | Rejected | docs/RESEARCH3_DISCOVERY_PILOTS.md; docs/RESEARCH3_JADES_INDEPENDENT_REVIEW.md | — | — | — | Grating inconsistency defeats the physical interpretation; overlap-based ratio approximately 2.73/2.86. The causal calibration/extraction error is not identified. |
| JADES GOODS-S 54611 physical Balmer anomaly | Rejected | docs/RESEARCH4_CAMPAIGN.md; docs/RESEARCH4_REVIEW.md | — | — | — | Repeatable released-product configuration discrepancy persists, but does not establish an intrinsic physical anomaly; sample gate fails. |
| JADES GOODS-S 8656 low Balmer ratio | Unconfirmed lead | docs/RESEARCH3_DISCOVERY_PILOTS.md | — | — | — | Weak support and unstable noisy overlap; no validated ratio anomaly. |
| MoM-z14 enriched elemental N/C | Unconfirmed lead | docs/FINAL_RESEARCH_REPORT.md; docs/TAKEOVER_BASELINE_PR54.md; docs/RESEARCH2_RATE_NOISE_CONTRACT.md | — | — | — | Conditional observed-stage ionic 95% Fieller interval [-0.158,9.905] admits the ambient ionic reference; formal-noise interval [0.429,7.762] does not. Noise assumption decides it. Neither interval is elemental N/C or empirically certified source coverage. |
| Source 46 physical identity / SED explanation | Unconfirmed lead | docs/FINAL_RESEARCH_REPORT.md; research_output/survivor46_flame_v1.json; research_output/survivor46_multiplicity_v1.json | — | — | — | Tested finite Bobcat and Flame/Skimmer families fail; F410M disfavors negligible-F410/F444-only excess. Identity and continuum/line/multiplicity remain unresolved. |
| SMACS source 1043 physical source claim | Unconfirmed lead | docs/FINAL_RESEARCH_REPORT.md; docs/SMACS1043_PATCH_DIAGNOSTICS.md; research_output/smacs_independent_repeat.json; research_output/candidate_neighborhood_v1.json | — | — | — | Historical Candidate -> Unconfirmed lead: persistent patch but unstable flux assignment; scene fits fail held-out residual gate. Existing repeat reduction is not the required complete null/injection/independent-data control trio. |
| Historical 1732-record dropout catalog | Rejected | FINDINGS.md | — | — | — | Zero survive the complete configured selection: all 1732 are untestable due to absent paired F090W/F200W coverage. Selection claim rejected; objects are not thereby proven artifacts. |
| Historical ~15% artifact-rate inference | Superseded | HANDOVER.md | — | — | — | 2026-10-09 ending correction says it was not reproduced. Single-epoch-only fraction is not a universal calibrated contamination rate. |
| 1000–1250 (and derived ~360) artifacts per high-z source | Superseded | HANDOVER.md | — | — | — | Uncalibrated cross-population/depth/selection-function comparison; no accepted contamination estimate follows. |
| Retrained morphology classifier scientific completeness | Unconfirmed lead | HANDOVER.md; research_output/artifact_classifier.json; research_output/injection_recovery.json | — | — | — | Limited methodological result, partly circular: training and test injections share the generator. Held-out visits do not replace representative independently labelled real point-source validation. |
| Null-calibrated ramp discriminator (AUC 0.791) | Null | HANDOVER.md; research_output/ramp_diagnostics.json | — | — | — | Five-group calibrated discrimination is too weak for the proposed science cut; AUC is a conditional performance metric, not an astrophysical discovery. |

All rows were checked against the named source documents. No new astrophysical
result has survived verification. There are no Candidate/Validated rows.
Phase 2 proposals require the lead's review and canonical ledger update.
