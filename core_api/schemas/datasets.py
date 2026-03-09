"""Dataset schemas - Pydantic models for Dataset API."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DatasetBase(BaseModel):
    """Base dataset schema."""

    name: str = Field(..., description="Dataset name (must be unique)")
    description: str = Field(..., description="Dataset description")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Flexible metadata")
    tags: List[str] = Field(default_factory=list, description="Dataset tags")


class DatasetCreate(DatasetBase):
    """Schema for creating a dataset."""

    pass


class DatasetResponse(DatasetBase):
    """Schema for dataset response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class DatasetList(BaseModel):
    """Response for listing datasets."""

    datasets: List[DatasetResponse]
    count: int


