"""Tests for JWST tool registration and prompt sync."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core_api.app import app
from core_api.startup import get_tool_definitions


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_tools_endpoint_exposes_jwst_visual_tools_and_photometry_schema(client: TestClient):
    """The API tool registry should expose the upgraded JWST visual workflow."""
    response = client.get("/tools")
    assert response.status_code == 200

    tools = {tool["name"]: tool for tool in response.json()["tools"]}
    for tool_name in (
        "compute_color_index",
        "detect_sources",
        "candidate_evidence_bundle",
        "render_field_overview",
    ):
        assert tool_name in tools

    extract_photometry = tools["extract_photometry"]
    input_properties = extract_photometry["input_schema"]["properties"]
    output_properties = extract_photometry["output_schema"]["properties"]

    for field_name in (
        "background_annulus_inner_radius",
        "background_annulus_outer_radius",
        "strict_data",
    ):
        assert field_name in input_properties

    for field_name in (
        "background_subtracted_flux",
        "background_subtracted_magnitude",
        "flux_error",
        "snr",
        "background_mean",
        "background_std",
        "coverage_fraction",
        "valid_pixel_count",
        "annulus_pixel_count",
    ):
        assert field_name in output_properties


def test_discovery_prompt_tools_exist_in_tool_definitions():
    """Every explicitly listed discovery-prompt tool should exist in startup definitions."""
    prompt_path = Path("memory_bank/DISCOVERY_PROMPT.md")
    prompt_text = prompt_path.read_text(encoding="utf-8")

    prompt_tools = set(re.findall(r"^- `([a-zA-Z0-9_]+)\(", prompt_text, re.MULTILINE))
    definition_tools = {tool.name for tool in get_tool_definitions()}

    assert prompt_tools
    assert prompt_tools - definition_tools == set()
