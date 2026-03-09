"""Tests for ResearchAgent."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from runner.executor import ResearchAgent
from runner.result_schema import RunResult
from core_api.schemas.experiments import ExperimentSpec


@pytest.fixture
def mock_tool_lookup():
    """Mock tool lookup."""
    return {
        "image_statistics": {
            "module_path": "tools.jwst.basic_stats",
            "function_name": "image_statistics",
        }
    }


@pytest.fixture
def mock_tool_metadata():
    """Mock tool metadata."""
    return {
        "image_statistics": {
            "description": "Compute image statistics",
            "input_schema": {
                "type": "object",
                "properties": {
                    "image_data": {"type": "array", "description": "Image data"}
                }
            },
            "output_schema": {"type": "object"},
            "tags": ["jwst", "stats"],
        }
    }


@pytest.fixture
def agent(mock_tool_lookup, mock_tool_metadata):
    """Create ResearchAgent instance."""
    work_dir = Path("./test_runner_work")
    work_dir.mkdir(exist_ok=True)
    return ResearchAgent(
        work_dir=work_dir,
        tool_lookup=mock_tool_lookup,
        tool_metadata=mock_tool_metadata,
    )


@patch("runner.executor.requests.post")
def test_research_agent_finish_immediately(mock_post, agent):
    """Test agent that finishes immediately."""
    # Mock LLM response that finishes
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": '{"action": "finish", "findings": "Test findings"}'
            }
        }]
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    result, trajectory = agent.run(
        objective="Test objective",
        datasets=[],
        constraints={"max_steps": 10},
    )
    
    assert result.status == "success"
    assert len(trajectory) >= 2  # User message + agent finish message
    assert any("findings" in msg.content.lower() for msg in trajectory)


@patch("runner.executor.requests.post")
@patch("runner.executor.Sandbox.execute_tool")
def test_research_agent_tool_call(mock_execute, mock_post, agent):
    """Test agent that calls a tool then finishes."""
    import numpy as np
    
    # Mock tool execution
    mock_execute.return_value = {
        "summary_stats": {
            "mean": 10.0,
            "std": 2.0,
        },
        "mean": 10.0,
        "std": 2.0,
    }
    
    # Mock LLM responses: first tool call, then finish
    responses = [
        '{"action": "tool_call", "tool_name": "image_statistics", "parameters": {"image_data": null}}',
        '{"action": "finish", "findings": "Found mean=10.0"}',
    ]
    
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    
    def side_effect(*args, **kwargs):
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": responses.pop(0) if responses else '{"action": "finish", "findings": "Done"}'
                }
            }]
        }
        return mock_response
    
    mock_post.side_effect = side_effect
    
    result, trajectory = agent.run(
        objective="Test objective",
        datasets=[],
        constraints={"max_steps": 10},
    )
    
    assert result.status == "success"
    assert mock_execute.called
    # Should have user, agent (tool call), tool result, agent (finish) messages
    assert len(trajectory) >= 4


def test_research_agent_max_steps(agent):
    """Test agent respects max_steps constraint."""
    with patch("runner.executor.requests.post") as mock_post:
        # Mock LLM to always request tool calls
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"action": "tool_call", "tool_name": "image_statistics", "parameters": {}}'
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        with patch("runner.executor.Sandbox.execute_tool") as mock_execute:
            mock_execute.return_value = {"mean": 10.0}
            
            result, trajectory = agent.run(
                objective="Test objective",
                datasets=[],
                constraints={"max_steps": 3},
            )
            
            # Should stop at max_steps
            assert agent.step_count <= 3
            assert result.status == "success"


def test_research_agent_format_tools(agent):
    """Test tool formatting for LLM."""
    formatted = agent._format_tools_for_llm()
    assert "image_statistics" in formatted
    assert "Compute image statistics" in formatted
    assert "jwst" in formatted or "stats" in formatted


def test_research_agent_summarize_result(agent):
    """Test tool result summarization."""
    # Test dict with summary_stats
    result = {
        "summary_stats": {"mean": 10.0, "std": 2.0},
        "sample_preview": [1, 2, 3],
    }
    summary = agent._summarize_tool_result(result)
    assert "mean=10.0" in summary or "10.0" in summary
    
    # Test simple dict
    result = {"value": 42, "count": 100}
    summary = agent._summarize_tool_result(result)
    assert "value=42" in summary or "42" in summary
    
    # Test list
    result = [1, 2, 3, 4, 5]
    summary = agent._summarize_tool_result(result)
    assert len(summary) > 0

