# Known-answer and wavelength-calibration test, 14 October 2026

**Current applicable MoM wavecorr remains DUMMY; no empirical replacement was
obtained. The separately frozen JADES current-release 1D check fails at the
published 1-sigma tolerance and passes at 2 sigma. Raw detector end-to-end
calibration was not performed.** These are calibration/measurement receipts,
not a new astrophysical result or permission to promote a spectroscopic claim.

## Frozen chronology

C1 design is immutable commit
`50a711a6060c6fd5667fb1150c0821dccc566ea3`, committed
2026-10-14 01:27:06 UTC, at
[the original design](frozen/C_KNOWN_ANSWER_DESIGN.md). The design was committed
before current CRDS/reference access and before any newly acquired spectra.
Only public literature, file naming/metadata and the required historical audit
were read first. Existing audit outcomes are not blind discovery data.

C1 selected Bunker et al., arXiv2306.02467v2 Table3's first target, GOODS-S
NIRSpec_ID10058975, [O III]5007 = 35.8 +/-0.8 in1e-19 erg/s/cm2. Original v1.0
spectrum acquisition is **blocked at the tested endpoints**: exact DR1/DR3
MAST and author paths returned404, while the current MAST product list exposes
only v2.0 for this target/configuration. This does not prove that every possible
old-release mirror is unavailable. C1 has no recovered flux or numerical
pass/fail. The immutable original design was neither edited nor rescued by
silently changing the data version.

The coordinator authorized C2, a separately prospective current-release test.
[C2 design](frozen/C2_CURRENT_RELEASE_KNOWN_ANSWER_DESIGN.md) is immutable
commit`8ac3d15391277b2143a9a05498528981391e729c`, committed
2026-10-14 01:40:56 UTC. First C2 science-data GET began
2026-10-14 01:41:12.143929 UTC, after that freeze. No catalogue or spectral
outcome was opened before this new design. Target, line, aperture, configuration,
fit windows and acceptance thresholds were fixed. No replacements followed
inspection. GOODS-N files/outcomes remain unopened.

## Actual current CRDS applicability

The current CRDS homepage advertises`jwst_1596.pmap`. Literal-AST selection
produces`jwst_nirspec_0444.imap` ->`jwst_nirspec_wavecorr_0005.rmap` ->
`jwst_nirspec_wavecorr_0004.asdf` for NRS_MSASPEC on2025-04-14, the actual MoM
observation date. The retrieved whole reference has16453bytes and SHA256
`869d4279137b1c7dea5e8bb4b4980d72fd0aa8423c87814050bfa710cd2b58f3`.
Its actual header still says DUMMY and simple toy MOS model, matching the
historical reference exactly. The mapping revision number0005 does not imply
reference0005 or new empirical MOS calibration. A fixed-slit/bright-object
reference cannot replace the applicable MOS reference.

[C CRDS verdict](../research_output/session_20261014/c_crds_verdict.json),
[acquisition and exact mapping text](../research_output/session_20261014/c_crds_acquisition.json)
and[actual reference header](../research_output/session_20261014/c_crds_reference_header.txt)
retain the chain and hashes. **The empirical-upgrade hypothesis fails the
non-DUMMY criterion.** Historical DUMMY receipts and wavelength sensitivity
calculations remain unchanged. No MoM source wavelength array was modified.

## Current-release known-answer recovery

Public DR4 PaperII (Scholtz et al., arXiv2510.01034) publishes the line-flux
catalogue. The official GOODS-S-only v1.2 catalogue contains3387 observation
rows, all explicitlyField=GS. Exact metadata selection identifies row3114,
Unique_ID`goods-s-deephst_10058975`, RA53.112434deg, DEC-27.774609deg,
published z9.4327. R1000_5pix identifies O3_5007 with G395M/F290LP; its flux is
294.9712061 +/-6.0018874 in the declared1e-20 units. Catalogue identity selection
preceded reading that row's line outcomes; no SNR/extremeness cuts were used.

The actual v2.0 x1d TARGET/position/grating/filter headers match. The filename/MAST product version isv2.0, while its header retains
HLSPVER1.0; this metadata discrepancy is preserved rather than silently relabelled.
Its main EXTRACT5PIX1D columns declare micron wavelengths and cgs per-Angstrom flux
and error. The frozen pixel-integrated single Gaussian+linear continuum fits
16 finite bins in+/-0.015micron, using supplied diagonal errors. The Jacobian
has rank5/5, optimizer converges, and no bound is active. Fit chi2 is4.3041 for
11 degrees of freedom; center5.224186micron and sigma0.00176343micron are
recorded, not calibration truth.

All entries below are integrated flux in **1e-19 erg/s/cm2**:

| Reference | Quoted value/error | Recovered value/diagonal error | Offset in quoted sigma | Frozen verdict |
|---|---:|---:|---:|---|
| Current DR4 GS catalogue, sole C2 primary |29.49712 +/-0.60019|28.36421 +/-0.71922|-1.88759|FAIL1sigma; PASS2sigma|
| Original Bunker Table3, secondary release-mismatched comparison |35.8 +/-0.8|28.36421 +/-0.71922|-9.29473|Disagrees; cannot execute or certify C1 with a changed reduction|

The descriptive combined-error offset is-1.2094, but both measurements share
photons and covariance is unknown; this is not independent corroboration. The
single target/line/aperture/configuration supplies one primary comparison,
so no look-elsewhere correction is required. The fit operator differs from
JADES' full published line-fitting implementation; the2sigma agreement checks
a narrow numerical recovery contract, not universal1sigma coverage.

[Actual known-answer fit](../research_output/session_20261014/c2_known_answer.json),
[published row receipt](../research_output/session_20261014/c2_reference.json),
[compact normalized input](../research_output/session_20261014/c2_known_answer_inputs.npz)
and[final verdict](../research_output/session_20261014/c_final_verdict.json)
retain the numerical outputs and identities.

## What did not become end-to-end calibration

The actual s2d has27 spatial rows, declared flux/error units and wavelength/WCS
metadata. The inspected headers do not identify the exact five-row extraction
center or an explicit five-pixel aperture/pathloss operator. No aperture or
correction was reverse engineered to make it agree after looking. Its
[metadata audit](../research_output/session_20261014/c2_s2d_metadata.json)
records the blocked2D re-extraction. Full contributor identities, detector
products, compatible JWST reduction execution and calibration references were
not established for a complete new raw chain. No partial raw download was
called end-to-end. The pilot makes no verified claim about the total bytes
needed by every possible full raw-reduction route.

Consequently the user-requested raw end-to-end/source calibration gate remains
**unmet**, despite the current released1D2sigma check. This result cannot certify
MoM's source-specific wavelength/LSF, noise transport, line-ratio coverage,
elemental N/C or physical-anomaly interpretations. State grades are solely the
coordinator's responsibility.

## Bounded acquisition and reproducibility

Actual CLI scientific response bodies:65,349,253bytes, including65,332,800bytes
for the south catalogue/x1d/s2d and16453bytes restoring the CRDS reference.
Recorded CLI metadata/error response bodies:466674bytes; HEAD response bodies
arezero. One optional astroquery criteria probe fetched service schema metadata
without response-body metering, then rejected an unsupported get_query_payload
filter; its byte contribution is unknown. Web search/provider transport and HTTP
headers are also unmetered. Scientific300MB compliance is exact; recorded metadata
is well below30MB, but complete metadata-byte compliance is not fully certified. Three acquired FITS files were deleted after compact reduction;
none are committed. The compact array is a released-data replay, not raw data.
[Exact science URLs/bytes/hashes/times](../research_output/session_20261014/c2_acquisition.json)
and the c_* metadata receipts retain successes, failed/empty queries and404s.

Acceptance commands (six focused tests pass, focused Ruff passes):

```bash
python -m pytest tests/test_session_known_answer.py tests/test_mom_compact_followup.py -q
python -m ruff check data_pipeline/session_known_answer.py tests/test_session_known_answer.py
python -m data_pipeline.session_known_answer --replay research_output/session_20261014/c2_known_answer_inputs.npz --reference research_output/session_20261014/c2_reference.json --output /tmp/c2-known-answer-replay.json
```

The compact replay reproduces the fit and both primary verdicts exactly.
`--catalogue FILE --output FILE` regenerates the reference from a hash-verified
GS-only catalogue; `--fits FILE --reference FILE --save-input FILE --output FILE`
regenerates the measurement from the hash-verified current x1d. Raw acquisition
must use the exact URLs/hashes in c2_acquisition.json and charge all transferred
bytes against a fresh declared pilot budget, then delete raws. The module's
`--audit-crds --output /tmp/current-crds.json` explicitly rechecks current public
CRDS metadata; a future changed context is new evidence, not this receipt.

Not run: C1 original-v1 measurement; a complete raw JWST detector reduction;
2D aperture/pathloss re-extraction; MoM-specific empirical wavelength, LSF or
noise-coverage calibration; independent photons/holdout validation; GOODS-N;
different-provider review; full integrated quality gate (coordinator-owned).
No state file or grade was edited. These limits are not pytest skips or passes.
