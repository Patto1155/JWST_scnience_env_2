# Tool Recipes (Science OS, Strict-Safe)

Purpose: practical runbook recipes for reliable JWST discovery runs with strict real-data guarantees and reusable evidence artifacts.

Primary operator docs:
- `DISCOVERY_GUIDE.md`
- `docs/JWST_DISCOVERY_INDEX.md`
- `docs/JWST_DISCOVERY_ROADMAP.md`

## Ground Truth
- Canonical dataset names come from `GET /datasets` (typically `jwst_*`).
- For strict workflows, prefer `GET /datasets?strict_ready=true` to avoid quarantined or invalid rows.
- Strict science mode is default in discovery flows (`constraints.strict_real_data=true`).
- `POST /runs/validate` is the required preflight check before queueing strict runs.
- Startup audits dataset catalog integrity and quarantines invalid entries.

## Non-Negotiable Rules
- Never rely on alias names like `SMACS-J0723.3-7327_F090W` in strict workflows.
- Missing or invalid `metadata.file_path` is a hard data-integrity failure.
- Strict runs must fail loudly; dummy fallback is never allowed silently.
- Use source ids and evidence bundles for candidate review, not adjacent bright-pixel peaks.

## Registered Tools (Current)
- `image_statistics(image_data, region=None, strict_data=None)`
- `brightness_distribution(image_data, bins=50, strict_data=None)`
- `compare_images(image1_data, image2_data, strict_data=None)`
- `extract_photometry(image_data, x, y, aperture_radius=5.0, background_annulus_inner_radius=6.0, background_annulus_outer_radius=10.0, strict_data=None)`
- `compute_color_index(flux_band1, flux_band2)`
- `detect_sources(image_data, threshold_sigma=3.0, min_pixels=9, deblend=True, top_n=50, border_margin=16, output_dir="catalogs", output_prefix=None, strict_data=None)`
- `candidate_evidence_bundle(reference_dataset, comparison_datasets, x=None, y=None, catalog_path=None, source_id=None, cutout_size=64, aperture_radii=[2,3,5], background_annulus_inner_radius=6.0, background_annulus_outer_radius=10.0, output_dir="visuals", output_prefix=None, strict_data=None)`
- `render_field_overview(image_data, catalog_path, highlight_source_ids=None, top_n=50, output_dir="visuals", output_prefix=None, strict_data=None)`
- `compute_mean(values)`

## Preflight Recipe (Required for Strict Runs)
1. Verify API + catalog:
- `python scripts/smoke_api.py`
- `curl -s "http://localhost:8000/datasets/?limit=20&strict_ready=true"`
2. Validate run payload before queueing:
- `curl -s -X POST http://localhost:8000/runs/validate -H "Content-Type: application/json" -d "{\"spec\":{\"objective\":\"Preflight\",\"datasets\":[\"<jwst_dataset_name>\"],\"steps\":null,\"constraints\":{\"strict_real_data\":true}}}"`
3. Only queue when `valid=true`.

## Source Discovery Recipe
1. Detect unique red-band sources:
- `detect_sources(image_data=<F444W dataset>, top_n=200, border_margin=16)`
2. Review source-level evidence:
- `candidate_evidence_bundle(reference_dataset=<F444W dataset>, comparison_datasets=[<F090W dataset>, <F200W dataset>], catalog_path=<catalog>, source_id=<id>)`
3. Confirm photometry numerically:
- `extract_photometry(..., aperture_radius=2)`
- `extract_photometry(..., aperture_radius=3)`
- `extract_photometry(..., aperture_radius=5)`
4. Compute color indices on positive background-subtracted fluxes:
- `compute_color_index(flux_band1=<blue flux>, flux_band2=<red flux>)`
5. Save a field summary for the shortlist:
- `render_field_overview(image_data=<F444W dataset>, catalog_path=<catalog>, highlight_source_ids=[...])`

## Candidate Vetting Heuristics
- Reference band: prefer `F444W` for source detection and ranking.
- Primary dropout proxy: `background_subtracted_flux(F090W, r=3) / background_subtracted_flux(F444W, r=3) < 0.05`.
- Batch rebuilds now attach falsification-aware triage fields to candidates:
- `validation_score`
- `validation_status`
- `keep_reasons`
- `reject_reasons`
- Require explicit quality review of:
- `coverage_fraction`
- `snr`
- `edge_distance_px`
- annulus background level and scatter
- evidence panel artifacts

## Preferred Batch Output Review Order
- `research_output/highz_shortlist.json`
- `research_output/highz_validation_top10.json`
- `research_output/highz_candidates.json`
- `research_output/visuals/*`
- `research_output/source_catalogs/*`

Treat `highz_shortlist.json` as the main entrypoint for follow-up review. It is scored using dropout strength, multi-aperture consistency, red-band S/N, blue-band detectability, coverage, and edge distance.

## Discovery CLI Recipes
- Validate only (no queue): `python run_discovery.py --dry-run-validate`
- Validate against isolated API: `python run_discovery.py --dry-run-validate --base-url http://127.0.0.1:8001`
- Strict run: `python run_discovery.py --runs 1 --steps 30`
- Strict run against isolated API: `python run_discovery.py --runs 1 --steps 30 --base-url http://127.0.0.1:8001`
- Non-strict debug only: `python run_discovery.py --allow-dummy`

## Strict Failure Signals
- API create/validate issues use stable codes like:
- `STRICT_DATASETS_REQUIRED`
- `STRICT_DATASET_NOT_FOUND`
- `STRICT_DATASET_FILE_PATH_INVALID`
- `STRICT_DATASET_FILE_MISSING`
- `STRICT_DATASET_QUARANTINED`
- Execution-time strict drift failures surface as:
- `STRICT_RUN_VALIDATION_FAILED`
- `STRICT_DATA_LOAD_FAILURE`

## Runtime Activity Signals
- Discovery runs now enforce:
- `min_successful_tool_calls=12`
- `min_reflections=2`
- Premature finishes fail loudly with:
- `AGENT_MINIMUM_ACTIVITY_NOT_MET`

## Troubleshooting
- `stuck_queued` with hints:
- check API process health (`python run_api.py`)
- inspect recent `/runs/{id}` `status_hints`
- restart API worker if queue is not advancing
- Strict dataset failures:
- repair `metadata.file_path`
- remove quarantine markers only after integrity is fixed
- re-run `POST /runs/validate`
- Source-level duplicates or weak evidence:
- re-run `detect_sources` with stricter `threshold_sigma` or larger `min_pixels`
- inspect `candidate_evidence_bundle` coverage and S/N panels before trusting a dropout
