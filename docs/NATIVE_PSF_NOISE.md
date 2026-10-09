# Native-grid PSF response and noise sensitivity

This experiment builds on merged PRs #15 and #16. It reuses the verified
original images and their calibrated, binary pixel-centre aperture operator.
It adds independently sourced **modeled** F090W and F200W PSFs to the existing
F444W model. None of these PSFs is a measured star in the original exposures.
No galaxy redshift, abundance, identity or population rate is inferred.

The aperture is 0.18873807945080867 arcsec and the shared background annulus
is 0.37747615890161734–0.6291269315026955 arcsec. Each model is integrated onto
its actual image grid: F090W 0.0312285081, F200W 0.0312291984 and F444W
0.0629126932 arcsec/pixel. For each measured source/band position, spherical
WCS separations define the same aperture and annulus as production photometry.
Finite SCI, positive finite WHT, explicit validity masks and image edges define
flux coverage. ERR validates uncertainty separately and does not change the
flux operator. Local Jy conversion is retained when subtracting the mean
native-unit annulus: averaging annulus Jy values would be a different operator.

Pixel-overlap integration conserves model flux without renormalizing discarded
wings. The finite supplied template defines the total. Nine fixed centring
phases measure sampling sensitivity; actual source phases are separately
measured. Nine phases are not an exhaustive bound or a statistical confidence
interval. Template axes are aligned to output pixels; field, visit, orientation,
outer-wing and PSF model uncertainties remain unquantified.

## Modeled instrumental response

The catalog SHA256 is
`aa0724bb51373a23caf87ffe5d84606077fa46213ea51e7741ff357d9dbd199d`.
There are 1,653 source/band response records. They are conditional instrumental
predictions at measured positions, not 1,653 observed stars.

| Band | Positions | Median unresolved-source total/aperture multiplier | 16–84% range over actual positions |
| --- | ---: | ---: | --- |
| F090W | 272 | 1.21713 | 1.21630–1.21814 |
| F200W | 254 | 1.20703 | 1.20674–1.20747 |
| F444W | 1,127 | 1.42867 | 1.42212–1.43658 |

The median modeled aperture-minus-total AB color is **−0.17335 mag** for
F090W−F444W and **−0.18270 mag** for F200W−F444W, on 272 and 254 matched
positions. Under an unresolved-source assumption, subtract these negative
biases to obtain a redder total color. Extended galaxies need a morphology/PSF
model; these corrections must not be silently applied to them.

Area coverage alone does not bound point-source flux loss. Source 1015 has
92.3% valid F444W aperture pixels, yet its modeled total/aperture multiplier is
1.71986 because masked pixels can contain concentrated PSF flux. Other retained
positions similarly combine sampling and coverage effects. The per-source CSV
preserves native centres, phases, operator pixel counts and modeled response;
no correction is substituted into the measured source catalog.

## Source-mask and spatial-block sensitivity

The primary mask reproduces the merged first-round noise estimate exactly:
3-sigma connected smoothed sources, with dilation protecting the largest
0.314563 arcsec diagnostic aperture. It uses 13 pixels for the short-wave
images and 7 for F444W. Fully covered aperture/annulus footprints are disjoint.
Changing the threshold or dilation admits different sky subsets.

| Band | Primary robust sigma/diagonal estimate | Range over four mask choices | Primary ordinary normalized standard deviation |
| --- | ---: | --- | ---: |
| F090W | 1.57635 | 1.39844–1.57635 | 1.40349 |
| F200W | 1.45152 | 1.41272–1.47146 | 1.30805 |
| F444W | 1.04756 | 1.04756–1.05973 | 1.48088 |

The four masks use the primary threshold/dilation; threshold 4 instead of 3;
primary dilation plus 3 pixels; and dilation protecting only the middle science
aperture. These ranges are nuisance sensitivity, not confidence intervals.
The JSON separately retains conditional block-bootstrap intervals for each
mask and primary block sizes 64, 128 and 256 pixels.

Both robust MAD and ordinary scatter are retained because the residual
background distribution is not certified Gaussian. In particular F444W's
ordinary scatter exceeds its robust estimate by about 41%. A Gaussian tail
probability cannot be inferred from a robust core width alone. The correction
combines covariance, residual confusion, background structure and calibration
residuals; it is not an identified drizzle factor. It must not multiply a
bright source's total Poisson error indiscriminately.

## Reproduce and validate

Run from the repository root after provisioning the pinned original images:

```bash
python -m discovery.native_psf fetch --psf-directory data_sources/pilot
python -m discovery.native_psf run \
  --psf-directory data_sources/pilot \
  --image-manifest data/original_round2/images_manifest.json \
  --catalog research_output/original_image_rerun/selection_measurements.csv
python -m pytest runner/tests/test_native_psf.py runner/tests/test_psf_noise.py
```

The new product inventory pins URLs, filter IDs, byte counts and hashes.
Downloads are bounded at 5 MiB each. Existing cached files must verify against
both receipts and inventory; different upstream bytes require deliberate
versioning. Receipts are committed, while the two new 1.8 MB model images are
regenerable downloads. The native response CSV is deterministic; compact noise
reports pin canonical hashes of omitted, regenerable blank-aperture arrays.

Independent Gaussian encircled-energy convergence, white/correlated noise,
physical-unit conversion, spherical geometry, coverage masks, checksum failure
and invalid template/grid controls pass. The prior production transfer check
matched 36 real blank positions in masks, Jy flux and diagonal errors. Unit
tests are synthetic controls and are labelled separately from real sky results.

Primary sources: the [JADES DR5 release](https://jades-survey.github.io/), exact
PSF product URLs and receipts in `data_sources/native_psf_products.json`, and
[STScI NIRCam PSF documentation](https://jwst-docs.stsci.edu/jwst-near-infrared-camera/nircam-performance/nircam-point-spread-functions).
STScI distinguishes individual-exposure and resampled PSFs. Its full downloadable
ASCII curves on that page are simulated individual-exposure curves; its
resampled table lists 50%/80% radii. They are not a supplied full empirical
curve for this field and are not used to manufacture a precise correction.

The highest-value next calibration is an observed-star response measured with
this exact operator across held-out visits, followed by extended-galaxy
PSF/morphology treatment and empirical tail/negative-image controls. The current
result rejects the assumption that geometric aperture matching and diagonal
ERR alone establish precision colors or calibrated faint-source tail rates.
