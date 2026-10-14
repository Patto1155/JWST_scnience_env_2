# SMACS 1043: completion assessment, 14 October 2026

**The promotion test remains failed; the physical patch remains unconfirmed.**
The prompt's premise that this arm stopped only on acquisition is false: the
previous official raw reduction already failed three of four frozen
structured-light null gates and the separate-source association gate. Neither
a future injection pass nor an archive timeout can overturn those outcomes.

## Prospective design and actual replay

The unchanged injection fluxes (+1000, +1500, -1000 nJy), all 279 retained ring
positions, zero positional offset and one trial per flux/image were committed
in `ba11dc1` before new array access. This is 1674 planned ring image trials. A subsequent prospective patch-grid
amendment (`e6c7ead`), committed before any injection outcome, adds 30 image
trials: the exact patch coordinate, five offsets (0,0), (±0.05,0) and
(0,±0.05) arcsec, all three signed fluxes and both images. Total planned
trials are 1704; total executed trials remain zero. Existing patch flux must
be subtracted from injected-image measurements when measuring incremental
recovery. The amendment is informed by known patch outcomes, not blind. The
session allowance amendment was also committed before access. These are
prospective prerequisite/injection designs informed by known historical
outcomes; the compact replay is explicitly the same photons, not independent
confirmation. Full commit hashes and access times are in
[d_verification.json](../research_output/calibrated_20261014/d_verification.json).

The two 829440-byte compact calibrated products retain SCI, ERR, WHT and WCS,
JWST 3.0.0, CRDS jwst_1596.pmap and S_RESAMP=COMPLETE. Replaying the actual
operators yields all 279 controls in each image, unchanged rank probabilities
and identical pass/fail decisions. Maximum target-flux discrepancy is
1.90e-7 nJy; maximum individual control-flux discrepancy is 2.12e-6 nJy,
within the prospectively fixed 1e-5 nJy replay tolerance.

| Operator | Rank p | Frozen p≤0.0125 |
|---|---:|---|
| Mean annulus | 0.0107143 | Pass |
| Constant | 0.0250000 | Fail |
| Plane | 0.0214286 | Fail |
| Quadratic | 0.0178571 | Fail |

This reproduces a persistent positive aperture patch embedded in structured
light, with an unpassed object-association contract. It supplies neither a
calibrated independent-tail probability nor a new astrophysical null.
The historical full-field association failure is preserved, not rerun or
claimed reconstructed from these small cutouts.

## Injection prerequisite assessment

**Completed image trials: zero.** Core1030 was selected from historical
catalogue metadata as the nearest eligible isolated brighter core, not identified
as a star. No separately validated same-field point source or held-out measured
PSF reduced-chi2 ≤2 artifact exists for it. The compact FITS omit native DQ;
prior target-aperture DQ validation does not certify unsaturation of this PSF
candidate. A core's own empirical profile fitted to itself would not establish
point-source identity or an independent held-out PSF control. Thus existing
compact pixels suffice for operator replay but do not satisfy the unchanged
injection prerequisite. No Gaussian or imported JADES PSF is substituted.

A future attempt must first independently certify the metadata-selected core's
point-source identity and unsaturation, and its measured same-field PSF on an
independent held-out residual control under the original ≤2 gate. Only then
can the frozen 1704-trial ring-plus-patch grids be executed. Even a successful result would
leave the previously failed required null/association gates failed.

## Other public epoch and resources

A single bounded retry of the original metadata-only MAST F444W position request
at 04:13:54 UTC timed out at 04:14:29 UTC, receiving zero response bytes. The
first compact array replay was at 04:14:37 UTC. The response does not establish
whether another qualifying epoch exists; its identity, coverage and midpoint
remain unverified. Forced photometry was therefore not run. The unchanged
selection requires ≥1-day separation and full coverage of the fixed target
1-arcsec disk before any acquisition. The metadata receipt is
[d_epoch_metadata.json](../research_output/calibrated_20261014/d_epoch_metadata.json).

New science/reference transfer: **0 bytes**. The cumulative conservative
reservation remains **5,826,074,168 / 6,442,450,944 bytes**, leaving
**616,376,776 bytes**. No counter was reset. Free disk remained above 22 GB
at final verification; raw/reference bodies were not restored or committed.
The exact replay JSON is preserved as `d_compact_replay.json.gz`; gzip
decompression restores the byte-identical JSON and its hash is in
`d_verification.json`. The append-only arm budget receipt is
[d_budget_fragment.json](../research_output/calibrated_20261014/d_budget_fragment.json).

## Acceptance and limits

All 20 focused SMACS tests pass; actual compact replay passes the frozen
numerical comparison. Execute:

```bash
python -m discovery.smacs_e2_photometry \
  research_output/session_20261014/jw02736001001_02105_00004_nrcalong_i2d_compact.fits \
  research_output/session_20261014/jw02736001001_02105_00003_nrcalong_i2d_compact.fits \
  --replay-compact --output /tmp/d_smacs_replay.json
python -m pytest -q tests/test_smacs_e2_run.py tests/test_smacs_e2_photometry.py \
  tests/test_smacs_raw_preflight.py tests/test_smacs_raw_gate.py
```

Not run/verified: measured-PSF calibration and injection recovery; new-epoch
forced photometry or exhaustive epoch inventory; full-field astrometry replay;
raw reduction repeat; physical source identity, intrinsic variability or
redshift; cross-lineage audit. Neither canonical state file was edited.
This session closes the bounded completion attempt with explicit unmet
prerequisites; it does not close the physical-source question or promote it.
