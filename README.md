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

## Notes
- Strict mode treats missing/invalid `metadata.file_path` as data-integrity failure.
- Startup audits catalog integrity and quarantines invalid datasets (including legacy invalid samples).
