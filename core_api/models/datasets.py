"""Dataset model - represents a dataset in the catalog."""

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime
from sqlalchemy.sql import func
from ..db import Base


class Dataset(Base):
    """Dataset catalog entry."""

    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=False)
    meta_data = Column("metadata", JSON, default=dict)  # Flexible metadata (filters, bands, etc.)
    tags = Column(JSON, default=list)  # List of strings
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Dataset(id={self.id}, name='{self.name}')>"


