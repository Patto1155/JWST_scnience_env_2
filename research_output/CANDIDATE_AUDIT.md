# Candidate Audit

Independent falsification pass over `highz_candidates.json`, computed from
the committed photometry blocks only. No FITS access, no pipeline rerun.

## Catalog-level result

- Candidates audited: **1732**
- Candidates where F090W was actually measured at the source position: **314** (18.1%)
- Candidates where F200W was actually measured: **365**
- Candidates with **both** F090W and F200W measured (the minimum for a
  two-color Lyman-break test): **0**
- Candidates whose blue and reference images sit on disjoint NIRCam
  modules (physically non-overlapping sky): **555**
- Candidates surviving every audit check: **0**

## Why candidates fail

| blocker | count |
| --- | ---: |
| `insufficient_bands_for_lyman_break_test` | 1732 |
| `blue_band_never_measured_at_source_position` | 1418 |
| `dropout_ratio_is_divide_by_unmeasured_zero` | 1416 |
| `mid_band_never_measured_at_source_position` | 1367 |
| `blue_and_reference_on_disjoint_nircam_modules` | 555 |
| `too_bright_for_high_redshift_interpretation` | 296 |

## Brightest blue-measured candidates, in physical units

`m_F444W` is an AB magnitude inside the r=3 px aperture after converting
MJy/sr to Jy with the long-wave pixel solid angle. `break` is the 2-sigma
lower limit on the F090W/F444W break after the short-wave/long-wave pixel
area correction the pipeline omits.

| target | source | m_F444W (r=3px) | break (mag) | pipeline status | verdict |
| --- | ---: | ---: | ---: | --- | --- |
| SMACS-J0723.3-7327 | 966 | 19.88 | -0.51 | reject | falsified |
| SMACS-J0723.3-7327 | 973 | 19.94 | -0.65 | reject | falsified |
| SMACS-J0723.3-7327 | 922 | 20.08 | 0.00 | reject | falsified |
| SMACS-J0723.3-7327 | 16 | 20.49 | 8.77 | keep | falsified |
| SMACS-J0723.3-7327 | 451 | 20.83 | 8.62 | keep | falsified |
| SMACS-J0723.3-7327 | 902 | 20.86 | -0.48 | reject | falsified |
| SMACS-J0723.3-7327 | 176 | 21.07 | 4.08 | review | falsified |
| SMACS-J0723.3-7327 | 1069 | 21.07 | -0.11 | reject | falsified |
| SMACS-J0723.3-7327 | 1119 | 21.35 | -0.87 | reject | falsified |
| SMACS-J0723.3-7327 | 1028 | 21.72 | 1.84 | keep | falsified |
| SMACS-J0723.3-7327 | 960 | 21.76 | 1.40 | reject | falsified |
| SMACS-J0723.3-7327 | 1031 | 21.79 | 2.29 | keep | falsified |
| SMACS-J0723.3-7327 | 1030 | 21.80 | 2.28 | keep | falsified |
| SMACS-J0723.3-7327 | 130 | 21.87 | 4.59 | review | falsified |
| SMACS-J0723.3-7327 | 1024 | 21.89 | 2.00 | review | falsified |
| SMACS-J0723.3-7327 | 909 | 21.91 | 0.31 | reject | falsified |
| SMACS-J0723.3-7327 | 1027 | 21.95 | 4.45 | keep | falsified |
| SMACS-J0723.3-7327 | 1026 | 21.99 | 1.51 | review | falsified |
| SMACS-J0723.3-7327 | 15 | 21.99 | 6.90 | keep | falsified |
| SMACS-J0723.3-7327 | 948 | 22.14 | -1.00 | reject | falsified |

For scale: the brightest spectroscopically confirmed z > 10 galaxies are
near m_AB ~ 26. Anything brighter than m_AB ~ 24.5 in F444W is
orders of magnitude too luminous for that interpretation and is far more
likely a low-redshift source, a star, or an uncorrected detector artifact.
