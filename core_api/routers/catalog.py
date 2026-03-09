"""Catalog router - endpoints for dataset catalog."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..db import get_db
from ..schemas.datasets import DatasetCreate, DatasetResponse, DatasetList
from ..services.catalog_service import CatalogService

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("/", response_model=DatasetList)
def list_datasets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    tags: Optional[List[str]] = Query(None),
    strict_ready: bool = Query(
        False,
        description=(
            "When true, only return datasets that pass strict real-data integrity "
            "checks (valid metadata.file_path and not quarantined)."
        ),
    ),
    db: Session = Depends(get_db),
):
    """List all datasets in the catalog."""
    datasets = CatalogService.list_datasets(
        db,
        skip=skip,
        limit=limit,
        tags=tags,
        strict_ready_only=strict_ready,
    )
    return DatasetList(datasets=datasets, count=len(datasets))


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(dataset_id: int, db: Session = Depends(get_db)):
    """Get a specific dataset by ID."""
    dataset = CatalogService.get_dataset(db, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.post("/", response_model=DatasetResponse, status_code=201)
def create_dataset(dataset: DatasetCreate, db: Session = Depends(get_db)):
    """Create a new dataset entry."""
    # Check if dataset with same name already exists
    existing = CatalogService.get_dataset_by_name(db, dataset.name)
    if existing:
        raise HTTPException(status_code=400, detail="Dataset with this name already exists")
    
    return CatalogService.create_dataset(db, dataset)


@router.delete("/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: int, db: Session = Depends(get_db)):
    """Delete a dataset."""
    success = CatalogService.delete_dataset(db, dataset_id)
    if not success:
        raise HTTPException(status_code=404, detail="Dataset not found")


