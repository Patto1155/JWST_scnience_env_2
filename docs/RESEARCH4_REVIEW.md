# Independent review of the GOODS-S paired-configuration continuation

## Round 1: decision before new spectra

**Accept an exploratory GOODS-S measurement-pattern experiment; reject a new physical Balmer-anomaly or population-prevalence claim under the current released-coadd contract.** This distinction permits execution without requiring exposure-level causal identification. GOODS-N outcome rows remain unopened.

The reviewer read `AGENT_RULES.md`, `RESEARCH3_DISCOVERY_PILOTS.md`, the independent JADES audit and the author pilot. Local metadata inspection opened the catalogue headers and explicitly subset `Field == GS` before reading redshifts or line fields. The catalogue contains 3,387 GS observation rows; 252 have robust A/B redshift, positive G140M/G235M exposure metadata and 2.45 < z < 2.95. This broad metadata count is feasibility only, not a line-detection denominator or physical-galaxy count. R1000 fields retain a selected filter for each line; the catalogue cannot itself supply both medium-resolution grating fluxes for a paired test.

A meaningful bounded endpoint is the same emission line measured in two released configurations, on objects selected without the low Balmer decrement or the paired discrepancy. An edge-near versus interior-control comparison can establish an observed measurement pattern within this selected GS cohort. Selection by coverage and exposure avoids direct conditioning on the tested residual, though it still yields a targeted, exposure-biased sample. Previously inspected 7496 is a motivating development source and must be distinguished from fresh follow-up evidence.

Recommended additional control: measure [OIII]5007 in the same products when covered. Its grating-to-grating ratio provides a within-object comparison for gray rescaling, while its difference from the Hbeta ratio can expose a line-local pattern. Different spatial morphology and wavelength-dependent throughput prevent causal interpretation of this contrast.

## Review conditions for the executable protocol

1. Freeze target IDs, grouping, coverage rules, line windows, continuum sidebands and endpoint before accessing new paired spectra. A deterministic small metadata-defined cohort is acceptable; call it a pilot rather than representative sampling.
2. Deduplicate sky objects without using the discrepancy. Distinguish repeat observation rows, shared DR5 identities, apertures and nod choices; dependent variants are sensitivity checks.
3. Report unusable coverage, missing products and rank-deficient fits as failures or null results, never silently replacing targets after flux inspection. Both positive-flux/SNR selection and chosen-grating catalogue selection bias the paired-flux ratio; avoid either as the primary cohort rule.
4. Use direct integration as an independent numerical method. It must expose masked coverage and continuum variance. Gaussian and integration agreement does not establish calibrated uncertainty or unbiased flux.
5. Summarize paired directions, magnitudes, and object-level robustness. Diagonal coadd errors may quantify conditional measurement precision, but cannot calibrate a astrophysical significance or error rate. Calibration can correlate configurations and objects; pixel covariance is unavailable.
6. Treat edge distance as an observed predictor confounded with redshift and product coverage. Small edge/interior groups cannot identify an edge calibration cause. A null pilot means absence of demonstrated pattern under this contract, not proof that the release is unbiased.
7. Separate this new exploratory follow-up from the frozen previous screen. Do not retrofit GOODS-S development into independent confirmation. GOODS-N stays unopened unless a subsequent reviewed protocol explicitly authorizes that holdout.

## Round 2

Awaiting the exact target manifest and frozen analysis protocol. Independent execution and numerical comparison will be appended after products exist.

### Protocol decision transmitted before acquisition

The proposed 12-source pilot is **accepted for execution**, subject to the following concrete conditions already sent to its author. Select six metadata-ranked sources in each redshift bin [2.45, 2.60) and [2.70, 2.90), robust A/B, positive paired exposure, maximum minimum exposure followed by Unique_ID; deduplicate positive DR5 identities/0.2 arcsec; exclude development targets 7496 and 8656. Preserve a frozen target manifest and make no replacements after coverage or download failures. These groups are redshift bins; measured edge distances must be reported rather than naming the groups true edge classes.

The primary descriptive source contrast is D = log(Hbeta_G235/Hbeta_G140) - log([OIII]5007_G235/[OIII]5007_G140). Require four identifiable positive line fluxes for the logarithmic contrast while retaining all measured values and failure counts. Gaussian fits must converge with full rank and no active parameter bounds. The author stop gate is fewer than four valid sources in either group; failure of that gate prevents a group-pattern conclusion. An optional exact permutation reference would depend on exchangeability that these exposure/redshift groups do not guarantee; the reviewer recommended omitting it from the primary report.

The independent oracle is `discovery/research4_review_integration.py`. It imports no author fitting code and integrates bin-clipped flux density over fixed boxes of +/-0.0025, +/-0.0035 and +/-0.0045 micron, subtracting an inverse-variance constant continuum from the red relative sideband [0.008,0.015] micron. The primary box is +/-0.0035 micron, with at least 90% finite covered width, four valid continuum samples and two line samples. It reports negative fluxes but gives a null logarithmic contrast if any component is nonpositive. Hashes, product headers, units, object IDs and explicit GOODS-S identity are checked. Aperture and nod variants remain dependent.

A controlled unit calculation recovered an exactly normalized 100-unit single-bin injection, independently matched the continuum-error contribution, and rejected an intentionally masked primary box. This verifies summation algebra, not real-data calibration or astrophysical accuracy.

### Frozen-manifest independent replay

The exact frozen manifest SHA256 is `3c181df81355e35afd738f0b390981e4dae7b1e92b11d0cd5cda4688676e2872`. An independent metadata-only selection replay reproduces all twelve target IDs in order and checks each catalogue index and redshift. Eligible GS observation counts are 71 in [2.45,2.60) and 83 in [2.70,2.90). The replay uses Astropy great-circle separations rather than the author's small-angle expression; deduplication decisions agree. Its receipt is `research_output/research4_review_manifest.json`. No line outcome columns were read in that selection replay.

The selected lower-redshift targets are 54611, 10011378, 203602, 42645, 43697 and 48912; interior-redshift targets are 20313, 283952, 7586, 8102, 52538 and 10009703. These are twelve operational sky representatives, not a completeness-corrected population sample.

## Round 3: actual coadd execution and method dependence

**The frozen group comparison stops.** The author Gaussian endpoint is available for only two of six lower-redshift targets and four of six interior targets. Independent primary-box integration yields three and five positive covered contrasts, respectively. Both methods fail the preregistered minimum of four in each group. No replacement targets were selected. The reviewer rejects a population, redshift-group, edge-cause or astrophysical inference from these results.

The independent integrator ran on all 24 actual released products, checked object IDs, tiers, sky coordinates and spectral units, and matched every whole-product hash and byte count to the author receipt. A second actual-product replay reproduced the independent JSON byte-for-byte after coordinate checks were added. GOODS-N outcomes remained unopened. Independent summation receipts are `research_output/research4_review_integration.json`; per-source comparison and failure reasons are `research_output/research4_review_comparison.json`.

| Operational source | Gaussian D | Primary direct-box D | Interpretation under this contract |
|---|---:|---:|---|
| GS deepjwst 54611 | -0.362 | -0.402 | Direction agrees; all twelve direct-integration aperture/nod/box variants are negative. |
| GS mediumjwst 43697 | +0.026 | -0.844 | Method-dependent sign; Hbeta is weak. |
| GS deephst 20313 | +0.125 | -0.674 | Method-dependent sign; aperture also changes the direct-integration direction. |
| GS deepjwst 283952 | +0.322 | +0.832 | Primary direction agrees, magnitude changes; one of twelve direct variants is slightly negative. |
| GS deepjwst 7586 | +0.270 | +0.292 | Primary methods agree; 3-pixel primary direct result is -0.029. |
| GS deepjwst 52538 | +0.460 | +0.405 | Primary methods agree; some nod/aperture variants change sign. |

D is a natural-log differential configuration ratio, not a Balmer decrement. Dependent variants are sensitivity checks, not twelve replications.

Two lower-bin failures are literal coverage losses: 10011378 has no G140M Hbeta box/sideband; 48912 has no G235M Hbeta box/sideband. Source 203602 has a boundary/nonidentifiable primary G140M Hbeta Gaussian fit; its direct Hbeta flux is only 2.97 +/- 46.18 in released units. Source 42645 has negative G235M Hbeta and a boundary G235M [OIII] fit. Thus mathematically positive box fluxes can add log-valid contrasts without supplying useful line evidence. The additional direct-integration interior source 10009703 likewise has G235M Hbeta 2.95 +/- 20.66. These conditional diagonal errors must not be treated as calibrated detection probabilities.

### The bounded individual measurement retained

GS deepjwst 54611 has predicted Hbeta wavelength 1.713059518 micron. In its primary G235M product the first finite flux/error wavelength is 1.694181760 micron, giving a 0.018877758 micron distance. The primary Hbeta box is fully covered. This distance is appreciably larger than the 0.00351047 micron in the previously inspected 7496; a measured wavelength-distance comparison does not identify a calibration cause.

For 54611, direct integration gives Hbeta G140M 169.80 +/- 18.52 and G235M 106.87 +/- 17.15, while [OIII] gives 703.80 +/- 18.24 and 662.28 +/- 16.35, all in 1e-20 erg/s/cm2. Thus Hbeta_G235/Hbeta_G140 is approximately 0.629, compared with [OIII]_G235/[OIII]_G140 approximately 0.941. The fitted Hbeta values, 170.76 and 110.23, reproduce the direction. This is a descriptive source-specific line-configuration contrast, in the opposite Hbeta direction from the old 7496 lead. It does not establish astrophysical line variability, a reduction defect, which grating is unbiased, or an intrinsic Balmer ratio.

Both methods impose measurement templates: the Gaussian assumes an integrated single profile and linear local continuum in a fixed window; the independent box uses redshift-predicted centers and a constant one-sided continuum. Continuum curvature, stellar absorption, morphology-dependent slit loss, contamination, line wings and wavelength-dependent calibration can bias either method. Agreement on a direction limits one numerical-method explanation, but cannot replace an exposure-level calibration or extraction audit. The remaining five Gaussian-valid individual contrasts illustrate this limitation through weak-line, continuum, aperture or nod sensitivity.

## Scientific signoff

Accept the frozen metadata selection, actual-product acquisitions and independently reproduced descriptive measurement receipts. Enforce the group-stop decision and do not claim a new physical discovery or a population prevalence. The defensible scientific output is a finite-cohort validation failure and a source-specific configuration inconsistency, with the method-dependent cases shown rather than removed. Reopening a group analysis requires a separately frozen, coverage-qualified protocol and new review; neither post hoc replacement nor GOODS-N opening is authorized by this review.

### Compact replay and hardened final check

`discovery/research4_review_replay.py` independently recomputes the box measurements from the retained actual released-coadd NPZ arrays. It exactly reproduces **576 integrations across 24 product archives**, and its receipt `research_output/research4_review_replay.json` pins each archive size and SHA256. This verifies the numerical data compressor against the independently audited actual-product results; it does not rerun the JADES reduction. Both reviewer modules pass Ruff. The author hardened acquisition failure handling, cached-product hash checks and header/unit validation without changing the frozen scientific manifest or endpoint. The reviewer accepts these implementation repairs and keeps the scientific stop decision.

```bash
python -m discovery.research4_review_replay \
  --receipt research_output/research4_review_integration.json \
  --compact-root research_output \
  --output /tmp/research4-review-replay.json
```
