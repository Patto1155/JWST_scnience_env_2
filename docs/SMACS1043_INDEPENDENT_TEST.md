# SMACS 1043: frozen independent-reduction test blocked by calibration budget

**No new calibrated repeat measurement was obtained.** The currently selected
required dark reference exceeds the frozen transfer allowance by itself.
The historical compact patch is not physically rejected by this result.
Proposal to the coordinator: **Unconfirmed lead**, with no promotion controls
claimed. This report does not edit the authoritative state files.

## Freeze and executed acquisition

Design [E_SMACS1043_DESIGN.md](frozen/E_SMACS1043_DESIGN.md) was committed as
`90110ef1913beff9d8537f5fc05361655cbdee6f` at 2026-10-14 01:27:10 UTC.
It remains unchanged. Measurements were held until the coordinator reported
that the integrated Phase 1 gate passed. New acquisitions used only the
fixed SMACS exposure identities; GOODS-N was not opened.

Both actual raw UNCAL products were downloaded with hard per-product ceilings,
hashed and verified from FITS headers. First completed new raw acquisition:
01:33:45.176279 UTC. Header access did not measure any science-array values.
The first official datamodel open started at 01:36:53.930331 UTC, after freeze;
this supplied CRDS selection metadata, not target photometry.

| Raw product | Complete body bytes | SHA256 |
|---|---:|---|
| jw02736001001_02105_00003_nrcalong_uncal.fits | 75,556,800 | 4711e54967820c8dc86811ecd3fbf813fd18806012fa397b1e6ad34910ac81e4 |
| jw02736001001_02105_00004_nrcalong_uncal.fits | 75,556,800 | 5bd6819845c9b9be341b7a677f55eabc0885683f903fce72c4030ca9fd4c5d8d |

Headers confirm NRCALONG/F444W, MEDIUM8, one integration of eight groups,
837.468 s effective exposure, and midpoints MJD 59737.24766954861 and
59737.25835620370. These are distinct integrations in the historical same visit,
not new epochs. Exact public URLs, retrieval times, byte counts, hashes and
HTTP metadata are in [raw download receipts](../research_output/session_20261014/e_raw_downloads.json).
[Header summaries](../research_output/session_20261014/e_raw_headers.json)
retain only metadata; no raw arrays enter git.

## Current reference gate and stopping decision

An isolated official pipeline environment was installed: JWST 3.0.0,
CRDS 14.0.3 and photutils 3.0.0. Installing the then-default photutils 3.1.0
initially broke the official pipeline import (`DEFAULT_COLUMNS` missing);
pinning 3.0.0 fixed that import. The shared test environment was not changed.
The full isolated software snapshot is [recorded here](../research_output/session_20261014/e_pipeline_requirements.txt).

The official remote CRDS selector returned **jwst_1596.pmap**, different from
the historical **jwst_1535.pmap**. Its matching raw-product parameters and
reference names are in [the selector receipt](../research_output/session_20261014/e_crds_remote.json).
The current required dark is **jwst_nircam_dark_0424.fits**.
An official CRDS HEAD response returned HTTP 200 and Content-Length
**4,378,878,720 bytes**. No dark-reference body was downloaded.

| Budget item | Bytes |
|---|---:|
| Frozen science/reference transfer cap | 1,610,612,736 |
| Complete raw bodies acquired | 151,113,600 |
| Required current dark reference alone | 4,378,878,720 |
| Current selected references, summed HEAD lengths | 4,732,087,416 |
| Raw plus current selected reference bodies, planned minimum | 4,883,201,016 |

All selected reference identities, exact URLs, successful HEAD statuses and
lengths are in [reference probes](../research_output/session_20261014/e_reference_heads.json).
Even the dark alone is over the cap, so the immutable design's calibration and
budget gate stops the experiment **before Detector1/Image2 reprocessing**.
The frozen promotion decision is blocked, not a measured astrophysical null.
This is a statement about the current selector/context and frozen acquisition
path; no exhaustive search over all CRDS contexts, old dark references, cached
resources or possible pipeline paths was performed.

MAST same-position cone queries via POST and GET both timed out. Their explicit
failure receipts are [preflight](../research_output/session_20261014/e_metadata_preflight.json)
and [GET retry](../research_output/session_20261014/e_cone_get_retry.json).
Other-epoch coverage remains unknown; the timeouts do not establish absence.

## Cleanup and accounting limits

After retaining hashes, headers and dependency receipts, all raw cache contents
were deleted at 01:40:39 UTC. The [cleanup receipt](../research_output/session_20261014/e_cleanup.json)
confirms zero remaining files. It also records an unattributed 60,293,120-byte
temporary file found after download completion. Because its transfer provenance
could not be established, it is conservatively charged at one additional full
raw product: **75,556,800 bytes**. The conservative science transfer charge is
therefore **226,670,400 bytes**, below the cap. Complete-product receipts account
for exactly 151,113,600 bytes; wire-level retries are not fully instrumented.

CRDS's initial local mapping sync was interrupted and replaced with remote
metadata selection. Cached mapping bodies total 48,854 bytes and are individually
hashed in the cleanup receipt. CRDS RPC response wire totals were not instrumented;
no claim of exact all-network accounting is made. No scientific calibration
reference bodies, mosaics, GOODS-N data or additional epochs were downloaded.

## Reproduction and not run

Replay the dependency verdict entirely from compact receipts:

```bash
python -m discovery.smacs_raw_gate \
  --receipt-dir research_output/session_20261014 \
  --output /tmp/e_smacs_verdict.json
python -m pytest -q tests/test_smacs_raw_preflight.py tests/test_smacs_raw_gate.py
```

The replay yields [the recorded verdict](../research_output/session_20261014/e_verdict.json),
including receipt hashes and absent control artifacts. Twelve focused tests pass;
new modules/tests pass ruff. These tests protect budget/identity handling and
dependency verdicts; they validate no sky measurement. The metadata-only network
preflight is `python -m discovery.smacs_raw_preflight --output /tmp/e_metadata.json`.
It does not perform photometry or restore/reduce the raw images.

**Not run:** Detector1 or Image2 reduction; calibrated forced photometry;
compact-centroid association; held-out frame calibration; the four frozen
structured-light null tests; measured same-field PSF calibration; positive and
negative injection recovery; other-epoch forced photometry; dropout, redshift,
source identity or variability inference. No null-control, injection-recovery
or independently reduced repeat artifact exists for promotion.
