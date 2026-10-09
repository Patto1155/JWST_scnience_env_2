# Independent scientific review and exact-noise controls

9 October 2026. Starting baseline: `docs/TAKEOVER_STATUS.md` and merged
research protocol at `695c8e1`. This review distinguishes numerical
reproducibility from independent observational truth. No discovery is certified.

The later [follow-up review](ADVERSARIAL_FOLLOWUP_REVIEW.md) updates this dated
scope: F090W/F200W PSFs, the frozen seven-proposal repeat screen, and all nine
native MoM exposures have since been acquired or tested. The recommendations
below are the first-round state, not claims of continuing archive blockers.

## Reviewed scope

| Work | Inspected revision or frozen artifact | Outcome |
|---|---|---|
| PSF/background noise | merged PR #15, `a042b20`; complete local output and compact tracked summary | Operator, covariance signs, calibration and finite-template normalization inspected; 16 controls pass |
| Original astrometry | specialist `c1024ae` | 4 controls pass; reported catalog offsets retain sparse-reference and shared-frame limitations |
| Calibrated photometry | specialist `aa65615` | 6 controls pass; proposals, untestable measurements and screen survivors stay separate |
| Real-source validation | specialist real-validation implementation and saved M92/JADES results | 7 controls pass; ambiguous matches remain unknown; repeated observations stay grouped |
| MoM-z14 spectroscopy | specialist `ebf542f`, actual spectrum SHA256 `42d95d348ebb55ca37eb31393b4603628ac13a4bca1f4f7f0ffba7b32d3125b1` | 9 new and 8 baseline controls pass; independent solver and unit checks below |
| Enrichment | specialist `888e0c4` | 13 controls pass; elemental bookkeeping and conditional clock definitions inspected |

These are per-component checks on the reviewed scientific revisions; they are
not a declaration that every later integrated commit or every original archived
exposure has been rerun. Root integration runs the combined gate separately.

## Actual-spectrum independent calculation

Astropy's spectral-density equivalency independently verifies the conversion
from µJy to the model's flux-density unit (10⁻²⁰ erg s⁻¹ cm⁻² µm⁻¹). It agrees
with `2.99792458e5 / wavelength_um²` to 6.7×10⁻¹⁶ relative precision.

A direct weighted SVD solve, using the same explicitly declared continuum and
bin-integrated templates but a different numerical solver, reproduces the
stored diagonal-covariance fit to **73 actual FITS bins**:

| Quantity | Independently recomputed value |
|---|---:|
| χ² / degrees of freedom | 89.990717 / 66 |
| N IV] integrated flux | 53.779761 |
| C IV integrated flux | 37.294782 |
| He II + O III] integrated flux | 32.579646 |
| N III] integrated flux | 13.763074 |
| C III] integrated flux | 27.684946 |

Flux units are 10⁻²⁰ erg s⁻¹ cm⁻². Maximum solver differences are 7.1×10⁻¹⁴
for flux and 2.9×10⁻¹³ for covariance entries. Direct masked inverse-variance
re-extraction from actual SCI/WHT/PROFILE reproduces the ±3-pixel optimal flux
to 5.6×10⁻¹⁷ µJy and its diagonal errors exactly.

This validates units and linear numerical operations, **not** the Gaussian
source LSF, profile accuracy, reduction quality, covariance or physical line
emissivities. The alternative extractions reuse the same exposures. The signed
five-group redshift scan includes its stated z/width search in a Gaussian null,
but not prior source/line selection, uncertain LSF or reduction systematics.
Its 1,000 null trials do not justify a probability smaller than their resolution.
Fieller uncertainty retains an unbounded set when the carbon denominator is
too weak; a nitrogen/carbon line-flux ratio is not elemental N/C.

## New independent stochastic oracle

`discovery/adversarial_noise_controls.py` challenges the empirical noise method
against a covariance model with an exactly computable variance. If independent
unit Gaussian pixels are convolved by a finite kernel K, and measured by the
signed aperture-minus-annulus operator A, the true variance is the squared norm
of their composed convolution. This calculation uses a separately constructed
operator; it does not infer its expected answer from the method's own report.

All trials use a 0.189-arcsec pixel-center aperture, 0.063-arcsec pixels,
annulus factors 2–10/3, an explicitly empty source mask, and unit marginal pixel
errors. Eighteen trials comprise six seeded 768×768 images for each kernel:

| Known noise model | Exact empirical/diagonal σ | Measured robust range | Block intervals containing exact value |
|---|---:|---:|---:|
| Independent white noise | 1.000000 | 1.005805–1.059705 | 5/6 |
| Positive neighbor covariance, separable [1,2,1] kernel | 2.291304 | 2.239759–2.433794 | 6/6 |
| Negative neighbor covariance, separable [-1,2,-1] kernel | 0.379363 | 0.351343–0.397641 | 6/6 |

Kernel normalization preserves unit marginal pixel variance. These examples
reject the claim that off-diagonal covariance must always inflate aperture
noise. A spatially constant noise mode cancels exactly because A sums to zero.
Three focused tests verify white-noise identity, uniform-mode cancellation, and
empirical agreement with both inflation and deflation counterexamples.

Six realizations do not calibrate nominal 95% coverage. One new white-control
interval misses its known value; the original PSF/noise report also has a
white-control aperture with a narrow miss. These are reminders that a bootstrap
interval is conditional on sampled spatial blocks and is not a coverage
guarantee. Actual images add source-mask selection, confusion, gradients,
heteroscedasticity and unknown large-scale covariance; this oracle does not
remove those uncertainties or permit globally rescaling source Poisson errors.

```bash
OPENBLAS_NUM_THREADS=1 python -m discovery.adversarial_noise_controls
python -m pytest -q tests/test_adversarial_noise_controls.py
```

The saved JSON retains every seed, exact value, observed value, interval and
count. This is synthetic calibration evidence, not an observed-sky result.

## Primary-source and interpretation audit

The four H/C/N/O yields were checked directly against [Nagele & Umeda v4,
Table 1](https://arxiv.org/html/2304.05013v4) and its reproduction in
[Ebihara et al. v3, Table 1](https://arxiv.org/html/2601.04344v3). They are
ejected masses; division by isotope masses is required for number ratios.
The 204- and 103-Myr total histories match [Kobayashi & Ferrara v2, Table
1](https://arxiv.org/html/2308.15583v2); a 100-Myr pause alone is not the
total formation history.

[MoM-z14 v2](https://arxiv.org/html/2505.11263v2) reports a Cue abundance
posterior and a separate stronger ionic estimate. They condition on different
physical analyses and cannot be exchanged. The yield tables assume a specified
initial stellar metallicity; arbitrary ambient metallicity changes are scenario
tests, not new self-consistent stellar evolution models.

## Claims and scenarios rejected

* **Seven confirmed high-redshift galaxies:** unsupported. The current screen
  uses F090W/F444W limits and requires covered valid F200W data, but applies no
  F200W color criterion localizing the Lyman break. Redshift and identity remain
  unmeasured. Area is pixel-center overlap, not completeness-weighted volume.
* **Existing PSF corrections calibrate the dropout color:** unsupported. The
  current templates cover F277W/F356W/F444W, not F090W/F200W. Fractional-aperture
  response also differs from the production integer-center operator; both
  responses are retained explicitly. An extended galaxy is not a point PSF.
* **Nearly perfect clean-star retention certifies faint high-z recovery:**
  unsupported. M92's type/sharpness/crowding/SNR cull defines a clean reference
  population; full-stack catalog SNR differs from individual-exposure SNR.
  Same-visit dithers do not supply multiple independent field validations.
* **The historical 9.54-hour F277W baseline:** corrected by current EXPMID
  values to 5.64853 hours. Nonpersistence does not by itself identify artifacts;
  the historical 15% claim was not rerun on the reprocessed images.
* **The GN-z11 fiducial 204-Myr history fits a z=20 onset at MoM-z14:**
  quantitatively false under Planck18: the available budget is 104.959 Myr.
  This rejects that combined scenario, not all WR enrichment.
* **The specific 1,000-Msun yield can reach the Cue median with equal retention
  and lower-N/C gas:** false; its pure-ejecta [N/C] is only 0.767 dex.
  This is a convex-mixture bound, not a statistical rejection of all VMS.
* **Primordial dilution adjusts a polluter's metal/metal ratios:** false;
  it changes O/H but preserves N/C, N/O and C/O.
* **These data select an SMS, WR, AGN, black-hole-cosmology or dark-matter
  mechanism:** unsupported. The current uncertainties, conditional abundance
  assumptions and absent selection function do not supply model probabilities.

## Unresolved constraints and next experiments

1. Test the seven screen survivors against deep/repeat images and spectroscopic
   catalogs, then fit multi-band SEDs. Acquire blue/mid PSF templates and retain
   operator, centering, source-extension and spatial-noise sensitivity.
2. Expand held-out observed stars to independent fields and visits, and report
   recovery versus actual individual-exposure brightness/crowding. Complete the
   frozen-model training provenance before calling every test fully held out.
3. Acquire independent nod/exposure pixel tables, quality flags and a calibrated
   point-source LSF. Derive covariance from controls rather than selecting a
   favorable assumed correlation. Resolve density diagnostics and He II/O III].
4. Jointly test predicted N/C, C/O, N/O and O/H with an emissivity/ionization
   model, covariant line errors and source-specific extraction. Solving only
   N/C does not establish that a mixture fits the other abundance constraints.
5. Measure the ionized emitting gas mass and differential element retention.
   Without them, a local gas-parcel mixing budget cannot become a global
   nitrogen inventory, event count or galaxy-formation mechanism.

The retrieved originals are selected current reprocessed products, not all 26
historical products or a byte-identical replay of older reductions. The shared
limitations above remain after successful tests and checksum verification.
