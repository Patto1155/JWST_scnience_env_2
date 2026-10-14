# Known-YSO time-domain pilot: frozen design and actual archive inventory

No new astrophysical result or promotion is claimed. Root owns grades.
The design was committed as93a1f07ad583b9743d79004878ed9fc1cd505f3a at
2026-10-14 01:27:30UTC, before new archive access. It remains unchanged.
First instrumented metadata access was01:30:38UTC. Phase1 green authorization
was received before the wavelength-only AA Tau science-product pilot.

## Actual current archive data

The authoritative completed two-release inventory is
`research_output/session_20261014/f_current/f_metadata_summary.json`.
Its21 successful official IRSA/SIMBAD response bodies total696,527bytes.
The current official overview explicitly documents QR2 and QR3 availability and
retirement of QR1. QR3-only screening initially missed earlier photons; that
limitation was corrected before interpretation. No outcomes selected targets.

| Fixed target | Unique QR2+QR3 physical exposures | Observation MJD range |
|---|---:|---|
|AA Tau|100|60914.728566–61282.929474|
|BP Tau|111|60912.554227–61280.483046|
|DG Tau|104|60913.641618–61282.659020|
|DR Tau|91|60916.289571–61281.974839|
|HL Tau|122|60913.025015–61282.518304|
|T Tau|106|60910.924986–61280.211118|

All six exact SIMBAD identities satisfy the frozen main-type identity gate.
These counts establish yearlong temporal feasibility, not source W1 coverage,
usable photometry, independent controls, or a new variability discovery.

## DDE 54 original-window continuation

Current QR3 returns exactly41 August exposures already in the historical input:
MJD61269.077387–61277.224458, zero new physical exposure IDs. Current QR2 returns
75 earlier exposures, MJD60906.239626–61097.897213. Only six enter the original
[61090,61310] confirmation window: four are same-pointing consecutive dithers.
Six physical source exposures supply at most six independent narrow channels,
less than the frozen eight-channel requirement for an additional qualifying
visit. No post-August photons are returned by these two release queries.
These newly inventoried older photons do not provide a qualifying second W1
visit. The exact original contract remains unmet; no window extension or period
fit was performed. DDE 54 remains an unconfirmed lead, pending root review.
Exact exposure IDs and dates are in `f_session_receipts.json`.

## AA Tau actual wavelength-only experiment

AA Tau is the first fixed target, with the same six-trial correction preserved.
The three chronological campaigns contain32,38,30frames, and **all100frames**
were measured from official source spectral WCS. The optimized two-range parser
first reproduced all13previously measured exposures at absolute1e-10 in source
x/y, wavelength and width, before accessing remaining exposures. This is an I/O
method verification, not independent astrophysical corroboration.

The executed slow/optimized acquisition code is preserved in commits `e16f74b` / `2b30537`; recorded code hashes bind those versions. Import-order cleanup after execution does not change the measurements. The reproducible scope arithmetic is `python -m discovery.research6_yso_scope`.

The optimized run finished in228.609seconds, consuming12,779,520exact range-body
bytes. Exact per-request URL, Content-Range, ETag, UTC, byte count and SHA256 are
retained in `f_aa_tau_fast_range_journal.jsonl`; reduced channels and source
positions are in `f_aa_tau_coverage_fast.json`. Raw ranges were erased after
reduction. The earlier slow run consumed4,662,400bytes and stopped after a
partial campaign in601.575seconds: a1.575second timing-budget breach. That run
is retained and disclosed, not represented as within budget. The optimized run
used a550second internal deadline and an external590second timeout.

Root adjudicated that the eight independent channels must support W1 within the
already declared source scope2.8–3.9microns. Whole-spectrum counts17/19/16 include
out-of-band D5 channels and are diagnostics only. No frozen file was edited.

| Campaign | Measured frames | Independent channels within W1 source scope | Within-scope W1 photon response | Coverage gate |
|---|---:|---:|---:|---|
|2025Aug (first)|32|7|90.9124%|fails eight-channel rule|
|2026Feb/Mar (middle)|38|8|99.6746%|spectral coverage passes|
|2026Aug (last)|30|7|97.8080%|fails eight-channel rule|

Only **one** campaign passes the spectral coverage gate; the frozen repeat-pair
requirement fails. The primary W1 variability statistic is **not estimable**.
This is an eligibility failure, not null variability. Pixel-quality, PSF-support,
noise, flux-calibration, null and injection requirements remain untested.
The authoritative scope verdict is `f_aa_tau_source_scope.json`.
An exploratory after-outcome1%-response channel diagnostic was examined, but
never became a decision rule; its counts6/7/6 must not be substituted for the
actual fixed-source-scope counts7/8/7.

AA Tau's exact AllWISE counterpart is J043455.42+242852.8, W1=7.447+/-0.036,
with clean W1 flag (and catalog saturation fraction0.077). The frozen control
cone contains14catalog objects. Excluding the target, one W1-flagged source and
known YSO associations leaves10identity/quality-eligible objects. All10nearest
Gaia matches pass the declared parallax/error and RUWE cuts. Ten actually usable
measured controls are **not** established, because no control photometry was run.
The object-by-object exclusions are in `f_control/f_aa_tau_adjudicated_controls.json`.

## All six fixed targets retained

The other five were screened in frozen order using identity/quality metadata,
not variability outcomes. Their clean-W1 other-source counts are upper bounds
before Gaia, YSO-association, coverage and pixel-quality cuts.

| Target | Maximum potential clean-W1 controls | Frozen minimum10 |
|---|---:|---|
|BP Tau|7|fails|
|DG Tau|3|fails|
|DR Tau|6|fails|
|HL Tau|0|fails|
|T Tau|0|fails|

No target was substituted, no magnitude/radius cut was widened, and multiplicity
remains six. None can advance under this design: AA lacks two qualifying W1
visits; the other five lack even ten potential matched controls. Their science
product measurements remain unexecuted. The catalog rows, actual queries and
receipts are in `f_other_controls/f_other_target_control_screen.json` and its
adjacent receipt files. This is a completed bounded feasibility verdict for
this design, not a finding that the objects are nonvariable or undiscoverable.

## Reproduction, accounting and limits

```
python -m discovery.research6_yso_pilot --timeout 25 --out research_output/session_20261014/f_current
timeout 590s python -m discovery.research6_yso_coverage_fast
python -m discovery.research6_yso_control_screen
python -m discovery.research6_yso_scope
python -m pytest -q tests/test_research6_yso_pilot.py
```

Eight focused tests and ten existing SPHEREx tests pass;
owned Ruff passes. Source-scope reduction follows the explicit2.8–3.9micron center cut, then the existing nonoverlapping-width and response-union method. Tests concern identity, release/exposure deduplication,
window protection, malformed responses and failed-response accounting; they
are not empirical astrophysical controls.

The initial instrumented metadata bodies total900,810bytes; later control screening is additionally charged in `f_final_acquisition_manifest.json`. The two actual science-range runs total17,441,920bytes. One initial documentation
probe has no recoverable tool/body receipt, so this is not a certified exact
entire-session byte total. A separate instrumented15s documentation timeout
received0bodybytes. Neither probe was used for science. The coverage budget
reserves1MB for the unreceipted probe; that reserve is an assumption, not a
measured upper bound. All exact retained receipts are in `f_session_receipts.json`.

Not run: synthetic W1 magnitudes or variability statistic; NEOWISE/ZTF outcome
lightcurves; matched field-star null; injections; flux photometry; science
product measurements for the other five targets; GOODS-N. No same-lineage
review is counted as independent astrophysical corroboration. No raw science
products are committed. No state files are edited.
