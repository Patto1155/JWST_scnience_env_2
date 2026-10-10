# Second continuation independent review

10 October 2026. The reviewer independently checked frozen author commits
`7c6cb106ec881a2cb5054650b6a056dd2767319b`,
`0eb17717e6dbca6000e20079cf9ece539ea03b62`, and
`a4743ac` in a separate worktree. All input hashes and numerical receipts are in
`research_output/research2_independent_review.json`. No downloads were made.

## Scope and decisions

**Approve shared-systematics numerical science.** A whitened SVD solve replaces
the author's normal equations. It reproduces signed N IV flux
13.6996161939±9.0070584183 and all three held-out statistics
5.2478000558, 4.5205678676, 6.3221909239. The seven-parameter design augmented
with its shared N IV response still has rank seven. Independently transporting
a full low-rank common covariance through the SVD measurement operator gives
the claimed N IV variance increment to 2.84e-14 absolute error. Closed-form
coverage and chi-square scale intervals agree. The design helper is shared;
this audit establishes numerical/algebraic correctness, not source calibration.

**Approve source46 finite-grid multiplicity result, conditional on frozen
photometry/floors.** The reviewer directly decoded actual archive members and
headers, selected wavelength columns and converted log10(mJy)-at10pc to nJy,
without calling the author's grid parser. All 1,052 rows and hashes agree.
Every actual row satisfies the saved dual inequality to 8e-17 tolerance.
A separate seven-variable constrained polar-cone optimization reproduces
minimum chi-square 125.5890502514 / 29.0484383466 within 6e-13.
Direct QR solves of asserted optimum pairs reproduce127.2757479433 /
29.2818749080; 4,000 random pair interior/single-boundary QR controls per
scenario never improve them. The all-row cone certificate is stronger than
the pair claim and does not require asserting uniqueness of the optimal
component mixture. No atmosphere class likelihood, identity or calibrated
significance is approved.

**Approve public PIXTAB acquisition, operator replay and dependence witness.**
Direct per-bin coefficient dot products independently reproduce467 finite
flux/error bins and exactly473 pixel counts. All actual input hashes match.
Over6,200 unique **nonzero** sky values recur across each tested same-nod,
cross-VISITGRP pair while associated science values differ. Different-nod
intersections are zero. These are measured shared sky values, not merely common
coordinates or zero padding. The pinned source explicitly writes the shared
negative average to `sky` and subtracts it from each positive science image.
Clipping negative profiles and dividing pathloss twice materially change the
coadd; both are rejection controls. This supports shared background use in the
public intermediate without recovering exact masks or covariance. The separate
current official CAL contract remains three disjoint RATE groups.

## Actual-pixel replay discrepancy

The reviewer reran `discovery.survivor_deep_model` on all restored actual deep
cutouts with the exact locked Python environment and
`OPENBLAS_NUM_THREADS=1`. The result is **not** byte-exact or scientifically
bit-exact to the historical artifact:84 acquisition-metadata leaves and1,850
numeric leaves differ. All scientific nonnumeric values, identities and input
hashes agree. Largest numeric difference is0.04523433 nJy in a degenerate
source254 phenomenological amplitude624.158→624.203; source46 morphology axial ratio q
moves0.224974→0.222812. The maximum source46 seven-band flux change is1.72e-7nJy.
Refitting the cone under fresh photometry/covariance gives125.5890468953 /
29.0484381512, changing the corresponding statistic by3.36e-6 /1.95e-7.
The receipt records every signed band-flux and7×7 covariance difference;
the finite-grid mixture conclusion is insensitive to this solver trajectory. These solver-trajectory differences mean the author's
zero-difference receipt (`9c2985c`) describes its particular replay environment,
not every thread setting. This review rejects universal exact replay language;
it does not reject the bounded scientific conclusions.

## Reproduction and controls

```bash
OPENBLAS_NUM_THREADS=1 python -m discovery.survivor_deep_model \
  --input /path/to/restored/deep --output /tmp/deep-review.json
OPENBLAS_NUM_THREADS=1 python -m discovery.research2_independent_review \
  --root . --deep /path/to/restored/deep \
  --author /path/to/author-provenance --deep-replay /tmp/deep-review.json \
  --output /tmp/independent-review.json
python -m pytest -q tests/test_research2_independent_review.py \
  tests/test_shared_systematics.py tests/test_survivor_multiplicity.py \
  tests/test_mom_author_provenance.py
```

21 focused tests pass. New alternate-solver controls recover a signed correlated
signal, verify covariance transport, reject duplicate line responses, distinguish
positive-cone membership from a negative-band residual and verify its distance.
Ruff passes for the independent module/tests. The public model/pixel-table and
spectral audits used actual cached input bytes or frozen extracted-likelihood
arrays as explicitly labeled. No elemental abundance, polluter, high-redshift
source or cosmological discovery is established.

## Revised-family and observation design review

**Approve `b7321e0`'s conditional, provisional FLAME pilot.** Separate direct
member parsing and XML parameter decoding verify all112 paired table hashes,
matching physical rows and37,800 retained models. All seven raw flux/magnitude
ratios lie within0.99498394–1.00503390 under the independently decoded Vega/Jy
zeropoints. This establishes consistency of the *inferred* mJy convention;
it does not establish that the contradictory author notebook documents mJy.
Both conventions remain separately tested. Independent inverse-precision
scalar GLS reproduces every all/equilibrium/disequilibrium minimum and every
held-out band optimum, prediction and conditional residual. The15% minimum
is38.8376383922 under inferred mJy and38.8281741932 from Vega/SVO. No source
identity or broader atmospheric-class exclusion is approved; The merged-dependency rerun `645174e` is independently revalidated with
its new exact report hash; all fitted scientific values are unchanged. Receipt: `research2_flame_review.json`.

**Approve `06483b6`'s conditional observation design.** Independently read and
hash-verify four actual primary response FITS, their wavelength units and all
nominal filter-range guards. Direct numerical integration of variable-width
unit-area Gaussian products reproduces all36 component-correlation cases to
1.69e-14 maximum absolute error. A bounded scalar alternative-amplitude
optimizer reproduces required density-contrast SNR to3.38e-13. Numerically
solving the independent fixed-floor noise equation gives28.80000000000009t0.
Null absolute seconds and unattainable SNR-above-floor cases are preserved.
Nominal curves are not a source-specific LSF or empirical sensitivity;
detector-gap geometry and absolute exposure feasibility remain unresolved.
Receipt: `research2_observation_review.json`.

```bash
python -m discovery.research2_flame_review --root . \
  --archive /path/to/flame_photometry.zip --deep /path/to/restored/deep \
  --report research_output/survivor46_flame_v1.json --output /tmp/flame-review.json
python -m discovery.research2_observation_review --root . \
  --output /tmp/observation-review.json
python -m pytest -q tests/test_research2_model_review.py \
  tests/test_observation_design.py tests/test_survivor_flame.py
```

The new control tests retain signed negative observations and the zero-amplitude
boundary, test held-out no-leakage and recover the unit-area norm's inverse-width
scaling.17 focused tests pass; independent review module/tests lint passes.

## Signed-response predictive check and rejected engineering pilot

The actual-pixel source/ghost response in `c9cf5b2` has a separate independent
SVD/erf validation in the PSF specialist's `973fecb`. This reviewer also checks
the held-out predictive distribution: add trained line covariance to held-out
measurement covariance, then project its separate continuum under that combined
precision. Only test continuum dimensions are subtracted from predictive dof;
training uncertainty is propagated rather than counted as another fit in the
test sample. An independent full-precision projector simulates4,000 known
Gaussian training/test data sets, with different training/test continua. Its
46-dof statistic mean45.7292 and95-percentile fraction0.9515 agree with the
conditional distribution. Actual revised group03/05/07 predictive tails are
independently recomputed as0.88486694 /0.44033570 /0.99558326 at208dof.
This validates conditional normalization, not empirical native-noise tails.
`4c65726` corrects the opening provenance text after public PIXTAB recovery.

```bash
python -m discovery.research2_prediction_review --root . \
  --output /tmp/predictive-review.json
```

A pre-expansion Cloudy input audit **rejected an engineering probe**: using
`metals z linear` together with explicit C/N/O abundances already multiplied by
z applied metallicity twice. Actual model000 output reported log(O/H)−4.7077
rather than the declared−4.0087739 at z0.2. The pinned C23.01 source applies
its global metals factor after explicit reference abundances; the actual saved
zone composition independently confirms this. No scientific20-model grid had
expanded. The model author preserves that359.65-second probe as misconfigured,
corrects the base overrides and adds actual output composition checks before
restarting in a distinct run directory. Its line predictions cannot enter the
scientific likelihood. Corrected thermal results await independent review.

## Corrected first complete thermal model

The corrected `model000` preflight is **approved for bounded expansion**, not
for an abundance conclusion. The reviewer hash-verifies all seven actual files,
checks the immutable ordered29-line contract, directly sums all five UV groups
and their blends, and independently checks every printed gas composition block
and234 zone number-density ratios relative to H. Actual log(O/H)−4.0088,
log(C/H)−4.3788 and log(N/H)−4.9788 now match the declared gas composition.
The final run stopped at low electron fraction at iteration3 of3 with234 zones,
no warning/failure at the completion summary and no truncation. Saved H+ weighted
Te=13,462.39K lies within the actual1,146–14,792K zone range.

Actual output explicitly says `Intensity (erg/s/cm^2)`. The pinned source's
save-line-list absolute branch and `cdLine` implementation confirm linear
absolute intensities; outdated internal comments about logarithms do not alter
that executable contract. Intrinsic and emergent29-line vectors are separately
verified. Source-specific distance/luminosity conversion is not claimed.

The source also establishes Cloudy's default namespace: wavelengths below2000Å
are vacuum; wavelengths above2000Å are air. All14 fitted UV components are below
that boundary. Extra C II2323–2328 labels therefore need an explicit air
convention/conversion for observation design, just like Hβ and optical [O III].
The authors were notified; this does not alter the fitted UV group predictions.
Receipt: `research2_cloudy_first_model_review.json`.

```bash
python -m discovery.research2_cloudy_model_review \
  --report /path/to/corrected-first-model.json \
  --runs /path/to/corrected-runs --source /path/to/c23.01 \
  --output /tmp/cloudy-first-review.json
python -m pytest -q tests/test_research2_cloudy_model_review.py \
  tests/test_research2_cloudy_composition_review.py
```

Five guard/control tests pass. This is independent validation of actual software
outputs and their physical/input contracts, not a separately implemented atomic
or thermal solver. The independently selected nitrogen-enhanced pair and refined
thermal-convergence checks remain pending before integrated inference.

## First complete Cloudy model: signed native likelihood

**Approve frozen `04766f6` first-model likelihood numerics, conditional on the
reviewed measurement assumptions.** The reviewer independently rebuilt the
five normalized groups from the actual 14 line intensities and attenuation,
formed the full 630-datum covariance from block Cholesky factors and the spectral
kernel, explicitly transported the bin responses through the frozen signed Q,
and solved both seven-parameter measurements and the three-parameter physical
model by whitened SVD. The direct full-data nonnegative-amplitude fit reproduces
all 36 two-stage profiles, full group covariance, fitted normalization and
normalization uncertainty to maximum absolute error 3.31e-9. This audit shares
the previously reviewed bin-integration helper and the pinned numerical Q; it
is compact numerical replay, not an additional pixel reduction. Two independent
controls cover continuum freedom and negative-amplitude boundary refitting.
Seven combined focused tests pass; Ruff passes.

For the original wavelength hypothesis, the ordinary composition model's
zero-screen empirical-noise group restriction costs delta chi-square
7.0823–7.6777 for four line-ratio restrictions. Its full-data chi-square is
551.44–556.53 for 627 fixed-model degrees of freedom. These conditional fits
are adequate; the formal-noise alternatives give approximately1222–1225 and
remain inadequate. Fixed-model Gaussian tails are diagnostics under stipulated
noise, not empirically calibrated probabilities. The three attenuation choices
and two wavelength hypotheses remain separate. A one-model pilot cannot
measure an ordinary-versus-enhanced preference: the recorded zero difference
from the global grid minimum is tautological until additional models complete.
The remaining thermal pairs, convergence refinement, ionizing-spectrum range,
source-specific calibration and transfer uncertainty still block an elemental
abundance posterior. The absolute Cloudy intensity geometry is absorbed by
one nonnegative common amplitude; no distance or retention fraction is inferred.

Executable audit:

```bash
OPENBLAS_NUM_THREADS=1 python -m discovery.research2_cloudy_likelihood_review \
  --root . --report research_output/mom_cloudy_first_model.json \
  --output research_output/research2_cloudy_likelihood_review.json
```

**Approve `f94252a` C II convention correction.** All four cited pinned Cloudy
source/data members agree in actual bytes and SHA256. The default source explicitly
uses air above2000Å; the C II2326.93 target now labels its preserved numerical
value an approximate air-based target. No vacuum conversion is asserted. All36
UV/density cases independently replay unchanged by numerical quadrature; the
updated report hash is in `research2_observation_review.json`. Fifteen relevant
tests pass. Reproduce the actual source-member audit by adding
`--cloudy-source ../research-cache/cloudy/c23.01` to the observation review command.

**Approve `fac4e6f` observation-contrast arithmetic and execution gate only.**
A fresh randomized20row synthetic fixture, independently integrated Gaussian
Gram matrix with varying instrumental widths, and bounded scalar optimizer
reproduce all100 environment-pair minima over9 attenuation pairs plus the ten
matched pairs to less than1e-12 in shape information fraction. Five author
synthetic controls pass. The CLI checks both the exact input SHA256 and its
presence in a specified merged revision in `origin/master` ancestry. Actual
thermal outputs and resulting forecasts have not yet been evaluated or approved.
Intrinsic and emergent responses stay separate; free amplitude removes pure
flux-scale information. The declared optimistic width/centroid/continuum/noise
assumptions still require observational validation. Review receipt:
`research2_cloudy_design_review.json`; executable module of the same stem.

**Atomic provenance extended.** Independent one-pass decoding of the actual
338,434,070-byte C23.01 archive verifies its SHA256 and all27 pinned atomic,
solar-abundance, documentation and source members; extracted cached files agree
byte-for-byte with those archive members. The first-model review receipt now
records this audit. Add `--archive-receipt research_output/cloudy_inputs.json`
to the actual-model audit command to reproduce it. This checks provenance, not
an independent derivation of atomic rates or a second thermal solver.

**Capped thermal expansion rejected as scientific output.** For `e6393e4`,
the reviewer verifies all49 raw file identities from the seven started models,
no final `Cloudy ends:` summary, and empty final line/temperature-average saves.
No complete flux prediction exists to score. The12 unstarted rows carry no raw
files. Exact wallcap/cancellation timing cannot be reconstructed independently
from retained raw files; the receipt is explicit about that limit. This failed
four-worker600s attempt does not invalidate the validated first single-model
460s run, but does invalidate assuming that its runtime scales to four-way
expansion. The revised limited pair and backend control need separate validation.
Raw audit module/receipt: `research2_cloudy_capped_review`.

**Approve `7612f59` plus `71f7011` ordinary-backend engineering control.**
Actual input,29 intrinsic+29 emergent line values, five weighted temperature
averages and the abundance save are byte-exact across the original and LP64
OpenBLAS executables. Both runs converge in234zones/three iterations. All seven
raw control files, new binary and existing library hashes match; the publisher
wrapper declares int32 external LAPACK arguments. The full zone overview is
not identical: maximum Te difference5.8K (relative7.024e-4), depth difference
8.14e-6 relative, and maximum scalar difference2.868e-3 in molecular fraction.
These changes are explicitly recorded and the author corrected the scope. Seven
focused execution/backend tests pass. This validates the ordinary model's
printed-line/average-temperature equivalence, not universal equality in every
physical regime. Runtime353.66s versus460.14s is observed engineering evidence,
not a guaranteed speed ratio. The original executable remains the authoritative
first-model science contract. Reviewer module/receipt:
`research2_cloudy_backend_review`.

## Focused complete composition pair

**Approve `62634bf` actual thermal pair and conditional likelihood.** All14
raw model files, actual abundances, complete29 component/blend identities,
linear units and convergence independently pass. The original LP64 enhanced
model completes378.81s/236zones/three iterations. Independent group sums give
N IV7.8250, C IV0.7835, He/O0.8880, N III8.7837 and C III0.8850 relative to
ordinary, with H+ weighted temperature13462.39→13177.67K. This explicitly
rejects pure nitrogen-flux rescaling `[10,1,1,10,1]` in this physical setup.
It establishes modeled thermal feedback, not measured source abundances.

All72 full-data alternatives independently replay through constrained SVD.
Original wavelengths prefer the ordinary member under all six stipulated noise
and response alternatives; DUMMY point-response choices give only0.224–0.352
chi-square advantage to the enhanced member. These are two finite models under
one environment, not elemental posterior odds or complete environment coverage.
The remaining18 environment/composition controls are uncompleted at this freeze.

All six held-out choices and predictive statistics are independently reproduced
from training-only direct SVD. Numerical integration normalizes the explicit
flat-measure nonnegative amplitude likelihood, independently obtains moments
and95% quantiles, and a full predictive-covariance nuisance precision projector
replaces the author's rank-one expression. Maximum numerical difference4.59e-10.
A known half-normal control validates the boundary normalization. This predictive
quadratic is moment matched and has no calibrated Gaussian p-value near the
boundary. Eight reviewer guard tests pass; Ruff passes. Compact likelihood,
actual thermal reproduction and group prediction remain distinct contracts.
Receipts: `research2_cloudy_pair_model_review.json`,
`research2_cloudy_pair_likelihood_review.json`,
`research2_cloudy_pair_heldout_review.json`. Actual model review supports
`--run-override model000=../research-cache/cloudy/corrected-runs` with main
`--runs ../research-cache/cloudy/focused-pair`; likelihood and held-out review
accept `--report research_output/mom_cloudy_focused_pair.json`.

## Native source-count and class-denominator audit

**Approve `796eea1` pinned source/header, mathematical identifiability and
public-accessibility scope.** All13 source/metadata pins and actual selection
cutout hashes match. Independent FITS/CSV joins reproduce F090W/F200W/F444W
contributor counts208/262/106, scalar WHT header counts47/72/62, matched current
query exposures32/43/48 and geometric exposure sums41400.998/45888.965/49893.783s.
These are not local valid exposure times or native photon-count maps. Direct
released source inspection verifies separate combining `outwht` and full-ERR
`outvar` exports plus the last-tile header inheritance after rebuilding the FLT
union. Exact deployed thumb/runtime mapping remains unverified.

The original background-only equality proposal failed full-ERR consistency and
was corrected before freeze. The compensated generic coadd has identical mean20
and full variance14 with source/background components4+10 versus13+1. Independent
200,000-draw native Poisson controls per case recover that variance. Forty
independent constrained minimizations verify the scalar lower boundF/sum(c_i);
vertex maxima verifyF/min(c_i). These conditional bounds require known positive
count conversion and nonnegative scalar weights; they do not describe signed
aperture/drizzle covariance or reproduce an exact DJA pipeline.

An independent zero-body HEAD request confirms the public VAR sibling returns200,
43,219,789bytes and the recorded ETag; reviewer acquired zero body bytes. The
currently retained record stores only80prefix bytes, insufficient to independently
decode the alleged3976×4032 FITS header. That narrow header claim awaits raw-prefix
preservation and is not covered by this approval. Missing class labels/denominators
remain explicit; one null centroid match and zero red null passes are not an
astronomical contamination estimate. Six focused author tests and independent
numerical replay pass; Ruff passes. Receipt/module:
`research2_selection_count_review`.

**Extend count-audit approval to `65d16cb` retained-prefix supplement.** The
reviewer directly decompresses the pinned actual4096gzip bytes and reads a valid
primary FITS header with BITPIX−32 and dimensions3976×4032. Prefix SHA256
88921ea0135dd62d619c1e0cb3dff8bccae2b17cf44bbecb7d1f3a9b990edcfe
matches the original probe; updated14source/metadata/prefix pins and all earlier
mathematical/header/source claims pass. Six focused tests pass. The full43MB
VAR image was not acquired and neither native count covariance nor the exact
historical cutout operator follows from its accessible header. The prior narrow
raw-header gap is now resolved; the updated receipt records its limited scope.

**Approve `5ebf3b2` enhanced backend control.** All14 raw original/revised
file identities and both executable hashes pass. Independent input/58printed
line values/five temperature averages/abundance saves agree byte-for-byte;
actual composition/convergence guards pass. The236zone depth grid is exact,
while maximum temperature difference is0.1K (relative7.43e-5). This is scoped
printed-output engineering equivalence. The revised runtime443.31s exceeds
original378.81s, so no universal acceleration follows. Actual remaining18runs
are a separate pending experiment, under the declared two-worker1200s cap.
Reviewer module accepts `--enhanced`; receipt:
`research2_cloudy_enhanced_backend_review.json`.

### Aggregate download accounting and release gate

The independent ledger charges **1,326,134,993 bytes** of new acquisition,
including recorded failed/repeated body reads and conservative allowances. This
leaves **821,348,655 bytes** below the initial 2 GiB cap. The combined figure is an
upper-bound charge, not an exact transfer measurement: author-data auxiliary
probes and part of the decoder installation were not fully instrumented. The
runtime category includes 2,200,275 measured extra-wheel bytes plus a 24 MiB UV
allocation; installed-file sizes are not substituted for transfer bytes. The
separate restored pinned-product total is **2,072,989,504 bytes**. It describes
retained original inputs, not complete restoration retry traffic.

The ledger counts the FLAME archive receipt-error retry, Cloudy's failed prefix
probes, the duplicate observation-reference page, the repeated VAR header prefix,
and both identical PNG query responses as transfers. Reused RATE pilot inputs,
CALs, PSFs, SVO curves, author spectra and candidate images are counted once under
their acquiring/restoring owner. The RATE expansion metadata repeats dependency
counters although source/probe requests occurred only once. Full VAR maps were
not acquired. Receipt identities are pinned by SHA256 and length.

An independent fetched-tree gate checks baseline ancestry, every tracked JSON
with strict finite syntax, historical research-artifact Git identities, and the
SHA256/length of 17 frozen scientific artifacts. It also requires every new
scientific Python module to appear in the explicit strict-lint targets. Meaningful
negative controls reject valid-JSON measurement corruption, malformed JSON,
NaN/Infinity, working-tree edits, historical-contract edits, uncovered science,
duplicate ledger owners, changed same-size receipts and budget overflow. The
latest completed integrity audit is **interim** at live master `cf2f10d`; final
acceptance awaits the remaining scientific/quality merges and a fresh fetch.

Mechanical changes `52f4731`, `836e300`, `21f76df`, and `82ab6fc` preserve all
computation and interpretation ASTs/literals. Import statement order/grouping
changes retain the same module/symbol/alias multiset. These approvals do not
validate the separate semantic RATE-to-Cloudy bridge changes.

```bash
OPENBLAS_NUM_THREADS=1 python -m discovery.research2_download_ledger \
  --manifest data_sources/research2_download_ledger/manifest.json \
  --source-root . --output /tmp/research2_download_ledger.json
OPENBLAS_NUM_THREADS=1 python -m discovery.research2_release_review \
  --root . --output /tmp/research2_release_integrity.json
```

### New public metadata inventory

Approved the metadata scope of `0798741` with the timing correction `f9b22f9`.
All 12 actual response bodies match their hashes/lengths (470,251 bytes). The nine
cached CAL files were independently rehashed and their actual primary/slit
headers compared with the inventory: source 277193, EXTENDED, context1535 and
wavecorr0004. No new CAL pixels were acquired.

Independent SkyCoord geometry gives the reported 0.03058-arcsec positional
separation for the CAPERS extraction. Source-shutter rows contain **18 unique
exposure roots**, one selected row per root, totaling **17,069.004 s**; all are
disjoint from the nine MoM roots after normalizing detector suffixes. The PUBLIC
source-level MAST record has finite later observation times. Of the 35 fully
paginated position records, six have times and 29 have null times. Program and
product samples are incomplete. The released CAPERS wavelength range excludes
all tested nitrogen/carbon UV features at the assumed redshift14.44. Coordinate
coincidence and the catalog's grade1 redshift fit establish neither identity nor
an astrophysical redshift.

The actual context1535 pipeline mapping points to NIRSpec0432; its five relevant
mapping names occur in the capped latest homepage, including wavecorr0005.
This proves listed mapping names, not applicable selected references. The actual
CAL wavecorr0004 reference metadata is DUMMY. Exact selector/reference and
compact-pixel followup remains a separate experiment.

Independent timing arithmetic caught a label error: active query durations sum
100.320318698 s, while the recorded cumulative query-phase clock is100.874835197 s.
The author corrected the labels and removed an unsupported outer wall-span claim
before approval. No science-response identity changed.

```bash
OPENBLAS_NUM_THREADS=1 python -m discovery.research2_public_metadata_review \
  --root . --cal-directory /path/to/restored/mom-native \
  --output /tmp/research2_public_metadata_review.json
```

### Exact selector and compact CAPERS followup

Approved `ba99a31` for its metadata and compact-input scope. The five retained
GET bodies and two zero-body HEADs match the frozen receipts: 718,228 body bytes,
of which 16,453 restore the historical wavecorr reference and 701,775 are new.
Independent AST inspection confirms latest1596→NIRSpec0444→wavecorr0005, and the
NRS_MSASPEC UseAfter2015 branch selected by the actual CAL observation date
returns **the same wavecorr0004 file**. Its whole SHA256 equals the historical
pin and its actual ASDF header remains DUMMY. This resolves applicability and
provenance; it supplies no empirical wavelength/LSF calibration.

The actual compact FITS verifies 18 unique NRS2 contributors across six exposure
groups, source coordinates/ID, the complete source-shutter root set, exposure
time, units, and declared extraction settings. Exactly195 of473 bins have
finite flux, positive finite error and positive pixel count; their wavelength
range equals3.93798944–5.50183332µm. No new fit, raw reduction, source identity or
line detection is approved. The advertised4,475,520-byte PIXTAB was excluded
without a GET. It is publicly accessible work requiring revised allocation,
not an unavailable author input.

The immutable first ledger is superseded for current accounting by
`research2_download_ledger_v2.json`. Including both metadata stages, the new
conservative charge is **1,327,307,019 bytes**, leaving **820,176,629 bytes** below
2 GiB. Restored pinned products total **2,073,005,957 bytes** separately. The
additional1,172,026 new response bytes include11,181 repeated author CSV bytes;
repeated requests are charged as transfers. This report retains the earlier
measurement-versus-upper-bound distinctions and does not claim instrumented
HTTP wire traffic.

```bash
OPENBLAS_NUM_THREADS=1 python -m discovery.research2_public_metadata_review \
  --root . --cal-directory /path/to/restored/mom-native --compact \
  --output /tmp/research2_compact_metadata_review.json
OPENBLAS_NUM_THREADS=1 python -m discovery.research2_download_ledger \
  --manifest data_sources/research2_download_ledger/manifest_v2.json \
  --source-root . --output /tmp/research2_download_ledger_v2.json
```

### Final bounded archive-transfer accounting

The current accounting is `research2_download_ledger_v3.json`; versions 1 and 2
remain immutable. The later PIXTAB, source-associated companion, and S2D
responses contribute exactly 4,475,520 + 1,219,486 + 1,353,600 = 7,048,606
additional body bytes, each fetched once. Their frozen receipt identities were
checked against the integrated coordinator tree. Actual-pixel scientific review
of these three inputs is separately owned by spectroscopy.

All bounded archive followups transferred 8,237,085 accepted body bytes. Of
these, 16,453 restore the already pinned wavelength reference, so 8,220,632 are
charged to new transfers. Deduplicating 11,181 bytes of deliberately repeated
author CSV queries gives 8,209,451 distinct payload bytes relative to those
earlier pins; repeated requests still count toward transfer allocation. The
recorded 5,177-byte metadata HTTP404 body is already included. No further
retries or failures were reported; HTTP transport overhead was not instrumented.

The final conservative new-transfer charge is **1,334,355,625 bytes**, leaving
**813,128,023 bytes** below the 2-GiB cap. This includes conservative author-probe
and software allocations rather than claiming every category is exactly
measured. Separately restored pinned products remain **2,073,005,957 bytes**.
Shared caches, repeated dependency counters and the restored reference are not
charged again as new selections.

```bash
OPENBLAS_NUM_THREADS=1 python -m discovery.research2_download_ledger \
  --manifest data_sources/research2_download_ledger/manifest_v3.json \
  --source-root . --output /tmp/research2_download_ledger_v3.json
```

The exact-artifact release gate now pins **33** frozen scientific/data artifacts,
including the empirical-RATE likelihood bridge, row-response and local
identifiability experiments, selection pilot/audit outputs, and all bounded
metadata/PIXTAB/X1D/S2D coverage receipts. Each added canonical identity was
read from its frozen Git revision and matched against the integrated tree.
The new thermal20 family and derived observation forecasts remain outside this
acceptance scope until their independent review and final merge.

The current ledger describes the reused JADES DR5 PSFs as **modeled**. The
immutable earlier accounting notes used the word empirical; that wording
does not establish empirical PSF calibration. No transfer total changes.

### Default atomic provenance

Approved metadata freeze `97524d5`: independently streamed and rehashed the
complete 338,434,070-byte Cloudy archive, compared all ten retained default
master/solver/recombination members with actual execution-cache bytes, and
parsed uncommented species entries separately from the author implementation.
N IV, C III, O III, N V and C II select Stout; N III and C IV select CHIANTI
10.0.1 exclusively in these default masters. Source inspection confirms the
internal hydrogen-like helium sequence and its H-like recombination table.
All 20 actual pilot decks lack database overrides. This establishes versioned
provenance, without certifying empirical atomic rates. The independent audit
took 15.06 s and acquired no new input.

Approved original raw preservation `56262de`: all 14 original Cloudy pair
outputs in the 228,541-byte gzip/tar container exactly match the previously
approved model receipt lengths and hashes. The saved line list is also pinned;
the 15 sorted members are regular relative files with normalized owner, time
and mode metadata, and gzip time is zero. This supports exact artifact
restoration after scratch loss, separately from numerical rerun tolerances.

All three immutable acquisition-ledger versions are also canonically pinned,
bringing the current release gate to **36** artifacts. Current version 3 uses
the corrected modeled-PSF wording.

Approved capped-run preservation `df3150b`: all 49 incomplete engineering files
match the approved failed-attempt ledger identities in a separate 316,171-byte
archive with deterministic, safe regular members. This preserves failed
experiments for audit without using any incomplete prediction.

### Complete composition-aware pilot acceptance

Approved thermal/output scope of frozen `a49e7f3`, artifact SHA256
`7ef48626ddfb7c882d9725b17939c3a7752151de734e3ab4c46472b940127759`.
All 20 actual converged models pass 140 raw-file identity checks, the complete
29-line intrinsic/emergent identity and summed-blend contracts, printed/zone
CNO composition guards, actual densities and the independently enumerated ten
environments. Paired decks differ only in nitrogen abundance and model IDs.
The actual executable and every model receipt share the validated OpenBLAS
binary; each recorded execution fits its predeclared cap.

Eleven models terminate at the declared electron-fraction threshold and nine
at the declared 1,000-K temperature floor. Independent checks tie final
physical stop labels to actual zone values and deck commands. These boundaries
remain model assumptions, particularly for low-ionization predictions.
The H+-weighted temperatures span 10,240.15–17,111.30 K; changing nitrogen
recomputes the thermal solutions and all lines rather than rescaling emission.
The 141-member raw archive independently matches all 140 model receipts and
the saved line list, actual cache bytes and canonical safe container metadata
(SHA256 `5b36c11a1f9839e30d433198ad47ec7c69e977f476992aaa26beae853fcf4f4a`).

Independent minima selection from the frozen score table gives enhanced versus
ordinary improvements of only 1.93–1.98 in full conditional chi-square for the
original-wavelength empirical-noise alternatives; ordinary line-shape penalties
are 3.60–4.86. Formal-noise improvements are 2.94–2.97, while DUMMY sensitivity
alternatives span 2.65–4.60. Spectroscopy separately validates the actual native
likelihood and held-out predictions. These finite-family differences establish
neither a calibrated abundance interval nor posterior odds. Supported
calibration, ionizing spectrum, transfer, thermal boundaries and priors remain
material; no elemental nitrogen requirement or stellar-polluter claim is approved.

```bash
OPENBLAS_NUM_THREADS=1 python -m discovery.research2_cloudy_model_review \
  --report research_output/mom_cloudy_pilot20_rate_v3.json \
  --runs /path/to/restored/cloudy-pilot20 \
  --source /path/to/verified/c23.01 --require-complete-pilot20 \
  --output /tmp/research2_cloudy_pilot20_model_review.json
```

The reviewed complete thermal family, its raw archive/manifest, default atomic
provenance and original/capped raw preservation artifacts are now canonical
release-gate inputs, bringing the gate to **44** exact artifacts. Actual derived
forecasts await separate validation before inclusion.
