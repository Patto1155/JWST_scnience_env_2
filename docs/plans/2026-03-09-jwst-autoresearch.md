# JWST Autoresearch Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a new standalone project `JWST_autoresearch` — a supervised multi-agent system that autonomously discovers what's scientifically interesting in JWST data, using OpenRouter API + a Karpathy-style outer loop.

**Architecture:** Karpathy-style outer loop (`run.py` + `program.md`) drives a Supervisor LLM that decomposes discovery goals into tasks for 5 specialized agents. Agents reuse `ScientificResearchAgent` from the JWST project as their inner loop. Anomaly detection (sigma clipping + catalog crossmatch) flags interesting findings; Supervisor reasons about which to pursue.

**Tech Stack:** Python 3.10+, OpenRouter API (OpenAI-compatible), astropy, astroquery, requests, rich (terminal output), sqlite3 (stdlib), arxiv/pyvo (literature/catalog search)

**Source to copy from:** `C:\Users\patri\Desktop\AI_Projects\JWST_scnience_env_2\`

---

## Task 1: Create Project Directory and Git Repo

**Files:**
- Create: `C:\Users\patri\Desktop\AI_Projects\JWST_autoresearch\` (directory)

**Step 1: Create directory and initialize git**
```bash
mkdir -p "C:/Users/patri/Desktop/AI_Projects/JWST_autoresearch"
cd "C:/Users/patri/Desktop/AI_Projects/JWST_autoresearch"
git init
```

**Step 2: Create .gitignore**
Create `C:\Users\patri\Desktop\AI_Projects\JWST_autoresearch\.gitignore`:
```
.env
__pycache__/
*.pyc
.venv/
findings/
runner_work/
*.fits
*.jpg
*.png
*.db
```

**Step 3: Commit**
```bash
git add .gitignore
git commit -m "chore: init repo"
```

---

## Task 2: Create Directory Structure

**Files:**
- Create: `agents/__init__.py`
- Create: `runner/__init__.py`
- Create: `tools/__init__.py`
- Create: `findings/.gitkeep`
- Create: `docs/plans/.gitkeep`

**Step 1: Create all package dirs + placeholder files**
```bash
mkdir -p agents runner tools findings docs/plans
touch agents/__init__.py runner/__init__.py tools/__init__.py findings/.gitkeep docs/plans/.gitkeep
```

**Step 2: Commit**
```bash
git add -A
git commit -m "chore: create package structure"
```

---

## Task 3: Copy and Adapt Runner Core from JWST Project

**Files:**
- Copy+modify: `runner/scientific_agent.py` (from JWST project)
- Copy: `runner/sandbox.py` (from JWST project)
- Copy: `runner/result_schema.py` (from JWST project)

**Step 1: Copy the three runner files**
```bash
cp "C:/Users/patri/Desktop/AI_Projects/JWST_scnience_env_2/runner/scientific_agent.py" runner/
cp "C:/Users/patri/Desktop/AI_Projects/JWST_scnience_env_2/runner/sandbox.py" runner/
cp "C:/Users/patri/Desktop/AI_Projects/JWST_scnience_env_2/runner/result_schema.py" runner/
```

**Step 2: Fix imports in runner/scientific_agent.py**
The file imports from `core_api` which won't exist in our new project. Update the imports at the top of `runner/scientific_agent.py`:

Replace:
```python
from runner.sandbox import Sandbox
from runner.result_schema import RunResult
from core_api.schemas.runs import Message
from core_api.config import (
    MAX_STEPS_PER_RUN,
    MAX_COST_PER_RUN,
    LLM_API_KEY,
    LLM_MODEL,
    LLM_API_URL,
    LLM_TEMPERATURE,
    OPENROUTER_API_KEY,
)
```

With:
```python
from runner.sandbox import Sandbox
from runner.result_schema import RunResult
from config import (
    MAX_STEPS_PER_RUN,
    MAX_COST_PER_RUN,
    LLM_API_KEY,
    LLM_MODEL,
    LLM_API_URL,
    LLM_TEMPERATURE,
    OPENROUTER_API_KEY,
    get_model_slug,
)

class Message:
    """Simple message dataclass."""
    def __init__(self, role: str, content: str, timestamp=None, tool_name: str = None):
        self.role = role
        self.content = content
        self.timestamp = timestamp
        self.tool_name = tool_name

    def model_dump(self):
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": str(self.timestamp) if self.timestamp else None,
            "tool_name": self.tool_name,
        }
```

Also remove the `get_model_slug` import from the try/except block inside `_call_llm` since it's now imported directly at the top.

**Step 3: Commit**
```bash
git add runner/
git commit -m "feat: copy runner core from JWST project"
```

---

## Task 4: Create config.py

**Files:**
- Create: `config.py`
- Create: `.env.example`

**Step 1: Create `config.py`**
```python
"""Configuration for JWST Autoresearch."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Guardrails
MAX_STEPS_PER_RUN = int(os.getenv("MAX_STEPS_PER_RUN", "30"))
MAX_COST_PER_RUN = float(os.getenv("MAX_COST_PER_RUN", "15.0"))

# Sandbox directory
SANDBOX_DIR = Path(os.getenv("SANDBOX_DIR", "./runner_work"))

# OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
LLM_API_KEY = OPENROUTER_API_KEY
LLM_API_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))

# Default model for supervisor and agents
LLM_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-3.5-sonnet")

# Supervisor model (can be different — cheaper/faster)
SUPERVISOR_MODEL = os.getenv("SUPERVISOR_MODEL", LLM_MODEL)

# Discovery loop budget
MAX_DISCOVERY_ITERATIONS = int(os.getenv("MAX_DISCOVERY_ITERATIONS", "10"))
SESSION_COST_BUDGET = float(os.getenv("SESSION_COST_BUDGET", "50.0"))

# Available OpenRouter model slugs
AVAILABLE_MODELS = {
    "claude-3.5-sonnet": "anthropic/claude-3.5-sonnet",
    "deepseek-v3": "deepseek/deepseek-chat",
    "gpt-4o": "openai/gpt-4o",
    "gemini-pro": "google/gemini-pro-1.5",
    "qwen3-72b": "qwen/qwen-2.5-72b-instruct",
}


def get_model_slug(model_name: str) -> str:
    """Get full OpenRouter slug from short name."""
    if "/" in model_name:
        return model_name
    return AVAILABLE_MODELS.get(model_name, model_name)
```

**Step 2: Create `.env.example`**
```bash
# Copy to .env and fill in your values
OPENROUTER_API_KEY=your_openrouter_key_here

# Optional overrides
LLM_MODEL=anthropic/claude-3.5-sonnet
SUPERVISOR_MODEL=anthropic/claude-3.5-sonnet
MAX_DISCOVERY_ITERATIONS=10
SESSION_COST_BUDGET=50.0
```

**Step 3: Commit**
```bash
git add config.py .env.example
git commit -m "feat: add config"
```

---

## Task 5: Create requirements.txt

**Files:**
- Create: `requirements.txt`

**Step 1: Create `requirements.txt`**
```
python-dotenv>=1.0.0
requests>=2.31.0
rich>=13.0.0
numpy>=1.26.0
astropy>=5.3
astroquery>=0.4.7
photutils>=1.13
matplotlib>=3.8.2
arxiv>=2.1.0
pyvo>=1.5
```

**Step 2: Install and verify**
```bash
pip install -r requirements.txt
```
Expected: all packages install without errors.

**Step 3: Commit**
```bash
git add requirements.txt
git commit -m "chore: add requirements"
```

---

## Task 6: Create Base Agent Class

**Files:**
- Create: `agents/base.py`

**Step 1: Create `agents/base.py`**
```python
"""Base agent class for all specialized research agents."""

from __future__ import annotations
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import requests

from config import OPENROUTER_API_KEY, LLM_API_URL, LLM_TEMPERATURE, get_model_slug, LLM_MODEL


@dataclass
class AgentResult:
    """Result returned by any agent."""
    agent_type: str
    status: str  # "success" | "failed"
    findings: str
    data: dict[str, Any] = field(default_factory=dict)
    anomalies: list[dict] = field(default_factory=list)
    error: str | None = None


class BaseAgent(ABC):
    """Base class for all research agents."""

    agent_type: str = "base"

    def __init__(self, model: str | None = None):
        self.model = model or LLM_MODEL

    def _call_llm(self, messages: list[dict], system: str | None = None) -> str:
        """Call OpenRouter LLM."""
        if not OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY not set in .env")

        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        response = requests.post(
            LLM_API_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": get_model_slug(self.model),
                "messages": all_messages,
                "temperature": LLM_TEMPERATURE,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    @abstractmethod
    def run(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Execute the agent's task and return findings."""
        ...
```

**Step 2: Update `agents/__init__.py`**
```python
from agents.base import BaseAgent, AgentResult
```

**Step 3: Commit**
```bash
git add agents/
git commit -m "feat: add base agent"
```

---

## Task 7: Create Data Retrieval Agent

**Files:**
- Create: `agents/data_retrieval.py`
- Create: `tools/catalog_tools.py`

**Step 1: Create `tools/catalog_tools.py`**
```python
"""Catalog and data retrieval tools using astroquery."""

from __future__ import annotations


def query_simbad(object_name: str) -> dict:
    """Query SIMBAD for basic object info."""
    try:
        from astroquery.simbad import Simbad
        result_table = Simbad.query_object(object_name)
        if result_table is None:
            return {"found": False, "object": object_name}
        row = result_table[0]
        return {
            "found": True,
            "object": object_name,
            "ra": float(row["RA_d"]) if "RA_d" in result_table.colnames else None,
            "dec": float(row["DEC_d"]) if "DEC_d" in result_table.colnames else None,
            "object_type": str(row.get("OTYPE", "unknown")),
            "redshift": str(row.get("RVZ_REDSHIFT", "N/A")),
        }
    except Exception as e:
        return {"found": False, "error": str(e)}


def query_ned(object_name: str) -> dict:
    """Query NASA/IPAC Extragalactic Database."""
    try:
        from astroquery.ipac.ned import Ned
        result_table = Ned.query_object(object_name)
        if result_table is None or len(result_table) == 0:
            return {"found": False, "object": object_name}
        row = result_table[0]
        return {
            "found": True,
            "object": object_name,
            "ra": float(row["RA"]),
            "dec": float(row["DEC"]),
            "type": str(row["Type"]),
            "redshift": float(row["Redshift"]) if row["Redshift"] else None,
            "velocity": float(row["Velocity"]) if row["Velocity"] else None,
        }
    except Exception as e:
        return {"found": False, "error": str(e)}


def list_jwst_programs(data_dir: str = "./data/jwst") -> list[dict]:
    """List available JWST programs from local metadata files."""
    import json
    from pathlib import Path
    programs = []
    data_path = Path(data_dir)
    if not data_path.exists():
        return []
    for meta_file in sorted(data_path.glob("program_*_metadata.json")):
        try:
            with open(meta_file) as f:
                meta = json.load(f)
            programs.append({
                "file": meta_file.name,
                "program_id": meta.get("program_id"),
                "target": meta.get("target"),
                "instrument": meta.get("instrument"),
                "filter": meta.get("filter"),
                "description": meta.get("description", ""),
            })
        except Exception:
            continue
    return programs
```

**Step 2: Create `agents/data_retrieval.py`**
```python
"""Data Retrieval Agent — queries catalogs, lists available JWST data."""

from __future__ import annotations
from typing import Any

from agents.base import BaseAgent, AgentResult
from tools.catalog_tools import query_simbad, query_ned, list_jwst_programs


class DataRetrievalAgent(BaseAgent):
    """Agent that retrieves catalog data and lists available datasets."""

    agent_type = "data_retrieval"

    def run(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        context = context or {}

        # List available local JWST programs
        programs = list_jwst_programs()

        # Ask LLM to figure out what objects/catalogs to query based on task
        system = """You are a data retrieval specialist for astronomical research.
Given a research task, identify the key astronomical objects or fields to query.
Respond with JSON: {"objects_to_query": ["NGC 1365", ...], "rationale": "..."}"""

        response = self._call_llm(
            [{"role": "user", "content": f"Task: {task}\nAvailable programs: {programs}"}],
            system=system,
        )

        # Parse LLM response
        objects_to_query = []
        try:
            import json, re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                objects_to_query = parsed.get("objects_to_query", [])
        except Exception:
            pass

        # Query catalogs for each object
        catalog_results = {}
        for obj in objects_to_query[:5]:  # limit to 5
            simbad = query_simbad(obj)
            ned = query_ned(obj)
            catalog_results[obj] = {"simbad": simbad, "ned": ned}

        findings = (
            f"Found {len(programs)} local JWST programs.\n"
            f"Queried {len(catalog_results)} objects from SIMBAD/NED.\n"
            f"Programs: {[p['program_id'] for p in programs]}\n"
            f"Catalog results: {catalog_results}"
        )

        return AgentResult(
            agent_type=self.agent_type,
            status="success",
            findings=findings,
            data={"programs": programs, "catalog_results": catalog_results},
        )
```

**Step 3: Commit**
```bash
git add agents/data_retrieval.py tools/catalog_tools.py
git commit -m "feat: add data retrieval agent"
```

---

## Task 8: Create Literature Agent

**Files:**
- Create: `agents/literature.py`
- Create: `tools/literature_tools.py`

**Step 1: Create `tools/literature_tools.py`**
```python
"""Literature search tools using arXiv."""

from __future__ import annotations


def search_arxiv(query: str, max_results: int = 5) -> list[dict]:
    """Search arXiv for papers matching query."""
    try:
        import arxiv
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        results = []
        for paper in client.results(search):
            results.append({
                "title": paper.title,
                "authors": [str(a) for a in paper.authors[:3]],
                "abstract": paper.summary[:300] + "...",
                "url": paper.entry_id,
                "published": str(paper.published.date()),
            })
        return results
    except Exception as e:
        return [{"error": str(e)}]
```

**Step 2: Create `agents/literature.py`**
```python
"""Literature Agent — searches arXiv for relevant papers."""

from __future__ import annotations
from typing import Any

from agents.base import BaseAgent, AgentResult
from tools.literature_tools import search_arxiv


class LiteratureAgent(BaseAgent):
    """Agent that searches scientific literature for context."""

    agent_type = "literature"

    def run(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        # Search arXiv
        papers = search_arxiv(f"JWST {task}", max_results=5)
        # Also search for the specific object/topic
        papers += search_arxiv(task, max_results=3)

        # Ask LLM to synthesize key findings from abstracts
        system = """You are an astronomy literature specialist.
Summarize the key findings from these papers relevant to the research task.
Focus on: what's known, what's uncertain, what gaps exist.
Be concise (3-5 sentences)."""

        paper_text = "\n\n".join(
            f"Title: {p.get('title', 'N/A')}\nAbstract: {p.get('abstract', 'N/A')}"
            for p in papers if "error" not in p
        )

        summary = self._call_llm(
            [{"role": "user", "content": f"Task: {task}\n\nPapers:\n{paper_text}"}],
            system=system,
        )

        return AgentResult(
            agent_type=self.agent_type,
            status="success",
            findings=summary,
            data={"papers": papers, "paper_count": len(papers)},
        )
```

**Step 3: Commit**
```bash
git add agents/literature.py tools/literature_tools.py
git commit -m "feat: add literature agent"
```

---

## Task 9: Create Analysis Agent

**Files:**
- Create: `agents/analysis.py`
- Create: `tools/astro_tools.py`

**Step 1: Create `tools/astro_tools.py`**
```python
"""Astronomical analysis tools (photometry, FITS inspection)."""

from __future__ import annotations
from pathlib import Path


def inspect_fits_metadata(file_path: str) -> dict:
    """Inspect FITS file headers and return key metadata."""
    try:
        from astropy.io import fits
        with fits.open(file_path) as hdul:
            info = []
            for i, hdu in enumerate(hdul):
                info.append({
                    "extension": i,
                    "name": hdu.name,
                    "shape": list(hdu.data.shape) if hdu.data is not None else None,
                    "header_keys": list(hdu.header.keys())[:20],
                })
            primary = hdul[0].header
            return {
                "file": str(file_path),
                "n_extensions": len(hdul),
                "extensions": info,
                "instrument": primary.get("INSTRUME", "unknown"),
                "filter": primary.get("FILTER", primary.get("FILTER1", "unknown")),
                "exptime": primary.get("EXPTIME", None),
                "target": primary.get("TARGNAME", primary.get("OBJECT", "unknown")),
            }
    except Exception as e:
        return {"error": str(e), "file": str(file_path)}


def image_statistics(file_path: str, extension: int = 1) -> dict:
    """Compute basic statistics on a FITS image extension."""
    try:
        import numpy as np
        from astropy.io import fits
        with fits.open(file_path) as hdul:
            data = hdul[extension].data
            if data is None:
                return {"error": f"No data in extension {extension}"}
            flat = data.flatten()
            finite = flat[np.isfinite(flat)]
            return {
                "mean": float(np.mean(finite)),
                "median": float(np.median(finite)),
                "std": float(np.std(finite)),
                "min": float(np.min(finite)),
                "max": float(np.max(finite)),
                "n_pixels": int(len(finite)),
                "n_nan": int(np.sum(~np.isfinite(flat))),
                "shape": list(data.shape),
            }
    except Exception as e:
        return {"error": str(e)}


def detect_sources(file_path: str, threshold_sigma: float = 5.0) -> dict:
    """Detect sources above threshold in FITS image using photutils."""
    try:
        import numpy as np
        from astropy.io import fits
        from astropy.stats import sigma_clipped_stats
        from photutils.detection import DAOStarFinder
        with fits.open(file_path) as hdul:
            # Find first 2D science extension
            data = None
            for hdu in hdul:
                if hdu.data is not None and len(hdu.data.shape) == 2:
                    data = hdu.data.astype(float)
                    break
            if data is None:
                return {"error": "No 2D data found"}

            mean, median, std = sigma_clipped_stats(data, sigma=3.0)
            daofind = DAOStarFinder(fwhm=3.0, threshold=threshold_sigma * std)
            sources = daofind(data - median)

            if sources is None:
                return {"n_sources": 0, "sources": []}

            return {
                "n_sources": len(sources),
                "background_mean": float(mean),
                "background_std": float(std),
                "threshold_adu": float(threshold_sigma * std),
                "sources": [
                    {
                        "id": int(s["id"]),
                        "x": float(s["xcentroid"]),
                        "y": float(s["ycentroid"]),
                        "flux": float(s["flux"]),
                        "mag": float(s["mag"]),
                    }
                    for s in sources[:20]  # top 20
                ],
            }
    except Exception as e:
        return {"error": str(e)}
```

**Step 2: Create `agents/analysis.py`**
```python
"""Analysis Agent — runs photometry and morphology on JWST data via ScientificResearchAgent."""

from __future__ import annotations
from pathlib import Path
from typing import Any

from agents.base import BaseAgent, AgentResult
from config import SANDBOX_DIR, MAX_STEPS_PER_RUN, MAX_COST_PER_RUN, LLM_MODEL


class AnalysisAgent(BaseAgent):
    """Agent that runs deep scientific analysis using the ScientificResearchAgent inner loop."""

    agent_type = "analysis"

    def run(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        context = context or {}
        datasets = context.get("datasets", [])

        try:
            from runner.scientific_agent import ScientificResearchAgent

            # Build tool lookup with our astro tools
            tool_lookup = {
                "image_statistics": {
                    "module_path": "tools.astro_tools",
                    "function_name": "image_statistics",
                },
                "detect_sources": {
                    "module_path": "tools.astro_tools",
                    "function_name": "detect_sources",
                },
                "inspect_fits_metadata": {
                    "module_path": "tools.astro_tools",
                    "function_name": "inspect_fits_metadata",
                },
            }
            tool_metadata = {
                "image_statistics": {
                    "description": "Compute mean, median, std, min, max of FITS image",
                    "input_schema": {
                        "properties": {
                            "file_path": {"type": "string", "description": "Path to FITS file"},
                            "extension": {"type": "integer", "description": "FITS extension index"},
                        }
                    },
                },
                "detect_sources": {
                    "description": "Detect point sources above sigma threshold in FITS image",
                    "input_schema": {
                        "properties": {
                            "file_path": {"type": "string", "description": "Path to FITS file"},
                            "threshold_sigma": {"type": "number", "description": "Detection threshold in sigma"},
                        }
                    },
                },
                "inspect_fits_metadata": {
                    "description": "Read FITS headers to understand file structure",
                    "input_schema": {
                        "properties": {
                            "file_path": {"type": "string", "description": "Path to FITS file"},
                        }
                    },
                },
            }

            agent = ScientificResearchAgent(
                work_dir=SANDBOX_DIR,
                tool_lookup=tool_lookup,
                tool_metadata=tool_metadata,
                model=self.model,
            )

            result, messages = agent.run(
                objective=task,
                datasets=datasets,
                constraints={
                    "max_steps": MAX_STEPS_PER_RUN,
                    "max_cost": MAX_COST_PER_RUN,
                    "min_reflections": 2,
                },
            )

            return AgentResult(
                agent_type=self.agent_type,
                status=result.status,
                findings=result.log_summary[-500:] if result.log_summary else "",
                data=result.summary_metrics or {},
                error=result.error,
            )

        except Exception as e:
            return AgentResult(
                agent_type=self.agent_type,
                status="failed",
                findings="",
                error=str(e),
            )
```

**Step 3: Commit**
```bash
git add agents/analysis.py tools/astro_tools.py
git commit -m "feat: add analysis agent with scientific inner loop"
```

---

## Task 10: Create Code Execution Agent

**Files:**
- Create: `agents/code_exec.py`
- Create: `tools/code_tools.py`

**Step 1: Create `tools/code_tools.py`**
```python
"""Code execution tools — run Python scripts and capture output."""

from __future__ import annotations
import subprocess
import sys
import tempfile
from pathlib import Path


def run_python_code(code: str, timeout: int = 30) -> dict:
    """Execute Python code and return stdout/stderr."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        tmp_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:500],
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Timeout", "returncode": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1}
    finally:
        Path(tmp_path).unlink(missing_ok=True)
```

**Step 2: Create `agents/code_exec.py`**
```python
"""Code Execution Agent — writes and runs Python scripts for analysis."""

from __future__ import annotations
import json
import re
from typing import Any

from agents.base import BaseAgent, AgentResult
from tools.code_tools import run_python_code


class CodeExecAgent(BaseAgent):
    """Agent that writes and runs Python for custom analysis."""

    agent_type = "code_exec"

    SYSTEM = """You are a scientific Python programmer specializing in astronomy.
Write a complete Python script to answer the research question using astropy, numpy, matplotlib.
The script must print its results as plain text.
Respond with ONLY the Python code inside a ```python ... ``` block."""

    def run(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        context = context or {}

        # Ask LLM to write the code
        response = self._call_llm(
            [{"role": "user", "content": f"Write a Python script to: {task}\nContext: {context}"}],
            system=self.SYSTEM,
        )

        # Extract code block
        match = re.search(r"```python\s*(.*?)```", response, re.DOTALL)
        if not match:
            return AgentResult(
                agent_type=self.agent_type,
                status="failed",
                findings="",
                error="LLM did not return a code block",
            )

        code = match.group(1).strip()
        exec_result = run_python_code(code, timeout=60)

        if exec_result["returncode"] != 0:
            return AgentResult(
                agent_type=self.agent_type,
                status="failed",
                findings=exec_result["stdout"],
                data={"code": code, "stderr": exec_result["stderr"]},
                error=exec_result["stderr"],
            )

        return AgentResult(
            agent_type=self.agent_type,
            status="success",
            findings=exec_result["stdout"],
            data={"code": code},
        )
```

**Step 3: Commit**
```bash
git add agents/code_exec.py tools/code_tools.py
git commit -m "feat: add code execution agent"
```

---

## Task 11: Create Modeling Agent

**Files:**
- Create: `agents/modeling.py`

**Step 1: Create `agents/modeling.py`**
```python
"""Modeling Agent — statistical fitting, SED analysis, population modeling."""

from __future__ import annotations
import re
from typing import Any

from agents.base import BaseAgent, AgentResult
from tools.code_tools import run_python_code


class ModelingAgent(BaseAgent):
    """Agent that fits models and does statistical analysis."""

    agent_type = "modeling"

    SYSTEM = """You are an astrophysicist specializing in statistical modeling.
Write Python code using numpy/scipy/astropy to fit models or analyze data.
Focus on: SED fitting, photometric redshifts, morphology fitting, statistical tests.
Print numeric results. Respond with ONLY a ```python ... ``` code block."""

    def run(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        context = context or {}

        prompt = f"Model/analyze: {task}\nData context: {context}"
        response = self._call_llm(
            [{"role": "user", "content": prompt}],
            system=self.SYSTEM,
        )

        match = re.search(r"```python\s*(.*?)```", response, re.DOTALL)
        if not match:
            # Fall back to text findings
            return AgentResult(
                agent_type=self.agent_type,
                status="success",
                findings=response,
            )

        code = match.group(1).strip()
        result = run_python_code(code, timeout=120)

        return AgentResult(
            agent_type=self.agent_type,
            status="success" if result["returncode"] == 0 else "failed",
            findings=result["stdout"],
            data={"code": code},
            error=result["stderr"] if result["returncode"] != 0 else None,
        )
```

**Step 2: Commit**
```bash
git add agents/modeling.py
git commit -m "feat: add modeling agent"
```

---

## Task 12: Create Anomaly Scorer

**Files:**
- Create: `anomaly.py`

**Step 1: Create `anomaly.py`**
```python
"""Anomaly scoring — flags statistically interesting findings."""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class Anomaly:
    source: str       # which agent found it
    description: str  # what was found
    score: float      # 0-1, higher = more anomalous
    data: dict        # supporting data


def score_anomalies(agent_results: list[dict[str, Any]]) -> list[Anomaly]:
    """
    Score anomalies in agent findings.
    Uses simple heuristics: sigma outliers, unexpected types, large uncertainties.
    """
    anomalies = []

    for result in agent_results:
        agent_type = result.get("agent_type", "unknown")
        findings = result.get("findings", "")
        data = result.get("data", {})

        # Heuristic 1: large sigma values in text
        sigma_matches = re.findall(r'(\d+\.?\d*)\s*[xX×]?\s*sigma', findings, re.IGNORECASE)
        for match in sigma_matches:
            sigma = float(match)
            if sigma >= 3.0:
                score = min(1.0, (sigma - 3.0) / 7.0)  # 3σ → 0.0, 10σ → 1.0
                anomalies.append(Anomaly(
                    source=agent_type,
                    description=f"{sigma}σ outlier detected",
                    score=score,
                    data={"sigma": sigma, "context": findings[:200]},
                ))

        # Heuristic 2: large source counts
        if "n_sources" in data:
            n = data["n_sources"]
            if n > 100:
                anomalies.append(Anomaly(
                    source=agent_type,
                    description=f"Unusually high source count: {n}",
                    score=min(1.0, n / 1000.0),
                    data={"n_sources": n},
                ))

        # Heuristic 3: keywords flagging something interesting
        interesting_keywords = [
            ("unexpected", 0.4), ("unusual", 0.4), ("anomal", 0.5),
            ("outlier", 0.5), ("peculiar", 0.6), ("unknown", 0.3),
            ("new source", 0.7), ("not in catalog", 0.7),
        ]
        findings_lower = findings.lower()
        for keyword, base_score in interesting_keywords:
            if keyword in findings_lower:
                anomalies.append(Anomaly(
                    source=agent_type,
                    description=f"Keyword '{keyword}' flagged in findings",
                    score=base_score,
                    data={"keyword": keyword, "context": findings[:200]},
                ))

    # Deduplicate by description
    seen = set()
    unique = []
    for a in anomalies:
        if a.description not in seen:
            seen.add(a.description)
            unique.append(a)

    return sorted(unique, key=lambda a: -a.score)
```

**Step 2: Commit**
```bash
git add anomaly.py
git commit -m "feat: add anomaly scorer"
```

---

## Task 13: Create Supervisor

**Files:**
- Create: `supervisor.py`

**Step 1: Create `supervisor.py`**
```python
"""Supervisor — orchestrates agents, scores anomalies, decides what to investigate next."""

from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents.base import AgentResult
from agents.data_retrieval import DataRetrievalAgent
from agents.analysis import AnalysisAgent
from agents.literature import LiteratureAgent
from agents.modeling import ModelingAgent
from agents.code_exec import CodeExecAgent
from anomaly import score_anomalies, Anomaly
from config import OPENROUTER_API_KEY, LLM_API_URL, LLM_TEMPERATURE, SUPERVISOR_MODEL, get_model_slug

import requests


@dataclass
class DiscoverySession:
    iteration: int = 0
    all_findings: list[dict] = field(default_factory=list)
    all_anomalies: list[Anomaly] = field(default_factory=list)
    total_cost: float = 0.0


class Supervisor:
    """
    LLM Supervisor that:
    1. Reads program.md for research context
    2. Decides which agents to dispatch and with what tasks
    3. Scores anomalies in results
    4. Reasons about what to investigate next
    5. Writes findings to markdown
    """

    def __init__(self, program_md_path: str = "program.md"):
        self.program_md = Path(program_md_path).read_text()
        self.agents = {
            "data_retrieval": DataRetrievalAgent(model=SUPERVISOR_MODEL),
            "analysis": AnalysisAgent(model=SUPERVISOR_MODEL),
            "literature": LiteratureAgent(model=SUPERVISOR_MODEL),
            "modeling": ModelingAgent(model=SUPERVISOR_MODEL),
            "code_exec": CodeExecAgent(model=SUPERVISOR_MODEL),
        }
        self.session = DiscoverySession()

    def _call_llm(self, messages: list[dict], system: str) -> str:
        response = requests.post(
            LLM_API_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": get_model_slug(SUPERVISOR_MODEL),
                "messages": [{"role": "system", "content": system}] + messages,
                "temperature": LLM_TEMPERATURE,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def plan_iteration(self) -> list[dict]:
        """Ask LLM supervisor what to investigate this iteration."""
        system = f"""You are a scientific supervisor managing autonomous research agents.
Your mission is DISCOVERY: find what's scientifically interesting in JWST data.
You have these agents: data_retrieval, analysis, literature, modeling, code_exec.

Program context:
{self.program_md}

Previous findings summary:
{self._summarize_session()}

Decide which agents to dispatch and what tasks to give them.
Think: what gaps exist? What anomalies need follow-up? What's unexplored?

Respond with JSON:
{{
  "rationale": "Why these agents and tasks...",
  "dispatch": [
    {{"agent": "data_retrieval", "task": "specific task description"}},
    {{"agent": "analysis", "task": "specific task description"}}
  ]
}}"""

        response = self._call_llm(
            [{"role": "user", "content": f"Plan iteration {self.session.iteration + 1}."}],
            system=system,
        )

        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                return parsed.get("dispatch", [])
        except Exception:
            pass

        # Fallback: run all agents with a default task
        return [
            {"agent": "data_retrieval", "task": "Survey available JWST datasets and catalog matches"},
            {"agent": "literature", "task": "Find recent papers on JWST discoveries"},
        ]

    def run_agents(self, dispatch: list[dict]) -> list[AgentResult]:
        """Run dispatched agents and return results."""
        results = []
        for item in dispatch:
            agent_name = item.get("agent")
            task = item.get("task", "")
            if agent_name not in self.agents:
                continue
            print(f"  [{agent_name}] {task}")
            result = self.agents[agent_name].run(task)
            results.append(result)
        return results

    def evaluate_and_decide(self, results: list[AgentResult]) -> str:
        """Score anomalies, reason about findings, return decision."""
        result_dicts = [
            {"agent_type": r.agent_type, "findings": r.findings, "data": r.data}
            for r in results
        ]

        # Anomaly scoring
        new_anomalies = score_anomalies(result_dicts)
        self.session.all_anomalies.extend(new_anomalies)

        # LLM supervisor reasons about findings
        system = f"""You are a scientific supervisor evaluating research results.
Identify the most scientifically interesting findings.
Decide: should we keep investigating, and what should we focus on next?
Be specific. Reference actual numbers and findings.

Program context:
{self.program_md}"""

        findings_text = "\n\n".join(
            f"Agent: {r.agent_type}\nFindings: {r.findings[:400]}"
            for r in results
        )
        anomaly_text = "\n".join(
            f"- [{a.score:.2f}] {a.description} (from {a.source})"
            for a in new_anomalies[:5]
        )

        response = self._call_llm(
            [{"role": "user", "content": (
                f"Results from iteration {self.session.iteration}:\n\n"
                f"{findings_text}\n\n"
                f"Flagged anomalies:\n{anomaly_text or 'None'}"
            )}],
            system=system,
        )
        return response

    def _summarize_session(self) -> str:
        if not self.session.all_findings:
            return "No findings yet — this is the first iteration."
        lines = []
        for f in self.session.all_findings[-3:]:  # last 3 iterations
            lines.append(f"Iteration {f['iteration']}: {f['decision'][:200]}")
        return "\n".join(lines)

    def save_findings(self, findings_dir: str = "findings") -> Path:
        """Write session findings to markdown file."""
        from datetime import datetime
        findings_path = Path(findings_dir)
        findings_path.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        out_file = findings_path / f"session_{timestamp}.md"

        lines = [
            f"# JWST Autoresearch — Session {timestamp}\n",
            f"**Iterations:** {self.session.iteration}\n",
            f"## Top Anomalies\n",
        ]
        for a in sorted(self.session.all_anomalies, key=lambda x: -x.score)[:10]:
            lines.append(f"- **[{a.score:.2f}]** {a.description} (agent: {a.source})\n")

        lines.append("\n## Iteration Log\n")
        for f in self.session.all_findings:
            lines.append(f"### Iteration {f['iteration']}\n")
            lines.append(f"{f['decision']}\n\n")

        out_file.write_text("".join(lines))
        return out_file
```

**Step 2: Commit**
```bash
git add supervisor.py
git commit -m "feat: add supervisor"
```

---

## Task 14: Create program.md

**Files:**
- Create: `program.md`

**Step 1: Create `program.md`**
```markdown
# JWST Autoresearch — Research Program

## Mission
Discover what's scientifically interesting in the available JWST datasets.
Do not look for specific things — instead, survey broadly and flag the unexpected.

## Available Data
Local JWST program metadata is in `./data/jwst/`. Programs include:
- Program 1180, 1181, 1345, 2736

## Research Strategy
1. Start by surveying what data is available (data_retrieval agent)
2. Cross-match objects with known catalogs (SIMBAD, NED)
3. Check recent literature for what's known about these fields
4. Run photometry and source detection on available FITS files
5. Flag any sources not in catalogs, unusual flux ratios, or unexpected morphologies
6. Model flagged sources to constrain their nature

## What Counts as Interesting
- Sources not in major catalogs (SIMBAD, NED, 2MASS)
- Anomalous flux ratios between filters
- Morphologically disturbed galaxies
- Unusual color-magnitude positions
- High-sigma outliers in any measured property
- Fields with unexpectedly high/low source density

## Astronomical Priors
- JWST NIRCam PSF FWHM ~0.06 arcsec at 2μm
- Typical field galaxy surface brightness ~23 mag/arcsec²
- Cosmic ray rate ~1 per 1000 pixels per exposure
- High-z galaxies (z>6) expected to drop out blueward of Lyman break

## Notes for Agents
- Prefer real data over synthetic
- Always state uncertainties and confidence levels
- When in doubt, flag it — better false positives than missed discoveries
```

**Step 2: Commit**
```bash
git add program.md
git commit -m "docs: add research program doc"
```

---

## Task 15: Create db.py

**Files:**
- Create: `db.py`

**Step 1: Create `db.py`**
```python
"""SQLite persistence for sessions and findings."""

from __future__ import annotations
import json
import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path("./autoresearch.db")


def init_db():
    """Create tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT,
            ended_at TEXT,
            iterations INTEGER,
            n_anomalies INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            iteration INTEGER,
            agent_type TEXT,
            findings TEXT,
            anomaly_score REAL,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_session(iterations: int, n_anomalies: int, started_at: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "INSERT INTO sessions (started_at, ended_at, iterations, n_anomalies) VALUES (?,?,?,?)",
        (started_at, datetime.now().isoformat(), iterations, n_anomalies),
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id


def save_finding(session_id: int, iteration: int, agent_type: str, findings: str, score: float = 0.0):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO findings (session_id, iteration, agent_type, findings, anomaly_score, created_at) VALUES (?,?,?,?,?,?)",
        (session_id, iteration, agent_type, findings, score, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
```

**Step 2: Commit**
```bash
git add db.py
git commit -m "feat: add sqlite persistence"
```

---

## Task 16: Create run.py (Entry Point)

**Files:**
- Create: `run.py`

**Step 1: Create `run.py`**
```python
"""
JWST Autoresearch — Entry Point

Usage:
    python run.py                     # Run full discovery loop
    python run.py --iterations 3      # Run N iterations
    python run.py --dry-run           # Plan only, no agent execution
"""

from __future__ import annotations
import argparse
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config import MAX_DISCOVERY_ITERATIONS, SESSION_COST_BUDGET, OPENROUTER_API_KEY
from supervisor import Supervisor
from db import init_db, save_session, save_finding

console = Console()


def main():
    parser = argparse.ArgumentParser(description="JWST Autoresearch")
    parser.add_argument("--iterations", type=int, default=MAX_DISCOVERY_ITERATIONS)
    parser.add_argument("--dry-run", action="store_true", help="Plan without executing agents")
    args = parser.parse_args()

    if not OPENROUTER_API_KEY:
        console.print("[red]ERROR: OPENROUTER_API_KEY not set. Copy .env.example to .env and fill it in.[/red]")
        return

    console.print(Panel.fit("[bold cyan]JWST Autoresearch[/bold cyan]\nAutonomous cosmological discovery", title="Science OS"))

    init_db()
    supervisor = Supervisor()
    started_at = datetime.now().isoformat()

    for i in range(args.iterations):
        console.print(f"\n[bold yellow]--- Iteration {i + 1}/{args.iterations} ---[/bold yellow]")

        # Plan
        dispatch = supervisor.plan_iteration()
        console.print(f"[cyan]Dispatching {len(dispatch)} agents:[/cyan]")
        for d in dispatch:
            console.print(f"  • [{d['agent']}] {d['task'][:80]}")

        if args.dry_run:
            console.print("[yellow]Dry run — skipping execution[/yellow]")
            continue

        # Execute agents
        results = supervisor.run_agents(dispatch)

        # Evaluate and decide
        decision = supervisor.evaluate_and_decide(results)
        supervisor.session.iteration = i + 1
        supervisor.session.all_findings.append({
            "iteration": i + 1,
            "decision": decision,
            "results": [r.agent_type for r in results],
        })

        # Save to DB
        for result in results:
            save_finding(0, i + 1, result.agent_type, result.findings[:1000])

        # Print decision
        console.print(Panel(decision[:600], title=f"[green]Supervisor Decision — Iteration {i+1}[/green]"))

    # Save findings report
    findings_path = supervisor.save_findings()
    console.print(f"\n[green]Findings saved to: {findings_path}[/green]")

    # Save session to DB
    save_session(
        iterations=supervisor.session.iteration,
        n_anomalies=len(supervisor.session.all_anomalies),
        started_at=started_at,
    )

    # Print anomaly summary
    if supervisor.session.all_anomalies:
        table = Table(title="Top Anomalies Found")
        table.add_column("Score", style="red")
        table.add_column("Source Agent")
        table.add_column("Description")
        for a in sorted(supervisor.session.all_anomalies, key=lambda x: -x.score)[:10]:
            table.add_row(f"{a.score:.2f}", a.source, a.description[:60])
        console.print(table)
    else:
        console.print("[yellow]No anomalies flagged this session.[/yellow]")


if __name__ == "__main__":
    main()
```

**Step 2: Commit**
```bash
git add run.py
git commit -m "feat: add entry point run.py"
```

---

## Task 17: Copy JWST Data Directory

**Files:**
- Copy: `data/` from JWST project

**Step 1: Copy the data directory**
```bash
cp -r "C:/Users/patri/Desktop/AI_Projects/JWST_scnience_env_2/data" ./data
```

**Step 2: Commit**
```bash
git add data/
git commit -m "chore: copy JWST program metadata"
```

---

## Task 18: End-to-End Verification

**Step 1: Set up .env**
```bash
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY
```

**Step 2: Install dependencies**
```bash
pip install -r requirements.txt
```

**Step 3: Dry-run test (no API calls for agents, only planning)**
```bash
python run.py --dry-run --iterations 2
```
Expected: Supervisor plans iterations, prints dispatch plan, no agent execution.

**Step 4: Smoke test imports**
```bash
python -c "from supervisor import Supervisor; from agents.analysis import AnalysisAgent; print('OK')"
```
Expected: `OK`

**Step 5: Real run (1 iteration)**
```bash
python run.py --iterations 1
```
Expected: 1 iteration completes, findings saved to `findings/session_*.md`, no crashes.

---

## Verification Summary

- `python run.py --dry-run` → plans dispatch without agent execution
- `python run.py --iterations 1` → full real run, findings saved
- `findings/session_*.md` → readable markdown report with anomalies
- `autoresearch.db` → SQLite with findings history
