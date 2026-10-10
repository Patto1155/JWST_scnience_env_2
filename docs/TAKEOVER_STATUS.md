# JWST research takeover: verified current status

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
