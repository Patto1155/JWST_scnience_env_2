# Ramp Diagnostics

Classifying detector events from the up-the-ramp reads instead of from
shape. An optical source accumulates charge steadily across every group;
a cosmic ray deposits it between two reads and stops. The statistic is the
fraction of total signal arriving in the largest single increment, which
sits near **0.25** for steady accumulation
and approaches 1 for an instantaneous deposition.

Exposure: `jw01180026001_05201_00003_nrcalong_`

- Sources with usable unsaturated ramps and a repeat-exposure label: **349** (316 real, 33 artifact)
- Median statistic, real sources: **0.281**
- Median statistic, artifacts: **0.694**
- ROC AUC against the repeat-exposure truth: **0.893**

## Does it preferentially reject compact sources? (threshold 0.6)

This is the question the morphology classifier failed. A ramp-based cut
never sees the shape, so its false-rejection rate should not depend on it.

| population | real | artifact | false rejection | artifact completeness |
| --- | ---: | ---: | ---: | ---: |
| compact (FWHM < 2 px) | 1 | 26 | 100.0% | 65.4% |
| PSF-scale (2 - 3.5 px) | 40 | 5 | 45.0% | 80.0% |
| extended (>= 3.5 px) | 275 | 2 | 11.6% | 100.0% |
| faint (S/N < 10) | 2 | 1 | 50.0% | 100.0% |
| moderate (S/N 10-30) | 50 | 5 | 48.0% | 80.0% |
| bright (S/N >= 30) | 264 | 27 | 9.8% | 66.7% |

Overall: false rejection 16.1%, artifact completeness 69.7%.

## The non-linearity bias

Raw `_uncal` ramps are not linearity-corrected. A pixel's response
flattens before hard saturation, which makes the first increment the
largest and mimics a jump. Compact sources concentrate flux into fewer
pixels, reach higher DN, and are hit hardest. Tightening the ceiling
shows how much of the bias that explains.

| DN ceiling | labelled | ROC AUC | false rej. compact | false rej. extended | artifact completeness |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 50000 | 386 | 0.867 | 54.0% | 14.9% | 72.2% |
| 30000 | 380 | 0.863 | 54.0% | 14.5% | 68.8% |
| 22000 | 372 | 0.865 | 53.1% | 13.2% | 67.4% |
| 18000 | 349 | 0.893 | 46.3% | 11.6% | 69.7% |
| 16000 | 321 | 0.933 | 33.3% | 10.3% | 87.5% |

Tightening the ceiling improves discrimination and roughly halves the
false-rejection rate for compact sources, so non-linearity is a real
part of the problem. It does not remove it: compact real sources are
still rejected about three times as often as extended ones at every
ceiling. **The ramp statistic as implemented here is therefore not yet
a safe replacement for the morphology cut.** It is better motivated -
it measures the physical accumulation history rather than a shape
correlate - but it needs the pipeline's non-linearity correction and a
per-pixel noise model before it can be used as a cut.

## Limits

- Needs `_uncal` ramps, which are ~50 MB per exposure and are not part of
  the products this pipeline otherwise uses.
- Saturated pixels carry no ramp information; a source saturating in its
  first groups also goes flat and is excluded rather than judged.
- Measured on one NIRCam long-wave exposure with NGROUPS=5. More groups
  give a sharper statistic; two would give none.
