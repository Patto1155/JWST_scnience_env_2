# Single-Image Artifact Classifier

Fitted to the repeat-exposure truth set from
`artifact_characterization.py`. The point is to reject detector artifacts
in images that have **no repeat coverage** - which is every band this
pipeline actually selects candidates in.

- Training rows: **5113** (718 artifacts, 4395 real sources)
- Filters: F277W, F356W
- Cross-validated ROC AUC: **0.981**

## Operating points (5-fold, out-of-sample)

| threshold | flagged | artifact purity | artifact completeness | real sources lost |
| ---: | ---: | ---: | ---: | ---: |
| 0.50 | 629 | 0.930 | 0.815 | 44 (1.0%) |
| 0.70 | 548 | 0.936 | 0.714 | 35 (0.8%) |
| 0.90 | 422 | 0.948 | 0.557 | 22 (0.5%) |
| 0.95 | 351 | 0.949 | 0.464 | 18 (0.4%) |

## Cross-filter transfer

Fitted on one filter and scored on the other. This is the closest proxy
available for applying the model to F444W, where no repeat pair exists.

| trained on | tested on | ROC AUC | purity @0.9 | completeness @0.9 |
| --- | --- | ---: | ---: | ---: |
| F356W | F277W | 0.981 | 0.964 | 0.588 |
| F277W | F356W | 0.980 | 0.937 | 0.500 |

## Coefficients

Positive weight pushes toward *artifact*. Features are standardized, so
magnitudes are comparable.

| feature | weight |
| --- | ---: |
| `psf_ratio` | -3.657 |
| `sharpness` | +3.583 |
| `log_area` | +2.362 |
| `ellipticity` | -0.159 |

## What this actually buys

At threshold 0.50, applied to a population with the
measured **14.8%** artifact
fraction, the surviving catalog is **3.1%**
artifacts - a 4.7x improvement, at the cost of
1.0% of real sources.

For a dropout search that is **~212
artifacts per genuine high-redshift source**, down from ~1200. That is a
large relative gain and still a hopeless absolute number. The classifier is
a mitigation for images that have no repeat coverage; it is not a substitute
for deep mosaics with cross-dither rejection, and nothing here makes
single-exposure dropout searching viable.


## Limits

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
