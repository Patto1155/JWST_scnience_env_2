# Calibrated known-answer arm — 14 October 2026

**The prescribed population N(0,1) prediction failed on the single northern
confirmation; raw end-to-end calibration remains unmet.** The population experiment tests
conditional released-1D estimator agreement. It does not validate the published
noise model, source wavelength calibration, or MoM spectroscopy.

## Frozen scope and metadata

B raw/population design was committed as `a44f756`, then a separately authorized
conditional population operator/prior as `9811e4c`, before the fresh catalogue
GET at 04:15:58.668829 UTC. The fixed-seed 30-row draw (1989 eligible source-line
rows) was committed as `877a02b` before training spectra acquisition. All 30
identities, quoted fluxes/errors and deterministic training/heldout assignments
are in `b_frozen_draw.json`. Opening published catalogue fluxes for the explicitly
requested S/N selection is recorded; this is not blind catalogue discovery.

The same exact published GOODS-S target maps by fresh MAST metadata to
G395M/F290LP observation `jw01210-o001_s000058975_nirspec_f290lp-g395m`,
obsid 252834985. Two bounded product-inventory POSTs timed out before a response
body. The rate/cal contributor list, lengths and source-specific five-row
extraction/pathloss operator consequently remain unresolved. No raw product was
downloaded. Required total bytes cannot be identified from these failed queries;
it would be false to report an over-cap proof or absence of public data.

## Deliberately conditional wavelength sensitivity

The primary RUBIES paper, arXiv:2409.05948v2 §3.3/Fig9, supplies an approximate
slit-edge one-pixel bound and a PRISM-minus-G395M systematic mean of +0.25 pixel.
It supplies no measured centring probability distribution for these JADES targets.
Our assumed uniform [-1,+1] pixel geometry prior, shifted by -0.25 pixel,
is a stress test. Transporting that PRISM/G395M mean to G140M/G235M/G395M JADES
spectra is **not an instrument calibration** and is not empirically justified.
This deficiency remains explicit rather than being disguised as a measured prior.
The applicable DUMMY MOS reference is never replaced.

At 41 Gauss-Legendre offset nodes and 41 fixed width nodes, signed Gaussian
line flux and linear continuum are fit with supplied diagonal errors. Gaussian
linear-parameter determinant weights enter the likelihood integral; mixture
variance includes within-node error and between-node variation. This newly
frozen operator fixes catalogue redshift and differs from the historical
free-centroid fit as well as JADES fitting. A discrepancy can reflect operator
or prior mismatch, spectral covariance or catalogue selection, rather than
underestimated published errors. The finite assumed width prior and linear
local bin mapping are additional conditions, not source-LSF calibration.

The requested combined-error pull assumes zero covariance in its denominator.
For shared photons, the actual difference variance is
Var(F1)+Var(F2)-2Cov(F1,F2). Unknown covariance, estimator bias and the S/N-truncated
sample prevent identifying a published-error scale factor from pull width.
The KS comparison to N(0,1) is descriptive; its usual interpretation would
require independent unbiased appropriately standardized rows.

## Historical criterion replay

The immutable old design remains untouched. The dated amendment's strict
combined-error criterion is implemented as a separate boolean, retaining the
original 1/2-published-sigma booleans. Compact same-photon replay recovers
28.36421 +/- 0.71922 versus 29.49712 +/- 0.60019 (1e-19 cgs), signed combined
pull -1.20940, PASS under |pull|<2. This neither executes a raw chain nor
grants a population/noise-validation pass.

## Reproduction and limits

```
python -m pytest tests/test_calibrated_population.py tests/test_session_known_answer.py tests/test_mom_compact_followup.py -q
python -m data_pipeline.session_known_answer --replay research_output/session_20261014/c2_known_answer_inputs.npz --reference research_output/session_20261014/c2_reference.json --output /tmp/b_historical_replay.json
```

Focused synthetic tests address signed recovery, missing-window rejection,
retained nuisance variance, combined-criterion boundaries and the nonidentified
error scale. These controls do not certify real-sky coverage. Actual population
compact spectra and receipts preserve measured-source identities and hashes;
raw downloaded bodies are removed immediately after normalization/measurement.

Not run or verified: a complete raw JWST reduction; source-specific extraction,
pathloss, LSF or empirical zero-point calibration; actual noise-coverage or
catalogue-error-factor identification; observed-sky injections; independent
cross-lineage audit; spectroscopy promotion. Root owns the integrated gate and
state files. GOODS-N access and confirmation must be reported separately.

## GOODS-S training result and northern confirmation protocol

The first 15 frozen GS rows all fit: mean combined pull **-0.71110**, sample
SD **1.25169**, diagnostic KS p **0.146996**. A failure to reject N(0,1) with
15 selected shared-photon comparisons is not validation. Neither the 1.25169
width nor the negative mean identifies which catalogue/model term is responsible.
The most discrepant row was retained, with no replacement or prior changes.

These GS outcomes and the numerical prediction were committed as `4fbf419`.
Only afterward did Agent B metadata-confirm the public GN-only v1.2 catalogue,
33,471,360 bytes, linked by official MAST. B3 confirmation scope was committed
as `e2b7b78` before its GET; northern identities were committed as `e55ce37`
before any northern spectra. Exactly one frozen first-15-row GN confirmation
is executed. The original GS heldout spectral half stays unopened and unused.
An existing northern catalogue cannot honestly be called absent to obtain the
fallback. No other agent opens northern catalogue or compact spectral arrays;
the lead receives only aggregate confirmation/chronology/accounting.

The primary descriptive reference predicts pull mean0, SD1 for n15, mean
95% range +/-0.50607, and the precomputed chi-square SD interval in
`b_confirmation_prediction.json`. The committed empirical sensitivity prediction
is GS mean -0.71110 and SD1.25169. These numerical references are unchanged.
Any repeated-source rows, source grouping, S/N selection and shared systematic
calibration weaken an iid interpretation; interval comparisons remain diagnostic.

The B2 model shifts its centroid by delta*medianbin while retaining the nominal
wavelength array. C's model shifts the wavelength array via w(j+delta), an
opposite sign convention in forward prediction. These are distinct assumed
sensitivity operators. They must never be described as the same calibrated
wavelength correction.

GS compact replay reproduces all15 flux/error pairs exactly. Replay command:

```
python -m data_pipeline.calibrated_population --replay research_output/calibrated_20261014/b_training.json --output /tmp/b_training_replay.json
```

This command opens only southern compact arrays. It is numerical verification
on the original photons. Focused acceptance currently has11passing tests;
Ruff passes. Download safeguards also have an explicit regression proving that
received overlength chunks are charged before rejection.

## Final single northern result: prescribed prediction fails

**The descriptive N(0,1) prediction fails; raw calibration remains unmet.**
GN has14usable of15selected measurements: one spectrum GET timeout (its HEAD returned 200) contributes
no flux or pull and is retained, with no replacement. The source-group counts
are15GS/14GN, so these achieved samples contain one selected line per object.
GN mean pull is **-0.970935**, sample SD **0.488430**, diagnostic KS p
**4.75144e-5**. The frozen functions evaluated at achieved n14 give mean95%
range +/-0.523832 and SD95% range [0.620716,1.379398]; both diagnostic interval
checks fail. The originally frozen n15 numerical intervals are also preserved
and give the same failure decision. The mean is a repeatable conditional
estimator discrepancy; the narrower pulls do not identify overestimated errors,
just as broad pulls would not identify underestimated errors. The cross-lineage
audit (`docs/AUDIT_20261014.md`) quantified the discrepancy as a systematic flux
deficit: median pipeline/JADES ratio 0.92 (GS) and 0.86 (GN), 13/14 GN pulls
negative, and insensitive to the width cap and centroid prior.

The northern result therefore provides no population-calibration pass. Its
comparison to the empirical GS prediction is descriptive, with different field
selection and estimator covariance unresolved; descriptively, the GN mean is
consistent with the GS training mean (Welch p=0.47), so the deficit replicates
across fields. No prior, window, width rule,
line set, target or acceptance rule changed after northern outcomes. The failed
prediction cannot be rescued using the unused southern half.

Total science/catalogue bodies are **113,178,240 of300,000,000bytes**; raw
known-answer science bodies are **0 of1,073,741,824bytes**. Raw metadata bodies
are1110bytes; HEAD bodies arezero. Remote search-provider transport is separately
unmetered, not silently counted as zero science transfer. Minimum per-transfer
recorded free disk remains above5GB. Both catalogues and every acquired spectral
body were deleted, preserving compact normalized arrays and SHA256 receipts.
All29successful fits replay exactly on their compact same-photon inputs.

The aggregate-only `b_aggregate_verdict.json` supplies the lead's permitted
review surface, achieved acceptance intervals, source counts, byte totals and
freeze/access chronology. Per-spectrum timestamps begin at HEAD before GET;
commit-before-HEAD proves commit-before-GET, but exact GET start times were not
separately recorded. Successful source headers were checked for TARGET, FILTER,
GRATING and required declared units; original unit strings and source RA/DEC
were not separately retained/validated. The raw slit/extraction gate remains
unmet independently of these released-data identity checks.

Not run additionally: the unused GS heldout spectra; northern refits or retries;
a direct empirical centring prior or cross-instrument transport validation;
full calibrated population coverage. There is no new astrophysical grade,
noise-scale determination or spectroscopy promotion.
