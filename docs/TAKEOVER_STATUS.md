# JWST research takeover: current verified status

9 October 2026. This document supersedes older scientific claims. The incoming
verified baseline is preserved in [TAKEOVER_BASELINE_2026-10-09.md](TAKEOVER_BASELINE_2026-10-09.md).
The [full research report](FINAL_RESEARCH_REPORT.md) distinguishes observations,
assumptions, conditional inferences and unresolved requirements.

Eight specialists completed acquisition, implementation, validation and further
experiments. All four incoming next-experiment categories were executed on real
public data; follow-ups were built on merged changes. No new astrophysical
source, elemental abundance, enrichment mechanism or cosmological discovery is
claimed.

## Results that are currently supported

- **Original images:** thirteen complete current GOODS-S/SMACS individual-exposure
  i2d products, 1,555,571,520 bytes under 1.5 GiB. External JADES F444W residual
  median 0.02155 arcsec. Old F277W repeat baseline corrected to 5.64853 hours.
- **GOODS selection:** 1,134 proposals; 891 untestable, 236 measured screen
  failures and seven first-screen survivors. Area 0.962808 arcmin². The screen
  uses F090/F444 and F200 coverage, with no F200 color or redshift criterion.
  Only **98 persists** among those seven in covered F444W siblings; six fail a
  stable-source interpretation at original brightness. Conditional entrants
  254/46 also persist and remain separate denominators. None is confirmed high-z.
- **SMACS geometry:** simultaneous coverage, rather than independent overlap,
  fixes disjoint-quarter selection. With the acquired F200 NRCA1 alternative:
  1,267 proposals; 940 untestable, 317 failures, ten raw survivors; 1.064573 arcmin².
  Noise/PSF/repeat validation of this raw screen remains a next experiment.
- **PSF and sky scatter:** unresolved model total/aperture multipliers
  1.217/1.207/1.429 (F090/F200/F444); empirical sky/diagonal factors
  1.576 [1.328,1.804], 1.452 [1.192,1.625], 1.048 [0.965,1.154]. Brackets are
  conditional spatial-block intervals. Corrections change candidate identities;
  neither model nor robust sky width certifies faint-source tails or galaxy totals.
  Eleven observed M92 stars give finite-aperture ratio 0.784 [0.754,0.807], with
  substantial crowded-background sensitivity.
- **Real recovery:** M92 conditional classifier rejection about 0.034%, nominal
  Wilson 95% upper bound 0.101%, but full-chain acceptance about 66.5% and sharply
  brightness dependent. One held-out visit and missing training provenance limit
  generalization. Three covered high-z controls missed in the original image:
  deeper public images recover two; the third has aperture signal but fails detection.
- **MoM spectrum:** resolution, signed bin-integrated UV fits, explicit masks,
  full linear flux covariance and alternative extractions are implemented.
  Nitrogen/carbon summed **line-flux** ratio 1.039 [0.448,2.159] with nominal slit
  R, versus 1.050 [0.502,2.047] with generic point-source R; conditional 95% Fieller
  sets, not elemental N/C. Intrinsic width remains unresolved. All nine native
  exposures acquired/verified; inspected DQ supports no removal of influential bins.
  Source-weighted coadd reconstruction and empirical covariance remain unresolved.
- **Chemistry and formation:** no calibrated emissivity/ionization grid means
  elemental N/C and polluter identity remain unidentified. Cue-median effective
  Q=0.521 [0.225,1.082], point-R Q=0.526 [0.251,1.026]. Joint C/O,O/H, helium and
  local gas budgets provide conditional discriminators. A 204-Myr history starting
  at z=20 fails the 104.959-Myr Planck18 budget; this rejects that combined history,
  not WR enrichment generally. Selected stellar models are compared on common
  solar conventions. No completeness-controlled population supports exotic cosmology.

Historical 1,732 candidates remain **untestable**, not measured artifacts.
Original historical claims, synthetic controls and independent real measurements
retain their different scopes. Counterexamples corrected cached-byte verification,
empty native inventories and a literature solar-convention comparison.

## Reproducible artifact index

| Experiment | Report and compact results | Executable entry point |
|---|---|---|
| Environment/ownership | [Protocol](RESEARCH_PROTOCOL.md), `requirements-research.lock` | `python scripts/quality_gate.py` |
| Original provisioning and astrometry | [Astrometry](ORIGINAL_IMAGE_ASTROMETRY.md), `research_output/original_image_astrometry.json` | `python -m data_pipeline.original_images`; `python -m discovery.external_astrometry` |
| Calibrated original selection | [Photometry](ORIGINAL_IMAGE_PHOTOMETRY.md), `research_output/original_image_rerun/` | `python -m discovery.image_photometry_rerun MANIFEST --output-dir OUTPUT` |
| Native PSF and real sky noise | [Noise report](../research_output/PSF_NOISE.md), [Native PSF](NATIVE_PSF_NOISE.md), phase CSV and noise JSON | `python -m discovery.psf_noise`; `python -m discovery.native_psf` |
| Real stars and galaxies | [Real-source validation](REAL_SOURCE_VALIDATION.md), `research_output/real_validation_*.json` | `python -m data_pipeline.real_validation_acquire`; `python -m discovery.real_validation` |
| Original repeat tests | [Repeat report](ORIGINAL_REPEAT_TEST.md), `research_output/f444w_repeat_screen*.json` | `python -m discovery.f444w_repeat_screen` |
| Joint selection, noise and continuum | [Imaging follow-up](PHOTOMETRY_ROUND_THREE.md), SMACS replay CSVs, sensitivity/continuum JSON | `python -m discovery.photometry_sensitivity`; `python -m discovery.survivor_continuum` |
| Deeper reference comparison | [Follow-up data](FOLLOWUP_DATA.md), `research_output/deep_reference_comparison.json` | `python -m data_pipeline.followup_data`; `python -m discovery.deep_reference_comparison` |
| Nine native spectra and primary tables | [Native batch](MOM_NATIVE_BATCH.md), native/stellar inventories and JSON | `python -m data_pipeline.mom_native_batch`; `python -m data_pipeline.rotating_benchmarks` |
| Nominal spectral analysis | [UV fit](../research_output/mom_z14_line_sensitivity.md), companion JSON/PNG | `python -m tools.jwst.line_sensitivity`; `python -m tools.jwst.line_report` |
| Point-source resolution and leverage | [Point-R report](../research_output/mom_z14_point_resolution.md), companion JSON | `python -m tools.jwst.point_resolution` |
| Conditional enrichment and formation | [Constraints](ENRICHMENT_CONSTRAINTS.md), companion JSON | `python -m discovery.enrichment_constraints` |
| Flux/abundance identifiability | [Identifiability](CHEMISTRY_IDENTIFIABILITY.md), [resolution comparison](CHEMISTRY_RESOLUTION_COMPARISON.md), JSON | `python -m discovery.chemistry_identifiability` |
| Observed aperture response | [Observed-star report](M92_APERTURE_RESPONSE.md), compact JSON/PNG | `python -m discovery.stellar_aperture` |
| Independent review | [Review](ADVERSARIAL_REVIEW_R3.md), [follow-up addendum](ADVERSARIAL_FOLLOWUP_REVIEW.md), independent input/noise evidence | `python -m discovery.adversarial_noise_controls` |

Report-specific commands give required arguments, exact inventories and caveats;
entry points above are an index, not complete invocations. Large raw FITS and
full trials stay outside git with bounded regenerators and receipts. Saved CSV
replays reproduce all three selection summaries but do not replace pixel reruns.
Spectral-resolution comparison retains an exact earlier point-report snapshot
with recovery from its public Git commit when later provenance guards change.

## Merged changes and validation

| Round | Merged PRs | Outcome |
|---|---|---|
| Real-image and spectral baseline | [#14](https://github.com/Patto1155/JWST_scnience_env_2/pull/14), [#15](https://github.com/Patto1155/JWST_scnience_env_2/pull/15), [#16](https://github.com/Patto1155/JWST_scnience_env_2/pull/16), [#17](https://github.com/Patto1155/JWST_scnience_env_2/pull/17), [#18](https://github.com/Patto1155/JWST_scnience_env_2/pull/18), [#19](https://github.com/Patto1155/JWST_scnience_env_2/pull/19) | Protocol, real noise, original rerun, conditional yields, covariant UV fits, real recovery |
| Dependency-driven follow-up | [#20](https://github.com/Patto1155/JWST_scnience_env_2/pull/20), [#21](https://github.com/Patto1155/JWST_scnience_env_2/pull/21), [#22](https://github.com/Patto1155/JWST_scnience_env_2/pull/22), [#23](https://github.com/Patto1155/JWST_scnience_env_2/pull/23), [#24](https://github.com/Patto1155/JWST_scnience_env_2/pull/24) | Native PSFs/deep data, all native spectra, repeat tests, point-R/leverage, chemistry guard |
| Further discrimination and corrections | [#25](https://github.com/Patto1155/JWST_scnience_env_2/pull/25), [#26](https://github.com/Patto1155/JWST_scnience_env_2/pull/26), [#27](https://github.com/Patto1155/JWST_scnience_env_2/pull/27), [#28](https://github.com/Patto1155/JWST_scnience_env_2/pull/28) | Common solar scale, joint coverage/noise/continuum, resolution-to-chemistry comparison, observed stellar aperture response |

Integrated Python3.12 gate: **363 passed, 2 explicit historical-fixture skips**;
all 61 scientific lint targets plus the core lint/format/type gates pass. The
skips request older fixed `data/jwst/mastDownload` fixtures not in the selected
acquisition. They do not substitute for the executed manifest-based real-image
experiments. A clean tracked-file checkout is independently checked without
local download caches. Every science PR passed CI before merge.

Three compact selection catalogs replay exactly, including CSV/metadata hashes.
The saved noise/PSF sensitivity JSON and the preserved spectral-resolution
chemistry JSON reproduce exactly. Independent review also replayed all observed
M92 aperture records byte-identically and verified all nine native hashes/DQ.
[Final validation receipt](../research_output/final_validation.json) records the
scope; numerical replay is distinct from calibration or astrophysical truth.

## Highest-value next work

1. Reconstruct independent native nod spectra with source-specific LSF/pathloss,
   trace-weighted quality masks and empirical shared-noise/background covariance.
   Public archive access is resolved; original PIXTAB/contributor weights and
   exact upstream settings are genuine missing inputs.
2. Fit versioned atomic/photoionization models jointly to covariant N/C/O/He line
   groups, then compare abundance-conditioned yields. Higher-resolution density
   multiplets and separated He II/O III] require new observations.
3. Deep multiband PSF/SED modeling and independent repeat vetting of conditional
   GOODS sources and raw SMACS survivors; calibrate faint real-source selection,
   completeness and contamination across fields/visits.
4. Constrain emitting gas mass, C/O, helium and differential retention; evaluate
   complete enrichment histories and completeness-controlled galaxy populations
   before cosmological claims.
