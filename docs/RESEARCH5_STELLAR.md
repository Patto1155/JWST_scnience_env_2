# KIC 8164262 TESS epoch extension — frozen pilot

12 October 2026. Trusted coding acquisition/analysis. Parent assigned a fresh
300,000,000-byte cap; metadata scout used less than 20KB successful responses,
plus two requests timed out without a response body. No TESS outcomes opened
before this document. This is one a priori literature-selected target and mode,
not a variability catalog screen. No physical discovery is established.

## Primary basis and target identity

Hambleton et al. 2017/2018, MNRAS 473 5165, arXiv:1706.05051,
https://academic.oup.com/mnras/article/473/4/5165/4553530 measured the
prominent n=229 TEO. Fixed ephemeris: primary minimum BJD 2455668.82920,
P = 87.4549 days. Mode frequency=229/P. Other known nearby components may
beat within a short TESS sector and must be bounded before any evolutionary
interpretation. Fuller et al.2017 arXiv:1706.05053 proposed resonance locking;
this pilot measures a conditional empirical amplitude extension, not a unique
mechanism. Later 2019/2024 phase papers and 2022 r-mode papers are known.
Search silence is not evidence that an unpublished TESS extension is novel.

MAST name lookup: RA 291.24683 Dec 44.00042; TIC cone crossmatch gives
TIC 159649612, KIC 8164262, Gaia DR2 2126194667646231168, separation 0.053 arcsec,
Tmag 13.0137. Eight QLP observations exist, sectors 15, 40, 41, 54, 74, 75, 81, 82.
Select all these products by metadata only, one version per sector from
research_output/research5_stellar_tess_metadata_post.json. Latest two sectors
81/82 are distinct-epoch checks; no flux outcomes yet observed. Public light
curves are independent TESS photons relative to published Kepler flux.

## Measurement contract

Keep all finite TIME/flux rows with QUALITY=0 where this field exists; do not
clip phase extrema. Mask periastron |wrapped(t-epoch)/P|<.04. Fixed frequency
f=229/P; sine/cosine plus per-segment quadratic nuisance (gaps > .5 days). Report
both available raw and detrended flux variants with exact naming and provenance;
if QLP lacks an independently calibrated SAP/PDC pair, say so and do not claim
pipeline independence. Correct known integration sinc attenuation. Fit the whole
sector and chronological halves. Report flux scatter, timestamps, camera/CCD,
aperture/crowding metadata, and numerical design conditioning. Formalwhite-noise
errors do not settle correlated noise; half-sector discordance and segment
scatter bound precision. Fixed229 fit is only exploratory before known-neighbor
and adjacent228/230 nuisance sensitivity tests. A joint stable-frequency
multisine across all epochs tests whether coherent beating explains changes.

A >30percent amplitude change repeated in distinct sectors is a candidate
screen, not a p-value claim or physical discovery. Actual timestamps plus known
neighbor terms and an injected 1000 ppm target mode are the window/sampling controls.
Distinct sectors and independently measured raw flux are stronger than halves
of one preprocessing product. Crowding/aperture/QLP processing differences and
unresolved beating remain primary alternatives. Mode changes are interpretable
only after these are bounded. If no large change appears, report new baseline
measurements and sensitivity honestly; do not promote a null as a discovery.

## Premeasurement literature refinement

Independent reviewer extracted Table 5 before any flux fit: target frequency
2.6184922(3)/day, amplitude 1010(20) ppm; three known sidebands
2.61912(2), 15(2) ppm; 2.61832(3), 11(1) ppm; 2.61901(5), 6(1) ppm.
Use this exact primary-paper target frequency for main fits rather than rounded
229/P. Mask minimum-light epoch as above; actual periastron epoch is
BJD 2455668.7898(2), a 0.0394-day difference immaterial for ±3.5-day mask.
Known sidebands sum 32 ppm, conditional constant-Kepler-amplitude peak-to-peak
beat envelope 64 ppm. Report actual timestamp injection envelope and conditioning.
The QLP format inspection shows SAP_FLUX, KSPSAP_FLUX and smaller/larger
aperture variants; no CROWDSAP. Spline break minimum 0.3 day is comparable to
0.382 day mode period, so detrended flux alone cannot establish mode damping.
Raw SAP is mandatory for any candidate continuation. BESTAP/SMALLAP/LARGEAP,
TIMEDEL, camera/CCD vary and must be reported explicitly.

## Executed products and initial measurements

Eight compressed FITS products were acquired (3,467,520 response-body bytes),
with full uncompressed SHA256 identities in
`research_output/research5_stellar_inputs.json`. Sector 74/75 use official v02
barycentric-time repairs; no obsolete v01 time series were analyzed. Products
span MJD 58710.885–60558.747, 2019–2024. The retained quality/periastron counts are
414, 3672, 2603, 2540, 11084, 11437, 10421, 10611 for sectors 15, 40, 41, 54, 74, 75, 81, 82.
The default/small/large geometrical apertures are fixed 2.5/1.75/3.0 pixels in all
files, but camera/CCD and crowding still change. Exact filenames encode dates,
versions and TIC and are preserved in the manifest.

The first schema reader omitted renamed late-epoch DET columns; no conclusion
was finalized from that omission. Official QLP release notes
https://tess.mit.edu/qlp-update/ explain the KSPSAP→DET rename and SYS_RM as an
intermediate systematics-removed product retaining stellar variability. These
are processed versions of the same photons, not independent replication.
The corrected reader includes every documented raw/detrended/aperture variant.

Main fixed 2.6184922/day amplitudes, corrected only for known integration time:

| Sector | Camera/CCD | raw SAP ppm | small-aperture DET/KSP ppm |
|---|---|---|---|
|15|2/3|1188±799|682±268|
|40|2/4|1108±334|666±84|
|41|2/3|695±232|428±96|
|54|3/2|645±357|553±107|
|74|4/1|772±268|614±81|
|75|4/2|765±201|590±77|
|81|3/2|726±201|601±76|
|82|3/1|264±277|621±72|

Errors here are white-residual formal errors, not calibrated total uncertainty.
Latest small-aperture measurements consistently recover a ~600 ppm mode. No
repeated >30 percent amplitude change survives this basic comparison. The
sector 40/41 apparent difference uses different CCDs and is neither strong enough
nor instrumentally bounded for a physical claim. Latest raw SAP noise is large
(14,500–20,200 ppm residual RMS); differences between raw, detrended and SYS_RM
preclude claiming precise stellar amplitude stability or damping. Per-half
changes and adjacent harmonic fits are retained in the JSON. The latest single
mode design condition is 13–15; unknown adjacent harmonic amplitudes can strongly
change a short-window fit even when numerical condition alone is not enormous.

The corrected integration-aware 1000 ppm extracted time-series injections recover
1000 ppm exactly by construction; this validates linear fitting and timestamp
window handling, **not** response of the upstream QLP photometry or detrending.
Three fixed published sidebands have a conditional maximum linear leakage ~32 ppm
per sector in the eight-phase numerical screen (reviewer computes an analytic bound).
That bounds only their published amplitudes, not all unknown neighbor power.
A Kepler 1010 ppm → TESS 600 ppm contrast has a passband alternative and is not a new
mode damping result. No significant physical change or unique resonance-lock
mechanism inference is established. Independent numerical review is complete; see `RESEARCH5_STELLAR_REVIEW.md`.


## Independent review and stopped pilot

An independent QR implementation reproduced all 36 primary coefficients to
within 2×10^-11 ppm, verified the eight uncompressed identities, and bounded
known-sideband leakage analytically. Joined 2024 small-aperture DET epochs
74/75 and 81/82 yield 597.52±55.97 and 606.87±52.38 ppm, respectively
(white errors only). The difference is 9.35±76.66 ppm, 1.6% of the earlier
apparent amplitude. Linear trend fits give 597.33 and 606.15 ppm; adding
background and centroid regressors gives 593.96 and 598.79 ppm. These are
consistent extracted-product measurements, not calibrated stellar-amplitude
limits. The latest baseline contains ~54-day sampled groups separated by
months; it does not continuously cover the full 2019–2024 interval.

The same fixed instrumental nuisance model shifts sector 82 raw SAP from
264±277 to 672±187 ppm, and SYS_RM from 398±269 to 791±185 ppm. Its
apparent collapse is therefore not robust. The officially documented change
from KSP to DET also changes the detrending algorithm; equal names after
alias translation do not establish homogeneous processing. No further pixel
acquisition is warranted by these outcomes.

This pilot stops with a new TESS epoch extension of a known mode and no
established physical evolution or astrophysical discovery. Exact inputs,
measurements, independent controls and limitations are retained. The schema
regression verifies that a 1000 ppm synthetic mode is retained identically
through old KSPSAP and new DET column names; one focused test passes and
strict lint/format checks pass. Numerical agreement is validation, not new
physical evidence.
