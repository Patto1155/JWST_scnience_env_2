# Ramp Diagnostics

Classifying detector events from the up-the-ramp reads instead of from
shape. An optical source accumulates charge steadily across every group;
a cosmic ray deposits it between two reads and stops. The statistic is the
fraction of total signal arriving in the largest single increment, which
Statistic: `jump_significance`. The raw increment fraction sits near
**0.25** for steady accumulation and approaches 1
for an instantaneous deposition; the jump significance is that deviation
expressed in sigma against the per-pixel read-noise and Poisson budget, so it
does not grow simply because a source is bright.

Exposure: `jw01180026001_05201_00003_nrcalong_`

- Sources with usable unsaturated ramps and a repeat-exposure label: **395** (342 real, 53 artifact)
- Median statistic, real sources: **2.810**
- Median statistic, artifacts: **49.928**
- ROC AUC against the repeat-exposure truth: **0.920**

## Does it preferentially reject compact sources? (threshold 5.0)

This is the question the morphology classifier failed. A ramp-based cut
never sees the shape, so its false-rejection rate should not depend on it.

| population | real | artifact | false rejection | artifact completeness |
| --- | ---: | ---: | ---: | ---: |
| compact (FWHM < 2 px) | 5 | 44 | 100.0% | 100.0% |
| PSF-scale (2 - 3.5 px) | 47 | 7 | 55.3% | 100.0% |
| extended (>= 3.5 px) | 290 | 2 | 24.8% | 100.0% |
| faint (S/N < 10) | 4 | 1 | 75.0% | 100.0% |
| moderate (S/N 10-30) | 58 | 7 | 60.3% | 100.0% |
| bright (S/N >= 30) | 280 | 45 | 23.2% | 100.0% |

Overall: false rejection 30.1%, artifact completeness 100.0%.

## Limits

- Needs `_uncal` ramps, which are ~50 MB per exposure and are not part of
  the products this pipeline otherwise uses.
- Saturated pixels carry no ramp information; a source saturating in its
  first groups also goes flat and is excluded rather than judged.
- Measured on one NIRCam long-wave exposure with NGROUPS=5. More groups
  give a sharper statistic; two would give none.
