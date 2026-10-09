# PSF aperture response and empirical noise diagnostics

The PSF results use verified public **modeled** templates. Noise controls are
synthetic unless an actual-image receipt is explicitly listed. Sensitivity
ranges are not observational uncertainty confidence intervals.

## Finite-template response near a common 0.189 arcsec radius

An explicitly recorded background annulus is subtracted. These
point-source corrections do not recover total extended-galaxy flux.

| Band | Aperture EE | Net response | Total multiplier | Old 61px crop retained |
| --- | ---: | ---: | ---: | ---: |
| F277W | 0.79072 | 0.78534 | 1.27333 | 0.97972 |
| F356W | 0.74143 | 0.73490 | 1.36072 | 0.97411 |
| F444W | 0.70371 | 0.69751 | 1.43368 | 0.96908 |

## Uncorrected point-source color biases

Reported value is aperture color minus intrinsic color; subtract it to
correct the modeled unresolved-source color. The sign matters.

| Bands | Radius arcsec | Centered bias mag | Paired phase sensitivity range |
| --- | ---: | ---: | --- |
| F277W − F356W | 0.126 | -0.09656 | -0.09656 to -0.09068 |
| F277W − F356W | 0.189 | -0.07207 | -0.07494 to -0.07207 |
| F277W − F356W | 0.315 | -0.01794 | -0.01830 to -0.01794 |
| F277W − F444W | 0.126 | -0.19110 | -0.19110 to -0.17800 |
| F277W − F444W | 0.189 | -0.12877 | -0.13275 to -0.12877 |
| F277W − F444W | 0.315 | -0.04454 | -0.04484 to -0.04407 |
| F356W − F444W | 0.126 | -0.09454 | -0.09454 to -0.08673 |
| F356W − F444W | 0.189 | -0.05670 | -0.05782 to -0.05670 |
| F356W − F444W | 0.315 | -0.02660 | -0.02660 to -0.02609 |

## Noise calibration controls

| Input | Radius arcsec | Blanks | Robust empirical / diagonal sigma | Block 95% interval |
| --- | ---: | ---: | ---: | --- |
| white | 0.126 | 361 | 0.844 | 0.762–0.983 |
| white | 0.189 | 361 | 1.021 | 0.908–1.134 |
| white | 0.315 | 361 | 1.025 | 0.884–1.149 |
| 3x3 correlated | 0.126 | 361 | 2.017 | 1.721–2.227 |
| 3x3 correlated | 0.189 | 361 | 2.389 | 2.112–2.616 |
| 3x3 correlated | 0.315 | 361 | 2.615 | 2.269–2.952 |
| /workspace/scratch/232075794deb/jwst/data/original_round2/jw01180026001_09201_00003_nrcalong_i2d.fits | 0.126 | 519 | 1.001 | 0.903–1.073 |
| /workspace/scratch/232075794deb/jwst/data/original_round2/jw01180026001_09201_00003_nrcalong_i2d.fits | 0.189 | 518 | 1.048 | 0.965–1.153 |
| /workspace/scratch/232075794deb/jwst/data/original_round2/jw01180026001_09201_00003_nrcalong_i2d.fits | 0.315 | 513 | 1.005 | 0.903–1.132 |
| /workspace/scratch/232075794deb/jwst/data/original_round2/jw01180026001_03201_00003_nrca1_i2d.fits | 0.126 | 176 | 1.362 | 1.146–1.631 |
| /workspace/scratch/232075794deb/jwst/data/original_round2/jw01180026001_03201_00003_nrca1_i2d.fits | 0.189 | 176 | 1.576 | 1.328–1.804 |
| /workspace/scratch/232075794deb/jwst/data/original_round2/jw01180026001_03201_00003_nrca1_i2d.fits | 0.315 | 175 | 1.705 | 1.411–1.999 |
| /workspace/scratch/232075794deb/jwst/data/original_round2/jw01180026001_13201_00003_nrca1_i2d.fits | 0.126 | 250 | 1.155 | 1.016–1.332 |
| /workspace/scratch/232075794deb/jwst/data/original_round2/jw01180026001_13201_00003_nrca1_i2d.fits | 0.189 | 249 | 1.452 | 1.192–1.625 |
| /workspace/scratch/232075794deb/jwst/data/original_round2/jw01180026001_13201_00003_nrca1_i2d.fits | 0.315 | 249 | 1.257 | 1.034–1.494 |

The multiplier is fitted to normalized net blank fluxes, includes the
aperture–annulus covariance, and belongs to this image/mask/aperture/noise
baseline. It is not an isolated or universal drizzle factor. Disjoint
footprints avoid direct aperture overlap; spatial blocks address some
remaining dependence. Source confusion and large-scale backgrounds remain.

## Reproduce

```bash
python -m discovery.psf_noise --psf-directory data_sources/pilot --radii 0.1258253863005391 0.18873807945080864 0.31456346575134775 --annulus-radii 0.3774761589016173 0.6291269315026955 --output-scale 0.06291269315026955 --image data/original_round2/jw01180026001_09201_00003_nrcalong_i2d.fits --image data/original_round2/jw01180026001_03201_00003_nrca1_i2d.fits --image data/original_round2/jw01180026001_13201_00003_nrca1_i2d.fits
# Add --image path/to/calibrated_i2d.fits for an actual sky estimate.
```

The tracked JSON retains phase trials, aggregate covariance checks, hashes and
deterministic seeds. Its `artifact_storage` lists larger blank-trial arrays omitted
from the compact summary and pins the complete output hash. The CLI regenerates
all blank positions, diagonal errors and spatial blocks using the recorded
`command_parameters`; large regenerable outputs stay outside git. PSF modeling, field
variation, outside-template wings, source extension and absolute calibration
are not quantified by the deterministic sensitivity ranges.

Production photometry transfer: 36/36 blank positions agree in pixel masks, calibrated flux and diagonal sigma.
