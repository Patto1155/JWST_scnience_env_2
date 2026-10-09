# Native-nod chemistry follow-up: weaker information than the old coadd

The independent native reduction is frozen at report SHA256
`88e3cdbf5b7759eaad84dc21ead0974c38f392292d71ce605fa0f5b5951637ec`
(spectroscopy commit `378c764`). This follow-up applies the merged PyNeb atomic
map and Cue v0.1 predictions to its four distinct resolution/noise scenarios.
These scenarios and the earlier public coadd share observations. Their
likelihoods are **not multiplied** or described as independent confirmation.

```bash
python -m tools.jwst.atomic_grid --spectrum research_output/mom_native_reduction.json \
  --output research_output/mom_native_ionic_fit.json
python -m tools.jwst.cue_grid /path/to/atomic-inputs/cue-v0.1.zip \
  --spectrum research_output/mom_native_reduction.json \
  --output research_output/mom_native_cue_grid_fit.json
```

The adapter preserves line order, units, signed fluxes, full covariance and
conditional sigmas. It rejects wrong units/order or disagreement between sigmas
and covariance diagonals. Both outputs hash the actual frozen input bytes.
Atomic assumptions, original multiplet-template limitations, Cue geometry,
emulator uncertainty, solar conventions and the absent N IV] response are retained
from [the atomic report](MOM_ATOMIC_IONIC_GRID.md) and
[the Cue report](MOM_CUE_PHOTOIONIZATION.md).

## Executed ionic constraints

At fixed Te=20,000 K and ne=1,000 cm^-3:

| Native spectral scenario | Two-stage ionic N/C point | Formal conditional 95% Fieller set |
|---|---:|---|
| Nominal/shared formal covariance | 7.153 | [2.655,14.571] |
| Point/shared formal covariance | 6.549 | [2.257,13.677] |
| Nominal/empirical off-trace transport | 7.071 | [0.397,23.179] |
| Point/empirical off-trace transport | 6.461 | [0.146,21.708] |

For the point/empirical case, relative to solar log(N/C)=-0.60, the central ionic
logarithm is **1.410 dex**. Even in this fixed cell, its lower 95% endpoint is
**-0.236 dex**, admitting a sub-solar ionic ratio. Across the 28 prescribed
temperature/density cells, **four point/empirical Fieller sets cross zero**.
Those signed endpoints are saved; they are not clipped and cannot be logged as
physical abundances. The empirical-transport central ionic logarithms span
1.241–1.768 dex, a model sensitivity range rather than an uncertainty interval.

This contrasts with the old coadd's Te=20k/ne=1,000 result
8.828 [3.878,18.306]. The weaker native inference follows the independently
constructed flux likelihood and empirical noise transport; it does not require
changing atomic physics. Transport, profile/pathloss and LSF assumptions remain
conditional, and density-dependent multiplet templates still need refitting.
Neither central value establishes elemental nitrogen enhancement or a polluter.

## Executed photoionization sensitivity

The same 2,025 versioned Cue models are fitted to the four available UV groups:

| Native spectral scenario | Best four-group chi² | Points at delta chi² ≤3.841 | Native N/O−C/O parameter span in that set |
|---|---:|---:|---|
| Nominal/shared formal | 0.01901 | 124 | -1.00 to 1.00 |
| Point/shared formal | 0.11493 | 145 | -1.50 to 1.00 |
| Nominal/empirical transport | 0.00451 | 583 | -1.7324 to 1.2324 |
| Point/empirical transport | 0.04207 | 672 | -1.7324 to 1.50 |

These threshold sets are **not confidence regions or posteriors**. They expose
the much weaker information once measured noise is transported into the native
likelihood. About 75–81% of their members touch sampled U/density/abundance
boundaries. N IV] remains omitted because the actual versioned emulator lacks it;
no numerical substitution is invented. Low best chi² values with many flexible
parameters do not calibrate a nitrogen/carbon abundance or model identity.

The testable next dependency is a source-specific multiplet/LSF fit coupled to a
versioned N IV]-inclusive photoionization model. Source and background covariance, line transfer and geometry should be varied jointly before comparing abundance-
conditioned stellar yields. The full covariance products and rejected assumptions
here are reproducible inputs for that work, rather than discoveries.

Two further primary public model archives were inspected as possible alternatives:
[Feltre et al. 2016 AGN grid coverage](https://www.iap.fr/neogal/ewExternalFiles/README.txt)
and [Gutkin et al. 2016 star-forming grid coverage](https://www.iap.fr/neogal/ewExternalFiles/README-1.txt).
Both published line inventories omit N IV]1486 **and** N III]1750. Those archives
were therefore not downloaded as a purported solution to the nitrogen-stage
dependency. An N IV]-inclusive forward map remains genuinely unfinished model
work; its absence is not merely an observational limitation.
