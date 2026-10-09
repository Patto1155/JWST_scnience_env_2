# Imaging follow-up: joint coverage and conditional selection

These experiments build on the merged verified original-image rerun, retaining
all 1,134 GOODS-S proposal denominators. No source identity, redshift, galaxy
abundance or discovery is inferred from the photometric screen.

## Noise and unresolved-source PSF sensitivity

Input CSV/metadata hashes, original science-image hashes, angular radius and
annulus must agree before noise or PSF factors can transfer. The modeled PSF
uses the same binary pixel-centre angular operator and native source phases.
Flux and its uncertainty are multiplied together by a point-source correction.
Missing measurements remain missing. Extended galaxies need a morphology model;
the point-source scenarios do not establish that the objects are unresolved.

| Scenario | Untestable | Fail screen | Pass screen |
| --- | ---: | ---: | ---: |
| Original diagonal errors | 891 | 236 | 7 |
| Empirical median sky-noise factors | 891 | 237 | 6 |
| Unresolved PSF model, original diagonal errors | 891 | 235 | 8 |
| Unresolved PSF model and empirical median noise | 891 | 236 | 7 |

The median empirical factors are 1.576348 in F090W, 1.451524 in F200W and
1.047564 in F444W. These are conditional empty-sky measurements, including
background/confusion as well as covariance; multiplying every total source
error is a sensitivity experiment, not a validated Poisson-noise replacement.
Eight combinations of the per-band spatial-block bootstrap endpoints all give
six survivors without point corrections and seven with point corrections.
They are sensitivity cases, not a joint posterior or simultaneous confidence bound.

Object membership changes even when totals agree. Source 336 fails the blue
limit under median noise. Point-only correction promotes 46; point correction
with median noise promotes 254 while losing 336. Under point-model bootstrap
endpoint cases, the final member switches between 336 and 254. Thus a count
of seven does not imply a stable seven-object population. The independent
F444W dither experiment tests these entrants as well as the original seven.

The configured selection is **F090W/F444W plus F200W measurement coverage**.
It has no F200W colour or redshift criterion. This is a proposal screen, not
a photometric-redshift likelihood or a clean high-redshift sample.

## Continuum checks and JADES catalogue crossmatch

Original survivors plus explicitly nominated entrants 46 and 254 were measured
at the same sky positions and matched aperture/annulus in two F277W and two
F356W images. Signed fluxes and diagonal uncertainties are preserved. These
cross-band measurements are independent of the F444W repeat result.

| GOODS source | F277W SNR, two epochs | F356W SNR, two epochs | Latest-visit frequency slope alpha |
| --- | --- | --- | --- |
| 98 | 84.76, 89.43 | 139.28, 171.94 | -3.504 ± 0.050 |
| 254 | 114.02, 112.68 | 109.56, 108.43 | -0.304 ± 0.051 |
| 46 | 2.01, 2.66 | 9.65, 14.83 | Not estimated |

Slopes use `f_nu proportional to nu^alpha` and nominal filter-label wavelengths,
not filter-integrated SED fitting. Errors assume independent diagonal noise;
PSF, calibration, covariance and extraction systematics are excluded. Relative
to an F277W/F356W power-law extrapolation, the uncorrected F444W flux is 25.15%
lower for 98 and 2.05% lower for 254. These are curvature diagnostics, not
significant rejections of an astrophysical model. Source 46 lacks a >=3-sigma
F277W continuum measurement; no logarithmic slope is invented.

The complete pinned JADES DR4 observation-coordinate transform contains 5,190
observations, including all quality flags. None of 98, 254 or 46 has an
observation within 0.3 or 0.5 arcsec. Their nearest A/B observations are
13.515, 24.761 and 10.880 arcsec away, respectively; **these are not
associations and supply no redshift**. Targeted spectroscopy is incomplete.
Absent matches do not establish previously unknown objects. Repeated catalogue
rows are observations, not automatically distinct galaxies.

## SMACS quadrant experiment

The three original SMACS products pair F090W NRCA1 with F200W NRCA4. Each
short-wave image overlaps F444W, but their common valid sky is zero:
1,267 detections yield 1,267 untestable proposals. This is preserved as a
negative control, not converted into a measured astrophysical null result.

An accessible original F200W NRCA1 product was subsequently acquired and verified.
The repaired selector chooses required-band pairs by bounded deterministic joint
WCS/valid-pixel coverage, resolving the greedy separate-overlap failure.
No detector or field name is hardcoded into that choice.

The same 1,267 F444W detections now yield 940 untestable proposals, 317 valid
screen failures and 10 uncorrected screen survivors. There are 329 positions
with both blue/mid coverage, of which 327 are fully testable. Joint valid
pixel-centre area is **1.064573 arcmin²**. This is not an aperture-safe,
completeness-weighted area or a survey volume. SMACS calibration is CAL_VER
2.0.1; GOODS-S is 3.0.0. GOODS noise/PSF factors are not transferred to SMACS.
These single-exposure survivors need field-specific noise, PSF and repeat/deep
image validation; no astrophysical identity is asserted.

## Reproduce

```bash
python -m discovery.photometry_sensitivity \
  research_output/original_image_rerun research_output/psf_noise.json \
  --psf-report research_output/native_psf.json \
  --phase-csv research_output/native_psf_source_phases.csv \
  --output /tmp/photometry-sensitivity.json
python -m discovery.survivor_continuum \
  research_output/original_image_rerun data/original_round2/images_manifest.json \
  data_sources/pilot/jades_dr4_reference.csv \
  --extra-source-ids 46 254 --output /tmp/survivor-continuum.json
```

For the SMACS comparison, filter the verified original round-three image
manifest to `target == "SMACS-J0723.3-7327"`. The twelve-product negative
control has three SMACS images; the matched thirteen-product manifest adds
the same-field F200W NRCA1 alternative. Run `discovery.image_photometry_rerun`
on each manifest with separate output directories. Compact CSVs, metadata,
hash receipts and replay checks preserve both results without committing large
raw proposal catalogs. Reproduction still requires provisioning the exact
hash-pinned images for a fresh measurement rather than a saved-record replay.
