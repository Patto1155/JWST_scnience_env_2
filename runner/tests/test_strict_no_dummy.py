"""Tests for strict real-data mode (no dummy fallback)."""

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from runner.sandbox import Sandbox
from tools.jwst.fits_loader import smart_load_data


def test_smart_load_data_non_strict_still_falls_back_to_dummy():
    """Non-strict mode should preserve legacy dummy fallback."""
    data = smart_load_data("definitely_not_a_real_dataset_name_12345", strict_data=False)
    assert isinstance(data, np.ndarray)
    assert data.shape == (512, 512)


def test_smart_load_data_none_strict_raises():
    """Strict mode should reject missing dataset identifiers."""
    with pytest.raises(ValueError, match="Strict real-data mode enabled"):
        smart_load_data(None, strict_data=True)


def test_smart_load_data_missing_dataset_strict_raises():
    """Strict mode should raise instead of returning dummy arrays."""
    with pytest.raises(FileNotFoundError, match="Strict real-data mode enabled"):
        smart_load_data("definitely_not_a_real_dataset_name_12345", strict_data=True)


def test_sandbox_injects_strict_data_when_enabled(tmp_path):
    """Sandbox should inject strict_data=True for tools that support it."""
    sandbox = Sandbox(tmp_path, strict_no_dummy_fallback=True)
    captured = {}

    def tool_with_strict(image_data=None, strict_data=False):
        captured["strict_data"] = strict_data
        return {"ok": True}

    with patch.object(sandbox, "import_tool", return_value=tool_with_strict):
        result = sandbox.execute_tool("dummy.module", "dummy_func", {"image_data": "x"})

    assert result["ok"] is True
    assert captured["strict_data"] is True


def test_sandbox_preserves_explicit_strict_data_value(tmp_path):
    """Explicit strict_data passed by caller should not be overridden."""
    sandbox = Sandbox(tmp_path, strict_no_dummy_fallback=True)
    captured = {}

    def tool_with_strict(image_data=None, strict_data=True):
        captured["strict_data"] = strict_data
        return {"ok": True}

    with patch.object(sandbox, "import_tool", return_value=tool_with_strict):
        sandbox.execute_tool(
            "dummy.module",
            "dummy_func",
            {"image_data": "x", "strict_data": False},
        )

    assert captured["strict_data"] is False
