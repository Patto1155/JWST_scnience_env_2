# Reproduce the external modeled-PSF stress diagnostic

Acquire three official JADES DR5 modeled PSFs using the versioned source
inventory (the acquisition CLI writes adjacent SHA-256 receipts). About 5.4 MB
total, bounded to 5 MB per download:

```bash
python -m data_pipeline.research_sources fetch --source jades-dr5-psf \
  --product f277wa --output data_sources/pilot/f277wa_v5.0_mpsf.fits
python -m data_pipeline.research_sources fetch --source jades-dr5-psf \
  --product f356wa --output data_sources/pilot/f356wa_v5.0_mpsf.fits
python -m data_pipeline.research_sources fetch --source jades-dr5-psf \
  --product f444wa --output data_sources/pilot/f444wa_v5.0_mpsf.fits
python -m discovery.external_psf_stress --psf-directory data_sources/pilot
```

Already acquired files are reused without a new network request. The experiment
checks their receipt hashes, sizes and FITS filter labels. It interprets arrays
as PSF shape kernels regardless of inherited BUNIT metadata. Flux-conserving
pixel-overlap integration resamples the measured input scale to 0.063 arcsec/pixel
to match the frozen classifier's long-wave scale assumption. A 61-pixel crop is
then normalized; retained flux fractions are saved so discarded wings are visible.

The independent generator convolves the PSF with a Gaussian intrinsic profile,
instead of reusing the existing empirical-PSF/Sersic source renderer. A
diffraction-width analytic Gaussian PSF is a comparator, **not** the existing
training generator. Both receive paired positions and noise per experiment cell.
The real segmentation/morphology and frozen artifact classifier run on those
synthetic images. Source placement is separated, detector matches are unique,
and every injected trial remains in the denominator, including missed sources.

The bounded default grid has 3 filters, 2 kernel types, 4 fluxes, 3 intrinsic
half-light radii, and 2 batches of 16 injections: 2,304 trials. Flux means total
normalized-kernel flux relative to one pixel's Gaussian background-noise sigma;
it is not a measured S/N or calibrated magnitude. Outputs contain raw trial
outcomes, Wilson intervals, model SHA-256, PSF URLs/checksums and all parameters.
No threshold is refitted. Null classifications remain unknown.

This tests sensitivity to renderer/kernel assumptions. It does **not** validate
recovery in JADES mosaics, astrophysical source truth, artifact recall, or survey
completeness. Training PSF provenance is incomplete, so the external template
origin does not prove disjoint training/validation PSFs. Noise is uncorrelated
and synthetic, no artifacts or crowding are injected, and sources lack shot
noise. Trial intervals are conditional diagnostic summaries; shared backgrounds
and estimated segmentation thresholds limit binomial independence. Centers lie
on integer pixels; subpixel-phase sensitivity remains untested. Resampled PSF
centroid offsets are recorded, with no hidden recentering step.
