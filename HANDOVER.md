# Handover: multi-epoch capability, and what this pipeline can actually discover

Current verified results and corrections are in [docs/TAKEOVER_STATUS.md](docs/TAKEOVER_STATUS.md).
The historical measurements below retain their original scope and reduction version.
In particular, older statements about absent F444W repeat coverage or unavailable
SMACS repeats are superseded by the current status and continuation reports.
The latest native atomic inference uses the separately versioned N IV doublet;
older coadd/single-line results remain historical conditional alternatives.

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
- `modules_are_disjoint(a, b)` — legacy-named module-name warning only. It must
  not veto a pair; different visits can place opposite modules on the same sky.

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
- The baseline informs interpretation but does not establish identity. A
  single-epoch detection over hours can be a detector event, moving source or
  astrophysical variability; depth and background differences also matter.

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
detector actually covers. For a nominal 129″ square long-wave field, 23% is
about **3827 arcsec² (1.06 arcmin²)**, not 30 arcsec². The usable common-band
area must still be measured from the joint WCS/validity masks.

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
   The currently registered SMACS data cannot supply this repeat-imaging test.
3. **The 9.5-hour baseline can help investigate artifacts.** It does not rule
   out rapid astrophysical variability or moving sources. Time dilation makes
   the rest-frame interval shorter at high redshift; identity still requires
   independent detector diagnostics, coverage/depth checks and follow-up.

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

The current data and analysis do not establish new physics. Better calibration,
controls and additional data can improve what is testable; novelty cannot be
assigned a zero probability from field popularity alone.

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
and NIRSpec follow-up. A single-exposure search needs independent validation before any novelty
claim; known discoveries are useful blinded recovery controls.

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
is sharp and reproducible: an LLM-driven pipeline produced 1732 candidates, none with both required
blue/mid bands covered, and its scoring layer could reward absent blue
measurements. Missing evidence does not identify all objects as artifacts. That is a
concrete, quantified result about where automated science fails, and it is more
interesting than another dropout catalog would have been. Its novelty must be checked against existing automated-science methods.

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
verdicts are consolidated: present in at least one comparison is an operational
persistence label, not proof of astrophysical identity. Detector-fixed patterns
or common processing artifacts can repeat. Only 0.9% give mixed verdicts.

### Why the measurement is trustworthy

Four checks, all of which had to pass and did:

1. **Cross-epoch photometry is sound.** Persistent sources have a flux ratio
   between epochs of 0.99 +/- 0.08. Centred on unity, so the single-epoch
   population is a genuine absence rather than a measurement failure. This is
   the check the original pipeline never had.
2. **The rate is independent of baseline.** 14.2-15.4% across pairs separated
   by 19 minutes and by 9.5 hours alike. This is consistent with a
   per-exposure stochastic process, but not a proof excluding astrophysics.
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

A residual in the red detection image can be absent in other bands and imitate
a dropout. It still must pass covered blue upper limits, angular-aperture and
quality checks; missing blue coverage is not a non-detection.

Against a genuine z > 10 surface density of order 0.03 per arcmin², the measured
artifact density implies roughly **1000-1250 artifacts per real high-redshift
source** in a single-exposure dropout search. This order-of-magnitude comparison is not a calibrated contamination estimate
for the shipped catalog; rates, depths and selection functions differ. Even with the cross-filter pairing
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
was the proposed mitigation, and it does not work for that purpose. Deep mosaics with cross-dither rejection are a strong practical route;
properly validated individual-exposure/ramp analyses remain possible.

## Part 7 — The ramp test, and Part 8 — the fixes applied

### The ramp statistic

Since any shape-based discriminator inherits the "compact = artifact" shortcut,
the natural alternative is one that never sees the shape. JWST reads each
exposure non-destructively, so accumulation history is recorded: an optical
source gains charge steadily, a cosmic ray deposits it between two reads.

```bash
python discovery/ramp_diagnostics.py --exposure <dir>/<root>_ --statistic jump_evidence
```

Real sources land at 0.281 against a linear-accumulation expectation of 0.25;
artifacts at 0.694. It also settles the streak independently, and corrects an
earlier error of mine: in the **detector frame** the track is 0.50 px wide, far
*below* the PSF. My i2d measurement of 3.58 px, which I had said matched real
point sources and pointed at a moving object, was drizzle broadening.

But the first version over-rejected compact real sources 4x, so three fixes
were applied.

---

## Part 8 — The three fixes

### Fix 1 — real detector calibration (`tools/jwst/ramp_calibration.py`)

The CRDS reference files the exposure header names were downloaded and applied
directly, without needing the `jwst` package: superbias, the per-pixel linearity
polynomial, per-pixel saturation limits, read noise and gain. Per-pixel
saturation limits keep **99.5%** of pixels usable where the earlier global
18000 DN ceiling kept a small fraction.

### Fix 2 — a noise-normalized, null-calibrated statistic

The raw increment fraction grows with brightness, so it inherited a compactness
bias through surface brightness. It was replaced by a chi-squared comparison of
a linear ramp against linear-plus-one-jump, weighted by the per-pixel read-noise
and Poisson budget. On synthetic ramps that statistic is brightness-independent
by construction (1.29 sigma faint, 1.34 sigma bright, 43.9 sigma for a jump).

Two things were then learned by measurement rather than assumption:

- **A model-error floor does not help.** Adding a signal-proportional variance
  term was expected to stop bright sources over-flagging. Swept from 0 to 10%,
  it only lowered discrimination. The residual bias is statistical, not
  systematic, so the floor is set to zero and the finding kept reproducible.
- **The bias reverses once noise is handled.** The significance statistic
  over-rejects *faint* sources instead, because searching four jump positions on
  a five-point ramp buys apparent significance by chance. That look-elsewhere
  effect scales with noise, and since faint sources here are mostly compact, it
  reappears as a compactness bias.

So the statistic is now calibrated against its own null by parametric bootstrap
(`jump_pvalue`): take each pixel's fitted linear ramp, add noise from its own
variance, and measure how often the statistic exceeds the observed value.

| statistic | ROC AUC | false rej. compact | false rej. extended | ratio |
| --- | ---: | ---: | ---: | ---: |
| raw increment fraction | 0.873 | 50.0% | 14.5% | 3.5x |
| noise-normalized significance | 0.896 | 40.4% | 8.6% | 4.7x |
| **null-calibrated evidence** | 0.791 | 59.6% | 39.3% | **1.5x** |

Compared at matched 70% artifact completeness.

**The calibration works and the result is negative.** It cuts the compactness
bias from 4.7x to 1.5x — and most of the apparent discriminating power goes with
it. That is the finding: the uncalibrated statistic's performance was
substantially *made of* the bias. With five groups there is not much honest
information left once the look-elsewhere effect is paid for. Deeper readout
patterns would change this; NGROUPS=5 will not.

### Fix 3 — retrain the classifier with injected point sources

This one worked. The diagnosis was that the truth set contains almost no real
point sources, so `discovery/injection_recovery.py --harvest-training` injects
PSF and near-PSF sources into the exposures, labels them real by construction,
and adds 1320 such rows to the fit.

| | before | after |
| --- | ---: | ---: |
| training rows | 5113 | 6433 (1320 injected) |
| cross-validated ROC AUC | 0.981 | 0.971 |
| held-out visit AUC | 0.973 / 0.985 | 0.979 / 0.965 |
| **F444W false rejection, all** | **28.8%** | **1.4%** |
| **F444W false rejection, unresolved** | **77.2%** | **5.0%** |
| **F444W false rejection, faint + unresolved** | **88.9%** | **0.0%** |
| F277W false rejection, faint + unresolved | 80.0% | 0.0% |
| near a bright neighbour (F444W) | 37.4% | 1.2% |
| artifact completeness @0.5 | 0.815 | 0.688 |
| residual contamination | 3.1% (4.7x) | 5.2% (2.9x) |

The classifier no longer destroys the science sample. It pays for that by
catching fewer artifacts — 69% instead of 82% — which is the correct direction
for the trade and was the whole point.

**Caveat, stated plainly: this validation is partly circular.** The training
rows and the test injections come from the same generator, so "0% rejection of
injected point sources" partly reflects that the model was shown that
population. The evidence that is *not* circular: held-out-visit AUC stays at
0.965-0.979; near-bright-neighbour placements were never in the training
harvest yet drop from 37.4% to 1.2%; and r_e = 3.0 px sources were not trained
on either. Breaking the circularity properly needs real point sources — a
stellar field, or an independently generated PSF model.

---

## Where this leaves the three cuts

| approach | preserves science sample? | usable? |
| --- | --- | --- |
| morphology classifier, original | no (89% of faint unresolved deleted) | no |
| ramp statistic, uncalibrated | no (4.7x compactness bias) | no |
| ramp statistic, null-calibrated | mostly (1.5x) | too weak (AUC 0.791) |
| **morphology classifier, retrained** | **yes (0-5%)** | **yes, at 2.9x mitigation** |

The measurements are untouched throughout: the 15% artifact rate, the 31-38 per
arcmin² per exposure density, and the ~1000-1250 artifacts per genuine
high-redshift source all come from repeat-exposure vetting and use no classifier
at all. With the retrained cut applied that last number falls to roughly 360 per
genuine source — better, and still hopeless for a single-exposure dropout
search. Deep mosaics with cross-dither rejection remain the preferred recovery benchmark.

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


## Measurement-integrity correction (2026-10-09)

`discovery/audit_candidates.py` now distinguishes absent evidence (`untestable`)
from valid measurements failing the configured selection (`falsified`). The old
1732 records are all untestable; they are not all independently identified
artifacts. Calibration comes from image-specific physical fields, not nominal
detector scales. Surviving requires matched angular apertures, valid positive
errors, covered bands, a red detection and a sufficiently deep blue upper limit.
The science-report terminology and pipeline call sites are being updated in this
integration round; historical JSON reports remain provenance records until rerun.

The repeat-based 15% single-epoch-only fraction and other historical numbers
above were not reproduced in this correction (the FITS archive is absent). They
are operational measurements from the earlier run, not universal contamination
rates. Spectroscopy, independent detector diagnostics and selection-function
calibration are required for stronger astrophysical claims. Null-calibrated ramps
and classifier injections have different targets and denominator populations;
AUC or conditional rejection rates alone do not establish end-to-end recovery.
