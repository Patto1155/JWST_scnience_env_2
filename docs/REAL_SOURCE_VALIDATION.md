# Frozen classifier on actual M92 stars and known JADES galaxies

9 October 2026. These are measurements on downloaded public image pixels,
not synthetic injections. The classifier weights, feature definition and
threshold 0.5 were frozen before evaluation. No fitting or threshold tuning was
performed. The small tracked JSON reports preserve the model/image SHA256,
denominators, quality policy, ambiguity counts, magnitude bins and all six
catalogue-matched rejection cases. Full per-source trials are reproducible
outside git; their exact output hashes are in the reports.

## M92: independent real stellar references

The [JWSTSTARS release](https://archive.stsci.edu/hlsp/jwststars) provides a
984,423-row M92 NIRCam catalogue, independently measured by DOLPHOT and aligned
to Gaia DR3. It is **not pre-culled**. We prespecified type 1, F444W SNR >= 10,
absolute DOLPHOT sharpness <= 0.2, nonnegative crowding <= 0.1 mag, quality flag
0 and valid photometry. These conservative operational cuts select **27,016**
stellar references. They are quality criteria, never labels from our classifier.
They are not claimed to be universally optimal or certified stellar identities.

Acquisition used the actual released catalogue plus two NRCALONG F444W `cal`
exposures, 1 and 4 of visit `01334001001`. Exposure 3 is expressly excluded
because the release reports excess astrometric jitter. The complete acquisition
is **534,424,320 bytes** (about 510 MiB), below the 600 MiB cap. The >1 GiB F150W
reference mosaic was not downloaded. The images were reprocessed with
`CAL_VER=2.0.1`, `CRDS_CTX=jwst_1535.pmap`; the catalogue used earlier pipeline
versions. This mismatch is disclosed, not hidden by changing the coordinates.

The frozen detector uses its original 5-sigma/5-pixel segmentation and morphology.
Native long-wave pixel sampling is required. Independent DO_NOT_USE/SATURATED
flags and coverage masks are applied. A 0.2 arcsec spherical match must be
one-to-one: blends and multiple neighbors remain unknown. Border, masked and
off-array references are counted separately.

| F444W exposure | Covered references | Ambiguous | Detected / unambiguous | Rejected / classified | Accepted / unambiguous |
|---|---:|---:|---:|---:|---:|
| 1 | 13,193 | 62 | 8,733 / 13,131 | 3 / 8,733 | 8,730 / 13,131 |
| 4 | 13,220 | 63 | 8,744 / 13,157 | 3 / 8,744 | 8,741 / 13,157 |

Conditional rejection is **0.0344%** (nominal 95% Wilson interval
**0.0117–0.1010%**) in exposure 1 and **0.0343%** (**0.0117–0.1008%**) in
exposure 4. Full-chain recovery among unambiguous references is **66.48%**
(65.67–67.29%) and **66.44%** (65.62–67.24%). Allowing all ambiguous references
to fail or pass gives bounds of **66.17–66.64%** and **66.12–66.60%** among all
covered quality references. These are different denominators.

Detection, rather than classifier retention, is the principal limitation:

| Reference Vega magnitude | Exposure 1 detected / references | Exposure 4 detected / references |
|---|---:|---:|
| <20 | 7,401 / 7,513 | 7,392 / 7,513 |
| 20–22 | 1,332 / 5,106 | 1,352 / 5,126 |
| 22–24 | 0 / 512 | 0 / 518 |

The reference SNR is from full-stack DOLPHOT photometry, not the single exposure.
There is no evidence here for faint high-redshift completeness. Catalogue-matched
rejections comprise six different source identities; every one passes in the
other dither. Detector events near a real source or association errors remain
possible explanations, so these are not unconditionally asserted true stellar
false positives. Their coordinates and both scores are retained for inspection.

There are **13,308 stable covered stellar groups**, with **9,029 accepted in at
least one covered image**. The dithers share one visit and the same stars. They
must not be pooled as 26,413 independent objects. No pooled-binomial interval is
reported. Median matched residuals are 0.0831 and 0.0828 arcsec; the radius-limited
residuals do not independently certify the absolute frame.

M92 is outside the known real training field (GOODS-S) and program/visit.
However, legacy injected training rows lack complete source/field/visit/generator
provenance, and hashes alone do not prove how the saved model was fitted. The full
independence contract therefore remains **unverified**, despite this useful
held-out real-field test. Only one held-out M92 visit is available in this bounded
experiment. Single-class stars cannot estimate artifact recall or ROC AUC.

## JADES: actual covered reference recovery, with observations grouped

The checksummed DR4 catalogue is grouped conservatively by shared positive,
field-scoped DR5 IDs or 0.3 arcsec spherical proximity. Negative sentinel IDs are
never identities. Connected components prevent repeated observations leaking
between cohorts, but close neighbors can merge; they are not certified counts of
unique galaxies. Ten components are wider than the radius through shared IDs or
transitive associations. There are no conflicting robust redshifts under the
declared consistency threshold.

| Cohort | Observation rows | Conservative sky groups |
|---|---:|---:|
| Robust A/B z >= 6 | 243 | 226 |
| Robust A/B 0 <= z < 3 | 1,461 | 1,440 |
| Separate secure C z >= 6 | 48 | 41 |

Only 22 references lie inside the valid corrected-anchor original F444W image:
19 low-z controls, one A/B high-z source and two C high-z sources. **11/22 are
detected; all 11 are low-z and pass the frozen classifier.** Zero rejection among
11 permits a nominal 25.9% Wilson upper bound, rather than proving lossless
classification. **All three covered high-z references are undetected.** No
classifier conclusion about those high-z sources can follow. Their IDs,
coordinates and redshifts remain in `real_validation_jades.json` for independent
deep-mosaic follow-up. Matched residuals have median 0.0178 arcsec and 95th
percentile 0.0341 arcsec. Target coordinates can differ from photometric centroids.

This GOODS image shares a training field and visit; it is a recovery diagnostic,
not a held-out generalization test. Neither targeted spectroscopy nor these
quality-selected stars measures survey prevalence or unbiased completeness.

## Reproduce

```bash
python -m data_pipeline.real_validation_acquire /tmp/m92
python -m discovery.real_validation stars /tmp/m92/hlsp_jwststars_jwst_nircam_m92_f090w-f150w-f277w-f444w_v1_phot.fits \
  --image /tmp/m92/jw01334001001_04101_00001_nrcalong_cal.fits \
  --image /tmp/m92/jw01334001001_04101_00004_nrcalong_cal.fits \
  --output /tmp/m92-summary.json --full-output /tmp/m92-trials.json
python -m discovery.real_validation galaxies data_sources/pilot/jades_dr4_reference.csv \
  --image /path/to/jw01180026001_09201_00003_nrcalong_i2d.fits \
  --output /tmp/jades-summary.json --full-output /tmp/jades-trials.json
python -m pytest tests/test_real_validation.py tests/test_reference_cohorts.py runner/tests/test_validation_metrics.py
```

All inputs are public. Acquisition verifies fresh MAST metadata and exact pinned
SHA256 values; altered upstream bytes fail rather than silently changing the
experiment. Images and large raw tables stay outside tracked artifacts. MAST's
JWSTSTARS DOI is `10.17909/cn6n-xg90`, with CC BY 4.0 attribution. The release README
snapshot, source URLs and receipts are in `data_sources/pilot/real_validation_*`.

The next useful tests are independent deep-mosaic recovery of the three JADES
nondetections; fainter real stars with sufficient per-exposure depth; independent
artifact labels; matching-radius/crowding sensitivity; and another held-out field
and visit. Bright M92 retention does not substitute for those experiments.
