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
