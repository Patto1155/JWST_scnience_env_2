"""Adversarial LLM replies must never create an unbounded research run."""

from unittest.mock import Mock

import pytest

from runner.scientific_agent import ScientificResearchAgent


@pytest.fixture
def agent(tmp_path, monkeypatch, forbid_external_connections):
    monkeypatch.setattr("runner.scientific_agent.LLM_API_KEY", "test-only-fake-key")
    return ScientificResearchAgent(work_dir=tmp_path)


def response(content, *, cost=0.01, tokens=10, include_usage=True):
    body = {"choices": [{"message": {"content": content}}]}
    if include_usage:
        body["usage"] = {"cost": cost, "prompt_tokens": tokens, "completion_tokens": 5}
    result = Mock()
    result.json.return_value = body
    return result


@pytest.mark.parametrize(
    "action",
    [
        '{"action":"reflect","thoughts":"Keep thinking indefinitely"}',
        '{"action":"tool_call","tool_name":"nonexistent","parameters":{}}',
    ],
)
def test_all_llm_actions_are_bounded(agent, monkeypatch, action):
    post = Mock(return_value=response(action))
    monkeypatch.setattr("runner.scientific_agent.requests.post", post)
    result, _ = agent.run("Bound adversarial actions", constraints={"max_steps": 3})
    assert post.call_count == 3
    assert agent.step_count == 3
    assert result.status == "failed"
    assert result.error.startswith("AGENT_STEP_LIMIT_REACHED")
    assert result.summary_metrics["llm_calls"] == 3
    assert result.summary_metrics["total_tokens"] == 45
    assert result.summary_metrics["provider_reported_cost_usd"] == pytest.approx(0.03)


def test_dollar_limit_prevents_next_call(agent, monkeypatch):
    post = Mock(return_value=response('{"action":"reflect"}', cost=0.02))
    monkeypatch.setattr("runner.scientific_agent.requests.post", post)
    result, _ = agent.run("Cost cutoff", constraints={"max_steps": 50, "max_cost": 0.02})
    assert post.call_count == 1
    assert result.error.startswith("AGENT_COST_LIMIT_REACHED")
    assert result.summary_metrics["provider_reported_cost_usd"] == 0.02
    assert result.summary_metrics["cost_limit_enforcement"] == "post_response"


def test_over_budget_reply_cannot_execute_tool(agent, monkeypatch):
    agent.tool_lookup = {"measure": {"module_path": "unused", "function_name": "unused"}}
    tool = Mock()
    monkeypatch.setattr(agent.sandbox, "execute_tool", tool)
    post = Mock(return_value=response('{"action":"tool_call","tool_name":"measure"}', cost=0.2))
    monkeypatch.setattr("runner.scientific_agent.requests.post", post)
    result, _ = agent.run("No over-budget action", constraints={"max_cost": 0.1})
    assert post.call_count == 1
    tool.assert_not_called()
    assert result.status == "failed"
    assert result.summary_metrics["provider_reported_cost_usd"] == 0.2


@pytest.mark.parametrize("cost,include_usage", [(0.01, False), (float("nan"), True), (-1, True)])
def test_unknown_or_invalid_cost_stops_run(agent, monkeypatch, cost, include_usage):
    post = Mock(
        return_value=response(
            '{"action":"finish","findings":"Unsupported success"}',
            cost=cost,
            include_usage=include_usage,
        )
    )
    monkeypatch.setattr("runner.scientific_agent.requests.post", post)
    result, _ = agent.run("Honest accounting", constraints={"max_steps": 5})
    assert post.call_count == 1
    assert result.status == "failed"
    assert result.error.startswith("AGENT_USAGE_UNAVAILABLE")
    assert result.summary_metrics["cost_tracking_complete"] is False


def test_token_limit_and_completion_cap(agent, monkeypatch):
    post = Mock(return_value=response('{"action":"reflect"}', tokens=10))
    monkeypatch.setattr("runner.scientific_agent.requests.post", post)
    result, _ = agent.run(
        "Token cutoff", constraints={"max_total_tokens": 15, "max_tokens_per_call": 7}
    )
    assert post.call_count == 1
    assert post.call_args.kwargs["json"]["max_tokens"] == 7
    assert result.error.startswith("AGENT_TOKEN_LIMIT_REACHED")
    assert result.summary_metrics["total_tokens"] == 15


@pytest.mark.parametrize(
    "constraints",
    [
        {"max_cost": 0},
        {"max_steps": 0},
        {"max_total_tokens": 0},
        {"max_cost": -1},
        {"max_cost": float("nan")},
    ],
)
def test_empty_or_invalid_budget_never_calls_provider(agent, monkeypatch, constraints):
    post = Mock()
    monkeypatch.setattr("runner.scientific_agent.requests.post", post)
    result, _ = agent.run("Preflight budget", constraints=constraints)
    post.assert_not_called()
    assert result.status == "failed"


def test_missing_real_key_has_no_dummy_fallback(agent, monkeypatch):
    monkeypatch.setattr("runner.scientific_agent.LLM_API_KEY", "")
    post = Mock()
    monkeypatch.setattr("runner.scientific_agent.requests.post", post)
    result, _ = agent.run("No credential")
    post.assert_not_called()
    assert result.status == "failed"
    assert "API key required" in result.error
    assert result.summary_metrics["llm_calls"] == 1


def test_zero_cost_provider_response_can_finish(agent, monkeypatch):
    post = Mock(return_value=response('{"action":"finish","findings":"Explicit result"}', cost=0))
    monkeypatch.setattr("runner.scientific_agent.requests.post", post)
    result, _ = agent.run("Free provider")
    assert result.status == "success"
    assert result.summary_metrics["provider_reported_cost_usd"] == 0
    assert result.summary_metrics["cost_tracking_complete"] is True


def test_network_guard_rejects_accidental_http():
    import requests

    with pytest.raises(AssertionError, match="Tests are offline"):
        requests.get("https://example.com", timeout=1)
