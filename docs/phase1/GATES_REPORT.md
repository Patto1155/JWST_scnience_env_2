# Phase 1 gates and entrypoint repairs — 2026-10-14

No astrophysical grades changed by this worker. The coordinator owns the canonical state files.

## Implemented

- `scripts/quality_gate.py` discovers Python modules through whole-tree Ruff `E,F,I` checks. `scripts/lint_baseline.json` records 736 preexisting diagnostic occurrences from commit `a25d656`; keys include repository path, rule, message and source line. Moving a legacy line does not create debt; a new occurrence, changed offending line or new file cannot inherit its exemption. Removed diagnostics do not require retaining the old code. Ruff is pinned to 0.17.0 so its rules agree with the recorded baseline. The baseline is existing lint debt, not a clean-tree claim.
- Pytest emits a temporary JUnit report. Every skip/xfail is rejected unless its exact test identity and data-absence reason match one of the three explicit allowed entries. Allow-listed skips print `SKIP; NOT PASS`. A missing report fails closed. The gate prints persistent totals (tests, passes, failures, errors, skips) before removing its temporary report.
- `scripts/lint_ledger.py` checks the fixed six-grade scale, each evidence file and all supplied control paths. Candidate/Validated require null-control, injection-recovery and independent-repeat/holdout references. The linter verifies existence and declared roles; the lead researcher must still verify artifact contents and scientific sufficiency. Both the quality gate and an explicit CI step run it.
- `run_discovery.py` imports the existing `stream_discovery.DiscoveryStreamer`. Windows launchers enter their own directory; the missing streamer filename is corrected; the all-in-one launcher checks HTTP health status and starts a titled server window that its shutdown filter can address.
- Requirements declare `astroquery` and the Psycopg 3 binary driver. Docker uses the tested Python 3.12 version; Docker and example configuration use `core_api.app:app` and `postgresql+psycopg://`.
- Removed `core_api/config_scientific.py` and `core_api/_import_helper.py`: no Python imports were found. Historical hash receipts intentionally remain historical. Retained `runner.executor.ResearchAgent`: dedicated tests still import it.

## Executed verification

- Full offline suite after removing the unused modules and installing the new dependencies: **778 passing, three known data-absence skips, zero failures**. A preceding JUnit run recorded 781 tests, zero errors/failures and those same three skips in 20.612 seconds.
- New gate tests and retained legacy ResearchAgent tests: **16 passing**. Gate tests prove each missing control role fails for both Candidate and Validated, missing evidence fails, an unknown skip fails, a changed skip reason fails, and new-file/duplicate lint diagnostics do not inherit baseline exemptions.
- Whole-tree lint: zero new diagnostics against the recorded 736-occurrence original baseline. New scripts and tests pass unbaselined `E,F,I` lint.
- Existing focused mypy invocation: exit 0, three source files checked.
- Actual coordinator claim ledger at `../jwst/docs/CLAIM_LEDGER.md`: linter exit 0; all evidence references exist in this worktree.
- Launcher Python CLI `--help` succeeds; the streamer import is available and resolves to the actual class.
- Driver smoke check constructs the SQLAlchemy engine with `postgresql+psycopg` without opening a database connection. Installed dependency versions: astroquery 0.4.11; psycopg 3.3.6.

## Not run / not verified

- The full combined canonical `python scripts/quality_gate.py` and deliberately-added-skip full-gate proof await coordinator integration, because this worker is forbidden to create or edit `docs/CLAIM_LEDGER.md`. The component checks above were executed; this is not a whole-gate PASS claim.
- Windows `.bat` execution, Docker build/Compose startup and a live PostgreSQL round-trip were not run. Docker is not installed in this environment.
- No archive downloads, calibration replay, GOODS-N access, live API research runs, model calls, scientific outcome tests or independent astrophysical corroboration were performed.
- No evidence-content judgment or claim promotion is delegated to the linter.
