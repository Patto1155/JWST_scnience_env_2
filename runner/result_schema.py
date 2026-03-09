"""RunResult schema for runner."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RunResult(BaseModel):
    """Result of a run execution."""

    status: str = Field(..., description="success or failed")
    summary_metrics: Dict[str, Any] = Field(default_factory=dict, description="Key metrics")
    artifacts: List[str] = Field(
        default_factory=list,
        description="Absolute paths to generated artifact files",
    )
    log_summary: str = Field(default="", description="Summary of logs")
    error: Optional[str] = Field(None, description="Error message if failed")


