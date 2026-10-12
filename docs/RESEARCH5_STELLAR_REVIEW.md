# Independent KIC 8164262 epoch review

**Actual TESS data retain the known pulsation in 2024; they do not establish a
new physical amplitude change.** The apparent decline in one raw sector is
background/centroid-sensitive, and the small-aperture detrended measurements
remain similar across the two 2024 observing windows. These are conditional
aperture measurements, not intrinsic stellar-amplitude limits.

The independent implementation is `discovery/research5_stellar_review.py` and
the numerical receipt is `research_output/research5_stellar_review.json`.
It imports no author analysis. The reader decompresses and verifies all eight
original FITS body hashes and sizes from `research5_stellar_inputs.json`, then
checks TIC159649612, sector identity, and BJD-2457000/TDB time conventions.
The original light-curve bodies total 3,467,520 bytes; the reviewer acquired no
additional light curves. GOODS-N outcomes remain unopened.

## Actual remeasurement

The review uses the frozen 2.6184922/day frequency, 87.4549-day orbital period,
minimum-light reference BJD2455668.82920, quality zero, and the same
absolute wrapped orbital-phase mask of 0.04. It normalizes each flux column by
its median and fits sine/cosine plus independent quadratic trends in segments
separated by gaps over 0.5 day. Rank-revealing QR, normalized SVD diagnostics
and an independently computed projection operator replace the author's solver.
No phase-extremum or residual clipping was applied.

All available primary flux-column amplitudes agree with the author to better
than 3e-11 ppm. Actual quality-filtered sectors span 22.3–28.0 days, with
cadence-summed coverage from 8.6–26.5 days; the long interepoch gaps do not
provide continuous frequency resolution. The observations run from August
2019 through September 2024, with additional windows in 2021 and 2022.

The 2024 windows were combined independently using their actual timestamps,
retaining separate segment trends and per-sector median normalization:

| Flux measurement | Sectors 74/75, Jan–Feb 2024 | Sectors 81/82, Jul–Sep 2024 |
|---|---:|---:|
| Raw SAP | 763 ± 168 ppm | 519 ± 186 ppm |
| Default detrended | 734 ± 100 ppm | 685 ± 105 ppm |
| Small-aperture detrended | 598 ± 56 ppm | 607 ± 52 ppm |
| Large-aperture detrended | 726 ± 154 ppm | 650 ± 169 ppm |
| Systematics-removed intermediate | 718 ± 131 ppm | 529 ± 177 ppm |

All ± values above are **conditional white-residual errors**, not total
uncertainties or calibrated significance. The adjacent-sector baselines are
54.5 and 52.6 days. The small-aperture values are 597 and 606 ppm with linear
trends, and 594 and 599 ppm after additional background/centroid regressors.
Agreement among these fits supports this conditional measurement; it does not
calibrate the detrending transfer function or establish an intrinsic constant
amplitude.

Sector 82 raw SAP alone changes from 264 ± 277 ppm to 672 ± 187 ppm after
fixed linear background and centroid regressors. Its intermediate
systematics-removed flux similarly changes from 398 to 791 ppm. This is a
concrete sensitivity of the supposed raw decline to instrumental nuisance
modeling. Other raw sectors are also noisy, and half-sector coefficients can
disagree substantially. No new frequency was chosen to improve these fits.

## Window, sideband and product controls

The [Hambleton et al. primary paper](https://arxiv.org/pdf/1706.05051v2),
Table 5, lists the dominant mode and three unresolved nearby components at
2.61912, 2.61832 and 2.61901/day with amplitudes 15, 11 and 6 ppm. Their
phases use periastron BJD2455668.7898, distinct from the minimum-light reference.
For unknown phases the review computes the exact singular-value leakage
envelope through the actual sampling and fitting operator. Adopting these
published sideband amplitudes gives about 32 ppm per-sector leakage. This is
a fixed-amplitude sampling control, not a calibrated upper bound on future
sideband evolution or the Kepler-to-TESS amplitude transfer.

The actual sampling-window moduli at the nearby frequency separations exceed
0.9994 in each sector: the sidebands are unresolved in these short windows.
Adjacent orbital harmonics are also strongly correlated with the primary
within a sector. Allowing unconstrained 228/230 terms increases the primary
errors substantially; those fitted amplitudes are sensitivity diagnostics,
not separate mode detections.

Forward-integrated 1000 ppm synthetic signals recover 1000 ppm after inverse
sinc correction. Three focused controls pass: recovery with gaps and trends,
handling isolated one-point segments, and the analytic sideband envelope.
They validate the numerical measurement convention, not the source physics.

The [official QLP release notes](https://tess.mit.edu/qlp-update/) identify the
post-sector-56 `DET_FLUX` and `SYS_RM_FLUX` products and the corrected v02
timestamps for sectors 74–79. The selected 74/75 inputs are v02. The review
uses every available flux column, preserving its actual name. Changes in
detrending products are not missing observations or independent reductions.
No `CROWDSAP` or `FLFRCSAP` value is provided in these products. Aperture
variants use shared photons; no independent source-dilution calibration is
claimed. The legacy/new processing distinction also prevents treating this
whole series as one uniformly calibrated amplitude history.

## Decision and reproduction

The retained product is a measured TESS epoch extension of the known mode.
The predefined repeated large-change screen is not supported by these data.
There is no sufficiently discriminating remaining discrepancy to justify pixel
downloads for this bounded pilot. No tidal-evolution detection, intrinsic
amplitude-evolution bound, or proof of novelty is inferred from the white errors.

With the exact research lock and one BLAS thread:

```bash
python -m discovery.research5_stellar_review \
  --manifest research_output/research5_stellar_inputs.json \
  --output /tmp/research5-stellar-review.json
python -m pytest tests/test_research5_stellar_review.py -q
```

The independent literature PDF retrieval used 1,563,787 bytes, SHA256
`00a4e738489a755e8c8592588c73946cf311c0137a5a9f5a495314056b1727aa`.
Search-service bandwidth is not measured. No paid service or external-person
contact was used.
