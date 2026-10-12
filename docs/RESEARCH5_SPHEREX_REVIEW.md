# Independent SPHEREx QR3 photometry review

Target: VarWISE J035034.07+353508.5 / Gaia DR3 219690291611604480,
also the previously known variable DDE 54. This review concerns an independent
2026 infrared epoch, not discovery of a new source. Author and reviewer are
different agents. No GOODS-N results were opened.

Final verdict: **the frozen W1 faint-state confirmation contract is unmet**.
Reliable channels near 3.11 and 3.29 µm are bright-like under a comparable
spectral-energy-distribution assumption, but the incomplete spectrum establishes
neither a broadband W1 magnitude nor definitive failure of periodic recurrence.

## Calibration contract

The official [ePSF tutorial](https://caltech-ipac.github.io/irsa-tutorials/spherex-psf/)
describes QR3's EPSF binary table, fivefold oversampling, and nearest-zone
selection in parent detector coordinates. The pixel-convolved model is sampled
at native pixel centers with the source's subpixel phase, then normalized.
Convolving or integrating this model again would broaden it incorrectly.
The implementation is independently checked against Photutils ImagePSF.
Oversampled-array sum unity does not imply native-grid sum unity.

The official [cutout tutorial](https://caltech-ipac.github.io/irsa-tutorials/spherex-cutouts/)
uses spectral WCS key W with the complete HDUList to evaluate source wavelength
and bandwidth. Detector footprint wavelength limits and ePSF-zone CWAVE are
not substitutes for the wavelength at the source.

The official [data-product guide](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/)
specifies IMAGE in MJy/sr, VARIANCE in (MJy/sr)^2, and unsubtracted zodiacal
background. Calibration solid-angle maps contain arcsec². Here the local,
SIP-aware celestial WCS Jacobian approximates solid angle. Multiplication by
solid angle and 10^9 converts fitted MJy/sr-pixel amplitudes to mJy.
Calibration-map replacement remains a limitation, not a silent assumption.

## Independent method

`discovery/research5_spherex_review.py` does no acquisition. It reads actual
author-acquired FITS data and hashes each input. It uses original detector
coordinates (ORIGX0/Y0, or CRPIXnA), selects the nearest ePSF zone, interpolates
with an independent scipy renderer, and normalizes on complete kernel support.
Missing or masked pixels are never absorbed into the normalization.

Actual QR3 FLAGS metadata use MSKN/MSKM fields. SOURCE and FULLSAMPLE are
information bits allowed by the review; every other set flag is rejected.
The old MP bit-index convention is also supported. Rejecting all nonzero
flags would incorrectly remove this source.

The fixed-coordinate primary estimate is a variance-weighted ePSF plus constant
background within six pixels. Checks use a planar background, four-pixel
fit radius, and two-/three-pixel apertures with robust four-to-eight-pixel
annular backgrounds and ePSF enclosed-fraction correction. Additional
diagnostics allow a bounded 0.6-pixel centroid displacement and the five
nearest ePSF zones. Diagnostics do not redefine source selection.
An explicitly after-outcome reviewer quality diagnostic requires at least
85% usable PSF support and four pixels from the cutout edge. These conservative
diagnostics do not replace or relax the original confirmation contract.
Errors include full linear-fit nuisance covariance and inflate by
sqrt(max(1,reduced chi²)); they do not include full correlated noise or an
instrument calibration floor. The delivered ePSF has finite support and
unknown omitted wings. Aperture and ePSF estimates share that limitation.

## First actual exposure

The **historical untrimmed intermediate**
`research_output/research5_time_spherex_000.fits.gz` had SHA256
`7eca3dbb0865d0bbb029907627087d37efa02cf4d0641f8925880bcdb3bceced`
when first measured at the approximate query-center position. That exact
untrimmed local file was subsequently replaced with a compact five-zone file.
The historical cutout contains original acquired pixels,
the full original ePSF table, and WCS-WAVE; this is actual data, not a
simulation. The parent records HTTP Range response hashes and byte sizes.
The final acquisition receipts preserve original ePSF headers, full-table
hashes, selected original row IDs and raw-range hashes. The final published
000 gzip SHA256 is
`20b91db27fd6b03ad27333477aa99192f86865711630cb46e535bf04f922e1ee`;
its uncompressed FITS SHA256 is
`11f19691d14745ab616e7f28a240543057d7b9743a72c75f3f961bcf4cee1766`.

| Quantity | Independently measured value |
|---|---:|
| Exposure start MJD | 61269.077386667 (17 August 2026) |
| Source wavelength / width | 2.795478 / 0.079925 µm |
| Parent source x/y | 300.076706 / 1367.240786 |
| Original nearest ePSF row | 297 |
| ePSF-zone CWAVE | 2.766453 µm |
| Raw native-grid ePSF sum | 0.03959352 |
| Normalized good PSF fraction | 1.0000 |
| Local solid angle | 8.97333 × 10^-10 sr |
| Constant-background flux | 5.1477 ± 0.1456 mJy |
| Planar-background flux | 5.1472 ± 0.1466 mJy |
| Four-pixel fit flux | 5.1700 ± 0.1546 mJy |
| Two-/three-pixel aperture flux | 5.1146 / 4.9516 mJy |
| Centroid displacement | +0.00556 / +0.00820 pixel |
| Centroid-fit flux | 5.1542 mJy |
| Five-nearest-zone flux range | 5.1105–5.1507 mJy |

The native-grid normalization is near 1/25, demonstrating why raw-array
normalization would create a major flux error. The correct source zone is
about 0.029 µm redder at the source than its zone-center CWAVE.
Background choices, centroid displacement, and nearby zone choices do not
explain a factor-of-several brightness change in this exposure. The central
pixel is flagged SOURCE only. The radius-six fit has reduced chi² about 3.4,
so formal diagonal-variance errors alone would be optimistic. The field is
crowded; a nearby source enters the outer annulus, motivating median
background and radius checks.

`research_output/research5_spherex_review_first.json` is explicitly a historical
intermediate receipt, not the hash binding for current published inputs.
Scientific-response acquisition was performed only by the author. Four official
documentation pages have retained URL/body-hash/status receipts; the HTML
bodies are temporary intermediates and are not published wholesale.

## Final compact 11-exposure reproduction

The final run uses the Gaia proper motion propagated from 2016 to campaign
midpoint MJD 61273: RA 57.641990555°, Dec 35.585678371°. The several-day
astrometric difference across the campaign is negligible. Each published
gzip file and acquisition receipt is pinned by SHA256 in
`research_output/research5_spherex_review_results.json` and
`research_output/research5_spherex_review_manifest.json`. All eleven
uncompressed FITS hashes were independently checked against their acquisition
receipts. No input failed parsing or measurement.

| File index | Start MJD | Source λ (µm) | Flux ± scaled error (mJy) | Usable PSF | Quality diagnostic |
|---|---:|---:|---:|---:|---|
| 000 | 61269.077387 | 2.795479 | 5.1460 ± 0.1457 | 1.0000 | usable |
| 004 | 61273.492383 | 2.570463 | 4.8549 ± 0.3242 | 1.0000 | usable; reduced χ² 18.4 |
| 008 | 61270.370799 | 3.287102 | 6.4732 ± 0.1404 | 0.9977 | usable |
| 012 | 61270.709327 | 3.655507 | 6.9545 ± 0.2458 | 0.3862 | rejected: masked core |
| 014 | 61270.913269 | 2.449321 | 5.9935 ± 0.1608 | 1.0000 | usable |
| 018 | 61271.726850 | 2.718644 | 6.8557 ± 0.1779 | 0.9677 | rejected: edge 0.687 pixel |
| 019 | 61271.795973 | 3.114087 | 7.2699 ± 0.2059 | 1.0000 | usable |
| 021 | 61271.866695 | 2.443635 | 6.9990 ± 0.1671 | 0.9997 | usable |
| 023 | 61275.464522 | 3.999478 | 5.3769 ± 0.1947 | 1.0000 | usable |
| 029 | 61275.936465 | 4.090424 | 5.5525 ± 0.1811 | 1.0000 | usable |
| 040 | 61277.224458 | 4.378684 | 5.8218 ± 0.1852 | 1.0000 | usable |

At a matching four-pixel fit radius, all nine eligible independent fluxes
agree with the author's Photutils implementation within 0.0002%. The comparison
uses independent least-squares implementations, solid-angle calculations and
renderers. Source wavelength agrees within 10^-6 µm. The independent
complete-support normalization exposes about 3.2% lost ePSF support for 018;
the author's cutout-normalized estimate differs by 3.34%, as expected from
this truncation. Both analyses exclude it from interpretation. This is an
instrument-method check, not an additional independent astrophysical epoch.

The close-wavelength 014/021 contrast is an exploratory difference. Remaining
field calibration, non-simultaneity, spectral response, reduced χ² and multiple
opportunities prevent a validated rapid-variability claim. No extra acquisition
or posthoc confirmation campaign was run for this contrast.

## Claim gate

The pre-outcome author freeze asks for synthesized WISE W1 using at least
eight independent wavelength channels, at least 80% of W1 response, and two
separate visits. A 2.795 µm narrowband detection does not satisfy that gate.
There is **no independent W1 faint-state confirmation from this exposure**.
The 41 SIA records contain 23 D4 and 18 D5 frames; their detector-wide
wavelength ranges must not be mistaken for source coverage. Minute-spaced
dithers are repeated exposures within a visit, not independent wavelength
channels or repeated full spectral visits. Actual source coverage and a
public W1 response calculation were checked with the official
[QE-based W1 response](https://irsa.ipac.caltech.edu/data/WISE/docs/release/All-Sky/expsup/figures/RSR-W1.txt)
(8,468 bytes; retained with a hash receipt). For Fν the photon-count integral
weights this response by R(λ)/λ. The calculation uses nominal source-bandwidth
supports, not detector ranges. WCS widths approximate actual transmission
profiles, so these percentages are diagnostics rather than exact throughput
deconvolution.

All eleven channels cover only about 31.77% of nominal W1 response; the nine
quality-eligible exposures cover **18.03%**, or **19.12%** under flat-Fν
photon-count weighting. Their wavelength convex hull spans 99.99998% of the
response, demonstrating that convex-hull coverage would grossly overstate
observed coverage. Eight nonoverlapping nominal channels across the entire
2.44–4.38 µm collection include three D5 channels with negligible W1 response
and cannot be counted as eight independent W1 channels. There is no pair of
independently measured complete spectral visits. No flux interpolation across
the unconstrained gaps, full-band extrapolation, or synthetic W1 magnitude was
reported.

The valid 3.114/3.287 µm detections near 6–7 mJy resemble the historic bright
state more than the predicted faint state if broad spectral shape and
calibration remain comparable. They are conditional hints in the opposite
direction, not a direct W1 measurement or a validated periodicity failure.

## Verification

Ten tests pass: official-renderer agreement at three subpixel phases,
flux recovery with masked central pixels and background gradients,
preservation of flux lost outside a cutout, parent-coordinate zone selection,
actual QR3 benign flag semantics, analytic solid-angle/unit recovery,
sparse-channel coverage versus interpolation hull, and repeated-channel
coverage invariance.
These are explicitly model-product tests, not additional astronomical data.
Ruff passes on the owned script and test module.
