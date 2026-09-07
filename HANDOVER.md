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

Recommendation #1 from Part 3 has been carried out. Nine exposures were pulled
from MAST and every same-filter pair that shares sky was compared. Results in
`research_output/ARTIFACT_CHARACTERIZATION.md` and
`research_output/visuals/artifact_diagnostics.png`.

```bash
python discovery/artifact_characterization.py --auto
```

### Headline

**About 15% of all 5-sigma detections in a single Stage-2b exposure are not real
sources**, at 31-38 per square arcminute per exposure.

Seven exposure pairs, spanning time baselines from 0.31 to 9.55 hours:

| | value |
| --- | ---: |
| pairs compared | 7 (F277W, F356W) |
| single-epoch fraction, per pair | **14.2% - 15.4%** (mean 14.8%) |
| artifact density | 30.6 - 37.6 per arcmin² per exposure |
| consolidated unique detections | 5113 |
| consensus artifacts | **718 (14.0%)** |
| detections with >1 independent comparison | 3847 |
| mixed verdicts | 47 (0.9%) |

Each detection is compared against every other overlapping exposure and the
verdicts are consolidated: present in even one comparison means real, because a
detector event cannot reappear at the same sky position in an independent
exposure. Only 0.9% of detections give mixed verdicts.

### Why the measurement is trustworthy

Four checks, all of which had to pass and did:

1. **Cross-epoch photometry is sound.** Persistent sources have a flux ratio
   between epochs of 0.99 +/- 0.08. Centred on unity, so the single-epoch
   population is a genuine absence rather than a measurement failure. This is
   the check the original pipeline never had.
2. **The rate is independent of baseline.** 14.2-15.4% across pairs separated
   by 19 minutes and by 9.5 hours alike. A per-exposure stochastic process
   behaves exactly this way; anything astrophysical would not.
3. **The process is symmetric.** Searching each exposure in turn gives the same
   fraction whichever is searched. A depth or calibration difference between
   epochs would show up as an asymmetry. It does not.
4. **The rate is physically plausible.** ~34 per arcmin² per exposure is ~0.17
   events per second per long-wave detector. With NGROUPS=5, up-the-ramp jump
   detection removes the great majority of incident cosmic rays, so a surviving
   rate around 1% of the incident flux is the right order of magnitude.

### Morphology: the artifacts are separable

| median | real | artifact |
| --- | ---: | ---: |
| FWHM (px) | 3.05 | **1.32** |
| peak / total flux | 0.087 | **0.376** |

The artifact population sits **below the PSF width** (NIRCam long-wave PSF FWHM
is ~1.5 px at 0.063"/px) and is four times more concentrated. That is the
cosmic-ray signature: charge deposited in a few pixels with no optical
convolution.

### The number that matters for this repo

An artifact appears in exactly one exposure, so it is absent from every other
band **by construction** and passes any dropout cut with full efficiency. A
dropout search does not suppress artifacts, it enriches them.

Against a genuine z > 10 surface density of order 0.03 per arcmin², the measured
artifact density implies roughly **1000-1250 artifacts per real high-redshift
source** in a single-exposure dropout search. That is the quantitative answer to
why the shipped catalog had 1732 candidates. Even with the cross-filter pairing
bug fixed, a single-exposure search of this kind is contaminated by three orders
of magnitude.

### A flaw found in this method, and fixed

For an extended source the 6-10 px background annulus sits on the source itself
and over-subtracts it to nothing, faking an absence. Every apparent single-epoch
source is now re-measured with a 15-25 px annulus before the classification is
allowed to stand. That recheck moves only **3.5%** of single-epoch sources
overall (1.0% of the compact population), so the headline is unaffected — but it
recovered 30% of the extended tail, which was entirely spurious.

### The loose end, resolved

The 20 non-cosmic-ray-like single-epoch sources were followed up individually.
They split three ways, and none of them is a discovery.

**6 of 20 were a flaw in my own method.** Re-measuring them in the comparison
epoch with a 15-25 px background annulus instead of 6-10 px flips them to
detected. These are extended galaxies whose background annulus sat on the galaxy
itself, over-subtracting the flux to nothing. The same recheck across the whole
sample moves only **3.5%** of single-epoch sources (1.0% of the compact
cosmic-ray-like population), so the 15% headline is unaffected — but the
extended tail was contaminated at 30% and had to be cleaned.

**The remaining 14 are detector events.** Visual inspection of 90x90 px stamps in
both epochs: two sit inside the diffraction/ring halo of a very bright star,
which moves with the pointing and so does not repeat; one is a perfectly round
bright compact source (ellipticity 0.02) with the classic snowball signature;
the rest are small irregular charge clusters or deblending differences beside
bright neighbours.

**The one real candidate was a streak, and it failed the decisive test.**
Source idx0 is a 19.6 px linear trail, ellipticity 0.88 — one of only three
elongated single-epoch events in 95. Its perpendicular width is **PSF-like, not
track-like**: FWHM 3.58 px, against 3.42 px for real point sources in the same
exposure and 1.82 px for the unbiased single-epoch population. Its trail length
over the 944.8 s exposure implies ~4.7 arcsec/hour. A SkyBoT cone search returned
no known solar-system object closer than 639 arcsec.

That all pointed at a moving object, so it was tested properly. The two sibling
dithers of the same visit — 19 and 38 minutes earlier, same detector, same
filter — were downloaded. **A moving object at 4.7 arcsec/hour must appear in
all three, displaced by ~24 and ~47 px. It appears in exactly one.** Nothing is
present at the expected offsets. It is a single-integration detector event: a
long, shallow-angle cosmic-ray track.

Two things are worth keeping from that exercise. The perpendicular-width test
was suggestive and wrong on its own; only the three-exposure sequence settled
it. And the sibling dithers were always in the archive — the pipeline collapsed
each filter to one "best" file and never looked at them.

---

## Part 6 — The solution: a classifier that needs no repeat coverage

Repeat-exposure vetting is the gold standard and it is unavailable exactly where
it matters: no F444W repeat pair, no SMACS repeat coverage at all. So the
labelled truth set was used to fit a rejector that works on a **single image**.

```bash
python discovery/artifact_classifier.py --train
```

Logistic regression on four interpretable features — FWHM normalized by the
filter's diffraction-limited PSF width, peak-to-total flux, log segment area,
and ellipticity. Fitted by Newton-Raphson in numpy; coefficients in
`research_output/artifact_classifier.json`.

| metric | value |
| --- | ---: |
| training rows | 5113 consolidated detections (718 artifact, 4395 real) |
| distinct sky objects | 1901 |
| cross-validated ROC AUC | **0.981** |
| purity @ threshold 0.5 | 0.930 |
| completeness @ threshold 0.5 | 0.815 |
| real sources lost | 44 of 4395 (**1.0%**) |

Three validation choices matter here. Training uses the **consolidated
per-detection rows**, never the raw per-pair comparisons, or one source would
appear many times. Cross-validation is **grouped by sky position**, so every
detection of one object lands in the same fold. And the model is tested on a
**held-out visit** (ROC AUC 0.973 and 0.985), which is harder than a random
split because detector state, background and pointing all change between visits.

**Cross-filter transfer**: fit on F277W alone and score F356W, and vice versa —
ROC AUC 0.981 and 0.980, no measurable loss. Normalizing FWHM by lambda/D is
what makes that work.

### Injection-recovery: the classifier fails the test that matters

Cross-filter transfer and a held-out visit do not establish that the cut
preserves the science sample, so it was tested directly. Synthetic sources
spanning brightness, size and surface brightness were injected into real
exposures — including F444W — and put through the complete detection,
morphology and classification chain.

```bash
python discovery/injection_recovery.py --auto --batches 8 --per-batch 200
```

4799 injected sources across three filters. The result is unambiguous:

| | F277W | F356W | **F444W** |
| --- | ---: | ---: | ---: |
| injected | 1600 | 1599 | 1600 |
| detected | 1069 (67%) | 1028 (64%) | 851 (53%) |
| false rejection, all detected | 13.5% | 0.1% | **28.8%** |
| false rejection, **unresolved** (r_e = 0) | 33.7% | 0.0% | **77.2%** |
| false rejection, **faint + unresolved** (S/N <= 8) | 80.0% | 0.0% | **88.9%** |
| false rejection, near a bright neighbour | 10.6% | 0.6% | 37.4% |

**On F444W — the band this pipeline actually selects candidates in — the
classifier throws away 77% of unresolved sources and 89% of faint unresolved
sources.** Those are real, injected, known-truth galaxies.

F356W looks clean only because it is effectively in-sample: six of the seven
training pairs are F356W. That contrast is itself the lesson — the apparently
lossless cross-filter transfer (ROC AUC 0.980) was measured on the filter the
model had already seen most of.

### Why it fails

The truth set contains almost no real **point** sources. GOODS-S is a deep
extragalactic field, so nearly every real source in it is a resolved galaxy —
median FWHM 3.05 px against 1.32 px for artifacts. The model had no reason to
learn "cosmic ray" when "compact" separated the classes just as well, so it
learned the shortcut. A genuine unresolved galaxy has FWHM at the PSF width,
which is exactly where the artifacts live.

Normalizing FWHM by lambda/D did not rescue this. It makes the feature
comparable across wavelength, but it cannot invent a training example of a real
point source that was never there.

### Verdict

**The classifier must not be applied to a high-redshift search.** It would
delete the majority of the target population while reporting a ROC AUC of 0.981.
The code and the model stay in the repository as a documented negative result,
because the failure is more instructive than the model would have been: a
headline discrimination metric certified a cut that destroys the science sample,
and only injection-recovery exposed it.

It remains defensible for one narrow use — rejecting compact artifacts from a
sample of **resolved** sources, where the false-rejection rate is 0.4-1.0%.
That is not the high-redshift use case.

To fix it properly, the training set needs real point sources: inject synthetic
PSF sources into the repeat-exposure pairs, label them real by construction, and
refit so the model must separate cosmic rays from point sources rather than
compact from extended. That is the obvious next experiment and it has not been
done.

### What this does not change

The 15% artifact rate stands — it comes from repeat-exposure vetting, not from
the classifier. So does the conclusion that a single-exposure dropout search
carries ~1000-1250 artifacts per genuine high-redshift source. The classifier
was the proposed mitigation, and it does not work for that purpose. Deep mosaics
with cross-dither rejection are not merely preferable; on this evidence they are
the only route.

## Part 7 — The ramp test: better motivated, still not safe

Since any shape-based discriminator inherits the "compact = artifact" shortcut,
the natural fix is a statistic that never sees the shape. JWST reads each
exposure non-destructively, so the accumulation history is recorded: an optical
source gains charge steadily across every group, a cosmic ray deposits it
between two reads and stops.

```bash
python discovery/ramp_diagnostics.py --exposure <dir>/<root>_ --sweep
```

The statistic is the fraction of a pixel's total signal arriving in its largest
single group-to-group increment — near `1/(n_groups-1)` = 0.25 for steady
accumulation, approaching 1 for an instantaneous deposition. Scored against the
repeat-exposure consensus labels by cross-matching through the cal frame's
TAN-SIP WCS.

### It separates

| | value |
| --- | ---: |
| labelled sources with usable unsaturated ramps | 349 (316 real, 33 artifact) |
| median statistic, real sources | **0.281** (linear expectation 0.25) |
| median statistic, artifacts | **0.694** |
| ROC AUC against repeat-exposure truth | **0.893** |

Real sources land almost exactly on the linear prediction. That is a clean
physical result and it confirms the streak independently: its pixels put ~100%
of their signal into a single increment.

### It still fails the test that matters

| population | false rejection of real sources |
| --- | ---: |
| PSF-scale (FWHM 2 - 3.5 px) | **45.0%** |
| extended (FWHM >= 3.5 px) | 11.6% |

Compact real sources are still rejected about four times as often as extended
ones — by a statistic that never sees their shape.

The mechanism is **detector non-linearity**. Raw `_uncal` ramps are not
linearity-corrected, and a pixel's response flattens well before hard
saturation, which makes the first increment the largest and mimics a jump.
Compact sources concentrate their flux into fewer pixels, reach higher DN, and
are hit hardest. The diagnosis is visible directly: among real sources, false
rejection rises from 12% to 58% to 100% across increasing ramp amplitude.

Tightening the DN ceiling confirms it and partly fixes it:

| DN ceiling | ROC AUC | false rej. compact | false rej. extended |
| ---: | ---: | ---: | ---: |
| 50000 | 0.867 | 54.0% | 14.9% |
| 30000 | 0.863 | 54.0% | 14.5% |
| 22000 | 0.865 | 53.1% | 13.2% |
| 18000 | 0.893 | 46.3% | 11.6% |
| 16000 | 0.933 | 33.3% | 10.3% |

Discrimination improves and the compact false-rejection rate roughly halves, so
non-linearity is a real part of the problem. It does not go away: compact
sources are still rejected ~3x more often at every ceiling.

### Verdict

**The ramp statistic is better motivated than morphology but is not yet a safe
cut either.** Used as implemented it would still preferentially delete compact
sources — the same failure, reached by a different route.

What it needs is not a different statistic but proper calibration: the
pipeline's non-linearity correction applied before the increments are measured,
and a per-pixel noise model (`VAR_RNOISE` and `VAR_POISSON` are already in the
cal file) so the quantity becomes a significance rather than a raw fraction.
With five groups the statistic is coarse; deeper readout patterns would sharpen
it considerably.

The general lesson is the one injection-recovery taught: **a discriminator that
separates the classes is not the same as a cut that preserves the science
sample**, and only a test with injected ground truth distinguishes them. Both
candidate cuts in this repository passed the first bar and failed the second.

### What still stands

Neither failure touches the measurements. The 15% artifact rate, the 31-38 per
arcmin² per exposure density, and the ~1000-1250 artifacts per genuine
high-redshift source all come from repeat-exposure vetting, which uses no
classifier at all. What has failed is every attempt to *mitigate* that rate
without repeat coverage. On this evidence deep mosaics with cross-dither
rejection are not the preferable route; they are the only one.

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
