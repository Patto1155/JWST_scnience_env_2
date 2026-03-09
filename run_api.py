"""Launcher script for Science OS API."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "core_api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disabled for background tasks to work properly
    )

