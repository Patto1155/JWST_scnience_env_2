"""Focused tests for ScientificResearchAgent activity enforcement."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from runner.scientific_agent import ScientificResearchAgent


@pytest.fixture
def scientific_agent():
    """Create ScientificResearchAgent instance with one mock tool."""
    work_dir = Path("./test_runner_work_scientific")
    work_dir.mkdir(exist_ok=True)
    return ScientificResearchAgent(
        work_dir=work_dir,
        tool_lookup={
            "image_statistics": {
                "module_path": "tools.jwst.basic_stats",
                "function_name": "image_statistics",
            }
        },
        tool_metadata={
            "image_statistics": {
                "description": "Compute image statistics",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "image_data": {"type": "string", "description": "Dataset name"},
                    },
                },
                "output_schema": {"type": "object"},
                "tags": ["jwst", "stats"],
            }
        },
    )


def _mock_llm_response(content: str) -> Mock:
    """Build requests.post response mock for a single LLM content payload."""
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {"choices": [{"message": {"content": content}}]}
    return response


@patch("runner.scientific_agent.requests.post")
@patch("runner.scientific_agent.Sandbox.execute_tool")
def test_scientific_agent_blocks_premature_finish_until_minimum_activity(
    mock_execute,
    mock_post,
    scientific_agent,
):
    """Agent should reject early finish before real tool activity and reflection."""
    mock_execute.return_value = {"mean": 10.0, "count": 4}
    responses = [
        '{"action": "finish", "findings": "too early"}',
        '{"action": "tool_call", "tool_name": "image_statistics", "parameters": {"image_data": "jwst_test"}}',
        '{"action": "reflect", "thoughts": "One observation is not enough yet."}',
        '{"action": "finish", "findings": "Enough evidence now."}',
    ]
    mock_post.side_effect = [_mock_llm_response(content) for content in responses]

    result, trajectory = scientific_agent.run(
        objective="Verify minimum activity gates",
        datasets=["jwst_test"],
        constraints={
            "max_steps": 4,
            "min_successful_tool_calls": 1,
            "min_reflections": 1,
        },
    )

    assert result.status == "success"
    assert mock_execute.call_count == 1
    assert "Finish blocked: minimum agent activity not met" in result.log_summary
    assert result.summary_metrics["successful_tool_calls"] == 1
    assert result.summary_metrics["reflection_count"] == 1
    assert result.summary_metrics["blocked_finish_attempts"] == 1
    assert any(msg.role == "tool" for msg in trajectory)


@patch("runner.scientific_agent.requests.post")
def test_scientific_agent_fails_when_max_steps_reached_before_minimum_activity(
    mock_post,
    scientific_agent,
):
    """Agent should fail if it never satisfies required tool activity."""
    mock_post.side_effect = [
        _mock_llm_response('{"action": "finish", "findings": "too early"}'),
        _mock_llm_response('{"action": "finish", "findings": "still too early"}'),
    ]

    result, _trajectory = scientific_agent.run(
        objective="Verify minimum activity failure",
        datasets=["jwst_test"],
        constraints={
            "max_steps": 2,
            "min_successful_tool_calls": 1,
        },
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.startswith("AGENT_MINIMUM_ACTIVITY_NOT_MET")
    assert result.summary_metrics["successful_tool_calls"] == 0
    assert result.summary_metrics["blocked_finish_attempts"] == 2


@patch("runner.scientific_agent.requests.post")
@patch("runner.scientific_agent.Sandbox.execute_tool")
def test_scientific_agent_collects_visual_artifacts(
    mock_execute,
    mock_post,
    scientific_agent,
):
    """Successful visual tool calls should populate absolute run artifact paths."""
    scientific_agent.tool_lookup = {
        "candidate_evidence_bundle": {
            "module_path": "tools.jwst.visualization",
            "function_name": "candidate_evidence_bundle",
        }
    }
    scientific_agent.tool_metadata = {
        "candidate_evidence_bundle": {
            "description": "Create JWST evidence bundles",
            "input_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object"},
            "tags": ["jwst", "visualization"],
        }
    }

    mock_execute.return_value = {
        "output_path": "visuals/candidate_panel.png",
        "sidecar_path": "visuals/candidate_panel.json",
        "quality_flags": [],
        "ratio_f090_f444": 0.02,
        "artifacts": [
            {"path": "visuals/candidate_panel.png", "kind": "evidence_panel"},
            {"path": "visuals/candidate_panel.json", "kind": "evidence_sidecar"},
        ],
    }
    responses = [
        '{"action": "tool_call", "tool_name": "candidate_evidence_bundle", "parameters": {}}',
        '{"action": "finish", "findings": "Visual evidence captured."}',
    ]
    mock_post.side_effect = [_mock_llm_response(content) for content in responses]

    result, trajectory = scientific_agent.run(
        objective="Collect visual evidence",
        datasets=["jwst_test"],
        constraints={
            "max_steps": 2,
            "min_successful_tool_calls": 1,
        },
    )

    assert result.status == "success"
    assert result.summary_metrics["artifact_count"] == 2
    assert len(result.artifacts) == 2
    assert all(Path(path).is_absolute() for path in result.artifacts)
    assert result.artifacts[0].endswith("candidate_panel.png")
    assert result.artifacts[1].endswith("candidate_panel.json")
    tool_messages = [msg for msg in trajectory if msg.role == "tool"]
    assert tool_messages
    assert "artifact=candidate_panel.png" in tool_messages[0].content


@patch("runner.scientific_agent.requests.post")
@patch("runner.scientific_agent.Sandbox.execute_tool")
def test_scientific_agent_prefers_tool_call_over_embedded_finish_plan(
    mock_execute,
    mock_post,
    scientific_agent,
):
    """Mixed responses should execute the tool call instead of finishing with a plan."""
    mock_execute.return_value = {"mean": 11.0, "count": 4}
    responses = [
        (
            "I'll begin with baseline checks.\n"
            "{\"action\":\"finish\",\"findings\":\"I'll begin by calling tools next.\"}\n"
            '{"action":"tool_call","tool_name":"image_statistics","parameters":{"image_data":"jwst_test"}}'
        ),
        '{"action":"reflect","thoughts":"Observed the baseline stats."}',
        '{"action":"finish","findings":"Completed after real observations."}',
    ]
    mock_post.side_effect = [_mock_llm_response(content) for content in responses]

    result, trajectory = scientific_agent.run(
        objective="Prefer execution over premature finish",
        datasets=["jwst_test"],
        constraints={
            "max_steps": 3,
            "min_successful_tool_calls": 1,
            "min_reflections": 1,
        },
    )

    assert result.status == "success"
    assert mock_execute.call_count == 1
    assert result.summary_metrics["successful_tool_calls"] == 1
    assert result.summary_metrics["reflection_count"] == 1
    assert any(msg.role == "tool" for msg in trajectory)
