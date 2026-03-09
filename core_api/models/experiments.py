"""Experiment model - represents an experiment definition."""

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime
from sqlalchemy.sql import func
from ..db import Base


class Experiment(Base):
    """Experiment definition."""

    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text)
    objective = Column(Text, nullable=False)  # Natural language objective
    spec = Column(JSON, nullable=False)  # Full ExperimentSpec JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Experiment(id={self.id}, name='{self.name}')>"


