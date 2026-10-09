# Geometry-frozen deep-image controls

9 October 2026; continuation from master `1b4012e`. This executes an expanded
real-source recovery test using the already acquired three 24-arcsec DAWN
F444W cutouts. No new image bytes were downloaded. It does **not** establish
population completeness, contamination or native-pixel classifier retention.

## Selection before pixel outcomes

`discovery.deep_control_recovery freeze` enumerates the complete grouped JADES
DR4 A/B/C reference catalogue, then selects every source with a conservative
full valid angular footprint in the union of the three fixed cutouts. Science
amplitudes, detection outcomes and redshift never enter footprint selection.
The required margin is 16 original pixels, 1.006 arcsec, exceeding the 0.6-arcsec
photometry annulus. Each source group receives one primary cutout by maximum
valid geometry margin, then filename; overlapping images are not extra trials.
The evaluator recomputes the frozen policy and verifies pinned input hashes.

The footprint is **still targeted** at three previous high-z nonrecoveries.
Those three seeds retain a separate denominator. Eleven additional geometry
controls comprise six robust A/B low-z, three robust A/B intermediate-z, and two
C-grade other-redshift groups. There are **zero additional robust high-z controls**.
The bounded cache cannot supply that missing denominator. One reference close
to an image boundary fails the full-margin rule.

## Actual measurements

Matched 0.2-arcsec apertures use 0.4–0.6-arcsec background annuli. The original
image and deep mosaics use the same 5-sigma segmentation rule; a second deep
operator matches the original minimum connected angular area. Original pixels
are about 0.0629 arcsec and mosaic pixels 0.05 arcsec, giving eight rather than
five minimum deep pixels. This changes only the area gate: PSF, per-pixel noise,
resampling and sensitivity remain different.

| Reference stratum | Original covered/detected | Deep five-pixel detected | Deep eight-pixel detected |
|---|---:|---:|---:|
| Additional robust low-z | 4 / 3 | 6 / 6 | 6 / 5 |
| Additional robust intermediate-z | 2 / 0 | 3 / 1 | 3 / 1 |
| Additional C-grade other | 1 / 1 | 2 / 2 | 2 / 2 |
| Original robust high-z seed | 1 / 0 | 1 / 1 | 1 / 1 |
| Original C-grade high-z seeds | 1 / 0 | 2 / 1 | 2 / 1 |

The strict original full-margin policy leaves one historical covered seed
untestable in this experiment; this is a different, prespecified denominator
from the earlier aperture-only three-seed comparison. The total deep denominator
is **14 unique conservative source groups**, not fifteen image/reference rows.

The robust low-z control `goods-s-deepjwst_186837` is detected with five connected
pixels, but has no matched centroid under the eight-pixel operator despite an aperture/empirical-blank-scatter
ratio of **27.40**. The intermediate-z source `73071` has that ratio **11.41** but
has no matched centroid under either segmentation operator. These counterexamples reject the claim that
large aperture signal necessarily implies recovery by a fixed connected-pixel
detector. Segmentation, deblending or displaced centroids can cause nonrecovery;
the experiment does not assert absent source flux, identity or redshift correctness.

The earlier high-z seed results reproduce: robust seed `20189546` is detected,
C seed `20083087` is detected, and C seed `20074794` has aperture ratio **12.36**
but is undetected. Native-grid classifier rejection is not estimated because
the classifier has not been validated on resampled mosaics.

Every deep image includes the original comparison exposure. Cutout pairs share
**58, 50 and 50 native contributors**, respectively. This is a dependent depth
comparison, not independent repeat confirmation. Per-source formal diagonal
aperture uncertainties and empirical blank-sky diagnostics are in the compact
output; neither includes complete PSF, spatial-depth or source-Poisson uncertainty.
No binomial survey interval is assigned to this fixed, biased, dependent sample.

## Reproduce

Acquire the pinned inputs using the existing `data_pipeline.followup_data` and
`data_pipeline.original_images` commands documented in `FOLLOWUP_DATA.md` and
`ORIGINAL_IMAGE_PHOTOMETRY.md`. With `$DEEP` set to the follow-up directory and
`$ORIGINAL` to `jw01180026001_09201_00003_nrcalong_i2d.fits`:

```bash
python -m discovery.deep_control_recovery freeze --input "$DEEP" \
  --original "$ORIGINAL" --frozen /tmp/deep_control_frozen.json
python -m discovery.deep_control_recovery evaluate --input "$DEEP" \
  --original "$ORIGINAL" --frozen /tmp/deep_control_frozen.json \
  --output /tmp/deep_control_recovery.json
python -m pytest -q tests/test_deep_control_recovery.py \
  tests/test_real_validation.py tests/test_deep_reference_comparison.py
```

Tracked artifacts: `research_output/deep_control_frozen.json` and
`research_output/deep_control_recovery.json`. Seven new offline tests guard
fixed SCI-independent selection, overlap deduplication, seed isolation,
integer-key hash round-trips, full margin, frozen-policy tampering, explicit
denominators and the aperture-versus-connected-area counterexample. Together
with the adjacent existing tests, **15 tests pass**; focused scientific lint passes.

Next: independent uniform deep field/visit controls with additional A/B high-z
references; PSF/SED-conditioned real-background injections; explicit source
association/crowding sensitivity. A targeted spectroscopy catalogue and three
cutouts cannot become a completeness-controlled galaxy population.
