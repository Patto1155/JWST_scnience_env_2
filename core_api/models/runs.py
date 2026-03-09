"""Run model - represents an experiment execution."""

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..db import Base


class Run(Base):
    """Experiment execution run."""

    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=True)
    status = Column(String, nullable=False, default="queued")  # queued, running, completed, failed
    spec = Column(JSON, nullable=False)  # ExperimentSpec used for this run
    result = Column(JSON, nullable=True)  # RunResult (when completed)
    trajectory = Column(JSON, nullable=True)  # Message history for agent runs
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Optional relationship
    experiment = relationship("Experiment", backref="runs")

    def __repr__(self) -> str:
        return f"<Run(id={self.id}, status='{self.status}')>"


