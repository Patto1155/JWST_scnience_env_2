# Frozen E: SMACS 1043 independent raw-reduction test

Frozen before new outcome data access on 2026-10-14. Historical results in
SMACS1043_PATCH_DIAGNOSTICS.md and SMACS_INDEPENDENT_REPEAT.md informed this
follow-up; this is not a blind retest of that prior selection. Do not edit this
file after committing it. Deviations invalidate the primary test.

## Hypothesis, target and selection

At fixed ICRS RA 110.63858928243717 deg, Dec -73.48487214542632 deg, a compact
F444W emission component survives independent reduction and a structured-light
null control. Persistence alone neither establishes a separately identified
object nor a high-redshift/dropout identity.

Primary raw products are jw02736001001_02105_00003_nrcalong_uncal.fits and
jw02736001001_02105_00004_nrcalong_uncal.fits, selected by the previously recorded
exposure identities, not by new pixel values. Both must be reduced. Acquire
MAST metadata first; no replacement target, exposure or filter is allowed if
coverage, dependencies or budget fail. Matching existing CAL/RATE products may
be acquired solely for pointing/identity, response calibration and comparison.
These files are dependent products of the same photons, never new observations.

Metadata cone inventory at this position may select an additional F444W epoch
only if its midpoint differs from these exposures by >=1 day and its metadata
footprint covers a 1-arcsec target disk. Choose the earliest such public epoch
with complete calibrated product and documented midpoint, within remaining
budget; otherwise state that no other-epoch measurement was performed. GOODS-N
is sealed and excluded from every query/acquisition.

## Independent reduction and calibration acceptance

Reprocess UNCAL ramps with the official JWST detector1 and image2 path under an
explicit pinned software version and a CRDS context different from jwst_1535.pmap.
Record step completion, effective exposure, calibration/reference identities,
DQ masks, product checksums, input contributors and the old/new context.
If the current selector selects the identical context, use the same raw ramps
with a fully recorded different official pipeline version; label this
independent reduction, not independent calibration. Never substitute altered
arithmetic on the old I2D mosaics or a repeated same-context released CAL.
Do not implement an incompletely calibrated custom ramp slope as a substitute.

Any unavailable pipeline dependency, required reference, missing astrometry,
nonfinite physical flux calibration, unsuccessful step, saturated target or
>=10% invalid aperture area blocks the primary measurement. Stop rather than
relaxing this gate. Raw and reference transfer accounting includes restores,
retries and every body byte, <=1,610,612,736 bytes in total; metadata <=30 MB.
Delete raw acquisitions after retaining compact reductions/receipts; no raw or
large calibration files enter git.

## Statistic and fixed operator

Use each independently reduced image's WCS, pixel area and photometric response.
Keep all fluxes signed and use the fixed angular aperture radius 0.18873115 arcsec
and annulus 0.37746230--0.62910384 arcsec. Report the aperture/mean-annulus flux,
plus three preregistered background operators fitted outside the central
0.3-arcsec disk: constant, plane and quadratic, each in a 0.65-arcsec square
halfwindow. Do not select whichever background gives the best signal.

Use an empirical matched-aperture control distribution for uncertainty and
one-sided rank p-values; diagonal ERR alone is not a calibrated significance.
Separate-exposure errors retain shared systematic limits. Source identity needs
a compact centroid within 0.2 arcsec of the fixed target in both reduced frames,
with their centroids within 0.05 arcsec of each other after a held-out astrometric
registration check. Relative astrometry must have held-out p90 <=0.05 arcsec.

## Null, injection and multiplicity controls

The dominant null is structured neighbour/diffraction light masquerading as a
compact source. Before target pixel inspection use catalogue source 1033 as the
bright-neighbour center, and source1043's frozen displacement as the null radius.
Use evenly spaced angles 0--359 deg at 1-deg steps on that ring, retaining only
positions >=0.45 arcsec from every frozen catalogue core and >=0.4 arcsec from
the target. This sign-blind exclusion must not inspect the new outcomes. Apply
exactly the target operator to every covered position and record all exclusions.
Ring controls are structured-light controls, not certified blank independent sky.
Require at least 40 covered control positions in both reduced frames.

Joint primary statistic is the smaller of the two target aperture fluxes divided
by the corresponding control MAD scale; use the analogous minimum statistic at
each covered control position. Its rank p=(1+number of controls >=target)/(1+N).
Report control spatial dependence explicitly: this is a diagnostic rank test,
not proof of an independent random sample or a Gaussian five-sigma tail.
Require p<=0.05/4=0.0125 for the primary operator and each of the three background
operators (Bonferroni across four operators); insufficient rank resolution is
a failed/blocked gate, not an inferred tiny probability. Both exposures must
have positive flux with empirical S/N>=5 under every operator, and their
positive aperture flux ratio must lie in [0.7,1.3].

Inject sources at every retained control position in copies of the independently
reduced data using a separately identified measured same-field unsaturated
point-source PSF. Select the PSF using metadata/frozen catalogue only: nearest
covered isolated core brighter than the target, with no catalogue neighbour
within 1 arcsec, outside target/1033 masks; require its held-out residual
reduced chi2<=2. No imported JADES PSF substitutes for this calibration.
Inject fixed aperture fluxes 1,000 and 1,500 nJy and negative -1,000 nJy using
that fixed PSF. Require >=90% injection detection/centroid recovery at each
positive level and median recovered/input flux in [0.8,1.2], with <=5% false
positive detection for negative injections. If PSF selection/calibration fails,
stop the promotion test; do not reinterpret synthetic success as sky calibration.
No data-selected source brightness or new threshold is allowed.

## Decision, additional epoch and limitations

Success requires the calibration, astrometry, all four flux/control tests,
injection recovery and centroid conditions simultaneously. Any failed condition
means the prior screen candidate does not graduate. A missing required component
means unconfirmed/blocked rather than astrophysical falsification. Parent owns
all ledger grades. Preserve failed gates and both exposures' measurements.

If metadata supplies an eligible other epoch, perform the exact fixed-position
operator without redetection/recentering; report midpoint, coverage, signed
flux and the same controls. A nonpositive or empirical <5-sigma epoch fails
persistence; a flux ratio outside [0.7,1.3] fails stable-emission interpretation
but is not by itself proof of variability. With no separate epoch, report only
a different-reduction same-visit test. Independent photons from distinct raw
integrations help; shared provider/model-lineage reviewer agreement does not
supply corroboration. Neither outcome assigns a redshift or dropout identity.

## Deliverables and acceptance

Write docs/SMACS1043_INDEPENDENT_TEST.md and
research_output/session_20261014/e_* receipts, compact outputs and reproduction
code as needed. Acceptance is focused pytest plus regeneration from the pinned
compact inputs using /workspace/scratch/337bba29e79a/jwst-venv/bin/python.
Record freeze commit hash and exact first new outcome access time; list every
measurement/control not run. No edits to STATUS.md or CLAIM_LEDGER.md.
