# Live Monitoring Guide

Beautiful real-time terminal dashboard showing what agents are doing as they explore.

---

## Quick Start

```bash
python run_discovery.py              # Auto-launches live dashboard
python run_discovery.py --runs 3     # Monitor 3 agents at once
python run_discovery.py --no-live    # Disable (simple text)
```

---

## What You See

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🔭 JWST Deep Discovery Monitor                            ┃
┃ ⏱️  Session time: 0:02:34 | Runs: 3                       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

╭─────────────── Active Discovery Runs ───────────────╮
│  ID  │ Status    │ Tools │ Duration │ Last Action   │
├──────┼───────────┼───────┼──────────┼───────────────┤
│ 123  │ 🔄 RUN   │   12  │  45.2s   │ 🔧 extract... │
│ 124  │ ✅ DONE  │   28  │ 134.7s   │ ✅ Finished   │
╰──────────────────────────────────────────────────────╯

╭──── Stats ────╮   ╭────── Recent Findings ──────╮
│ Completed: 1  │   │ Run 124: 28 tools          │
│ Running: 1    │   │ Found 12 new candidates... │
│ Total: 40     │   │                            │
╰───────────────╯   ╰────────────────────────────╯
```

**Updates every 2 seconds** showing:
- Live tool call counts
- What each agent is doing RIGHT NOW
- Duration timers
- Findings as they emerge

---

## Key Metrics

- **Tools**: Number of experiments run (target: 20-50)
- **Duration**: Wall-clock time
- **Last Action**: Latest tool call or thought
- **Status**: 🔄 Running | ✅ Done | ❌ Failed

---

## Usage

### Monitor Existing Runs
```bash
python discovery_monitor.py 42 43 44
```

### Disable Live Mode
```bash
python run_discovery.py --no-live   # Simple text output
```

---

## Tips

1. **Make terminal wide** (120+ columns)
2. **Watch reflections** - high count = thoughtful agent
3. **Compare multi-agent runs** - see different strategies side-by-side
4. **Take screenshots** - shows discovery in action

---

That's it! Live monitoring makes agent exploration **visible and beautiful**. 🎨
