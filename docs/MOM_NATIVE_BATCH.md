# Nine native MoM-z14 exposures and competing numerical benchmarks

Follow-up to the merged compact-input/deep-reference comparison. An expanded
600 MiB public-data ceiling allowed acquisition of the eight remaining official
calibrated exposures, resolving the original data-volume dependency directly.

## Actual native data acquired

All nine exposure names derive from the identity-verified DAWN spectrum's
SLITS metadata, then each official archive `_cal` product was HEAD-verified
before streaming. Each original is 51,563,520 bytes: **464,135,040 bytes total**
(442.63 MiB), including the original already acquired in the earlier pilot.
The additional eight consumed 412,571,520 bytes. The full literature/data input
acquisition across both batches totals **470,088,034 bytes**, counting originals
once. No paid access, provider keys or proprietary observations were needed.

Each target slit identifies source 277193 at the published coordinates and
preserves 28×423 SCI/ERR/DQ/WAVELENGTH pixels, variance and pathloss arrays.
Official calibration 2.0.1 / `jwst_1535.pmap` treats the source as EXTENDED.
Three nod positions occur in each of three groups, with total metadata exposure
time **15,756.003 seconds**. Raw originals and compact derivatives remain outside
git; the tracked [inventory](../data_sources/followup/mom_native_inventory.json)
and [report](../research_output/mom_native_batch.json) pin their hashes, byte
counts, identity and exact derivation.

At fixed z=14.44, full-slit windows within ±3,500 km/s of N IV], C IV,
He II+O III], N III] and C III] contain respectively **59, 64, 75, 85 and 95**
pixels per exposure. All of these pixels have finite science/wavelength,
positive finite ERR, and neither DO_NOT_USE nor SATURATED, in every exposure.
The large whole-slit bad-pixel denominator from the first exposure is therefore
not evidence that the nominal UV-line windows themselves require those masks.

This is a quality-control result, not a detection or abundance inference. It is
not restricted to the source trace and does not measure local background bias,
pathloss accuracy, row covariance, or extraction sensitivity. Shared reference
and background choices can correlate nods. The official EXTENDED processing and
DAWN point-source correction are distinct reductions of the same observations.

```bash
python -m data_pipeline.mom_native_batch \
  --spectrum data_sources/pilot/mom_z14_dja_v4.spec.fits \
  --output /tmp/mom-native --report /tmp/mom-native-batch.json
```

Inputs must match the tracked inventory including caches with their own valid
receipts. The batch refuses changed sizes/hashes or mismatched SLITS names and
coordinates. Per-file streams have a 64 MiB cap; preflight aggregate bytes must
fit the declared 600 MiB maximum before any new full download. A changed public
calibration requires a separately documented version and new inventory.

The next fitting experiment should compare three nod-position coadds and three
group subsets on native grids, with source-trace and independent background
apertures, explicit EXTENDED-to-point treatment and empirically estimated shared
noise. This enables an extraction test rather than merely another aperture on
the already resampled 2D spectrum. Individual 1,750.667 s exposures are shallow;
failure to detect a line in one exposure does not refute a joint-stack detection.

## Numerical rotating-star alternative

[Nandal et al. 2024, arXiv:2405.11235v1](https://arxiv.org/html/2405.11235v1)
Table 2 is now available as a [24-row numerical derivative](../data_sources/followup/nandal_rotating_mixed_ism_v1.csv)
with primary-HTML receipt. It has four IMF/ejection prescriptions and six initial
metallicities. Preserve raw table cells alongside conservative N/C endpoint
envelopes computed as log(N/C)=log(N/O)−log(C/O). The same paper's solar values
give log(N/C)⊙=−0.63, which is an explicit conversion assumption.

For its Z=10⁻⁵, top-heavy, above-remnant scenario, log(N/O)=−0.38 and
log(C/O)=−0.51 give **[N/C]=+0.76 dex**. For its Z=0, Salpeter,
above-remnant scenario, −0.55 and −0.20 give **[N/C]=+0.28 dex**. These
scenario benchmarks lie within the broad quoted MoM-z14 v2 [N/C] interval
0.27–1.19 dex under that solar conversion. They show why a broad nitrogen
enhancement alone cannot uniquely identify supermassive-star pollution.

This is a conditional comparison of model predictions, not statistical model
selection. Table 2's dilution factors are constrained to GN-z11's oxygen range
(roughly 12+log(O/H)=7.62–8.00); they were not fit to MoM-z14. The table is
mixed-ISM predictions rather than a raw stellar-yield grid, and model ranges
are not posterior errors. Rotation, incomplete stellar evolution, IMF, remnant
mass cuts, element retention and dilution remain assumptions. In particular,
the paper's prose and table C/O values should not be silently harmonized: the
exact tabulated values, with version provenance, are retained here.

```bash
python -m data_pipeline.rotating_benchmarks \
  --input /tmp/jwst-followup/nandal_2405.11235v1.html \
  --output /tmp/nandal-mixed-ism.csv
```

Actual chemistry discrimination requires tighter N/C, independent oxygen and
density constraints, time-resolved enrichment/retention predictions, and fits
under each mechanism's physical priors. No stellar population has been identified.
