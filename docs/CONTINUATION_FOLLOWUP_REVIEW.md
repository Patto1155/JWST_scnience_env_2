# Independent follow-up likelihood and blue-counterpart review

9 October 2026. This extends the first continuation review without replacing its
frozen results. Reviewed changes: native reduction `378c764`, Cue `220f445`,
corrected multiband spatial model `8e65aaf`, enrichment `6455b61`. The independent
oracles reuse observed data and stated models; they are numerical and operator
checks, not additional observations or astrophysical calibration.

## Native pixels and full likelihood

The actual nine pinned CAL products independently reran. All scientific output
and derived arrays agreed exactly; the compact NPZ byte SHA256 is
`9412f52afbed589777cf55ad27ca2e93065cb4003be4990debc17503fe097027`.
Relocated filenames and a harmless metadata wording change remain distinguishable
from scientific results. The stored data have 70 columns across nine exposures:
630 correlated amplitude samples, three disjoint RATE groups, shared references.

A separate reviewer constructs block-diagonal per-column Cholesky factors and
`L (K tensor I) L^T`, then solves GLS by normal equations. The production code
uses tensor contraction and whitened QR. Native wavelength/profile/mask arrays
are independently reconstructed rather than importing the new reduction module.
All four signed five-group flux fits agree within 1.82e-13 flux units; complete
5×5 flux covariance agrees within 2.5e-13 relative. Units, correction order,
signed negative ghosts, common masks, background incidence and nonnegative
variance reconciliation were separately inspected.

The point-LSF empirical-transport line-flux ratio's 95% Fieller set admits zero
nitrogen. This is a conditional reduction/noise result; it does not establish
that the published coadd or abundance analysis is wrong. Its measured spatial
width does not calibrate dispersion-direction illumination or a source-specific
spectral LSF. Off-trace stationary noise transport, omitted spatial covariance
in that first fit, source Poisson and inter-group calibration remain assumptions.

## Photoionization and retained-yield algebra

The pinned Cue v0.1 archive regenerated its entire 2,025-point prediction and
comparison JSON exactly. A separate whitened SciPy nonnegative least-squares
optimizer fits each model's common normalization using the marginal four-group
covariance. It independently reproduces best chi² to 2.3e-16 absolute and the
illustrative threshold counts 157/126 for slit/generic-point scenarios. N IV]
is missing from the actual model, rather than assigned a fictitious zero flux.
The sparse threshold sets are not confidence regions or mechanism probabilities.
Their solar/depletion conventions and equal spectral multiplet assumptions are
explicit. Low best chi² with many free physical parameters does not identify a
polluter or validate the emulator.

Both coadd and native retained-yield outputs independently reran exactly. Another
whitened NNLS operator fits the convex cone between ambient and retained-ejecta
ratios, then profiles the unrestricted positive quadrant. It verifies all **672
actual atomic-cell/yield comparisons** to 1.5e-14 absolute deviance error: 224
coadd and 448 native cases. The generator now reconstructs every ionic vector
and covariance from its referenced spectrum/grid, rejecting self-consistent
forged downstream summaries. Stage fractions and differential retention remain
uncalibrated; the fixed-k coadd 1,000-solar-mass SMS ceiling conflict disappears
under either native empirical-noise family. No enrichment mechanism is excluded.
AGB 40/150-Myr endpoints are labelled illustrative history assumptions rather
than a new calibrated stellar-lifetime grid.

## Corrected multiband operator and new actual blue-sky experiment

Review found that the first blank-noise implementation recentered the target
while preserving a companion at its science-template position. This changed
the relative target/companion geometry for source 98. Commit `8e65aaf` preserves
the complete science design at all blank positions and adds a nonzero-offset
regression. The actual corrected seven-band run reproduces the full JSON exactly.
Its blue-counterpart evidence for source 254 is retained: 17.84 ± 0.81 nJy under
the stated spatial/background model. Source 98's structured residuals still
preclude interpreting its tiny formal errors as accurate physical total fluxes.

The reviewer independently integrates actual source-254 F090W pixels using the
recorded `10.0*nanoJansky` pixel-flux unit. Fixed 0.2-arcsec apertures are tested
against four separately specified annuli with both a mean and a weighted plane.

| Background annulus, arcsec | Mean-sky flux, nJy | Plane-sky flux, nJy | Plane diagonal error, nJy |
|---|---:|---:|---:|
| 0.4–0.6 | 19.011 | 19.012 | 1.047 |
| 0.4–0.8 | 18.780 | 18.786 | 0.996 |
| 0.6–0.8 | 18.618 | 18.626 | 1.022 |
| 0.8–1.0 | 18.468 | 18.485 | 1.008 |

All variants retain positive blue aperture signal. This rejects a no-measured-
F090W-counterpart premise at this deeper depth, without assigning a redshift.
The unmasked annuli, same source photons and diagonal WHT errors omit deblending,
correlated noise, systematic background uncertainty and morphology. These
operator variants are sensitivity scenarios, not four independent detections.

## Reproduce the independent artifacts

After the science dependencies are merged, use the locked Python environment:

```bash
python -m discovery.continuation_followup_review \
  --native-report research_output/mom_native_reduction.json \
  --native-npz research_output/mom_native_reduction.npz \
  --deep-inventory data_sources/survivor_deep/manifest.json \
  --deep-directory /cache/jwst-deep-survivors \
  --output /tmp/continuation_followup_review.json
python -m discovery.covariant_model_review cue \
  --model-input /cache/cue-v0.1.zip \
  --spectrum research_output/mom_z14_point_resolution.json \
  --comparison research_output/mom_cue_grid_fit.json \
  --output /tmp/continuation_cue_review.json
python -m discovery.covariant_model_review yield \
  --model-input research_output/mom_ionic_fit.json \
  --comparison research_output/atomic_enrichment_coadd.json \
  --output /tmp/continuation_yield_coadd_review.json
python -m discovery.covariant_model_review yield \
  --model-input research_output/mom_native_ionic_fit.json \
  --comparison research_output/atomic_enrichment_native.json \
  --output /tmp/continuation_yield_native_review.json
```

The four compact reviewer JSONs pin every supplied model/report input and retain
independent discrepancies and signed blue measurements. Raw input files stay
external. The original reduction and model reports give acquisition recipes and
physical assumptions; these audit commands do not replace those experiments.
