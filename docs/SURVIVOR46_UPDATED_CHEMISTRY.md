# Source46: updated cloudfree chemistry does not close the seven-band discrepancy

This experiment follows merged PR57 at
`bc7abf06378ecb02859df0e172637dbf9c6863f4`. A fresh scientific rerun after fetching
and merging that live remote revision reproduces the independently reviewed
provisional pilot. Its
question is whether newer opacity and vertical-mixing chemistry, rather than
adding more Bobcat objects, can explain source46 and predict withheld bands.
Competing predictions are a single cool spectrum whose detailed molecular
features explain the curvature, and a persistent cross-band discrepancy requiring
other model families or better photometry. The planned information gain is a
bounded rejection or retention of this new family, without establishing identity.

Before fitting, the pilot declares Teff200–1000K, logg3.5–5.5 and all published
JWST photometry rows within those limits: equilibrium plus disequilibrium,
metallicity−1 to+2dex, C/O0.5/1/1.5/2.5 times solar, and disequilibrium
logKzz2/4/7/8/9. This gives37,800 rows. The upper temperature retains cool
explanations for the steep red shape; this is not a full atmospheric class test.
The acquisition budget is200MiB for this specialist, runtime pilot120seconds,
and no paid resources. The stopping rule is no grid refinement if the best
15%-floor conditional chi2 exceeds20 or a withheld band exceeds3 assumed sigma.
These are transparent operational criteria, not calibrated significance levels.

## Public release and a discovered unit inconsistency

The [Sonora Flame Skimmer v1 release](https://zenodo.org/records/20030439),
[paper Mang et al.2026](https://arxiv.org/abs/2608.06454v1), supplies the
73,013,302-byte `photometry_tables.zip` with publisher
MD5`1a14aec657747413f3a33a65d1aec604` and independently measured
SHA256`4ef41b43028e4fae91c3a74ed98d372f3e6c2d9229c22531088b7f85abd44ed3`.
Only112 JWST flux/magnitude regular members are read, with their own pinned
byte lengths and hashes; no full atmosphere spectra, archive code or notebooks
are executed. Their table headers explicitly identify each filter and physical
row. The broader grid updates chemical kinetics/opacities but remains cloudfree.

The author notebook states its flux table has `erg/cm²/s/cm` units. That prose
is inconsistent with the supplied **paired flux and magnitude numbers**. The
400K/logg4.5/solar equilibrium F444 table value is0.2301; its paired magnitude
is14.76. Pinned SVO F444 Vega zeropoint184.1022219Jy gives0.22954mJy, not a
physically supported literal F_lambda conversion.

Every retained row and all seven bands are checked against independently pinned
SVO `MagSys=Vega`, `ZeroPointUnit=Jy`, `ZeroPointType=Pogson` values.
Interpreting raw table numbers as mJy versus converting paired magnitudes with
those zeropoints gives ratios **0.99498394–1.00503390**, consistent with rounded
0.01-magnitude tables. Median band ratios differ from one by less than6e−5.
This numerical identity establishes a defensible **conditional mJy/Vega
interpretation** and rejects silently applying the notebook's F_lambda wording
to these table numbers. Absolute source-specific calibration and the author's
undocumented implementation are not thereby reproduced.

Both independently decoded conventions are fitted separately, with their actual
seven-band predictions. They are alternative measurements of model-table
rounding/conventions, not independent observed data or likelihoods to multiply.
The source46 photometry is frozen to the prior version's exact hash. The inherited
model PSFs, source shape and5%/15% individual plus3% common floors remain assumptions.

## Results and held-out predictions

| Adopted convention | Assumed independent floor | All models best chi2 | Equilibrium best | Disequilibrium best |
|---|---:|---:|---:|---:|
| Raw flux inferred mJy |5%|105.6634|118.7742|105.6634|
| Raw flux inferred mJy |15%|38.8376|41.8463|38.8376|
| Vega magnitudes with SVO Jy zeropoints |5%|105.4827|118.1875|105.4827|
| Vega magnitudes with SVO Jy zeropoints |15%|38.8282|42.0004|38.8282|

The direct-mJy5% best row is400K/logg3.5/[M/H]−1/C/O1.5/logKzz4;
the15% best row is250K/logg3.5/[M/H]+1.5/C/O0.5/logKzz7. These are labels of
inadequate best fits, not temperature, composition, age, mass or radius measurements.
Substantial model selection instability under the floors reinforces that limit.

| Omitted band | Observed nJy | Predicted by refit without band,15% direct-mJy | Descriptive residual / assumed conditional sigma |
|---|---:|---:|---:|
| F090W |0.434|1.653|−3.260|
| F115W |3.906|14.676|−16.226|
| F150W |3.003|0.549|+4.249|
| F200W |2.120|0.159|+4.219|
| F277W |9.740|2.237|+4.708|
| F356W |68.694|16.399|+4.806|
| F444W |644.880|22972.845|−227.056|

The enormous omitted-F444 prediction records the lack of control of an overall
red extrapolation when that decisive band is removed; it is not a forecast of
actual source variability. Each retained-band fit uses the covariance submatrix,
and conditional residuals remove the stipulated common covariance term.
Parameter search and shared selected morphology prevent calibrating these
numbers as discovery or exclusion probabilities. The prediction table should
be read as failure locations of the model family.

The new best fits improve the old finite Bobcat **single** objective, but neither
chemistry subset passes the pilot's adequacy criteria. No refinement is warranted
from this pilot alone. Cloudy atmospheres, galaxy spectra, source-specific PSFs,
calibration and independent medium bands or motion remain useful alternatives.
No stellar/dwarf/galaxy identity or physical redshift has been established.

## Reproduction, acquisition accounting and validation

```bash
python -m data_pipeline.survivor_deep_data --output /tmp/jwst-deep
python -m discovery.survivor_flame --input /tmp/jwst-models --deep /tmp/jwst-deep \
  --photometry research_output/survivor_deep_model.json \
  --output /tmp/source46-flame.json
python -m pytest tests/test_survivor_flame.py tests/test_survivor_multiplicity.py
```

The CLI downloads only the pinned73MB table if absent. The raw archive stays
outside git; manifests and compact predictions, dual convention audit, code/
photometry hashes, convergence/runtime and original covariance are versioned.
New unique selection is77,133,810bytes: archive73,013,302, author notebook410,723,
paper3,687,767 and metadata22,018. A wrapper receipt error discarded a complete
first table transfer; retry adds73,013,302 transfer bytes, recorded separately.
Total transfer150,147,112bytes remains below200MiB; restored53,282,944 bytes
are separately accounted, not newly selected science.

Twenty-three relevant source-data/model tests pass, including seven new joint
solver tests (three new-family and four multiplicity controls):
they reject incompatible units/AB zeropoints, invalid physical/filter headers,
and compare vectorized full-covariant retained-band fitting with independent
scalar GLS while verifying withheld observations cannot leak into fits. Independent
actual-table validation must precede merge; authors are not sole validators.
