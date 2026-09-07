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

## Notes
- Strict mode treats missing/invalid `metadata.file_path` as data-integrity failure.
- Startup audits catalog integrity and quarantines invalid datasets (including legacy invalid samples).
