# Original-image calibrated photometry rerun

Execution status: **executed**. Input manifest SHA256: `cd8e9635a6bb2b9d91cf65fba37cd079d6e8947bb55b25a6474bd6245a2f6940`.

Historical catalogs are preserved. Input bytes are verified before analysis.
The existing Universe Table, WCS anchor selection, source detector, calibrated
matched-angular-aperture photometry and physical candidate audit are used.

- Detections: 1267
- Exploratory measured proposals: 1267
- Untestable proposals: 1267
- Valid proposals failing the configured dropout cut: 0
- Proposals surviving the dropout screen: 0

The morphology classifier is frozen and is not applied to this science selection.
Selection requires all three covered calibrated bands, matched angular apertures,
F444W SNR >= 5, F090W SNR <= 2, and (max(blue,0)+2 sigma)/red < 0.05.

SMACS-J0723.3-7327: joint valid pixel-centre area **0.000000 arcmin²**.
This is not an aperture-safe or completeness-weighted survey area.

Matched apertures retain filter-dependent PSFs and diagonal uncertainties.
Empirical correlated-noise and aperture corrections must be assessed separately.
Single-exposure i2d images remain single exposures; full spatial extent does not
mean an observation-level deep mosaic or independent repeat confirmation.
No redshift, galaxy abundance, contamination fraction or discovery is inferred.
