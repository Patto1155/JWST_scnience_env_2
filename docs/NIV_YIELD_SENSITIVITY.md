# Conditional yield sensitivity to the N IV doublet contract

The fresh version2 total1483+1486 fits weaken the selected yield tensions. They do
not identify an elemental abundance or a polluter. The point-source empirical
covariance family has **0/28 cells above the conditional reference for every
selected yield and every tested k**. At k=1 its 1000-solar-mass SMS profile range
falls from 1.826–3.063 to 0.422–1.952. This is a paired sensitivity experiment on
the same observations, not independent evidence or a mechanism ranking.

## Observations and operators

Input contracts are the immutable [version1 physical-template result](MOM_NATIVE_MULTIPLET_REFIT.md)
and [version2 doublet result](MOM_NIV_DOUBLET_V2.md). Each has 112 fresh
five-group flux/covariance fits: four extraction/resolution/noise scenarios times
28 fixed temperature/density cells. Version1 NIV means1486-only; version2 means
the total1483.321+1486.496 group. At 20,000K and density1000cm−3 the point-source
empirical ionic ratio changes from 6.4509 [0.2601,21.1594] to
2.7504 [−0.5064,9.5916], conditional Gaussian95% Fieller sets. All28 version2
point-empirical intervals include zero; three version1 intervals did.

`discovery/niv_yield_sensitivity.py` checks frozen file hashes, separate version
contracts, matched cells and doublet-emissivity/weight closure. It independently
replays the signed two-component ionic measurement and its full2×2 covariance
from **each cell's own fit and full5×5 covariance**, using that version's atomic
response. It does not use a version1 grid validator on version2, relabel or scale
old fluxes/covariances, or rerun upstream spectral fits/raw pixels. Their numerical
replay is the upstream experiment's responsibility. All version1 artifacts stay
unchanged.

## Assumptions and inference

ElementalN/C = ionicN/C × k, with unknown k=f_C,observed/f_N,observed. Fixed
k={0.3,1,3} are sensitivity assumptions, without calibrated weights. Equal N/C
retention is assumed. The same four discrete0.1-solar SMS models yield pure-ejecta
number-ratio ceilings1.4704,35.8958,40.3823,12.3928. A solar-N/C ambient parcel
(0.25119) mixed with one ejecta model defines a ratio interval between ambient
and ceiling. The four rounded top-heavy rotating benchmarks predict0.70795,
1.34896,0.51286,0.58884; their quoted pristine dilution does not alter N/C.
Sources are the versioned primary tables pinned in
[enrichment_benchmarks.json](../data_sources/pilot/enrichment_benchmarks.json):
[SMS Table1 reproduction](https://arxiv.org/html/2601.04344v3),
[original SMS Table1](https://arxiv.org/html/2304.05013v4), and
[rotating Table2](https://arxiv.org/html/2405.11235v1). These selected cases do not
span either mechanism's model space.

For each interval divided by k, the code minimizes the full covariant Gaussian
over its nonnegative two-dimensional cone. Deviance is measured relative to the
best positive-quadrant fit; signed data and cross-covariance are preserved.
3.84146 is a one-ratio conditional Gaussian reference, **not a calibrated global
rejection rate**. Grid counts are deterministic sensitivity summaries, not
probabilities, independent trials or posterior weights.

At k=1 the counts above that reference are:

| Family | SMS1000 v1→v2 | Rotators1/2/3/4 v1→v2 |
|---|---:|---|
| Nominal formal |28→9|28/28/28/28→28/12/28/28|
| Point formal |28→2|28/28/28/28→17/2/28/22|
| Nominal empirical |0→0|6/0/13/9→0/0/0/0|
| Point empirical |0→0|0/0/0/0→0/0/0/0|

The other three SMS ceilings exceed the measured point throughout version2 at
k=1, giving zero profile deviance. At the reference point-empirical cell,
SMS1000 deviance changes2.453→0.569; rotators1/2/3/4 change
3.301/2.581/3.533/3.442→1.526/0.690/1.843/1.716. Version2 creates no new
above-reference cells among the tested alternatives. At k=3, nominal empirical
rotators3/4 retain one above-reference cell each; the point empirical family
retains none. The dependence on k, resolution and covariance prevents an
identified model exclusion or preference.

## Reproduction and remaining tests

After the version2 source dependency (PR49) is merged:

```bash
python -m discovery.niv_yield_sensitivity
python -m pytest tests/test_niv_yield_sensitivity.py tests/test_atomic_enrichment.py
```

The compact [result](../research_output/niv_yield_sensitivity.json) records all
paired cells, signed Fieller sets, 5,376 profiles, summaries, exact input/software
receipts and assumptions. New tests independently whiten both fresh covariance
families and use SciPyNNLS for every cone and unrestricted positive quadrant;
cached-output replay tolerates only1e−12 relative/absolute roundoff with exact
structure and lineage. Controls reject mismatched version responses, borrowed
cell fits, inconsistent ionic caches, wrong physical weights, unsupported
calibration claims and changed frozen bytes. Together with the earlier atomic
tests, 36 tests pass.

Next physical tests require calibrated stage fractions/CIV transfer and a
source-specific LSF/profile/covariance transport. Separated oxygen, helium and
hydrogen lines could test the independent C/O and He/H mixing predictions;
isotope predictions require an achievable observing model. Gas mass, differential
retention and complete formation/yield grids remain genuine dependencies. No
elemental inference, mechanism probability or cosmological claim follows here.
