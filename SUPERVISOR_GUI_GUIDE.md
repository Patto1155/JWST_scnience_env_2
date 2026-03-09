# Supervisor GUI Guide

`discovery/supervisor_dashboard.py` is the main browser GUI for supervisor campaigns.

It is the preferred way to watch high-volume supervisor experimentation live.

## Purpose

It reads the session telemetry written by `discovery/supervisor_campaign.py`:

- `research_output/supervisor_sessions/<session_id>/live_state.json`
- `research_output/supervisor_sessions/<session_id>/event_stream.jsonl`
- `research_output/supervisor_sessions/<session_id>/session_manifest.json`
- `research_output/supervisor_sessions/<session_id>/operator_inbox.jsonl`
- `research_output/supervisor_sessions/<session_id>/supervisor_outbox.jsonl`

That means the GUI stays simple:

- no database dependency
- no API dependency
- no frontend build step
- easy to replace later with a richer UI

## Quick Start

1. Rebuild the candidate frontier so the dashboard has fresh proposal metadata:

```bash
python discovery/build_universe_table.py
```

This refreshes:

- `research_output/highz_shortlist.json`
- `research_output/highz_validation_top10.json`
- `research_output/proposal_channel_summary.json`
- `research_output/visuals/*`

2. Run a supervisor campaign:

```bash
python discovery/supervisor_campaign.py --max-candidates 8
```

3. In another terminal, launch the dashboard:

```bash
python discovery/supervisor_dashboard.py --open-browser
```

4. If you want to lock onto one session:

```bash
python discovery/supervisor_dashboard.py --session-id supervisor_20260308_123456 --open-browser
```

5. For repeated high-volume local experiments, keep the dashboard open and launch campaigns with different worker budgets:

```bash
python discovery/supervisor_campaign.py --max-candidates 12 --top-k-judge 4
python discovery/supervisor_campaign.py --max-candidates 20 --skip-judge
```

## What You See

- Session selector for all known supervisor campaigns
- Live session metadata plus a last-refresh timestamp
- Worker table with status, verdict, confidence, interestingness, primary proposal channel, and portfolio bucket
- Worker tool-count tracking via each worker's `tool_call_count`
- Proposal frontier summary panel driven by `proposal_channel_summary.json`
- Event timeline showing supervisor and worker messages
- Selected worker detail card with:
  - proposal channel and bucket
  - completeness and novelty
  - filter measurability
  - falsification and disqualifying flags
  - expandable raw JSON only when needed
- Minimal operator inbox hook for later supervisor chat/control

## Why This Helps

The dashboard is already aligned with a future richer GUI because the campaign
runner writes structured session telemetry instead of raw terminal text.

If you later replace this with a React or FastAPI UI, keep these files as the
stable session boundary:

- `live_state.json` for the latest snapshot
- `event_stream.jsonl` for append-only timeline playback
- `session_manifest.json` for session metadata and artifact pointers
- `operator_inbox.jsonl` for GUI-to-supervisor notes
- `supervisor_outbox.jsonl` for supervisor/judge replies or status messages

## Notes

- The page auto-refreshes every 2 seconds.
- The refresh timestamp next to the button is the easiest way to confirm the dashboard is still live.
- It only serves local files from the supervisor session directory.
- It now includes a minimal operator note endpoint, but it does not yet change the running supervisor logic.
- The proposal summary panel is only populated after `python discovery/build_universe_table.py` has written `research_output/proposal_channel_summary.json`.
- If `python discovery/supervisor_campaign.py ...` returns `405 Method Not Allowed` on `/runs/validate`, restart the local API (`python run_api.py`). That means the running server is stale relative to the current source tree.
- If workers appear in the GUI but all fail immediately with `failed_strict_validation` or `STRICT_DATA_LOAD_FAILURE`, inspect the referenced dataset `metadata.file_path` values before scaling up. The dashboard will still render proposal metadata, but the worker loop is not actually exercising JWST tools successfully.
