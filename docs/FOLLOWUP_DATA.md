# Bounded acquisition after real-source nonrecovery

The original images and frozen real-reference validation were exercised before
this follow-up. Three catalogue positions with covered F444W nonrecoveries were
selected for a targeted depth comparison: one A-grade redshift and two C-grade
redshifts. The C-grade cases are retained separately, not promoted to robust truth.

## Inputs actually acquired

The [follow-up manifest](../data_sources/followup/manifest.json) and individual
receipts pin seven public products. Actual acquisition totals **57,516,514 bytes**,
within the 100 MiB literature/data budget. Large original data remain outside git.

| Product | Actual use | Limitation |
|---|---|---|
| Three DAWN F444W science + inverse variance cutouts, 5.62 MB total | Follow covered nonrecoveries in deeper processed imaging | Mosaics include the original exposure; cutouts can share sky |
| UNITE author source at `156e29eb75f788f90041b5d2bbae27ae9dac78d8` and official prism grid | Parse the numeric point-source polynomial without executing code; generate checked-in FITS/CSV | Generic point-source resolving power, not MoM's shutter-specific LSF or exact paper runtime |
| Official `jw05224004001_03101_00002_nrs2_cal.fits`, 51,563,520 bytes | Identity-verified native target slit SCI/ERR/DQ/WAVELENGTH, variance and pathloss arrays | One 1,750.667 s exposure, not an independent nine-exposure reduction |
| Nandal et al. `2405.11235v1` HTML Table 2 | Numerical competing rotating-star mixed-ISM benchmarks | Not a raw stellar-yield grid or a MoM-specific fit |

The native slit identifies source **277193** at (150.0933255°, 2.2731627°),
slit 21, with **28 × 423** native pixels. SCI units are MJy/sr. Its official
calibration is 2.0.1 / `jwst_1535.pmap`, and the upstream source classification is
**EXTENDED**. This differs from the DAWN point-source correction; converting it
into a fresh spectrum requires an explicit calibration/extraction model.
Of 11,844 pixels, 4,179 carry DO_NOT_USE and 121 carry SATURATED; 7,565 retain
finite positive error/wavelength and neither bit. DQ nonzero also includes bits
that are not automatically fatal. These are whole-slit counts, not UV-line
quality statistics. The compact slit is reproducibly derived outside git.

## Reproduce

```bash
python -m data_pipeline.followup_data acquire --output /tmp/jwst-followup
python -m data_pipeline.followup_data derive-resolution \
  --input /tmp/jwst-followup --output /tmp/point-resolution
python -m data_pipeline.followup_data extract-native-slit \
  --input /tmp/jwst-followup/jw05224004001_03101_00002_nrs2_cal.fits \
  --output /tmp/mom-native-slit.fits
python -m discovery.deep_reference_comparison \
  --input /tmp/jwst-followup \
  --original /path/to/jw01180026001_09201_00003_nrcalong_i2d.fits \
  --output /tmp/deep-comparison.json
```

Existing input bytes must agree with receipts; a new download must agree with
manifest size/SHA256. Dynamic APIs can change: a mismatch requires a documented
new version rather than silently refreshing inputs. Every product has a streamed
byte ceiling, including a 60 MiB ceiling for the selected native exposure, and
the full acquisition enforces a 100 MiB aggregate ceiling. UNITE code is GPLv3+;
cite UNITE and de Graaff et al., DOI 10.1051/0004-6361/202347755. DAWN/MAST
redistribution terms were not explicitly verified here; preserve source and
observing-program acknowledgements. Full author code and HTML remain external.

The public DAWN bucket refused a bounded prefix listing (403). No public MoM
PIXTAB file was verified. The existing coadded spectrum omits PIXTAB and per-pixel
DQ. Its nine SLITS entries identify public original exposures, so original
calibrated/ramp reacquisition is a computational/data-volume dependency rather
than a claim that the observations are proprietary. This round acquired one.

## Depth comparison actually executed

All three positions fail the original 5-sigma, at-least-five-pixel detector. In
the deeper cutouts the robust A-grade reference and one C-grade reference match
within 0.022 arcsec. The other C-grade source remains undetected by segmentation.

| DR4 ID / quality | Single aperture diagonal SNR | Deep diagonal SNR | Deep blank-scatter SNR | Deep segmentation |
|---|---:|---:|---:|---|
| 20083087 / C | 4.71 | 16.07 | 14.11 | Matched |
| 20074794 / C | 2.44 | 13.38 | 12.36 | Not detected |
| 20189546 / A | 2.66 | 22.14 | 15.53 | Matched |

Matched 0.2 arcsec apertures use 0.4–0.6 arcsec background annuli. Formal errors
use the inverse variance weights and background-mean variance. Source-masked, disjoint blank apertures retain drizzle covariance/confusion; scatter is robust
MAD. There are 100, 83 and 85 accepted blank apertures respectively, with
scatter/formal-error ratios 1.144, 1.118 and 1.392. These are empirical nuisance
estimates with explicit source-mask and spatial-depth assumptions. They are not
Gaussian line significances or a full calibration uncertainty budget.

This rejects the interpretation that the robust reference's original
nonrecovery demonstrated classifier rejection: it was not detected in that
image. Deeper processing makes it measurable by the same segmentation rule.
Depth, drizzle sampling and detector-event rejection change together; the
experiment does not isolate their individual causes. Aperture SNR and pixel
segmentation are different criteria, as the remaining C-grade nonrecovery shows.
No native-pixel classifier was applied to the differently sampled mosaics.

No population completeness follows from three deliberately chosen failures.
The next controlled experiment is a blinded robust high-z and low-z cohort on
uniform deep mosaics, with jointly covered bands, PSF-matched angular detection,
aperture corrections and source-group leakage control. Inject on actual mosaic
backgrounds to measure the resulting end-to-end selection function.

Results: [actual measurements](../research_output/deep_reference_comparison.json).
Acquisition, checksum corruption, identity/DQ preservation and scaled-flux units
are covered by offline tests. No new galaxy or abundance discovery is claimed.
