# Native UV refits with physical ionic multiplet weights

This experiment resolves the mismatch between density-dependent PyNeb UV
multiplet emissivities and the earlier fixed equal N III]/C III] spectral
templates. Every one of the 28 common temperature/density cells gets a **fresh
five-group spectral fit and 5×5 line-flux covariance** in each of four native
resolution/noise scenarios: 112 fits in total. The source-amplitude data and
measured noise covariance remain those of the frozen native reconstruction.
This is an accessible forward-model correction, not an independent observation
or a temperature/density measurement.

## Reproduction and exact inputs

The experiment branches from merged spatial-covariance revision `05d6191`.
Its original four likelihoods and compact replay are unchanged; the spatial
covariance alternatives are a separate sensitivity and are not combined here.

```bash
# Optional regeneration: separate verified PyNeb1.1.32 runtime, no shared-env install.
PYTHONPATH=/path/to/atomic-inputs/pyneb-runtime python -m tools.jwst.multiplet_refit \
  --generate-components research_output/mom_multiplet_components.json
# Replay requires only the committed component grid and compact native NPZ.
python -m tools.jwst.multiplet_refit
python -m pytest tests/test_multiplet_refit.py tests/test_mom_native_reduction.py \
  tests/test_line_sensitivity.py -q
```

The native report is SHA256
`88e3cdbf5b7759eaad84dc21ead0974c38f392292d71ce605fa0f5b5951637ec`;
the compact NPZ is
`9412f52afbed589777cf55ad27ca2e93065cb4003be4990debc17503fe097027`.
The atomic grid is
`b3923cd0084950e4b73a89a20848785188fc484287140c9f4d2720af43a5dc8d`;
the newly executed component grid is
`cbd151a8274979f9378b0ce485f23793ca77ccc9eb1df8eae391012691d3fb8e`.
These are independent experiment pins, so an internally consistent replacement
of component weights/totals cannot silently become this experiment. Generation
checks all 11 atomic member identities from the publisher-verified PyNeb wheel
and verifies that the individual ionic emissivities sum to the merged grid.
The result includes the resolution receipts and SHA256 of each software module.

`line_matrix(..., components=...)` accepts five groups of vacuum wavelengths
and nonnegative weights, normalized per group. Invalid wavelength/weight arrays
and conflicting named blend rewrites are rejected. `fit_native` forwards the
components on the **full native grid before quality selection**, preserving bin
edges around missing pixels. `load_native_replay` returns actual wavelength,
mask, trace and derived amplitude/covariance arrays; it supplies no SCI pixels.
The default-template replay reproduced all four saved flux/covariance products
exactly on this runtime before extending the model.

## Physical weights and explicit assumptions

N III], C III] and C IV have the actual pinned per-component PyNeb emissivities
at each fixed Te/ne, normalized within their single-ion groups. For example,
at Te=20,000 K, the C III]1907 fraction changes from 0.606 at ne=100 cm^-3
to 0.317 at ne=100,000 cm^-3. N III]1749.674's fraction changes from 0.330
to 0.497. Equal weights are therefore not a physical description of those
doublet/multiplet components, even where the prism cannot distinguish them well.
Every wavelength, individual emissivity and normalized weight is saved in
`mom_multiplet_components.json`.

The merged atomic contract supplies **N IV]1486 only**. This round therefore
keeps 1483 absent and labels that omission explicitly. He II/O III] retains the
equal three-line blend template: cross-element emissivities cannot determine
the unknown helium/oxygen ionic mixture. C IV remains optically thin and
collisionally excited; resonant transfer, stellar emission and absorption are
not calibrated. Redshift=14.44, zero intrinsic line width, source geometry,
pathloss, original native wavelengths and resolution-family assumptions remain
fixed. Both instrumental curves are generic sensitivities rather than measured
source-specific LSF posteriors.

## Executed conditional ionic results

At common Te=20,000 K and ne=1,000 cm^-3:

| Native spectral scenario | Refitted two-stage ionic N/C | Conditional Gaussian 95% Fieller set |
|---|---:|---|
| Nominal/shared formal | 7.1913 | [2.6980,14.6219] |
| Point/shared formal | 6.5422 | [2.3214,13.5128] |
| Nominal/empirical off-trace transport | 7.1092 | [0.4523,23.2347] |
| Point/empirical off-trace transport | 6.4509 | [0.2601,21.1594] |

The previous point/empirical fixed-template map was
6.4611 [0.1460,21.7078]. Physical multiplet weighting changes the point estimate
little in this reference cell. Across the full prescribed grid, its central
ionic log(N/C), relative to solar log(N/C)=-0.60, spans **1.260–1.768 dex**.
That is a sensitivity span, not a confidence interval. **Three** of its 28
conditional Fieller sets still cross zero; the lowest lower endpoint is -0.149.
Signed endpoints are retained rather than clipped or logged as abundances.

| Scenario | Largest line-flux change in its old conditional sigma units | Largest fractional change in a line's conditional sigma |
|---|---:|---:|
| Nominal/shared formal | 0.070 | 1.14% |
| Point/shared formal | 0.225 | 3.48% |
| Nominal/empirical transport | 0.050 | 1.20% |
| Point/empirical transport | 0.162 | 3.67% |

The largest absolute line-flux change over all 112 fits is 0.857 in units of
1e-20 erg s^-1 cm^-2. New covariances are numerically distinct; they were not
copied from fixed-template fits. This rules out physical multiplet weights as
a large correction within the two assumed prism-resolution families and this
fixed geometry/noise model. It does not rule out density effects in a calibrated
higher-resolution spectrum.

## Validation and remaining inference

Independent finely sampled Gaussian quadrature validates the bin-integrated
provider and recovers signed synthetic fluxes through masked full-grid bins.
A separate normal-matrix calculation validates the freshly fitted covariance.
An intentionally wrong multiplet template biases that resolved synthetic
spectrum and cannot reuse its covariance. Other controls reject malformed
components, unknown He/O mixture substitutions, and internally consistent
component-file forgeries; all 112 saved ionic projections are checked against
their **own cell-specific** spectral covariance.

The elemental map still requires
N/C = observed-two-stage ionic N/C × f_C/f_N. Neither observed-stage fraction
is measured here. The [Cue model](MOM_CUE_PHOTOIONIZATION.md) omits N IV]
and cannot close that map. The [native chemistry follow-up](MOM_NATIVE_CHEMISTRY_FOLLOWUP.md)
and this correction share the observations, so their likelihoods are not
multiplied. No polluter, stellar population or cosmology is identified.

The next useful experiments are an N IV]1483-inclusive atomic/template contract,
explicit He/O mixture profiling, composition-aware N IV]-inclusive
photoionization predictions, and source-specific instrumental/line-transfer
calibration. Fresh model-coupled flux likelihoods here are reproducible inputs
for those experiments and for conditional enrichment predictions.
