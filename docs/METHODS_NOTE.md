# Methods note: controls that limited inference in an automated public-data campaign

Draft, 14 October 2026. This note synthesizes existing repository evidence; it
introduces no new measurements, data access or scientific grade changes. The
current scientific state is maintained separately in `docs/CLAIM_LEDGER.md`.

## Abstract

We examined documented failures in an automated astronomical research campaign
using public imaging, spectroscopy and time-series products. No new
astrophysical discovery survived the repository's verification requirements.
The recurring failures concerned incomplete selection, unmatched denominators,
training/validation dependence, unverified measurement coverage and source
calibration. Controls often invalidated an inference without disproving the
underlying object's physical existence. We distinguish an acquisition or
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

**Shared-photon comparisons.** For measurements made from shared photons,
Var(measured − published) = Var(measured) + Var(published) − 2 Cov(measured,
published). Thus a pull normalized by the sum of variances need not follow
N(0,1), even if both marginal error estimates are correct. A broad pull
population may indicate underestimated uncertainty, operator mismatch,
configuration effects or an inappropriate covariance model. Its width alone
cannot uniquely attribute an error scale factor to the published catalogue.
A narrow distribution can likewise reflect positive covariance rather than
conservative errors. A population remeasurement is a valuable consistency
check; independent-photon controls or validated covariance are required for
an empirical coverage claim. This algebraic limitation supplements the
shared-photon warning in `docs/KNOWN_ANSWER_TEST.md`.

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
noise fit, injection recovery, independent epoch, literature search or GOODS-N
holdout was accessed. No full quality gate, external-model audit or scientific
promotion was performed by this note's author. Previously reported controls
remain subject to independent review before merge.
