# JWST verified research status

Verified 2026-10-14 governance realignment. **No new astrophysical result
has survived verification in this repository.** Reversals and failed gates are
preserved, not converted into discoveries. Current grades belong only in
`docs/CLAIM_LEDGER.md`; older reports below retain historical measurements and
assumptions. The 2026-10-09 ending correction in `HANDOVER.md` controls its earlier
artifact/selection interpretations.

## 19 October audit clarification

PR86's cross-lineage audit reports no blocking merge findings. Its independent
synthetic mechanism check and the committed real-background controls show an
upward low-S/N response for tested Gaussian profiles, disfavoring the stated
fitter-reads-low H2 in that scope. Catalogue selection is not thereby established;
untested profile/LSF mismatch and other measurement effects remain unresolved.
The improper-amplitude-prior evidence term can contribute to the upward response.
No operator repair, MoM correction or scientific grade promotion follows. See
[FLUX_DEFICIT_DIAGNOSIS.md](FLUX_DEFICIT_DIAGNOSIS.md) and the linked audit.

## 15 October flux-deficit diagnosis

No scientific grade changes. The 29 committed comparisons reproduce
log(fit/published) = -0.04228 - 0.96130/catalogue-SNR; the overall median
ratio is 0.88919 (object-bootstrap 95% CI [0.83600, 0.91662]). Both the
inverse-SNR and inverse-square slope intervals include zero. The inverse-SNR
intercept CI [-0.17408, 0.08923] includes zero; the inverse-square intercept
CI [-0.17879, -0.00811] does not. Field differences are not thereby proved
to be entirely S/N differences. The frozen fitter is signed, without the
positivity restriction assumed in the incoming handover.

The 1,000 frozen real-background injections (200 at each true S/N5,7,10,15,25)
do not follow either frozen control curve. At S/N5 and7 the absolute mean
recoveries are approximately1.275 and1.088, above unity; the secondary
baseline-subtracted responses are also upward. Two higher-S/N trials have
extreme numerical outputs and are retained. This is a stability warning for
allowed windows, not a calibration pass or evidence for catalogue selection.
The control fails to reproduce H2's proposed downward response, but cannot
exclude all fitter/prior mismatch. H1/H2 causal attribution stays unresolved;
see [the diagnosis](FLUX_DEFICIT_DIAGNOSIS.md).

Both per-row southern holdout predictions were committed before access.
The first HEAD was rejected by the configured proxy CONNECT tunnel (403),
as were the independent-line catalogue preflight and G235H metadata query.
No new science/catalogue/metadata response bodies were acquired. All 15
southern outcomes remain unopened; GOODS-N is spent and was not reacquired.
B/C cannot adjudicate H1 versus H2 or the grey-scale follow-up trigger.
D spends zero and remains deferred; product/continuum/pathloss/Jacobian causes
are not excluded. G235H public availability remains unresolved. SMACS closes
this bounded PSF attempt because retained inputs do not certify unsaturated
stellar identity and a held-out PSF control. No operator fix, raw-known-answer
pass or MoM correction follows. See [the holdout receipt](FLUX_HOLDOUT.md),
[independent selection](INDEPENDENT_LINE_SELECTION.md),
[other arms](FLUX_OTHER_ARMS.md), and [methods](METHODS_NOTE.md).

## 14 October calibrated-answers follow-up (awaiting cross-lineage audit)

No grade is promoted. A fresh MoM signed ionic N/C moment-Fieller set is
[0.10155, 13.48043], including ambient 0.25119 and the headline boundary 2.51189.
The frozen practical noise diagnostics pass, but source coverage, raw known-answer
calibration and the assumed geometric wavelength-prior distribution remain
unvalidated. This neither replicates nor refutes elemental enrichment, and the
cross-lineage audit found the PRISM arm cannot discriminate: the wavelength prior
decides ambient membership and no PRISM analysis can test the headline boundary.
**The PRISM arm is paused until G235H data.** See
[MOM_CALIBRATED_CHALLENGE.md](MOM_CALIBRATED_CHALLENGE.md) and
[AUDIT_20261014.md](AUDIT_20261014.md).

The amended 1.2094 combined-error comparison is **not passing evidence**: the
criterion was set after the result was known, and shared-photon covariance makes
a combined-error pull lean toward passing. Under the original published-error
criterion it is 1.89σ, in the same direction as the population deficit below. Raw end-to-end recovery remains blocked on contributor/operator/prior
prerequisites. Released-1D training covers 15 GOODS-S lines; the sole authorized
GOODS-N confirmation covers 14/15 lines and fails its frozen descriptive N(0,1)
mean/SD prediction (mean -0.97093, SD 0.48843). Shared photons and operator/prior
mismatch prevent identifying a published-error scale. What the test does show is a
replicated systematic deficit: this operator's fluxes are about 8–15% below the
JADES catalogue in both fields (13/14 GN pulls negative). Finding its cause is
now the first calibration task. The southern fallback
spectra remain unopened. Earlier sealed-GOODS-N statements below are historical;
only B accessed the northern confirmation after committing the GS prediction.
See [CALIBRATED_KNOWN_ANSWER.md](CALIBRATED_KNOWN_ANSWER.md).

SMACS compact replay preserves the failed null decisions. The measured point-PSF
prerequisite is absent; all 1,704 frozen injection trials remain unrun. Epoch
metadata timed out, so absence of another epoch is not established. The claim
stays Unconfirmed lead; see [SMACS1043_COMPLETION.md](SMACS1043_COMPLETION.md).

The new fixed 13-target pole-field YSO screen closes without science acquisition:
three northern targets fail the necessary daily-frame bound; southern source
coverage and controls remain unresolved. Missing catalogue associations are not
zero infrared flux or a variability null. See [YSO_POLE_FEASIBILITY.md](YSO_POLE_FEASIBILITY.md).

[DATA_BUDGET.md](DATA_BUDGET.md) records every arm's final charge; all are within
allowances. [METHODS_NOTE.md](METHODS_NOTE.md) preserves six documented inference
failures. The session report records freeze chronology, validation and not-run
work. Different-family audit is still required before merging the session PR.

## 14 October executed calibration and acquisition evidence

The separately frozen current-release JADES known-answer check recovers
28.3642 +/- 0.7192 versus 29.4971 +/- 0.6002 (1e-19 erg/s/cm2): it fails
at the published 1-sigma tolerance and passes at 2 sigma. The original-release
check is blocked at the tested endpoints. Current applicable MoM wavecorr is
still the hash-identical DUMMY reference. Raw end-to-end and source-specific
spectral calibration remain unmet; no spectral grade is promoted. See
[KNOWN_ANSWER_TEST.md](KNOWN_ANSWER_TEST.md).

The fresh MoM empirical-noise attempt consumed 299,991,808 response-body bytes
and stopped at its pilot allowance during overfetch. No fresh noise calibration
or N/C interval was computed. Astropy's subsequent ASDF KeyError is a parser
side effect, not evidence that archive ASDF metadata is absent. The old interval
remains historical/conditional. An optimized reader has synthetic tests only;
see [MOM_EMPIRICAL_NOISE_TEST.md](MOM_EMPIRICAL_NOISE_TEST.md).

SMACS E1 stopped because the required current dark is 4,378,878,720 bytes.
The user approved a separately frozen 6 GiB E2 allowance after a space check.
The actual JWST 3.0.0 / CRDS jwst_1596.pmap raw reduction completed: the patch
persists, but three of four frozen structured-light null gates and the separate
source-centroid association gate fail. Injection recovery was not run after
these required gates failed. This leaves the physical-source claim Unconfirmed,
not physically rejected. Conservative cumulative transfer reservations are
5,826,074,168 of 6,442,450,944 bytes, including the failed transfer; bounded
resume recovered from synchronization-related ENOSPC. Raw/reference files were
deleted and about 25 GB free remained. See
[SMACS1043_E2_INDEPENDENT_TEST.md](SMACS1043_E2_INDEPENDENT_TEST.md).

The frozen six-YSO cohort is not estimable under its matched-control requirement.
AA Tau has actual W1-scope channel counts 7/8/7 across three campaigns: only one
passes the wavelength component, so no qualifying repeat pair exists. The other
five targets fail the minimum control count even before further screening.
No W1 flux, variability statistic, or NEOWISE/ZTF outcome was measured. DDE 54
has no new post-August QR3 exposures; the older QR2 frames do not satisfy its
unchanged W1 contract. This is a coverage/control stop, not a variability null.
See [YSO_TIME_DOMAIN_PILOT.md](YSO_TIME_DOMAIN_PILOT.md). GOODS-N remains sealed.

## Live questions and stop rules

- DDE 54: historical IR modulation is credible; recurrence and SPHEREx W1 state
  remain unconfirmed because the frozen coverage/two-visit contract is unmet.
- MoM-z14: conditional ionic N/C includes the ambient reference with the stated
  residual-noise model. Empirical noise and a known-answer calibration test are
  required before stronger spectroscopy claims; this is not elemental abundance.
- SMACS 1043: persistent patch, unstable flux assignment and failed scene-model
  residual checks. Downgraded from historical Candidate to Unconfirmed lead until
  claim-specific null/injection/independent-repeat controls exist and pass.
- Source 46: identity and SED explanations remain unresolved. This session's
  selected fourth track is the preregistered YSO time-domain direction; unallocated
  source46 work remains pending, not implicitly closed.
- J111855 failed its original narrow-control gate. KIC 8164262 evolution is null.
  CHIME temporal-plasma stopped on insufficient qualifying repeated events.
  JADES 7496/54611 physical anomaly interpretations are rejected.

## Session governance

Only STATUS and CLAIM_LEDGER track scientific state; the lead owns their grades.
Freeze designs in commits before new outcomes; edits after access are void.
GOODS-N remains sealed. Pilots <=300 MB, original imaging <=1.5 GiB, subject to
specific campaign allocations. A user-approved, separately frozen SMACS E2
exception permits 6 GiB including its prior transfer charge; all other pilots
retain their caps. Delete raw downloads after reduction and never
commit them. Same-lineage reviewer agreement is not independent corroboration.
Runtime quotas default to zero; supervisor escalation only queues a statistical
gate. Software health uses `python scripts/quality_gate.py`; SKIP is not PASS.
Known data-absent skips remain explicit and do not validate pixels or calibration.

The recorded 767-pass/3-skip audit is a starting receipt, not an execution claim
for this worktree. The integrated validation receipt and original frozen-design
history are linked from [SESSION_20261014.md](SESSION_20261014.md). Computational
replay reproduces the released-data fit, SMACS compact control decisions and
YSO W1-scope arithmetic; it is not independent astrophysical corroboration.
Historical worker peak memory, full-field astrometry replay and complete early
metadata-transfer accounting remain unverified.

# Historical baseline and executed campaign evidence

## 12 October new-observable campaign

[Research5](RESEARCH5_CAMPAIGN.md) extends the search to NEOWISE/ZTF,
SPHEREx, TESS and SDSS/DESI through four rounds and independent numerical
reviews. DDE 54 has robust historical infrared modulation, but the selected
four-year recurrence is unconfirmed. Its frozen optical median-state contrast
is null despite substantial optical variability. Eleven August 2026 SPHEREx
extractions provide a partial spectrum; inadequate W1 coverage and one
observing campaign prevent the frozen broad-band confirmation.

A 36-galaxy coronal-line screen has no full-gate discovery. J111855 remains an
unconfirmed weakening lead with flagged baseline pixels and weak comparison
lines. Eight TESS epochs extend KIC 8164262's amplitude baseline without
establishing evolution. The earlier GOODS-N holdout remains unopened.
No new astrophysical discovery is established; the campaign report preserves
actual measurements, failed gates and specific next observations.

## 12 October multi-round discovery continuation

See [the research4 campaign](RESEARCH4_CAMPAIGN.md) for the subsequent frozen
designs, actual-data pilots and independent checks. A new twelve-target GOODS-S
paired-grating experiment failed its predeclared usable-sample threshold; an
independent integration method corroborated the stopping decision. A repeatable
configuration contrast in source 54611 remains a measurement discrepancy, not
an intrinsic anomaly. A separate CHIME/FRB Catalog 2 temporal-plasma pilot
retained only 29 qualifying events with at most 4 per repeating source, failing
its six-event/six-source gate before any covariance was computed. GOODS-N remains
unopened. No astrophysical discovery was established and the earlier physical
inference limits remain in force.

## 12 October discovery continuation

[The discovery-pilot checkpoint](RESEARCH3_DISCOVERY_PILOTS.md) records the new
target search, independent remeasurement and stopping decisions. The strongest
selected JADES Balmer-ratio lead fails grating consistency; a second is
unconfirmed. GOODS-N outcomes remain unopened. A bounded relative-ion-response
test supports the existing finite-model observing forecast under modest gain
freedom, without establishing source calibration or abundance. The documented
NEXUS processed-data endpoint supplied no demonstrated independent post-study
epoch. No new astrophysical discovery is established. The 10 October evidence
and limitations below remain applicable.

## 10 October verified baseline

10 October 2026. This status supersedes the PR54 inference summary. The exact
incoming status and report are preserved in [TAKEOVER_BASELINE_PR54.md](TAKEOVER_BASELINE_PR54.md)
and [FINAL_RESEARCH_REPORT_PR54.md](FINAL_RESEARCH_REPORT_PR54.md). Live master
initially equaled `379ff35786aff31535335bbe7d1de114f91dd3c4`; ancestry passed,
with no intervening changes. [Current full report](FINAL_RESEARCH_REPORT.md)
gives inputs, assumptions, rejected hypotheses, executable reproduction and
ranked next experiments.

**No new high-redshift source, elemental abundance, stellar polluter or
cosmological discovery has been established.** Eight specialists worked on
separate branches through dependency-driven pilot, revision and integrated
assessment rounds. Authors were not sole scientific validators. Ownership,
budgets and stopping rules are in [the protocol](RESEARCH2_PROTOCOL.md).

## What changed scientifically

- Actual nine-RATE/nine-CAL data and exact JWST 2.0.1 source reject the older
  CAL-variance demixing assumption: target ERR does not include subtracted
  donor noise. Version 3 propagates signed donors, measured calibration gains
  and full covariance, then recomputes off-source transport once. The empirical
  scale is 1.427616; applying the old 2.220621 as well double counts donor noise.
- Original-wavelength generic-point total N IV is 22.646±11.718 in
  `10^-20 erg/s/cm²`. The conditional observed-stage ionic N/C 95% Fieller set
  is [-0.158,9.905], admitting the stated ambient ionic reference. Formal noise
  alone gives [0.429,7.762], so the residual-noise assumption remains decisive.
  This is neither elemental N/C nor empirically certified source coverage.
- Signed known-spectrum injections reject the old positive-only mean response.
  Full-row wavelengths make a small conditional change. Three independent
  RATE groups cannot identify shared line-shaped systematics. Local redshift
  changes are exactly confounded with common assigned-centroid shifts; unknown
  source LSF absorbs tested Gaussian intrinsic widths. No tighter abundance
  follows from selecting those calibration branches.
- Public author PIXTAB/settings reproduce its published coadd numerically,
  while reused sky rows expose dependent group slices. The exact-date current
  CRDS selector still selects the same DUMMY reference. No empirical absolute
  wavelength or source LSF calibration has been obtained.
- Complete Cloudy C23.01 now supplies twenty independently equilibrated
  composition/environment controls, 480 fresh RATE fits and six held-out
  predictions. The primary family minima differ by only 1.982 chi-squared;
  ordinary composition remains conditionally adequate. Nitrogen-only rescaling
  fails, while ionizing-environment degeneracy remains material. All original
  model outputs are durably preserved with exact hashes.
- Later CAPERS same-position release products contain no 2.15–3.20 micron
  UV diagnostic coordinates in SPEC, PIXTAB, official X1D or rectified S2D.
  This rejects a gap due solely to the 1D extraction mask. It is not zero flux,
  an upper limit, absence in all raw pixels, or proof that new time is necessary.
- The geometry-frozen injection pilot demonstrates morphology, association
  and count-gain dependence. Actual WHT/VAR/header audits show that released
  mosaic variance does not identify native source-Poisson transport. Survey
  completeness, contamination and population/cosmology odds remain unavailable.
- Source254 retains its blue counterpart. Source98 remains blended; every
  tested red neighbor/background family fails the held-out residual gate.
  Source1043 remains a persistent patch with unstable flux assignment. Stop
  classification from these inadequate fits.
- Source46 rejects tested Bobcat multiplicities and the broader finite
  Flame/Skimmer family. Actual F410M rejects negligible-F410/F444-only excess;
  overlapping passbands still permit a single line under the declared tolerance.
  Its identity and continuum/line/multiplicity explanation remain unresolved.
- The merged-model forecast favors N III with a C III anchor for
  conditional finite-family discrimination: narrow G235H matched bundle SNR
  about 11 for expected squared separation 9. It supplies no posterior-weighted
  information gain or absolute exposure time; source-specific coverage and
  response/sensitivity calibration are required.

## Reproduction and release evidence

The incoming exact-lock gate reproduced **579 passing tests and three explicit
skips**. Original GOODS selection and native extraction were reproduced from
actual restored, hash-verified pixels. Compact likelihood replay is separately
labeled. Historical version1/version2/336-fit artifacts remain intact.

The final exact-lock quality gate passes **719 tests, with three explicit skips**
(722 collected, zero failures/errors). The incoming 579/3 result is preserved.
The same two visual-runner tests lack their expected repository-layout archive
files; the third requires the separately pinned author Cue weights. These skips
do not count as actual-pixel validation. Actual scientific pixel runs have their
own receipts. [Final validation](../research_output/research2_final_validation.json)
records all 65 installed versions, immutable tested code, JUnit/log identities,
independent numerical reviews and successful CI heads for PRs 55–79.

The canonical gate preserves 46 reviewed artifacts and all 261 historical
PR54 research-output blobs. The final independently fetched remote-tree audit is
in [the release receipt](../research_output/research2_release_integrity_final.json).
CI for PR79 initially failed a one-ULP floating-point exact-equality assertion; the
independently validated numeric tolerance preserves exact labels/nulls/structure.
Its corrected CI run 298 passes, with no changed scientific output.

New-transfer accounting is **1,334,355,625 bytes conservatively charged**:
1,290,651,149 exact recorded body bytes plus 43,704,476 in upper-bound categories.
This is 1.243 GiB against the 2 GiB cap, leaving 813,128,023 bytes. Separately,
2,073,005,957 bytes of unique previously pinned products were restored; historical
restoration retry wire totals are not fully instrumented. The immutable earlier
ledgers remain historical; [v3](../research_output/research2_download_ledger_v3.json)
is the authoritative complete ledger.


Reports and manifests retain identities, raw-output preservation, runtime and
convergence, independent reviews and focused merged PR links. A truncated PR65
candidate artifact was repaired exactly in PR67; publication now verifies every
remote Git blob, and the final remote-tree audit verifies JSON and historical
artifact identities in addition to CI.

## Highest-value next work

1. Recover or independently calibrate source-specific geometry, wavelength,
   LSF/pathloss and source-versus-control noise transport; inspect remaining
   raw CAPERS trace geometry before asserting an archive limitation.
2. Obtain ion-stage/density/He–O observables that survive normalization and
   attenuation degeneracy, with source-specific detector coverage and an
   instrument-specific sensitivity calculation.
3. Recover the native count/resampling operator and labeled representative
   held-out cohorts before enlarging injection surveys or evaluating cosmology.
4. Use independent source46 data to resolve its specific SED ambiguity;
   improve scene/background information before further 98/1043 classification.

Expanded conditional grids, model-member counts and candidate counts alone
cannot resolve these missing likelihood inputs.
