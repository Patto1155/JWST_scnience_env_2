# Three RATE groups: shared calibration identifiability

10 October 2026. This extends the merged [336 physical spectral fits](MOM_COMPOSED_SPECTRAL_ROUND.md)
at master `379ff35786aff31535335bbe7d1de114f91dd3c4`. It independently
reconstructs their original-wavelength, generic-point-resolution, empirical
row-plus-column likelihood at Te=20,000 K/ne=1,000 cm⁻³. N IV retains the version
2 total 1483+1486 doublet. Historical reports and contracts are unchanged.

## Declared experiment

**Question:** Can three independent RATE groups bound a globally shared
line-shaped systematic, and do held-out groups reject a common weak spectrum?

**Competing predictions:** Independent conditional noise should give nominal
Gaussian coverage. An omitted globally shared perturbation should cause
undercoverage while cancelling from group contrasts. A genuinely inconsistent
group should have a large held-out five-flux predictive residual.

**Expected gain:** Distinguish a useful exposure-consistency test from a
calibration measurement. Quantify a limitation that larger conditional grids
cannot fix, and identify the need for a calibrator or an independently constrained
source/reference response.

**Budget/stopping:** No downloads; reuse pinned compact arrays. Cap computation
at 30 seconds and 100,000 paired Gaussian draws per prescribed scale. Stop when
the independent normal-equation fit matches the frozen production QR fit, group
contrasts cancel the common mode numerically, and coverage agrees with closed
form. The single-thread numerical calculation took approximately 0.2 seconds;
import/runtime overhead was approximately 2 seconds.

## Actual conditional group diagnostics

The independent likelihood reproduces the reference N IV total flux
**13.6996±9.0071 ×10⁻²⁰ erg s⁻¹ cm⁻²**. Maximum differences versus the frozen
physical-v2 reference are 1.77×10⁻¹⁰ in flux, 1.16×10⁻⁹ in covariance entries,
and 3.50×10⁻¹¹ in χ². These tiny differences arise from independently computing
the Gaussian FWHM conversion rather than using the production rounded constant.

Each group is fit with its own continuum and compared against the remaining two
groups, also fit with their own continuum. The signed five-flux difference uses
the sum of their conditional covariance matrices; cross-group measurement-noise
blocks are zero under the existing native model.

| Held-out group | N IV total flux ± conditional sigma | Five-flux predictive χ²/5 dof | Conditional Gaussian tail probability |
|---|---:|---:|---:|
| 03 | 38.05±15.86 | 5.248 | 0.386 |
| 05 | 3.10±15.42 | 4.521 | 0.477 |
| 07 | 0.76±15.53 | 6.322 | 0.276 |

Group 03 carries most of the conditional nitrogen support. These held-out tests
do not reject a common weak five-line spectrum under the declared covariance.
The three contrasts overlap in their training data and are not independent
tests or three independent confirmations. Their conditional tail probabilities
do not validate covariance tails or source calibration.

## What group agreement cannot measure

Inject one **prescribed globally shared N IV-template amplitude** through the
native spectral design. Its fitted line-flux response is identical in all three
groups; both the source residual and group-versus-training contrast remain
unchanged (maximum residual response 1.74×10⁻¹⁸ µJy; group contrast response
below 10⁻¹⁴ flux units). The contrast matrix has rank two and annihilates the
global common mode. That mode's information from group contrasts is exactly zero.

This is an exact identifiability counterexample: a global additive residual
aligned with a line response is confounded with the astrophysical line flux.
It does **not** show that this contaminant exists, quantify its amplitude, or
assign an empirical probability to it. A grey multiplicative calibration error
can cancel in a ratio; the demonstrated differential line-like mode need not.
Off-source residual controls do not measure source-specific pathloss, wavelength
assignment or LSF, and therefore cannot eliminate every such mode.

Under a deliberately prescribed zero-mean Gaussian shared amplitude, known-spectrum
linear injections give the following exact coverage of a nominal signed N IV
95% interval if the shared term is omitted:

| Assumed shared sigma / conditional sigma | Exact coverage if omitted | Simulated coverage (100,000 draws) |
|---|---:|---:|
| 0 | 95.00% | 95.03% |
| 0.5 | 92.04% | 92.20% |
| 1 | 83.42% | 83.57% |
| 2 | 61.93% | 61.98% |

Including the assumed term in quadrature gives exact 95% coverage and simulated
95.03–95.14%. The simulation uses the exact GLS-projected independent-noise draw
plus one global shared draw; drawing that amplitude independently per exposure
would instead simulate another model. This is a known-distribution operator test,
not detector-pixel injection, an empirical prior, or elemental-abundance coverage.

Even an idealized equal-variance, independent Gaussian **group-varying**
systematic has only two variance degrees of freedom with three groups: its
95% population-sigma interval is 0.521–6.285 times the sample sigma. This
illustration is not applied to the actual heteroscedastic group estimates and
does not bound the completely shared mode. The existing leave-one-control-group
off-source variance range 2.179–2.247 likewise is a sensitivity range rather
than a coverage-calibrated global-systematics interval.

## Reproduce and validate

```bash
OPENBLAS_NUM_THREADS=1 python -m tools.jwst.shared_systematics \
  --output research_output/mom_shared_systematics_v1.json
python -m pytest tests/test_shared_systematics.py \
  tests/test_mom_native_reduction.py tests/test_mom_native_spatial_covariance.py \
  tests/test_composed_spectral_refit.py
```

The artifact records input hashes, all group estimates/covariances, assumed
coverage scales, RNG seed, exact-versus-simulated probabilities and runtime.
24 focused tests passed. Independent algebra controls cover a heteroscedastic
weighted mean, signed known-spectrum recovery, low-rank covariance propagation,
common-mode nullspace, coverage closed form and the two-degree variance interval.

This is numerical artifact reproduction. It does not claim raw-pixel
reproduction, empirical source calibration, a new line detection or revised
elemental N/C. The scientific conclusion changes by making the calibration
limitation quantitative: exposure consistency cannot supply a finite bound on
all shared source-response uncertainties. A constrained calibration response,
an independently calibrated spectrum, or an observation that separates the
line family is more informative than enlarging an uncalibrated scenario grid.
