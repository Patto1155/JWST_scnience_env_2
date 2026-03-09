"""Experiment schemas - Pydantic models for Experiment API."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ToolInvocation(BaseModel):
    """A single tool invocation in an experiment step."""

    tool_name: str = Field(..., description="Name of the tool to invoke")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")


class ExperimentSpec(BaseModel):
    """Complete experiment specification."""

    objective: str = Field(..., description="Natural language objective")
    datasets: List[str] = Field(default_factory=list, description="Dataset IDs or names to use")
    steps: Optional[List[ToolInvocation]] = Field(None, description="Ordered list of tool invocations (optional for agent mode)")
    constraints: Optional[Dict[str, Any]] = Field(None, description="Optional constraints (max_steps, max_cost, etc.)")
    model: Optional[str] = Field(None, description="LLM model to use (e.g., 'claude-3.5-sonnet', 'deepseek-v3.2')")


class ExperimentBase(BaseModel):
    """Base experiment schema."""

    name: str = Field(..., description="Experiment name")
    description: Optional[str] = Field(None, description="Experiment description")
    objective: str = Field(..., description="Natural language objective")
    spec: ExperimentSpec = Field(..., description="Full experiment specification")


class ExperimentCreate(ExperimentBase):
    """Schema for creating an experiment."""

    pass


class ExperimentResponse(ExperimentBase):
    """Schema for experiment response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class ExperimentList(BaseModel):
    """Response for listing experiments."""

    experiments: List[ExperimentResponse]
    count: int


