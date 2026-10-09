# Same-filter validation built on merged PR16

The seven GOODS-S proposals in merged PR16 passed an **uncorrected photometric
screen**. New original F444W dithers now test that red signal independently at
the same sky coordinates. **One of seven persists; six do not reappear at the
measured depth.** This rejects six stable-source interpretations under the
stated measurement assumptions. It does not establish detector-artifact
identity, a redshift or a discovery.

## New archive products and accessible coverage repair

Round three is based on merged master
`656ad2b281dbc6adaa2930187f302ccb9bd30980`. The original seven-image manifest,
receipts and scientific reports remain unchanged. Five full original i2d
products add three SMACS filters plus GOODS F444W exposures `00001`/`00002`.
`data_sources/original_images_round3.json` preserves this 12-image selection.

The initially selected SMACS F090W is NRCA1, whereas its historical F200W is
NRCA4. The negative common-coverage result should not be treated as a search
finding. A provider HEAD request and full download verified
`jw02736001001_02105_00004_nrca1_i2d.fits`: its primary header gives
**DETECTOR=NRCA1, FILTER=F200W**, and actual SCI/ERR/WHT/WCS arrays pass the
checksum/readiness gate. The matched 13-image selection is separately pinned
in `data_sources/original_images_round3_matched_smacs.json`. This supplies the
accessible matched-quadrant repair for the next photometry rerun.

The 13 selected images total **1,555,571,520 bytes**, below the 1.5 GiB ceiling;
each is below 300 MiB. Old images are reused in place after verification.
Actual HTTP receipts for the six additions are under
`data_sources/receipts/original_round3/`. GOODS is CAL_VER 3.0.0; SMACS is
CAL_VER 2.0.1. These are single-exposure i2d images, not observation-level deep
mosaics or cutouts. The complete historical archive is still not provisioned.

## Three independent F444W looks

The new F444W products have the same effective exposure time, **1159.571 s**.
Actual mid-times give baselines **0.37280 and 0.74859 hours** from reference
exposure `00003`; the two new dithers are separated by 0.37579 hours. The
original repeat-pair machinery measures a WCS grid overlap of **0.950625** for
each pair. The source's own frozen reference flux is rerun and required to
reproduce before comparing the sibling measurements.

Every measurement uses the original fixed RA/Dec and the same angular aperture
(0.1887380795 arcsec) and annulus (0.3774761589–0.6291269315 arcsec). Fluxes are
calibrated in Jy using each image's own WCS pixel areas. Comparison errors
remain diagonal ERR plus background-mean estimates.

| Frozen source ID | Reference SNR | Sibling 00001 SNR | Sibling 00002 SNR | Operational result |
| --- | ---: | ---: | ---: | --- |
| 361 | 286.97 | 0.17 | untestable, 73.3% coverage | single-epoch-only in the covered comparison |
| 107 | 307.79 | 0.51 | 1.01 | single-epoch-only |
| 98 | 239.71 | 228.62 | 245.58 | persistent detection |
| 994 | 118.90 | -2.26 | -1.93 | single-epoch-only |
| 138 | 182.06 | -0.41 | -1.53 | single-epoch-only |
| 333 | 36.29 | 0.08 | 0.16 | single-epoch-only |
| 336 | 18.86 | -0.35 | 0.04 | single-epoch-only |

Source 98 has sibling/reference aperture-flux ratios **1.0469 and 1.0595**.
Persistence does not require perfectly constant measured aperture flux.
Subpixel aperture phase, PSF position, background and calibration can change
flux ratios. No variability or astrophysical-source classification is inferred.

There are **23 independently JADES-identified controls** with >=10 diagonal
SNR in the reference image. Sibling 00001 retains 22 at >=3 SNR; one comparison
is untestable because of coverage. Sibling 00002 retains all 23. This reports
the denominator before conditioning on recovery. Among the 22/23 controls
with >=10 SNR in both images, median flux ratios are **1.0352 and 1.0071**;
finite-source bootstrap 95% intervals are **[1.0034, 1.0656]** and
**[0.9761, 1.0258]**. The respective 16th–84th percentile ratio ranges are
0.9867–1.1168 and 0.9342–1.0407. These controls test registration and measurement
stability, not unbiased completeness or classifier retention.

## Assumption sensitivity and additional proposals

Inflating **both** compared diagonal flux errors by a factor of three still
leaves every covered comparison of the six nonpersistent proposals above
**6.10 sigma** discrepancy. With a factor of ten, source 336 becomes
inconclusive; the five other proposals still have significant discrepancies.
These factors are explicit sensitivity assumptions, not measured covariance
corrections or source-noise prescriptions. A common noise factor cannot be
silently applied to bright-source Poisson errors.

Additional proposals 254 and 46 entered a separate, conditional point-source
photometry screen. They were measured without replacing the original seven
or claiming that the PSF assumption is established. Both repeat:

| Conditional proposal | Reference SNR | Sibling 00001 SNR | Sibling 00002 SNR |
| --- | ---: | ---: | ---: |
| 254 | 122.78 | 125.51 | 125.66 |
| 46 | 53.00 | 93.88 | 65.63 |

Their astrophysical nature remains unresolved. The complete forced measurements,
depth/status checks and sensitivity variants are in
`research_output/f444w_repeat_screen.json`; the explicitly separate additional
selection is in `research_output/f444w_repeat_screen_conditional.json`.

## Reproduce

```bash
python -m data_pipeline.original_images data_sources/original_images_round3.json --output-dir data/original_round3 --previous-dir data/original_round2
python -m data_pipeline.original_images data_sources/original_images_round3_matched_smacs.json --output-dir data/original_round3 --previous-dir data/original_round2 --runtime-manifest-name images_manifest_matched_smacs.json
python -m discovery.f444w_repeat_screen data/original_round3/images_manifest.json
python -m discovery.f444w_repeat_screen data/original_round3/images_manifest_matched_smacs.json --additional-source-ids 254 46 --output research_output/f444w_repeat_screen_conditional.json
python -m pytest tests/test_external_astrometry.py tests/test_f444w_repeat_screen.py
```

The highest-value follow-up is to inspect calibrated detector/ramp/DQ history
for the six single-epoch events and fit multiband, PSF-aware contaminant models
for the three repeat-detected proposals. A source moving or varying over these
hour-scale baselines is still logically possible. Single-exposure selection
plus repeat imaging does not measure a galaxy abundance without independent
completeness, survey-volume and contaminant controls.
