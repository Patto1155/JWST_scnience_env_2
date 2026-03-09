"""Experiments router - endpoints for experiment definitions."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..db import get_db
from ..models.experiments import Experiment
from ..schemas.experiments import ExperimentCreate, ExperimentResponse, ExperimentList

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("/", response_model=ExperimentList)
def list_experiments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """List all experiment definitions."""
    experiments = db.query(Experiment).offset(skip).limit(limit).all()
    responses = [ExperimentResponse.model_validate(exp) for exp in experiments]
    return ExperimentList(experiments=responses, count=len(responses))


@router.get("/{experiment_id}", response_model=ExperimentResponse)
def get_experiment(experiment_id: int, db: Session = Depends(get_db)):
    """Get a specific experiment by ID."""
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return ExperimentResponse.model_validate(experiment)


@router.post("/", response_model=ExperimentResponse, status_code=201)
def create_experiment(experiment: ExperimentCreate, db: Session = Depends(get_db)):
    """Create a new experiment definition."""
    db_experiment = Experiment(
        name=experiment.name,
        description=experiment.description,
        objective=experiment.objective,
        spec=experiment.spec.model_dump(),
    )
    db.add(db_experiment)
    db.commit()
    db.refresh(db_experiment)
    return ExperimentResponse.model_validate(db_experiment)


