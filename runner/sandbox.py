"""Sandbox execution environment for experiments."""

import os
import sys
import importlib
import inspect
from typing import Any, Dict, Callable
from pathlib import Path


class Sandbox:
    """Sandboxed execution environment."""

    def __init__(self, work_dir: Path, strict_no_dummy_fallback: bool = False):
        """Initialize sandbox with work directory."""
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._module_cache: Dict[str, Any] = {}
        self.strict_no_dummy_fallback = strict_no_dummy_fallback

    def set_strict_no_dummy_fallback(self, enabled: bool):
        """Enable/disable strict real-data mode for tool calls."""
        self.strict_no_dummy_fallback = bool(enabled)

    def _supports_parameter(self, func: Callable, param_name: str) -> bool:
        """Return True if func accepts param_name explicitly or via **kwargs."""
        try:
            sig = inspect.signature(func)
        except (TypeError, ValueError):
            return False

        if param_name in sig.parameters:
            return True

        for param in sig.parameters.values():
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                return True

        return False

    def import_tool(self, module_path: str, function_name: str) -> Callable:
        """Import a tool function from a module."""
        cache_key = f"{module_path}.{function_name}"
        
        if cache_key in self._module_cache:
            return self._module_cache[cache_key]
        
        try:
            module = importlib.import_module(module_path)
            func = getattr(module, function_name)
            self._module_cache[cache_key] = func
            return func
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Could not import tool {module_path}.{function_name}: {e}")

    def execute_tool(
        self,
        module_path: str,
        function_name: str,
        parameters: Dict[str, Any],
    ) -> Any:
        """Execute a tool with given parameters."""
        func = self.import_tool(module_path, function_name)
        call_params = dict(parameters or {})

        # Enforce strict real-data mode by injecting strict flags when supported.
        if self.strict_no_dummy_fallback:
            if "strict_data" not in call_params and self._supports_parameter(func, "strict_data"):
                call_params["strict_data"] = True
            elif "strict_real_data" not in call_params and self._supports_parameter(func, "strict_real_data"):
                call_params["strict_real_data"] = True
        
        # Change to work directory for execution
        original_cwd = os.getcwd()
        try:
            os.chdir(self.work_dir)
            result = func(**call_params)
            return result
        finally:
            os.chdir(original_cwd)

    def get_artifact_path(self, filename: str) -> Path:
        """Get path for an artifact file."""
        return self.work_dir / filename


