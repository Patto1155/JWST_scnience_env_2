# Calibrated image aperture photometry

`tools.jwst.photometry.extract_photometry` measures a 2D SCI image. It retains
raw aperture sums, but never supplies an invented magnitude zeropoint. A raw
surface-brightness sum is **not** a flux density and cannot be compared between
filters on different pixel grids.

## Physical calibration

The SCI `BUNIT` is read from the SCI header first, then the primary header.
Astropy parses the unit, preserving the case distinction between MJy and mJy.

- Flux density units convertible to Jy or Jy/pixel: sum values converted to Jy.
- Surface brightness units convertible to Jy/sr: integrate each value times its
  pixel solid angle in steradians. MJy/sr introduces a factor of `1e6`.
- Pixel solid angles use the **current celestial image WCS**, evaluated at the
  four corners of each aperture pixel and integrated as two spherical triangles.
  This respects the resampled grid, rotation, local projection and FITS SIP
  distortions. Pixel corners are at centre coordinates plus/minus half a pixel.
- With no celestial WCS, a positive finite `PIXAR_SR`, or `PIXAR_A2` converted to
  steradians, is an explicit average-area fallback. The result records its
  source; the fallback is only as reliable as that product's metadata. If a
  supplied celestial WCS gives invalid areas, metadata does not override it.
- Unknown/missing BUNIT, DN/s, or missing/invalid required area produces `None`
  physical values and a failure `calibration_status`. Count-rate calibration
  requires the applicable instrument/filter/reference files; it is not guessed.
- Positive Jy flux densities map to `m_AB = -2.5 log10(f_Jy / 3631)`. Signed
  fluxes remain signed; nonpositive fluxes have no logarithmic magnitude.

Official provenance, checked 2026-10-09:

1. [STScI JWST photom step](https://jwst-pipeline.readthedocs.io/en/latest/jwst/photom/main.html):
   SCI and ERR units are changed together by calibration; PIXAR_SR/A2 describe
   average pixel area. Calibrated imaging normally contains MJy/sr.
2. [STScI resample arguments](https://jwst-pipeline.readthedocs.io/en/latest/jwst/resample/arguments.html):
   output pixel scale can differ from detector scale; output-WCS pixel area
   informs PIXAR_SR/A2. A nominal NIRCam detector scale is insufficient for
   an arbitrary resampled mosaic.
3. [Astropy AB flux units](https://docs.astropy.org/en/stable/units/logarithmic_units.html):
   flux-density magnitudes are logarithmic physical units, not instrumental
   counts with a universal arbitrary zeropoint.

## Matched sky apertures

For different filters, use the same sky centre and angular radii:

```python
measurement = extract_photometry(
    image_data=registered_dataset,
    ra_deg=53.0,
    dec_deg=-28.0,
    aperture_radius_arcsec=0.3,
    background_annulus_inner_radius_arcsec=0.5,
    background_annulus_outer_radius_arcsec=0.8,
    strict_data=True,
)
```

A celestial WCS is required. Pixel centres are selected by their actual angular
separation from the requested centre. The projected angular boundary determines
an enclosing image window. The same angular aperture can also be centred on
explicit `x,y`. Do not specify both pixel and sky coordinates. When angular
annulus radii are omitted, defaults are 1.2 and 2 times the angular aperture.
The old pixel-radius parameters remain available for diagnostics but do not
by themselves define matched apertures on different grids.

This matches geometrical apertures only. It does **not** match filter PSFs,
apply encircled-energy/aperture corrections, or fit total galaxy fluxes. Pixel
centre membership also introduces discretization error for small apertures.
Colours must use calibrated fluxes plus appropriate PSF treatment before being
interpreted as astrophysical spectral features.

## Returned fields and scientific gates

| Fields | Meaning |
| --- | --- |
| `flux`, `background_subtracted_flux`, `flux_error`, `raw_flux_unit` | Raw SCI sums and diagonal uncertainty in the input unit; retained for diagnostics. |
| `flux_jy`, `background_subtracted_flux_jy`, `flux_error_jy` | Calibrated aperture flux densities and diagonal uncertainty; `None` when not calibratable/measurable. |
| `magnitude`, `background_subtracted_magnitude`, `magnitude_system` | Actual AB magnitudes of positive calibrated fluxes; never zeropoint-25 magnitudes. |
| `calibration_status` | `calibrated`, `missing_bunit`, `unsupported_bunit`, `missing_pixel_area`, `invalid_pixel_area`, or `invalid_wcs_pixel_area`. |
| `measurement_status` | `measured`, `partial_coverage`, `off_image`, or `no_valid_pixels`. |
| `background_status` | `measured` or `missing_annulus`; absent background is never replaced with zero. |
| `coverage_fraction` | Valid aperture pixels divided by the full aperture, including positions beyond image edges. |
| `pixel_area_source`, `mean_pixel_area_sr` | Actual WCS-corner integration or named metadata fallback. |
| `uncertainty_method`, `uncertainty_assumptions`, `snr_basis` | Explicit noise estimate and limits; SNR uses Jy when calibrated, raw units otherwise. |
| `*_radius_arcsec` | Actual angular radii, or `None` for a pixel-radius measurement. |

A genuinely measured zero is `0.0`; an off-image or all-masked aperture is `None`
with an unmeasured status. A negative background-subtracted flux is a valid
measurement, not an unobserved band. Consumers must never coerce unmeasured
values to zero before proposing a dropout or taking a logarithm.

## Error model and limitations

For independent pixels, the variance of a background-subtracted flux density is

`sum_ap((c_i sigma_i)^2) + (sum_ap(c_i))^2 * variance(mean_annulus)`.

Here `c_i` converts each pixel's raw unit to Jy. With ERR, the background mean
variance is `sum_ann(sigma_i^2) / N_ann^2`; annulus scatter is **not** added again
as a second source-noise term. Without ERR, sample annulus variance estimates
both the per-pixel noise and background mean variance. Invalid ERR pixels yield
an explicitly unavailable uncertainty rather than being ignored by `nansum`.
Absent annulus or zero estimated noise gives no SNR. WHT is used only for valid
coverage; it is not assumed to be inverse variance.

Drizzle introduces covariance which ERR alone does not encode. These errors
are therefore explicitly **diagonal** estimates. Background gradients,
contamination, correlated noise, PSF corrections, and absolute calibration
systematics require further modelling/empty-aperture validation. No finite
reported SNR alone establishes a galaxy detection.

## Validation

`runner/tests/test_calibrated_photometry.py` contains synthetic FITS/WCS controls,
not observations. Tests cover unit conversions, missing calibration, primary
metadata fallback, stale detector area vs actual WCS, flux invariance across
two grids with a common sky aperture, diagonal variance propagation, empirical
noise, missing/off-image/zero distinctions, edge coverage, loader metadata, and
spherical pixel areas across RA zero near the celestial pole.
