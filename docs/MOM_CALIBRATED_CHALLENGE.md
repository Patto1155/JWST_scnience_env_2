# MoM nitrogen challenge, 14 October 2026

The fresh, wavelength-marginalized conditional ionic N/C moment-Fieller95% set
is **[0.10155,13.48043]**, admitting ambient0.25119 and the published headline
boundary2.51189. It is consistent with, but does not confirm, the published
conditional nitrogen enhancement. **It neither replicates nor refutes an
elemental abundance.** The raw known-answer prerequisite is blocked, not failed.
Any spectrum result below is conditional; no elemental-abundance claim or grade
promotion follows. The applicable MOS wavecorr remains DUMMY. A geometric
prior supplies an explicitly assumed sensitivity, not empirical calibration.

## Published claim and actual comparison

[Naidu et al.](https://arxiv.org/html/2505.11263v2), Table 1 and section 3.2.3,
report direct [N/C]>1 at 2 sigma using N/C approximately equal to
(N3++N2+)/(C3++C2+). Their log10(N/C) spans0.7+/-0.15 to1.1+/-0.15 as
Te varies5000--30000 K. Solar log10(N/C) is-0.60. Their separate Cue result
is[N/C]=0.90(+0.29,-0.63), and omits NIV from its nebular model.

Section 3.1.1 specifies UNITE point-source resolution/LSF and calibration
uncertainties, linked redshift/width, FWHM prior0--650 km/s, redshift prior14--15,
local continuum windows+/-15000 km/s excluding+/-3500 km/s, and numpyro sampling.
The publication does not specify in that section a numerical full shared-nod
covariance; its plotted1sigma spectrum is not proof of calibrated source-noise
coverage. Our signed-donor empirical-noise operator differs, so we do not call
this an exact replication of UNITE or infer that the paper assumed zero
calibration uncertainty. The frozen target is a direct conditional ionic-proxy
challenge, with fixed Te 20000 K and ne 1000 cm^-3.

The relevant benchmarks are ambient0.2511886, the headline lower boundary
2.5118864, and the paper's conditional quoted log range[0.55,1.25]. Membership
or interval overlap cannot establish or refute an elemental abundance over the
paper's different thermal/ionization/continuum assumptions.

## Frozen chronology and wavelength treatment

Scientific design commit43a2b84 precedes first science access
2026-10-14T04:14:42.622019+00:00. Session allowance amendment efe2f43 was also
committed before access. The original D design remains untouched.
I/O-only amendment6b269aa was committed before the whole-CAL range retry;
source identities, thresholds and prior were unchanged. Two header-scan attempts
stopped before reduction, retain all reservations, and are not measurements.

[RUBIES](https://arxiv.org/html/2409.05948v2), section 3.3 / Figure 9, finds an
approximately+0.25 PRISM detector-pixel systematic and reports centring offsets
up to+/-1 pixel for slit-edge point sources. These are a mean and geometric
bound, **not** a measured MoM uncertainty distribution. The assumed conditional
prior is uniform u in[-1,1], common across all exposures, correcting assigned
row wavelength by detector-coordinate shift delta=u-0.25. Forty-one fixed
Gauss-Legendre nodes integrate conditional linear Gaussian likelihoods, including
the coefficient-integral determinant. Signed amplitudes remain unconstrained.
The returned mixture covariance includes within-node and between-node terms.
Fieller applied to these moments is an approximation; it is not an exact 95%
credible set or empirically demonstrated95% coverage for a non-Gaussian mixture.
Every node-specific conditional fit is retained. No post-outcome prior choice.

## Execution and accounting

20 focused tests pass (range identity/budget, control arithmetic, wavelength
shift, signed mixture recovery, coefficient integration determinant); focused
Ruff passes. They are synthetic numerical checks, not source injections.

Exact final acquisition/measurement CLI:

```bash
OPENBLAS_NUM_THREADS=1 /tmp/jwst-cal-env/bin/python -m tools.jwst.mom_noise_challenge_run \
  --output research_output/calibrated_20261014/c_completed_receipt.json \
  --compact research_output/calibrated_20261014/c_completed_compact.npz \
  --calibration-verdict blocked --cap-bytes 644429624 \
  --freeze-commit 43a2b84 --geometric-wavelength-prior --coalesced-cal
```

The two initial interrupted scans reserve6,062,536bytes in total. Three whole-CAL
retries consume480,060,288bytes each: the first two stop on implementation
errors; the third completes. Retry cap falls1,604,550,200 ->1,124,489,912
->644,429,624bytes after each charged acquisition. Final cumulative
conservative charge is1,446,243,400of1,610,612,736bytes. Receipts preserve
started/finished requests, exact ranges, hashes, statuses and unresolved
reservations. Disk check at retry was above20GB free. Full-CAL raw bodies use
temporary BytesIO, closed after source-array reduction, and are never committed;
no whole-file hash check is claimed even when every byte is read.

G235H's preexisting next design remains unexecuted: no fresh metadata accession
established exact public on-source NIII/CIII coverage. This does not establish
archive absence. C did not open GOODS-N; B alone ran the separately authorized northern confirmation.

Not run/verified: empirically identified MoM wavelength-prior distribution;
complete raw known-answer recovery; source 95% noise coverage; exact non-Gaussian
marginal ratio coverage; independent photons/reduction;
observed-source injection recovery; G235H measurement; new Cloudy or Cue model
posterior; full temperature/ionization abundance comparison; independent model
family audit; quality gate integration, state updates, promotion or merge.

## Measured controls, implementation corrections and replay

All frozen practical diagnostics pass: even-row noise variance rescale1.409251;
odd-row held-out variance ratios1.06170,1.09576,1.04219; original fixed red
windows 64 columns, reduced chi2=0.972312 (558.107/574). These controls do not
validate source 95%coverage, and the centered residual mean test is algebraically
weak. Lag 4 spatial transport is not measured (zero eligible pairs). Source-noise
transport and the geometric wavelength prior remain conditional assumptions.

The approximate primary signed ionic estimate is3.75098; its moment-Fieller
set[0.1015474479,13.4804284784] intersects the paper's quoted conditional range
[10^0.55,10^1.25]. No significance larger than the frozen contract is claimed.
RATE/CAL SCI closure maxima are below1.74e-6 CAL sigma in all three groups.

Two complete acquisition runs failed in implementation before a deliverable
interval: insufficient wavelengths in entirely masked rows (corrected to retain
them unchanged; the fixed source operator skips them), then an inherited
all-row wavelength mean poisoned by invalid samples, producing an empty red
control and malformed einsum. The corrected mean excludes missing/zero
wavelengths and preserves the same three frozen red windows; fewer than 30
columns now records failed coverage instead of an einsum exception. These are
implementation corrections, not changes to scientific gates or scientific nulls.
Regression tests cover both and the full 41-node/seven-coefficient serialization.

A compact normalized source/operator/control snapshot is saved before inference
in addition to the final fit compact, allowing future corrections without
new transfers. Frozen 41-node replay exactly reproduces every flux and ionic
set. An explicitly secondary 81-node diagnostic gives[0.1015458045,13.4804371744];
maximum absolute line-flux difference is4.20e-6 in1e-20 units. The41-node
statistic remains primary; quadrature agreement does not establish coverage.

```bash
OPENBLAS_NUM_THREADS=1 python -m tools.jwst.wavelength_mixture \
  --replay research_output/calibrated_20261014/c_completed_compact.npz \
  --output /tmp/c-replay41.json
OPENBLAS_NUM_THREADS=1 python -m tools.jwst.wavelength_mixture \
  --normalized research_output/calibrated_20261014/c_completed_compact_normalized.npz \
  --nodes 81 --output /tmp/c-diagnostic81.json
```

Total recorded accepted bodies1,446,220,352bytes; conservative fresh-counter
charge1,446,243,400/1,610,612,736bytes. Four unfinished and four error-finished header requests retain conservative
charges; no raw file bodies are committed. Full acquisitions were repeated
for code fixes, not independent measurement confirmation. Summary:
`research_output/calibrated_20261014/c_acquisition_summary.json`.

Request journals are preserved as deterministic gzip archives (mtime0);
`c_request_journal_manifest.json` records compressed and uncompressed SHA256
hashes, sizes, and verified byte-exact decompression. CLI receipts remain JSON.
