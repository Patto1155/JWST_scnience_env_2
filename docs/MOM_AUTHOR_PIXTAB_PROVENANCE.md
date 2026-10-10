# Public MoM pixel table recovered and independently replayed

10 October 2026. Starting revision `379ff35786aff31535335bbe7d1de114f91dd3c4`.
This resolves the earlier **public PIXTAB/extraction-settings acquisition
blocker**. It does not supply a source-specific empirical wavelength/LSF
calibration, an original RATE reduction, or the publication's full likelihood.

## Question, budget and stopping rule

Can the public release provide the source pixel table, contributor identities,
optimized profile and exact extraction weights needed to explain its coadd?
The alternatives were a recoverable public intermediate versus a genuine
external dependency. Expected gain was an auditable measurement operator and
direct evidence about reused background photons. Budget: 100 MiB newly selected
inputs; stop after one verified intermediate, pinned code and small metadata
queries, rather than expanding a calibration scenario grid.

The `.pixtab.fits` sibling is explicitly written separately by the pinned
`msaexp/slit_combine.py` implementation. It was absent from the `.spec.fits`
extensions, which does **not** imply that it was unavailable publicly.

## Verified inputs and settings

[Manifest and exact receipts](../data_sources/author_provenance/manifest.json)
pin the public 5,457,600-byte table, SHA256
`c3566b0173e9b1808b7fd856d98ca1be96ff2d6a0959132c1c7b9791d10e7420`.
It contains 56,734 rows and twelve columns: signed science, sky, total and
read-noise variances, wavelength, dispersion, slit-relative position, bar,
signed profile, pathloss, exposure index and duration. No raw detector x/y,
original excluded-pixel masks, negative-contributor masks or full covariance
are supplied.

The exact source snapshot `e2b237b` is 168,970 bytes, SHA256
`191bf8cda952bcdbfc72db18023cd3d3cb2ca3a2b65acaf13c0b5cf5ac6dfd9a`.
Its `pixel_table_to_1d`, `make_diff_image`, `get_flat_diff_arrays` and
`combine_grating_group` identify the public operator without installing or
executing the upstream software.

| Verified setting | Value |
|---|---|
| Public release version | `0.9.5.dev8+ge2b237b` |
| Weight | `ivm`: inverse `var_rnoise` |
| Profile center/sigma | 0.001 / 0.36213376323372604 |
| Extraction limits | slit-relative -3 through +3 pixels, inclusive |
| Pathloss | stored factor divided once; range 0.79501467–0.82854391 |
| Profile slice | 0 through 473 |
| Public reduction CRDS | `jwst_1298.pmap`, version 12.1.4 |
| Public calibration revision | `0.1.dev8704+g9b678d4` |

These profile parameters belong to the author's PRF implementation; the sigma
must not be equated with the independent reduction's Gaussian sigma. The
paper's stated msaexp v0.9.4 and this release's stored development version
remain distinct provenance facts. Current official CALs use calibration 2.0.1
and `jwst_1535.pmap`, so they are a separate reduction alternative.

Every table exposure index is matched to the ordered `SFILE000`–`SFILE008` and
SLITS filename, source ID/coordinates, planned source x position and 1750.667-s
duration. All nine contributor identities match the known observations.
The MSA spatial API returns estimated shutter placement; this repeats planned
metadata and is not an independent measurement of actual dispersion-direction
placement. The two nearby trace offsets are -21.1718 and +19.9738 pixels in
the public trace-overlap query; these metadata do not certify absence of all
contamination. The fresh extraction query matches the existing index exactly,
including the weak CAPERS entry; no new high-resolution UV spectrum was found
in this bounded release query.

## Independent extraction replay and dependence witness

An independent NumPy histogram implementation constructs wavelength bin edges
from the existing SPEC1D centers. With `w=1/var_rnoise`, `p=profile`, `l=pathloss`,
it computes each bin's signed flux as

\[
F=\frac{\sum sci\,w\,p/l}{\sum w\,p^2},\qquad
\sigma^2=\frac{\sum var_{total}\,w^2p^2/l^2}{(\sum wp^2)^2}.
\]

All 467 finite flux/error bins and all finite masks reproduce the public coadd.
Maximum absolute differences are 5.061e-11 microJy for flux and 9.869e-11
microJy for diagonal error. Pixel counts match exactly in all 473 bins;
profile/flux/variance sums also reproduce. This is actual public-intermediate
data replay, distinct from both compact-artifact replay and original RATE
recalibration. It checks the extraction implementation, not interval coverage.
36,520 stored profiles are negative; clipping them would change the operator.

The table directly demonstrates **shared sky across the three official RATE
groups**: index0/3 share 6,296 exact stored sky values, index0/6 share 6,293,
index1/4 share 6,299, and index2/5 share 6,301. These pairs have the same nod
position in different VISITGRPs. Every different-nod pair has zero common
values. The nine-by-nine matrix is saved in
[the numerical audit](../research_output/mom_author_provenance_v1.json).

The source's negative operator averages other nod positions within a SlitGroup;
the repeated arrays support pooling across the nine public inputs. The exact
pixel denominator additionally depends on unavailable `mask`/`bkg_mask` arrays.
The set intersections are dependence witnesses, **not covariance estimates**
or recovered pixel correspondences. Slicing this author table by official
VISITGRP does not create independently background-subtracted held-out data.
The separate current official CAL reduction still has its documented three
disjoint RATE groups; these are different operator contracts.

## Reproduce and validate

```bash
python -m data_pipeline.mom_author_provenance \
  --cache /tmp/mom-author-provenance --acquire \
  --output /tmp/mom-author-provenance-v1.json
python -m pytest tests/test_mom_author_provenance.py tests/test_mom_native_batch.py
```

Hash/size/schema/contributor/settings mismatches fail closed. The oracle tests
recover a known signed signal, independently propagate a linear operator's
variance, reject invalid pathloss/variance/wavelengths, preserve empty bins,
check the dependence witness and reject stale files. Independently validating
this result requires the raw public intermediate and an alternative summation
implementation; the author is not its sole scientific validator.

New unique selected payload: **5,637,897 bytes**, including 168,970 bytes of
upstream software source and 11,327 bytes of archive metadata. Repeated probes,
including a duplicate initial pixel-table GET, are separately bounded in the
manifest by a conservative total of 16,338,377 transfer bytes. The existing
688,320-byte spectrum is reused. Large raw table/source files remain external.

The next discriminating step is to carry the recovered signed operator into
source/sky controls with shared covariance, compare the public release against
current official CALs as separate likelihoods, and restore original RATE inputs
only when their information resolves a specified missing mask/calibration term.
No nitrogen abundance or independent line confirmation changes here.

Primary sources:

- [Public MoM PIXTAB](https://s3.amazonaws.com/msaexp-nirspec/extractions/mom-cos04-v4/mom-cos04-v4_prism-clear_5224_277193.pixtab.fits)
- [Pinned msaexp source](https://github.com/gbrammer/msaexp/blob/e2b237b/msaexp/slit_combine.py)
- [DJA API documentation](https://dawn-cph.github.io/dja/general/api_summary/)
- [MoM publication v2, reduction details](https://arxiv.org/html/2505.11263v2)
