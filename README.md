# Science OS (JWST Discovery)

Science OS is a FastAPI + runner stack for autonomous JWST discovery workflows with strict real-data enforcement.

## Quick Start
1. Install runtime deps:
```bash
python -m pip install -r requirements.txt
```
2. Start API:
```bash
python run_api.py
```
3. Smoke-check:
```bash
python scripts/smoke_api.py
```

## Strict Run Workflow (Recommended)
1. Inspect canonical datasets:
```bash
curl -s http://localhost:8000/datasets/?limit=20
```
2. Preflight validate:
```bash
curl -s -X POST http://localhost:8000/runs/validate \
  -H "Content-Type: application/json" \
  -d "{\"spec\":{\"objective\":\"Strict check\",\"datasets\":[\"<jwst_dataset>\"],\"steps\":null,\"constraints\":{\"strict_real_data\":true}}}"
```
3. Queue run only when `valid=true`:
```bash
curl -s -X POST http://localhost:8000/runs -H "Content-Type: application/json" -d @payload.json
```

## Discovery CLI
- Strict discovery run:
```bash
python run_discovery.py --runs 1 --steps 30
```
- Validation only (no queue):
```bash
python run_discovery.py --dry-run-validate
```
- Validation against isolated API:
```bash
python run_discovery.py --dry-run-validate --base-url http://127.0.0.1:8001
```
- Non-strict debug override:
```bash
python run_discovery.py --allow-dummy
```

## API Endpoints
- `GET /health`
- `GET /tools`
- `GET /datasets`
- `GET /runs`
- `GET /runs/{id}` (includes `status_reason` and `status_hints`)
- `POST /runs/validate` (preflight validation)
- `POST /runs` (queue execution)

## Quality Gates
Install dev deps:
```bash
python -m pip install -r requirements-dev.txt
```
Run lint/type/tests:
```bash
python scripts/quality_gate.py
```

## Candidate Audit (read before trusting any result)

Independent falsification pass over the committed candidate catalog. Pure
stdlib, no FITS access, no pipeline rerun:

```bash
python discovery/audit_candidates.py
```

It writes `research_output/CANDIDATE_AUDIT.md` and
`research_output/candidate_audit.json`, checking that the blue band was actually
measured at each source position, that the compared filters share sky, and what
each candidate's brightness is in physical units (AB mag from MJy/sr, with the
short-wave/long-wave pixel solid angle correction).

See `FINDINGS.md` for what the audit found in the shipped catalog and for an
honest assessment of what this pipeline can and cannot establish.

## Repeat-exposure vetting

A source present in one exposure and absent from an independent exposure of the
same sky in the same filter is a detector artifact, not an object. Single
exposures carry no cross-dither cosmic-ray rejection, so this check matters:

```bash
python discovery/multi_epoch.py --pairs-only   # what repeat coverage exists
python discovery/multi_epoch.py                # apply the veto to candidates
```

Verdicts are interpreted against the measured time baseline: a few hours rejects
cosmic rays but says nothing about astrophysical variability.

## Stage-2b artifact characterization

Two independent exposures of the same sky in the same filter form a labelled
truth set for detector artifacts that survived calibration:

```bash
python discovery/artifact_characterization.py --auto
```

Measured on JADES GOODS-S: **~15% of all 5-sigma detections in a single
Stage-2b exposure are not real sources** (32-39 per arcmin² per exposure), and
they separate cleanly from real sources in FWHM and peak-to-total flux. Results
in `research_output/ARTIFACT_CHARACTERIZATION.md`.

## Single-image artifact classifier

Repeat coverage does not exist for every band. The classifier is fitted to the
repeat-exposure truth set and rejects artifacts in a single image:

```bash
python discovery/artifact_classifier.py --train
```

Cross-validated ROC AUC **0.981** (sky-grouped folds, held-out visits 0.973 /
0.985). **It fails injection-recovery and must not be used on a high-redshift
search**: on F444W it falsely rejects 77% of unresolved sources and 89% of faint
unresolved sources. It is retained as a documented negative result. See
`research_output/ARTIFACT_CLASSIFIER.md` and `INJECTION_RECOVERY.md`.

## Injection-recovery

Measures what a cut actually costs the science sample, which a discrimination
metric cannot:

```bash
python discovery/injection_recovery.py --auto
```

## Ramp diagnostics

Classifies detector events from the up-the-ramp reads rather than from shape:

```bash
python discovery/ramp_diagnostics.py --exposure <dir>/<root>_ --sweep
```

Real sources sit at the linear-accumulation prediction (0.281 vs 0.25 expected),
artifacts at 0.694; ROC AUC 0.893. **Also not a safe cut**: uncorrected detector
non-linearity still makes it reject compact real sources ~4x more often than
extended ones. See `research_output/RAMP_DIAGNOSTICS.md`.

See `HANDOVER.md` for the measured footprint and epoch coverage of the current
archive, and for what this pipeline can realistically be used to discover.

## Notes
- Strict mode treats missing/invalid `metadata.file_path` as data-integrity failure.
- Startup audits catalog integrity and quarantines invalid datasets (including legacy invalid samples).
