# Preregistered local spectral identifiability experiment

This pre-outcome freeze extends the inherited positive-only width/continuum checks through the merged full-row signed mean and fresh RATE v3 covariance. It preserves every historical contract. The question is whether local redshift, Gaussian intrinsic width or continuum shape changes materially alter the conditional nitrogen measurement or predict a held-out RATE group, and whether such changes can distinguish intrinsic physics from unresolved source calibration.

Competing predictions: a resolved intrinsic width changes the bin-integrated multiplets and improves held-out prediction; an unknown source LSF can produce exactly the same Gaussian total width. A centroid change may improve the fit, but a shared fractional centroid calibration can produce exactly the same assigned centers. A curved smooth continuum may change line allocation rather than identify a new abundance. Expected information gain is an explicit diagnosis of these confounders and a bounded uncertainty-budget comparison, rather than a larger conditional grid.

Before outcomes, fix original native wavelength, generic point resolution, the merged empirical RATE v3 covariance (fresh scale 1.427615919211), and the Te=20,000 K/ne=1,000 cm^-3 physical multiplet cell. The source geometry, pathloss and gains remain conditional. Six full-data fits are baseline z=14.44/intrinsic FWHM=0/linear continuum, z=14.42, z=14.46, intrinsic FWHM=300 km/s, intrinsic FWHM=1,000 km/s, and quadratic continuum. Six training fits compare baseline and width 1,000 for each of three held-out RATE groups. Test continuum is profiled; no test line amplitudes enter training. The pooled off-source covariance remains conditioned on all control groups, so this is not a wholly held-out calibration experiment.

The z range follows the published emission-line z=14.44 +/-0.02 sensitivity range in [the primary v2 paper](https://arxiv.org/html/2505.11263v2); it is not an independent prior, because the paper reuses these photons. The published beta=-2.47 implies mild curvature in Fnu across this band, motivating one quadratic-continuum alternative. The widths and quadratic continuum were already tested under the historical positive-only measurement contract; this experiment adds the actual signed-row mean, corrected noise, held-out predictions and explicit identifiability diagnosis.

For Gaussian widths, intrinsic FWHM v and unknown source resolution R_eff(lambda)=[R(lambda)^-2+(v/c)^2]^-1/2 give identical total line shapes. Evaluate an equivalent zero-intrinsic forward response without an additional fit. For centroid calibration, define assigned center=lambda_rest(1+z)(1+epsilon), with detector WAVE, Fnu bin units and continuum fixed and LSF evaluated at the assigned center. Only this centroid convention has the exact redshift/calibration degeneracy. No claim is made that dilating a full calibrated wavelength grid leaves all units and response invariant.

Projected finite contrasts use fitted baseline amplitudes and project out its continuum and five line amplitudes. They are plug-in local model-change SNRs, not empirical power or confidence intervals. Width is parameterized by u=(v/1,000)^2; the 300-km/s contrast is finite u=0.09, not a regular derivative with respect to v at its zero-width boundary. LSF +/-1% is a directional forward diagnostic, not measured uncertainty. No fitted grid counts are probabilities.

Budget: zero downloads, at most 180 seconds computation and exactly twelve fitted comparisons. Stop after this bounded pilot. Verify baseline fluxes against the immutable v3 receipt to 1e-8 and equivalent-response counterexamples to 1e-10. A failed closure stops scientific interpretation until the source convention or implementation is resolved. Report every declared scenario's signed covariance, ionic interval and chi-square, and all six predictive statistics; their Gaussian tails are conditional diagnostics. No multiple-scan calibrated rejection threshold is claimed. Exact calibration counterexamples reject an assertion of absolute redshift/intrinsic-width identification without additional calibration, even if a fixed-LSF scenario fits better. Any nitrogen change remains observed-stage ionic and depends on ionization and unmeasured common calibration. Results are added only after independent pre-run design approval.

Executable freeze: `tools/jwst/native_local_identifiability.py`.

## Declared pilot results

PSF specialist approved the exact executable freeze `0fb32c4` before outcomes. The twelve comparisons completed in 9.070 seconds through the fits and forward counterexamples, without downloads. The baseline reproduces the immutable v3 fluxes to numerical precision. This is an actual-nine-CAL row-response calculation using the previously independently validated, hash-checked RATE-derived compact noise/gain receipt; it does not re-read RATE pixels or redo their reduction.

| Declared alternative | Conditional chi-square / dof | Total N IV flux +/-sigma | Observed-stage ionic N/C 95% Fieller interval |
|---|---:|---:|---:|
| z=14.44, width=0, linear | 549.253 /623 | 22.646 +/-11.718 | [-0.158,9.905] |
| z=14.42 | 551.376 /623 | 18.313 +/-11.718 | [-1.217,9.504] |
| z=14.46 | 548.778 /623 | 26.174 +/-11.718 | [0.477,12.317] |
| Intrinsic FWHM=300 km/s | 549.268 /623 | 22.720 +/-11.744 | [-0.161,9.914] |
| Intrinsic FWHM=1,000 km/s | 549.430 /623 | 23.435 +/-11.996 | [-0.189,10.026] |
| Quadratic continuum | 548.576 /622 | 23.533 +/-11.768 | [-0.295,10.100] |

Flux units are 1e-20 erg/s/cm2; N IV is the total physical 1483+1486 doublet. All line amplitudes retain their signs and joint covariance. The quadratic improvement of 0.677 uses one extra coefficient and is not a detection of curvature. The bounded redshift contrasts shift N IV by -0.370/+0.301 of its baseline conditional sigma; the 1,000-km/s width and quadratic continuum change it by +0.067/+0.076 sigma. These are sensitivity contrasts, not random uncertainty components to add in quadrature.

The z=14.46 conditional ionic lower limit exceeds the ambient ionic reference 10^-0.60=0.2512, although its chi-square improves only 0.475 relative to baseline. A common assigned-centroid shift of +0.1295337% reproduces precisely the same forward response. The z=14.42 equivalent is -0.1295337%. Maximum response differences are 2.04e-17 and 1.25e-17 in extraction-design units. Thus changing this conditional branch can create an apparent ionic comparison without independently measured wavelength calibration; it cannot establish elemental enrichment. The published emission redshift is not an external independent calibration measurement.

The Gaussian intrinsic-width/unknown-LSF counterexamples close to 1.08e-19 for both declared widths. An unmeasured source LSF curve can absorb the intrinsic broadening exactly. The 300-km/s finite broadening direction and +/-1% generic-LSF direction have projected cosine 0.947, consistent with strong local confounding. Their projected plug-in SNRs are 0.0198 and 0.0167. The redshift contrast has projected SNR0.978; the unit quadratic coefficient has 4.366. These values and the stored singular values depend on the declared contrast scales and fitted baseline amplitudes; they are not invariant Fisher information, empirical power or calibrated bounds. In particular, the unit quadratic coefficient is a scale convention, not a measured continuum change.

All six held-out predictions remain statistically consistent under the fixed Gaussian transport. Baseline versus 1,000-km/s predictive chi-square changes are +0.195,+0.0127,+0.155 for groups03,05,07; none improves. Conditional tails span0.418–0.996. Three groups and pooled off-source noise calibration cannot bound shared wavelength, LSF, pathloss or reference errors. These controls do not establish empirical predictive coverage.

This experiment rejects absolute intrinsic-width or emission-redshift identification from these fixed-calibration families alone. It does not reject every physical broadening or continuum alternative. No tighter nitrogen constraint, new abundance, stellar polluter or cosmological conclusion follows. Relative to the corrected-noise baseline, the major unresolved measurement inputs remain the common wavelength assignment and source LSF, together with the empirical noise transport. The largest scientific uncertainties still include ionization fractions, He/O blending and C IV transfer. Further intrinsic-width grids are low priority until source LSF is calibrated; resolving the common centroid calibration or obtaining independent higher-resolution ion-stage/density diagnostics has more information value.

Reproduction in the locked environment:

```bash
OPENBLAS_NUM_THREADS=1 python -m tools.jwst.native_local_identifiability \
  --native-dir /path/to/pinned-nine-CALs
python -m pytest -q tests/test_native_local_identifiability.py \
  tests/test_native_rate_noise.py tests/test_native_row_response.py
```

The versioned JSON records every fit, full five-line covariance, signed ionic Fieller interval, all six held-out predictions, exact counterexamples, input hashes and plug-in diagnostics. Independent post-outcome review is required before publication.
