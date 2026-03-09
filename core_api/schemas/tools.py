"""Tool schemas - Pydantic models for Tool API."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ToolBase(BaseModel):
    """Base tool schema."""

    name: str = Field(..., description="Tool name (must be unique)")
    description: str = Field(..., description="Tool description")
    input_schema: Dict[str, Any] = Field(..., description="JSON Schema for tool inputs")
    output_schema: Dict[str, Any] = Field(..., description="JSON Schema for tool outputs")
    tags: List[str] = Field(default_factory=list, description="Tool tags")
    module_path: str = Field(..., description="Python module path (e.g., 'tools.jwst.photometry')")
    function_name: str = Field(..., description="Function name to call (e.g., 'extract_photometry')")


class ToolCreate(ToolBase):
    """Schema for creating a tool."""

    pass


class ToolResponse(ToolBase):
    """Schema for tool response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class ToolList(BaseModel):
    """Response for listing tools."""

    tools: List[ToolResponse]
    count: int


