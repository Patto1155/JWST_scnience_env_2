# Single-Image Artifact Classifier

Fitted to the repeat-exposure truth set from
`artifact_characterization.py`. The point is to reject detector artifacts
in images that have **no repeat coverage** - which is every band this
pipeline actually selects candidates in.

- Training rows: **6433** (718 artifacts, 5715 real sources, of which 1320 are injected point sources)
- Filters: F277W, F356W, F444W
- Cross-validated ROC AUC: **0.971**

## Operating points (5-fold, out-of-sample)

| threshold | flagged | artifact purity | artifact completeness | real sources lost |
| ---: | ---: | ---: | ---: | ---: |
| 0.50 | 539 | 0.917 | 0.688 | 45 (0.8%) |
| 0.70 | 437 | 0.936 | 0.570 | 28 (0.5%) |
| 0.90 | 328 | 0.933 | 0.426 | 22 (0.4%) |
| 0.95 | 274 | 0.934 | 0.357 | 18 (0.3%) |

## Cross-filter transfer

Fitted on one filter and scored on the other. This is the closest proxy
available for applying the model to F444W, where no repeat pair exists.

| trained on | tested on | ROC AUC | purity @0.9 | completeness @0.9 |
| --- | --- | ---: | ---: | ---: |
| F356W, F444W | F277W | 0.964 | 0.944 | 0.467 |
| F277W, F444W | F356W | 0.969 | 0.922 | 0.353 |
| F277W, F356W | F444W | not estimable | not estimable | not estimable |

## Coefficients

Positive weight pushes toward *artifact*. Features are standardized, so
magnitudes are comparable.

| feature | weight |
| --- | ---: |
| `psf_ratio` | -5.914 |
| `sharpness` | +3.266 |
| `log_area` | +3.750 |
| `ellipticity` | +0.933 |

## What this actually buys

At threshold 0.50, applied to a population with the
measured **14.8%** artifact
fraction, the surviving catalog is **5.2%**
artifacts - a 2.9x improvement, at the cost of
0.8% of real sources.

For a dropout search that is **~357
artifacts per genuine high-redshift source**, down from ~1200. That is a
large relative gain and still a hopeless absolute number. The classifier is
a mitigation for images that have no repeat coverage; it is not a substitute
for deep mosaics with cross-dither rejection, and nothing here makes
single-exposure dropout searching viable.


## Limits

- Sky-group folds and held-out visits are internal diagnostic checks.
  Shared fields or injection generators/PSFs are not independent external
  validation. Legacy training rows lack complete provenance; use the gate
  in `validation_metrics.py` before claiming independent performance.
- ROC AUC requires both classes. Real-only synthetic-source tests can
  estimate rejection, but their AUC is explicitly not estimable.
- Fitted on NIRCam long-wave imaging only. `psf_ratio` normalizes by the
  diffraction-limited FWHM so the model transfers across wavelength, but
  short-wave detectors sample the PSF differently and should be validated
  separately before the model is trusted there.
- The truth labels come from a 5.65-9.55 hour baseline. That is long
  enough to be certain about cosmic rays and far too short to distinguish
  a genuine fast transient from an artifact. The model learns *detector
  event*, not *not astrophysical*.
- It is a rejector, not a detector. A high score is grounds to drop a
  candidate; a low score is not evidence that a source is real.
