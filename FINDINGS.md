# What this repo can and cannot teach anyone

An honest audit of the science claims in `research_output/`, done from the
committed JSON products. Reproduce with:

```bash
python discovery/audit_candidates.py
```

Output: `research_output/CANDIDATE_AUDIT.md`, `research_output/candidate_audit.json`.

---

## The headline number

**0 of 1732 "high-z candidates" are testable, and 0 of the 25 shortlisted ones
survive an independent check.** Not "weak" — undefined. The measurement the
selection rests on was never made.

| check | result |
| --- | ---: |
| candidates in `highz_candidates.json` | 1732 |
| where F090W was actually measured at the source position | 314 (18.1%) |
| where F200W was actually measured | 365 (21.1%) |
| **where both were measured** — the minimum for a Lyman-break test | **0** |
| blue/red pairs on physically disjoint NIRCam modules | 555 |
| survive the full audit | **0** |

Not a single source in the catalog has the two-color photometry a dropout
selection requires. The pipeline reports 1732 candidates anyway.

---

## Four defects, in order of severity

### 1. `_pick_best_dataset` chose the blue image by alphabetical accident

The old selector ranked datasets per filter independently, breaking ties on the
dataset *name string*. For GOODS-S it picked:

- reference: `..._F444W_jw01180030001_09201_00003_nrcalong_i2d` — module **A**
- blue: `..._F090W_jw01180030001_03201_00001_nrcb1_i2d` — module **B**

NIRCam modules A and B point at non-overlapping sky. `nrcb1 > nrca1`
lexicographically, so module B won a string comparison, and the F090W image for
those candidates covers none of the F444W field. Every aperture maps to
x ≈ −7870 … −3684, thousands of pixels off the array. `extract_photometry`
returns flux 0 for an off-array aperture, `_ratio_from_fluxes` divides that zero
by the red flux, and the result is a **perfect dropout for all 555 GOODS-S
candidates**.

SMACS J0723 is a milder version of the same bug: F444W on `nrcalong` (the full
129″ long-wave field) paired with F090W on `nrca1` (one short-wave quadrant).
859 of 1177 SMACS candidates fall outside that quadrant — 73% null measurements,
scored as detections of nothing.

**Fixed:** selection is now anchored on the reference filter, and every other
band is chosen by measured WCS footprint overlap (`_sky_footprint_overlap`,
`_pick_overlapping_dataset`). A filter with no overlapping exposure is dropped
from the map rather than paired with disjoint sky.

### 2. A null measurement scored higher than a real one

`_validation_summary` puts 55% of its weight on `ratio_score` +
`aperture_score`. Both are computed from the blue flux. When the blue aperture
is off-detector, the ratio is exactly 0.0 and `dropout_lt_0p05` is true at every
radius, so **both terms max out**. The code notices the band is unmeasured, but
only afterwards, and only demotes `keep` → `review`.

The consequence is visible in the shipped shortlist: all ten GOODS-S entries
score an identical **0.847** — a value produced entirely by the absence of data —
and outrank nine of the fourteen candidates that were actually measured.

**Fixed:** an unmeasured blue band now zeroes both terms and adds explicit
`*_undefined_blue_unmeasured` reject reasons. Candidate admission also now
requires the blue band to be measured, not just the reference band.

### 3. Pixel sums were treated as fluxes

`extract_photometry` sums raw `i2d` pixel values. Those are **surface
brightness in MJy/sr**, not flux. Converting requires the per-pixel solid angle,
and NIRCam short-wave pixels (0.031″) subtend **a quarter** of long-wave pixels
(0.063″). So every F090W/F444W ratio in the catalog is wrong by ~4.1×, and
`magnitude` — `-2.5 log10(sum) + 25.0`, a hardcoded placeholder zeropoint — is
not on any photometric system at all.

This one cuts *in the pipeline's favor*: correcting it makes the breaks look
stronger, not weaker. It still has to be fixed, because it makes the numbers
uninterpretable and the "color index" plots meaningless.

**Fixed:** `surface_brightness_sum_to_jansky` / `ab_magnitude` in
`discovery/audit_candidates.py`, with `f444_flux_jy`, `f444_ab_magnitude`, and
`physical_ratio_f090_f444` now written into every candidate record.

### 4. The surviving candidates are far too bright to be high-z

Once the units are right, the shortlist's own numbers refute it:

| source | m_F444W (r=3px) | implied break | pipeline said |
| ---: | ---: | ---: | --- |
| 16 | 20.49 | 8.77 mag | keep, score 0.939 |
| 451 | 20.83 | 8.62 mag | keep, score 0.940 |
| 15 | 21.99 | 6.90 mag | keep, score 0.914 |
| 955 | 22.25 | 6.03 mag | keep, score 0.865 |
| 1063 | 22.59 | 6.69 mag | keep, score 0.957 |

Confirmed z > 10 galaxies sit at m_AB ≈ 26–29; GN-z11 is ≈ 26. A z > 10 source
at m = 20.5 would be ~100× more luminous than anything ever found at that
redshift — brighter than most quasars. And an 8.8-magnitude break is larger than
a Lyman break can physically produce. Two implausible things at once is the
signature of an instrumental artifact, not a discovery.

The likely culprit is in the data selection: these are **single-exposure**
`i2d` products (`jw02736001001_02105_00004_...`). Single exposures have no
cross-dither cosmic-ray rejection, so snowballs and CR residuals survive as
bright, compact, single-band sources — exactly the profile being selected. The
`cal` / `i2d` / `crf` triplets in the catalog are three renderings of *the same*
exposure, not three independent looks, so the pipeline has no way to reject them.

The repo already detects this failure mode — `anomaly_catalog.json` flags
"heavy_tail / potential cosmic ray" on 55 datasets — and never cross-links it to
candidate vetting.

---

## Where the premise itself is wrong

You asked where you're wrong about what this can teach humanity. The code
defects above are fixable in an afternoon. The framing problems are not.

**The fields are the wrong fields.** SMACS J0723 is JWST's first-light image and
GOODS-S/JADES is the most intensively analyzed extragalactic field in existence.
Hundreds of astronomers with the full mosaics, the calibration pipeline, PSF
models, and spectroscopic follow-up have combed both. The probability that a
photometric dropout search on single exposures finds something they missed is
not small — it is zero. Any real dropout here already has a paper and often a
NIRSpec redshift.

**The data are the wrong data.** Single-exposure Stage-2b products are the
deepest structural problem. High-z work uses the deep drizzled mosaics —
hundreds of exposures, matched PSFs, proper astrometric alignment. You are
searching noise realizations that the survey teams throw away as intermediate
products. Nothing about the agent layer changes that.

**More runs cannot fix it.** `DISCOVERY_GUIDE.md` proposes scaling to 1000s of
runs. Every one of those runs would have consumed the same broken dataset
pairing and produced the same divide-by-off-chip-zero. The 1732-candidate
catalog *is* the result of scaling: it scaled a single selection bug into 1732
copies of itself. Throughput is not the bottleneck; the absence of a
falsification step that can return zero is.

**"Falsification-aware" is the load-bearing false claim.** The shortlist is
described as falsification-aware and it does compute aperture consistency, edge
distance, and coverage. But no check in it could ever have returned "no
candidates" — the scoring is a weighted sum with a threshold, and an absent
measurement scored maximum. A vetting system that cannot output zero is not
vetting.

---

## What it *can* honestly do

The infrastructure is genuinely decent, and none of the above is an argument for
throwing it away. It is real: WCS-based cross-matching, coverage and validity
masks, error propagation from the ERR extension, aperture growth curves,
provenance-tracked sidecars, campaign event streams. That is more rigor than
most exploratory astronomy scripts have.

Three honest uses:

1. **A reproduction harness.** Point it at the public JADES DR3 mosaics and try
   to recover known z > 10 objects with published photometry. If it can recover
   them and reject their known contaminants, the selection function is
   characterized and worth something. If it cannot, you have learned that first,
   cheaply. This is the only path from here to a defensible result.
2. **An artifact-characterization study.** The single-exposure products it
   already has are *ideal* for measuring the rate and morphology of snowball and
   CR residuals that survive Stage-2b, as a function of detector, filter, and
   exposure time. That is a real, publishable, unglamorous result nobody has
   fully catalogued — and this repo's failures are literally the dataset for it.
3. **A methods paper on agent falsification.** The concrete finding here — an
   LLM-driven pipeline generated 1732 candidates, 100% of them from a null
   measurement scored as a maximal detection, and its own falsification layer
   ranked the nulls highest — is a sharp, reproducible result about automated
   science. It is more interesting than another dropout catalog would have been.

The audit tool now ships in the repo so any future claim has to pass it first.
The most valuable thing this codebase produced is a precise example of how
automated discovery fails, and it earned that honestly.
