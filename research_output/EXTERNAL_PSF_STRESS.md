# External modeled-PSF stress experiment

This exercises the actual segmentation/morphology and frozen classifier
on independently rendered Gaussian-intrinsic sources in synthetic Gaussian noise.
It is **not independent real-sky validation** and cannot establish survey completeness.

Trials: 2304; model SHA-256: `2d5fe3bc291652e0748fa5dea9911bc5c0430fbb29f87b306679ff9f8bc87a21`.

Flux is in total per-pixel background-noise units. Both kernels receive the
same noise and positions within each cell. Brackets: conditional 95% Wilson interval.

## Exploratory sensitivity findings

- F277W, unresolved, flux 60: modeled kernel detects 1/32 and accepts 1; Gaussian detects 24/32 and accepts 0.
- F277W, unresolved, flux 120: modeled kernel detects 32/32 and accepts 32; Gaussian detects 32/32 and accepts 0.
- F356W, unresolved, flux 60: modeled kernel detects 0/32 and accepts 0; Gaussian detects 30/32 and accepts 25.
- F444W, unresolved, flux 60: modeled kernel detects 0/32 and accepts 0; Gaussian detects 21/32 and accepts 21.

These differences show kernel sensitivity in this synthetic setup. They are
not measured astrophysical error rates or evidence that one kernel represents all sky sources.

## Full grid

| Filter | Radius px | Flux | Kernel | Detected/injected | Rejected/classified | Accepted/injected |
| --- | ---: | ---: | --- | --- | --- | --- |
| F277W | 0.0 | 30.0 | jades_dr5_modeled | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F277W | 0.0 | 30.0 | analytic_gaussian | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F277W | 0.0 | 60.0 | jades_dr5_modeled | 1/32 (3.1%; 0.6–15.7%) | 0/1 (0.0%; 0.0–79.3%) | 1/32 (3.1%; 0.6–15.7%) |
| F277W | 0.0 | 60.0 | analytic_gaussian | 24/32 (75.0%; 57.9–86.7%) | 24/24 (100.0%; 86.2–100.0%) | 0/32 (0.0%; 0.0–10.7%) |
| F277W | 0.0 | 120.0 | jades_dr5_modeled | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F277W | 0.0 | 120.0 | analytic_gaussian | 32/32 (100.0%; 89.3–100.0%) | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) |
| F277W | 0.0 | 240.0 | jades_dr5_modeled | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F277W | 0.0 | 240.0 | analytic_gaussian | 32/32 (100.0%; 89.3–100.0%) | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) |
| F277W | 0.75 | 30.0 | jades_dr5_modeled | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F277W | 0.75 | 30.0 | analytic_gaussian | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F277W | 0.75 | 60.0 | jades_dr5_modeled | 1/32 (3.1%; 0.6–15.7%) | 0/1 (0.0%; 0.0–79.3%) | 1/32 (3.1%; 0.6–15.7%) |
| F277W | 0.75 | 60.0 | analytic_gaussian | 26/32 (81.2%; 64.7–91.1%) | 0/26 (0.0%; 0.0–12.9%) | 26/32 (81.2%; 64.7–91.1%) |
| F277W | 0.75 | 120.0 | jades_dr5_modeled | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F277W | 0.75 | 120.0 | analytic_gaussian | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F277W | 0.75 | 240.0 | jades_dr5_modeled | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F277W | 0.75 | 240.0 | analytic_gaussian | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F277W | 1.5 | 30.0 | jades_dr5_modeled | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F277W | 1.5 | 30.0 | analytic_gaussian | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F277W | 1.5 | 60.0 | jades_dr5_modeled | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F277W | 1.5 | 60.0 | analytic_gaussian | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F277W | 1.5 | 120.0 | jades_dr5_modeled | 6/32 (18.8%; 8.9–35.3%) | 0/6 (0.0%; 0.0–39.0%) | 6/32 (18.8%; 8.9–35.3%) |
| F277W | 1.5 | 120.0 | analytic_gaussian | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F277W | 1.5 | 240.0 | jades_dr5_modeled | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F277W | 1.5 | 240.0 | analytic_gaussian | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F356W | 0.0 | 30.0 | jades_dr5_modeled | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F356W | 0.0 | 30.0 | analytic_gaussian | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F356W | 0.0 | 60.0 | jades_dr5_modeled | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F356W | 0.0 | 60.0 | analytic_gaussian | 30/32 (93.8%; 79.9–98.3%) | 5/30 (16.7%; 7.3–33.6%) | 25/32 (78.1%; 61.2–89.0%) |
| F356W | 0.0 | 120.0 | jades_dr5_modeled | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F356W | 0.0 | 120.0 | analytic_gaussian | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F356W | 0.0 | 240.0 | jades_dr5_modeled | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F356W | 0.0 | 240.0 | analytic_gaussian | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F356W | 0.75 | 30.0 | jades_dr5_modeled | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F356W | 0.75 | 30.0 | analytic_gaussian | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F356W | 0.75 | 60.0 | jades_dr5_modeled | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F356W | 0.75 | 60.0 | analytic_gaussian | 16/32 (50.0%; 33.6–66.4%) | 0/16 (0.0%; 0.0–19.4%) | 16/32 (50.0%; 33.6–66.4%) |
| F356W | 0.75 | 120.0 | jades_dr5_modeled | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F356W | 0.75 | 120.0 | analytic_gaussian | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F356W | 0.75 | 240.0 | jades_dr5_modeled | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F356W | 0.75 | 240.0 | analytic_gaussian | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F356W | 1.5 | 30.0 | jades_dr5_modeled | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F356W | 1.5 | 30.0 | analytic_gaussian | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F356W | 1.5 | 60.0 | jades_dr5_modeled | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F356W | 1.5 | 60.0 | analytic_gaussian | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F356W | 1.5 | 120.0 | jades_dr5_modeled | 2/32 (6.2%; 1.7–20.1%) | 0/2 (0.0%; 0.0–65.8%) | 2/32 (6.2%; 1.7–20.1%) |
| F356W | 1.5 | 120.0 | analytic_gaussian | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F356W | 1.5 | 240.0 | jades_dr5_modeled | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F356W | 1.5 | 240.0 | analytic_gaussian | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F444W | 0.0 | 30.0 | jades_dr5_modeled | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F444W | 0.0 | 30.0 | analytic_gaussian | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F444W | 0.0 | 60.0 | jades_dr5_modeled | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F444W | 0.0 | 60.0 | analytic_gaussian | 21/32 (65.6%; 48.3–79.6%) | 0/21 (0.0%; 0.0–15.5%) | 21/32 (65.6%; 48.3–79.6%) |
| F444W | 0.0 | 120.0 | jades_dr5_modeled | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F444W | 0.0 | 120.0 | analytic_gaussian | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F444W | 0.0 | 240.0 | jades_dr5_modeled | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F444W | 0.0 | 240.0 | analytic_gaussian | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F444W | 0.75 | 30.0 | jades_dr5_modeled | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F444W | 0.75 | 30.0 | analytic_gaussian | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F444W | 0.75 | 60.0 | jades_dr5_modeled | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F444W | 0.75 | 60.0 | analytic_gaussian | 6/32 (18.8%; 8.9–35.3%) | 0/6 (0.0%; 0.0–39.0%) | 6/32 (18.8%; 8.9–35.3%) |
| F444W | 0.75 | 120.0 | jades_dr5_modeled | 31/32 (96.9%; 84.3–99.4%) | 0/31 (0.0%; 0.0–11.0%) | 31/32 (96.9%; 84.3–99.4%) |
| F444W | 0.75 | 120.0 | analytic_gaussian | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F444W | 0.75 | 240.0 | jades_dr5_modeled | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F444W | 0.75 | 240.0 | analytic_gaussian | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F444W | 1.5 | 30.0 | jades_dr5_modeled | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F444W | 1.5 | 30.0 | analytic_gaussian | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F444W | 1.5 | 60.0 | jades_dr5_modeled | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F444W | 1.5 | 60.0 | analytic_gaussian | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F444W | 1.5 | 120.0 | jades_dr5_modeled | 0/32 (0.0%; 0.0–10.7%) | not estimable | 0/32 (0.0%; 0.0–10.7%) |
| F444W | 1.5 | 120.0 | analytic_gaussian | 31/32 (96.9%; 84.3–99.4%) | 0/31 (0.0%; 0.0–11.0%) | 31/32 (96.9%; 84.3–99.4%) |
| F444W | 1.5 | 240.0 | jades_dr5_modeled | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |
| F444W | 1.5 | 240.0 | analytic_gaussian | 32/32 (100.0%; 89.3–100.0%) | 0/32 (0.0%; 0.0–10.7%) | 32/32 (100.0%; 89.3–100.0%) |

## PSF receipts and resampling

- F277W: `c90117d6f3261a00a4e6ac1821aca30cc2c29917697fcea90db76fa255f8ec3b`; 0.029994759 → 0.063 arcsec/pixel; crop retains 97.98% of template flux before normalization. [Source](https://slate.ucsc.edu/~brant/jades-dr5/GOODS-S/hlsp/images/submosaics/hlsp_jades_jwst_nircam_jw011800-deep_f277wa_v5.0_mpsf.fits).
- F356W: `7bd8a4854c3b587be258022d05f72ac29aab393d98dff64bc2f69ed7dfbf7203`; 0.029994759 → 0.063 arcsec/pixel; crop retains 97.42% of template flux before normalization. [Source](https://slate.ucsc.edu/~brant/jades-dr5/GOODS-S/hlsp/images/submosaics/hlsp_jades_jwst_nircam_jw011800-deep_f356wa_v5.0_mpsf.fits).
- F444W: `b74abf676cd57f272ada642a27fbb6a8fcb6e0181407357784d812c7f5fd6db2`; 0.029994759 → 0.063 arcsec/pixel; crop retains 96.91% of template flux before normalization. [Source](https://slate.ucsc.edu/~brant/jades-dr5/GOODS-S/hlsp/images/submosaics/hlsp_jades_jwst_nircam_jw011800-deep_f444wa_v5.0_mpsf.fits).

## Software and captured warnings

numpy=2.3.5, scipy=1.17.0, astropy=8.0.1, photutils=3.0.0

- 226 × AstropyDeprecationWarning: 'npixels' was deprecated in version 3.0 and will be removed in version 4.0. Use argument 'n_pixels' instead.
- 62 × NoDetectionsWarning: No sources were found. Try lowering the threshold or pixels parameters.
- 1187 × AstropyDeprecationWarning: The 'xcentroid' attribute was deprecated in version 3.0; use 'x_centroid' instead. It will be removed in version 4.0.
- 1187 × AstropyDeprecationWarning: The 'ycentroid' attribute was deprecated in version 3.0; use 'y_centroid' instead. It will be removed in version 4.0.

## Limits

- All injected sources and backgrounds are synthetic; PSFs are modeled JADES shapes.
- Analytic Gaussian is a comparator, not the repo's empirical-PSF/Sersic training generator.
- Training PSF provenance is incomplete; independence from training PSF cannot be certified.
- No detector artifacts, correlated drizzle noise, source Poisson noise, crowding or sky coverage holes.
- Classifier assumes 0.063 arcsec long-wave pixels; kernels are resampled to that exact scale.
- Flux is total normalized-kernel flux in per-pixel background-noise units, not AB magnitude or measured SNR.
- Wilson intervals are conditional diagnostics; 16 same-image trials share an estimated background threshold.
- No AUC: the simulated truth contains only real-source equivalents.
- All injection centers are integer pixels; subpixel phase sensitivity is not measured.
- Crop wings and Gaussian intrinsic profiles differ from actual extended galaxies.
