import json
import re
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from runner.sandbox import Sandbox
from runner.result_schema import RunResult
from core_api.schemas.experiments import ExperimentSpec, ToolInvocation
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


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for persisted messages."""
    return datetime.now(UTC)


class ExperimentExecutor:
    """Executes experiments based on ExperimentSpec."""

    def __init__(self, work_dir: Path = None):
        """Initialize executor with work directory."""
        if work_dir is None:
            work_dir = Path("./runner_work")
        self.sandbox = Sandbox(work_dir)

    def run_experiment(self, spec: ExperimentSpec, tool_lookup: Dict[str, Dict[str, str]]) -> RunResult:
        """
        Execute an experiment spec.
        
        Args:
            spec: ExperimentSpec to execute
            tool_lookup: Dict mapping tool_name -> {module_path, function_name}
        
        Returns:
            RunResult with execution results
        """
        logs = []
        metrics: Dict[str, Any] = {}
        artifacts: List[str] = []
        step_results: List[Any] = []

        try:
            strict_real_data = bool((spec.constraints or {}).get("strict_real_data", False))
            self.sandbox.set_strict_no_dummy_fallback(strict_real_data)
            logs.append(f"Starting experiment: {spec.objective}")
            logs.append(f"Using datasets: {spec.datasets}")
            logs.append(f"Executing {len(spec.steps)} steps")
            if strict_real_data:
                logs.append("Strict real-data mode enabled (dummy fallback disabled)")

            # Execute each step
            for i, step in enumerate(spec.steps):
                logs.append(f"Step {i+1}/{len(spec.steps)}: {step.tool_name}")

                # Look up tool metadata
                if step.tool_name not in tool_lookup:
                    raise ValueError(f"Tool '{step.tool_name}' not found in registry")

                tool_info = tool_lookup[step.tool_name]
                module_path = tool_info["module_path"]
                function_name = tool_info["function_name"]

                # Execute tool
                try:
                    result = self.sandbox.execute_tool(
                        module_path=module_path,
                        function_name=function_name,
                        parameters=step.parameters,
                    )
                    step_results.append(result)
                    logs.append(f"Step {i+1} completed successfully")

                    # Extract metrics if result is a dict
                    if isinstance(result, dict):
                        # Check for common metric keys
                        for key in ["value", "mean", "median", "count", "metrics"]:
                            if key in result:
                                metrics[f"{step.tool_name}_{key}"] = result[key]

                except Exception as e:
                    error_msg = f"Step {i+1} failed: {str(e)}"
                    logs.append(error_msg)
                    logs.append(traceback.format_exc())
                    raise

            # Success
            log_summary = "\n".join(logs)
            return RunResult(
                status="success",
                summary_metrics=metrics,
                artifacts=artifacts,
                log_summary=log_summary,
            )

        except Exception as e:
            # Failure
            error_msg = str(e)
            logs.append(f"Experiment failed: {error_msg}")
            log_summary = "\n".join(logs)
            return RunResult(
                status="failed",
                summary_metrics=metrics,
                artifacts=artifacts,
                log_summary=log_summary,
                error=error_msg,
            )


def run_experiment(
    spec: ExperimentSpec,
    tool_lookup: Dict[str, Dict[str, str]],
    work_dir: Path = None,
) -> RunResult:
    """
    Convenience function to run an experiment.
    
    Args:
        spec: ExperimentSpec to execute
        tool_lookup: Dict mapping tool_name -> {module_path, function_name}
        work_dir: Optional work directory path
    
    Returns:
        RunResult
    """
    executor = ExperimentExecutor(work_dir=work_dir)
    return executor.run_experiment(spec, tool_lookup)


class ResearchAgent:
    """Autonomous research agent that iteratively thinks, calls tools, and returns findings."""

    def __init__(
        self,
        work_dir: Path = None,
        tool_lookup: Dict[str, Dict[str, str]] = None,
        tool_metadata: Dict[str, Dict[str, Any]] = None,
        strict_no_dummy_fallback: bool = False,
    ):
        """
        Initialize research agent.
        
        Args:
            work_dir: Working directory for tool execution
            tool_lookup: Dict mapping tool_name -> {module_path, function_name}
            tool_metadata: Dict mapping tool_name -> {description, input_schema, output_schema, tags}
        """
        if work_dir is None:
            work_dir = Path("./runner_work")
        self.sandbox = Sandbox(
            work_dir,
            strict_no_dummy_fallback=strict_no_dummy_fallback,
        )
        self.tool_lookup = tool_lookup or {}
        self.tool_metadata = tool_metadata or {}
        self.messages: List[Message] = []
        self.step_count = 0
        self.cost_estimate = 0.0

    def _format_tools_for_llm(self) -> str:
        """Format available tools for LLM consumption."""
        if not self.tool_metadata:
            return "No tools available."
        
        result = "Available Tools:\n"
        for tool_name, metadata in self.tool_metadata.items():
            result += f"\n- {tool_name}:\n"
            result += f"  Description: {metadata.get('description', 'N/A')}\n"
            
            # Format input schema
            input_schema = metadata.get('input_schema', {})
            if 'properties' in input_schema:
                result += "  Parameters:\n"
                for param, details in input_schema['properties'].items():
                    param_type = details.get('type', 'any')
                    param_desc = details.get('description', '')
                    result += f"    - {param} ({param_type}): {param_desc}\n"
            
            tags = metadata.get('tags', [])
            if tags:
                result += f"  Tags: {', '.join(tags)}\n"
        
        return result

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Call LLM API (OpenRouter)."""
        api_key = OPENROUTER_API_KEY or LLM_API_KEY
        if not api_key:
            raise ValueError("LLM_API_KEY or OPENROUTER_API_KEY must be set")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": LLM_MODEL,
            "messages": messages,
            "temperature": LLM_TEMPERATURE,
        }
        
        response = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Parse LLM response to extract tool calls or finish decision.
        
        Expected formats:
        - Tool call: {"action": "tool_call", "tool_name": "...", "parameters": {...}}
        - Finish: {"action": "finish", "findings": "..."}
        - Or natural language that we try to parse
        """
        decoder = json.JSONDecoder()

        def _extract_action(parsed_obj: Any) -> Optional[Dict[str, Any]]:
            """Return first valid action dict from parsed object."""
            if isinstance(parsed_obj, dict) and parsed_obj.get("action") in ("tool_call", "finish"):
                return parsed_obj
            if isinstance(parsed_obj, list):
                for item in parsed_obj:
                    if isinstance(item, dict) and item.get("action") in ("tool_call", "finish"):
                        return item
            return None

        # 1) Prefer fenced JSON blocks
        fenced_blocks = re.findall(r"```json\s*(.*?)```", response, re.DOTALL | re.IGNORECASE)
        for block in fenced_blocks:
            try:
                parsed = json.loads(block)
            except Exception:
                continue
            action = _extract_action(parsed)
            if action:
                return action

        # 2) Scan for a valid JSON object/array anywhere in response
        for match in re.finditer(r"\{|\[", response):
            try:
                parsed, _ = decoder.raw_decode(response[match.start():])
            except Exception:
                continue
            action = _extract_action(parsed)
            if action:
                return action

        # 3) If whole response is JSON, parse it
        try:
            parsed = json.loads(response)
            action = _extract_action(parsed)
            if action:
                return action
        except Exception:
            pass
        
        # Try to detect tool call in natural language
        for tool_name in self.tool_lookup.keys():
            if f"call {tool_name}" in response.lower() or f"use {tool_name}" in response.lower():
                # Try to extract parameters
                params_match = re.search(r'parameters[:\s]*\{[^}]*\}', response, re.IGNORECASE | re.DOTALL)
                params = {}
                if params_match:
                    try:
                        params = json.loads(params_match.group(0).split('{', 1)[1].rsplit('}', 1)[0])
                    except:
                        pass
                
                return {
                    "action": "tool_call",
                    "tool_name": tool_name,
                    "parameters": params,
                }
        
        # Default: assume finish if no clear tool call
        return {
            "action": "finish",
            "findings": response,
        }

    def _summarize_tool_result(self, result: Any) -> str:
        """Create a token-efficient summary of tool result."""
        if isinstance(result, dict):
            # If already has summary_stats, use it
            if "summary_stats" in result:
                stats = result["summary_stats"]
                summary = f"Summary: mean={stats.get('mean', 'N/A')}, median={stats.get('median', 'N/A')}, std={stats.get('std', 'N/A')}"
                if "sample_preview" in result:
                    sample = result["sample_preview"][:5]  # First 5 samples
                    summary += f", sample={sample}"
                return summary
            
            # Otherwise, create a compact summary
            summary_parts = []
            for key, value in list(result.items())[:10]:  # First 10 keys
                if isinstance(value, (int, float, str, bool)):
                    summary_parts.append(f"{key}={value}")
                elif isinstance(value, list) and len(value) <= 5:
                    summary_parts.append(f"{key}={value}")
                elif isinstance(value, list):
                    summary_parts.append(f"{key}=[{len(value)} items]")
                else:
                    summary_parts.append(f"{key}=[complex]")
            
            return ", ".join(summary_parts)
        elif isinstance(result, (list, tuple)):
            if len(result) <= 10:
                return str(result)
            else:
                return f"[{len(result)} items: {result[:5]}...]"
        else:
            return str(result)[:500]  # Truncate long strings

    def run(
        self,
        objective: str,
        datasets: List[str] = None,
        constraints: Dict[str, Any] = None,
        trajectory_callback: Optional[callable] = None,
    ) -> Tuple[RunResult, List[Message]]:
        """
        Run the research agent loop.
        
        Args:
            objective: Research objective
            datasets: Available datasets
            constraints: Optional constraints (max_steps, max_cost)
            trajectory_callback: Optional callback to update trajectory in DB
        
        Returns:
            Tuple of (RunResult, trajectory messages)
        """
        datasets = datasets or []
        constraints = constraints or {}
        
        max_steps = constraints.get("max_steps", MAX_STEPS_PER_RUN)
        max_cost = constraints.get("max_cost", MAX_COST_PER_RUN)
        strict_real_data = bool(constraints.get("strict_real_data", False))
        self.sandbox.set_strict_no_dummy_fallback(strict_real_data)
        
        # Initialize message history
        self.messages = []
        self.step_count = 0
        self.cost_estimate = 0.0
        
        # System prompt
        system_prompt = f"""You are an autonomous scientist operating in a Science OS environment.

Your job:
- Think about the research objective
- Decide which tools to use
- Call tools and observe results
- Iterate until you have findings
- Report your findings clearly

Available Tools:
{self._format_tools_for_llm()}

Available Datasets: {', '.join(datasets) if datasets else 'None specified'}

When you want to call a tool, respond with JSON:
{{"action": "tool_call", "tool_name": "tool_name", "parameters": {{...}}}}

When you're done, respond with JSON:
{{"action": "finish", "findings": "Your findings and conclusions"}}

Tools return summaries, not raw data. Use the summaries to make decisions.
Be efficient with tool calls - don't call the same tool repeatedly with the same parameters.
"""
        
        # Initial user message
        user_message = f"Research Objective: {objective}"
        self.messages.append(Message(
            role="user",
            content=user_message,
            timestamp=utc_now(),
        ))
        
        logs = [f"Starting research agent: {objective}"]
        if strict_real_data:
            logs.append("Strict real-data mode enabled (dummy fallback disabled)")
        metrics: Dict[str, Any] = {}
        artifacts: List[str] = []
        
        try:
            while self.step_count < max_steps:
                # Build messages for LLM
                llm_messages = [{"role": "system", "content": system_prompt}]
                for msg in self.messages[-10:]:  # Last 10 messages for context
                    if msg.role == "user":
                        llm_messages.append({"role": "user", "content": msg.content})
                    elif msg.role == "agent":
                        llm_messages.append({"role": "assistant", "content": msg.content})
                    elif msg.role == "tool":
                        llm_messages.append({
                            "role": "assistant",
                            "content": f"Tool {msg.tool_name} returned: {msg.content}",
                        })
                
                # Call LLM
                logs.append(f"Step {self.step_count + 1}: Calling LLM...")
                try:
                    agent_response = self._call_llm(llm_messages)
                except Exception as llm_error:
                    error_msg = f"LLM call failed: {str(llm_error)}"
                    logs.append(error_msg)
                    raise
                
                # Add agent message
                agent_msg = Message(
                    role="agent",
                    content=agent_response,
                    timestamp=utc_now(),
                )
                self.messages.append(agent_msg)
                
                # Parse response
                parsed = self._parse_llm_response(agent_response)
                
                if parsed.get("action") == "finish":
                    findings = parsed.get("findings", agent_response)
                    logs.append(f"Agent finished: {findings}")
                    
                    # Add final findings message
                    self.messages.append(Message(
                        role="agent",
                        content=f"Final Findings: {findings}",
                        timestamp=utc_now(),
                    ))
                    
                    # Update trajectory if callback provided
                    if trajectory_callback:
                        trajectory_callback([m.model_dump() for m in self.messages])
                    
                    log_summary = "\n".join(logs)
                    return RunResult(
                        status="success",
                        summary_metrics=metrics,
                        artifacts=artifacts,
                        log_summary=log_summary,
                    ), self.messages
                
                elif parsed.get("action") == "tool_call":
                    tool_name = parsed.get("tool_name")
                    parameters = parsed.get("parameters", {})
                    
                    if not tool_name or tool_name not in self.tool_lookup:
                        error_msg = f"Invalid tool: {tool_name}"
                        logs.append(f"ERROR: {error_msg}")
                        self.messages.append(Message(
                            role="agent",
                            content=f"Error: {error_msg}",
                            timestamp=utc_now(),
                        ))
                        continue
                    
                    # Execute tool
                    logs.append(f"Executing tool: {tool_name} with parameters: {parameters}")
                    try:
                        tool_info = self.tool_lookup[tool_name]
                        result = self.sandbox.execute_tool(
                            module_path=tool_info["module_path"],
                            function_name=tool_info["function_name"],
                            parameters=parameters,
                        )
                        
                        # Summarize result
                        summary = self._summarize_tool_result(result)
                        
                        # Add tool message
                        tool_msg = Message(
                            role="tool",
                            content=summary,
                            tool_name=tool_name,
                            timestamp=utc_now(),
                        )
                        self.messages.append(tool_msg)
                        
                        logs.append(f"Tool {tool_name} completed: {summary[:100]}")
                        
                        # Extract metrics
                        if isinstance(result, dict):
                            for key in ["value", "mean", "median", "count", "metrics"]:
                                if key in result:
                                    metrics[f"{tool_name}_{key}"] = result[key]
                    
                    except Exception as e:
                        error_msg = f"Tool {tool_name} failed: {str(e)}"
                        logs.append(error_msg)
                        logs.append(traceback.format_exc())
                        
                        self.messages.append(Message(
                            role="tool",
                            content=f"Error: {error_msg}",
                            tool_name=tool_name,
                            timestamp=utc_now(),
                        ))
                
                self.step_count += 1
                
                # Update trajectory periodically
                if trajectory_callback and self.step_count % 5 == 0:
                    trajectory_callback([m.model_dump() for m in self.messages])
            
            # Max steps reached
            logs.append(f"Max steps ({max_steps}) reached")
            log_summary = "\n".join(logs)
            
            if trajectory_callback:
                trajectory_callback([m.model_dump() for m in self.messages])
            
            return RunResult(
                status="success",
                summary_metrics=metrics,
                artifacts=artifacts,
                log_summary=log_summary,
            ), self.messages
        
        except Exception as e:
            error_msg = str(e)
            logs.append(f"Agent failed: {error_msg}")
            logs.append(traceback.format_exc())
            log_summary = "\n".join(logs)
            
            if trajectory_callback:
                trajectory_callback([m.model_dump() for m in self.messages])
            
            return RunResult(
                status="failed",
                summary_metrics=metrics,
                artifacts=artifacts,
                log_summary=log_summary,
                error=error_msg,
            ), self.messages
