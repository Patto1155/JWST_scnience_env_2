"""Tool model - represents a registered tool in the system."""

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime
from sqlalchemy.sql import func
from ..db import Base


class Tool(Base):
    """Tool registry entry."""

    __tablename__ = "tools"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=False)
    input_schema = Column(JSON, nullable=False)  # JSON Schema or Pydantic model schema
    output_schema = Column(JSON, nullable=False)
    tags = Column(JSON, default=list)  # List of strings
    module_path = Column(String, nullable=False)  # e.g., "tools.jwst.photometry"
    function_name = Column(String, nullable=False)  # e.g., "extract_photometry"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Tool(id={self.id}, name='{self.name}')>"


