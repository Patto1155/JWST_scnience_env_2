# Row-resolved native wavelength response: bounded follow-up

Declared before execution. This follow-up depends on the reviewed signed-response
PR60 merge `f0a9fd8ce6e2e3dbe6225bbd1cdfca2a0754b4b9`, verified in live master's
ancestry. The worktree starts at newer live master `51d544b` (PR62); unrelated
changes are preserved.

Question: is scalar source-centered wavelength averaging adequate for the
revised signed native measurement, or does the full row-dependent WAVELENGTH
map materially change known-source recovery, measured flux or uncertainty?

Competing predictions: small wavelength spread relative to instrumental width
predicts negligible changes; finite slit/trace shear predicts changes coherent
with the actual extraction weights. A row-resolved source injected through
signed nod differences should close under the matching operator. Scalar fits
may show residual approximation bias.

Expected information gain: quantify one specific instrumental approximation
using existing detector coordinates. This does not measure a source-specific
LSF, repair an unknown absolute wavelength calibration, or recreate the author's
older-calibration likelihood. The current extended-source WCS and point
throughput are assumed alternatives.

Budget: zero downloads; four fixed reference-cell fits (original/DUMMY
wavelength×nominal/generic-point resolution), three held-out original-point
RATE-group predictions, and bounded noise-free cross-operator injections.
Use existing masks, source profile, signed nod incidence and row+column covariance.
No atomic, thermal, redshift, continuum or width grid expansion. Stop after the
four alternatives and controls; report any failure without enlarging scans.

Full native row-grid bin edges precede quality selection. Missing wavelengths
outside calibrated row coverage are extrapolated only to complete the full
model grid, and no invalid science pixels enter the measurement. The native
measurement wavelengths are not inferred from the injected spectral outcome.

## Result: this approximation is small in the bounded pilot

The revised positive pixel model evaluates the bin-integrated physical multiplet
response separately on every calibrated row's full native wavelength grid. The
source Gaussian profile and point throughput multiply that response. Each actual
triplet's signed nod operator then mixes donor sources before the frozen spatial
extraction weights are applied. Full5×5 flux covariance is refitted for each
alternative; the source-amplitude covariance and empirical transport stay fixed.

All four scalar signed reference fits from PR60 reproduce to numerical precision.
A separate direct synthetic image contraction closes against the row design.
Matched row-source total N IV20 is recovered to numerical precision by the row
model. The scalar model gives19.882 under original/point assumptions. Across the
four families, every scalar injection bias is below0.017 of its conditional
line sigma for the specified faint source; this analytic Gaussian calculation
checks the assumed covariance, not empirical coverage or brightness scaling.

| Wavelength / resolution | Row-model N IV total±conditional sigma | Row ionic N/C | Signed conditional95% Fieller set |
|---|---:|---:|---|
| Original / nominal |31.79±15.72|3.367|[-0.246,11.817]|
| Original / point |22.87±11.99|3.004|[-0.202,9.698]|
| DUMMY / nominal |34.38±15.79|3.574|[0.165,11.321]|
| DUMMY / point |26.20±12.07|3.580|[0.350,11.153]|

N IV is total1483.321+1486.496 in10^-20erg/s/cm². Te20,000K/ne1,000cm^-3,
z14.44, intrinsic width0 and linear continuum remain fixed. Ionic N/C is the
observed two-stage quantity, not elemental N/C. Both original alternatives admit
zero and ionic ambient0.2512. DUMMY/point conditionally excludes ambient while
DUMMY/nominal admits it; the toy calibration receives no empirical preference.

For original/point, the row change in measured N IV is+0.407, versus conditional
sigma11.99. The maximum row-versus-scalar measured flux difference across all
four families is0.052 conditional sigma. The change in its ionic point is
2.981→3.004. Conditionalχ² changes by less0.18. These calculations bound the
**specified row-averaging comparison**, not every possible wavelength/LSF model.
Unknown source-specific LSF, absolute wavelength, common calibration and ion
fractions therefore still dominate the unresolved physical interpretation.
There is no justification for expanding a large row-approximation grid.

The original-point held-out predictions remain stable: groups03/05/07 give
conditionalχ²183.74/210.41/158.53 for208dof, with independently trained line
covariance propagated and a separate test continuum profiled. The same sparse
three groups cannot bound a common calibration offset. No new independent
exposure or off-source photons were obtained. Existing below-break/off-trace
measurement controls remain unchanged because their extraction operators and
source-amplitude covariance were retained; this work changes the spectral
forward response rather than the measured columns.

## Limits and reproduction

The per-row WAVELENGTH map belongs to the official extended-source calibration.
Combining it with assumed point throughput/source geometry and a generic Gaussian
LSF is an explicit independent-reduction alternative. A point source does not
necessarily experience the same LSF/wavelength mapping as uniformly illuminated
slit pixels. Source illumination along dispersion, instrument shear and LSF may
therefore require a consistent empirical reduction rather than choosing the
slightly tighter row result. The public author PIXTAB uses a different older
calibration and globally shared negative sky; it is not reproduced by this pilot.
No elemental abundance or physical enrichment mechanism is identified.

```bash
python -m data_pipeline.mom_native_batch \
  --spectrum data_sources/pilot/mom_z14_dja_v4.spec.fits \
  --output /tmp/mom-native --report /tmp/mom-native-restoration.json
OPENBLAS_NUM_THREADS=1 python -m tools.jwst.native_row_response \
  --native-dir /tmp/mom-native --output /tmp/mom-native-row-response.json
python -m pytest tests/test_native_row_response.py \
  tests/test_native_measurement_validation.py -q
```

`research_output/mom_native_row_response.json` pins the merged signed artifact,
physical/wavelength inputs, software and all nine original CAL identities. Tests
include a full-grid completion counterexample, the exact zero-row-shear scalar
limit, an independent erf/CDF single-line pixel-image oracle under nonzero shear,
and Gaussian bias/coverage checks. Historical artifacts and model contracts remain
unchanged. Independent actual-CAL matrix/coordinate review is required before merge.

Next use the complete thermal model through the signed likelihood. Pursue measured
source-specific wavelength and LSF calibration before extending the minor row
approximation or interpreting abundance. Keep all calibration alternatives and
shared-photon dependencies explicit.
