"""Run schemas - Pydantic models for Run API."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .experiments import ExperimentSpec


class Message(BaseModel):
    """A message in the agent trajectory/history."""
    
    role: Literal["user", "agent", "tool"] = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    tool_name: Optional[str] = Field(None, description="Tool name if role is 'tool'")
    timestamp: Optional[datetime] = Field(None, description="Message timestamp")


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


class RunBase(BaseModel):
    """Base run schema."""

    experiment_id: Optional[int] = Field(None, description="Associated experiment ID")
    spec: ExperimentSpec = Field(..., description="Experiment spec used for this run")


class RunCreate(RunBase):
    """Schema for creating/starting a run."""

    pass


class RunResponse(RunBase):
    """Schema for run response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str  # queued, running, completed, failed
    result: Optional[RunResult] = None
    trajectory: Optional[List[Message]] = Field(None, description="Agent message history")
    error_message: Optional[str] = None
    status_reason: Optional[str] = Field(
        None,
        description="Machine-readable reason describing current status state.",
    )
    status_hints: List[str] = Field(
        default_factory=list,
        description="Actionable hints for queued/stuck/failed runs.",
    )
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class RunList(BaseModel):
    """Response for listing runs."""

    runs: List[RunResponse]
    count: int


class RunValidationIssue(BaseModel):
    """Structured preflight validation issue."""

    code: str
    message: str
    dataset: Optional[str] = None
    file_path: Optional[str] = None
    hint: Optional[str] = None
    severity: str = "error"


class RunValidationResponse(BaseModel):
    """Preflight response for run validation before queueing."""

    valid: bool
    strict_real_data: bool
    checked_datasets: List[str] = Field(default_factory=list)
    tool_count: int = 0
    issue_count: int = 0
    issues: List[RunValidationIssue] = Field(default_factory=list)
    hints: List[str] = Field(default_factory=list)
    unresolved_datasets: List[str] = Field(default_factory=list)
    datasets_missing_file_path: List[str] = Field(default_factory=list)
    datasets_with_missing_files: List[str] = Field(default_factory=list)
    quarantined_datasets: List[str] = Field(default_factory=list)


