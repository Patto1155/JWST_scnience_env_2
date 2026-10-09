# Independent follow-up review

9 October 2026. This addendum updates [the first review](ADVERSARIAL_REVIEW_R3.md)
against the experiments built on merged PRs #14–19. Its earlier acquisition
recommendations describe that round's state, not remaining archive blockers.
Successful arithmetic and reproducible measurements do not certify discoveries.

## Earlier open experiments now completed

* **Blue and middle-band PSF inputs:** F090W and F200W point templates are now
  acquired alongside red templates. The native operator follows the actual
  WCS, source phase, valid-pixel masks, physical SCI units, integer pixel-center
  aperture and mean annulus used by production photometry. A generic point
  model remains conditional on source extension, detector position and PSF
  orientation; it is not an observed galaxy calibration.
* **Frozen seven-proposal repeat test:** actual F444W sibling images now test
  each first-round screen survivor. ID 98 persists under the stated measured
  depth; the other six fail at least one covered comparison at diagonal errors.
  One second comparison for 361 has partial coverage and remains untestable.
  Error multipliers are explicit sensitivities: 336 becomes inconclusive at
  10× errors. Nonpersistence does not identify a source's physical nature or
  measure a survey-wide false-positive rate from this selected seven-item list.
* **Original-image coverage:** required blue/middle images are now selected by
  simultaneous valid sky coverage, avoiding disjoint SMACS quadrants. A bounded
  40×40 sampling grid ranks pairs; the resulting valid-pixel area is separately
  measured. Neither quantity is a completeness-weighted survey volume.
* **Native MoM data:** all nine original calibrated exposures are acquired and
  identity verified, rather than being an outstanding data-volume dependency.
  Total actual bytes are 464,135,040; per-file sizes range from 51,560,640 to
  51,575,040. Native SCI/ERR/DQ/wavelength, pathloss and variance inputs are
  accessible. Reconstruction of matched native nod/exposure spectra is still
  analysis work, not a claim that these files cannot be obtained.
* **Instrumental resolution:** a pinned author-code derivative supplies a
  generic point-source R curve. It is not the exact published runtime or a
  source-specific full LSF. The preceding fully illuminated curve remains
  explicit provenance; the new report records point-resolution scenarios.

## Independent numerical and input checks

Four cross-implementation controls inject a one-Jy elliptical PSF on a rotated
WCS at fractional phase, with and without invalid SCI/WHT pixels, in both Jy
and MJy/sr. The production photometer independently reconstructs aperture and
annulus geometry and physical conversion. Its measured net flux agrees with
the modeled aperture response to 10⁻¹² absolute precision, and valid pixel
counts agree. An additional manual injection on an actual F444W WCS gave
0.6999995214178533 versus modeled 0.6999995214178534.

The read-only [native audit](../discovery/adversarial_native_inputs.py) imports
neither acquisition nor its quality-count implementation. It independently
checks all nine original SHA256/byte counts against the external inventory,
each selected derivative hash, source identity, array shapes and full-slit
UV-window counts. [Saved evidence](../research_output/adversarial_followup_checks.json)
matches all five reported windows: 59, 64, 75, 85 and 95 pixels per exposure;
all are usable under finite SCI/wavelength, finite positive ERR and no
DO_NOT_USE/SATURATED. These are **all-row wavelength counts**, not source-trace
fractions, independent line detections or an empirical covariance estimate.

A direct weighted SVD solve independently reproduces the point-resolution
73-bin fit, whose production solver uses QR:

| Group | Integrated flux (10⁻²⁰ erg s⁻¹ cm⁻²) |
|---|---:|
| N IV] | 40.400942413 |
| C IV | 31.586027078 |
| He II + O III] | 23.252370332 |
| N III] | 14.410795684 |
| C III] | 20.606614667 |

Maximum solver discrepancy is 5.7×10⁻¹⁴. The summed line-flux ratio is 1.050,
conditional Gaussian 95% Fieller set [0.502, 2.047]; 29 specified point-model
scenarios span 0.619–1.413 in their point estimates. The latter range is not a
confidence interval. Removing one C IV-supporting bin gives 5.10±27.72 rather
than 31.59±9.31, but this is expected leverage for a sampled unresolved line,
not evidence that the bin is bad. Actual native DQ currently supplies no
flag-based justification to remove the influential wavelengths.

The photometry sensitivity report transfers empirical-background and point
responses only with matching input hashes and measurement operators. The
screen has seven diagonal-error survivors, six with median empirical noise,
and seven with median noise plus point response. The point scenario promotes
ID 254, illustrating a selection boundary rather than a confirmation. The
bright released JADES sample has 23 reference controls: 22 pass the first
F444W sibling comparison, with one untestable, and all 23 pass the second.
The covered SNR≥10 subsets therefore contain 22 and 23 objects, respectively,
with median flux ratios 1.035 and 1.007. These controls demonstrate measurement
consistency at their brightness, not the faint high-redshift completeness.

## Counterexamples corrected

The review supplied a coherent-cache counterexample: cached `altered` bytes
with their own valid receipt were accepted against an externally pinned
`correct` manifest. The acquisition fix independently enforces manifest SHA,
size and per-product budget on cache hits, with a regression that forbids
network access. A further direct receipt gate checks fresh inputs before
extraction. This is defense in depth: the actual lower-level fetcher already
enforced the prepared SHA/size pins before publication. The new regression
uses a replaced fetcher returning coherently wrong bytes, and rejects them
before extraction.

An empty spectral native-batch manifest also returned both “all usable” booleans
as true and claimed the full exposure set was available. The follow-up guard
now requires the exact nine identities, externally pinned original and derived
bytes, verified source SLITS nods and all required UV groups. The original empty
manifest counterexample is rejected. Empty wavelength support instead reports
`not_estimable`, and rendered prose follows that status. Actual nine-exposure
inputs independently pass the stricter gate. Mathematical truth of an empty
`all()` is not observational evidence.

The rotating-star table uses solar log(N/C)=−0.63, while MoM uses −0.60. On
MoM's common scale, selected top-heavy EMP and Salpeter Pop III benchmarks are
respectively +0.73 and +0.25 dex, rather than +0.76 and +0.28 on the original
paper scale. Only the first falls inside the quoted MoM marginal interval
[0.27, 1.19]. The 0.02-dex gap for the second is not statistical rejection;
model systematics and a marginal box cannot supply a model probability.

## Chemistry and claims that remain unsupported

The covariance-aware chemistry calculation defines, but does not measure,
the physical nuisance factor Q in F_N/F_C=Q(N/C). Its Fieller calculation
retains full fitted covariance and disconnected/unbounded sets. Required Q
values for conditional targets are not calibrated stellar or nebular predictions;
Q can itself change with density, ionization, chemistry and cooling.

The nominal-resolution chemistry report intentionally keeps its own 31-scenario
input hash separate from the new point-resolution report. A further comparison
now preserves the separate 31/29 scenario families, requires the same pixel
SHA, and leaves the original saved nominal calculation unchanged. Required
central Q changes by 1.033%, while a conditional 95% lower threshold changes
by 11.932%; neither calibrates Q or excludes a stellar population. Under the selected
36-case grid, independently recomputed Cue-median compatibility counts are
0/36, 24/36, 12/36 and 12/36 for the four SMS yields. The O/H–C/O endpoint box
is a necessary marginal check, not a joint confidence region or likelihood.
The 100,000-Msun yield's 0.007-dex shortfall below a fixed 1.70 target is not
evidence against a population. Published Cue and ionic-temperature analyses
are distinct; their intervals are not pooled.

The updated evidence still rejects seven confirmed high-z galaxies, a global
artifact interpretation of all unselected proposals, universal point corrections,
fully calibrated bootstrap coverage, elemental N/C from summed UV flux alone,
and a selected WR/VMS/SMS/rotation/AGN mechanism. No dark-matter or black-hole
cosmology claim follows from this screen, whose selection function and galaxy
redshifts remain unmeasured.

## Reproduction and remaining high-value work

```bash
OPENBLAS_NUM_THREADS=1 python -m pytest -q \
  tests/test_adversarial_native_operator.py tests/test_adversarial_noise_controls.py
python -m discovery.adversarial_native_inputs \
  --native-dir /path/to/acquired/native/products
```

The operator tests require the native-PSF follow-up; the native audit requires
the tracked nine-exposure inventory and batch report. Focused reviewer gates
passed: four new operator controls, three exact-noise controls, 13 native PSF
controls, 15 photometry/coverage/replay controls, 10 repeat/astrometry controls,
33 point-resolution/line controls, 13 acquisition/deep/native controls, and
28 chemistry/enrichment controls on their inspected trees. Integration CI is
a separate gate; passing component checks is not evidence of sky truth.

Highest value now: reconstruct native nod/group spectra with matched point
pathloss and source-trace/background geometry; measure covariance from controls;
obtain resolved N/C density and He II/O III] diagnostics; constrain emitting gas
mass and element retention; and evaluate persistent imaging proposals with
multi-band SED/redshift and a selection-function calculation. These answer
specific remaining uncertainties rather than reclassifying accessible inputs
as external dependencies.

## Final observed-star aperture follow-up

Specialist commit `2a37fa1` adds actual M92 F444W aperture measurements rather
than synthetic-source recovery alone. All 40 stellar/native-PSF/noise controls
pass, including 11 new covariance, physical-unit, DQ, mask, centroid and
source-group controls. The review reran the full actual-data experiment:
its compact report is byte-identical (SHA256
`17397e03b37fa688b3d41fb55b9b483853d448aa7f5eefb82b757473d85a07e3`).
Code hash and the canonical 220-record hash agree. Independently dividing
saved measured fluxes, checking exact epoch-0/1 pairs, and recomputing all nine
source-bootstrap configurations reproduces every median and interval.

The fixed catalog-quality/isolation screen yields 56 candidates; all are
attempted, the 24-star cap is not reached, and 11 identities survive both
images. The 45 documented failures comprise 13 masked/saturated cores,
20 background-coverage failures, seven ambiguous centroids, two reference
coverage failures and three low-reference-SNR cases. This is a selected bright
reference sample, with unresolved faint neighbors and selection effects; the
two dithers share a visit and are not 22 independent stars.

The production science aperture divided by a **finite 0.8-arcsec reference**
is 0.78396, with conditional source-bootstrap 95% interval [0.75448, 0.80694].
The comparable modeled finite-aperture ratio is 0.76316. Comparing the observed
ratio with a modeled whole-template response near 0.6975 would mix denominators
and is rejected. Shared aperture/annulus pixels enter ratio covariance, while
interpixel detector correlation and field/calibration systematics remain absent.

The unmasked-background ratio is 0.99264; alternate masked background gives
0.77929. Forced catalog centering loses about 5% median science-aperture flux
relative to the bounded image centroids. Background and centering effects thus
remain measurable even in this quality-selected sample. The smallest-aperture
observed cores exceed the sampled modeled phase/scale envelope; the diagnostic
plot displays that discrepancy and labels finite references, dependent dithers,
conditional intervals and excluded systematics. Agreement at the production
radius does not validate the template at every radius, establish total flux,
or permit universal transfer from native M92 pixels to resampled GOODS-S
products or extended galaxies. Exact-product isolated-star calibration remains
the highest-value photometric follow-up.
