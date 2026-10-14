# Frozen F design: known YSO temporal survey and DDE 54 continuation

2026-10-14. Prospective design: no new archive outcome data have been downloaded
or opened in this session. Historical repo summaries and the historical DDE 54
contract were read as declared inputs. This file must be committed before any
new archive query. Changes after outcome access void this design.

## Identity-only target selection

The exact preselected names, in fixed order, are AA Tau, BP Tau, DG Tau, DR Tau,
HL Tau, and T Tau. These are a small named classical Taurus pilot, not a complete
or representative YSO population. Resolve each name against SIMBAD basic
identity/coordinate/type metadata only. Require an exact identifier association
and a YSO/T Tauri classification; otherwise retain a blocked row and never
substitute a source chosen for measured variability. Do not query variability,
flux, or period fields when resolving identities. DDE 54 is a seventh, separately
reported continuation target at ICRS 57.64197830092,+35.58569174346, Gaia epoch2016,
proper motion +3.373,-4.526 mas/yr. Its known classification ambiguity remains.

## Primary hypothesis, data, and statistic

Known YSOs can show independently measured W1 variability between SPHEREx visits.
Use only public official IRSA SPHEREx SIA, NEOWISE single-exposure, and ZTF
lightcurve products. Obtain SPHEREx metadata first; detector wavelength ranges
are feasibility metadata, never actual source response. Stop numerical source
analysis if full W1 measurements in two independent visits are unavailable.
QR versions of the same exposure are the same photons. Independent visits must
be at least30days apart; minute-spaced dithers are not independent channels.

Per SPHEREx visit require at least8 nonoverlapping independent source channels
and at least80% integrated W1 response, using actual source WCS bandwidths and
the official W1 photon-count response R(lambda)/lambda. No interpolation across
unmeasured gaps. Apply the existing independently checked native-pixel ePSF
method with fixed astrometry, >=85% usable PSF support, >=4pixel edge distance,
non-benign flags masked, and nuisance-covariance plus empirical noise scaling.

Choose the earliest and latest eligible visits without examining flux. Primary
statistic is T=abs(mW1_last-mW1_first)/sigma_delta. Null: no intrinsic change,
with the matched field-star distribution accounting for field/calibration noise.
Require absolute change >=0.30mag and a two-sided source p<=0.05/6 (Bonferroni
family of the six fixed YSOs), plus agreement in sign with aperture and planar
background measurements. No best-of-wavelength or best-of-visit selection.
A Gaussian p alone is insufficient without the matched empirical null.

For each target choose the20 nearest eligible Gaia/AllWISE field stars within
0.5deg and +/-0.5mag AllWISE W1, ordered by angular distance then stable catalog
ID. Require finite parallax/error with parallax/error>=5, RUWE<1.4, no catalogue
YSO association and unflagged W1, without inspecting variability outcomes.
Require at least10 usable controls with identical channel/visit eligibility.
Controls are not presumed constant from a classifier; report their distribution.
Require empirical false-positive rate <=0.05 with a binomial interval, an
injection-recovery artifact for +/-0.30mag changes in actual representative
backgrounds, and an independent visit/holdout artifact before any promotion.
The20controls cannot alone resolve a 0.00833tail; use a declared Gaussian model
only after QQ/residual diagnostics, otherwise report not estimable and stop.

NEOWISE reference: accept clean paired W1/W2 contamination flags, positive frame
quality, finite positive magnitude errors<0.15 and PSF chi-square<5; visits split
on gaps>30days and require>=4observations. Historical range is characterization,
not independent new discovery. ZTF: separate OIDs, catflags0, 0<magerr<0.15,
<=1arcsec astrometric match; select largest usable r-band OID by count. Secondary
only: contemporaneous30day-bin r vs W1 rank correlation if>=8paired bins;
no lag scan, no discovery promotion or extra primary trial from this statistic.

## DDE 54 exact historical contract continuation

Check current SIA metadata against the existing August campaign
MJD61269.077386667–61277.226. A new release/reduction is not a new epoch.
Re-run only if genuinely new usable exposures in the ORIGINAL confirmatory
window [61090,61310] can add qualifying source coverage/visits. Preserve original
prediction MJD61279, synthesized W1>12.6 with95%lower bound>12.3,
>=8independent channels, >=80%W1response and two separate visits. No window
extension, no synthetic W1 across gaps, and no new period fit. Current metadata
alone cannot pass the W1 source-level contract. If the original data capability
is still absent, the source remains an unconfirmed lead; do not force a flux run.

## Budgets, chronology and stop rules

Total response bodies <=300,000,000bytes, including restored science products,
failed-response bytes, and metadata. Metadata <=30,000,000bytes. Each numerical
run <=600seconds. Record exact URL, status, UTC time, byte count, SHA256 and first
new data-access time. Compact reductions only; delete raw downloads after
reduction and never commit them. No GOODS-N access. No state-file edits.
Phase1 quality gate must be green before outcome science acquisition/analysis;
identity and archive-availability metadata may be checked after this freeze.

Deliver docs/YSO_TIME_DOMAIN_PILOT.md, compact f_* receipts/results under
research_output/session_20261014, necessary code/tests, and explicitly list
what was not run. Root owns grades. Same-lineage agent agreement is not an
independent observation, reduction provider, or physical corroboration.
