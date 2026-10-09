# Original-image calibrated photometry rerun

Execution status: **executed**. Input manifest SHA256: `aed2f5074d9dce254110c66d75f4a3cca56f2cf9a8cb1fb0ef74c23bbe498006`.

Historical catalogs are preserved. Input bytes are verified before analysis.
The existing Universe Table, WCS anchor selection, source detector, calibrated
matched-angular-aperture photometry and physical candidate audit are used.

- Detections: 1134
- Exploratory measured proposals: 1134
- Untestable proposals: 891
- Valid proposals failing the configured dropout cut: 236
- Proposals surviving the dropout screen: 7

The morphology classifier is frozen and is not applied to this science selection.
Selection requires all three covered calibrated bands, matched angular apertures,
F444W SNR >= 5, F090W SNR <= 2, and (max(blue,0)+2 sigma)/red < 0.05.

GS-MEDIUM-HST: joint valid pixel-centre area **0.962808 arcmin²**.
This is not an aperture-safe or completeness-weighted survey area.

Matched apertures retain filter-dependent PSFs and diagonal uncertainties.
Empirical correlated-noise and aperture corrections must be assessed separately.
Single-exposure i2d images remain single exposures; full spatial extent does not
mean an observation-level deep mosaic or independent repeat confirmation.
No redshift, galaxy abundance, contamination fraction or discovery is inferred.
