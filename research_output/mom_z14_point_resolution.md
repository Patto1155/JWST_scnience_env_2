# MoM-z14 follow-up: generic point-source resolution and bin leverage

This experiment builds on merged PR #18 without replacing its provenance report. A pinned, generic UNITE point-source resolving-power calibration changes conditional flux constraints; source-specific slit geometry, wavelength uncertainty and empirical covariance are still missing. Nothing here measures elemental N/C or selects an enrichment mechanism.

## Verified calibration

[Pinned author code](https://raw.githubusercontent.com/TheSkyentist/unite/156e29eb75f788f90041b5d2bbae27ae9dac78d8/unite/instrument/nirspec/disperser.py) supplies PRISM POINT-source R(λ), citing [de Graaff et al.](https://doi.org/10.1051/0004-6361/202347755). The acquired CSV and receipt pin the source, official wavelength grid and derivative checksums. We replay the descending polynomial coefficients without executing downloaded author code. Generic point-source R is closer to the published UNITE model family than the preceding fully illuminated slit curve, but the current pinned commit is not proven to be the exact paper runtime, and its Gaussian approximation is not MoM's shutter-specific full LSF.

| UV group | Nominal illuminated R | Generic point-source R |
|---|---:|---:|
| NIV | 61.36 | 122.18 |
| CIV | 66.04 | 130.42 |
| HeII_OIII | 74.61 | 144.94 |
| NIII | 82.80 | 158.40 |
| CIII | 97.68 | 182.42 |

## Actual-FITS fits

Same 73 quality-masked bins, full original bin edges, z=14.44, intrinsic width zero, signed amplitudes and a linear fν continuum. Flux units are 10⁻²⁰ erg s⁻¹ cm⁻²; ± values are conditional GLS errors.

| Group | Earlier nominal R | Generic point-source R | All-bin-delete flux range (point R) |
|---|---:|---:|---:|
| NIV | 53.78 ± 15.66 | 40.40 ± 10.82 | 29.30–41.96 |
| CIV | 37.29 ± 13.32 | 31.59 ± 9.31 | 5.10–33.08 |
| HeII_OIII | 32.58 ± 14.70 | 23.25 ± 12.21 | 19.90–28.71 |
| NIII | 13.76 ± 10.43 | 14.41 ± 8.32 | 11.98–16.96 |
| CIII | 27.68 ± 8.93 | 20.61 ± 6.88 | 20.01–21.49 |

The point-source summed nitrogen/carbon **line-flux** ratio is 1.050, conditional 95% Fieller set `{"type": "bounded", "interval": [0.5017799257698845, 2.0472251119124865]}`. Across the 29 specified point-resolution scenarios its point estimate spans 0.619–1.413; this is an assumption range, not a confidence interval or elemental abundance.

The tied scan gives z=14.440, Δχ²≤1 profile envelope [14.43, 14.45]. Line-flux profile intervals propagating the tied z/width grid are saved with the conditional covariance matrices. Width, redshift and correlations remain model conditional; no independently calibrated significance is claimed.

Assumed AR(1) ρ=0/0.25/0.5, all six central 2D extraction alternatives, intrinsic width 300/650 km/s, continuum orders 0/2/3 and alternative multiplet/blend weights are retained in the compact JSON. Empirical covariance is not inferred from these scenarios. The no-correlation null scan repeats 1,000 seeded simulations under the same limited Gaussian model; it includes the stated z/width search but excludes prior source/line selection and unknown reduction systematics.

## Leverage is expected at PRISM sampling

Every usable bin is withheld once, with no neighbor bin-edge changes and no flux-dependent rejection. These are diagnostic perturbations, **not** newly justified masks or bad-pixel identifications. A genuine unresolved feature sampled by few bins can have high one-bin leverage.

| Group | Smallest estimate after one omission | Omitted observed wavelength |
|---|---:|---:|
| NIV | 29.30 ± 31.37 | 2.297625 µm |
| CIV | 5.10 ± 27.72 | 2.393414 µm |
| HeII_OIII | 19.90 ± 12.38 | 2.546498 µm |
| NIII | 11.98 ± 9.93 | 2.692085 µm |
| CIII | 20.01 ± 6.89 | 3.078733 µm |

The useful next test is recurrence and native quality of influential detector samples across independent nods/integrations, with the complete extraction geometry. Removing a high bin solely because it supports a line would bias the fit.

## Acquired actual native-DQ control

One public native-grid calibrated MoM-z14 slit was acquired and verified by source ID and coordinates. It supplies SCI/ERR/DQ/WAVELENGTH and pathloss/variance arrays for 1750.667 s, calibrated with `2.0.1` / `jwst_1535.pmap`. 7,565 pixels have finite values, positive errors and neither DO_NOT_USE nor SATURATED. Upstream `SRCTYPE=EXTENDED` and `BUNIT=MJy/sr` differ from the DJA point-source extraction; no unvalidated conversion/extraction is presented.

Line-window DQ counts include **all spatial slit rows**, including geometric edges, and cannot be read as trace contamination fractions. One exposure's DQ is now accessible, while complete coadd PIXTAB, exposure-mask mapping and calibrated source-specific geometry remain genuine dependencies.

## All-nine-exposure quality follow-up

The acquisition team subsequently fetched all 9 actual native calibrated exposures (464,135,040 bytes), selected from the verified DJA SLITS list. This experiment independently re-reads each compact target slit, validates receipt and manifest SHA256, and re-evaluates wavelength/DQ/error overlap. All pixels in the five ±generic-point-FWHM UV windows are finite with positive errors and lack DO_NOT_USE/SATURATED in every acquired exposure. All highest-leverage N IV]/C IV wavelength-overlap samples are likewise usable under these explicit criteria.

This closes the specific archive-access and basic native-DQ input gaps. It supplies no flag-based reason to discard the influential bins. It does **not** close source-trace mapping, geometry/pathloss, exposure/nod background modelling, source-specific LSF or empirical covariance, and it does not establish independent line detections. All-row wavelength checks are kept distinct from a full reduction or source-trace completeness.

| High-leverage DJA bin | All-nine native wavelength-overlap pixels | Native usable pixels | DO_NOT_USE | SATURATED |
|---|---:|---:|---:|---:|
| NIV: 2.297625 µm | 171 | 171 | 0 | 0 |
| CIV: 2.393414 µm | 171 | 171 | 0 | 0 |

These native samples supply no flag-based justification for dropping the influential wavelengths. The 2026 official native calibration differs from the 2025 DJA processing; mapping exact original coadd contributors and its internal rejection remains an analysis task. Complete matched re-extraction is still needed, while the nine original calibrated exposures are acquired and verified.

## Rejected shortcuts and next experiments

Reject equating UV flux ratios with N/C, arbitrary rejection of influential bins, treating repeated extractions as independent data, and substituting the generic R polynomial for a full source-specific calibrated LSF. WR/VMS/SMS/AGN/rotating Pop III are still not distinguished by these data alone.

Highest value: reconstruct exposure/nod-separated spectra with native DQ and matched pathloss/geometry; compare a full point-source LSF and wavelength calibration nuisance against the Gaussian approximation; calibrate spectral/spatial covariance on independent controls; obtain higher-resolution N IV], N III], C III] and separated He II/O III] for density/ionization/emissivity inference.

```bash
OPENBLAS_NUM_THREADS=1 python -m tools.jwst.point_resolution
# Include the acquired native slit control explicitly:
OPENBLAS_NUM_THREADS=1 python -m tools.jwst.point_resolution --native-slit data_sources/followup/mom_00002_native_slit.fits
# Reproduce all-nine acquisition and quality follow-up (bounded 600 MiB):
python -m data_pipeline.mom_native_batch --spectrum data_sources/pilot/mom_z14_dja_v4.spec.fits --output /tmp/mom-native --report /tmp/mom-native-batch.json
OPENBLAS_NUM_THREADS=1 python -m tools.jwst.point_resolution --native-batch /tmp/mom-native-batch.json --native-dir /tmp/mom-native
python -m pytest -q tests/test_point_resolution.py tests/test_line_sensitivity.py
```

The first-round nominal-R JSON is retained unchanged. The new companion JSON omits model-vector duplication and records scenario flux/covariance, redshift profiles, null summaries, all 73 bin omissions under each R curve and native quality support for the acquired nine-exposure set.
