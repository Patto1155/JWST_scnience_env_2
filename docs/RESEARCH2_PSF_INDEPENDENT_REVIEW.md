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
