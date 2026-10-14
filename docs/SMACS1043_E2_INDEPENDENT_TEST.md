# SMACS 1043 E2: real independent reduction, failed frozen promotion gates

**The aperture patch persists under an actual raw reduction, but fails the
frozen structured-light and separate-source association gates.** Propose
**Unconfirmed lead** to the coordinator. This is not physical rejection of the
patch, a redshift determination, a new epoch or a discovery. E1 remains blocked
under its original allowance; its evidence and immutable design are preserved.

## Approval, freeze and actual reduction

The user approved 6 GiB conditional on room at **2026-10-14T01:45:14Z**.
[E2's immutable design](frozen/E2_SMACS1043_BUDGET_DESIGN.md) is commit
`19f2702294b680d2961045c55a508a6edcd157b4`. It changes the acquisition allowance,
not E1's hypothesis, target, selection, operators, thresholds or multiplicity.
Prior raw headers, reference selection and published historical photometry were
known. This is prospective reduction validation of a nominated patch, not a
blind target search. E2 acquisition began01:50:29.605674UTC and the first raw
pipeline open started02:17:20.762226UTC. First new target-array analysis began
**02:19:45.082179 UTC**,
after approval and freeze. GOODS-N was not opened.

Both exact SHA-pinned UNCAL exposures were restored and independently processed
with official **JWST 3.0.0 / CRDS jwst_1596.pmap**, compared with historical
**2.0.1 / jwst_1535.pmap**. Detector1 and Image2 ran sequentially, with explicit
selected reference paths and forbidden unmanifested reference/body downloads.
The official selector was checked again after freeze and retained the exact
context/reference list ([receipt](../research_output/session_20261014/e2_selector.json)).

Required mask initialization, saturation, IPC, superbias, reference-pixel,
linearity, dark subtraction, jump, ramp fitting, WCS assignment, flat and
photometric calibration report COMPLETE. Both independent I2D products have
S_RESAMP=COMPLETE, CAL_VER=3.0.0 and CRDS_CTX=jwst_1596.pmap.
Group-scale/gain-scale and disabled or inapplicable steps retain their actual
SKIPPED status; SKIP is not presented as PASS. Native target apertures have
100% valid pixels and zero saturation flags ([DQ/control receipt](../research_output/session_20261014/e2_native_dq_validation.json)).
[Pipeline parameters and states](../research_output/session_20261014/e2_pipeline.json)
and [eight product/header hashes](../research_output/session_20261014/e2_products.json)
identify the actual execution. The calibrated outputs retain disjoint raw
contributors, but are the same historical visit/photons, with midpoints only
15.3888 minutes apart. They are not a new observing epoch or independent sky field.

## Frozen operators and structured-light controls

The fixed RA/Dec, aperture radius 0.18873115 arcsec and mean-annulus boundaries
0.37746230--0.62910384 arcsec are unchanged. Constant, plane and quadratic
backgrounds use a 0.65-arcsec halfwindow and exclude the central 0.3-arcsec disk.
No operator was selected for giving the strongest signal.

Before new target analysis, the frozen source1033-centred 360-angle ring was
constructed from the old catalogue. Its radius is 2.3263843 arcsec. The stated
catalogue/target exclusions retain **279 controls**, all covered in both new
images. Their positions, exclusions and catalogue hash are in
[the geometry receipt](../research_output/session_20261014/e2_geometry.json).

| Operator | Reference 00004 flux (nJy) | Repeat 00003 flux (nJy) | Repeat/reference | Controls ≥ target | Rank p | Fixed p≤0.0125 |
|---|---:|---:|---:|---:|---:|---|
| Mean annulus | 1232.719 | 1293.693 | 1.04946 | 2/279 | 0.0107143 | Pass |
| External constant | 1241.085 | 1301.952 | 1.04904 | 6/279 | 0.0250000 | Fail |
| External plane | 1228.582 | 1285.016 | 1.04593 | 5/279 | 0.0214286 | Fail |
| External quadratic | 1241.897 | 1307.478 | 1.05281 | 4/279 | 0.0178571 | Fail |

The statistic is the smaller of the two target flux/control-MAD ratios. The
rank calculation is `(1 + controls >= target)/(1 + 279)`. Both exposures remain
positive with empirical ratios 23.38--42.42 and flux ratios inside [0.7,1.3],
but **three of four rank gates fail**. Bonferroni's fixed 0.05/4 cut was not
changed after inspection. These spatially dependent ring controls are an
explicit structured-light diagnostic; their MAD and rank p are not certified
independent noise tails or Gaussian confidence levels. They demonstrate why
persistent positive aperture flux alone cannot promote this scene feature.

## Astrometry passes; separate-source association fails

Independent full-image 5-sigma segmentation produces **346 training matches and
339 held-out matches**. The fitted east/north translation is
(-0.002290,+0.001857) arcsec. Held-out corrected radial p90 is
**0.042223 arcsec**, passing the fixed 0.05-arcsec frame gate. The same centroids
did not both fit and certify that translation.

The nearest independently segmented centroids to the fixed target are
**2.4343 arcsec in 00004** and **1.8902 arcsec in 00003**, both outside the frozen
0.2-arcsec association radius. The separate-source centroid gate therefore
fails. This does not prove the patch is instrumental: segmentation can merge
real scene components. It prevents claiming a separately identified compact
object from this particular detector/background/association contract.

All target operators, control operators, empirical scales, counts, registration
summaries and centroid outcomes are preserved in
[the actual measurement](../research_output/session_20261014/e2_photometry.json).
The already-failed required gates stop promotion. Measured same-field point-PSF
validation and injection recovery were not run; no passing injection artifact
is manufactured. Catalogue core1030 is merely the frozen nearest eligible
PSF candidate, not a validated star/point-spread calibration.

## Transfer failure, recovery and physical-resource limits

| Accounting item | Bytes |
|---|---:|
| Approved cumulative cap | 6,442,450,944 |
| E1 conservative charge carried forward | 226,670,400 |
| E2 actual response-body reads, including failed read/write overlap | 4,897,881,080 |
| E1 conservative + E2 actual reads | 5,124,551,480 |
| Cumulative conservative reservations, retaining entire failed request | 5,826,074,168 |
| Allowance remaining after conservative reservations | 616,376,776 |

The first dark request read 3,677,356,032 bytes before ENOSPC. Growing files
inside the synchronized workspace accumulated duplicated temporary copies,
using approximately27GiB rather than their approximately3.9GiB logical file
sizes. Only identified copies were removed; live inputs moved outside workspace
synchronization into `/tmp`. Recovered free disk was21GiB. The retained dark
prefix is3,662,675,968 bytes, so **14,680,064 read bytes were not present in the
retained file**. The original failed request remains charged at its entire
4,378,878,720-byte reservation.

A single explicit bounded continuation reserved **716,202,752 bytes** before
GET. The server returned HTTP206 with exact
`Content-Range: bytes 3662675968-4378878719/4378878720`. Its completion produced
the full reference hash; no full-file retry was performed. Initial failure,
prefix size/hash, space recovery, request/range hashes and all reference/raw
identities remain in [failed acquisition](../research_output/session_20261014/e2_acquisition_failed.json),
[storage recovery](../research_output/session_20261014/e2_storage_recovery.json)
and [completed cumulative ledger](../research_output/session_20261014/e2_acquisition.json).
No new scientific threshold was introduced by that storage repair.

Post-freeze CRDS selector response reads total1,171,171 bytes; pipeline metadata
reads total1,161,469 bytes, separately metered below the30MB metadata cap.
The filtered later-epoch metadata request timed out before receiving a body
([receipt](../research_output/session_20261014/e2_epoch_metadata.json)); its failure
establishes no absence of other epochs. E1's uninstrumented RPC totals remain an
explicit historical limitation. Existing software was reused; its original
package-transfer bytes were not instrumented and are separate from science data.

The parent-side process monitor reported480KiB maximum RSS, which is implausible
for this worker and is **not verified actual pipeline peak memory**. The wrapper
had physical stops configured, but that telemetry does not prove their effective
coverage. This limitation is recorded in the pipeline receipt. The actual
pipelines completed; no claim of a measured6.5GiB worker-memory bound is made.

## Compact replay and checks

Two calibrated 810KiB cutouts preserve actual SCI/ERR/WHT values and WCS covering
the target, all ring controls and the frozen nearest PSF candidate. They are
compact derived data, not raw ramp downloads. Replay all four operators with:

```bash
python -m discovery.smacs_e2_photometry \
  research_output/session_20261014/jw02736001001_02105_00004_nrcalong_i2d_compact.fits \
  research_output/session_20261014/jw02736001001_02105_00003_nrcalong_i2d_compact.fits \
  --replay-compact --output /tmp/e2_replay.json
python -m pytest -q tests/test_smacs_e2_run.py tests/test_smacs_e2_photometry.py \
  tests/test_smacs_raw_preflight.py tests/test_smacs_raw_gate.py
```

[Compact replay](../research_output/session_20261014/e2_compact_replay.json) preserves
all control counts, rank p values and pass/fail decisions. Maximum target-flux
difference is1.90e-7nJy, and maximum control-MAD difference2.06e-7nJy
([verification](../research_output/session_20261014/e2_replay_verification.json)).
This is numerical reproducibility on the same photons, not new corroboration.
Nineteen focused tests pass and new modules pass ruff. Synthetic tests validate
budget guards, multiplicity resolution and signed background subtraction; they
are not observed-sky injection controls.

Raw ramps, reference bodies, partial files and large generated products were
removed after compact verification; [cleanup](../research_output/session_20261014/e2_cleanup.json)
records identities and zero remaining task-cache files. No large inputs enter git.

**Not run:** measured point-PSF calibration/injection recovery; new-epoch forced
photometry; a blue/dropout/redshift test; stellar/galaxy identity; intrinsic
variability inference; exhaustive alternative contexts or pipeline paths; an
independent-provider reviewer; verified actual-worker peak-memory measurement.
No canonical status or claim-ledger file was edited by this agent.

Coordinator follow-up: future resource monitoring now resolves direct-child PIDs
against the procfs namespace instead of reading an unrelated process. A real
16 MiB child-allocation test passes. This repairs future sampling; it does not
retroactively establish the historical pipeline peak, which remains unverified.
The science reduction was not repeated solely to obtain new memory telemetry.
