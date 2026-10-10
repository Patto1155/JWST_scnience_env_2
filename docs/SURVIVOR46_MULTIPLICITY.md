# Source46: multiplicity cannot rescue the finite Bobcat grid

The question was whether source46's previously rejected **single** cloudless,
chemical-equilibrium Sonora Bobcat spectrum could become adequate when two
objects are blended. Predictions compete: a binary can add short-wave light to
a very cool red component, whereas a mismatch in the grid's achievable colors
persists even after arbitrary positive blending. The expected information gain
is rejection or retention of this specific multiplicity explanation, without
classifying the source. The computation budget is all 552,826 distinct pairs
of the 1,052 pinned rows, two existing covariance scenarios, and seven held-out
bands per scenario. No newly selected bytes are required. The stopping rule is
to test the entire positive grid cone first/alongside pairs, then cease expanding
this grid if even its unrestricted mixture remains inadequate under the adopted
15% sensitivity floor. Inadequacy here is descriptive, not a calibrated p value.

## Inputs and restored controls

All21 actual deep science/weight cutouts, seven modeled PSFs and seven passbands
were restored and verified against the previous manifest:52,332,339 bytes.
The pinned Bobcat archive adds950,605 bytes, for53,282,944 restored bytes,
accounted separately from new scientific selection. The manifest guards WCS,
filter identities and exact bytes. The old deep model and atmosphere contracts
remain unchanged. The independently restored atmosphere computation reproduces
171.4926606425/49.3833505151 for the old5%/15% single-member best fits.
A fresh actual-pixel deep-model replay is a separate restoration check; replaying
compact photometry is never called independent image reproduction. Its executed
inherited/default BLAS-thread environment reproduces all scientific values
exactly, with84 acquisition-provenance leaf changes. Independent review using
`OPENBLAS_NUM_THREADS=1` finds1850 numeric leaves changed by degenerate spatial
optimizer trajectories. Exact numerical replay therefore has a thread-policy
scope; frozen source photometry remains the versioned input for this experiment.
The replay receipt records runtime/thread policy and the independent discrepancy.

## Exhaustive GLS pairs and a verifiable cone lower bound

Each actual table row supplies seven **log(mJy)-at10pc** band fluxes, converted
under the unchanged author-header parser. For each pair, signed measured fluxes
are fitted by two nonnegative amplitudes with the existing full covariance.
Single-member boundary solutions are retained. Arbitrary amplitudes are more
permissive than a coeval physical binary and do not supply distance estimates.

An unrestricted nonnegative least-squares fit to all1,052 columns is an even
larger family: every finite mixture from this grid lies inside its positive
cone. Its whitened residual `r` supplies a dual witness `u=r/||r||`. The compact
artifact records band weights and all direct checks: `u.T u=1`,
`max(A_white.T u) <= numerical tolerance`, and
`u.T y_white=sqrt(minimum chi2)`. Thus every positive grid mixture lies on the
opposite side of a separating hyperplane from the measured vector. This is a
numerical certificate for the **conditional geometric mismatch**, not a
scientific significance calibration. No grid-member-count probability is used.

| Assumed independent floor | Previous best single chi2 | Exact best pair chi2 | All-row cone minimum chi2 |
|---|---:|---:|---:|
|5%|171.4927|127.2757|125.5891|
|15%|49.3834|29.2819|29.0484|

The15% cone's measured vector is5.390 assumed Mahalanobis units away from this
superset; its dual maximum row projection is−6.5e−19. Four nonzero components
improve flexibility but do not remove the mismatch. No number of positive
components from these finite rows can have smaller conditional chi2 than29.0484.
The empirical photometry errors plus5%/15% individual and3% shared floors are
explicit assumptions; their coverage and the model passband/calibration match
are not newly established.

## Held-out predictions resolve why the binary does not suffice

All pairs are refitted with each omitted band removed from the likelihood.
Predictions retain the same F444-derived morphology and are not independent
imaging validations. Under15% floors, holding outF277 gives2.122nJy versus
9.739nJy observed, with descriptive conditional residual4.852 assumed sigma.
Holding outF115 predicts10.131nJy versus3.907nJy measured (−9.477 assumed sigma),
and holding outF090 predicts3.275nJy versus0.432nJy (−7.544 assumed sigma).
Adding a hotter object to recover short-wave flux forces too much blue emission;
the positive mixture cannot freely repair all of these bands. Full predictions,
components, fresh residuals, covariance, input hashes and dual weights are in
`research_output/survivor46_multiplicity_v1.json`.

## Changed conclusion and limits

Previously the finite grid failed for single objects. It now fails even for
arbitrary nonnegative mixtures of its1,052 rows under the same conditional
photometry/covariance. **Multiplicity within that grid is not a sufficient
explanation.** This does not reject brown dwarfs, clouds, disequilibrium chemistry,
new opacities, additional stellar/galaxy spectra, imperfect photometry or arbitrary
foreground blending as classes. No redshift, stellar identity or discovery follows.
The next useful experiment is a genuinely different, versioned atmosphere family
or independent medium-band/epoch data; more combinations of Bobcat rows have
reached the stopping criterion.

## Reproduce and independent validation targets

```bash
python -m data_pipeline.survivor_deep_data --output /tmp/jwst-deep
python -m discovery.survivor_multiplicity --input /tmp/jwst-deep \
  --photometry research_output/survivor_deep_model.json \
  --output /tmp/source46-multiplicity.json
python -m pytest tests/test_survivor_multiplicity.py tests/test_survivor_atmosphere.py tests/test_survivor_deep_data.py
```

Eleven focused tests pass. An independentNNLS oracle enumerates every pair in a
correlated analytic control, verifies omitted-band no-leakage, retains collinear
single boundaries and signed negative observations, and directly evaluates the
cone dual inequality. A separate researcher must verify actual-grid witnesses,
units and prediction reconstruction before merging; the author is not sole validator.
