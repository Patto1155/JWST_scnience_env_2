# An executed, versioned photoionization fit with an explicit N IV] coverage gap

Building on the merged atomic map, this experiment runs the actual **Cue v0.1**
trained photoionization emulator and fits four measured UV groups with their
full covariance. It resolves software/data access; it does not establish an
elemental abundance or identify an enrichment mechanism.

## Inputs and replay

```bash
python -m data_pipeline.atomic_inputs /path/to/atomic-inputs --cue
python -m tools.jwst.cue_grid /path/to/atomic-inputs/cue-v0.1.zip
JWST_CUE_ARCHIVE=/path/to/atomic-inputs/cue-v0.1.zip \
  python -m pytest tests/test_atomic_grid.py tests/test_cue_grid.py -q
```

The immutable [Cue v0.1 archive](https://doi.org/10.5281/zenodo.11118643) is
**31,885,220 bytes**, SHA256
`8c1089f4d7407c57558e14b0f26028379ca14d555a94f873834c767f3cc5abfb`,
also matching the publisher MD5 `370380e7e685acfb03861bfb82650301`.
With PyNeb, the bounded atomic acquisition totals **60,636,277 bytes** of its
100 MiB allocation. Each actually used member has a separate hash in the output.

The original package initializes TensorFlow even for its NumPy path. Our decoder
loads only numeric arrays and inert state containers through a narrow whitelist;
it rejects other pickle globals. No TensorFlow/dill installation or shared
environment modification occurs. Inference reproduces the author's `nn.py`
NumPy routine, PCA inverse transform and output scaling. An independent check
executes that pinned author arithmetic on every grid point and all five networks;
predictions agree within 1e-13. This is numerical implementation validation,
not astrophysical calibration.

The public emulator's default FSPS projection removes newly added UV lines.
We retain the full wavelength-tagged network outputs, including C IV and N III],
instead of applying that 128-line compatibility projection. Every required line
must be present; missing lines cause an error rather than a zero prediction.

## What is modeled

[Li et al.](https://arxiv.org/html/2405.04598v1) describe a CLOUDY 22.00 emulator
with a single spherical H II region, constant hydrogen density and fixed inner
radius 10^19 cm. Seven piecewise ionizing-spectrum parameters describe incident
light. Abundance ratios, metallicity and ionization parameter are variable;
helium follows a metallicity relation, and dust depletion is fixed.

Critically, **N IV] is not emulated**. The [MoM paper v2 §3.2.3](https://arxiv.org/html/2505.11263v2)
also excludes it from Cue fitting. Our fit therefore uses C IV, He II+O III],
N III] and C III] only. The covariance is the marginal four-group submatrix,
not a covariance conditioned on a fake N IV] model. The He/O sum is physically
predicted, but the observed blend does not independently separate either element.

The grid consists of **2,025 deterministic model choices**: three explicit
piecewise-spectrum controls, logU=-3/-2/-1, log nH=2/3/4, native Cue O/H
parameters -2/-1.3/-0.6, and five points each in native N/O and C/O spanning
-1 to log10(5.4). The controls are not classified as stars, AGNs or polluters.
A nonnegative common flux normalization is profiled analytically using the
complete covariance. No observational EW, continuum or photon-budget likelihood
is added. Emulator/geometry error and source-specific LSF calibration are absent.
Density-dependent multiplet proportions also need a spectrum-template refit:
the present group flux likelihood retains the earlier equal-weight templates.

## Actual fit and a useful negative result

| Input spectral scenario | Best four-group chi² | Grid points with delta chi² ≤3.841 | Native Cue N/O−C/O parameter range in that set |
|---|---:|---:|---|
| Nominal illuminated slit | 0.09195 | 157 / 2,025 | -1.50 to 1.2324 |
| Generic point-source LSF | 0.41089 | 126 / 2,025 | -1.50 to 1.50 |

These sets are an **illustrative sensitivity threshold**, not a confidence region,
posterior, probability or calibrated significance test. We vary too many physical
parameters relative to four group measurements to assign a residual number of
physical degrees of freedom. Their low best chi² values do not validate the model.
About **79%/87%** of selected points touch sampled U/density/abundance edges.

The four-group data allow widely different nitrogen/carbon model parameters.
The brighter N IV] observation carries information that this version cannot
use. Thus an ionic enhancement from the four-line PyNeb transformation and a
wide four-group Cue result are compatible: they are different likelihoods and
different physical assumptions. Treating Cue as a joint fit of all five groups,
or treating a low chi² as a unique enrichment diagnosis, fails this explicit
coverage test. The published Cue posterior additionally uses its own EWs and
sampling assumptions; our sparse grid does not reproduce that posterior.

Cue adopts solar log(N/O)=-0.88 and log(C/O)=-0.37, giving log(N/C)=-0.51.
Its N/C depletion difference is +0.08 dex. Relative to MoM's -0.60 convention,
the native parameter difference would shift by **+0.09 dex for undepleted**
ratios or **+0.17 dex for gas-phase** ratios under those assumptions. We retain
native parameters and record both mappings, rather than silently mixing solar
or depletion conventions.

`research_output/mom_cue_grid_fit.json` pins input-spectrum bytes, exact archive
and member hashes, parameter values, predicted-grid byte hash, ranked points,
flux/covariance, boundaries, omissions and inference guards. Large author inputs
remain outside git. CLI `--spectrum` also accepts the independent native-nod
likelihood schema; subsequent frozen native results are kept in separate files.

The next substantive model dependency is a photoionization calculation including
N IV] and calibrated multiplet/LSF templates, with ionizing-spectrum, depletion,
geometry and continuum/EW sensitivity. Higher-resolution N/C density multiplets,
separated He II/O III] and independent line transfer constraints would improve
identifiability more than a denser version of this underconstrained grid.
