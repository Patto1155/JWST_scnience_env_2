# Independent MoM-z14 native-column reduction

9 October 2026. This experiment closes the public-data extraction blocker; it
does **not** recreate the author's unavailable PIXTAB or calibrate a
source-specific spectral LSF. Its conditional uncertainties cannot establish an
elemental abundance, polluter or independent line discovery.

## What was actually reduced

All nine pinned official CAL files were reverified against the existing native
inventory, including source position, size and SHA256. The embedded calibration
logs identify the two other RATE exposures used as each nod's background, within
each of three VISITGRPs. These CAL products already have `S_BKDSUB=COMPLETE`:
**another nod subtraction would be wrong**. Nod products within a group reuse
raw exposures. There are three groups with disjoint RATE inputs, not nine
independent spectra; shared references across groups are still unmeasured.

The official source is `EXTENDED`, `PTHLOSS=UNIFORM`, `BARSHDW=T`, `BUNIT=MJy/sr`.
Under the point-source hypothesis the conversion is

`SCI × PIXAR_SR × 1e12 × PATHLOSS_UN × BARSHADOW / PATHLOSS_PS`.

This restores the existing uniform pathloss and extended-only barshadow
corrections before applying the stored source-position point correction once.
The extraction operates in a common pre-point-pathloss calibration and includes
the appropriate point throughput in each positive and negative nod profile.
No second sky subtraction is made. A constant/linear **residual background** is
a fitted nuisance, not a reapplication of the original background subtraction.
The solid angle is the official nominal pixel value, not a new area-map
calibration. Point throughput, finite source extent, barshadow and spatial
illumination remain reduction assumptions.

The author's versioned SLITS base polynomial supplies a geometry seed, transformed
between the old 509-column and current 423-column cutouts. The trace offset and
Gaussian cross-dispersion width are independently refit using **3.35–4.45 µm**
continuum only: best offset **+0.20 native pixels**, sigma **0.80 pixels**.
Conditional Δχ²=2.30 grid envelopes are offset 0.20–0.30 and sigma 0.75–0.85;
these are not independent calibration confidence intervals. A constant pixel
width is transported to the UV; wavelength-dependent spatial structure remains
an explicit limitation. Negative ghosts from both background nods enter the
profile. Continuum trace measurements do not measure illumination along the
dispersion direction or the source's spectral LSF.

Seventy unchanged native UV columns in 2.15–3.20 µm are fit jointly across nine
exposures, preserving each exposure's wavelength grid and full-grid bin edges.
Finite science/error/wavelength/pathloss/barshadow and positive error, with
neither DO_NOT_USE nor SATURATED, define quality. All nods in a group use common
valid pixels. There is no flux/SNR-dependent rejection. Signed five-group line
fluxes and continuum are fit at fixed z=14.44, intrinsic width zero, with the
existing nominal-slit and generic point Gaussian R curves and blend assumptions.
The nominal/generic R curves are sensitivities, not measured source-specific LSFs.

## Shared and empirical noise

With mean subtraction of the other two nods, the mixing matrix has diagonal 1
and off-diagonal −1/2. Its SCI rank is two: it cannot reconstruct the missing
common background. Its squared-element variance matrix is invertible. However,
the exact diagonal relation `D_i=V_i+(V_j+V_k)/4` yields negative inferred raw
variances in **13/19/11 UV pixels** in groups 03/05/07. This is an observed
counterexample to exact variance demixing from incidence alone. Clipping,
calibration and variance terms need additional raw-stage information.

Failed pixels therefore receive an explicitly recorded nonnegative least-squares
variance reconciliation plus independent positive diagonal remainder, retaining
positive semidefinite covariance and avoiding underestimated supplied marginal
variances. Independent pre-subtraction rate pixels and linear background mixing
remain conditional assumptions. Extraction operators propagate that shared
pixel model into the source-amplitude covariance.

Blank controls exclude the union of all positive/negative traces by 2.5 pixels,
then remove each control row's UV-window mean. There are **305 shared control
pixels per group** (2,745 individual nod samples, not independent draws).
The pooled normalized variance is **2.22062**; leaving out one group gives
**2.17938–2.24683**, a sensitivity range, not a coverage-calibrated interval.
Same-pixel observed nod correlations range **−0.57370 to −0.38507**, consistent
with strong shared subtraction. The extracted source amplitudes instead have
conditional positive correlations **+0.21035 to +0.28803**, because their spatial
operators differ. Assigning the pixel correlation directly to line fluxes is wrong.

Measured spectral lag 1/2/3 correlations are **0.04688/0.04356/0.00821** from
2,691/2,637/2,583 paired control samples. A Bartlett-tapered stationary kernel,
with explicit PSD guard, transports these correlations to the source extraction.
Measured spatial lag 1/2/3 correlations are **−0.01038/0.09086/0.10947** from
1,485/819/189 pairs. They are recorded but **not propagated in this first fit**;
especially the last lag has few spatial placements. Spatial covariance, tail
calibration and common inter-group reference systematics remain next work.
The empirical transport is an estimated nuisance scenario, not the true source
covariance or a calibrated posterior. Source Poisson and sky variance cannot be
fully separated from these already subtracted products.

## Results and independent subsets

All fluxes below are 10⁻²⁰ erg s⁻¹ cm⁻². Errors are conditional one-sigma GLS
standard errors, not separately calibrated detection significances.

| Treatment | N IV] | C IV | He II+O III] | N III] | C III] |
|---|---:|---:|---:|---:|---:|
| Nominal R; shared formal variance | 27.30±8.92 | 21.68±7.79 | 23.14±8.29 | 5.39±5.69 | 17.33±4.87 |
| Generic point R; shared formal variance | 17.10±5.98 | 14.44±5.26 | 16.14±6.46 | 4.66±4.20 | 12.72±3.51 |
| Nominal R; empirical off-trace transport | 27.43±13.61 | 22.20±11.90 | 23.72±12.83 | 5.37±8.73 | 17.51±7.46 |
| Generic point R; empirical off-trace transport | 16.76±8.94 | 14.52±7.88 | 16.08±9.81 | 4.77±6.34 | 12.67±5.28 |

The last fit has χ²=543.61 for 623 conditional degrees of freedom, versus
1204.52/623 under the shared formal model. Off-trace transport widens uncertainty
without selecting an LSF or proving that every covariance component is right.
The summed nitrogen/carbon **line-flux** ratio is **0.79179**, conditional 95%
Fieller set **[−0.00677,2.88294]**. Nominal R gives **0.82586 [0.00954,2.93418]**.
The former admits a zero numerator. Negative fitted amplitudes/ratio endpoints
remain in the Gaussian fit; physical positivity would require an explicit prior.

The generic-point, empirical-transport group split gives N IV] fluxes
**45.34±15.76 / 5.58±15.33 / 0.38±15.40** for groups 03/05/07. Group 03 carries
much of the conditional N IV] support; the other individual groups are shallow.
The five-flux heterogeneity χ² is **12.4459 for 10 conditional degrees of
freedom** with separate group continua. These group fluctuations do not refute
a common weak source. Nod splits are also saved, with their shared-background
dependence explicitly retained; they are not independent confirmations.

Conditional point-R ratio sensitivity spans **0.512–1.008** for assumed ±0.25
native-pixel wavelength shifts. Spatial sigma 0.65/0.95 gives 0.796/0.769;
trace offsets 0.10/0.30 give 0.752/0.831; a constant rather than linear residual
background gives 0.681. These are stated perturbations, not a marginalized
calibration posterior. Their source/profile/pathloss/covariance model differs
from the author coadd, whose earlier point-R fit was N IV] 40.40±10.82 and
line-flux ratio 1.050. The independent reduction lowers fitted UV flux and weakens
conditional nitrogen support. It does not identify which reduction is correct,
reproduce the publication's likelihood, or invalidate its elemental-abundance
analysis.

## Reproduce and validate

```bash
python -m data_pipeline.mom_native_batch \
  --spectrum data_sources/pilot/mom_z14_dja_v4.spec.fits \
  --output /tmp/mom-native --report /tmp/mom-native-batch.json
python -m tools.jwst.native_reduction --native-dir /tmp/mom-native \
  --output research_output/mom_native_reduction.json
python -m tools.jwst.native_reduction \
  --replay-report research_output/mom_native_reduction.json \
  --output /tmp/mom-native-replay.json
python -m pytest tests/test_mom_native_reduction.py tests/test_line_sensitivity.py \
  tests/test_point_resolution.py tests/test_mom_native_batch.py
```

The compact NPZ stores derived amplitudes, full native wavelengths/masks, shared
column covariance and the spectral transport kernel. Its receipt is in the
JSON. Four main flux/covariance fits replay without raw SCI pixels; this is a
numerical audit, not a pixel reduction or calibration check. Group/nod splits
and extraction sensitivities require the original pinned files. Seven synthetic
oracles independently check units/correction order, unequal raw-noise variance
algebra, 120,000-draw covariance propagation, signed-ghost extraction with a
background slope, finite aperture support, failed-demix reconciliation, and
known signed flux recovery with a masked column retaining original bin edges.

Primary calibration sources:

- [JWST 2.0 pathloss algorithm](https://jwst-pipeline.readthedocs.io/en/2.0.0/jwst/pathloss/description.html)
- [JWST photometric units and pixel area](https://jwst-pipeline.readthedocs.io/en/stable/jwst/photom/description.html)
- [JWST background calibration distinctions](https://jwst-pipeline.readthedocs.io/en/latest/jwst/master_background/description.html)
- [Exact author base-trace implementation](https://github.com/gbrammer/msaexp/blob/e2b237b/msaexp/slit_combine.py)

The strongest next experiment is empirical **spatial** covariance propagation
and extraction controls on off-source locations with the same source operator,
followed by source-specific wavelength/dispersion calibration. Exact original
PIXTAB/contributor weights/optimized trace settings and a source-specific
dispersion LSF remain genuine external inputs. The native contributor incidence,
archive access, spatial trace refinement and stored point pathloss are resolved.
