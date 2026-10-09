# Final spectral round: physical multiplets across wavelength and noise alternatives

This experiment executes **336 fresh native spectral fits**: 28 prescribed
Te/ne cells × two instrumental resolution families × three fixed noise models
× original or DUMMY-predicted wavelength grids. It composes merged version2
N IV]1483+1486 physics (PR #49) with the separately reviewed compact wavelength
and spatial-covariance inputs (PR #50). Its base `98e4e2e` also contains the
version2 conditional yield bridge (PR #51). All alternatives share observations;
their likelihoods are not pooled or assigned model probabilities.

## Reproduce and validate

```bash
python -m tools.jwst.composed_spectral_refit
python -m pytest tests/test_composed_spectral_refit.py tests/test_niv_doublet_refit.py \
  tests/test_multiplet_refit.py tests/test_mom_native_wavecorr.py -q
```

The existing merged grids and compact arrays are sufficient; no additional
public data, raw-pixel extraction, GWCS runtime or PyNeb installation is needed
for this replay. Every fit uses its own normalized version2 physical multiplet
response, full native wavelength grid before quality selection, jointly fitted
continuum, and fresh 5×5 flux covariance. Its fixed source-amplitude covariance
uses formal shared-exposure blocks, measured empirical column transport, or
measured empirical row+column transport. Every ionic projection uses that same
cell's summed doublet emissivity and freshly fitted covariance.

Independently pinned inputs are:

| Input | SHA256 |
|---|---|
| Wavecorr report | `80ca86e7969e82bca424a963b39282f2fec42d589fb055238b4ac18510ab3fe6` |
| Wavecorr compact NPZ | `6ac87fb9fcb527b951f9dccf6e4a40fcae5ee78c0f85a55bfb2d93ac55281cb0` |
| Version2 atomic grid | `a48ea0076ae9f6ef4d76845644880776c266efce0a281b0866d12889e36b1e0e` |
| Version2 component grid | `692ce2fe0ca5463708abfa3c232378f3aebe22ff9b96f97d779091d54ac5f474` |
| Previous original-wavelength version2 result | `446c1f7a35ed8c8e272ba277576088f7a4dbbd6d75dcceb2dd6c1767b2891b63` |

The loader replays the pinned wavelength prediction and its 12 fixed-template
controls. The original four version2 families additionally reproduce all 112
previous flux/covariance results exactly on this runtime. Data, model and
software receipts are recorded in `mom_composed_spectral_refit.json`.
No earlier report, grid or default template changes.

## Reference cell and full-grid sensitivity

The table uses common Te=20,000 K/ne=1,000 cm^-3. Intervals are signed conditional
Gaussian 95% Fieller sets for **observed-two-stage ionic** N/C. Grid counts state
how many of the 28 deterministic cells admit zero or an ambient **ionic**
reference of 10^-0.60=0.2512. Those counts are sensitivity summaries, not
posterior weights, confidence coverage or elemental-abundance tests. Matching
this ionic reference to elemental solar N/C would additionally assume equal
observed carbon/nitrogen stage fractions, which are not measured.

| Wavelength hypothesis | Resolution | Fixed noise model | Ionic point | Conditional 95% set | Cells admitting zero / 28 | Cells admitting ionic ambient / 28 |
|---|---|---|---:|---|---:|---:|
| Original | Nominal | Formal shared | 3.1679 | [0.9005,6.6821] | 0 | 0 |
| Original | Nominal | Empirical columns | 3.1274 | [-0.3159,10.6041] | 26 | 28 |
| Original | Nominal | Empirical rows+columns | 3.1304 | [-0.3196,10.6266] | 26 | 28 |
| Original | Generic point | Formal shared | 2.7845 | [0.6250,6.0940] | 0 | 0 |
| Original | Generic point | Empirical columns | 2.7504 | [-0.5064,9.5916] | 28 | 28 |
| Original | Generic point | Empirical rows+columns | 2.7535 | [-0.5058,9.5970] | 28 | 28 |
| DUMMY prediction | Nominal | Formal shared | 3.3979 | [1.1812,6.8866] | 0 | 0 |
| DUMMY prediction | Nominal | Empirical columns | 3.3783 | [0.0447,10.8065] | 3 | 16 |
| DUMMY prediction | Nominal | Empirical rows+columns | 3.3828 | [0.0427,10.8325] | 3 | 16 |
| DUMMY prediction | Generic point | Formal shared | 3.7006 | [1.2673,8.0908] | 0 | 0 |
| DUMMY prediction | Generic point | Empirical columns | 3.7212 | [0.1059,14.5478] | 0 | 18 |
| DUMMY prediction | Generic point | Empirical rows+columns | 3.7236 | [0.1077,14.5265] | 0 | 18 |

![Signed reference-cell ionic intervals](../research_output/mom_composed_spectral_refit.png)

All 336 measured Fieller sets in this experiment are bounded; signed negative
endpoints remain intact. Direct quadratic membership is also tested on
unbounded, empty and degenerate ratio sets, so counting does not silently clip
or omit those possibilities. The static figure shows the twelve reference-cell
sets, not a probability band or the full temperature/density uncertainty.

## What changes and what remains conditional

Transporting the measured row correlations changes the reference ionic points
and endpoints very little compared with transporting columns alone. In contrast,
the wavelength hypothesis changes numerator sign support. For the generic point
family with empirical rows+columns, the original-grid result is
**2.7535 [-0.5058,9.5970]**, while the pinned prediction gives
**3.7236 [0.1077,14.5265]**. Both admit the ambient ionic reference at this cell.
Original-grid empirical families admit it in every sampled cell; the DUMMY
prediction excludes it in some cells under these fixed assumptions.

The reference is explicitly labelled **DUMMY / MOS simple toy model** by its
publisher. Replaying its planned source-position offsets and original-GWCS
dispersion is a versioned instrumental sensitivity, not empirical wavelength
calibration or a source-specific LSF posterior. A positive signed lower endpoint
under that hypothesis does not validate the hypothesis. The formal-covariance
results likewise cannot be chosen merely because their bounds are tighter.
No averaging across these alternatives or preference probabilities is reported.

The rejected shortcuts are pooling reprocessed observations as independent
evidence, using the old single-line N IV emissivity on a physical doublet total,
selecting only formal errors, and treating the DUMMY prediction as calibration.
It would also be incorrect to state that every alternative admits zero: the
explicit model contrast in the table must remain visible.

## Independent checks and prioritized next experiments

Tests independently project all 336 full fitted covariances and solve the signed
Fieller quadratic, checking literal endpoint inclusion against the saved counts.
They retain the distinct noise/wavelength families, source/model byte pins and
version2 flux definitions; consistent calibration-metadata substitutions fail
closed. The original-quartet replay and separate twelve-fit loader controls are
execution checks, not substitutes for raw-data calibration validation.

The unresolved observations and assumptions are source-specific wavelength/LSF
and extraction calibration, stationary transport from off-trace noise, unknown
He II/O III] mixing, C IV transfer/stellar contamination, and common homogeneous
Te/ne. Elemental N/C still needs f_C/f_N, and no measured ionization correction
exists here. The Cue emulator omits N IV], so it cannot close the full map.
None of these alternatives identifies a polluter, galaxy-formation mechanism
or cosmology.

The next spectral work should first constrain source geometry, wavelength and
instrumental response with an empirical calibration; then profile explicit
He/O mixture and C IV-transfer models with the version2 templates; and finally
fit a composition-aware N IV]-inclusive photoionization grid. Follow-up yield
or cosmology predictions should retain these versioned alternatives and their
covariances rather than convert the sensitivity table into model odds.
