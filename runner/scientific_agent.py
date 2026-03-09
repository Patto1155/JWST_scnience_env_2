"""
Enhanced Research Agent with Scientific Method thinking.

This agent follows a rigorous scientific process:
1. Hypothesis formation
2. Experimental design
3. Data collection
4. Analysis
5. Interpretation
6. Conclusion
"""

import json
import re
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

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


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for persisted messages."""
    return datetime.now(UTC)


class ScientificResearchAgent:
    """
    Enhanced agent that thinks deeply and follows scientific method.

    Key differences from basic ResearchAgent:
    - Explicit hypothesis formation
    - Reflection after each observation
    - Multi-step analysis before conclusions
    - Scientific reasoning required
    """

    def __init__(
        self,
        work_dir: Path = None,
        tool_lookup: Dict[str, Dict[str, str]] = None,
        tool_metadata: Dict[str, Dict[str, Any]] = None,
        stream_callback: Optional[callable] = None,
        model: Optional[str] = None,
        strict_no_dummy_fallback: bool = False,
    ):
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
        self.stream_callback = stream_callback  # Callback for real-time streaming
        self.model = model

    def _format_tools_for_llm(self) -> str:
        """Format available tools for LLM consumption."""
        if not self.tool_metadata:
            return "No tools available."

        result = "Available Tools:\n"
        for tool_name, metadata in self.tool_metadata.items():
            result += f"\n- {tool_name}:\n"
            result += f"  Description: {metadata.get('description', 'N/A')}\n"

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
        """Call LLM API."""
        api_key = OPENROUTER_API_KEY or LLM_API_KEY
        if not api_key:
            raise ValueError("API key required")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        chosen_model = self.model or LLM_MODEL
        payload = {
            "model": chosen_model,
            "messages": messages,
            "temperature": LLM_TEMPERATURE,
        }

        # Allow full OpenRouter slug mapping when a short name is passed
        try:
            from core_api.config import get_model_slug

            payload["model"] = get_model_slug(chosen_model)
        except Exception:
            payload["model"] = chosen_model

        response = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _parse_non_negative_int(value: Any, default: int = 0) -> int:
        """Parse integer-like constraint values defensively."""
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return default

    def _extract_structured_actions(self, response: str) -> List[Dict[str, Any]]:
        """Extract all structured action objects from a response."""
        decoder = json.JSONDecoder()
        actions: List[Dict[str, Any]] = []

        fenced_blocks = re.findall(r"```json\s*(.*?)```", response, re.DOTALL | re.IGNORECASE)
        for block in fenced_blocks:
            try:
                parsed = json.loads(block)
                if isinstance(parsed, dict) and parsed.get("action") in ("tool_call", "finish", "reflect"):
                    actions.append(parsed)
                elif isinstance(parsed, list):
                    actions.extend(
                        item for item in parsed
                        if isinstance(item, dict) and item.get("action") in ("tool_call", "finish", "reflect")
                    )
            except Exception:
                continue

        for match in re.finditer(r"\{", response):
            try:
                parsed, _ = decoder.raw_decode(response[match.start():])
                if isinstance(parsed, dict) and parsed.get("action") in ("tool_call", "finish", "reflect"):
                    actions.append(parsed)
                elif isinstance(parsed, list):
                    actions.extend(
                        item for item in parsed
                        if isinstance(item, dict) and item.get("action") in ("tool_call", "finish", "reflect")
                    )
            except Exception:
                continue

        try:
            parsed = json.loads(response)
            if isinstance(parsed, dict) and parsed.get("action") in ("tool_call", "finish", "reflect"):
                actions.append(parsed)
            elif isinstance(parsed, list):
                actions.extend(
                    item for item in parsed
                    if isinstance(item, dict) and item.get("action") in ("tool_call", "finish", "reflect")
                )
        except Exception:
            pass

        deduped: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for action in actions:
            key = json.dumps(action, sort_keys=True, ensure_ascii=True)
            if key not in seen:
                seen.add(key)
                deduped.append(action)
        return deduped

    @staticmethod
    def _looks_like_unexecuted_plan(findings: str) -> bool:
        """Detect findings that still look like an execution plan."""
        text = (findings or "").strip()
        lowered = text.lower()
        plan_markers = (
            '{"action": "tool_call"',
            '{"action":"tool_call"',
            '{"action": "reflect"',
            '{"action":"reflect"',
            "let's start",
            "i'll begin",
            "i will begin",
            "next i will",
            "then i'll",
            "then i will",
        )
        return any(marker in lowered for marker in plan_markers)

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response to extract the highest-priority action."""
        actions = self._extract_structured_actions(response)
        for preferred_action in ("tool_call", "reflect", "finish"):
            for action in actions:
                if action.get("action") == preferred_action:
                    return action

        for tool_name in self.tool_lookup.keys():
            if f"call {tool_name}" in response.lower() or f"use {tool_name}" in response.lower():
                return {
                    "action": "tool_call",
                    "tool_name": tool_name,
                    "parameters": {},
                }

        # Default: finish
        return {
            "action": "finish",
            "findings": response,
        }

    def _summarize_tool_result(self, result: Any) -> str:
        """Create token-efficient summary of tool result."""
        if isinstance(result, dict):
            if "summary_stats" in result:
                stats = result["summary_stats"]
                summary = f"Summary: mean={stats.get('mean', 'N/A'):.4f}, median={stats.get('median', 'N/A'):.4f}, std={stats.get('std', 'N/A'):.4f}"
                if "sample_preview" in result:
                    sample = result["sample_preview"][:5]
                    summary += f", sample={sample}"
                return summary

            summary_parts = []
            for key, value in list(result.items())[:10]:
                if isinstance(value, (int, float, str, bool)):
                    if isinstance(value, float):
                        summary_parts.append(f"{key}={value:.4f}")
                    else:
                        summary_parts.append(f"{key}={value}")
                elif isinstance(value, list) and len(value) <= 5:
                    summary_parts.append(f"{key}={value}")
                elif isinstance(value, list):
                    summary_parts.append(f"{key}=[{len(value)} items]")

            artifact_paths = self._extract_artifact_paths(result, resolve_paths=False)
            if artifact_paths:
                summary_parts.append(f"artifact={Path(artifact_paths[0]).name}")

            return ", ".join(summary_parts)
        elif isinstance(result, (list, tuple)):
            if len(result) <= 10:
                return str(result)
            else:
                return f"[{len(result)} items: {result[:5]}...]"
        else:
            return str(result)[:500]

    def _extract_artifact_paths(
        self,
        result: Any,
        *,
        resolve_paths: bool,
    ) -> List[str]:
        """Extract artifact-like paths from a tool result payload."""
        if not isinstance(result, dict):
            return []

        discovered: List[str] = []
        for key in ("output_path", "catalog_path", "segmentation_overlay_path", "sidecar_path"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                discovered.append(value.strip())

        artifacts = result.get("artifacts")
        if isinstance(artifacts, list):
            for artifact in artifacts:
                if isinstance(artifact, dict):
                    value = artifact.get("path")
                elif isinstance(artifact, str):
                    value = artifact
                else:
                    value = None
                if isinstance(value, str) and value.strip():
                    discovered.append(value.strip())

        deduped: List[str] = []
        for raw_path in discovered:
            path_obj = Path(raw_path)
            if resolve_paths:
                if not path_obj.is_absolute():
                    path_obj = (self.sandbox.work_dir / path_obj).resolve()
                else:
                    path_obj = path_obj.resolve()
                normalized = str(path_obj)
            else:
                normalized = str(path_obj)

            if normalized not in deduped:
                deduped.append(normalized)
        return deduped

    @staticmethod
    def _is_strict_data_load_failure(error_text: str) -> bool:
        """Detect strict real-data loader failures from tool error text."""
        text = (error_text or "").lower()
        markers = (
            "strict real-data mode enabled",
            "dummy fallback is disabled",
            "dataset_identifier is required",
            "no file_path in metadata",
            "fits file not found",
            "could not load dataset",
        )
        return any(marker in text for marker in markers)

    def run(
        self,
        objective: str,
        datasets: List[str] = None,
        constraints: Dict[str, Any] = None,
        trajectory_callback: Optional[callable] = None,
        model: Optional[str] = None,
    ) -> Tuple[RunResult, List[Message]]:
        """
        Run the scientific research agent with deep thinking.
        """
        datasets = datasets or []
        constraints = constraints or {}
        # Allow per-run model override
        if model:
            self.model = model

        max_steps = constraints.get("max_steps", MAX_STEPS_PER_RUN)
        max_cost = constraints.get("max_cost", MAX_COST_PER_RUN)
        strict_real_data = bool(constraints.get("strict_real_data", False))
        min_successful_tool_calls = self._parse_non_negative_int(
            constraints.get("min_successful_tool_calls", 0)
        )
        min_reflections = self._parse_non_negative_int(constraints.get("min_reflections", 0))
        self.sandbox.set_strict_no_dummy_fallback(strict_real_data)

        self.messages = []
        self.step_count = 0
        self.cost_estimate = 0.0
        successful_tool_calls = 0
        reflection_count = 0
        blocked_finish_attempts = 0

        # Enhanced system prompt with scientific method
        system_prompt = f"""You are an autonomous scientist following rigorous scientific methodology.

SCIENTIFIC PROCESS:
1. HYPOTHESIS: Form clear, testable hypotheses
2. DESIGN: Plan which observations/measurements to make
3. OBSERVE: Use tools to collect data
4. REFLECT: After EACH observation, think deeply about what it means
5. ANALYZE: Compare observations, look for patterns
6. CONCLUDE: Draw evidence-based conclusions

CRITICAL THINKING GUIDELINES:
- After each tool result, reflect on what you learned
- Consider alternative explanations
- Look for patterns across multiple measurements
- Quantify uncertainty and limitations
- Build understanding iteratively

Available Tools:
{self._format_tools_for_llm()}

Available Datasets: {', '.join(datasets) if datasets else 'None'}

RESPONSE FORMAT:
You have three action types:

1. Call a tool:
{{"action": "tool_call", "tool_name": "tool_name", "parameters": {{...}}, "reasoning": "Why I'm calling this tool"}}

2. Reflect on results (IMPORTANT - do this after observations):
{{"action": "reflect", "thoughts": "What does this observation mean? What patterns do I see? What should I investigate next?"}}

3. Finish with findings:
{{"action": "finish", "findings": "Complete scientific analysis with evidence"}}

IMPORTANT RULES:
- Think step-by-step
- Reflect after observing results (use "reflect" action)
- Don't rush to conclusions - gather evidence
- Quantify findings with numbers
- State confidence levels and uncertainties
- Compare multiple measurements before concluding
"""

        # Initial message
        user_message = f"Research Objective: {objective}"
        self.messages.append(Message(
            role="user",
            content=user_message,
            timestamp=utc_now(),
        ))

        logs = [f"Starting scientific research: {objective}"]
        if strict_real_data:
            logs.append("Strict real-data mode enabled (dummy fallback disabled)")
        if min_successful_tool_calls or min_reflections:
            logs.append(
                "Minimum activity gates enabled: "
                f"successful_tool_calls>={min_successful_tool_calls}, "
                f"reflections>={min_reflections}"
            )
        metrics: Dict[str, Any] = {}
        artifacts: List[str] = []

        def update_activity_metrics() -> None:
            metrics["successful_tool_calls"] = successful_tool_calls
            metrics["reflection_count"] = reflection_count
            metrics["blocked_finish_attempts"] = blocked_finish_attempts
            metrics["min_successful_tool_calls"] = min_successful_tool_calls
            metrics["min_reflections"] = min_reflections
            metrics["artifact_count"] = len(artifacts)

        def minimum_activity_note(prefix: str) -> str:
            deficits = []
            if successful_tool_calls < min_successful_tool_calls:
                deficits.append(
                    f"successful tool calls {successful_tool_calls}/{min_successful_tool_calls}"
                )
            if reflection_count < min_reflections:
                deficits.append(f"reflections {reflection_count}/{min_reflections}")
            deficit_text = ", ".join(deficits) if deficits else "all minimums satisfied"
            return (
                f"{prefix}: minimum agent activity not met ({deficit_text}). "
                "Continue with real tool usage before concluding."
            )

        try:
            while self.step_count < max_steps:
                # Build messages with MORE context (last 20 instead of 10)
                llm_messages = [{"role": "system", "content": system_prompt}]
                for msg in self.messages[-20:]:  # More context for deeper thinking
                    if msg.role == "user":
                        llm_messages.append({"role": "user", "content": msg.content})
                    elif msg.role == "agent":
                        llm_messages.append({"role": "assistant", "content": msg.content})
                    elif msg.role == "tool":
                        # Include tool results in conversation
                        llm_messages.append({
                            "role": "user",
                            "content": f"OBSERVATION from {msg.tool_name}: {msg.content}",
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

                # Stream agent response to terminal
                if self.stream_callback:
                    self.stream_callback("agent", agent_response, self.step_count)

                # Parse response
                parsed = self._parse_llm_response(agent_response)

                if parsed.get("action") == "finish":
                    findings = parsed.get("findings", agent_response)
                    if self._looks_like_unexecuted_plan(findings):
                        blocked_finish_attempts += 1
                        update_activity_metrics()
                        note = (
                            "Finish blocked: findings still contain unexecuted plan content or "
                            "embedded action JSON. Execute the next tool call or reflect on real "
                            "observations before concluding."
                        )
                        logs.append(note)
                        self.messages.append(
                            Message(
                                role="user",
                                content=note,
                                timestamp=utc_now(),
                            )
                        )
                        self.step_count += 1
                        if trajectory_callback and self.step_count % 3 == 0:
                            trajectory_callback([m.model_dump() for m in self.messages])
                        continue
                    if (
                        successful_tool_calls < min_successful_tool_calls
                        or reflection_count < min_reflections
                    ):
                        blocked_finish_attempts += 1
                        update_activity_metrics()
                        note = minimum_activity_note("Finish blocked")
                        logs.append(note)
                        self.messages.append(
                            Message(
                                role="user",
                                content=note,
                                timestamp=utc_now(),
                            )
                        )
                        self.step_count += 1
                        if trajectory_callback and self.step_count % 3 == 0:
                            trajectory_callback([m.model_dump() for m in self.messages])
                        continue

                    logs.append(f"Agent finished: {findings[:200]}...")

                    self.messages.append(Message(
                        role="agent",
                        content=f"Final Findings: {findings}",
                        timestamp=utc_now(),
                    ))

                    update_activity_metrics()
                    if trajectory_callback:
                        trajectory_callback([m.model_dump() for m in self.messages])

                    log_summary = "\n".join(logs)
                    return RunResult(
                        status="success",
                        summary_metrics=metrics,
                        artifacts=artifacts,
                        log_summary=log_summary,
                    ), self.messages

                elif parsed.get("action") == "reflect":
                    # Agent is thinking - this is good!
                    thoughts = parsed.get("thoughts", "Reflecting...")
                    reflection_count += 1
                    update_activity_metrics()
                    logs.append(f"Agent reflecting: {thoughts[:100]}...")

                    # Stream reflection to terminal
                    if self.stream_callback:
                        self.stream_callback("reflection", thoughts, self.step_count)

                    # Reflection doesn't count as a step - encourage more thinking!
                    continue

                elif parsed.get("action") == "tool_call":
                    tool_name = parsed.get("tool_name")
                    parameters = parsed.get("parameters", {})
                    reasoning = parsed.get("reasoning", "Not provided")

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
                    logs.append(f"Executing {tool_name}: {reasoning}")

                    # Stream tool call to terminal
                    if self.stream_callback:
                        self.stream_callback("tool_call", f"{tool_name}({parameters})", self.step_count)

                    try:
                        tool_info = self.tool_lookup[tool_name]
                        result = self.sandbox.execute_tool(
                            module_path=tool_info["module_path"],
                            function_name=tool_info["function_name"],
                            parameters=parameters,
                        )

                        for artifact_path in self._extract_artifact_paths(
                            result,
                            resolve_paths=True,
                        ):
                            if artifact_path not in artifacts:
                                artifacts.append(artifact_path)

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
                        successful_tool_calls += 1
                        update_activity_metrics()

                        logs.append(f"Tool {tool_name} completed: {summary[:100]}...")

                        # Stream tool result to terminal
                        if self.stream_callback:
                            self.stream_callback("tool_result", summary, self.step_count)

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

                        if strict_real_data and self._is_strict_data_load_failure(str(e)):
                            strict_msg = f"STRICT_DATA_LOAD_FAILURE: {error_msg}"
                            logs.append(strict_msg)
                            raise RuntimeError(strict_msg) from e

                self.step_count += 1

                # Update trajectory periodically
                if trajectory_callback and self.step_count % 3 == 0:
                    trajectory_callback([m.model_dump() for m in self.messages])

            # Max steps reached
            logs.append(f"Max steps ({max_steps}) reached")
            update_activity_metrics()
            logs.append(
                "Activity summary: "
                f"successful_tool_calls={successful_tool_calls}, "
                f"reflections={reflection_count}, "
                f"blocked_finish_attempts={blocked_finish_attempts}"
            )
            log_summary = "\n".join(logs)

            if trajectory_callback:
                trajectory_callback([m.model_dump() for m in self.messages])

            if (
                successful_tool_calls < min_successful_tool_calls
                or reflection_count < min_reflections
            ):
                error_msg = minimum_activity_note("AGENT_MINIMUM_ACTIVITY_NOT_MET")
                return RunResult(
                    status="failed",
                    summary_metrics=metrics,
                    artifacts=artifacts,
                    log_summary=log_summary,
                    error=error_msg,
                ), self.messages

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
            update_activity_metrics()
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
