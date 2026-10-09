# Original-image recovery and external astrometry, 9 October 2026

Seven **complete original, single-exposure MAST i2d products** were retrieved
and checksum-pinned. These are calibrated image arrays, not cutouts, headers,
modeled PSFs or synthetic data. The selected download is 838,696,320 bytes;
the complete historical archive remains unprovisioned. Exact URLs, byte sizes
and SHA256 values are in `data_sources/original_images.json`; actual HTTP
receipts are in `data_sources/receipts/original_round2/`.

The three-band selection uses the corrected GOODS-S observation 026 F444W
anchor, F090W NRCA1 and F200W NRCA1. Four additional products supply F277W and
F356W repeats from observations 025 and 026. Current archive products were
reprocessed with `CAL_VER=3.0.0`, with September 2026 `Last-Modified` headers.
All have actual two-dimensional SCI, ERR and WHT planes, a celestial WCS and
`BUNIT=MJy/sr`. Checks require positive finite ERR/WHT where scientific pixels
are admitted. Historical pixels and earlier classifier statistics are not
assumed numerically unchanged after archive reprocessing.

## External astrometry

The pinned JADES DR4 release supplies **independent released target coordinates**.
Only A/B GOODS-S observations are retained. Repeated positive NIRCam DR5 source
identities are grouped; unassigned identifiers use rounded sky coordinates.
This leaves 1,737 reference source identities. The images are segmented at a
fixed 5-sigma pixel threshold; matching uses the observed, intensity-weighted
centroids rather than forced peaks near the catalog coordinates. The maximum
angular match distance is 0.5 arcsec, with one-to-one matches. No translation
was fitted and then applied before evaluating the offsets.

F444W has 858 detected centroids, **23 matches among 43 covered reference
sources**, a median radial residual of **0.02155 arcsec** and a 90th percentile
of **0.10715 arcsec**. The median east/north offset is
**(-0.00905, -0.01503) arcsec**. Bootstrap 95% intervals for these two median
components are **[-0.01797, -0.00376]** and **[-0.02766, -0.01164] arcsec**.
Shifting the reference catalog by +/-10 arcsec in each coordinate gives only
1-2 matches per 34-54 covered references. This supports correspondence with
the released source frame beyond a self-WCS round trip or a chance catalog.

| Image | Covered external identities | Matches | Median radial residual (arcsec) |
| --- | ---: | ---: | ---: |
| F444W obs026 | 43 | 23 | 0.02155 |
| F090W obs026 | 2 | 1 | 0.44505 |
| F200W obs026 | 4 | 3 | 0.06018 |
| F277W obs025 | 15 | 11 | 0.03681 |
| F277W obs026 | 43 | 26 | 0.02933 |
| F356W obs025 | 12 | 5 | 0.04522 |
| F356W obs026 | 43 | 28 | 0.02692 |

The F090W/F200W external sample is too sparse to establish a frame offset.
Intervals are explicitly omitted for fewer than five matches. In particular,
the single 0.445 arcsec F090W match must not be fitted as a global translation.

An additional, **secondary** frame check compares independently detected
short-wave centroids with the F444W image centroids. F090W matches 137/213
covered F444W centroids and F200W matches 171/199. Their median radial
separations are 0.02779 and 0.01658 arcsec; median east/north offsets are
(-0.00340, -0.00513) and (-0.00135, -0.00352) arcsec. The complete matches,
shifted-catalog controls and finite-sample intervals are in
`research_output/original_image_astrometry.json`. This supports relative
cross-band registration. It is not a second external reference catalog.

Released NIRSpec target coordinates are not a Gaia absolute-frame certificate.
Galaxy structure, color gradients, blends and targeting choices contribute
to measured offsets. Bootstrap errors capture finite-source sampling and
exclude image-wide calibration systematics. These measurements do not measure
population completeness or establish any new galaxy.

## Repeat coverage and reconciled timing

The actual `python -m discovery.multi_epoch --pairs-only` execution finds:

| Filter | WCS grid overlap | EXPMID baseline |
| --- | ---: | ---: |
| F277W obs025 x obs026 | 0.522500 | 5.64853 hours |
| F356W obs025 x obs026 | 0.511875 | 9.54657 hours |

The older handover's early table gives F277W 9.54 hours. Actual FITS EXPMID
values, 59859.745519965276 and 59859.98087528935, give 5.64853 hours. The
historical `ARTIFACT_CHARACTERIZATION.md` already reports 5.65 hours for this
same pair, so this is a reconciliation of inconsistent earlier summaries,
not evidence that an observation time changed in reprocessing. Results are
in `research_output/original_repeat_pairs.json`.

No F444W repeat exists in this selected archive. These hour-scale comparisons
can test persistence subject to depth and detector diagnostics; they cannot
identify every nonpersistent source as an artifact. The historical 15% claim
was not rerun or promoted to an astrophysical contamination rate here.

## Reproduce

From the repository root with its dependencies installed:

```bash
DATABASE_URL=sqlite:///./data/original_round2/pairs.sqlite python -m data_pipeline.original_images data_sources/original_images.json --output-dir data/original_round2 --register
python -m discovery.external_astrometry --image-dir data/original_round2
DATABASE_URL=sqlite:///./data/original_round2/pairs.sqlite python -m discovery.multi_epoch --pairs-only --pairs-output research_output/original_repeat_pairs.json
python -m pytest tests/test_external_astrometry.py
```

Acquisition stops above 300 MiB per product or 1.5 GiB total. Existing inputs
are reused only after full checksum, size, identifier, array and WCS checks.
Current MAST may eventually change its reprocessed bytes; a checksum failure
requires a consciously versioned acquisition rather than silent substitution.
Tests use explicitly synthetic fixtures; the scientific report is computed
from verified original arrays and the independently released catalog.
