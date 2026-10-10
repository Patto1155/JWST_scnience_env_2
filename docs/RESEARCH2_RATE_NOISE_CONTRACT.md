# Third-round RATE/CAL noise-contract audit

Preregistered question: does the exact JWST 2.0.1 Spec2 background step propagate donor noise into target ERR/VAR, as assumed by the historical native covariance demixing? Actual one-group RATE/CAL variances will discriminate target-only versus post-subtraction variance. A second bounded question tests whether finite donor pixels support equal half weights on the target footprint.

Competing predictions: target-only VAR_RNOISE and VAR_POISSON retain a common multiplicative calibration gain relative to their own RATE arrays; post-subtraction variance requires donor variance terms. The pinned background source predicts target-only ERR/VAR despite a separately computed background ERR. If verified, use a new versioned transport, leave historical arrays/contracts intact, and label all frozen likelihoods using the demixed covariance conditional on an unsupported noise assumption.

Expected information gain: resolve a foundational shared-noise contract before refining nuisance grids. This does not calibrate the source-specific LSF or absolute wavelength. Budget: three group03 RATE files, 251,890,560 bytes; 62,306 bytes exact pipeline source; eight concurrent checked 4 MiB ranges; no paid resources, JWST installation or CRDS reprocessing. The nine pinned CAL files (464,135,040 bytes) are restoration accounted separately. Stop after identity, variance closure and a one-group signed covariance comparison. Remaining groups require additional inputs beyond this acquisition cap; do not extrapolate their numerical correction.

Independent validation will use primary-source functions with lightweight model stubs and a separately constructed raw-pixel covariance. No full author reproduction is claimed.

Pilot result and expansion decision: group03 target-only variance closure agrees within 2.86e-7 relative error; half-donor SCI closure within 1.49e-6 CAL sigma. This falsifies historical demixing and justifies reconstructing the signed covariance for all three groups. Coordinator reallocated the selected spectral cap to 870 MiB, within the global 2 GiB cap. Acquire six remaining RATE files (503,781,120 bytes), with the same range and identity checks. Stop after all nine donor-noise transports, source likelihood comparison and independent numerical validation; no pipeline/CRDS installation or added scenario grid.

## Actual results

All nine selected RATE products are JWST 2.0.1, CRDS `jwst_1535.pmap`, full 2048×2048 NRS2 images in DN/s. Their exposure starts match the nine pinned CALs. The target crop is zero-index rows1292:1320, columns439:862. Whole-file SHA256 pins and exact public URLs are in `data_sources/followup/mom_rate_noise_manifest.json`. Range checks enforce HTTP206, exact total/offset Content-Range and exact response length before whole-file hashing.

The exact pinned `jwst/background/background_sub.py` function subtracts background SCI and ORs background DQ, leaving target ERR, VAR_POISSON and VAR_RNOISE unchanged. The background ERR is computed separately and returned. Executing that exact AST with a donor-error999 stub leaves target error3 and variances5/4 unchanged. The pinned background step and Spec2 driver introduce no donor variance correction. Actual data confirm the mechanism: gain-squared is inferred from CAL/RATE VAR_RNOISE; target-only VAR_POISSON and total ERR-squared identities agree to maximum5.849e-7 relative error. The common multiplicative gain includes post-subtraction calibration, and is applied consistently to both mean source response and covariance.

For each actual group, equal-half subtraction of the two other RATE SCIs, multiplied by the measured calibration gain, reproduces common usable CAL science pixels within1.737e-6 CAL sigma. There are7544,7611 and7368 common usable target-footprint pixels in groups03,05 and07. Missing SCI and donorDQ outside that support cannot be extrapolated into weights inside it. The frozen extraction operators have no support on unmodeled donor pixels. A second background subtraction is never applied to CAL science.

The historical assumption `D_i=V_i+(V_j+V_k)/4` for CAL ERR is rejected. Therefore historical nonnegative demixing and its independent variance remainder are not a physically identified reconstruction of raw photon/read noise. The versioned replacement uses actual RATE error variance and measured gain:

`Cov_ij(r,c) = G_i G_j sum_k M_ik M_jk RATE_ERR_k²`, with `M_ii=1`, `M_ij=-1/2`.

A target-specific CAL VAR_FLAT remainder is added independently. Its cross-nod/reference covariance is not identified by FITS diagonal variances and remains an explicit assumption. The recorded independent flat remainder contributes only6.3–7.8e-5 of formal N IV variance. A shared same-detector-pixel signed flat-reference model contributes2.0–2.2e-4. Even unrestricted correlations consistent with these recorded marginal flat variances have a fixed-estimator upper bound of2.9–4.1% of formal N IV variance. These bounds do not constrain unrecorded common calibration systematics. Raw pixels and extraction weights then determine all same-column amplitude covariance. Calibration gains also enter donor source responses as `G_i/G_j`; their maximum same-pixel nod spread is7.30e-4. The CAL-only equal-gain approximation is small in this dataset but is not used as the primary noise transport.

Correct total pixel variance is a median1.5047,1.5040 and1.5039 times target-only CAL variance in the three groups. Re-estimating off-source controls against those full marginal variances gives excess scale-squared1.427616, versus historical2.220621. Fresh spatial/spectral moments and guarded stationary kernels are recomputed. Reusing2.220621 with added donor variance would double-count much of the measured diagonal excess. The residual1.427616 is still material; three groups, correlated rows/nods and common calibrations do not calibrate its source-interval coverage.

| Conditional noise transport | Wavelength | Resolution | Total N IV flux ±sigma | Observed-stage ionic N/C 95% Fieller interval |
|---|---|---|---|---|
| RATE + fresh controls | Original | Generic point | 22.6461 ±11.7184 | 3.0602 [-0.1582,9.9050] |
| RATE + fresh controls | Original | Nominal | 31.1511 ±15.3690 | 3.4122 [-0.2591,12.2692] |
| RATE + fresh controls | DUMMY sensitivity | Generic point | 26.0698 ±11.8163 | 3.6624 [0.4039,11.4858] |
| RATE + fresh controls | DUMMY sensitivity | Nominal | 33.7938 ±15.4360 | 3.6389 [0.1716,11.7826] |

Flux units are1e-20 erg/s/cm². The original generic-point interval includes the ambient ionic reference10^-0.60=0.2512. DUMMY sensitivity changes that conditional comparison but does not supply empirical wavelength calibration. Formal RATE photon/read+independent-flat noise alone gives original generic-point N IV22.7318±9.6647 and ionic interval[0.4286,7.7620], excluding that reference under narrower assumptions. The residual empirical noise transport therefore controls the claimed conditional tension. Ionic N/C remains distinct from elemental N/C; unknown ion fractions and C IV transfer remain unmeasured.

Four models share4000 fresh Gaussian raw-detector realizations, signed before measured gain and extraction. The independent flat residual is drawn separately. Marginal N IV coverage is94.525–95.025% with approximately0.345 percentage-point Monte Carlo standard error; noisefree known-source closure is below3.2e-14 in coefficient units. This validates fixed observed RATE variance arithmetic, not source-Poisson realizations, true empirical covariance or source-specific LSF. Fresh held-out official group prediction tails span0.399–0.996. They test conditional statistical consistency; common calibration errors cannot be excluded with three groups.

## Reproduction and use

In the exact locked environment, from the repository root:

```bash
python -m tools.jwst.acquire_rate_noise_inputs --output-dir /path/to/rate-cache
OPENBLAS_NUM_THREADS=1 python -m tools.jwst.native_rate_noise \
  --native-dir /path/to/pinned-nine-CALs --rate-dir /path/to/rate-cache
python -m pytest -q tests/test_native_rate_noise.py tests/test_native_measurement_validation.py \
  tests/test_native_row_response.py tests/test_mom_native_reduction.py \
  tests/test_mom_native_spatial_covariance.py tests/test_composed_spectral_refit.py
```

Actual-pixel reproduction verifies all nine RATE hashes, nine original CAL inventory hashes and the source spectrum hash. `load_rate_noise_replay(report_path, empirical=False/True)` verifies the compact NPZ receipt and returns selected columns, full-column covariance blocks, kernel, variance scale, frozen amplitudes and gain-corrected source/ghost coupling. Apply the coupling to model-weighted source designs before fresh GLS. This compact replay is numerical likelihood reproduction; it does not re-read RATE pixels. Its selection and amplitudes are identical to the native wavelength replay and its noise contract is explicitly version3. Historical contracts, arrays and analyses remain untouched. Positive-only historical spectra, old demixed covariance and old empirical controls must be labeled historical conditional alternatives.

Acquisition: pilot68.3s, expansion170.1s,755,671,680 scientific bytes,62,306 exact-source bytes and4096 range-probe bytes. Total selected transfer755,738,082 bytes fits the reallocated870 MiB cap and coordinated2 GiB global cap. CAL restoration464,135,040 bytes is separate. The final actual-pixel computation took30.24s with one BLAS thread. The bounded experiment contains four fixed resolution/wavelength families, three separately reported noise contracts, twelve held-out predictions and one4000-realization ensemble. No scenario counts are probabilities.

Validation:36 focused tests and Ruff pass. Independent review is required before publication; the authors of this transport are not its sole numerical validators. The authoritative scientific change is a rejected CAL variance contract and a validated replacement donor-noise arithmetic. No new source, elemental abundance, stellar polluter or cosmological result is established. Remaining dominant uncertainties are common calibration/reference correlations, source-specific LSF and absolute wavelength, empirical transport to source pixels, ionization and radiative transfer. The next high-information experiment couples complete composition-aware models to this fresh likelihood; a larger generic nuisance grid is lower priority.
