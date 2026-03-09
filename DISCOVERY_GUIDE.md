# Science OS Discovery Guide

## How to Make Real Discoveries with Science OS



### Quick Start

```bash
# 1. Start the API server (if not already running)
python run_api.py

# 2. View agent's complete thinking process
python discovery/trajectory_viewer.py 27

# 3. Run a research campaign (5 questions at once)
python discovery/batch_runner.py photometry

# 4. Submit custom batch of questions
python discovery/batch_runner.py
```

---

## Part 1: Getting Real JWST Data

### Option A: Download from MAST Archive

```bash
# Install astroquery
pip install astroquery astropy

# Download real JWST data
python data_pipeline/download_jwst_data.py

# Register downloaded datasets
python data_pipeline/register_datasets.py
```

### Option B: Use Your Own FITS Files

1. Place FITS files in `data/jwst/`
2. Run: `python data_pipeline/register_datasets.py`
3. Datasets will auto-register with metadata extracted from headers

### Check Available Datasets

```bash
curl http://localhost:8000/datasets/
```

---

## Part 2: Scaling Up Discoveries

### Strategy 1: Run Research Campaigns

Pre-designed campaigns with 5 focused questions each:

```bash
# Photometry campaign - measure sources
python discovery/batch_runner.py photometry

# Morphology campaign - understand structure
python discovery/batch_runner.py morphology

# Quality assessment campaign
python discovery/batch_runner.py quality

# Systematic effects search
python discovery/batch_runner.py systematic
```

Each campaign runs 5 questions in parallel and saves results to `discovery/[campaign]_results.json`

### Strategy 2: Custom Batch Submissions

Create your own question list:

```python
from discovery.batch_runner import batch_submit, wait_for_completion, save_results

questions = [
    "Identify variable sources by comparing brightness at different positions",
    "Search for transient objects not present in archival data",
    "Characterize the color distribution of sources in this field",
    # ... add 20+ more
]

run_ids = batch_submit(questions, datasets=["jwst_ngc1365_f200w"])
results = wait_for_completion(run_ids)
save_results(results)
```

### Strategy 3: Multi-Dataset Comparison

```python
from discovery.batch_runner import submit_research_question

# Compare same object in different filters
filters = ["jwst_ngc1365_f200w", "jwst_ngc1365_f356w", "jwst_ngc1365_f444w"]

for filter_data in filters:
    submit_research_question(
        "What is the average source brightness and how does it compare to background?",
        datasets=[filter_data]
    )
```

### Strategy 4: Supervisor-Worker Campaigns

Use a cheap worker model to triage many candidates, then escalate only the most
interesting outputs to a larger judge model:

```bash
python discovery/build_universe_table.py
```

This regenerates the source frontier and proposal metadata:

- `research_output/highz_shortlist.json`
- `research_output/highz_validation_top10.json`
- `research_output/proposal_channel_summary.json`

Then run a campaign:

```bash
python discovery/supervisor_campaign.py \
  --max-candidates 8 \
  --worker-model qwen/qwen3-next-80b-a3b-thinking
```

Each session writes:

- `research_output/supervisor_sessions/<session_id>/event_stream.jsonl`
- `research_output/supervisor_sessions/<session_id>/live_state.json`
- `research_output/supervisor_sessions/<session_id>/session_manifest.json`
- `research_output/supervisor_sessions/<session_id>/operator_inbox.jsonl`
- `research_output/supervisor_sessions/<session_id>/supervisor_outbox.jsonl`
- `research_output/supervisor_sessions/<session_id>/worker_results.json`
- `research_output/supervisor_sessions/<session_id>/judge_report.json`

Worker runs use `constraints.allowed_tools` to stay on the narrow JWST triage
surface, and each worker result tracks its own `tool_call_count`.

`event_stream.jsonl`, `live_state.json`, and `session_manifest.json` are the
intended local GUI/control boundary. `operator_inbox.jsonl` and
`supervisor_outbox.jsonl` are the provision for a later lightweight chat/control
loop between the GUI and the supervisor.

Open that GUI with:

```bash
python discovery/supervisor_dashboard.py --open-browser
```

The browser dashboard is the main GUI for supervisor campaigns. It now shows:

- worker portfolio bucket and primary proposal channel
- proposal frontier summary from `proposal_channel_summary.json`
- structured worker detail cards instead of raw JSON dumps
- a last-refresh timestamp so you can tell whether the page is stale

For the full dashboard workflow, see `SUPERVISOR_GUI_GUIDE.md`.

### Terminal Monitor (for core API runs)

For monitoring raw API runs (not supervisor campaigns), use the Rich terminal dashboard:

```bash
python discovery_monitor.py 42 43 44
```

This shows live tool call counts, reflection tracking, duration timers, and findings
previews in a rich terminal UI that updates every 2 seconds. It is automatically
invoked by `run_discovery.py` unless you pass `--no-live`.

---

## Part 3: Viewing Agent Thinking

### See Complete Trajectory

```bash
# View full thinking process
python discovery/trajectory_viewer.py 27

# Export to readable markdown
python discovery/trajectory_viewer.py 27 --export

# Compare multiple runs
python discovery/trajectory_viewer.py --compare 27 28 29
```

### What You'll See

1. **User message** - The research objective
2. **Agent reasoning** - LLM's thought process and decisions
3. **Tool calls** - Which tools the agent chose and why
4. **Tool results** - Observations from each tool execution
5. **Iterations** - How agent refined approach based on results
6. **Final findings** - Synthesized conclusions

---

## Part 4: Discovery Workflow

### The Scientific Discovery Loop

```
1. Define Research Questions (10-50 questions)
        ↓
2. Batch Submit to Science OS
        ↓
3. Agents Work Autonomously (~20 seconds each)
        ↓
4. Collect Results
        ↓
5. Analyze Patterns Across Runs
        ↓
6. Generate New Questions Based on Findings
        ↓
7. REPEAT
```

### Current JWST Batch Outputs

The source-level JWST pipeline now produces:

- `research_output/universe_table_summary.json`
- `research_output/highz_candidates.json`
- `research_output/highz_shortlist.json`
- `research_output/highz_validation_top10.json`
- `research_output/anomaly_catalog.json`
- `research_output/visuals/*`
- `research_output/source_catalogs/*`

Use `highz_shortlist.json` first when reviewing results. It is the falsification-aware shortlist built from validation score, aperture consistency, red-band S/N, coverage, blue-band detectability, and edge distance.

### Current Recommended Review Order

1. Rebuild the source-level outputs:
```bash
python discovery/build_universe_table.py
```
2. Open `research_output/proposal_channel_summary.json` to confirm the frontier is not saturated by one channel
3. Open `research_output/highz_shortlist.json`
4. Inspect `validation_score`, `validation_status`, `primary_channel`, `portfolio_bucket`, `completeness_score`, `keep_reasons`, and `reject_reasons`
5. Review the linked evidence sidecars and panels in `research_output/visuals`
6. Only then dig into the much larger `highz_candidates.json`

### Supervisor Campaign Troubleshooting

- If a local supervisor run fails on `POST /runs/validate` with `405 Method Not Allowed`, restart the API with `python run_api.py` and retry. That indicates an older server process is still running.
- If the browser dashboard shows workers but every worker lands in `failed_strict_validation`, inspect dataset catalog `metadata.file_path` entries and confirm the referenced FITS files exist on disk. That failure blocks meaningful higher-volume experimentation even if the GUI itself is healthy.

### Example: Finding Rare Objects

```python
# Round 1: Broad survey
questions_r1 = [
    "What is the brightness distribution? Are there outliers?",
    "Identify the 5 brightest sources",
    "Are there any unusual spectral energy distributions?",
]

# Round 2: Follow-up on findings
# (Based on Round 1 identifying bright outlier at position X,Y)
questions_r2 = [
    "Perform detailed photometry on source at position (X, Y)",
    "Compare this source to similar brightness sources elsewhere",
    "Is there variability or time-domain behavior?",
]

# Round 3: Characterization
questions_r3 = [
    "What is the morphology of this unusual source?",
    "Measure color indices across all filters",
    "Compare to known object catalogs",
]
```

---

## Part 5: Maximizing Discoveries

### 1. **Ask Specific, Testable Questions**

✓ GOOD: "Is there a correlation between source brightness and distance from field center?"
✗ BAD: "Analyze the data"

✓ GOOD: "Identify sources with color index (F200W - F356W) > 2.0"
✗ BAD: "Find interesting things"

### 2. **Use Constraints Wisely**

```python
# For quick surveys
constraints = {"max_steps": 5}

# For deep analysis
constraints = {"max_steps": 20, "max_cost": 5.0}
```

### 3. **Run in Parallel**

Submit 10-50 questions at once. Each runs independently in ~15-30 seconds.

```python
# Submit 50 questions - total time ~30 seconds (not 25 minutes!)
run_ids = batch_submit(fifty_questions)
```

### 4. **Iterate Based on Results**

Don't just run once. Let discoveries guide next questions:

1. Run 10 broad questions
2. Find anomaly
3. Run 10 focused questions on anomaly
4. Characterize finding
5. **Publish discovery!**

### 5. **Cross-Reference Results**

Compare findings across multiple runs:

```python
from discovery.trajectory_viewer import compare_trajectories

# See which runs found similar patterns
compare_trajectories([27, 28, 29, 30, 31])
```

---

## Part 6: Real Discovery Examples

### Discovery Pattern: Transient Detection

```python
questions = [
    "Compare brightness statistics to archival observations",
    "Identify sources present in this epoch but not in archival data",
    "Search for sources with unusual brightness variability",
    "Flag any sources with non-stellar morphology appearing since last observation",
]
```

### Discovery Pattern: Rare Object Finding

```python
questions = [
    "Identify the 3-sigma outliers in the brightness distribution",
    "Find sources with extreme color indices (> 2 sigma from mean)",
    "Detect asymmetric or peculiar morphologies",
    "Flag sources with unexpected photometric properties",
]
```

### Discovery Pattern: Systematic Studies

```python
# Run on 100 different targets
for target in target_list:
    submit_research_question(
        f"Measure the stellar mass function for {target}",
        datasets=[f"jwst_{target}_f200w"]
    )
```

---

## Part 7: Performance Optimization

### Current System Limits

- Max steps per run: 50
- Max cost per run: $10
- Typical run time: 15-30 seconds
- Parallel capacity: Limited only by API rate limits

### Scaling to 1000s of Runs

```python
# Submit in batches to avoid overwhelming system
import time

all_questions = [...]  # 1000 questions

batch_size = 50
for i in range(0, len(all_questions), batch_size):
    batch = all_questions[i:i+batch_size]
    run_ids = batch_submit(batch)
    time.sleep(60)  # Wait for batch to complete
```

---

## Part 8: Next-Level Discoveries

### Add Your Own Tools

Create specialized analysis tools in `tools/jwst/`:

```python
# tools/jwst/advanced_analysis.py
def detect_variable_sources(image_data_t1, image_data_t2):
    """Compare two epochs to find variables"""
    # Your algorithm here
    return {"variable_sources": [...]}
```

Register in `core_api/startup.py` and the agent can use it automatically!

### Multi-Wavelength Analysis

```python
# Combine data from different instruments
submit_research_question(
    "Compare morphology between NIRCam F200W and MIRI F770W",
    datasets=["jwst_target_nircam_f200w", "jwst_target_miri_f770w"]
)
```

### Time-Domain Discoveries

```python
# Analyze multiple epochs
epochs = ["epoch1", "epoch2", "epoch3"]

for i, epoch in enumerate(epochs):
    submit_research_question(
        f"Measure photometry of all sources in epoch {i+1}",
        datasets=[epoch]
    )

# Then compare
submit_research_question(
    "Identify sources showing > 0.5 mag variability across epochs",
    datasets=epochs
)
```

---

## Get Started Now!

```bash
# 1. Run your first campaign
python discovery/batch_runner.py photometry

# 2. View the agent's thinking
python discovery/trajectory_viewer.py <run_id>

# 3. Start scaling up!
```

**The scientific method, automated and scaled. Go discover something!** 🔭
