# MoM-z14: UV-line and extraction sensitivity

The public DJA spectrum supports a reproducible conditional UV-line fit, but it does not identify an enrichment mechanism or measure elemental N/C. Extraction/background and source-specific LSF remain material limitations. All numerical values below come from actual FITS samples.

## Inputs and calibration

Source SHA256: `42d95d348ebb55ca37eb31393b4603628ac13a4bca1f4f7f0ffba7b32d3125b1`. MsaExp version: `0.9.5.dev8+ge2b237b`. The 473-bin PRISM/CLEAR product has SCI/WHT/PROFILE/BACKGROUND, but no exposure DQ or PIXTAB. Stored SPEC1D prefers the original unresampled pixel-table extraction.

[The exact MsaExp generator](https://github.com/gbrammer/msaexp/blob/e2b237b/msaexp/slit_combine.py) divides science by pathloss and variance by pathloss² before resampling. SCI is nod-differenced, BACKGROUND is a separate sky estimate, and PROFILE has signed negative nod ghosts. Our alternatives use the central profile, propagate WHT=1/variance, and apply neither a second path correction nor a second sky subtraction. The optional spatially constant background is fitted as a nuisance in each wavelength column, with its covariance propagated.

[STScI's tabulated PRISM resolving power](https://jwst-docs.stsci.edu/jwst-near-infrared-spectrograph/nirspec-instrumentation/nirspec-dispersers-and-filters) supplies wavelength-dependent R=61.4–97.7 across these groups. Its nominal 2.2-pixel fully illuminated aperture is approximated with a Gaussian; it is **not** a source-specific calibrated point-source LSF. A ±30% FWHM scaling is a sensitivity check, not a calibration posterior.

## Model and masks

The fixed 2.15–3.20 µm window has 73 usable bins. Finite flux, positive finite errors, npix, profile_sum, var_sum and path_corr define the stored mask. Alternatives require valid SCI/WHT/PROFILE, at least two valid spatial rows and ≥95% of the modeled aperture support. No flux/SNR-dependent rejection is applied. Original full-grid bin edges remain unchanged when a bin is masked.

Five signed integrated line amplitudes are fit jointly with a smooth polynomial continuum in fν. Gaussians are integrated over bins, convolved by quadrature with instrumental FWHM and a shared intrinsic FWHM. Redshift and width are tied across groups. Multiplet weights and the He II/O III] decomposition are explicit assumptions. We retain negative estimates rather than imposing a positivity prior. Formal errors include linear continuum covariance; redshift/width profile intervals are saved separately.

## Results at published z=14.44

All fluxes are 10⁻²⁰ erg s⁻¹ cm⁻². ± values are conditional one-sigma GLS errors, not independently calibrated detection significances.

| Scenario | N IV] | C IV | He II + O III] | N III] | C III] | (N IV]+N III])/(C IV+C III]) |
|---|---:|---:|---:|---:|---:|---:|
| stored_pixel_table_1d; ρ=0; LSF×1; width=0; cont=1; equal_HeO | 53.78 ± 15.66 | 37.29 ± 13.32 | 32.58 ± 14.70 | 13.76 ± 10.43 | 27.68 ± 8.93 | 1.039 |
| stored_pixel_table_1d; ρ=0.25; LSF×1; width=0; cont=1; equal_HeO | 57.11 ± 18.10 | 43.85 ± 15.44 | 35.39 ± 17.89 | 17.74 ± 12.37 | 28.11 ± 10.50 | 1.040 |
| stored_pixel_table_1d; ρ=0.5; LSF×1; width=0; cont=1; equal_HeO | 61.53 ± 18.75 | 54.54 ± 16.07 | 39.99 ± 20.50 | 24.76 ± 13.37 | 28.47 ± 11.18 | 1.039 |
| 2d_optimal_r1; ρ=0; LSF×1; width=0; cont=1; equal_HeO | 50.41 ± 17.14 | 34.22 ± 14.46 | 33.21 ± 15.81 | 15.34 ± 11.07 | 26.74 ± 9.42 | 1.079 |
| 2d_optimal_r1; ρ=0.25; LSF×1; width=0; cont=1; equal_HeO | 53.94 ± 19.83 | 40.56 ± 16.76 | 35.98 ± 19.23 | 19.32 ± 13.13 | 27.61 ± 11.09 | 1.075 |
| 2d_optimal_r1; ρ=0.5; LSF×1; width=0; cont=1; equal_HeO | 58.70 ± 20.57 | 50.83 ± 17.45 | 40.45 ± 22.00 | 26.35 ± 14.19 | 28.85 ± 11.79 | 1.067 |
| 2d_optimal_r2; ρ=0; LSF×1; width=0; cont=1; equal_HeO | 53.77 ± 16.91 | 34.32 ± 14.27 | 35.87 ± 15.64 | 14.77 ± 10.95 | 26.99 ± 9.33 | 1.118 |
| 2d_optimal_r2; ρ=0.25; LSF×1; width=0; cont=1; equal_HeO | 57.81 ± 19.56 | 40.47 ± 16.55 | 38.35 ± 19.02 | 18.95 ± 12.98 | 27.75 ± 10.98 | 1.125 |
| 2d_optimal_r2; ρ=0.5; LSF×1; width=0; cont=1; equal_HeO | 63.54 ± 20.28 | 50.42 ± 17.24 | 42.13 ± 21.76 | 26.36 ± 14.04 | 28.76 ± 11.68 | 1.135 |
| 2d_optimal_r3; ρ=0; LSF×1; width=0; cont=1; equal_HeO | 54.01 ± 16.89 | 35.33 ± 14.26 | 36.03 ± 15.63 | 14.80 ± 10.94 | 27.20 ± 9.32 | 1.100 |
| 2d_optimal_r3; ρ=0.25; LSF×1; width=0; cont=1; equal_HeO | 58.23 ± 19.53 | 41.56 ± 16.53 | 38.52 ± 19.01 | 18.96 ± 12.98 | 27.99 ± 10.97 | 1.110 |
| 2d_optimal_r3; ρ=0.5; LSF×1; width=0; cont=1; equal_HeO | 64.30 ± 20.25 | 51.65 ± 17.22 | 42.27 ± 21.76 | 26.32 ± 14.03 | 29.03 ± 11.67 | 1.123 |
| 2d_boxcar_r1; ρ=0; LSF×1; width=0; cont=1; equal_HeO | 47.81 ± 18.35 | 33.11 ± 15.66 | 33.03 ± 16.94 | 14.47 ± 11.72 | 25.43 ± 9.88 | 1.064 |
| 2d_boxcar_r1; ρ=0.25; LSF×1; width=0; cont=1; equal_HeO | 51.22 ± 21.24 | 39.93 ± 18.16 | 35.66 ± 20.58 | 18.70 ± 13.90 | 27.14 ± 11.62 | 1.042 |
| 2d_boxcar_r1; ρ=0.5; LSF×1; width=0; cont=1; equal_HeO | 55.64 ± 22.05 | 50.99 ± 18.92 | 39.61 ± 23.50 | 26.13 ± 15.01 | 29.94 ± 12.36 | 1.010 |
| 2d_boxcar_r2; ρ=0; LSF×1; width=0; cont=1; equal_HeO | 52.61 ± 21.29 | 22.57 ± 18.70 | 42.10 ± 19.73 | 15.55 ± 14.08 | 28.44 ± 11.94 | 1.336 |
| 2d_boxcar_r2; ρ=0.25; LSF×1; width=0; cont=1; equal_HeO | 57.04 ± 24.62 | 29.49 ± 21.78 | 43.38 ± 24.00 | 20.75 ± 16.62 | 29.50 ± 14.05 | 1.319 |
| 2d_boxcar_r2; ρ=0.5; LSF×1; width=0; cont=1; equal_HeO | 63.39 ± 25.52 | 41.00 ± 22.85 | 44.18 ± 27.44 | 29.93 ± 17.81 | 31.09 ± 14.94 | 1.295 |
| 2d_profile_plus_background_r3; ρ=0; LSF×1; width=0; cont=1; equal_HeO | 36.60 ± 24.02 | 45.33 ± 20.62 | 23.23 ± 22.39 | 16.85 ± 15.71 | 25.33 ± 13.20 | 0.756 |
| 2d_profile_plus_background_r3; ρ=0.25; LSF×1; width=0; cont=1; equal_HeO | 40.13 ± 27.79 | 54.77 ± 23.95 | 26.84 ± 27.29 | 18.53 ± 18.60 | 27.50 ± 15.50 | 0.713 |
| 2d_profile_plus_background_r3; ρ=0.5; LSF×1; width=0; cont=1; equal_HeO | 44.65 ± 28.84 | 70.76 ± 25.03 | 33.13 ± 31.38 | 20.85 ± 20.03 | 31.22 ± 16.43 | 0.642 |
| stored_pixel_table_1d; ρ=0; LSF×0.7; width=0; cont=1; equal_HeO | 46.67 ± 12.85 | 34.78 ± 10.97 | 28.30 ± 13.31 | 14.85 ± 9.09 | 23.26 ± 7.59 | 1.060 |
| stored_pixel_table_1d; ρ=0; LSF×1.3; width=0; cont=1; equal_HeO | 59.60 ± 18.46 | 38.25 ± 15.63 | 34.33 ± 15.95 | 12.90 ± 11.74 | 31.10 ± 10.18 | 1.045 |
| stored_pixel_table_1d; ρ=0; LSF×1; width=300; cont=1; equal_HeO | 53.82 ± 15.68 | 37.31 ± 13.34 | 32.60 ± 14.71 | 13.75 ± 10.44 | 27.75 ± 8.95 | 1.039 |
| stored_pixel_table_1d; ρ=0; LSF×1; width=650; cont=1; equal_HeO | 53.97 ± 15.74 | 37.35 ± 13.40 | 32.69 ± 14.75 | 13.69 ± 10.50 | 27.96 ± 9.02 | 1.036 |
| stored_pixel_table_1d; ρ=0; LSF×1; width=0; cont=0; equal_HeO | 52.04 ± 14.76 | 36.12 ± 12.84 | 31.91 ± 14.56 | 13.80 ± 10.43 | 28.25 ± 8.76 | 1.023 |
| stored_pixel_table_1d; ρ=0; LSF×1; width=0; cont=2; equal_HeO | 54.48 ± 15.80 | 37.01 ± 13.35 | 31.01 ± 15.41 | 12.71 ± 10.89 | 27.52 ± 8.94 | 1.041 |
| stored_pixel_table_1d; ρ=0; LSF×1; width=0; cont=3; equal_HeO | 59.10 ± 15.97 | 46.10 ± 14.13 | 39.40 ± 15.99 | 11.95 ± 10.90 | 23.06 ± 9.22 | 1.027 |
| stored_pixel_table_1d; ρ=0; LSF×1; width=0; cont=1; HeII_only | 52.90 ± 15.62 | 36.54 ± 13.29 | 24.94 ± 11.91 | 13.27 ± 10.41 | 27.36 ± 8.92 | 1.035 |
| stored_pixel_table_1d; ρ=0; LSF×1; width=0; cont=1; OIII_only | 51.56 ± 15.60 | 35.49 ± 13.28 | 16.90 ± 11.56 | 12.84 ± 10.42 | 27.27 ± 8.92 | 1.026 |
| stored_pixel_table_1d; ρ=0; LSF×1; width=0; cont=1; alternate_multiplets | 53.55 ± 15.81 | 37.39 ± 13.34 | 32.58 ± 14.70 | 13.76 ± 10.43 | 27.66 ± 8.94 | 1.035 |

The baseline line-flux ratio is 1.039, with a conditional 95% Fieller interval [0.448, 2.159]. Across all 31 stated scenarios its point estimate spans 0.642–1.336; this range is not a confidence interval. The spatial background-nuisance alternative admits zero/negative nitrogen-line flux at 95%, while its point estimate remains consistent with the baseline within broad errors.

Increasing intrinsic FWHM from 0 to 650 km/s changes baseline fluxes by <1.1% because the nominal instrument FWHM is roughly 3,000–4,900 km/s. Under this nominal LSF the data do not resolve intrinsic widths in that range. Source illumination and background treatment have larger effects. N III] is a weak conditional estimate in this implementation; this does not refute the published fit, whose calibrated point-source LSF, continuum, prior and extraction handling differ.

## Redshift scan, covariance and limits

The tied UV-group scan over z=14–15 (step 0.005) and intrinsic widths 0/300/650 km/s gives best z=14.440, consistent with the published z=14.44. The Δχ²≤1 profile envelope is [14.425, 14.455]. This is conditional on the adopted LSF, continuum, blends and covariance and is not a replacement for the published posterior. The best width is on the lower boundary; no resolved width measurement is claimed.

AR(1) ρ=0, 0.25 and 0.5 are **assumed covariance scenarios**, not measured correlations. With stored diagonal errors χ²=89.99 for 66 degrees of freedom; ρ=0.5 increases it to 186.30/66. Strong assumed positive covariance is thus a poor residual description under this smooth model and should not be promoted as a calibrated uncertainty estimate. None of the scenarios includes unknown spatial covariance or exposure-level reduction systematics.

A seeded conditional Gaussian-null exercise repeats the full z/width scan for 1,000 simulations. Zero simulated maxima exceed the observed joint signed-template improvement under either tested covariance, so the Monte Carlo resolution is only about 0.001 (plus-one value); it does not establish an exact smaller tail probability. This is a conditional check of joint template structure, not new line discoveries or an astrophysical false-positive rate. The line set and source were selected in previous research; that selection, alternative continua, uncertain LSF and unknown real covariance are outside this null.

## Relation to published chemistry and rejected shortcuts

[Naidu et al. v2](https://arxiv.org/html/2505.11263v2) already uses UNITE wavelength-dependent point-source LSF and calibration uncertainty, tied intrinsic widths up to 650 km/s, and multi-Gaussian blends. The old input JSON caveat has been corrected to make that explicit. We reproduce the existence of useful UV constraints under a simpler model, not the exact published posterior. Paper line values remain a separately labelled transcription, not fit inputs.

Reject these interpretations: a flux ratio of ~1 is not elemental N/C; a line-width boundary is not resolved kinematics; re-extractions sharing the same exposures are not independent confirmations; nominal spectral null tails do not resolve astrophysical identity; nitrogen enhancement is not an age clock for the entire galaxy. No WR, VMS, SMS, AGN, Population III or cosmology mechanism is selected by this experiment.

## Highest-value next experiments

1. Acquire original slit/exposure pixel tables with DQ and source-specific LSF/pathloss metadata; compare UNITE-style point-source convolution against the nominal curve and fit independent nod groups. The current file lacks these inputs, so neither exact original extraction nor empirical exposure covariance can be recovered here.
2. Calibrate wavelength and spatial covariance from independent integrations and line-free controls, then fit a residual background model constrained by genuinely off-source pixels. Stored BACKGROUND must not be subtracted again.
3. Obtain higher-resolution spectra resolving N IV], N III], C III] density diagnostics and separating He II from O III]; propagate temperature, density, ionization and atomic emissivity into any abundance/yield comparison.

## Reproduce

```bash
OPENBLAS_NUM_THREADS=1 python -m tools.jwst.line_sensitivity
python -m tools.jwst.line_report
python -m pytest -q tests/test_line_sensitivity.py
```

Known-signal controls independently integrate Gaussian spectra on fine grids, mask a line-center bin without changing its neighbors' bin edges, recover synthetic spatial fluxes and nuisance backgrounds, verify inverse-variance propagation, preserve unbounded Fieller sets for weak denominators, and preserve masked-bin separations in AR covariance. Raw per-scenario fluxes, covariance matrices, model vectors, profile intervals, masks and scan/null results are in the companion JSON.

Rerunning `line_report` saves the companion scientific plot as `mom_z14_line_sensitivity.png`.
