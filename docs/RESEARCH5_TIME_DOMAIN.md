# DDE 54: new archival characterization and a bounded independent-facility followup

**No confirmed new object, periodicity, or physical mechanism is established.**
Actual public data show three pronounced mid-infrared faint states in 2014,
2018, and 2022 for the already known eruptive YSO candidate **DDE 54**
(VarWISE J035034.07+353508.5; Gaia DR3 219690291611604480).
The changes survive basic quality and local comparison-star checks.
A prospectively specified optical state comparison did not detect the predicted
median r-band contrast. Newly acquired August 2026 SPHEREx pixel data measure
several bright narrow infrared channels, but fail the frozen coverage and
independent-visit requirements for confirming the predicted fourth W1 faint state.
The defensible result is a candidate characterization with constraints, not a
new discovery announcement.

## Identity, novelty, and observed inputs

The coordinate is RA 57.64197830092°, Dec 35.58569174346° at Gaia epoch 2016.
Marton et al. (2016) already list the exact AllWISE source as a class I/II YSO
candidate; Gaia DR3 also classifies it as a YSO. VSX records **DDE 54**, OID
476580, registered in January 2017, with a roughly four-magnitude optical
brightening in 1988 and irregular CSS variation in 2005–2013. Aliases include
2MASS J03503406+3535085 and CSS_J035034.1+353508. The VSX period is blank.
The prior source/classification and known optical variability must remain visible.
The independently checked Gaia parallax is 2.4852±0.1514 mas, RUWE 1.005,
with no duplicated-source or multi-peak flag. No additional Gaia source was
returned within 10 arcsec. See `RESEARCH5_IDENTITY.md` for exact catalog queries,
classification disagreements, and provenance.

Primary sources:

- [VarWISE, Paz et al. 2026](https://arxiv.org/abs/2605.19059), DOI
  [10.3847/1538-4365/ae562f](https://doi.org/10.3847/1538-4365/ae562f).
  [IRSA catalog documentation](https://irsa.ipac.caltech.edu/data/WISE/VarWISE/overview.html).
  Dataset DOIs: 10.26131/IRSA656, IRSA657, IRSA658.
- [DDE 54 primary VSX record](https://www.aavso.org/vsx/index.php?view=detail.top&oid=476580).
- [SPHEREx QR3 overview](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_qr.html),
  DOI 10.26131/IRSA662; [official ePSF tutorial](https://caltech-ipac.github.io/irsa-tutorials/spherex-psf/).

The original VarWISE paper publishes infrared variability and the entire
2013–2024 mission is its discovery input. Its general YSO variability and color
examples cannot be claimed here as new. The specific added question was whether
this source's apparent longer recurrence has an optical counterpart and a new
2026 infrared faint state. Exact-name/alias searches did not locate a published
four-year analysis, but absence of a search result is not proof of novelty.

The exploratory catalog query returned 28 northern sources with W1 amplitude>1,
W1<14, Gaia G<19, parallax>3 errors, and catalog blend/latent flags<0.1 in
selected irregular classes. Three high-confidence YSO candidates were then
examined. All three followup outcomes are retained; selection was not a
population-complete search. The primary is safely below WISE saturation.
Raw GATOR single-exposure tables, ZTF lightcurve CSVs, Gaia/AllWISE/SIMBAD
metadata, and exact acquisition receipts are compressed under
`research_output/research5_time_*`. The literature PDF is cached outside the
repository; its original 22,420,197-byte SHA256 receipt remains.

## Infrared observations and artifact challenge

The primary has 281 raw NEOWISE rows and 272 accepted paired-band measurements,
forming **21 visits** when consecutive observations separated by more than
30 days start a new visit; visits require at least four accepted exposures.
Cuts require clean first-two-band contamination flags, positive frame quality,
positive finite magnitude errors<0.15, finite time/positions/magnitudes, and
profile-fit chi-squared<5. These are exploratory measurements, not independent
replication of the catalog's variability finding.

W1 visit medians range from 11.687 to 13.089: **1.402 mag**. The three conspicuous
faint visits occur at MJD 56898.725, 58356.004, and 59818.554, with separations
1457.279 and 1462.550 days. This approximate 1460-day spacing is an exploratory
cadence pattern. Minimum times lie between sparse six-month visits; these
separations are not a five-day period uncertainty. A conservative neighboring-
visit bracket for three consecutive minima permits roughly 1272–1634 days,
even before allowing aliasing, nonconsecutive cycles, or stochastic variation.
The published catalog's 387.5-day fit is explicitly marked suspect; its alternate
97.07-day solution and the coarse sampling prevent a unique period claim.

A stricter diagnostic retains 197 exposures with moon flags00, frame quality10,
both fit chi-squared<2 and SAA separation>5, preserving all 21 visit faint/bright
patterns. The nearby AllWISE J035030.00+353453.7 comparison source, about 52 arcsec
away, has 21 matching visits, W1 range **0.050 mag** and W2 range **0.071 mag**.
The target-minus-comparison W1 range remains **1.3885 mag**. Faint and bright
states occur in the same annual observing phase; visit centroids stay within
about 0.1 arcsec of the expected target position. These checks weaken global
calibration, annual sampling, and gross source-swap explanations.

They do not eliminate source-specific background/ghost effects or an unresolved
companion. AllWISE W2 has lowercase optical-ghost flag `0o00`; six individual
NEOWISE rows have the same flagged band and are removed by the paired-band cuts.
W1 is unflagged. Actual scan-angle measurements and dedicated WISE faint/bright
image subtraction were not obtained. No unique dust/accretion interpretation
is claimed.

## Frozen optical comparison and all candidate outcomes

`research5_time_optical_freeze.json` was written after the IR exploration and
before ZTF photometric acquisition. The primary prediction was r-band fading
in IR-faint windows [58206,58564] and [59660,59968], relative to IR-bright
windows [58623,59187] and [60082,60283]. The gate was a ≥0.3-mag contrast,
positive conditional bootstrap lower bound, and ≥3 bins/15 observations per
state. The precise bin anchor/bootstrap implementation was clarified after
schema/first-row inspection but before aggregate outcomes; this chronology is
recorded rather than presenting an entirely pre-data formal preregistration.

ZTF cuts require catflags0, finite photometry/astrometry, 0<error<0.15 and a
position within 1 arcsec of propagated Gaia coordinates. Distinct OIDs are
analyzed separately. The largest quality-count r-band OID is selected by a
fixed count rule. Bins are floor(MJD/30); 10,000 bootstrap resamples of bin
medians use seed20261012. Intervals are conditional on these bins and windows,
not independent cycles or universal causal evidence.

| Candidate | State contrast in r | Conditional 95% interval | Counts and outcome |
|---|---:|---:|---|
| DDE 54 / J035034 | faint−bright −0.0489 mag | [−0.1528,+0.0938] | 185/536 exposures, 19/19 bins; prediction fails |
| J003201.18+652930.8 | later−earlier +0.0289 mag | [−0.0278,+0.0825] | 163/734 exposures, 22/22 bins; predicted brightening fails |
| J203459.71+474206.1 | later−earlier +0.3054 mag | [+0.0504,+0.5971] | 13/81 exposures, 3/12 bins; fails 15-observation followup gate |

DDE 54's two cycle-specific contrasts are −0.0968 and +0.0134 mag, also
compatible with zero. Its other OID gives −0.2891 mag with an interval crossing
zero; no pooling rescues the result. Paired same-channel g−r measurements have
only six faint-state pairs and fail the count gate. The broad state-window
medians do not establish absence of an optical counterpart at shorter lags:
30-day r-bin medians themselves span **1.2276 mag**, and historical optical
outbursts are known. Do not call the source optically constant, infer a constant
photosphere, or use an unqualified “IR-only” label.

## Actual independent 2026 infrared data

`research5_time_spherex_freeze.json` specified a fourth faint state around
MJD61279, a window61090–61310, synthesized W1>12.6, ≥8 distinct channels,
≥80% W1 response coverage, and two separate visits before any SPHEREx outcomes.
SIA returns 41 unique exposures across MJD61269.077–61277.226. Eleven pointing
bases were sampled, comprising eight D4 and three D5 images. They form one
August 2026 campaign, not 41 independent epochs. QR3 is improved processing;
its actual observation dates, rather than the release date, establish new photons.

IRSA cutout requests returned HTTP503 twice. Anonymous S3 HTTP ranges succeeded.
Each compact FITS preserves actual IMAGE, VARIANCE, FLAGS and ZODI pixels,
five nearest ePSF rows, the wavelength lookup table, shifted WCS references,
and original-index/header/range hashes. Response206, exact Content-Range,
consistent ETag, bounded streamed body and finite in-image target coordinates
are checked. All 11 published slices are 135,360 bytes before compression;
full range payloads and repeated large ePSF tables stay outside the repository.

Author photometry uses native-center `ImagePSF` sampling with explicit
normalization, local celestial-WCS pixel area, proper-motion propagation,
source/fullsample benign flags, PSF+constant and PSF+plane fits. Spectral TAB WCS
uses the source pixel and bypasses unrelated celestial SIP terms. Errors include
residual variance; no absolute-calibration floor is claimed. Frame012 has severe
core flags and frame018 lies within four pixels of the image edge; both are
ineligible. Independent spline, aperture, plane-background and zone checks
support the usable narrow-channel flux measurements.

For example, author fluxes are **7.272±0.242 mJy at 3.11409µm** and
**6.499±0.132 mJy at 3.28710µm**; independent values are 7.260±0.206 and
6.475±0.140 mJy. These are narrow channels, not direct W1 measurements.
Usable spectral-channel response support covers only **18.03% of W1**
(19.12% under photon weighting); nine frames pass the stated image-quality
diagnostics. The eight nonoverlapping spectral channels include D5 channels
with little W1 response and do not constitute eight well-covered W1 channels.
The wavelength hull is misleadingly broad because large gaps are unobserved.
**Both the 80% coverage and two-visit gates fail; there is no independent
confirmation of a fourth W1 faint state.** The channels appear bright-like,
so the result does not support the faint-state prediction; incomplete coverage
prevents a full synthetic-W1 falsification either.

A posthoc roughly17% difference between two near2.44µm channels is retained
only as an exploratory lead. Its wavelengths/positions differ, calibration and
fit residuals matter, and it arose among several opportunities. No new data or
claim was added for it this round.

## Reproduction, bytes, and next decisive measurement

Use the exact locked `/tmp/jwst-handover-env/bin/python` from the repository:

```bash
python -m discovery.research5_time_explore
python -m discovery.research5_time_followup
python -m discovery.research5_time_spherex_photometry
python -m discovery.research5_time_figure
python -m pytest -q tests/test_research5_time.py
```

The acquisition receipt URLs reproduce individual public queries. GATOR/ZTF/Gaia
readers verify decompressed response bytes and SHA256 before parsing; SPHEREx
readers verify compact-slice hashes. Independent reports are
`research5_review_time.json`, `research5_review_time_control.json`, and the
separate SPHEREx review. The figure is `research5_time_primary.png` / `.pdf`.
The three author boundary tests and strict lint/format checks pass; the
coordinator's full integration gate is reported separately.

`research5_time_byte_ledger.json` records **78,862,376 response-body bytes**,
including the literature PDF and **54,996,304 SPHEREx range bytes**.
Early endpoint probes include one arXiv HTML response whose size was not recorded;
the ledger explicitly does not claim complete exact accounting. Three NEOWISE
TAP cones timed out before any body was observed; two HTTP503 bodies total380
bytes and are retained as failures. The declared allocation was300MB. No login,
paid service, external-person contact, or GOODS-N outcome access occurred.

The next scientifically decisive work is a truly separate, adequately sampled
3–4µm campaign spanning the W1 response, with contemporaneous optical measurements
and source-specific WISE image controls. Retain the failed gates and the known
DDE 54 identity. Confirmation needs additional observations rather than relaxed
coverage thresholds or interpolation through missing infrared channels.
