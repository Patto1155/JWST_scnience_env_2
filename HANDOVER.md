# Handover: multi-epoch capability, and what this pipeline can actually discover

Companion to `FINDINGS.md` (the audit of the shipped candidate catalog). This
document covers what was built, what was measured against real data, and an
honest assessment of the physics reachable from here.

---

## Part 1 — What was built

### `tools/jwst/footprints.py` (new)

Sky-footprint geometry from the WCS instead of from file names.

- `overlap_fraction(a, b)` — fraction of A's pixel grid whose sky position lands
  inside B. Deliberately asymmetric: it answers "if I detect sources in A, what
  fraction can I measure in B?"
- `sky_to_pixel(bundle, ra, dec)` — returns `None` off-array rather than an
  out-of-range coordinate. This is the single guard that prevents the failure
  behind the shipped catalog.
- `modules_are_disjoint(a, b)` — cheap NIRCam module check before any FITS read.

Covered by `tests/test_footprints.py` (9 tests, all passing). The suite encodes
real NIRCam geometry and asserts the ~0.25 short-wave/long-wave quadrant ratio.

### `discovery/multi_epoch.py` (new)

Repeat-exposure vetting — the capability that was missing.

- `find_repeat_pairs()` — discovers same-target, same-filter exposures that
  genuinely share sky, and records the **time baseline** between them.
  `cal`/`i2d`/`crf` renderings collapse to one exposure, so an artifact can
  never veto itself.
- `veto_candidate()` — re-measures a candidate at the same sky position in both
  epochs and returns `persistent`, `single_epoch_only`, or `undetected_in_both`.
  Returns `None` when the position is not on both detectors.
- The verdict is interpreted **against the baseline**. A single-epoch detection
  over a few hours is a detector event; calling it a transient requires weeks.

```bash
python discovery/multi_epoch.py --pairs-only   # what repeat coverage exists
python discovery/multi_epoch.py                # apply the veto
```

### `discovery/build_universe_table.py` (fixed)

Reference-anchored, overlap-measured band selection. Beyond the earlier fix,
the choice of *which* reference exposure to anchor on is now itself scored by
how much required-band coverage it buys. That change matters — see below.

### `discovery/audit_candidates.py` (from the previous pass)

Stdlib-only falsification pass over the committed catalog.

---

## Part 2 — What the real data says

Measured by pulling the actual WCS headers of all 26 exposures from MAST via
HTTP range requests, then running the repo's own `overlap_fraction` on them.
These are measurements, not estimates.

### The bug, confirmed on real headers

| pairing | overlap |
| --- | ---: |
| GS F444W(obs030) × F090W(obs030, **nrcb1**) — **what shipped** | **0.000** |
| GS F444W(obs030) × F090W(obs026, nrca1) | 0.000 |
| GS F444W(**obs026**) × F090W(obs026, nrca1) — **recovered** | **0.231** |
| GS F444W(obs026) × F200W(obs026, nrca1) | **0.223** |
| SMACS F444W × F090W(nrca1) | 0.231 |
| SMACS F444W × F200W(nrca4) | 0.229 |

Two things follow.

First, the shipped GOODS-S pairing has **exactly zero** shared sky — confirmed
against flight WCS, not inferred from names.

Second, and more useful: anchoring on the **obs026** F444W exposure instead of
obs030 recovers *both* F090W (0.231) and F200W (0.223) on the same sources. The
audit found that **zero of 1732 candidates** had both bands measured. With the
corrected anchor, a genuine two-color Lyman-break test becomes possible on this
data for the first time — on the ~23% of the long-wave field that the short-wave
detector actually covers. That is roughly 30 arcsec², not a survey, but it is
real and it is testable.

### Multi-epoch coverage: thin, and absent where it is needed

Only two same-filter pairs in the local archive share meaningful sky:

| target | filter | overlap | baseline |
| --- | --- | ---: | ---: |
| GS-MEDIUM-HST | F277W | 0.522 | 9.54 h |
| GS-MEDIUM-HST | F356W | 0.512 | 9.55 h |

(A third, F200W obs025 × obs026, sits at 0.045 — below the 5% floor.)

Three consequences, in descending order of how much they hurt:

1. **There is no F444W repeat pair at all.** Every candidate was selected in
   F444W, and the reference band is exactly the band that cannot be
   self-vetoed. The veto machinery is built and correct; this archive cannot
   feed it where it matters. Fixing that is a download, not a code change.
2. **SMACS J0723 has zero repeat coverage in any filter.** All six NIRCam
   filters were taken within ~4.7 hours on MJD 59737 as a single observation.
   Every SMACS candidate is permanently unvettable from this data.
3. **The 9.5-hour baseline supports artifact rejection only.** It is ample for
   cosmic rays, which are per-exposure, and useless for astrophysical
   variability. Nothing astrophysical of interest changes in 9.5 hours at
   cosmological distance.

### One more thing the archive query turned up

NIRCam observes short- and long-wave simultaneously through a dichroic. The
SMACS exposure times show the pairing directly: F090W+F277W at MJD 59737.024,
F150W+F356W at 59737.123, F200W+F444W at 59737.221. So **F090W and F444W were
never simultaneous** — they are ~4.7 hours apart. Irrelevant for static sources,
but it means any variability interpretation of an F090W/F444W color has a
built-in 4.7-hour lever arm nobody accounted for.

Also worth knowing: `t_exptime` for the full SMACS o001 observation is 7537 s
per filter, across all dithers. The pipeline uses **one exposure**, so it is
working at roughly an eighth of the available depth, without the dither
combination that would reject cosmic rays for free.

---

## Part 3 — What new physics is reachable

The honest answer is: **none from this data**, and the reasons are structural
rather than fixable by better code.

I want to concede real ground first, because the pessimistic case is often
overstated. JWST *photometry* has produced genuine surprises. "Little red dots"
— compact, extremely red, abundant AGN-like objects at z ≈ 4–8 — were a
photometric discovery and remain an open problem in galaxy and black-hole
formation. The JuMBOs, free-floating planetary-mass binaries in Orion, came from
imaging and are difficult to reconcile with formation theory. Photometry can
still surprise people.

But both came from **deep mosaics with many bands, carefully controlled
systematics, and spectroscopic follow-up**. Neither came from two-band dropout
selection on single exposures. That is the gap, and it is not a gap of effort.

### Why "new physics" specifically is out of reach

New physics is a residual claim: `signal = data − (known astrophysics +
instrument model)`. You need both subtracted terms modeled to better precision
than your claimed effect. This pipeline has no SED library, no dust model, no
IMF, no PSF model, no completeness function, no cosmic variance estimate. You
cannot form the residual, so you can only find outliers — and an outlier is not
a residual. The most-cited recent case makes the point: the "impossibly massive
early galaxies" of 2023 looked like a challenge to structure formation until
spectroscopy dissolved most of them into AGN with revised masses. Photometry
proposed; it did not dispose.

The field constraint compounds it. SMACS J0723 is JWST's first-light image and
GOODS-S/JADES is the most heavily worked extragalactic field in existence. Both
have been combed with the full mosaics, the calibration pipeline, PSF models,
and NIRSpec follow-up. A photometric dropout search on single exposures is not
going to find something those teams missed.

### The one channel that genuinely touches fundamental physics

**Caustic-crossing lensed stars in cluster lenses.** Icarus in MACS J1149,
Earendel in WHL0137, Godzilla in the Sunburst arc. Individual stars magnified by
factors of thousands near a cluster caustic, flickering as intracluster
microlenses drift across the line of sight. The event rate and light-curve shape
constrain the compact-object fraction of dark matter — a real particle-physics
limit derived from imaging alone.

The requirements are specific and none of them are met here:

- a **cluster lens** (SMACS J0723 qualifies — it is a lensing cluster at z=0.39)
- **repeat imaging with month-to-year baselines** (you have 9.5 hours, in the
  wrong field)
- **difference imaging** with PSF matching and sub-pixel astrometric alignment
- a **completeness function from source injection**, because the science is a
  *rate*, and a rate needs a denominator

That last point is the one most often skipped and it is the one that converts a
detection list into a physics constraint. Constraints live in rates and limits
— "compact objects are < X% of dark matter in this mass range" — not in
anomalies. Anomalies are where claims go to die; limits are where they survive.

### What this codebase is actually well-suited to

Ranked by how likely each is to produce something real.

**1. Stage-2b artifact characterization.** Measure the rate, morphology, and
detector-dependence of cosmic rays and snowballs that survive single-exposure
calibration, as a function of filter, detector, and exposure time. Your archive
is *already the right data* for this — the very property that makes it useless
for high-z makes it ideal here. The F277W and F356W repeat pairs give you a
labelled truth set on ~51% of the field right now, today, with the code in this
PR. Unglamorous, genuinely uncatalogued, and finishable.

**2. A reproduction harness on JADES DR3 mosaics.** Point the corrected pipeline
at the public deep mosaics and try to recover known z > 10 objects with
published photometry. If it recovers them *and* rejects their known
contaminants, you have a characterized selection function — the thing that makes
any later result defensible. If it cannot, you have learned that cheaply. This
is the only path from here to a publishable astronomical claim, and it should
come before any search.

**3. A methods result on automated falsification.** The finding in `FINDINGS.md`
is sharp and reproducible: an LLM-driven pipeline produced 1732 candidates, 100%
of them from a null measurement scored as a maximal detection, and its own
falsification layer ranked the nulls *above* the real measurements. That is a
concrete, quantified result about where automated science fails, and it is more
interesting than another dropout catalog would have been. It is also the only
thing here that is genuinely novel.

**4. Archive-scale uniform search — the long game.** If you want a shot at
physics, this is the shape it takes: apply one selection uniformly across every
JWST field with repeat visits and month-plus baselines, compute the selection
function by injection, and publish a *rate or a limit*. Uniform mechanical
application across enormous archives is the one thing automation genuinely does
better than graduate students. It needs difference imaging (Alard–Lupton or
ZOGY), PSF matching, sub-pixel alignment, and injection-recovery — none of which
exist in this repo yet, all of which are well-trodden.

---

## Part 5 — Results: Stage-2b artifact characterization (done)

Recommendation #1 from Part 3 has been carried out. Four exposures were pulled
from MAST, the two same-filter pairs were compared, and the results are in
`research_output/ARTIFACT_CHARACTERIZATION.md` and
`research_output/visuals/artifact_diagnostics.png`.

```bash
python discovery/artifact_characterization.py --auto
```

### Headline

**About 15% of all 5-sigma detections in a single Stage-2b exposure are not real
sources.** The surviving-artifact surface density is 32-39 per square
arcminute per exposure.

| | F277W | F356W |
| --- | ---: | ---: |
| epochs | obs025 x obs026 | obs025 x obs026 |
| time baseline | 5.65 h | 9.55 h |
| exposure time | 944.8 s | 944.8 s |
| shared sky | 2.465 arcmin² | 2.415 arcmin² |
| sources compared | 1256 | 981 |
| persistent | 1066 | 828 |
| single-epoch | **190 (15.1%)** | **153 (15.6%)** |
| artifact density | 38.5 / arcmin² / exposure | 31.7 / arcmin² / exposure |

### Why the measurement is trustworthy

Three independent checks, all of which had to pass and did:

1. **Cross-epoch photometry is sound.** Persistent sources have a flux ratio
   between epochs of **0.993 ± 0.078** (F277W) and **0.991 ± 0.079** (F356W).
   Centred on unity, so the single-epoch population is a genuine absence rather
   than a measurement failure. This is the check the original pipeline never had.
2. **The process is stochastic and symmetric.** Searching each of the four
   exposures in turn gives single-epoch fractions of 14.5%, 15.0%, 15.7%, 16.0%.
   A depth or calibration difference between epochs would show up as an
   asymmetry. It does not.
3. **The rate is physically plausible.** 38.5 / arcmin² / exposure works out to
   ~178 events per long-wave detector per 945 s, or **0.16-0.19 events per
   second per detector**. With NGROUPS=5, up-the-ramp jump detection removes the
   great majority of incident cosmic rays, so a surviving rate around 1% of the
   incident flux is the right order of magnitude.

### Morphology: the artifacts are separable

| median | persistent | single-epoch |
| --- | ---: | ---: |
| FWHM (px) | 3.0-3.1 | 1.3-1.4 |
| area (px) | 23-25 | 7 |
| peak / total flux | 0.08-0.09 | 0.34-0.40 |

The single-epoch population sits **below the PSF width** (NIRCam long-wave PSF
FWHM is ~1.5 px at 0.063"/px) and is four times more concentrated. That is the
cosmic-ray signature: charge deposited in a few pixels with no optical
convolution. The separation is clean enough in the FWHM/sharpness plane to build
a single-image classifier from, which is the practical payoff — it would let you
flag artifacts in exposures that have *no* repeat coverage.

### The number that matters for this repo

An artifact appears in exactly one exposure, so it is absent from every other
band **by construction** and passes any dropout cut with full efficiency. A
dropout search does not suppress artifacts, it enriches them.

Against a genuine z > 10 surface density of order 0.03 per arcmin² (JWST deep
surveys find a few such objects per hundred square arcminutes), the measured
artifact density implies roughly **1000-1300 artifacts per real high-redshift
source** in a single-exposure dropout search.

That is the quantitative answer to why the shipped catalog had 1732 candidates.
Even with the cross-filter pairing bug fixed, a single-exposure search of this
kind is contaminated by three orders of magnitude. Deep mosaics with
cross-dither rejection are not an optimization — they are the whole ballgame.

### One loose end worth pulling

20 of the 343 single-epoch sources (5.8%) are **not** cosmic-ray-like: FWHM
>= 2.4 px with normal sharpness (median 0.12, matching real sources). Something
PSF-shaped that appears in one exposure and not the other. The most likely
explanations are detector persistence (an afterimage of a bright source from a
preceding exposure, which is PSF-shaped by construction) or moving objects.
GOODS-S sits at high ecliptic latitude so the asteroid density is low, but not
zero, and this machinery is exactly what would find them.

This is a small, well-defined, checkable sample — the honest kind of loose end.
It is not a discovery, and it should not be described as one until each object
has been checked against the preceding exposure in the visit sequence.

---

## Part 4 — Immediate next steps

1. **Download the deep mosaics**, not single exposures. `_i2d` products at the
   observation level (`jw02736-o001_t001_nircam_clear-f444w_i2d.fits`) combine
   all dithers and reject cosmic rays for free. This one change removes the
   dominant systematic and gains ~8× depth.
2. **Rerun `build_universe_table.py`** with the corrected selection, then
   `audit_candidates.py`. On the GOODS-S obs026 anchor you should for the first
   time get candidates with both F090W and F200W measured. Expect very few, and
   treat that as the pipeline working correctly.
3. **Run `multi_epoch.py --pairs-only`** after any new download to see what
   repeat coverage you have bought before committing to an analysis.
4. **Add injection-recovery completeness** before making any claim that involves
   a number of objects. Without it you have detections; with it you have a rate.

### Caveat on verification

`footprints.py` is unit-tested and was validated against real flight WCS for all
26 exposures. `multi_epoch.py` and the `build_universe_table.py` changes are
syntax-checked and logically verified against those same real footprints, but
have **not** been executed end-to-end — this container has no `data/` directory,
and the FITS archive is gitignored. Run both on a machine with the archive
before trusting their output.
