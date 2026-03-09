"""Dataset Catalog service - manages dataset catalog."""

from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.datasets import Dataset
from ..schemas.datasets import DatasetCreate, DatasetResponse
from ..services.strict_validation import validate_dataset_record


class CatalogService:
    """Service for managing datasets."""

    @staticmethod
    def create_dataset(db: Session, dataset: DatasetCreate) -> DatasetResponse:
        """Create a new dataset entry."""
        db_dataset = Dataset(
            name=dataset.name,
            description=dataset.description,
            meta_data=dataset.metadata,
            tags=dataset.tags,
        )
        db.add(db_dataset)
        db.commit()
        db.refresh(db_dataset)
        data = db_dataset.__dict__.copy()
        data['metadata'] = data.pop('meta_data', {})
        return DatasetResponse.model_validate(data)

    @staticmethod
    def get_dataset(db: Session, dataset_id: int) -> Optional[DatasetResponse]:
        """Get a dataset by ID."""
        db_dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if db_dataset:
            return DatasetResponse.model_validate(db_dataset)
        return None

    @staticmethod
    def get_dataset_by_name(db: Session, name: str) -> Optional[DatasetResponse]:
        """Get a dataset by name."""
        db_dataset = db.query(Dataset).filter(Dataset.name == name).first()
        if db_dataset:
            data = db_dataset.__dict__.copy()
            data['metadata'] = data.pop('meta_data', {})
            return DatasetResponse.model_validate(data)
        return None

    @staticmethod
    def list_datasets(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        tags: Optional[List[str]] = None,
        strict_ready_only: bool = False,
    ) -> List[DatasetResponse]:
        """List datasets with optional filtering."""
        query = db.query(Dataset)

        if tags:
            for tag in tags:
                query = query.filter(Dataset.tags.contains([tag]))

        if strict_ready_only:
            datasets = [ds for ds in query.all() if not validate_dataset_record(ds)]
            datasets = datasets[skip : skip + limit]
        else:
            datasets = query.offset(skip).limit(limit).all()

        result = []
        for ds in datasets:
            data = ds.__dict__.copy()
            data["metadata"] = data.pop("meta_data", {})
            result.append(DatasetResponse.model_validate(data))
        return result

    @staticmethod
    def delete_dataset(db: Session, dataset_id: int) -> bool:
        """Delete a dataset."""
        db_dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if db_dataset:
            db.delete(db_dataset)
            db.commit()
            return True
        return False


