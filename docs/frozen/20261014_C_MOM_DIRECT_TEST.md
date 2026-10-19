# Frozen C: direct MoM nitrogen challenge, 2026-10-14

New prospective test; historical D_NITROGEN_DESIGN.md remains untouched.
No new outcome access precedes this file's commit. Adopt its exact nine CAL/RATE
identities, source 5224_277193, extraction, atomic state (20,000 K, 1000 cm^-3),
parity/off-trace/red-window tests, signed amplitudes and 95% Fieller statistic.
The fresh cap is 1,610,612,736 received/reserved response-body bytes, including
failed requests, under the separately committed session amendment. Range reads
only; stop below 5 GB free disk; no raw bodies committed.

## Exact published question and bounded comparison

Primary literature: Naidu et al. arXiv:2505.11263v2, Table 1, section 3.2.3:
https://arxiv.org/html/2505.11263v2 . Table 1's direct line-ratio claim is
solar-relative [N/C]>1 at 2 sigma, pending higher-resolution confirmation.
The section gives log10(N/C)=0.7+/-0.15 to 1.1+/-0.15 over Te=5000--30000 K;
solar log10(N/C)=-0.60. Its direct calculation approximates elemental N/C by
(N3+ + N2+)/(C3+ + C2+). Cue is a separate abundance inference and omits NIV.
The published likelihood uses msaexp-v0.9.4 extracted spectrum and per-bin
errors; neither a full signed-donor covariance nor source-noise coverage is
established by that statement. Do not attribute a quantified covariance to it.

Our one-temperature ionic set compares to ambient 10^-0.60 and the headline
threshold 10^0.40=2.511886. Report reference membership and whether the set
intersects the stated published log-ratio range [0.55,1.25]. This checks a
conditional ionic proxy only, not a refutation of the paper's elemental claim
or a replication of its temperature/model posterior. No positivity truncation.
If B's raw calibration prerequisite is unmet, use --calibration-verdict blocked;
if failed, use fail. Either way report conditional results without promotion.

## Wavelength nuisance before outcomes

Primary literature: de Graaff et al. RUBIES arXiv:2409.05948v2 section 3.3,
Figure 9: https://arxiv.org/html/2409.05948v2 . Reports a PRISM-minus-G395M
mean/median offset around +0.25 detector pixel, plus a slit-position correlation;
point-like slit-edge sources can have centring offsets up to +/-1 pixel.
The 0.25 value is NOT a Gaussian standard deviation. No source-specific offset
probability distribution is published for MoM in these sources.

Therefore freeze a weak, explicitly assumed maximum-entropy prior on unknown
slit position: uniform detector-pixel centring error in [-1,1], common across
exposures. Apply a -0.25-pixel global correction to the assigned PRISM wavelength
coordinate, then add that centring error. This prior's support and common
calibration offset are literature-informed; its uniform density and transport
from RUBIES to MoM are assumptions, not validated empirical calibration.
Use 41 fixed Gauss-Legendre nodes; integrate conditional linear Gaussian
coefficient likelihoods with the prior, retaining signed fluxes. The mixture
mean/covariance Fieller set is a moment approximation and must be labelled
that, with conditional sets at all nodes retained. It is NOT an exact 95%
coverage guarantee for the non-Gaussian mixture. A requested validated
marginal interval remains unavailable without empirical prior/coverage checks.
If a fresh acquisition fails, no mixture is computed and no prior or historical
interval is passed off as measured. No choice among priors after inspection.

GOODS-N sealed. G235H outcomes forbidden; preexisting next design remains
unexecuted unless public on-source product metadata first establish exact
coverage. No state-file edits or grade promotion. Output c_* compact receipts
and docs/MOM_CALIBRATED_CHALLENGE.md. Acceptance focused numerical/range tests,
actual bounded CLI or exact blocking receipt; list what was not run.
