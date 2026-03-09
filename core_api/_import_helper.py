"""Import helper to handle hyphenated directory name.

This module sets up the import system to handle 'core-api' directory name.
It should be imported first in any module that needs to import from ..
"""

import sys
from pathlib import Path

# Get the core-api directory
_core_api_dir = Path(__file__).parent
_parent_dir = _core_api_dir.parent

# Add parent to path if not already there
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

# Create a module proxy for 'core-api' imports
class CoreApiProxy:
    """Proxy module to handle core-api imports."""
    pass

# Register the proxy in sys.modules
if "core-api" not in sys.modules:
    sys.modules["core-api"] = CoreApiProxy()

