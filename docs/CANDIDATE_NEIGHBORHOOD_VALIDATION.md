# Broader neighborhoods do not yet validate component colours for 98 or 1043

10 October 2026. This follows merged master `bc7abf0` and preserves the earlier
deep two-knot and SMACS nine-background reports. **Neither candidate gains a
source identity or calibrated dropout classification.** Broader models improve
source 98's red-image residuals substantially, but the remaining discrepancies
still exceed the declared prediction gate. Source1043 remains dominated by
structured-neighbor/background assignment.

## Declared question and bounded experiment

Can explicitly modeled neighbors and extended target/neighbor light supply
identifiable, stable component fluxes that predict withheld spatial pixels?
Competing predictions: a stable target coefficient plus satisfactory predicted
residuals, versus nuisance-dependent assignments or persistent model error.
Expected information gain was to decide whether simple additional neighbor
components resolve the current colour ambiguity before fitting more SEDs.

The plan was stated to the coordinator before fitting: at most six families,
six spatial amplitude folds and three bands per candidate; no new downloads.
The stopping criterion was fixed-geometry standardized prediction RMS <=2 plus
stability across at least two accepted families within the larger of 20% of
median target flux or twice the largest conditional diagonal standard error.
This is an operational decision gate, **not a calibrated hypothesis test**.
After failure, stop classification rather than expand unvalidated conditional
SED grids. The numerical pilot evaluates 36 fits and 216 amplitude folds in
about ten seconds with BLAS threads fixed to one.

The restored actual pixels are source 98's pinned DAWN F090W/F200W/F444W cutouts
and source 1043's original singleton F090W/F200W/F444W products. All six image
hashes and three finite modeled PSF hashes are checked against earlier merged
manifests. Zero newly selected input bytes are acquired. Deep cutout FLT
contributor lists are retained; the native singleton identification is inferred
from the product filename with actual primary `NDRIZ=1` checked. It is not a new
archive-association reconstruction or independent-repeat claim.

## Geometry, template families and uncertainty contract

A 3-arcsec stamp supplies each image, with a 2.5-arcsec square fitting halfwidth.
Up to six bright, smoothed F200 local maxima outside 0.25 arcsec from the target
and separated by 0.25 arcsec define explicit neighbor positions. Five are
selected for 98; six for 1043. Coordinates are transported through each band's
actual WCS, rather than assuming equal detector orientation. The source 98
target center/axis ratio/angle come from the frozen earlier red morphology;
1043 remains at its frozen nomination coordinates. The neighbor positions are
data-dependent scene hypotheses, not a complete or classified source catalog.

The six families use:

1. An extended target, compact neighbors and a plane.
2. The extended target, compact plus 0.15-arcsec Gaussian neighbor envelopes and
   a quadratic background.
3. Point plus extended target light, the same two-scale neighbors and quadratic.
4. Target scales 0/0.10/0.30 arcsec with the two-scale neighbors and quadratic.
5. The three target scales with 0.30-arcsec neighbor envelopes and quadratic.
6. Family 4 with the modeled PSF rotated 90 degrees as a sensitivity alternative.

All coefficients remain signed. Finite PSF wings lost from the stamp are not
renormalized. Totals refer to template coefficients, not empirically measured
physical galaxy totals. Target contribution inside a fixed selection-centered
0.2-arcsec aperture is also retained. SVD after column normalization tests rank
and yields the complete conditional linear covariance and target/nuisance
correlations. Full rank does **not** establish that a model is adequate.

Six fixed classes of 0.2-arcsec spatial blocks withhold amplitudes from fitting
and measure residual RMS in supplied per-pixel ERR units. Geometry is already
conditioned on the F200 guide and, for 98, earlier F444 morphology. These are
therefore **conditional amplitude prediction checks**, not unbiased complete
pipeline cross-validation. The pixels share drizzle/calibration effects and
are not independent observing epochs. Diagonal errors omit empirical spatial
covariance, shot-noise separation and PSF calibration uncertainty. RMS or model
excursions must not be converted into detection probabilities or abundance odds.

## Results and stopping decisions

| Source | Band | Best prediction RMS / supplied ERR | Families passing <=2 |
|---|---|---:|---:|
|98|F090W|1.524|3/6|
|98|F200W|5.186|0/6|
|98|F444W|5.229|0/6|
|1043|F090W|7.400|0/6|
|1043|F200W|11.581|0/6|
|1043|F444W|15.420|0/6|

For98, adding extended neighbor/target structure improves red predictions
substantially: the plane and compact-neighbor family has RMS 33.96 in F200 and14.94
in F444, compared with minima 5.19/5.23. It does **not** supply adequate red
component photometry under the fixed prediction gate. Across all failed and
accepted template alternatives, target-total coefficients span225–598 nJy in
F200 and3,772–4,537 nJy in F444. These are model stress-test ranges, **not flux
uncertainty intervals**. Tiny conditional standard errors do not absorb the
model discrepancy.

Three F090 families pass the conditional gate. Their signed target totals are
2.05/2.26/6.99 nJy with diagonal errors2.22/2.08/5.96 nJy; all corresponding
Gaussian 95% intervals admit zero. The 4.94 nJy inter-family excursion is below
the fixed 11.91 nJy operational stability tolerance. This is compatible with a
weak/uncertain blue component; it neither establishes a counterpart nor turns
the failed red assignments into calibrated colours.

Every 1043 family fails. Adding compact and extended neighboring components
does not validate the broader scene. F090 target coefficients range−136 to808 nJy
across inadequate alternatives, versus the earlier smaller-window forced point
coefficients around 31–45 nJy. Those different windows and component contracts
cannot be equated. Their disagreement is a demonstration of background/halo
assignment sensitivity, not a revised astrophysical blue flux or confidence
interval. Compact red patch persistence from the previous distinct exposure
remains separate evidence and does not identify this structured scene.

Both candidate classifications stop. Source98 needs a validated spatial model,
empirical/source-relevant PSF and covariance before using component colours in
stellar/galaxy fits. Source1043 specifically needs the bright neighbor's
diffraction/background response modeled or an independent observation resolving
that nuisance. The new experiment rejects the sufficiency of these bounded
families under the declared conditional error model; it rejects no stellar or
galaxy class and establishes no high-redshift object.

## Reproduction and independent validation

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -m discovery.candidate_neighborhood \
  --deep-directory /path/to/pinned-deep-survivors \
  --originals-directory /path/to/pinned-originals \
  --output /tmp/candidate-neighborhood-v1.json
python -m pytest tests/test_candidate_neighborhood.py
```

[Compact versioned artifact](../research_output/candidate_neighborhood_v1.json)
contains image/input-manifest/code hashes, contributor names/status, transported
sky coordinates, every signed coefficient, full component covariance and diagnostics, all 216 fold
scores and explicit decisions for both sources. Runtime need not replay byte for
byte. Four independent mathematical oracles check signed SVD recovery and
inverse-Fisher covariance, zero/duplicate-column rejection, known spatial truth
versus omitted structure, and exclusion/separation of guide maxima.
Scientific acceptance also requires independent actual-pixel review of the
transported geometry, PSF normalization, prediction sums and error interpretation.
