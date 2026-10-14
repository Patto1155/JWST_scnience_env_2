# MoM-z14 empirical-noise challenge: blocked at acquisition cap

**No fresh N/C interval was computed.** The historical original-
wavelength RATE-v3 conditional signed ionic interval [-0.158, 9.905] admits the
explicit ambient comparison 10^-0.60; it remains historical evidence, not this
session's recalibration. No source-noise coverage or elemental abundance is
validated by the new synthetic tests.

The immutable design is `d50fa97`,
[the frozen protocol](frozen/D_NITROGEN_DESIGN.md). Source/line selection,
parity split, thresholds and multiplicity were frozen before outcome access.
The new model uses even-row off-trace residuals divided by proper target-plus-
donor ERR, a single variance rescale, and measured tapered spectral lags.
Odd rows, exposure-group stability and fixed red-continuum regions challenge
that model. The prior RATE-v3 spatial kernel remains a declared conditional
transport; odd rows/nods are correlated, and the row-centered mean check is
algebraically weak. Three groups cannot identify common line-shaped systematics.

Agent C's current applicable CRDS chain remains DUMMY. Substituting an invented
"real" reference would be invalid. Its separate frozen current-release JADES
1D known-answer test is FAIL at published 1 sigma and PASS at 2 sigma; that
limited check does not validate MoM's raw detector calibration, source wavelength,
LSF, or control-to-source noise transport. This challenge therefore runs with
`--calibration-verdict fail`, even if it can eventually report a conditional
ionic interval. No grade promotion is authorized.

## Executed checks and acquisition

Twelve focused arithmetic/range-reader tests pass. They test loss-of-row-dof
adjustment, absence of flux clipping, held-out variance failure without changing
training noise, missing controls, signed direct ambient-reference contrast,
FITS seek/section behavior, wrong-range rejection and budget enforcement.
They are synthetic numerical controls, not observed-sky injection recovery.
Focused Ruff passes. Subsequent I/O-only improvements (`6eea4b1`) use exact
2880-byte headers, coalesced target-HDU reads, four independent file-pair workers
with atomic shared budgeting, append-only request journals, recorded HDU offsets
and a bounded header-hint helper. SIGTERM/KeyboardInterrupt sets cancellation,
retains receipts and labels interruption distinctly from a scientific null.
Failed/partial responses are conservatively budget-charged. These improvements
passed synthetic tests but **were not run against new scientific transfers**;
no fresh 300-MB counter was started. A future retry needs a separate allocation.

A current exact MAST CAL header probe succeeded HTTP 206: bytes 0–2879 of
51,563,520; response body 2,880 bytes, SHA256
`9facecbfcdc8c6da09caac9fa804bdd3b82e2120ed25718e6bc964cb42bad572`.
See `research_output/session_20261014/d_range_probe.json`.
A fragment hash and source header identity are not whole-file hash verification.
Raw range blocks remain temporary in memory and are cleared after reduction;
only compact derived controls and scientific/transfer receipts are deliverables.

The actual nine-CAL/nine-RATE range measurement command is:

```bash
OPENBLAS_NUM_THREADS=1 python -m tools.jwst.mom_noise_challenge_run \
  --output research_output/session_20261014/d_noise_receipt.json \
  --compact research_output/session_20261014/d_noise_compact.npz \
  --calibration-verdict fail
```

The initial actual run exited 2 at the frozen acquisition cap, before the
nine-product empirical controls or interval fit. Its 4,578 received fragments
sum to **299,988,928 scientific bytes**; with the 2,880-byte header probe, total
accepted bodies are **299,991,808 bytes**, below 300 MB. First remote pixel/header
access was 2026-10-14T01:34:51.829896+00:00, after design commit `d50fa97`.
The exact published receipt is `research_output/session_20261014/d_noise_receipt.json.gz`
(gzip decompression reproduces the original JSON byte-for-byte); per-product totals are in
`d_noise_summary.json`.

The initial 64-KiB header prefetch inadvertently covered five entire CALs,
five corresponding RATE stripes, and part of the sixth CAL. Astropy swallowed
the cap exception while scanning HDU 694 and then reported ASDF not found.
That is a cap-induced parser side effect, not archive absence or FITS corruption.
No statistic was computed; this is an engineering/acquisition block, not a
scientific null. The source grade remains for root to assign; no upgrade follows.

An initial FITS-record-copy error before remote access is separately preserved
in `d_noise_first_attempt.json`. The active run used the initial scanner before
subsequent source/RATE guard and journaling improvements; those changes must not
be represented as exercised by this failed acquisition. The CLI
never describes replaying historical compact likelihood arrays as empirical
recalibration or known-answer validation. Its received-body cap is 300 MB;
headers/fragments are charged and total-file identity is never asserted.

## G235H scope and not run

Current metadata-only MAST position queries by POST (40-second timeout) and GET
(30-second timeout) failed. Receipts are `d_mast_metadata_receipt.json` and
`d_mast_metadata_get_receipt.json`. Access failures do not establish absence of
public G235H data. The prior public metadata report verifies PRISM and nearby
or footprint leads, not N III/C III G235H source coverage. The separate
[next protocol](frozen/D_G235H_NEXT_DESIGN.md) is frozen and waiting for exact
public on-source accession; no G235H outcomes were opened or measured.

Not run/verified: completed actual nine-product empirical
noise fit, observed UV/source-noise calibration, independent astrophysical
repeat, G235H reduction/measurement, new Cloudy grids, independent-provider
review, GOODS-N outcomes, grade promotion, push/merge/PR. No canonical state
files were edited. Root owns every grade.
