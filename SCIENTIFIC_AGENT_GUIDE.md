# Scientific Research Agent Guide

## What Changed

The system now uses a **ScientificResearchAgent** that thinks deeper and follows the scientific method rigorously.

---

## How It Works Differently

### Old Agent (Basic)
```
Question → Tool Call → Tool Call → Tool Call → Finish
(~3-5 tool calls, ~15 seconds)
```

### New Agent (Scientific)
```
Question
  ↓
Hypothesis Formation
  ↓
Experimental Design
  ↓
Tool Call 1 → Observe
  ↓
REFLECTION (What does this mean?)
  ↓
Tool Call 2 → Observe
  ↓
REFLECTION (Patterns? Alternative explanations?)
  ↓
Tool Call 3 → Observe
  ↓
DEEP ANALYSIS (Compare all observations)
  ↓
CONCLUSION (Evidence-based, with uncertainties)

(~5-10 tool calls + reflections, ~30-60 seconds)
```

---

## Key Features

### 1. Reflection After Each Observation

The agent now has a third action type: `{"action": "reflect"}`

After each tool result, it can (and is encouraged to) reflect:
```json
{
  "action": "reflect",
  "thoughts": "The mean brightness of 0.023 is lower than expected.
              This could indicate either low surface brightness sources
              or poor sensitivity. I should measure specific regions
              to test which explanation is correct."
}
```

Reflections **don't count against the step limit** - encouraging deeper thinking!

### 2. Scientific Method Prompting

The system prompt now explicitly guides the agent through:

1. **HYPOTHESIS**: Form testable hypotheses
2. **DESIGN**: Plan measurements
3. **OBSERVE**: Collect data via tools
4. **REFLECT**: Think about meaning
5. **ANALYZE**: Find patterns
6. **CONCLUDE**: Draw evidence-based conclusions

### 3. Reasoning Required

Every tool call must include reasoning:
```json
{
  "action": "tool_call",
  "tool_name": "image_statistics",
  "parameters": {...},
  "reasoning": "Need baseline statistics to establish if outliers are significant"
}
```

### 4. More Context

- Old: Last **10** messages
- New: Last **20** messages

Allows agent to remember and connect more observations.

### 5. Tool Results as User Messages

Tool results now appear as:
```
"OBSERVATION from image_statistics: mean=0.023, std=0.012..."
```

This reinforces that observations are data to be analyzed, not just function returns.

---

## Configuration

### Max Steps
Default: 30 steps (was 50)

More reflections mean fewer wasted tool calls. Quality over quantity.

Change in `core_api/config_scientific.py`:
```python
SCIENTIFIC_MAX_STEPS = 30
```

### Max Cost
Default: $15 (was $10)

Deeper thinking uses more tokens but produces better science.

---

## Example Trajectory Comparison

### Old Agent Trajectory
```
[1] USER: Analyze brightness distribution
[2] AGENT: {"action": "tool_call", "tool_name": "image_statistics", ...}
[3] TOOL: mean=0.023, std=0.012
[4] AGENT: {"action": "tool_call", "tool_name": "extract_photometry", ...}
[5] TOOL: flux=245.6
[6] AGENT: {"action": "finish", "findings": "Mean is 0.023, found source with flux 245.6"}
```
Total: 3 steps, minimal analysis

### New Scientific Agent Trajectory
```
[1] USER: Analyze brightness distribution
[2] AGENT: I'll investigate systematically.
    HYPOTHESIS: If this is a typical galaxy field, brightness should follow
    a log-normal distribution with possible bright outliers from point sources.

    {"action": "tool_call", "tool_name": "image_statistics",
     "reasoning": "Establish baseline distribution parameters"}

[3] TOOL: OBSERVATION from image_statistics: mean=0.023, std=0.012, min=0.001, max=0.089

[4] AGENT: {"action": "reflect", "thoughts": "The mean of 0.023 with std 0.012 shows
    ~50% relative variation - quite high. The max of 0.089 is 3.7x the mean, suggesting
    outliers. I should sample different regions to see if this is uniform or if there
    are bright concentrations."}

[5] AGENT: {"action": "tool_call", "tool_name": "extract_photometry",
     "parameters": {"x": 256, "y": 256, "aperture_radius": 5},
     "reasoning": "Sample central region to test for spatial variation"}

[6] TOOL: OBSERVATION from extract_photometry: flux=573.2, magnitude=18.7

[7] AGENT: {"action": "reflect", "thoughts": "Central flux of 573.2 is much higher than
    the field mean, confirming non-uniform distribution. Let me check corners."}

[8] AGENT: {"action": "tool_call", "tool_name": "extract_photometry",
     "parameters": {"x": 100, "y": 100, "aperture_radius": 5},
     "reasoning": "Test corner region for comparison"}

[9] TOOL: OBSERVATION from extract_photometry: flux=234.1

[10] AGENT: {"action": "reflect", "thoughts": "Corner shows ~2.4x less flux than center.
     This gradient is significant. Let me quantify it across multiple positions."}

... more measurements and analysis ...

[18] AGENT: {"action": "finish", "findings": "Analysis reveals:
     1. Non-uniform brightness with 2.4x center-to-edge gradient (p<0.01)
     2. Log-normal base distribution (mean=0.023, σ=0.012)
     3. 3 sources exceed 3σ threshold, likely point source contaminants
     4. Gradient suggests either vignetting or real extended emission

     RECOMMENDATION: Flat-field correction needed before photometry.
     UNCERTAINTY: ±15% from limited sampling (N=8 positions)"}
```
Total: 12 steps, rigorous analysis with quantified uncertainties

---

## How to Use

### Restart API Server

The new agent is already integrated! Just restart:

```bash
# Kill old server
Ctrl+C

# Start with new scientific agent
python run_api.py
```

### Submit Questions as Before

```bash
curl -X POST "http://localhost:8000/runs/" \
  -H "Content-Type: application/json" \
  -d '{
    "spec": {
      "objective": "Investigate brightness patterns in NGC 1365",
      "datasets": ["jwst_ngc1365_f200w"],
      "steps": null
    }
  }'
```

### View Enhanced Trajectories

```bash
python discovery/trajectory_viewer.py <run_id>
```

You'll now see:
- Hypothesis formation
- Reflection steps
- Reasoning for each tool call
- Deeper analysis
- Quantified conclusions

---

## Tuning the Agent

### Make It Think Even Deeper

Edit `runner/scientific_agent.py`, line 162:

```python
# Increase context window
for msg in self.messages[-30:]:  # Was 20, now 30
```

### Require More Measurements

Edit system prompt to add:
```
- Require at least 5 measurements before concluding
- Always compute statistical significance
- Quantify all uncertainties
```

### Add Domain Knowledge

Inject astronomical priors:
```python
system_prompt = f"""...

ASTRONOMICAL PRIORS:
- JWST NIRCam PSF FWHM ~0.06 arcsec at 2μm
- Typical galaxy surface brightness ~23 mag/arcsec²
- Cosmic ray rate ~1 per exposure per 1000 pixels
- ...

{self._format_tools_for_llm()}
"""
```

---

## What You Get

### Better Science
- Hypothesis-driven investigation
- Multiple lines of evidence
- Quantified uncertainties
- Statistical rigor

### Reproducible Process
- Clear reasoning at each step
- Explicit assumptions stated
- Alternative explanations considered

### Publishable Results
- Evidence-based conclusions
- Quantified confidence levels
- Limitations acknowledged
- Testable predictions made

---

## Example Questions That Benefit

### Before (Basic Agent)
"What is the brightness?" → "Mean is 0.023"

### Now (Scientific Agent)
"What is the brightness?" →
- "I hypothesize brightness varies spatially due to vignetting"
- "Measured 8 positions systematically"
- "Found 2.4x gradient (p=0.003)"
- "Alternative explanation: extended source - testing..."
- "Conclusion: Vignetting + point sources (confidence 85%)"

---

## Next: Real Data Integration

Now that thinking is deeper, let's connect real JWST data:

```bash
# Install dependencies
pip install astroquery astropy

# Download real observations
python data_pipeline/download_jwst_data.py

# Register them
python data_pipeline/register_datasets.py

# Run scientific analysis on REAL data!
```

The scientific agent will now apply rigorous methodology to actual JWST observations!

---

**The scientific method, automated with deep thinking. Real discoveries await.** 🔬
