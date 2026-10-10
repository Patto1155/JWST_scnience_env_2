# Native spectral measurement: independent reduction alternative, round 2

## Declared experiment, before execution

Question: do conditional nitrogen measurements depend more on the adopted noise,
unknown common calibration, redshift/intrinsic width/continuum, or the signed
spatial extraction? Can the three disjoint RATE groups predict each other under
the version 2 N IV doublet likelihood?

Competing predictions: a coherent weak source predicts consistent group fluxes
within correctly transported group noise. A group-specific disturbance predicts
poor held-out prediction. A mis-specified profile or continuum predicts biased
known-spectrum recovery even when its statistical covariance is internally
consistent. Shared calibration can shift all three groups without increasing
between-group scatter; group agreement cannot bound that error.

Expected information gain: expose influential measurement assumptions, establish
operator closure and conditional interval coverage, and test group prediction.
This cannot empirically calibrate a source-specific LSF or recover every donor
mask and old-calibration processing step in the published likelihood. The public
PIXTAB profile and weighting settings were recovered later in this round, as
documented below; those accessible settings are no longer an external dependency.

Inputs and budget: restore the nine previously pinned CALs (464,135,040 bytes,
separate from newly selected data). New acquisition allowance350MiB, with zero
new bytes initially required. Existing compact arrays and physical doublet grid
are pinned. Pilot seven one-factor model alternatives at Te20,000K/ne1,000cm^-3
under each of two generic resolution and original/DUMMY wavelength families;
keep each likelihood separate. No thermal/ionic-grid expansion. Bound simulation
at 4,000 Gaussian draws for each declared operator/noise scenario. Limit analysis
to the unchanged70 native UV columns; full wavelength grids determine bin edges.

Stopping criteria: stop after baseline reproduction,28 one-factor sensitivity
fits, three held-out group predictions per resolution, and operator injection
checks with documented model/mismatch coverage. Do not add larger parameter
scans unless these pilots identify a narrower discriminating question. Signed
fits and covariance remain available; no clipped flux or ratio endpoints.

Redshift14.40/14.44/14.48, intrinsic Gaussian FWHM0/300/1,000km/s, and continuum
Legendre orders0/1/2 are deliberate bounded nuisance perturbations, **not**
empirical calibration ranges or a prior distribution. The default physical
multiplets use the separate N IV total1483.321+1486.496 version2 contract.
He/O mixing and C IV transfer remain assumed. The assumed model covariance is
transported from the existing controls; simulation of it is an internal
calibration check, not empirical coverage of unknown source noise.

## Baseline reproduction and a failed forward-closure pilot

All nine pinned official CAL originals were restored and hash-verified; the
record is `research_output/research2_native_reproduction.json`. Their 464,135,040
bytes are restoration, with zero newly selected download bytes in this track.
A fresh actual-pixel native extraction reproduces every compact array exactly:
70-column fluxes, covariance blocks, spectral kernel, masks, full wavelengths,
trace, width and variance scale. Four old fitted flux/covariance results differ
by at most1.78e-14/2.84e-14. The336-fit compact replay differs by at most
2.84e-14/1.14e-13; it is numerically reproduced, **not byte-identical** on this
runtime. Additional metadata wording and an explicit spatial-correlation flag
also differ from the historical JSON. Compact replay and actual-pixel extraction
are separate claims, and both remain independent reduction alternatives.

The initial28 one-factor/6 group pilot was completed before an injection exposed
a dominant forward-model omission. It is preserved as a historical-response
control in the new JSON, not promoted as a calibrated uncertainty envelope.
A matched geometry, physically signed source with N IV total20 injected before
nod mixing recovers only13.9338 through the historical positive-centered
spectral response. Its nominal95% interval covers the injected N IV truth in
82.575% of4,000 declared formal-noise draws. Statistical covariance algebra
itself matches; increasing uncertainty alone does not fix response bias.

This is not a discovered source or a falsification of the publication. It is a
counterexample to the historical forward model under a specific injected source
and the frozen official native extraction. The historical signed spatial
extraction is retained exactly; its later spectral response omitted the ghosts'
**different source-centered wavelength responses**. Same-detector-pixel WCS
alignment does not imply that sources at different nod rows have identical
wavelength per column. Their source-centered grids differ by up to0.0261µm in
the UV (roughly one native column in this reduction).

## Revised signed-source response

Let P_j(r,c) be each nod's positive spatial profile times stored point
throughput, M_ij its actual logged triplet nod mixing, and o_i(r,c) the frozen
source extraction operator. A spectral source model S_j(c) on nod j's own full
wavelength grid predicts the extracted amplitude

`a_i(c) = sum_j Q_ij(c) S_j(c)`,

where `Q_ij(c) = M_ij sum_r o_i(r,c) P_j(r,c)`.

The revision transports the spectral design through Q before GLS, preserving
full native bin edges, masks, signed ghosts and covariance. It never performs
another subtraction on observed CAL science. Constant-spectrum response closes
to6.7e-16. A separate explicit image injector constructs each positive source,
then its signed synthetic nod difference; its measurement agrees with the
transported design before fitting.

Matched-profile noiseless total20 now recovers20.000000000000018. Four thousand
raw-detector Gaussian noise realizations propagated through actual nod mixing,
variance reconciliation, masks and extraction give95% marginal coverage
94.675–95.425% across the five groups. Every simulated covariance entry agrees
within1.53 expected Monte Carlo sampling standard deviations. A separate draw
from the *assumed* empirical measurement covariance checks that model only.
Changing injected sigma0.80→0.95 pixels biases N IV20→18.675; shifting the
trace by+0.10 pixels gives19.777. Those bounded mismatches and frozen variance
are not a brightness- or morphology-calibrated population coverage study.

The revised response still approximates each nod by a profile-weighted scalar
wavelength grid and generic Gaussian LSF. It does not yet integrate the full
row-dependent spectrograph response, determine source extent/along-dispersion
illumination, or reproduce the author's older-calibration operator. These
limits remain distinct from the corrected, independently testable signed
spectral response.

## Four revised conditional fits and held-out prediction

Atomic reference cell is Te20,000K/ne1,000cm^-3; z14.44, intrinsic width0 and
linear continuum are fixed. Noise is the frozen empirical row+column transport.
The fresh5×5 fitted covariance is retained for every alternative. N IV below is
total1483.321+1486.496 in10^-20erg/s/cm². The ionic ratio is observed two-stage
N/C, with unknown elemental stage correction.

| Wavelength / generic resolution | N IV total | Ionic N/C | Signed conditional95% Fieller set |
|---|---:|---:|---|
| Original / nominal |31.54±15.69|3.357|[-0.291,11.961]|
| Original / point |22.46±11.92|2.981|[-0.255,9.770]|
| DUMMY / nominal |34.21±15.77|3.570|[0.138,11.421]|
| DUMMY / point |25.92±12.02|3.571|[0.324,11.222]|

The original-point revised N IV flux increases from13.70 to22.46 at this
physical reference cell, while uncertainty also changes. Both original families
still admit ionic ambient0.2512 and a zero numerator. DUMMY/point excludes that
ionic reference at this cell, whereas DUMMY/nominal admits it. That explicit
conditional contrast remains visible; **DUMMY is not measured calibration**, and
model preference or elemental enrichment does not follow from the contrast.
The alternative likelihoods are not pooled or ranked by these bounds.

Independent official-CAL RATE-group prediction uses the two other groups for
training, profiles a separate test continuum, and propagates the trained line
covariance into prediction. For the revised original-point model, holding out
groups03/05/07 gives conditional predictiveχ²183.86/210.40/158.50 for208dof.
Their training N IV totals are4.76/31.54/31.32; each held-out group fits
59.08/4.85/4.39. Group03 carries much of the weak conditional support, but no
held-out discrepancy rejects the fixed empirical model. These are conditional
model checks, not an empirically calibrated tail test. Only three groups exist;
a shared additive line offset is exactly confounded with source flux and has
**no upper bound from group agreement**.

## Public author provenance: newly resolved, still dependent

The astrometry specialist acquired the public sibling PIXTAB and exact indexed
msaexp source during this round. Its optimized profile settings and weights are
now public and inspected; the earlier statement that PIXTAB was unavailable is
superseded by that acquisition. That work independently reproduces the author's
public1D histogram extraction and proves repeated negative sky samples across
VISITGRPs. Its source `make_diff_image` averages other nod positions within the
nine-exposure SlitGroup; public author group cuts must not be treated as three
independent observations. The official CAL alternative uses the separately
logged per-triplet backgrounds. Older public CAL/CRDS calibration differs from
the current officialCAL2.0.1/jwst_1535 context. Different operators, calibration,
masking and pathloss require explicit reconciliation before comparing fits.
PIXTAB supplies no full donor-mask/detector-coordinate map, and the optimized
PRF sigma is not interchangeable with this native Gaussian detector width.
No claim here reproduces or falsifies the published author's likelihood.

## Reproduction and independent validation

```bash
python -m data_pipeline.mom_native_batch \
  --spectrum data_sources/pilot/mom_z14_dja_v4.spec.fits \
  --output /tmp/mom-native --report /tmp/mom-native-restoration.json
python -m tools.jwst.native_reduction --native-dir /tmp/mom-native \
  --output /tmp/native-actual-replay.json
python -m tools.jwst.composed_spectral_refit \
  --output /tmp/composed-replay.json --figure /tmp/composed-replay.png
OPENBLAS_NUM_THREADS=1 python -m tools.jwst.native_measurement_validation \
  --native-dir /tmp/mom-native --draws 4000 \
  --output /tmp/mom-native-measurement-validation.json
python -m pytest tests/test_native_measurement_validation.py \
  tests/test_composed_spectral_refit.py tests/test_mom_native_reduction.py \
  tests/test_niv_doublet_refit.py -q
```

The CLI caps draws at4,000. Compact-only
execution without `--native-dir` reproduces the historical-response sensitivity
controls, but does not manufacture signed pixel validation or revised fits.
The new response is versioned separately and leaves all old grids, defaults,
JSON/NPZ and N IV version1/version2 contracts unchanged. Independent tests solve
normal equations and continuum-projected predictive precision, preserve native
bin edges across quality cuts, and demonstrate a same-detector-WCS/different-nod
wavelength counterexample with a known raw source. An independent specialist's
actual-CAL SVD/erf implementation is required before publication.

Next priorities are applying this signed response to the complete thermal
photoionization likelihood, a full row-dependent source/LSF response, and the
public author's pixel/donor/old-calibration reconciliation. Redshift/geometry
ranges need measured calibration; shared source/systematic calibration and
ion-stage fractions remain unquantified. No elemental abundance, stellar
polluter, galaxy identity or cosmological conclusion is established.
