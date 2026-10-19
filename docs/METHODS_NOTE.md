# Methods note: controls that limited inference in an automated public-data campaign

Draft, 15 October 2026. This note synthesizes existing repository evidence; it
introduces no new measurements, data access or scientific grade changes. The
current scientific state is maintained separately in `docs/CLAIM_LEDGER.md`.

## Abstract

We examined documented failures in an automated astronomical research campaign
using public imaging, spectroscopy and time-series products. No new
astrophysical discovery survived the repository's verification requirements.
The recurring failures concerned incomplete selection, unmatched denominators,
training/validation dependence, unverified measurement coverage and source
calibration, selection on noisy flux and post-hoc acceptance criteria. Controls
often invalidated an inference without disproving the underlying object's physical existence. We distinguish an acquisition or
eligibility stop from a statistical null, numerical reproducibility from
independent observations, and ionic line constraints from elemental abundances.
These distinctions preserve useful negative results while preventing software
success from being reported as scientific validation.

## Evidence and limiting controls

All evidence paths below are relative to the repository root. Historical
measurements retain their original reduction and assumptions; they are not
rerun results of this note.

| Failure mode | Evidence | Control and bounded conclusion |
| --- | --- | --- |
| Incomplete dropout selection | `FINDINGS.md`; `HANDOVER.md` ending correction dated 2026-10-09 | Sky-footprint, aperture-validity and calibrated selection checks distinguish missing data from a covered non-detection. None of the 1,732 historical records has both required F090W/F200W coverage at the configured aperture-coverage threshold. All are untestable by that complete selection, rather than falsified objects. Synthetic positive, negative and absent-evidence controls check this distinction. |
| Unreproduced artifact-rate inference | `HANDOVER.md` ending correction; `docs/CLAIM_LEDGER.md` | The correction records that the historical approximately 15% single-epoch-only fraction was not reproduced because the archive was absent. Exposure identity, repeat coverage, depth and selection-function checks are necessary before non-repeat detections become artifact labels or rates. Cross-population artifacts-per-high-redshift-source comparisons lack matched denominators. Non-reproduction and unsupported extrapolation do not prove that the original numerical fraction is false. |
| Partly circular classifier validation | `HANDOVER.md` classifier retraining section; `research_output/artifact_classifier.json`; `research_output/injection_recovery.json` | Injection recovery exposed strong rejection of faint unresolved sources by the original morphology classifier. Retraining improved recovery for its injected population, but training and test injections share a generator. Held-out visits test visit transfer; they do not supply independent representative real-source labels or certify survey completeness. |
| Missing-coverage and injection-recovery traps | `docs/FINAL_RESEARCH_REPORT.md`; `docs/YSO_TIME_DOMAIN_PILOT.md`; `docs/SMACS1043_E2_INDEPENDENT_TEST.md`; `research_output/session_20261014/e2_photometry.json` | Source-coordinate coverage checks reject inference from detector-wide wavelength spans or off-array zeros. The imaging injection pilot exposes morphology, association and assumed count-gain dependence; released mosaic variance does not identify native source-Poisson transport. SMACS 1043 persists after a new raw reduction, but three of four frozen structured-light gates and the separate-source centroid gate fail. Injection recovery and another epoch were not run. Persistence alone does not identify a separate source, while gate failure does not physically reject the patch. |
| DUMMY MOS wavelength reference | `docs/KNOWN_ANSWER_TEST.md`; `research_output/session_20261014/c_crds_verdict.json`; `research_output/session_20261014/c_crds_reference_header.txt` | The actual CRDS applicability chain and reference header establish that `jwst_1596.pmap` still selects `jwst_nirspec_wavecorr_0004.asdf`, marked DUMMY. A newer mapping number or a fixed-slit reference is not an empirical MOS calibration. Absolute wavelength uncertainty remains unresolved; a future spectroscopic inference must declare a source-relevant zero-point nuisance prior and marginalize it rather than silently substitute a reference. This note has not estimated that prior. |
| Incorrect known-answer comparison criterion | `docs/KNOWN_ANSWER_TEST.md`; `research_output/session_20261014/c2_known_answer.json` | The historical current-release comparison recovers 28.3642 ± 0.7192 against 29.4971 ± 0.6002, in units of 10^-19 erg s^-1 cm^-2. Dividing only by the published error gives 1.8876; using the specified combined-error discrepancy gives 1.2094. The latter passes the session's less-than-two criterion, but that criterion was adopted after the result was known, and for shared photons the combined-error denominator ignores positive covariance and so leans toward passing (see the safeguard below). It is therefore not passing evidence. A dated amendment must preserve the original design and historical verdict. This released-1D check does not satisfy the raw end-to-end calibration requirement. |

## Interpretation safeguards

**Selection on noisy catalogue flux.** A catalogue-selected comparison is
conditional on the selection measurement. In
`data_pipeline/calibrated_population.py`, `select` requires
5 <= published_flux / published_error <= 30 for the same line whose refit is
compared to the catalogue. Near the lower cut, positive catalogue noise can
admit intrinsically fainter lines. A second measurement that does not share all
that noise can then lie below the selected catalogue flux even if its estimator
is unbiased before selection. The upper cut also conditions the population.
This is a possible explanation of an estimator discrepancy, not a demonstrated
cause of the deficit documented in `docs/AUDIT_20261014.md`. Different extraction,
prior, calibration or fitting choices remain alternatives. Field comparisons
also require matched S/N and selection distributions before a field effect can
be inferred.

Write S = published_flux / published_error and R = refit / published_flux.
An approximately fixed displacement of k catalogue error units gives
R approximately 1 - k/S and hence log R approximately -k/S when k/S is small.
Such a 1/S dependence can arise from selection near a threshold or from an
estimator displacement; it is not a unique signature of either. In a different
regime, Gaussian flux noise with fixed variance sigma² and a smooth local
prior p(F) proportional to F^(-alpha) gives a leading posterior correction
E[F | f] - f approximately -alpha sigma²/f. The corresponding fractional
correction scales as 1/S². That expansion need not describe a threshold edge,
heteroscedastic errors, a different flux distribution or partially correlated
estimators. A chosen 1/S or 1/S² regression is therefore a descriptive model
until its assumptions and frozen predictions survive independent controls.
Because R and S both contain published_flux, plotting them against each other
also creates mathematical coupling without identifying a physical cause.
This note has not reproduced or fitted either S/N law.

For other JADES users, record whether selection used the line being compared,
the cuts, extraction and release versions, and the treatment of failed or
negative fits. Selection on a different line can reduce the direct
same-line selection-noise dependence, but intrinsic line correlations, shared
continuum, calibration and spectral noise need not disappear. Test that
independence rather than assuming it. Freeze the selection and prediction
before reading new comparison spectra; retain nondetections and failures.
Paired log ratios require positive fluxes, so any exclusion or alternative
signed-flux statistic must also be declared before outcomes. Report source
counts and use an object-level bootstrap when multiple lines share an object;
report both SD and MAD and a sign test with its dependence assumptions.

**Shared-photon comparisons, including partial sharing.** For measurements
made from shared photons,
Var(measured - published) = Var(measured) + Var(published) - 2 Cov(measured,
published). Thus a pull normalized by the sum of variances need not follow
N(0,1), even if both marginal error estimates are correct. The released-1D
operator and JADES catalogue use different extractions of partly shared
observations: they are neither independent-photon measurements nor identical
estimators. The covariance can therefore be intermediate and remains
unmeasured here. Scatter close to a quadrature estimate would not establish
zero covariance, since selection, estimator mismatch and calibration can also
contribute. Do not use the quadrature denominator as an acceptance or coverage
criterion for this comparison.

A broad pull population may indicate underestimated uncertainty, operator
mismatch, configuration effects or an inappropriate covariance model. Its
width alone cannot uniquely attribute an error scale factor to the published
catalogue. A narrow distribution can likewise reflect positive covariance
rather than conservative errors. A population remeasurement is a valuable
consistency check; independent-photon controls or validated covariance are
required for an empirical coverage claim. Paired differences or ratios and
object-level empirical scatter describe agreement without pretending that
unknown covariance is zero. This limitation supplements the warning in
`docs/KNOWN_ANSWER_TEST.md` and the conditional scope in
`docs/CALIBRATED_KNOWN_ANSWER.md`.

**Post-hoc acceptance criteria.** The historical known-answer comparison
illustrates why an arithmetically correct recomputation does not repair a
criterion chosen after seeing the answer. As recorded in
`docs/AUDIT_20261014.md`, the combined-error discrepancy of 1.2094 used a
post-hoc criterion and ignores shared-photon covariance. It supplies no passing
evidence. Preserve the original design, result and verdict; date and label
exploratory amendments, then commit a new selection, statistic, null,
threshold, multiplicity treatment and numerical prediction before an
independent test. An unused holdout cannot retroactively validate an amended
interpretation of an already failed frozen test.

**Injection recovery as an operator control.** Inject known fluxes across
the relevant S/N range into predeclared line-free windows of committed spectra
and run the unchanged estimator, with a frozen recovery prediction, sampling
plan and acceptance criterion. Preserve signed recoveries and failed fits;
record input-flux/S/N definitions, nuisance parameters, window eligibility and
noise-generation assumptions. This tests the operator conditional on those
spectra, profiles and noise assumptions. It does not by itself reproduce
catalogue selection: that requires paired measurements with the appropriate
noise correlation and the actual eligibility cut, or an independent-selection
control. Recovery flat at unity would constrain the tested operator bias; it
would not prove that selection caused the catalogue discrepancy. Biased
recovery would implicate the tested estimator/background combination without
uniquely identifying its mechanism.

The current `marginal_fit` in `data_pipeline/calibrated_population.py` uses
signed unconstrained Gaussian linear flux estimates at each of 41 offset by
41 width nodes, followed by likelihood-weighted marginalization; it does
**not** impose positive flux. The existing synthetic negative-line control in
`tests/test_calibrated_population.py` explicitly checks signed recovery. A
positivity-induced low-flux explanation therefore has a false premise for
this operator. Marginalization, finite nuisance priors, continuum mismatch and
non-Gaussian or correlated noise can still require testing. Injecting only
the fitted Gaussian profile under the same diagonal Gaussian noise model can
check numerical recovery while missing real profile, LSF or covariance
mismatch. Adding lines to released spectra also does not recreate native
source-Poisson transport, extraction/pathloss calibration or independent
photons. This note supplies no new injection experiment or verdict between
catalogue selection and operator bias.

**Improper amplitude priors in nuisance marginalization.** The unchanged
operator weights nodes using a coefficient-integral evidence term containing
minus one-half the log determinant of the linear precision matrix. A flat
improper amplitude prior can favour nodes with less constrained amplitudes,
including wider line templates. The [15 October cross-lineage audit](https://github.com/Patto1155/JWST_scnience_env_2/pull/86#issuecomment-6186297641)
found a small additional upward low-S/N response from this term in independent
synthetic controls. Its size depends on the tested profile and noise assumptions;
it is not an established correction to real catalogue fluxes. Together with
width marginalization, it disfavours a fitter-reads-low explanation for the
Gaussian profiles tested, while leaving other profile/LSF mismatch unresolved.
No frozen estimator, prior, outcome or scientific grade is changed here.

**Spectral and temporal coverage.** The SPHEREx source measurements documented
in `docs/RESEARCH5_SPHEREX_REVIEW.md` assemble channels observed at different
times; they do not establish simultaneous complete 0.75–5 micrometre spectra.
Channel time stamps, actual source wavelengths and bandpass-support unions
matter for variability and ice-band depth. A wavelength convex hull can
bridge unobserved gaps. In the previous six-YSO design, AA Tau supplies only
one campaign meeting the wavelength requirement, while the other five targets
lack sufficient potential matched controls. No variability statistic was
measured; this is a completed feasibility stop for that design, not evidence
of constant brightness or constant ice depth.

**Conditional spectroscopy.** `docs/MOM_EMPIRICAL_NOISE_TEST.md` records an
acquisition-cap stop; the follow-up `docs/MOM_CALIBRATED_CHALLENGE.md` then
produced a fresh conditional interval [0.10155, 13.48043]. That interval is
non-discriminating: it contains both the ambient reference and the headline
boundary, its lower end depends on the interval method, and the assumed
wavelength prior decides ambient membership. Both MoM-z14 intervals are
conditional observed-stage ionic constraints, not elemental N/C. Source noise, wavelength, line-spread function and
ionization corrections must remain explicit. Synthetic Gaussian coverage
and successful range-reader tests validate specified numerical contracts,
not observed source-noise transport.

## Reproducibility and limits

Evidence-path existence and the promotion-contract linter were checked for
this draft. Their success establishes document integrity, not correctness of
the cited measurements. No new outcome data, raw reduction, catalogue draw,
noise fit, injection recovery, independent epoch, literature search or new
heldout outcome was accessed. Existing narrative evidence, operator source and
synthetic test source were read; no population JSON outcomes or spectral arrays
were opened. No full quality gate, external-model audit or scientific
promotion was performed by this note's author. Previously reported controls
remain subject to independent review before merge.
