# SMACS empirical tails, covariance and finite-PSF controls

This executed continuation uses the three selected original SMACS products and
the frozen 1,267-proposal matched-quadrant catalogue. It does not establish a
source identity, high redshift, contamination rate, completeness or discovery.
The compact evidence is
[`smacs_empirical_imaging_controls.json`](../research_output/smacs_empirical_imaging_controls.json).

## Observed sky and conditional tail uncertainty

The aperture-minus-mean-native-annulus operator is exactly the frozen spherical
pixel-centre geometry: science radius 0.188731151502 arcsec and annulus
0.377462303004–0.629103838340 arcsec. Additional 0.125820767668 and
0.314551919170 arcsec radii share that annulus. A seed-731 translated grid has
disjoint largest aperture/annulus supports. All support pixels must have finite
SCI, positive finite ERR/WHT and avoid the source mask; nonzero DQ is excluded
where present. There is no clipping of aperture fluxes after sampling.

The primary positive-source mask uses 3-sigma connected smoothed sources with
minimum five pixels and dilation protecting the largest diagnostic aperture.
A second mask unions positive and negative source masks. Both masks condition
the distribution being sampled; the symmetric mask can remove real noise
extremes, so it is a sensitivity case, not a preferred estimate of true tails.

| Band | Disjoint blanks | Robust sky/diagonal ERR factor | Conditional spatial-block 95% | Ordinary normalized sigma |
|---|---:|---:|---:|---:|
| F090W | 729 | 1.183548 | 1.080602–1.351275 | 1.655475 |
| F200W | 647 | 1.285443 | 1.182611–1.379847 | 1.882287 |
| F444W | 2,463 | 0.937894 | 0.894036–0.978576 | 0.983079 |

The factors describe this empty-sky estimator and ERR baseline. They do not
separate drizzle covariance, residual backgrounds, confusion or flat errors,
and must not become a universal multiplier of a bright source's Poisson error.
The below-unity F444W factor does **not** establish uncorrelated pixels.

Tail counts use a median and MAD calibrated on the opposite checkerboard of
128-pixel spatial blocks. Each aperture is held out from its scale estimate;
the source mask is still determined from the full image. Disjoint supports and
checkerboard separation do not remove long-range correlations.

| Band | Held-out +3 / −3 sigma | +4 / −4 sigma | +5 / −5 sigma | Nominal +5-sigma probability upper bound |
|---|---:|---:|---:|---:|
| F090W | 0 / 2 | 0 / 1 | 0 / 1 | 0.005047 |
| F200W | 1 / 2 | 1 / 1 | 0 / 1 | 0.005685 |
| F444W | 9 / 8 | 2 / 2 | 0 / 1 | 0.001497 |

Bounds are two-sided Clopper–Pearson 95% intervals under an additional independent
Bernoulli assumption, explicitly not a proved confidence guarantee for spatial
sky. The Gaussian one-sided 5-sigma reference is 2.87e-7; even zero positive
5-sigma events provides no calibration at that probability. A MAD core width
cannot certify the tails. Symmetric masking gives zero signed 5-sigma events in
all bands, showing why mask-conditioned zero counts cannot certify noise truth.

## Measured pixel covariance and aperture dependence

Ordinary products of ERR-normalized off-source residuals, after subtracting
separate means in 128×128-pixel blocks, show adjacent horizontal/vertical
zero-lag-normalized covariances of 0.502/0.489 (F090W), 0.524/0.514 (F200W), and
0.692/0.692 (F444W). These are actual selected-sky second moments, with millions
of overlapping pairs, not millions of independent trials. They retain residual
structure/confusion and do not identify a stationary drizzle kernel.

At radii 0.125821 / 0.188731 / 0.314552 arcsec, the primary robust factors are
1.186 / 1.184 / 1.304 (F090W), 1.207 / 1.285 / 1.469 (F200W), and
0.884 / 0.938 / 1.012 (F444W). The dependence on the complete aperture/background
operator rejects transfer of a single pixel-noise or field-wide multiplier
without matched geometry and inputs. Empirical aperture covariance and local
pixel covariance are complementary diagnostics; neither isolates source noise.

## Independent operator control from mirrored images

Blind negative F444W segmentation uses the production 3-sigma threshold,
nine-pixel minimum, deblending and 16-pixel border. All three bands are sign
reversed before the same angular photometry and physical blue/red screen.
This finds **15 negative proposals**, of which five are jointly testable and
ten lack required-band coverage. **Zero of the five passes** the screen.

This is an independently signed detector/operator control on the same pixels.
It does not supply independent exposures, a zero contamination rate, a bound
on all artifacts, or evidence that the positive ten are astrophysical objects.
Actual objects and backgrounds make the sign distributions asymmetric.

## Raw-survivor noise and finite-PSF sensitivity

The frozen baseline replays exactly: 1,267 proposals, 940 untestable,
317 valid screen failures and ten raw survivors. Applying the empirical median
sky factors as a **total-error sensitivity scenario** gives nine survivors,
318 failures and the same 940 untestable. Source **152** loses the blue-limit
criterion: its 2-sigma F090W/F444W limit is 0.054661 rather than below 0.05.
Its adjusted red aperture SNR remains 7.949. Source 1043 remains a photometric
screen survivor, with red SNR 173.213 and blue SNR −5.283; its strongly negative
blue flux motivates independent background/crowding tests rather than identity.

Pinned finite JADES GOODS-S point-source PSFs are then transported to SMACS
as an explicitly uncalibrated field-transfer assumption. At the actual ten
positions, median total/aperture multipliers are 1.217549, 1.206977 and
1.428782 for F090W/F200W/F444W. Changing the template angular width by factors
0.9, 1.0 and 1.1, with flux-conserving overlap integration and the same annulus,
leaves all ten original candidates passing in each point-PSF-plus-noise case.
This restores 152 conditionally through differential aperture response; it
does not override the independently observed repeat-image evidence.

These PSF scenarios evaluate the **original ten only**. Other proposals are not
PSF modeled, so the result is not a new population count. The three widths are
nuisance choices, not statistical confidence bounds, and none is a measured
SMACS star or an extended galaxy's total-flux correction.

## Reproduce and validate

Input SHA256 values are frozen in the catalogue receipts and verified anew:

| Band | Original product | SHA256 |
|---|---|---|
| F090W | jw02736001001_02101_00004_nrca1_i2d.fits | fb3929f8470dd5e012e66fd19868e32d9154f0a7a7b572fc6c66a0fd2badaefc |
| F200W | jw02736001001_02105_00004_nrca1_i2d.fits | 45020ba0b16a8819cafbcd7a2b9d5af8672c8cb13ab71c5896947f04775cef38 |
| F444W | jw02736001001_02105_00004_nrcalong_i2d.fits | 0226bb8a980aa2770bb6e57e0f91812bbbe247358f0ae80611a788a5827e1b92 |

The CLI verifies all manifest entries, frozen catalogue/metadata hashes and
exact selected product identities. It accepts portable relocated cache paths;
altered bytes and duplicate selected products fail closed. No new imaging was
downloaded for this experiment. Large blank-sample arrays stay outside git;
their deterministic JSON hash is retained in the compact result.

```bash
python -m discovery.empirical_imaging_controls \
  /path/to/images_manifest_matched_smacs.json \
  research_output/smacs_matched_image_rerun \
  --short-psf /path/to/verified/f090w-and-f200w-models \
  --long-psf data_sources/pilot \
  --output research_output/smacs_empirical_imaging_controls.json \
  --full-output /external/cache/smacs_empirical_blank_samples.json
python -m pytest -q tests/test_empirical_imaging_controls.py \
  runner/tests/test_psf_noise.py runner/tests/test_native_psf.py \
  tests/test_adversarial_noise_controls.py
```

The F090W/F200W PSFs can be provisioned with `discovery.native_psf fetch`;
their exact URLs/hashes are in `data_sources/native_psf_products.json`.
The original-image inventory is
`data_sources/original_images_round3_matched_smacs.json`.
Tests include signed heavy tails, zero-event finite-sample bounds, empty folds,
known white/positive/negative neighbor covariance, portable identity guards,
and a blind synthetic negative-source screen. Synthetic success tests code,
not faint observed-source completeness or Gaussian-sky assumptions.

Next work is independent same-filter repeat vetting, background/morphology
dissection of the persistent 1043 patch, deep multiband modeling, and real
source injections across independent visits. The observed negative extremes,
source-mask sensitivity and insufficient 5-sigma tail resolution remain
explicit calibration limitations.
