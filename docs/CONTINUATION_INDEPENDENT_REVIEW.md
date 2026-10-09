# Independent continuation review and new aperture counterexample

Executed 9 October 2026. Incoming verified master was `e9975a1` (protocol PR30,
scientific baseline PR29). Eight specialist workstreams retain distinct
ownership; this report audits their contracts independently. The reviewed
commits are astrometry `529a326`, real sources `97655bd`, atomic `8ccb576`,
noise `a343e5a` and photometry acquisition `07b28a0`. Later versions require
separate review. No source, abundance, enrichment or cosmology discovery follows.

## Actual-input reproduction and independent oracles

The repeat experiment reran from the two actual, independently pinned SMACS
F444W integrations and reproduced the full JSON exactly: nine nominal
nonpersistent proposals; one persistent aperture patch, source 1043. Detector1
ASDF logs have disjoint native contributors. Both integrations have effective
exposure 837.468 s, separated by 0.25648 hours; common calibration remains. Relative
frame fit/evaluation uses disjoint 345/352 controls, with candidate neighborhoods
excluded. Source1043's nearest segmented centroid remains 0.951 arcsec away.
It is an aperture patch, not a separately identified source.

The geometry-selected deep-control experiment also reproduced its full JSON
exactly: 14 unique sky groups, three historical seeds and eleven additional
controls; no additional robust high-z group. Seven satisfy the strict original
footprint denominator. Every deep cutout includes the original integration and
pairwise shares 58/50/50 contributors. The area-matched detector counterexample
is a failure of centroid association, not absence of measured flux. These counts
are conditional on targeted footprints and catalog labels.

The complete PyNeb 1.1.32 28-cell atomic grid independently regenerated exactly
from the pinned wheel. A separate inverse-emissivity matrix and polynomial-root
Fieller oracle recovers the 20,000 K/1,000 cm^-3 two-stage ionic ratio:

| LSF assumption | Ionic ratio | Full-covariance conditional 95% | Incorrect independent-lines scenario |
|---|---:|---|---|
| Nominal slit | 8.828314 | 3.877742–18.306064 | 3.793496–18.968927 |
| Generic point | 8.875985 | 4.276097–17.817773 | 4.233681–18.095011 |

This validates algebra and pins, not homogeneous gas, line interpretation,
ionization closure or elemental N/C. The observed template assumes equal
CIII/NIII multiplet weights while atomic ratios depend on density; its use is
an explicitly conditional total-flux map, not a self-consistent density fit.
Independent negative/NaN emissivity, duplicate cell, wavelength, version and
flux-unit counterexamples all fail closed after the review-requested guards.

For all 18 real noise band/radius/mask sample sets, a separate checkerboard
cross-fit reproduced both signed 5-sigma tail counts. Independent covariance
identities `Var(A−B)=Var(A)+Var(B)−2Cov(A,B)` agree within 2.9e-15 relative. The
binomial zero-event upper limit is independently derived as
`1−0.025^(1/n)` for nominal two-sided 95%, conditional on independent trials.
Thousands of selected blank apertures cannot calibrate a 2.87e-7 Gaussian tail.
Source-mask conditioning, overlapping pixel pairs and shared calibration remain.

All 35 photometry acquisition inputs were independently SHA256/size checked,
including 21 SCI/WHT 480×480 cutouts with BUNIT `10.0*nanoJansky` and header
NDRIZIM 35–102. Seven actual SVO tables contain wavelength/transmission arrays.
Total 52,332,339bytes includes three reused PSFs ; 46,932,339 new bytes. These are
pinned public versions, not independent epochs or empirically calibrated PSFs.

## New pixel experiment:1043 depends on aperture and background

`discovery.continuation_review` independently converts the actual MJy/sr images
to Jy using finite celestial Jacobians rather than production spherical polygon
areas. At the original 0.188731 arcsec radius the fluxes agree to 6.7e-8 relative.
Thus the persistent signal is not explained by a Jy/surface-brightness unit bug.

| Angular radius, arcsec | Repeat/reference aperture-flux ratio |
|---:|---:|
| 0.10 | 1.115095 |
| 0.15 | 1.053753 |
| 0.188731 | 1.014903 |
| 0.25 | 1.006833 |
| 0.30 | 1.001462 |

Using the same 0.377462–0.629104arcsec annulus, replacing its full mean by each
quadrant mean changes original nominal-radius flux by −12.745% to +8.804%, and
repeat flux by −12.822% to +8.723%. These directional backgrounds are counterfactual
nuisance operators, not preferred calibrations or confidence intervals. The
aperture ladder reuses the same photons. The small-aperture ratio change does
not establish variability: centering, sampled PSF and bright-neighbor structure
are unresolved. The result motivates deblended neighbor/spatial modeling before
source 1043 can enter an astrophysical catalog.

## Reproduce the independent artifact

Use the locked Python 3.12 environment. Run the worker report commands for the
repeat JSON, deep control JSON and full blank samples. The independent oracle
imports no new specialist measurement module:

```bash
python -m discovery.continuation_review \
  --repeat-manifest /cache/smacs-repeat/images_manifest.json \
  --repeat-result research_output/smacs_independent_repeat.json \
  --blank-samples /cache/smacs_empirical_blank_samples.json \
  --spectrum research_output/mom_z14_point_resolution.json \
  --atomic-grid research_output/mom_atomic_grid.json \
  --output /tmp/continuation_independent_review.json
python -m pytest tests/test_continuation_review.py
```

Input hashes, signed fluxes, diagonal errors, background-sector variants and
independent covariance results are in
`research_output/continuation_independent_review.json`. Raw image and full sample
arrays stay external. Mathematical controls check covariance/scale invariance,
signed ratios and refusal to represent unbounded cases as finite intervals;
they do not substitute for the actual-input experiments.
