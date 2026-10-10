# Independent baseline, selection and signed spectral-response review

10 October 2026. PSF/noise specialist validation of other authors' work. This
review does not authorize pooling dependent reductions or interpreting assumed
count/LSF responses as measured calibration.

## Baseline release and geometry-selected pilot

`research_output/research2_selection_baseline_review.json` independently verifies
the coordinator baseline XML/log hashes, 582 tests (579 passing/three explicit
skips), all 65 installed lock versions, 68 preserved scientific artifact hashes
and 210 preserved code/configuration hashes. The baseline receipt retains its
explicit distinction between committed-artifact replay and actual pixels.

The selection design was frozen at `ca5e16e`, with the response committed at
`7e941db`. The review pins the final response SHA256
`f1b19aea12e4623e1b3a6253399f9f4a12eaf629e760ac659020e5f5a7fc2b10`
and canonical full-trial content SHA256
`e290d6813cd7a6ec12212d7ec363fa99ae0a5767991ff98fbbd0fe0e0a6119e6`.
All 1,152 raw-trial rows and 72 summary groups were parsed independently.
Every group denominator, site-averaged bootstrap fraction/interval and paired
source-minus-scene identity was recomputed. Maximum paired arithmetic error is
zero. No unmodified site passes the joint red-and-centroid criterion. The
added toy photon-transport covariance [[5,5],[5,5]] is independently recovered
as A diag(20) Aᵀ for A=[0.5,0.5]ᵀ; a signed difference has zero variance.

A separate 2,000-draw Poisson/source-aperture moment check before response
publication gave mean standardized error 0.137 and measured variance 0.1791
versus analytic 0.1869, consistent with finite sampling. The signed sky operator
has sum 3.55×10⁻¹⁵. These checks validate conditional count arithmetic. They do
not calibrate electrons/nJy or source-drizzle covariance from the JWST detector.

**Approval scope:** the bounded conditional response pilot. Required caveats
are finite modeled PSFs, assumed output-grid count conversion, spatial diagnostic
strata sharing the global threshold, repeated scenes, uncalibrated interval
coverage and no real-source labels/population likelihood. The author report now
states those limitations explicitly.

## Native signed-source spectral closure

The spectroscopy author discovered that a noiseless source with total N IV=20
was recovered as 13.9338 under the frozen positive-source-only spectral design.
An independent reviewer must distinguish an injector defect from a missing
measurement response before certifying the proposed correction.

The review reopens all nine actual CALs through existing pinned input guards,
then independently reconstructs integrated spatial profiles, all positive and
negative nod contributors, a block subtraction matrix and per-column weighted
spatial extraction using SVD. No spectroscopy-author source/response/extraction
function is imported. The separately reconstructed source amplitudes agree
with the historical compact amplitudes to **1.87×10⁻¹⁶ µJy**.

The three positive source positions in each nod group have different
source-centered wavelengths. At the first selected UV column they are
**2.15030/2.16332/2.13724 µm**. The fixed spatial extraction combines their
spectra. Modeling only each positive nod's wavelength response omits the
negative contributor spectra already present in the source operator.

For profile P, signed mixing M and source extraction L, the independent transfer
is Qᵢⱼ(c)=Mᵢⱼ Σᵣ Lᵢ(r,c)Pⱼ(r,c). Direct synthetic image mixing and extraction
match the composed Q-times-source response to **1.39×10⁻¹⁷ µJy**; its row sums
are one within 4.44×10⁻¹⁵. Consequently equal constant contributor spectra
close, while distinct source-centered line responses need not close with the
old positive-source-only design.

The independent formal-covariance fit reproduces the original counterexample:
N IV input20 is recovered as **13.9338272104**. The all-contributor response
recovers20 to floating-point accuracy, and all five injected line fluxes close
within9×10⁻¹⁴. Changing only the covariance to the existing empirical transport
changes the old mis-specified recovery to13.7767; a covariance choice cannot
repair the omitted response.

Applied to actual native source amplitudes, the independently corrected
original-wavelength/generic-point/empirical-row-plus-column fit gives N IV
**22.4618494521** with covariance142.1758895 (conditional sigma11.9246), and
χ²**547.381118886**. Five-flux/covariance differences against the author's new
corrected fit are below1.4×10⁻¹⁰ and1.2×10⁻⁹ respectively. The artifact
`research_output/research2_signed_response_review.json` pins the exact author
artifact reviewed and all nine actual input hashes.

**Approval scope:** the independent signed-contributor response correction,
all four fixed original/DUMMY ×nominal/point references and the declared
fixed-covariance detector-noise injection arithmetic at frozen science commit
`c9cf5b2`. Its cause is resolved within the
declared source model. Neither scalar per-nod source-centered wavelength
assignment nor noiseless closure measures full2D wavelength response, source
LSF, morphology, pathloss or author's exact extraction likelihood. Refit ionic
ratios remain conditional; elemental N/C is unmeasured. Historical v1/v2 and
336-fit artifacts should remain unchanged and clearly superseded where this
specific operator approximation matters. This review alone does not certify
every new nuisance/shift/group family or empirical coverage of source noise.

The expanded independent review pins author artifact
`c7e31e81a6bb6b9b4b81bf48661ccfa28475be5cf6b226f85113c78fe73074ca`.
All four fixed-family fluxes, covariance and signed Fieller roots were recomputed
with the SVD spatial extraction and independent Gaussian-bin/normal-equation
spectral solver. Maximum flux/covariance differences are2.03×10⁻¹⁰/3.31×10⁻⁹.
Original nominal/point conditional ionic intervals are[-0.2906,11.9608] and
[-0.2553,9.7699]; both admit the solar ionic reference0.2512. DUMMY nominal
[0.1383,11.4213] admits it; DUMMY point[0.3244,11.2220] excludes it. The
latter is a toy-calibration conditional tension, not calibrated empirical
evidence for elemental nitrogen enrichment.

An independent exhaustive active-subset solver reconciles the43 negative raw
variance pixels without importing the author's NNLS/noise routines. Propagating
the resulting signed raw-plus-diagonal-remainder covariance reproduces extracted
formal covariance to7.05×10⁻¹⁹ and coefficient covariance to2.84×10⁻¹⁴. This
checks the actual frozen masks/operators and conditional noise algebra.

For the matched profile, exact signed-flux Gaussian coverage is95% under that
declared fixed covariance; the author's4,000 detector-noise draws lie within
1.24 binomial sampling standard errors of it. Independent image-level broader
profile/trace-offset injections reproduce their noiseless recoveries within
1.8×10⁻¹². Analytic bias-aware Gaussian coverage predicts94.51–94.98% for the
broader profile and94.99–95.00% for the trace shift; author draws agree within
1.39 sampling standard errors. Ten thousand separate GLS-projected Gaussian
draws confirm these conditional probabilities. No source-photon variance is
recomputed and none of these tests calibrates unknown nonstationary source noise.

## Reproduction commands

```bash
OPENBLAS_NUM_THREADS=1 python -m discovery.research2_selection_receipt \
  --coordinator "$COORDINATOR_REPO" --selection "$SELECTION_REPO" \
  --trials "$SELECTION_CACHE/selection_pilot_trials.json" \
  --output /tmp/research2_selection_baseline_review.json
OPENBLAS_NUM_THREADS=1 python -m discovery.research2_signed_response_review \
  --root "$SPECTROSCOPY_REPO" --native-dir "$NATIVE_CACHE" \
  --output /tmp/research2_signed_response_review.json
```

Both are independent executable audits; they require the exact pinned inputs.
The selection trial file is outside git; the native file identities are guarded
before any pixel calculation. No new downloads occurred for these reviews.

## Source46 adjacent F410M: independent actual-pixel review

The medium-band experiment at frozen photometry commit`ddcd23b` is approved
within its declared conditional scope. Independent audit
`discovery.research2_medium_review.py` checks all actual cutout/PSF/passband
hashes and pins author result
`df00194c821bc3ff4b17ffd95c9fe7ba885c8f297f2bbdb636baf5da8f582eec`.
The source46 position/filter/unit/WHT and transported morphology are verified.
SCI conversion is10nJy per stored pixel unit, and formal sigma is10/sqrt(WHT).

Independently integrating input/output PSF angular pixel overlaps retains
0.9723168 of the finite supplied PSF. Explicit convolution/bilinear mapping
and a separate spatial SVD solver reproduce all six conditional signed flux
fits within2.3×10⁻¹³nJy; errors and objectives also agree numerically. Six
independent spherical-aperture/annulus pixel sums reproduce331.75–418.55nJy
and their diagonal uncertainties. A distinct Nelder–Mead centroid fit agrees
with the author's Powell result within7.44×10⁻⁷arcsec, giving a displacement
0.004676arcsec from the transported F444 position.

Approximately82.13% of the fiducial diagonal residual objective lies within
0.2arcsec of the source center. This quantifies structured central model
inadequacy; it does not identify a companion or distinguish source structure
from PSF error. The six model coefficients span544.81–575.27nJy, far exceeding
the1.04nJy background-only scaled error. The report correctly excludes that
error from a total calibrated uncertainty or precise flux-ratio claim. Unknown
PSF/background/neighbor/source-noise effects remain material for classification.

A separate XML TABLEDATA reader validates both photon passbands and reproduces
the conditional single-line overlap window4.307–4.316µm under the specified15%
tolerance. Explicit integration of a narrow line centered at4.3115µm gives
F410/F444=0.83533, compatible with the conditional template coefficient ratio
0.84483 under that illustrative tolerance. Thus the positive adjacent-band
counterpart rejects negligible F410 emission, while an overlapping line remains
a concrete counterexample to identifying a broad continuum. The interval is
not a measured line wavelength/redshift range. Different-filter contributors
have no exact filename overlap, which does not establish independent calibration
or a contemporaneous/static-source spectral likelihood.

The exact receipt is`research_output/research2_medium_review.json`. Reproduce
without downloading additional data:

```bash
OPENBLAS_NUM_THREADS=1 python -m discovery.research2_medium_review \
  --root "$PHOTOMETRY_REPO" --input "$MEDIUM_CACHE" --deep "$DEEP_CACHE" \
  --output /tmp/research2_medium_review.json
```

This approval establishes actual positive adjacent-band emission and validates
the conditional measurement/degeneracy arithmetic. It does not establish source
identity, proper motion, an empirical PSF, a calibrated total SED covariance or
a broad-continuum interpretation.

## Candidate 98 and 1043: independent neighborhood audit

Frozen author commit `2b050c0ae6f574944f7681b1f24a1eb7f18e588f` and artifact
`10e74e8bd2c0b33b0a0e67927189580d5ac1e98561a6822924d8ed8b93a0b973`
passed an independent actual-pixel review. The reviewer verifies six science
image hashes and three finite modeled PSF hashes, independently reconstructs
F200 guide peaks and WCS transport, integrates angular PSF pixel overlaps, and
uses explicit bilinear coordinate maps with an unnormalized QR solver. The new
author module is not imported. Previously reviewed image loaders and physical
stamp conversion are shared and disclosed in the receipt.

All 36 fits and 216 amplitude folds agree: maximum coefficient difference is
4.84e-10 nJy, covariance difference 3.64e-11 nJy², and fold RMS difference
8.39e-13. Full target covariance sums and selection-centered aperture functionals
agree. The largest normalized design conditions are 11.90 and 16.96, with
maximum target/nuisance correlations 0.650 and 0.433. Thus numerical rank loss
is not the source of these failed predictions; low condition number does not
establish a scientifically adequate decomposition.

Source 98 passes three blue F090 families but no F200 or F444 family: minimum
held-out standardized RMS is 1.524, 5.186 and 5.229, respectively. Weak accepted
blue amplitudes admit zero under their conditional errors. Source 1043 passes
no family, with minima 7.400, 11.581 and 15.420. Classification stops for both.
These same-image amplitude folds have data-conditioned prior geometry and
correlated pixels. They do not establish unbiased pipeline cross-validation,
independent epochs, calibrated uncertainties or astrophysical identities.
Failed-family flux excursions remain model sensitivities, not confidence sets.

The exact review is `research_output/research2_neighborhood_review.json`.

```bash
OPENBLAS_NUM_THREADS=1 python -m discovery.research2_neighborhood_review \
  --root "$ASTROMETRY_REPO" --deep "$DEEP_CACHE" \
  --originals "$ORIGINALS_CACHE" --output /tmp/research2_neighborhood_review.json
```

No downloads were required. Approval covers the conditional numerical
measurement and explicit stopping decisions.

## Row-resolved native response: independent conditional approval

Frozen spectroscopy commit `dc9cb69` and artifact
`ee0a79bcc65ff60da25cbd97ad8e9aca895a70d9c7f222dca7039da29036ab00`
passed a separate pixel-row spectral oracle. The review reads all nine pinned
actual CAL WAVELENGTH arrays, reconstructs spatial extraction by SVD, explicitly
integrates each row's full spectral bins using erf rather than production
`line_matrix`, subtracts each signed donor individually, and uses independent
normal GLS. Four original/DUMMY × nominal/generic-point likelihoods agree within
2.02e-10 in line flux and 3.30e-9 in covariance. A pixel-image injection of N IV
20 recovers 20 within 2.6e-13; the original-point scalar approximation recovers
19.881895. Across all four families, the declared scalar injection discrepancy
is below 0.0166 conditional sigma. Its analytic fixed Gaussian covariance
95% interval coverage is 0.949969 or better, consistent with the author's
conditional approximation budget; this is not empirical coverage calibration.

Original-point held-out RATE group predictive chi² values are 183.7431,
210.4134 and 158.5321, each with 208 conditional degrees of freedom. Independent
precision-matrix continuum profiling agrees with the author's QR projection
within 1.6e-11. Three RATE groups cannot constrain a shared systematic
calibration distribution; neither held-out fit agreement nor a more detailed
response establishes the absolute wavelength or source LSF calibration.

Optional full metadata decoding also succeeded independently. All nine actual
CAL ASDF/GWCS wavelength grids agree with stored WAVELENGTH within
2.3842e-7 µm, consistent with float32 storage; x±0.5 GWCS dispersion agrees
exactly with the pinned transform inputs. Reading the actual ASDF reference
with its explicit DUMMY pedigree and independently mapping mean columns
reproduces every corrected row within 1.78e-15 µm. This validates the numerical
sensitivity transform, not its applicability as empirical source calibration.

The locked 65-package environment was preserved. Compatible ASDF/GWCS decoders
were placed in a separate target. Exact versions, installed-content hashes,
and earlier verified wheel download identities are recorded in
`data_sources/metadata_decoder/manifest.json`. The final installed files occupy
about 10.3 MB. UV transfers were not instrumented; the ledger transparently
reserves 24 MiB for them plus exactly 2,200,275 bytes for extra archived wheels,
a total software allocation of 27,366,099 bytes, below the 32 MiB bound. No new
astronomical pixels were downloaded. Initial older converter/schema sets could
not decode the CAL2.0.1 tags; the final compatible clean target resolved that
accessible dependency.

The exact receipt is `research_output/research2_row_response_review.json`.
For metadata-inclusive reproduction, install only these pinned optional
packages into a fresh directory outside the locked environment:

```bash
uv pip install --target "$METADATA_DECODER" --no-deps \
  asdf==4.2.0 gwcs==1.0.3 asdf-astropy==0.11.0 asdf-standard==1.5.0 \
  asdf-transform-schemas==0.6.0 asdf-coordinates-schemas==0.5.1 \
  stdatamodels==6.0.0 asdf-wcs-schemas==0.5.0 attrs==25.3.0 \
  semantic-version==2.10.0 jmespath==1.0.1 importlib-metadata==8.7.0 zipp==3.21.0
PYTHONPATH="$METADATA_DECODER" OPENBLAS_NUM_THREADS=1 \
  python -m discovery.research2_row_response_review \
  --root "$SPECTROSCOPY_REPO" --native "$NATIVE_CACHE" \
  --output /tmp/research2_row_response_review.json
```

The physical point profile/pathloss and generic LSF remain assumed. The native
WAVELENGTH mapping is for extended illumination, so row resolution alone does
not measure the point-source instrumental response. This review approves the
numerical row response under the frozen covariance. A subsequent investigation
of whether pipeline 2.0.1 background subtraction retained target-only ERR/VAR
is underway and can change that covariance contract. This approval does not
certify the inherited demixing as empirical detector covariance, identify
an elemental abundance, pool alternative likelihoods or establish a discovery.

## RATE-derived noise version 3: independent actual-pixel review

Frozen author commit `d2958d3d87e725b3e3159b461f75e4c51bb73610`, JSON
`5e9cc7e5e46870f0221c42f762a1186a1396f440e6b34f2b42d5c5fb259d9fc7`,
and compact NPZ `4d679850b44b28ed3d8fc71f0e7fd41f0aa7a7cfcd95aff896de97b728bdfa5e`
passed independent actual-pixel validation. No RATE-noise author module is
imported by the reviewer. This is a physical noise-contract correction that
supersedes interpreting historical CALERR demixing as empirically identified
raw donor noise. Historical arrays and their numerical reviews remain valid
as explicitly conditional contracts and are preserved.

The reviewer hashes all nine complete RATE files, nine original CAL inputs
through their existing pinned guards, and three exact JWST 2.0.1 source files.
A distinct 2×2 exact-function AST experiment confirms background SCI subtraction
and DQ OR while preserving target ERR, VAR_POISSON and VAR_RNOISE object
identities despite donor error 999. Source inspection confirms the background
wrapper has no variance update. The Spec2 driver's variance assignments are to
the unrelated `wfss_esec` electron-conversion helper; all actual inputs are
NRS_MSASPEC. This branch distinction is recorded rather than assuming every
Spec2 mode has the same error contract.

Independent DN/s detector crops, CAL extended-correction restoration, exposure
starts and coordinates establish the target-only variance relationship. Actual
equal-half donor SCI closure is below 1.74e-6 CAL sigma. Common usable footprint
counts are 7544, 7611 and 7368; no frozen extraction weight touches unsupported
donor pixels. Full marginal pixel variance is a median 1.504711, 1.503983 and
1.503916 times target-only CAL variance. Thus interpreting CAL ERR as an
already propagated nod difference variance is rejected by source and data.

Independent detector-weight Gram matrices reproduce formal and spatial
amplitude covariance to 1.14e-18, post-subtraction pixel variance to 3.47e-18,
and frozen extraction weights to 1.81e-14. Measured gains enter both covariance
and the source/negative-ghost response as donor ratios G_i/G_j. There is no
second subtraction of CAL science. The reviewer also independently recomputes
the trace-union off-source mask, row means, variance moments, Bartlett taper
and positive-definite guards. Fresh pooled variance scale is exactly
1.427615919211; reusing historical 2.220621 with newly added donor noise would
count much of the diagonal excess twice.

The first review identified float32 rounding in PATHLOSS_UN/BARSHADOW gain
conversion. The author cast these to float64 consistently with native input
conversion before freezing. The discrepancy is resolved: it did not explain
the physical target-only variance finding, which exceeds that rounding scale
by orders of magnitude.

All twelve fixed likelihoods, signed ionic Fieller sets and twelve fresh
held-out group predictions agree with a separate normal GLS/precision-profile
oracle. Maximum flux discrepancy is 2.02e-10, covariance discrepancy 3.30e-9,
and predictive chi² discrepancy 5.84e-11. Original generic-point control
transport admits the ambient observed-stage ionic reference; formal RATE noise
alone conditionally excludes it. Therefore transporting the remaining excess
noise to the source still controls the conditional enrichment comparison.
DUMMY alternatives are numerically validated sensitivity experiments and
remain uncalibrated.

A separate seed and 5,000 raw-detector Gaussian realizations are mixed by donor,
scaled by measured gains and extracted before line estimation. N IV 95%
coverage spans 94.80–95.18%, within 0.65 binomial sigma of 95%; standard deviation
ratios are 1.003–1.009. Known-spectrum noisefree closure is below 1.16e-13.
This certifies arithmetic for fixed observed RATE variance and the assumed
independent recorded flat remainder. It does not test source Poisson
recalibration, non-Gaussian tails or empirical source-interval coverage.

The independent recorded VAR_FLAT budget reproduces both shared-same-pixel
alternatives and the unrestricted covariance bound. Its independent contribution
is 6.3–7.8e-5 of formal N IV variance; any correlation allowed by those recorded
diagonals contributes at most 0.04014. This bound does not constrain unrecorded
common calibration, absolute throughput or extraction systematics. The
stationary row/column transport from off-source pixels remains an assumption;
three RATE groups cannot identify a shared systematic distribution. No
source-specific empirical LSF, elemental abundance or cosmological result is
established.

The exact receipt is `research_output/research2_rate_noise_review.json`.
Reproduce from the locked environment with the pinned restored inputs:

```bash
OPENBLAS_NUM_THREADS=1 python -m discovery.research2_rate_noise_review \
  --root "$SPECTROSCOPY_REPO" --native "$NATIVE_CACHE" --rate "$RATE_CACHE" \
  --output /tmp/research2_rate_noise_review.json
```

The reviewer downloaded zero additional bytes. Ruff and the complete
actual-pixel executable review pass. Approval covers the replacement donor
noise contract and its explicitly conditional transport, with historical
contracts preserved and the above limits retained.

## Bounded local-identifiability pilot: independent post-outcome review

Approval applies to spectroscopy commit
`b44f2192538ae23ccc822901d2d20982ca750d87` and artifact
`36538f611670eed232c07064fc731e90c88211e384a34b5054fa35441cb45ce2`.
The exact executable was approved at `0fb32c4` before outcomes; the separate
pre-outcome receipts preserve the declared six full likelihoods and six
training fits, zero acquisition and 180-second stopping budget. The author
completed the declared pilot in 9.070 seconds, without expanding its cases.

The separate review executable reads the actual nine CAL wavelength rows and
constructs their row profiles and explicit erf-integrated multiplet responses.
It contracts every positive and negative donor with the measured gain ratios,
then solves GLS with the independently validated, hash-pinned RATE v3 noise
snapshot. It reuses that snapshot, rather than claiming to re-reduce RATE pixels.
All six line vectors and joint covariances agree within 1.50e-10 and 1.20e-9;
conditional chi-square differences are below 1.61e-11. Independent quadratic
roots reproduce all six bounded, signed ionic Fieller intervals. Separate
precision-profile held-out predictions agree within 2.38e-11. Normal nuisance
projection independently reproduces the contrast norms, cosines and singular
values without using the author's QR implementation.

The independent Gaussian forward oracle reproduces both intrinsic-width /
unknown-LSF counterexamples to 2.17e-19 and both redshift / assigned-centroid
counterexamples to 2.05e-17 in response units. These are exact mathematical
confounders under the declared source-response conventions. The centroid check
keeps detector bins, Fnu conversion and continuum fixed; it does not establish
invariance under arbitrary dilation of a calibrated wavelength grid. The
Gaussian LSF alternatives are sensitivity functions, not measured calibrations.

The original-native, generic-point corrected-noise baseline remains N IV
22.6461 +/-11.7184 in 1e-20 erg/s/cm2, with observed-stage ionic N/C interval
[-0.1582,9.9050]. Redshift 14.46 gives [0.4765,12.3167], conditionally excluding
the ambient ionic reference, but improves chi-square by only 0.475 and is
exactly reproduced by a +0.12953% common centroid shift. Thus this apparent
ionic exclusion cannot identify enrichment while that calibration remains
unresolved. Intrinsic width 1,000 km/s and quadratic continuum move N IV only
+0.067 and +0.076 baseline conditional sigma; the width alternative improves
none of the three held-out predictions. These are declared sensitivity
contrasts, not independent uncertainty draws to add in quadrature.

The projected broadening / generic-LSF contrast cosine is 0.94697; their
plug-in model-change SNRs are only 0.01981 and 0.01673 at the declared scales.
The redshift contrast SNR is 0.97793. Unit quadratic-continuum SNR 4.36583 is a
coefficient scale convention and does not detect curvature: its fitted
improvement is only 0.677 for one additional coefficient. These quantities
are conditional local diagnostics, not invariant Fisher information, empirical
power, prior probabilities or measured nuisance ranges. Pooled controls use
all three groups, so training amplitude predictions are not fully held-out
calibration and do not establish empirical interval coverage.

No tighter elemental nitrogen, source-specific instrumental resolution,
absolute emission redshift or intrinsic width is established. Calibrating the
shared centroid and source LSF has more information value than another broad
conditional width grid. Ion fractions, He/O blending, C IV transfer and the
transport of off-source noise remain material. This review approves the bounded
pilot's arithmetic and interpretation with those explicit limits.

Reproduce the separate executable using the locked environment and pinned CAL
restoration:

```bash
OPENBLAS_NUM_THREADS=1 python -m discovery.research2_local_identifiability_review \
  --root "$SPECTROSCOPY_REPO" --native "$NATIVE_CACHE" \
  --output /tmp/research2_local_identifiability_review.json
```

The exact receipt is `research_output/research2_local_identifiability_review.json`.
The reviewer downloaded zero bytes. Ruff and the actual-pixel numerical review
pass; the frozen author report was independently checked against these results.
