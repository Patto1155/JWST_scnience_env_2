# JWST research takeover: verified baseline

9 October 2026. Three rounds of work established calibrated measurements,
tested the frozen recovery pipeline, and added actual public spectroscopy.
The original research PR #1 and new PRs #2–#12 are merged. PR #13 records this
handoff and expands lint coverage across the new scientific modules.

## Merged work

| Round | Pull requests | Result |
|---|---|---|
| Baseline | [#2](https://github.com/Patto1155/JWST_scnience_env_2/pull/2), [#3](https://github.com/Patto1155/JWST_scnience_env_2/pull/3), [#7](https://github.com/Patto1155/JWST_scnience_env_2/pull/7) | BUNIT/WCS calibration, matched sky apertures, uncertainty-aware dropout limits, WCS overlap, physical repeat-epoch comparisons |
| Baseline | [#4](https://github.com/Patto1155/JWST_scnience_env_2/pull/4), [#5](https://github.com/Patto1155/JWST_scnience_env_2/pull/5), [#6](https://github.com/Patto1155/JWST_scnience_env_2/pull/6) | Bounded agent loops, offline CI, denominator-aware validation, pinned public data |
| Follow-up | [#8](https://github.com/Patto1155/JWST_scnience_env_2/pull/8), [#9](https://github.com/Patto1155/JWST_scnience_env_2/pull/9), [#10](https://github.com/Patto1155/JWST_scnience_env_2/pull/10) | Actual-FITS epoch controls, 2,304 PSF stress trials, calibrated evidence panels and cache invalidation |
| Real data | [#11](https://github.com/Patto1155/JWST_scnience_env_2/pull/11), [#12](https://github.com/Patto1155/JWST_scnience_env_2/pull/12) | Quality-aware reference cohorts, verified public MoM-z14 spectrum, unit/error diagnostics |

## Findings and their limits

* Historical candidates: **1,732 untestable**, zero measured falsifications and
  zero survivors under the corrected audit. Missing calibrated evidence does
  not establish detector-artifact identity. Historical catalogs were not silently
  replaced; the original FITS archive must be provisioned for a fresh pipeline run.
* Existing F444W faint point injections: **27/119 recovered (22.7%)**, nominal
  Wilson interval 16.1–31.0%. Zero classifier rejections among 27 detections still
  allows a 12.5% nominal upper bound. Shared-image dependence and systematics are
  not captured by these intervals. See [validation](VALIDATION.md).
* New stress experiment: source-template choices materially alter recovery and
  morphology. For unresolved F277W sources with total injected flux 120 times
  the per-pixel noise sigma, both kernels detect 32/32; the frozen classifier
  accepts 32/32 JADES-model kernels and 0/32 Gaussian kernels. This is a paired
  synthetic-background comparison, not observed-sky performance. Training PSF
  provenance remains incomplete. See [PSF stress](EXTERNAL_PSF_STRESS.md).
* Real JADES DR4 references: **243 A/B high-z observations, 1,461 A/B low-z
  controls, and 48 separately retained C high-z observations**. Repeated
  observations are not unique galaxies, and targeted spectra do not measure
  population prevalence. See [cohorts](DR4_REFERENCE_COHORTS.md).
* Actual MoM-z14 spectrum: source ID, slit coordinates, spatial query and SHA256
  agree. Of 473 samples, 467 have finite wavelength/flux and positive finite
  errors. Signed bin SNR is a stored-value diagnostic, not line significance.
  No new redshift, abundance or galaxy-age inference was made. See
  [spectrum report](../research_output/mom_z14_spectrum_reference.md).

The nitrogen question concerns an inferred abundance ratio, not a direct clock
for the whole galaxy. [Source notes](RESEARCH_SOURCES.md) pin the published
MoM-z14 version and distinguish observational line values from photoionization
and stellar-yield hypotheses.

## Reproduce

```bash
python -m pip install -r requirements-dev.txt
python scripts/quality_gate.py
python -m data_pipeline.research_sources validate
python -m discovery.validation_audit --help
python -m discovery.external_psf_stress --help
python -m data_pipeline.reference_cohorts data_sources/pilot/jades_dr4_reference.csv --output /tmp/dr4-cohorts.json
```

The source manifest and acquisition receipts pin actual inputs. Spectrum and PSF
experiments verify hashes before reading values. No provider keys or paid LLM
calls are required for these checks. Final combined suite: **202 passed, 2
explicit archive-dependent skips**. Lint, targeted type checking and offline CI
are enabled. Agent dollar budgets are enforced after each response and may
overshoot by one bounded completion.

## Next experiments

1. Provision the original images and verify astrometry against external sources.
   Rerun detection and calibrated photometry; report exploratory proposals
   separately from dropout survivors. Saved proposal catalogs are not discoveries.
2. Freeze the classifier and evaluate real JWSTSTARS stars across held-out
   fields/visits, then known JADES sources with observation groups kept together.
   Quantify detection, classifier retention and full-chain recovery separately.
3. Measure PSF aperture corrections and correlated drizzle/background noise
   before treating cross-band colors or faint upper limits as precision evidence.
4. Fit MoM-z14's continuum and UV lines with instrumental resolution, explicit
   extraction-quality masks, covariance and alternative extractions. Propagate
   ionization/density assumptions before comparing WR, massive-star and other
   nitrogen-yield models. The generic diagnostic reader currently checks stored
   values and units; it does not implement future DQ/extraction masks.

Independent review reproduced the saved spectral and cohort diagnostics exactly.
There is no new astrophysical-discovery claim in this baseline.
