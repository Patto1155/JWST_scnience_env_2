# Verified scientific continuation, 10 October 2026

This report supersedes the PR54 inference summary while preserving its historical
contracts in `FINAL_RESEARCH_REPORT_PR54.md`. No new high-redshift source, elemental
abundance, stellar polluter or cosmological discovery is established.

## Starting state and actual reproduction

Live master was fetched before any local scientific claim was used. It was exactly
`379ff35786aff31535335bbe7d1de114f91dd3c4`, the supplied PR54 handover; ancestry
verification passed and there were no subsequent changes. The prescribed status,
handover, final report, instructions/protocol, validation and coordinator review
were read in order. Existing working copies were preserved; eight named specialists
worked in isolated branches with separate numerical/data validators. The ownership,
budgets, questions and stopping rules are recorded in `RESEARCH2_PROTOCOL.md`.

Python 3.12.14 and all 65 distributions match `requirements-research.lock`. The incoming
quality gate reproduced 579 passing tests and three explicit skips. All 68 incoming
scientific artifact identities and 210 code/configuration identities matched.
The independent 336-fit replay differed by at most 2.86e-10 in flux and 1.79e-11 in
scaled covariance, consistent with solver roundoff rather than byte identity.

All 13 selected original mosaics and nine CALs were restored and whole-file hashed.
Actual GOODS pixel selection reproduced its CSV and metadata byte for byte:
1,134 proposals, 891 untestable, 236 failures, seven first-screen survivors and
0.962808 arcmin². Native extraction arrays reproduced from actual CAL pixels.
Deep photometry reproduces all scientific numerical fields in the inherited
default-thread environment, with 84 acquisition-metadata differences. The
independent one-thread run has 1,850 numerical and 84 metadata differences;
the largest is 0.0452343 nJy in a degenerate source 254 continuum amplitude.
The largest source 98 band-flux change is 2.21e-6 nJy. The source 46 morphology
parameter that moved from 0.224974 to 0.222812 is axial ratio, not Gaussian width.
Compact NPZ replays are
explicitly distinguished from these actual-pixel runs.

## Spectral measurement: a rejected error contract and its replacement

Public author PIXTAB, extraction settings and contributor information were found.
The table has 56,734 rows including 36,520 negative-profile rows. Applying its own
read-noise weights, y[-3,3] extraction and pathloss once reproduces 467 finite coadd
bins to about 1e-10 µJy and all 473 contribution counts. Its reused background rows
make author group slices dependent. It uses an older pipeline/context than the
current public CALs; these reductions are not independent datasets and are not
pooled. This closes the public-settings accessibility blocker without reproducing
the entire published likelihood, source masks or instrumental response. Our
RATE-based implementation is an independent reduction alternative. A difference
from the published analysis neither reproduces nor falsifies it without its
complete source-specific settings and calibration contract.

Known-spectrum injections exposed omitted negative-nod spectral mixing in the
earlier mean response: an injected total N IV 20 was recovered as 13.934 under the
positive-only design. A signed contributor response restores exact closure.
Using every detector row's own wavelength changes fitted coefficients by less
than 0.052 conditional sigma; under the declared morphology, row averaging is a
smaller effect than covariance or unknown instrumental calibration.

Nine newly selected RATE images and exact JWST 2.0.1 pipeline source establish the
decisive variance result. NRS_MSASPEC background subtraction changes SCI and DQ
but leaves the target's ERR/variance arrays unchanged. The historical equation
that treated CALERR as target-plus-quarter-donor variance is therefore false for
these products. Actual target-only variance closure is within 5.85e-7 relative;
equal-half donor SCI subtraction plus measured gain reproduces CAL within
1.74e-6 CAL sigma. Historical artifacts are retained as conditional controls.

Version 3 propagates all signed raw contributors and their gain differences into
full covariance and the source/ghost mean response. It recomputes the empirical
off-source scale against donor-inclusive variance: 1.427616 instead of reusing
2.220621. Reusing the old scale would count donor variance twice. Independent
raw-pixel covariance, 12 likelihoods/Fieller sets, 12 heldouts and new-seed 5,000
Gaussian injections pass; conditional 95% coverage is 94.80–95.18%. This is fixed
observed-variance Gaussian coverage, not calibrated empirical source-Poisson coverage.

The original-wavelength generic-point reference gives total N IV 22.6461±11.7184
in units 10^-20 erg/s/cm². Observed-stage ionic N/C is 3.06015 with signed conditional
95% Fieller interval [-0.158243,9.90503], admitting the stated ambient ionic reference
10^-0.60. Formal photon/read/independent-flat noise alone gives the narrower
[0.4286,7.7620] interval and excludes that reference. The empirical noise assumption
therefore controls the conditional enrichment tension. Negative interval endpoints
represent signed measurement uncertainty, not negative physical abundances.

Three disjoint RATE groups test differential consistency but cannot measure an
arbitrary shared line-shaped systematic: it is exactly confounded with source
flux. Off-source covariance transport is an assumption about source pixels.
Recorded flat variance contributes little diagonally, but arbitrary correlation
can contribute up to 4.02% of formal N IV variance; unrecorded common systematics
remain unbounded. DUMMY wavelength corrections remain sensitivity experiments.
Source-specific morphology/pathloss, LSF and absolute wavelength calibration are
not established by the closure tests.

## Bounded redshift, width and continuum identifiability

Six full fits and six held-out comparisons use the merged RATE likelihood.
Redshift 14.42/14.46 changes N IV by -0.370/+0.301 conditional sigma; the
z=14.46 ionic interval excludes the ambient reference but improves chi-squared
by only 0.475. A +0.12953% common shift of assigned line centroids reproduces that
forward-response change exactly, with detector wavelengths, continuum and
units held fixed. It is not a proof for dilation of the full calibrated grid. Unknown Gaussian instrumental width likewise absorbs the
tested intrinsic broadening exactly. These are explicit confounding examples,
not fitted calibration errors. Intrinsic 1,000 km/s width and quadratic continuum
change N IV by only +0.067/+0.076 sigma, with no held-out width improvement.
This pilot provides no absolute-redshift, intrinsic-width or tighter elemental
abundance identification.

## Complete composition models

Cloudy C23.01 was acquired publicly and fully pinned, including atomic provenance.
A first engineering run accidentally applied metallicity twice; independent review
rejected it. Its outputs are preserved and excluded. Corrected inputs verify actual
C/N/O abundance saves, all 14 UV components and 29 total saved line entries (including five blends),
intrinsic/emergent units, multiplet sums and convergence. Missing or incomplete
outputs are never treated as zero. Default Cloudy wavelengths above 2000 Å are air;
the fourteen UV measurement components are vacuum.

The ambient reference fixes log(N/C)=-0.60 at declared log(C/O)=-0.37,
with GASS10 background metals. This is not an unmodified scaled-solar C/N/O
pattern. The paired experiment changes nitrogen by +1 dex and recomputes thermal
balance. H+ weighted temperature falls 13,462.39→13,177.67K. N IV/N III increase
7.825/8.784 rather than 10; C IV/C III/He+O change 0.784/0.885/0.888. Nitrogen-flux
rescaling is rejected as a shortcut in this declared physical setup. These
responses do not imply that the observed source has enhanced nitrogen. After
normalization to C III, enhanced/ordinary N IV, N III, C IV and He+O ratios are
8.842, 9.925, 0.885 and 1.003. Absolute line-response changes should not be
misrepresented as equally large changes in normalized abundance observables.

Four environmental runs hit the original 600-second cap; three more started
during exception unwinding and were interrupted, and twelve were unexecuted.
An existing supported LAPACK backend was validated against actual complete
outputs before retrying the unchanged 20-model pilot with two workers and 1,200 s
caps. Both backend controls match 58 printed line responses and five weighted
temperatures; small zone-profile differences and variable runtimes are recorded.
No universal speedup or bitwise thermal-profile identity is claimed.

All twenty declared models now converge under one pinned backend, after three
iterations. Eleven stop at the declared low electron fraction and nine at the
1,000 K temperature floor. These finite outer-boundary choices can affect
additional low-ionization predictions; they are not physical completeness of
all phases. H+ weighted temperatures span 10,240–17,111 K. Individual wall
runtimes are 323–584 seconds; 8,779.59 seconds is the sum of model wall times,
including reused controls, rather than parallel elapsed time or summed CPU.

All 140 original model files and the line list are preserved in an exact-hash
compressed archive. Original controls and capped failures are preserved separately.
Fresh coupling produces 480 fits across eight distinct measurement alternatives
and three screens, plus six training-only group predictions. Independent raw
thermal and direct constrained-GLS reviews pass at solver roundoff.

Under original wavelengths, generic point response and fresh empirical RATE
noise, the ordinary high-ionization model gives chi-squared 554.534 and the
nitrogen-enhanced/hotter-blackbody model 552.552: a difference of 1.982.
Ordinary composition remains conditionally adequate. Both model and screen
selection are finite sensitivities; different environmental winners prevent
attribution solely to nitrogen. Held-out predictive quadratics are ordinary/
enhanced 188.277/186.470, 209.011/212.121 and 157.503/154.851 for groups 03/05/07;
two improve and one worsens. They are conditional moment-matched diagnostics.

The normalized N IV/C III enhancement factor varies 6.322–9.531 across
otherwise paired controls, while ordinary N IV/C III varies by more than
200-fold across the declared environments. These finite ranges illustrate
ionization/thermal degeneracy, rather than supply an abundance interval or
prior distribution. The [complete pilot report](MOM_CLOUDY_PILOT20_REPORT.md)
records all alternatives, raw preservation and selected predictions.

The best ordinary environmental model illustrates the likelihood scope: its
profiled N IV prediction is about 1.06 while its unconstrained fitted total
is about 21.99±11.65 in the same flux units. Statistical adequacy under weak, correlated
constraints is not a claim that central observed line features are reproduced.
The bridge uses source-column wavelength responses; the independently tested
full-row response remains a bounded sensitivity, not empirical calibration.

Ionizing-spectrum, density, metallicity, attenuation and nitrogen controls remain
assumed families. No member counts are posterior odds. Selecting a best member over environments
and screens also changes the goodness-of-fit question; a nominal fixed-model
chi-squared tail is not a calibrated selected-family probability. Ionic N/C is not elemental
N/C; missing ion fractions, He/O blending and C IV transfer remain material.
Stellar yield or polluter inference is not identified before observational,
ionization and retention uncertainties are propagated.

## Source-specific archive coverage and calibration

An exact-date CRDS selector audit follows both the product context 1535 and
public current context 1596 to the same NRS_MSASPEC wavecorr reference:
`jwst_nirspec_wavecorr_0004.asdf`, SHA256
`869d4279137b1c7dea5e8bb4b4980d72fd0aa8423c87814050bfa710cd2b58f3`.
Its internal DUMMY/toy contract is unchanged. Updated context numbers and
matching reference filenames alone do not establish empirical calibration.

A later CAPERS release has a source only 0.03058 arcsec from the MoM position.
Position coincidence is a useful association lead, not proven source identity.
Its actual SPEC and all 46,519 PIXTAB rows cover roughly 3.94–5.50 microns,
with zero UV diagnostic rows. Shared background values connect nominal author
groups; group slices cannot be pooled as independent photons. The official
combined NRS1/NRS2 source X1D has a gap from 1.84305 to 3.89722 microns.
The source-specific S2D has zero wavelength pixels at 2.15–3.20 microns before
any flux or quality cut. Thus the released UV gap is not solely a 1D mask.
This does not prove the absence of useful unrectified photons in every raw
exposure. It supplies no nitrogen likelihood or UV upper limit. Nominal prism
bandpass alone is insufficient to design coverage of this source.

## Selection and bounded candidate decisions

A predeclared 40 arcsec GOODS cutout contains 16 disjoint unmasked injection sites,
0.0267 arcmin² of usable stamps. The 1,152 trials vary point/extended/pair morphology,
color, 20/80 nJy flux and explicitly assumed output-grid count gains. At gain 10,
red 20 nJy joint recovery is 11/16 point, 6/16 extended and 3/16 pair; gain 1 gives 1/16
point. Bright pair color recovery 16/16 becomes 6/16 after centroid requirements.
Those denominators are two realizations at each of eight diagnostic sites,
not sixteen independent skies. Site-bootstrap intervals are 0.375–0.938,
0.125–0.688 and 0.0625–0.375 for the three faint profiles. These are conditional
resampling intervals without calibrated coverage, not population confidence
intervals. Degenerate bright-profile 1–1 intervals do not bound unseen failures.

Actual mosaic headers, contributor footprints and released Grizli source separate
combining WHT from separately propagated VAR. The public VAR image is accessible;
a bounded 4,096-byte prefix was retained and independently decoded. Neither WHT
nor VAR identifies each contributor's count/variance operator. A constructive
Poisson witness gives the same released SCI/variance with different source shot
noise. Expanding assumed-gain injections would not fix this identifiability gap.
Labeled galaxy/star/blend/background denominators and held-out field/visit
selection are absent, so completeness, contamination and cosmological odds are
not supplied by this pilot.

For 98 and 1043, 36 actual-pixel neighbor/background fits and 216 fixed-geometry
heldouts test explicit RMS/flux-stability gates. Every red classification family
fails the RMS≤2 gate. For 98, best heldout RMS remains 5.19/5.23 in F200/F444 after
neighbor modeling; 1043 minima are 7.40/11.58/15.42. Rank is adequate: failure is
model inadequacy and background assignment, not numerical singularity. Stop
classification from these fits. Source 254 retains its established blue counterpart.

For 46, all 552,826 positive two-member pairs and the unrestricted positive cone
of 1,052 Bobcat members fail the finite-family fit. A broader 37,800-member
Flame/Skimmer atmosphere family also fails the declared photometric floors and
held-out F277 prediction. This rejects these finite families, not all stellar
atmospheres or the source's identity. Actual F410M gives strong aligned emission,
rejecting negligible F410 with an F444-only excess. Fiducial F410/F444 is 0.8448;
background/PSF/aperture alternatives matter far more than its tiny formal error.
The two filters overlap, allowing a single line near 4.307–4.316µm under the assumed
ratio tolerance. Continuum, line and multiplicity explanations remain unresolved.
Mixed mosaic contributors provide no proper-motion constraint.

## Discriminating observations and ranked continuation

The exact merged twenty-model input passed an ancestry/hash gate before the
48-case forecast ran (12.170 seconds, zero acquisitions). A separate oracle
reproduces all 43,200 distances and 96 direct spectral quadratures. Each
comparison profiles a nonnegative normalization and the declared attenuation
choices. These are hardest-pair stress tests across all finite models, including
members that are not the best native fits, rather than posterior-weighted
expected information gain.

For Cloudy intrinsic line-energy responses, zero intrinsic FWHM and the
pinned nominal G235H instrumental response:

| Measured bundle | Hardest enhanced-truth matched total SNR for expected squared separation 9 |
|---|---:|
| N IV + C III | 4,723.4 |
| He/O + C III | 1,195.0 |
| N III + C III | 11.315 |
| All fourteen UV components | 10.792 |

The strong next contrast is N III with the C III anchor under these assumptions;
N IV-only and He/O-only composition contrasts remain nearly degenerate across
environments. He/O separation retains a separate value for physical component
identification. Required SNR is a matched-template quantity under white noise,
known centroid/width/continuum and nominal response, not empirical source
sensitivity. A lower threshold in some broadened cases does not mean broader
sources need less observing time: template norms and sensitivity also change.

Intrinsic N V/C III ranges are ordinary 0–0.002415 versus enhanced 0–0.015959;
C II/C III ranges are 0.020698–0.577398 versus 0.020139–0.640808. Their overlap
prevents a guaranteed abundance discriminator. A calibrated ratio outside these
finite ranges would test the declared physical family, not all ordinary gas.
Outer stopping boundaries, C IV transfer, ionizing spectra and dust remain
material. No absolute exposure time or archive-independent observing necessity
is asserted. See [the forecast report](MOM_CLOUDY_OBSERVATION_CONTRASTS.md).

Nominal medium-resolution NIRSpec separates narrow N IV and C III geometrically;
high resolution alone does not separate 1,000 km/s components. Density-component
shape discrimination requires total doublet SNR of roughly 6–20 under fixed
centroids/known response, rather than merely a nominal Rayleigh criterion.
These are optimistic design calculations. Required MSA placement and detector
gap coverage must be checked for the actual source, rather than inferred from
nominal disperser curves. Relative exposure scaling needs a
declared instrument-specific reference; no absolute ETC seconds or feasible
proposal has been established.

1. Source-specific calibration with public PIXTAB/actual RATE contributors:
   determine morphology/LSF/wavelength and source-control noise transport. Highest
   immediate information gain because these control the nitrogen likelihood.
2. Complete-model ion-stage/density/He-O predictions under the fresh likelihood:
   target observables that differ after normalization and attenuation profiling;
   acquire additional ion stages or medium/high-resolution spectra where archive
   coverage cannot supply them. Physical continuum/transfer families precede
   larger abundance grids.
3. Native contributor count/variance transport and representative labeled controls:
   establish source-Poisson and selection likelihood before expanding the field
   pilot or attempting population/cosmology odds.
4. Candidate 46 independent epoch/optical/medium-band or spectroscopy, conditional
   on resolving its specific continuum/line/multiplicity ambiguity. For 98/1043,
   improved morphology/background or genuinely independent data precede another
   classification fit.

## Uncertainty budget and rejected explanations

The following contrasts are not independent random errors to add in quadrature.
They identify measured arithmetic, conditional transport and unidentified physics.

| Input | Actual evidence | Consequence for nitrogen |
|---|---|---|
| Signed mean / donor variance | Actual RATE/CAL closure; known spectra; independent GLS | Reject positive-only response and historical CAL variance demixing |
| Residual covariance | Fresh off-source scale 1.427616; fixed Gaussian injection coverage | Empirical ionic interval admits ambient reference; formal-only interval excludes it; transport to source remains assumed |
| Common wavelength | Exact-date reference still DUMMY; explicit ±0.12953% centroid counterexamples | A selected redshift branch can change the ionic comparison without calibrated absolute wavelength |
| Source LSF | Exact Gaussian width confounding; no held-out broadening improvement | Intrinsic width is unidentified; nominal response is conditional |
| Row wavelength / tested continuum | Less than 0.052 sigma scalar-row change; quadratic N IV change +0.076 sigma | Small within these declared alternatives; no universal bound on morphology or continuum |
| Recorded flat-reference variance | Independent diagonal small; arbitrary recorded correlation bound up to 4.02% formal N IV variance | Bounds only recorded marginal flat errors, not unrecorded common systematics |
| Shared calibration | Three disjoint groups; common line shape exactly confounded with flux | No empirical finite bound on arbitrary common source/calibration error |
| Composition / ionization / transfer | Complete thermal alternatives; unknown stage fractions, He/O and C IV transfer | Observed-stage N/C cannot be promoted to elemental abundance or polluter identity |
| Population selection | Unknown native count operator and real class denominators | No completeness, contamination or galaxy-formation/cosmology likelihood |

Rejected explanations are specific: positive-only nod response; the target-plus-
donor CAL ERR assumption; nitrogen-only flux rescaling for the declared physical
setup; absolute redshift/width identification under unresolved calibration;
classification from the tested inadequate 98/1043 scene models; the tested finite
source 46 atmosphere families; and negligible F410 with an F444-only excess.
None of these rejects all low-redshift galaxies, stars, backgrounds or standard
cosmology. Dusty/nebular galaxy fits and other atmosphere physics remain untested
identity alternatives where the present measurements cannot discriminate them.

## Reproduction, validation and acquisition

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


Use Python 3.12 and the unchanged exact research lock; all 65 distributions were
checked against it. Commands below run from the repository root. Cache paths
are examples; acquisition commands restore their exact public manifests and
verify whole-file identities, not assumptions about surviving scratch data.

```bash
python3.12 -m venv /tmp/jwst-research-env
/tmp/jwst-research-env/bin/python -m pip install -r requirements-research.lock
source /tmp/jwst-research-env/bin/activate
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BLIS_NUM_THREADS=1
python scripts/quality_gate.py

# Actual native pixels: nine already-pinned CALs, nine newly selected RATEs.
python -m data_pipeline.mom_native_batch \
  --spectrum data_sources/pilot/mom_z14_dja_v4.spec.fits \
  --output /tmp/mom-native --report /tmp/native-restoration.json
python -m tools.jwst.acquire_rate_noise_inputs --output-dir /tmp/mom-rate
python -m tools.jwst.native_rate_noise \
  --native-dir /tmp/mom-native --rate-dir /tmp/mom-rate \
  --output /tmp/rate-noise.json --compact-output /tmp/rate-noise.npz
python -m tools.jwst.native_local_identifiability --native-dir /tmp/mom-native \
  --output /tmp/local-identifiability.json

# Compact numerical replay: does not read or re-reduce raw RATE pixels.
python -m tools.jwst.cloudy_pilot \
  --replay-models research_output/mom_cloudy_pilot20_rate_v3.json \
  --fit-native --held-out --rate-noise-report research_output/mom_native_rate_noise.json \
  --output /tmp/cloudy20-native-replay.json

# Offline retained metadata and source-product coverage checks.
python -m data_pipeline.mom_public_metadata --output /tmp/public-metadata.json
python -m data_pipeline.mom_compact_followup --output /tmp/compact-followup.json
python -m data_pipeline.capers_companion_coverage --output /tmp/companion.json
python -m data_pipeline.capers_s2d_coverage --output /tmp/s2d.json
python -m data_pipeline.capers_pixtab_coverage \
  --pixtab /tmp/capers-pixtab.fits --acquire --output /tmp/pixtab-coverage.json
python -m discovery.research2_capers_source_review
python -m discovery.research2_download_ledger \
  --manifest data_sources/research2_download_ledger/manifest_v3.json \
  --source-root . --output /tmp/download-ledger.json
python -m discovery.research2_release_review --root . --output /tmp/release-integrity.json
```

Thermal reexecution is a numerical comparison; runtime-bearing output text
need not reproduce original file hashes. Exact original restoration uses the
preserved raw archive and member manifests. Reexecute the declared pilot with:

```bash
python -m data_pipeline.cloudy_inputs /tmp/cloudy --build --scipy-openblas
python -m tools.jwst.cloudy_pilot --cloudy-directory /tmp/cloudy \
  --executable /tmp/cloudy/c23.01/source/sys_pilot/cloudy-openblas.exe \
  --run-directory /tmp/cloudy/runs --limit 20 --workers 2 --timeout-seconds 1200 \
  --output /tmp/cloudy/models20.json
```

Reproduce the ancestry-gated numerical observation forecast using its exact
merged model identity:

```bash
git fetch origin master
python -m tools.jwst.cloudy_observation_contrasts \
  --input research_output/mom_cloudy_pilot20_rate_v3.json \
  --validated-merged-revision 6b44032b82e550ed0f740a56830deed296b5c4e9 \
  --input-sha256 7ef48626ddfb7c882d9725b17939c3a7752151de734e3ab4c46472b940127759 \
  --output /tmp/cloudy-observation-contrasts.json
```
Actual original GOODS, deep/source 46, representative injection and candidate
scene commands remain in their linked track reports; their inputs and output
hashes are preserved in baseline/restoration/actual-pixel receipts.

Major input identity anchors: Cloudy archive SHA256
`a9ad2dc037e88f552389de0e483d68f54310976dee32154ed13830882aedae0b`;
original author PIXTAB
`c3566b0173e9b1808b7fd856d98ca1be96ff2d6a0959132c1c7b9791d10e7420`;
CAPERS PIXTAB
`2c0d315274d0d0c74252f6d584e80636ae49e3a1361c0976216a366e8dbe6430`.
The nine individual RATE hashes are in
`data_sources/followup/mom_rate_noise_manifest.json`, restored CAL identities in
`research_output/research2_native_reproduction.json`, and image/model/filter
identities in their versioned `data_sources` manifests. Final validation and
the independent canonical release gate index all accepted artifact identities.


All focused merges require relevant tests, independent numerical/data validation
and CI. PR67 repairs a publication truncation discovered after PR65; its exact
frozen candidate artifact supersedes the truncated copy. Publication now reads
bounded chunks and checks every remote Git blob against the immutable local
identity. Final remote-tree JSON/hash checks complement tests and scientific
review. No paid resource or external-person contact was used.

## Focused merged changes

| PR | Validated change |
|---|---|
| [#55](https://github.com/Patto1155/JWST_scnience_env_2/pull/55) | Verify PR54 baseline and start bounded scientific continuation |
| [#56](https://github.com/Patto1155/JWST_scnience_env_2/pull/56) | Measure what three spectral groups cannot constrain |
| [#57](https://github.com/Patto1155/JWST_scnience_env_2/pull/57) | Reject finite Bobcat multiplicity as source 46 explanation |
| [#58](https://github.com/Patto1155/JWST_scnience_env_2/pull/58) | Recover MoM author pixel table and audit dependent extraction |
| [#59](https://github.com/Patto1155/JWST_scnience_env_2/pull/59) | Calibrate bounded selection operator and expose source-count dependency |
| [#60](https://github.com/Patto1155/JWST_scnience_env_2/pull/60) | Correct omitted ghost wavelength response in native spectral measurement |
| [#61](https://github.com/Patto1155/JWST_scnience_env_2/pull/61) | Quantify UV doublet separability and conditional observing sensitivity |
| [#62](https://github.com/Patto1155/JWST_scnience_env_2/pull/62) | Test source 46 against broader equilibrium and mixing atmospheres |
| [#63](https://github.com/Patto1155/JWST_scnience_env_2/pull/63) | Publish independent research validation and original-pixel reproduction |
| [#64](https://github.com/Patto1155/JWST_scnience_env_2/pull/64) | Constrain source 46 spectral width with independent medium-band pixels |
| [#65](https://github.com/Patto1155/JWST_scnience_env_2/pull/65) | Test broader neighbors and stop inadequate candidate classifications |
| [#66](https://github.com/Patto1155/JWST_scnience_env_2/pull/66) | Connect complete Cloudy emission to signed native spectrum |
| [#67](https://github.com/Patto1155/JWST_scnience_env_2/pull/67) | Repair candidate artifact transfer and verify exact published identity |
| [#68](https://github.com/Patto1155/JWST_scnience_env_2/pull/68) | Prepare bounded complete-model observation contrasts with provenance gates |
| [#69](https://github.com/Patto1155/JWST_scnience_env_2/pull/69) | Quantify native row wavelength response under retained covariance |
| [#70](https://github.com/Patto1155/JWST_scnience_env_2/pull/70) | Resolve Cloudy runtime blocker with validated existing backend |
| [#71](https://github.com/Patto1155/JWST_scnience_env_2/pull/71) | Correct native spectral uncertainty with nine actual RATE exposures |
| [#72](https://github.com/Patto1155/JWST_scnience_env_2/pull/72) | Bound native selection calibration by actual mosaic provenance |
| [#73](https://github.com/Patto1155/JWST_scnience_env_2/pull/73) | Test complete nitrogen thermal response before environmental expansion |
| [#74](https://github.com/Patto1155/JWST_scnience_env_2/pull/74) | Recompute complete-model fits with actual RATE covariance |
| [#75](https://github.com/Patto1155/JWST_scnience_env_2/pull/75) | Test native measurement alternatives and calibration identifiability |
| [#76](https://github.com/Patto1155/JWST_scnience_env_2/pull/76) | Verify public calibration applicability and CAPERS source coverage |
| [#77](https://github.com/Patto1155/JWST_scnience_env_2/pull/77) | Require strict science lint and independent release integrity checks |
| [#78](https://github.com/Patto1155/JWST_scnience_env_2/pull/78) | Complete 20 thermal models and validate their native likelihood |
| [#79](https://github.com/Patto1155/JWST_scnience_env_2/pull/79) | Rank finite-model UV observing contrasts after calibration-aware fits |
| [#80](https://github.com/Patto1155/JWST_scnience_env_2/pull/80) | Authoritative integrated assessment and final release evidence; independent remote-tree review before merge |

The ranked work above is feasible in different ways. Calibration/contributor
recovery is archive and software work with moderate computation and the highest
immediate effect on the nitrogen likelihood. A usable new ion-stage observation
requires source placement, detector-gap and ETC verification, and may require
new observing time; the finite-model SNR forecast does not establish that cost.
Selection calibration requires native inputs and a labeled held-out cohort before
more simulation expenditure is informative. Candidate follow-up has lower priority
until an independent datum can resolve a declared ambiguity. None currently
supports galaxy-formation or cosmology odds without the population likelihood.
