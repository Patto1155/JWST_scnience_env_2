# Science OS: North Star Vision

## Vision

**Science OS is an autonomous research agent that, given a natural-language scientific question, iteratively thinks, calls tools over large datasets, and returns concise statistical findings and plots, without the user scripting the steps.**

Instead of requiring users to write experiment specifications or predefined pipelines, Science OS acts as an intelligent scientist that:
- Understands your question
- Explores available datasets and tools
- Plans its approach autonomously
- Executes tool calls iteratively
- Synthesizes results into clear findings
- Returns statistical summaries and visualizations

## User Story

**Example Question:** "How does the brightness distribution of NGC 1234 compare between F200W and F356W filters?"

**What Happens:**
1. The agent receives your question
2. It explores the dataset catalog to find NGC 1234 data
3. It identifies relevant tools (sampling, statistics, plotting)
4. It autonomously decides to:
   - Sample brightness values from both filters
   - Compute summary statistics (mean, median, std, percentiles)
   - Generate comparison plots (histograms, scatter plots)
   - Analyze the differences
5. It returns a concise report with:
   - Key statistical findings
   - Visualizations
   - Confidence intervals and limitations
   - No raw data dumps—only summaries

**You don't write any code or experiment specs.** You just ask the question.

## Core Principles

### 1. Autonomous Loop
The agent operates in an iterative loop:
- **Think**: Analyze the question and current state
- **Decide**: Choose next action (call tool, analyze, finish)
- **Toolcall**: Invoke appropriate tools with parameters
- **Observe**: Process tool results (summaries, stats, plots)
- **Repeat**: Continue until question is answered or limits reached

### 2. Token-Efficient Data Access
- Tools return **summaries**, not raw datasets
- Statistical summaries (mean, median, std, min, max, percentiles)
- Sample previews (first N rows) when needed
- Plot references (base64 PNG or paths) instead of full data
- The agent never requests full datasets—only compressed insights

### 3. Read-Only by Default, Sandboxed Writes
- Agents have read-only access to datasets
- Any writes (plots, intermediate results) go to sandboxed directories
- No direct filesystem manipulation
- All data access through registered tools

### 4. Reusability Across Questions
- Tools are generic and reusable
- Same tools work for different scientific questions
- No question-specific hardcoding
- Tools act as "data compressors" that transform large datasets into small summaries

### 5. Honest Uncertainty
- Agent reports limitations of sample-based analyses
- Includes confidence intervals when possible
- Acknowledges when data is insufficient
- Prefers robust conclusions over flashy ones

## What This Means for Implementation

- **No predefined experiment steps**: The agent decides what to do
- **Iterative exploration**: The agent can refine its approach based on intermediate results
- **Tool-based abstraction**: All data access goes through tools that return summaries
- **Guardrails**: Max steps, max cost, max runtime to prevent runaway loops
- **Trajectory tracking**: Full history of agent decisions and tool calls for debugging

## Current State vs. North Star

**Current State:**
- System requires predefined experiment specifications (JSON with fixed steps)
- Users must script the exact sequence of tool calls
- More like an "experiment runner" than an autonomous agent

**North Star:**
- Users ask natural language questions
- Agent autonomously plans and executes
- Returns findings without requiring user to script steps

**The refactor plan moves us from current state toward the North Star.**






