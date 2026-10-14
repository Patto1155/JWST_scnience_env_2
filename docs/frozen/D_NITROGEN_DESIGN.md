# Frozen D: MoM-z14 empirical-noise challenge

This design is frozen by its first git commit before any new outcome arrays are
opened, downloaded or measured. Historical prose and implementation source were
read to declare it; no current NPZ/FITS/JSON likelihood outcomes were opened.
A later change to this file after access voids the design. Code may implement
this unchanged specification; feasibility failures cannot be rescued by changing
cuts. GOODS-N is sealed and excluded.

## Inputs and hypothesis

Use only the nine hash-pinned MoM-z14 NRS2 CAL/RATE exposures in
`data_sources/followup/mom_native_inventory.json` and
`data_sources/followup/mom_rate_noise_manifest.json`, source identity
`5224_277193`, their original-wavelength RATE-v3 signed extraction contract,
N IV doublet v2, generic-point PRISM resolution, fixed redshift, and atomic cell
T=20,000 K, electron density=1,000 cm^-3. Source geometry and masks retain their
historically frozen red-continuum choices; no geometry reoptimization.

Hypothesis: an empirical residual-noise model calibrated outside the line
outcomes is adequate on declared observed controls, and its signed two-stage
ionic N/C 95% Fieller set excludes the explicit comparison 10^-0.60.
Null: that reference is admitted, or noise calibration/transport is not
established. This is an ionic comparison, never elemental abundance, intrinsic
nitrogen enrichment, or a newly discovered source. Previous photons do not
provide an independent astrophysical replication.

Execution waits for Phase 1 green and Agent C's known-answer calibration verdict.
A failed/blocked C verdict permits code/synthetic checks and metadata scoping but
no affirmative spectroscopic inference. It must be reported prominently.

## Data selection and empirical model

1. Reconstruct target-plus-shared-donor RATE-v3 variance using actual RATE
   ERR/VAR and CAL gains/flat remainder. Preserve signed extraction weights;
   never subtract background twice or apply the old demixed scale twice.
2. Calibration pixels are all valid off-trace CAL pixels at the original frozen
   selected UV columns, outside the union of positive/negative nod traces by
   >2.5 pixels. No flux-dependent rejection/clipping or source-line residuals
   enter noise estimation. Subtract each eligible row's constant; require >=20
   valid columns per row. Degrees-of-freedom adjustment uses n/(n-1).
3. Split controls deterministically by physical spatial row parity. Even rows
   train the ERR variance rescale and lag-1..3 spectral correlations; odd rows
   are held-out control checks. All nods of one exposure group remain together
   for reported leave-one-group-out diagnostics. Correlated rows/nods are not
   described as independent sample sizes. Estimate spatial lag correlations
   from training even-row separations (lags 2 and 4), with odd lags explicitly
   unavailable from this split; use the previously declared RATE-v3 spatial
   kernel as a fixed conditional transport rather than estimating unseen lags.
4. Build Bartlett-tapered spectral lag-1..3 kernel, with fixed identity
   shrinkage only as needed for minimum eigenvalue 0.1. Use one pooled training
   variance scale, multiplied once onto RATE-v3 covariance. This is an actual
   fresh raw-pixel empirical recalibration only if fresh controls are read;
   loading the historical replay alone is not recalibration.
5. Independent source-aperture residual check uses only observed 3.35–3.60,
   3.90–4.10 and 4.25–4.45 micron columns. Fit a linear continuum to these
   declared wavelengths, whiten with the transported noise, and report residual
   variance and mean. These red controls test limited transport; no assertion
   that red continuum calibrates UV common line-shaped systematics follows.

## Calibration thresholds and statistic

Require >=100 finite held-out off-trace pixels per each of three exposure
groups, >=30 usable source-aperture red-control columns overall, finite positive
covariance and no unsupported extraction weights. Held-out off-trace variance
ratios (held-out variance / predicted training scale) and red residual reduced
chi-squared must each lie within [0.70,1.30]. Each held-out group standardized
mean absolute value must be <=0.20. Report all groups even on failure. These
fixed practical thresholds are adequacy diagnostics, not certified 95% source
coverage; the small number of independent exposure groups and shared
calibration errors remain limitations. Failure prevents the adjective
"validated" for source noise and prevents promotion.

Fit the fixed original-wavelength, generic-point signed UV measurement by GLS
under the recalibrated covariance. Keep negative fitted line amplitudes. Report
signed N IV total flux, all line amplitudes/covariances, and the two-stage
(NIII+NIV)/(CIII+CIV) emissivity-adjusted Fieller confidence set, including
unbounded/disjoint sets. Never truncate the set to positive ratios. Check its
reference membership independently with the direct contrast
(n-r*d)^2 <= z^2*(var(n)+r^2*var(d)-2*r*cov(n,d)).

One target, one primary statistic, one fixed atomic/response/noise model:
familywise alpha=0.05 (no multi-model best-interval selection). All alternative
historical covariances are contextual sensitivities, never additional tests
used to select a discovery. Exclusion is a conditional ionic tension only if
all calibration gates pass and Agent C passes; otherwise report unconfirmed or
blocked. Null results and failed gates are deliverables.

## Acquisition, provenance, next design

Pilot <=300 MB; initial metadata <=30 MB. Existing verified shared inputs may be
used after authorization. For new transfer record URL, exact body bytes, SHA256
and object/exposure identity. Full-file identity cannot be claimed from range
fragments; record ranges and fragment hashes separately. Stop if the required
inputs cannot be obtained within cap. Delete newly downloaded raw products
after compact derived controls and receipt preservation; never commit raws.

After freeze, inspect public MAST/CAPERS metadata only for G235H N III/C III
coverage of MoM-z14. Product metadata is not zero-flux evidence. Write a separate
next frozen protocol only if source coordinates, grating coverage and public
products can be identified; do not open/measure G235H outcomes.

Outputs: `docs/MOM_EMPIRICAL_NOISE_TEST.md`, compact
`research_output/session_20261014/d_*`, focused implementation/tests if useful.
Acceptance: focused pytest and actual measurement CLI with the session venv;
if inputs/gates block, code checks and a precise blocked receipt instead of a
fabricated measurement. Never edit `docs/STATUS.md` or `docs/CLAIM_LEDGER.md`,
promote a grade, push, merge, or open a PR. Report freeze commit, first-data-access
identity/time, every executed command and **what was not run**. Root owns grades.
