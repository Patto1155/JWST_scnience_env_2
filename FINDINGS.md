# Measurement audit and scientific limits

Reproduce the recorded-photometry audit with:

```bash
python discovery/audit_candidates.py
```

The checked-in historical JSON products are preserved research records, not
results regenerated with the corrected pipeline. Rerun the command to obtain a
current report before quoting catalog-level audit verdicts.

## What the historical catalog supports

All **1732 entries are untestable by the complete configured dropout selection**;
none have both F090W and F200W coverage. This invalidates their high-redshift
selection evidence. It does **not** establish that every object is a detector
artifact, that no genuine high-redshift source exists, or that discovery is
impossible. The 25 shortlisted entries also fail to supply the required evidence.

At the current 90% aperture-coverage threshold:

| check | count |
| --- | ---: |
| historical candidate records | 1732 |
| F090W covered | 311 |
| F200W covered | 363 |
| both covered | 0 |
| different module names (warning only) | 555 |
| untestable | 1732 |
| falsified by valid complete measurements | 0 |
| surviving the configured selection | 0 |

The earlier 314/365 coverage counts used a 50% threshold. They are not equivalent
to full-aperture measurements. Historical products also lack image-specific
physical calibration and matched angular aperture metadata required by the audit.

## The failures and the corrected checks

**Missing sky coverage was treated as a perfect non-detection.** Independently
choosing one image per filter paired exposures whose WCS footprints did not cover
the source. A returned off-array zero is missing data, not a flux upper limit.
Exposure selection and aperture measurement must use actual WCS and validity
masks. Module A/B names alone cannot establish overlap: different visits and
orientations can bring opposite modules onto the same sky position.

**The audit previously accepted ordinary faint sources.** It calculated a blue
limit but did not require that limit to pass the dropout cut. The current audit
requires a covered calibrated red detection (SNR >= 5), a blue non-detection
(SNR <= 2), and `(max(blue_flux, 0) + 2*blue_error)/red_flux < 0.05`, with finite
positive uncertainties. Missing evidence is `untestable`; valid evidence failing
the cut is `falsified`; passing is `survives`, not a redshift confirmation.
Independent synthetic controls verify all three outcomes.

**MJy/sr sums were mistaken for flux densities.** A flux conversion needs the
image's actual pixel solid angle and units. Nominal detector pixel scales can
provide labelled estimates for old records, but are not authoritative for
resampled mosaics. Equal pixel aperture radii across detectors do not measure the
same sky area. The audit requires calibrated background-subtracted Jy fluxes and
matched angular aperture radii. PSF differences, aperture corrections and
correlated drizzle noise still require assessment before precision colours or
uncertainties are claimed.

**Brightness was used as a hard physical veto.** A bright apparent magnitude
alone cannot rule out high redshift, particularly in the lensed SMACS field.
Extreme colours also have no universal maximum Lyman-break amplitude: an
undetected blue flux gives a depth-dependent lower limit, not a measured break
amplitude. Brightness now triggers contaminant/lensing review only.

## What to build next

Known-galaxy recovery on public deep mosaics, independent artifact classification
controls, and completeness measurements are useful before a discovery campaign.
Single-exposure detections can study detector residuals, but repeated absence
alone is not a universal artifact label; moving sources, variability, depth and
background errors must be considered. Deep well-studied fields reduce expected
novelty, but do not imply a zero discovery probability.

A defensible high-redshift claim needs multiband SED modelling, contaminants,
lensing where relevant, calibrated uncertainties and independent redshift
confirmation. The current audit is a reproducible screening check, not a model
of the high-redshift universe or a proof of new physics.
