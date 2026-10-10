# Source-count identifiability and missing selection denominators

10 October 2026. This follow-up starts from live remote master
`139c4c21160208cebdb7db9a92c50b8744bd3149`, including the merged selection pilot.
Design commit `4f1f4c5` froze an 8-MiB metadata/source ceiling, 120-second
computation limit, no full-image acquisitions and at most four existing-site
reruns **only if physical count conversion/transport could be recovered**.

The result is an explicit information limit, rather than another assumed-gain
grid. **Exported SCI/WHT and aggregate exposure metadata cannot uniquely
recover native source-count covariance.** Relevant products are publicly
accessible follow-up reduction work; their absence from the current bounded
export is not an unavailable author input or an inaccessible archive.

## Actual acquired products and provenance

This round selected **1,544,079 new bytes**: 1,528,430 bytes of center exposure/association metadata, public
Grizli 1.12.10 release/tag/source metadata and DJA documentation, plus
11,553 bytes of bounded public VAR-path response bodies and a separately
accounted 4,096-byte repeat transfer to preserve the exact original compressed
FITS prefix for independent decoding. Individual URLs, hashes and sizes are pinned in
`data_sources/selection_count_audit/manifest.json`; files remain outside git.
The 9,221,810-byte full Grizli source archive exceeded this round's ceiling and
was avoided by acquiring the required source files directly at release-tag
commit `3c5b6beb620607993ddf9c300652980c59ed2fa1`. Downloaded code was parsed as
data, never imported or executed.

All three actual cutouts match their pilot byte/hash pins and have only SCI
and WHT planes. Their logged Grizli version is 1.12.10 and weighting is
`jwst_var`. Inspection of the matching public release establishes that the
combining weight uses local read-noise variance plus a median Poisson term,
while full input ERR variance is propagated separately. Scalar `WHTnnnnn`
header entries are exposure medians. They are not local input coefficient
maps or an independent exposure-time image. A release-version string does not
certify the exact production commit or absence of custom changes.

Crucially, released `visit_processor.cutout_mosaic` writes combining `outwht`
to `_wht.fits` and separately propagated full ERR `outvar` to `_var.fits`.
The released tile assembler rebuilds the unique contributor union but copies
other header cards from the last loaded tile. This offers a concrete mechanism
for nonmatching contributor/median counts and uncertified EXPTIME: neither
scalar median indices nor remaining last-tile summaries form a global local
contribution table. It does not certify the exact production thumb handler.
**WHTTYPE=`jwst_var` cannot establish that the inspected WHT is full ERR variance.**
The artifact reports `100/WHT` as publisher inverse-weight quantities, not as
measured full-ERR diagonal variance.

| Band | Header FLT contributors | Scalar median-weight headers | Matching center-query contributor rows | Center geometric exposure sum | Mosaic header EXPTIME |
|---|---:|---:|---:|---:|---:|
| F090W | 208 | 47 | 32 | 41,400.998 s | 56,861.948 s |
| F200W | 262 | 72 | 43 | 45,888.965 s | 68,049.659 s |
| F444W | 106 | 62 | 48 | 49,893.783 s | 63,733.479 s |

The center query contains 854 rows across all filters. The table intersects
requested filter and exact named contributor identities; it does not count
all current exposures as inputs to the pinned cutout. The query is a current
geometric database snapshot near one coordinate, not an unchanged historical
release or per-pixel valid exposure map. DQ, gain, ramp weighting, exact
footprint/distortion, local masks and combining coefficients remain absent.
The disagreement is sufficient to reject using the mosaic header EXPTIME as
a certified local photon exposure. The sums are provenance diagnostics, not
replacement effective gains.

The [DJA API description](https://dawn-cph.github.io/dja/general/api_summary/)
provides exposure footprints and SCI cutouts with optional inverse-variance
WHT. The exported products inspected here contain no native gain, time,
VAR_POISSON, VAR_RNOISE, context or per-input weight arrays. The
[JWST gain reference documentation](https://jwst.readthedocs.io/en/latest/jwst/references_general/gain_reffile.html)
defines pixel-level DN-to-electron calibration. Public access to such reference
files does not supply the per-input maps/transforms absent from a coadded
SCI/WHT export.

## Bounded public variance search

The documented association table supplies actual public SCI URLs. Replacing
`_sci.fits.gz` with the released pipeline's `_var.fits.gz` pattern for one
normal-imaging F444W association gave **HTTP 200** on HEAD, length
**43,219,789 bytes**. A 4,096-byte Range request returned HTTP 206 and a valid
compressed FITS header, dimensions 3976 by 4032. This establishes public VAR
accessibility; the full product exceeded this round's 8-MiB ceiling and was
not downloaded. Its current single-association operator is not the pinned
historical multi-association cutout operator.

The uncompressed sibling returned 403. Two guessed undocumented tiny-cutout
flags, `output=fits_var` and `output=fits_variance`, returned PNG rather than
VAR. These bounded path tests do not establish general absence of a public
variance cutout route. Probe statuses, headers, prefix hashes, dimensions and
byte accounting are versioned in `selection_variance_public_probes.json`.
The exact original 4,096-byte compressed prefix is retained outside git and
pinned in the source manifest; bounded Range restoration checks its hash and
ETag. `selection_var_prefix_retention.json` accounts the repeat transfer
separately. Independent zero-body HEAD already confirmed access and file size.
Even when a matched full VAR plane is acquired, it describes the existing
scene diagonal. Under independent nonnegative component assumptions its
pixel source component is between zero and VAR; it does not identify a new
source's photon increment, input count conversions or off-diagonal transport.
No actual VAR pixel values were acquired here, so this audit supplies no
numerical empirical VAR-based source bound.

## Constructive ambiguity and supported bounds

For independent input source photon counts N_i with expected value F c_i,
where c_i is the positive effective electrons/nJy conversion, a normalized
calibrated scalar coadd has

\[
\hat F=\sum_i a_iN_i/c_i,\qquad
\mathrm{Var}_{\rm source}(\hat F)=F\sum_i a_i^2/c_i.
\]

Consider F=20 nJy and c=(1,4). The native background variance is
nonnegative but is not separately supplied by the export. Both local
weight hypotheses below produce the same expected source flux and **full-ERR
variance 14 nJy²**, hence inverse-variance WHT 1/14. They have the same named
contributors and aggregate count conversion/time. Altering local pixels
does not recover them from a global median-weight header. Native background
variances of 10/0.68 each in the first case, and 1/0.68 each in the second,
give the two propagated background terms below.

| Normalized local coefficients | Expected flux | Background component | Source component | Full ERR variance |
|---|---:|---:|---:|---:|
| (0.2, 0.8) | 20 nJy | 10 nJy² | 4 nJy² | 14 nJy² |
| (0.8, 0.2) | 20 nJy | 1 nJy² | 13 nJy² | 14 nJy² |

This is a mathematical identifiability counterexample for calibrated linear
coaddition, **not** a proposed alternative DJA reduction. It shows why an
exported full variance and a summed time cannot recover the separate source-noise
response even when the individual count conversions are given for the example.
An additional 20-nJy source has added variance 4 versus 13 nJy² under the
same two operators; existing-scene ERR does not resolve this difference.
The exact pipeline's native ramp statistics and overlap operators require
additional inputs, rather than a universal Poisson term attached to output
pixels.

If positive c_i are known and a_i ≥0 sum to one, Cauchy–Schwarz and convexity
provide attainable scalar bounds:

\[
\frac{F}{\sum_i c_i}\leq\mathrm{Var}_{\rm source}(\hat F)
\leq\frac{F}{\min_i c_i}.
\]

The lower endpoint occurs at a_i proportional to c_i; the upper endpoint puts
all weight on an input with minimum c_i. These bounds apply to the stated
scalar coadd. **They are not bounds for a signed aperture/sky operator or
native-to-mosaic drizzle covariance.** A general measurement needs
Cov(y)=A diag(λ) Aᵀ, with calibration and native overlap/ramp response included
in A (or the appropriate native ramp-noise covariance).

Because the inspected export does not provide physical c_i or A, it gives no
finite numerical upper bound for the added source variance without additional
calibration assumptions. Nonnegativity is supported. This is an information
limit of this export, not a claim that the actual JWST detector has arbitrary
gain or unbounded physical noise. The earlier 1/10 electrons/nJy choices
remain assumptions, not empirically justified uncertainty endpoints.

## Representative classes and contamination denominators

The uniform pilot has 16 actual unmasked scene sites and 1,152 modeled source
insertions. It has **zero supplied independently verified labels** for actual
stars, faint galaxies, high-redshift objects or blends. This means their labels
are missing, not that those classes are absent from the field. Point/extended/
pair are prescribed spatial models; three color triples do not establish
astronomical class identity or include the breadth of real atmospheric,
dusty/nebular and galaxy SEDs.

There is one null centroid match and zero null joint red passes. Actual
astronomical contamination numerator and denominator are **undefined**, not
0/16 or 0/1,152. The zero blue/intermediate-model selection counts establish
conditional controls under the simulated colors. They do not constrain the
fraction of a real selected population that consists of stars, low-redshift
galaxies, blends or background structures. With exclusively unknown real
labels, a hypothetical contamination fraction remains unidentified over
[0,1]. No cosmological population likelihood follows from these counts.

Missing representative controls are independently labelled faint galaxies
across SED/morphology/redshift, empirically identified stars and broader
atmospheres, realistic labelled blends/backgrounds, visit/field-disjoint
holdouts, known coverage/depth/volume and population sampling weights. The
older 14 geometry controls were in candidate-centered footprints and do not
supply these denominators for this distinct uniform patch.

## Validation, stopping and next reduction

The audit executes in **under one second**. Six offline tests verify the exact
constructive witness, both attainable scalar bounds, independent input-photon
Monte Carlo moments, failure on invalid conversions/weights and the distinction
between aggregate and effective photon exposure, plus the 4,096-byte read
ceiling even when a server ignores Range. Together with the existing
selection tests, **14 tests pass**; focused lint passes. Independent review
checks the actual source/input pins, header/contributor counts and an alternate
variance witness before publication.

No physical count transport was identified, so no site rerun or enlarged
assumed-gain grid was executed. The calibrated rerun condition is not silently
replaced by a toy source model.

The next accessible work is a bounded **native imaging reduction**: recover
RATE/CAL pixel regions and their Poisson/ramp variance, gain/calibration and DQ
maps; retain actual contributor identity and exact WCS/registration; reconstruct
local weights and kernel/pixfrac overlap coefficients. A local exposure map or
context map helps coverage bookkeeping but cannot by itself recover squared
coefficients or photon-sharing covariance. Then forward-inject photons and
verify interval coverage on fixed scenes before expanding the pilot or obtaining
new representative class labels.

```bash
python -m discovery.selection_count_audit acquire --input "$COUNT_AUDIT"
# Optional live bounded public path reprobe; statuses may change.
python -m discovery.selection_count_audit probe --input "$COUNT_AUDIT" \
  --output /tmp/selection_variance_public_probes.json
python -m discovery.selection_count_audit audit --input "$COUNT_AUDIT" \
  --image-input "$SELECTION" --output /tmp/selection_count_audit.json
python -m pytest -q tests/test_selection_count_audit.py tests/test_selection_pilot.py
```

The compact artifact records actual input/source hashes, all contributor names,
exported planes, geometric query diagnostics, class-denominator deficiencies,
conditional bounds and the explicit stopping decision. It preserves the prior
pilot, its source-count assumptions and its existing scientific contracts.
