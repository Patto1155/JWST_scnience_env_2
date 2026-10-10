# Geometry-frozen three-band selection response pilot

10 October 2026; starting master `379ff35786aff31535335bbe7d1de114f91dd3c4`.
This extends the previous observed-template injection operator without changing
its historical contract. **No survey completeness, real-source contamination,
source identity or cosmological population likelihood is established.**

## Question and frozen design

The question is whether morphology, colors, crowding/background structure and
source-count assumptions can change the joint centroid-plus-color response even
at identical finite source flux. Competing predictions are a flux-only response
versus a morphology/association-dependent response. Expected information gain is
a bounded test of a selection operator that previously had no multiband selector,
unmasked spatial controls or fresh count realizations.

Before inspecting trial outcomes, design commit `ca5e16e` froze one 40-arcsec
GOODS-S DAWN patch centered at RA 53.120000, Dec −27.810000 degrees. This was a
geometrical choice, separated from the earlier candidate-centered patches. It
was not selected using candidate brightness, redshift or recovery. Public SCI
and inverse-variance WHT inputs for F090W/F200W/F444W total **15,517,440 new
bytes**, against a 60-MiB pilot cap and 150-MiB track allocation. Hashes, precise
URLs and byte sizes are pinned in `data_sources/selection_pilot/manifest.json`.
Recovery of already pinned modeled PSFs is accounted separately.

All 16 fixed 4×4 lattice sites have full valid 49×49-pixel coverage in all bands.
The full input field is 0.444 arcmin²; the 16 disjoint 2.45-arcsec square
trial stamps sample only 96.04 arcsec² (0.0267 arcmin²). Depth enters through
actual local WHT and the frozen uninjected detector threshold; no local-depth
cut or nominal summed-EXPTIME exposure assignment is used.
No science-flux mask filters sites: observed sources, blends and background
structure can occur. Their 8-arcsec lattice spacing makes pixel stamps disjoint.
Checkerboard labels `pilot`/`heldout` are **spatial diagnostic strata**; both
share the fixed global uninjected median/scatter used by the detector. There is
no trained threshold, tuning, independent calibration validation, coverage
validation or independent field/visit claim.

Three noiseless finite profiles are constructed from restored, verified JADES
DR5 **modeled**, rather than empirically measured, PSFs: point, PSF-convolved
Gaussian (major sigma 0.12 arcsec, axis ratio 0.65), and equal pair (separation
0.4 arcsec). These are morphology classes, not verified stellar/galaxy labels.
Resampling retains 98.45%, 97.19%, 94.89% of the supplied F090/F200/F444 finite
PSFs before explicitly declared 49-pixel renormalization. Fluxes therefore
refer to the finite model, not calibrated infinite-aperture galaxy totals.

Finite F444 flux is 20 or 80 nJy. Colors F090:F200:F444 are 1:1:1,
0.2:0.5:1 or 0.03:0.1:1. Two fresh source-count draws are made for each
site/profile/flux/color/gain cell: **1,152 trials**, retaining actual background
pixels. Fixed five-sigma segmentation uses at least five connected pixels and
one centroid within 0.2 arcsec. Forced signed photometry uses a 0.2-arcsec
aperture minus the scaled mean in a 0.4–0.6-arcsec annulus. The declared red
operator requires formal diagonal F444 aperture SNR ≥5, F090/F444 <0.1,
F200/F444 <0.25, and centroid recovery. It is a bounded pilot operator, not
silent validation of the historical native-grid classifier.

## Measured response and its uncertainty

The executed pilot took **24.75 seconds** (maximum resident memory 229,684 KiB).
The table uses the assumed 10-electron/nJy output-grid count model and the
8-site checkerboard diagnostic stratum. Each site has two count realizations;
counts below are realizations, not independent skies.

| Finite red-profile flux | Centroid matches | Joint red passes | Conditional site-bootstrap interval for joint response |
|---|---:|---:|---:|
| Point, 20 nJy | 16/16 | 11/16 | 0.375–0.9375 |
| Extended, 20 nJy | 12/16 | 6/16 | 0.125–0.6875 |
| Pair, 20 nJy | 8/16 | 3/16 | 0.0625–0.375 |
| Point, 80 nJy | 16/16 | 16/16 | 1–1 |
| Extended, 80 nJy | 16/16 | 16/16 | 1–1 |
| Pair, 80 nJy | 6/16 | 6/16 | 0.1875–0.625 |

For the 80-nJy pair, all 16 color measurements enter the red bin, but only six
have a uniquely associated centroid. This rejects a flux-and-color-only
recovery premise under the declared model/association operator. It does not
imply physically brighter binaries become harder to observe. The finite pair
places component centers at the association gate; deblending and centroid
assignments are part of this controlled ambiguity.

Expected F444 aperture-minus-annulus responses are 0.749, 0.579 and 0.351 of
finite injected flux for the point, extended and pair profiles. The compact
artifact reports both total assigned flux bias (which includes existing scene
flux) and paired source response minus the same unmodified scene. Pairing
isolates the implemented insertion response; it does not yield a second,
independent observed galaxy or a native instrumental calibration.

Unmodified controls have one centroid match in 16 unmasked sites and **zero
joint red passes**. No blue/intermediate model in the checkerboard diagnostic
stratum passes the joint red selector (0/192 realizations each). These are
conditional controls only. Unknown real object labels, a tiny prescribed model
family, the fixed field, source association and spatial covariance prevent
interpreting them as a measured astronomical contamination rate.

The 1,000-resample intervals average the two realizations within each site,
then resample sites. They describe this scene/model/operator design and have no
calibrated 95% coverage guarantee. The eight-site strata, repeated scenes,
shared mosaic contributors, PSF models and unknown instrumental systematics are
not replaced by 1,152 independent trials. Degenerate 1–1 intervals do not bound
unseen failure probabilities.

## Dominant incomplete calibration

DAWN headers provide PHOTFNU, summed EXPTIME, drizzle kernel/pixfrac and
contributor inventories. They do **not** recover local effective electrons/nJy
or source-photon transport through the native drizzle operator. The pilot's
1 and 10 electrons/nJy are explicit nuisance assumptions on the output grid,
not measured gains or empirically justified confidence ranges. All three bands
use the same prescribed gain for this controlled sensitivity experiment.

This assumption is decisive: at 20 nJy in the diagnostic stratum, joint red
point response changes from **1/16** at gain 1 to **11/16** at gain 10;
extended/pair response changes from zero to 6/16 and 3/16. These numbers cannot
be promoted to an astronomical selection function until the count conversion
and native source covariance are recovered. Existing correlated background
pixels are retained, but source-shot covariance is not empirically transported.
The source-Poisson requirement is therefore **partly implemented, incompletely
calibrated**, and no further grid expansion is justified yet.

An analytic photon-transport counterexample is included in the compact output:
N~Poisson(20) split evenly into two adjacent output pixels has covariance
[[5,5],[5,5]]. Independent Poisson output pixels with equal expected means have
diagonal covariance 10 and zero cross-covariance. The signed pixel-difference
variance is 0 versus 20. This exact counterexample demonstrates why output-grid
Poisson noise is not a substitute for the actual measurement operator; it is
not an empirical claim about a particular JWST drizzle kernel.

## Validation and reproduce

Independent PSF/noise review checked the pre-outcome design, signed operator,
source-count moments, all 72 summary groups, bootstrap fractions/intervals and
paired-response arithmetic against the complete trial table. Output-grid gain,
modeled PSF, finite flux and diagnostic-strata limitations are required parts
of that approval. Eight new offline tests cover source moments, fresh flux
fluctuations, finite-profile conservation, signed sky rejection, color gates,
invalid count models, frozen-plan tampering and shared photon covariance.
The adjacent focused suite passes **32 tests**; focused lint passes. Integrated
CI and merging remain coordinator-owned.

```bash
python -m discovery.selection_pilot acquire --input "$SELECTION"
python -m data_pipeline.survivor_deep_data --output "$DEEP"
python -m discovery.selection_pilot freeze --input "$SELECTION" \
  --psf-input "$DEEP" --plan /tmp/selection_pilot_plan.json
python -m discovery.selection_pilot execute --input "$SELECTION" \
  --psf-input "$DEEP" --plan /tmp/selection_pilot_plan.json \
  --output /tmp/selection_pilot_response.json \
  --full-output /tmp/selection_pilot_trials.json
python -m pytest -q tests/test_selection_pilot.py \
  tests/test_observed_template_injections.py tests/test_deep_control_recovery.py \
  tests/test_deep_reference_comparison.py tests/test_real_validation.py
```

Full trials remain outside git. Canonical trial content SHA256:
`e290d6813cd7a6ec12212d7ec363fa99ae0a5767991ff98fbbd0fe0e0a6119e6`.
Committed plan and compact response preserve raw-input hashes, contributor
lists, profile hashes, counts, uncertainty diagnostics and assumptions.
Re-download timestamps do not enter the scientific frozen-design identity.

The next experiment by information gain is recovering calibrated native
count/drizzle operators in this same fixed field, then empirical PSFs and
neighbor models. A visit-disjoint field with externally validated labels is
required for real selection/contamination calibration. Geometry-only site
selection removes candidate targeting from this particular pilot, but does
not make one GOODS patch representative of a cosmological galaxy population.
