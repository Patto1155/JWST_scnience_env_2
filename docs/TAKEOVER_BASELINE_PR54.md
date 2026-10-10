# JWST research takeover: current verified status

9 October2026. This document supersedes historical claims. Incoming master
`1b4012e326664ce2a3ec5a515b5a832138aba46b` (PR #29) is preserved in
[TAKEOVER_BASELINE_PR29.md](TAKEOVER_BASELINE_PR29.md), with its
[full report](FINAL_RESEARCH_REPORT_PR29.md). The
[current full report](FINAL_RESEARCH_REPORT.md) distinguishes observations,
assumptions, conditional inferences and speculation. Historical1,732 candidates
remain **untestable**, not measured artifacts. No new high-z source, elemental
abundance, polluter or cosmological discovery is claimed.

Eight specialists completed separate-branch research, implementation and
independent-validation rounds; [protocol](CONTINUATION_PROTOCOL.md) records
ownership/dependencies. Follow-ups use merged inputs and preserve earlier
contracts. The coordinator reproduced the incoming363-test/two-fixture-skip
gate, all 13 original image hashes, nine native hashes, fresh GOODS pixel
CSV/metadata byte for byte and nominal coadd numerical fits/scans.

## Supported results and limitations

- **GOODS:**1,134 proposals,891 untestable,236 measured screen failures,seven
  first-screen survivors,0.962808arcmin². Six fail stable original-brightness
  persistence;98 persists. Conditional254/46 remain separate denominators.
- **SMACS:** matched selection1,267/940 untestable/317 failures/ten raw survivors.
  A newly acquired disjoint-contributor F444 exposure separated by 15.39minutes
  rejects nine nominal persistence premises.1043 retains a fixed-aperture red
  patch, without an independent segmented object or confirmed identity.
- **SMACS noise/background:** measured field-specific aperture factors
  F0901.184[1.081,1.351],F2001.285[1.183,1.380],F4440.938[0.894,0.979]. Conditional
  block intervals and sparse tails do not certify Gaussian five-sigma behavior.
 1043's blue residual changes strongly with background; its old negative
  aperture is not a background-independent non-detection.
- **Deep modeling:**254 has aligned F09017.84±0.81nJy, with independent
  background checks18.47–19.01. Its no-blue-counterpart premise fails.98 is a
  persistent blended complex with inadequate residual fit; component totals and
  dropout identity remain uncertain.46 has strongly curved red photometry.
  All 1,052 tested cloudless Sonora equilibrium rows fit poorly; this finite
  grid fails, without identifying the source or excluding other atmosphere families.
- **Real-source recovery:** frozen14-group controls and2,436 observed-profile
  injections expose centroid/segmentation failures and nonmonotonic recovery.
  The latter has149 paired losses/no gains for the larger detector threshold.
  These conditional local tests do not measure survey completeness or contamination.
- **Native spectroscopy:** nine actual CALs form three RATE groups with shared
  background photons. The reconstruction applies no second nod subtraction,
  uses guarded pathloss/profile extraction, and transports empirical covariance.
  Original point empirical line-flux N/C=.79179[−.00677,2.88294]; spatial transport
  gives.79306[−.00598,2.88356]. These are signed conditional95% Fieller sets,
  not abundance measurements. Source-specific LSF remains uncalibrated.
- **Atomic models:** PyNeb1.1.32 and Cuev0.1 are versioned and member-pinned.
  Cue omits N IV and cannot supply a full N-line ionization map. Version2
  explicitly fits total N IV1483+1486 with physical weights and fresh covariance:
  atTe20k/ne 1,000 point empirical ionic N/C=2.7504[−.5064,9.5916], and all 28
  original-wavelength point empirical cells cross zero. Elemental N/C requires unmeasured stage
  fractions, with unresolved He/O and C IV transfer.
- **Wavelength sensitivity:** the exact logged reference is DUMMY/toy. Original
  target WCS was not wave-corrected despite the global COMPLETE flag. Its
  prediction changes conditional line flux and worsens the legacy point
  scenario's chi²; the composed response depends on resolution. It is neither a
  preferred detection model nor empirical wavelength/LSF calibration.
- **Enrichment/formation:** full covariant yield profiles do not identify an SMS
  or rotating polluter.720 histories/216 budgets/80 inverse tests give explicit
  conditional predictions. Standard rising histories can lie inside the
  published marginal SED boxes under assumed mass conventions. Population
  selection/contamination and survey volume are absent, so cosmological model
  odds cannot be assigned from these candidate counts.

The final336-fit composition explicitly compares original and DUMMY wavelength
hypotheses with all three reviewed noise transports. Original empirical cells
admit the assumed solar ionic reference in28/28 cells; DUMMY alternatives admit
it in16/28 nominal and18/28 point cells. Positive lower endpoints under the toy
hypothesis are conditional sensitivity, with no measured calibration or stage
correction. At the reference point/row+column cell, original2.7535[−.5058,9.5970]
versusDUMMY3.7236[.1077,14.5265] both admit that reference.

## Reproducible experiment index

Report-specific commands give exact arguments and raw inventories. Entry points
below identify executable work; numerical replay is distinct from calibration.

| Experiment | Report | Entry point / compact artifacts |
|---|---|---|
| Incoming independent baseline | [Protocol](CONTINUATION_PROTOCOL.md) | `research_output/continuation_baseline.json`; `python scripts/quality_gate.py` |
| Distinct repeat and held-out coordinates | [SMACS repeat](SMACS_INDEPENDENT_REPEAT.md) | `discovery.independent_repeat_vetting`; repeat JSON/figure |
| Local empirical PSF/noise/tails | [SMACS controls](SMACS_EMPIRICAL_CONTROLS.md) | `discovery.empirical_imaging_controls`; controls JSON |
| Persistent patch spatial models | [1043 diagnostics](SMACS1043_PATCH_DIAGNOSTICS.md) | `discovery.source_patch_diagnostics`; JSON/native figure |
| Deep data and seven-band model | [Inputs](SURVIVOR_DEEP_DATA.md), [models](SURVIVOR_DEEP_MODEL.md) | `data_pipeline.survivor_deep_data`; `discovery.survivor_deep_model`; JSON/figures |
| Frozen controls and injections | [Controls](DEEP_CONTROL_RECOVERY.md), [injections](OBSERVED_TEMPLATE_INJECTIONS.md) | `discovery.deep_control_recovery`; `discovery.observed_template_injections`; plan/recovery JSON |
| Source46 atmosphere families | [Atmosphere](SURVIVOR_ATMOSPHERE.md) | `discovery.survivor_atmosphere`;1,052-row CSV and JSON |
| Native extraction/shared covariance | [Reduction](MOM_NATIVE_REDUCTION.md), [spatial covariance](MOM_NATIVE_SPATIAL_COVARIANCE.md) | `tools.jwst.native_reduction`; `tools.jwst.native_spatial_covariance`; pinned NPZ/JSON |
| Source-offset toy wavelength model | [Wavelength report](MOM_NATIVE_WAVECORR.md) | `tools.jwst.native_wavecorr`; reference, original-GWCS derivatives, NPZ/JSON |
| Atomic and four-group photoionization | [Atomic](MOM_ATOMIC_IONIC_GRID.md), [Cue](MOM_CUE_PHOTOIONIZATION.md), [native chemistry](MOM_NATIVE_CHEMISTRY_FOLLOWUP.md) | `tools.jwst.atomic_grid`; `tools.jwst.cue_grid`; pinned grids/native fits |
| Versioned physical multiplets | [Version1](MOM_NATIVE_MULTIPLET_REFIT.md), [N IV doublet v2](MOM_NIV_DOUBLET_V2.md) | `tools.jwst.multiplet_refit`; `tools.jwst.niv_doublet_refit`;112 fresh fits per contract |
| Composed physical/noise/wavelength alternatives | [Final336 fits](MOM_COMPOSED_SPECTRAL_ROUND.md) | `tools.jwst.composed_spectral_refit`; fresh flux/covariance JSON and signed interval figure |
| Covariant yields and formation predictions | [Version1 yields](ATOMIC_ENRICHMENT_COMPARISON.md), [version 2 bridge](NIV_YIELD_SENSITIVITY.md), [formation](FORMATION_PREDICTIONS.md) | `discovery.atomic_enrichment`; `discovery.niv_yield_sensitivity`; `discovery.formation_predictions`; full-covariance JSON |
| Independent solvers and counterexamples | [First](CONTINUATION_INDEPENDENT_REVIEW.md), [follow-up](CONTINUATION_FOLLOWUP_REVIEW.md), [final](CONTINUATION_FINAL_REVIEW.md) | `discovery.continuation_review`; follow-up/final/physical review modules; compact receipts; `research_output/continuation_coordinator_review.json` |

Large raw inputs remain outside git with public bounded regenerators and exact
byte/hash receipts. Newly selected scientific inputs total 228,790,074bytes;
3,425,987bytes of optional WCS software/source are separately accounted. After
transient cache loss,464,135,040bytes of already-pinned native originals were
recovered, separately from new input selection. The lost original-image cache
is not claimed present; its completed reruns and reviews remain committed.

## Release validation and merged PRs

The final receipt `research_output/continuation_final_validation.json` records
the tested tree, exact test/skips and lint target counts, numerical replays,
input ledger, artifact pins and merged PR revisions. Every science PR passed
CI and independent validation before merge. Earlier gates are historical;
final clean tracked-tree release gate: **579 passed, 3 explicit skips**,
117 scientific lint targets plus six core targets. The two historical
archive fixtures and optional author Cue archive are named skips. The optional
author NumPy/weight test passed separately on the actual pinned archive.

| PR | Validated change | Merge revision |
|---|---|---|
| [#30](https://github.com/Patto1155/JWST_scnience_env_2/pull/30) | Incoming baseline/protocol | `e9975a1560ce` |
| [#31](https://github.com/Patto1155/JWST_scnience_env_2/pull/31) | Distinct SMACS repeat | `0ad4a654addc` |
| [#32](https://github.com/Patto1155/JWST_scnience_env_2/pull/32) | Frozen deep controls | `e4bcfd41b0eb` |
| [#33](https://github.com/Patto1155/JWST_scnience_env_2/pull/33) | SMACS empirical noise/tails | `ecc015b3a30e` |
| [#34](https://github.com/Patto1155/JWST_scnience_env_2/pull/34) | Versioned atomic inputs | `e95d05b5b532` |
| [#35](https://github.com/Patto1155/JWST_scnience_env_2/pull/35) | Deep cutouts/PSF/filter inputs | `efdf88e59b2b` |
| [#36](https://github.com/Patto1155/JWST_scnience_env_2/pull/36) | Nine-CAL native reconstruction | `06273801b1e8` |
| [#37](https://github.com/Patto1155/JWST_scnience_env_2/pull/37) | Cue photoionization comparison | `f1a74d1ce0e3` |
| [#38](https://github.com/Patto1155/JWST_scnience_env_2/pull/38) | Deep multiband spatial models | `fdfc98f52400` |
| [#39](https://github.com/Patto1155/JWST_scnience_env_2/pull/39) | Covariant enrichment comparisons | `d87538305b9d` |
| [#40](https://github.com/Patto1155/JWST_scnience_env_2/pull/40) | Independent review/operators | `2cdcbc4e7c95` |
| [#41](https://github.com/Patto1155/JWST_scnience_env_2/pull/41) | Observed-profile injections | `9944ac3e8ded` |
| [#42](https://github.com/Patto1155/JWST_scnience_env_2/pull/42) | Source46 atmosphere grid | `c984db47e8b2` |
| [#43](https://github.com/Patto1155/JWST_scnience_env_2/pull/43) | Native spatial covariance | `05d619135da6` |
| [#44](https://github.com/Patto1155/JWST_scnience_env_2/pull/44) | Native atomic/Cue follow-up | `6293d04ffe65` |
| [#45](https://github.com/Patto1155/JWST_scnience_env_2/pull/45) | 1043 background/PSF diagnostics | `83b5c8ed1bf3` |
| [#46](https://github.com/Patto1155/JWST_scnience_env_2/pull/46) | Version1 physical multiplet refits | `f1e428f62647` |
| [#47](https://github.com/Patto1155/JWST_scnience_env_2/pull/47) | Formation/population predictions | `2758481572de` |
| [#48](https://github.com/Patto1155/JWST_scnience_env_2/pull/48) | Actual-data follow-up reviews | `384448e3bc4e` |
| [#49](https://github.com/Patto1155/JWST_scnience_env_2/pull/49) | Version2 N IV doublet refits | `678e6cf24fbf` |
| [#50](https://github.com/Patto1155/JWST_scnience_env_2/pull/50) | Logged toy wavelength sensitivity | `bbbd15288237` |
| [#51](https://github.com/Patto1155/JWST_scnience_env_2/pull/51) | Version2 conditional yield bridge | `98e4e2ea48eb` |
| [#52](https://github.com/Patto1155/JWST_scnience_env_2/pull/52) | Composed336 physical/noise/wavelength fits | `0bdb5337a9e2` |
| [#53](https://github.com/Patto1155/JWST_scnience_env_2/pull/53) | Final independent GLS/atomic/formation/yield/WCS review | `a1568038ab2a` |

## Prioritized next work

1. Obtain actual PIXTAB/extraction settings and source-specific wavelength/LSF
   calibration; validate cross-group covariance, residual tails and consistent
   point-source recalibration. Extend the merged336-fit composition to
   source geometry, redshift, intrinsic width and He/O/C IV nuisance hypotheses
   with each own covariance, without likelihood pooling.
2. Build a complete N IV-inclusive, composition-aware photoionization grid.
   Public Cloudy is accessible; its≈323MB release archive exceeds the present
   atomic acquisition allocation, requiring a separately bounded model round.
3. Separate N IV/C III density components and He II/O III with higher-resolution
   observations; constrain other ion stages, gas mass, C/O and retention.
4. Improve empirical PSF/neighbor modeling for98/1043, broader source 46 spectral
   families, optical/medium-band constraints and a disjoint long-baseline motion test.
5. Retrieve author SED mass/time-bin conventions and fit joint data. Acquire
   representative selection/contamination/volume evidence before population or
   cosmological inference. Historical untestability is not negative evidence.
