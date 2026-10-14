# Calibration amendment — 2026-10-14

This dated prospective amendment leaves all original frozen designs untouched.
It records the user's explicit correction to the recovery criterion and the
wavelength treatment for the present session. It is committed before any new
science acquisition or outcome inspection in this session. Historical outcomes
below are already documented evidence, not a blind test.

## Applicable MOS wavelength reference

For NRS_MSASPEC in CRDS context `jwst_1596.pmap`, the applicable reference is
`jwst_nirspec_wavecorr_0004.asdf`. Its own header is DUMMY; changing mapping
revision, substituting fixed-slit/bright-object calibration, or relabelling this
reference cannot provide empirical MOS calibration. The applicability chain and
reference hash are recorded in `docs/KNOWN_ANSWER_TEST.md` and
`research_output/session_20261014/c_crds_verdict.json`.

Carry the wavelength zero-point as a nuisance parameter in every new
spectroscopic measurement. Before spectral outcome access, freeze a numerical
prior justified by primary published NIRSpec MOS slit-centring offsets, cite the
source and applicability, and state its units and transformation to wavelength.
This amendment does not invent that numerical prior: each arm must record it in
its committed design. Marginalise every reported spectroscopic result over the
prior, including its uncertainty. If a defensible prior cannot be established,
stop numerical inference and report that calibration dependency as unmet.

## Combined-error known-answer criterion

The session recovery acceptance criterion is

`abs(measured - published) / sqrt(sigma_measured**2 + sigma_published**2) < 2`.

This supersedes the published-only one-sigma tolerance for the present session;
it does not overwrite the original design, change its historical FAIL result,
or introduce relaxed scientific discovery/promotion gates. The already recorded
C2 current-release recovery is 1.2094 combined-error sigma and therefore PASS
under this amendment. It is one released-1D check on shared photons, with unknown
covariance; it is neither independent corroboration nor a full raw-level test.
Raw detector-to-flux calibration remains unmet until Agent B completes its
separately frozen raw known-answer test. Population-scale calibration also
remains unmet. If the raw-level test fails or remains blocked, spectroscopic
ledger rows remain at or below Unconfirmed lead; the lead owns all grades.

Not run by this amendment: new raw reduction, population fits, nuisance-prior
inference, GOODS-N access, astrophysical measurements or promotion.
