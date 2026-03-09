"""Shared strict run validation and dataset integrity checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models.datasets import Dataset
from ..schemas.experiments import ExperimentSpec

STRICT_VALIDATION_ERROR_CODE = "STRICT_RUN_VALIDATION_FAILED"
LEGACY_SAMPLE_DATASET_NAME = "jwst_ngc1234_f200w"


@dataclass
class ValidationIssue:
    """Single strict validation or integrity issue."""

    code: str
    message: str
    dataset: Optional[str] = None
    file_path: Optional[str] = None
    hint: Optional[str] = None
    severity: str = "error"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize issue for API responses/logging."""
        return {
            "code": self.code,
            "message": self.message,
            "dataset": self.dataset,
            "file_path": self.file_path,
            "hint": self.hint,
            "severity": self.severity,
        }


@dataclass
class StrictValidationResult:
    """Strict-mode validation result for a run spec."""

    strict_real_data: bool
    checked_datasets: List[str] = field(default_factory=list)
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        """True when no blocking issues were found."""
        return not any(issue.severity == "error" for issue in self.issues)

    def _legacy_issue_lists(self) -> Dict[str, List[str]]:
        """Build compatibility issue lists used by older clients/tests."""
        unresolved: List[str] = []
        missing_file_path: List[str] = []
        missing_files: List[str] = []
        quarantined: List[str] = []

        for issue in self.issues:
            if issue.code == "STRICT_DATASET_NOT_FOUND" and issue.dataset:
                unresolved.append(issue.dataset)
            elif (
                issue.code
                in ("STRICT_DATASET_METADATA_INVALID", "STRICT_DATASET_FILE_PATH_INVALID")
                and issue.dataset
            ):
                missing_file_path.append(issue.dataset)
            elif issue.code == "STRICT_DATASET_FILE_MISSING" and issue.dataset:
                missing_files.append(
                    f"{issue.dataset} -> {issue.file_path}" if issue.file_path else issue.dataset
                )
            elif issue.code == "STRICT_DATASET_QUARANTINED" and issue.dataset:
                quarantined.append(issue.dataset)

        return {
            "unresolved_datasets": unresolved,
            "datasets_missing_file_path": missing_file_path,
            "datasets_with_missing_files": missing_files,
            "quarantined_datasets": quarantined,
        }

    def to_payload(self) -> Dict[str, Any]:
        """Structured API payload for preflight endpoint."""
        legacy_lists = self._legacy_issue_lists()
        hints = [
            "Use canonical dataset names from /datasets (jwst_* style).",
            "Ensure every strict dataset has metadata.file_path mapped to an existing FITS file.",
            "Quarantined datasets must be repaired before strict runs.",
        ]

        return {
            "valid": self.valid,
            "strict_real_data": self.strict_real_data,
            "checked_datasets": self.checked_datasets,
            "issue_count": len(self.issues),
            "issues": [issue.to_dict() for issue in self.issues],
            "hints": hints,
            **legacy_lists,
        }

    def to_http_error_detail(self) -> Dict[str, Any]:
        """Standardized strict failure detail for HTTP 422 responses."""
        payload = self.to_payload()
        payload.update(
            {
                "code": STRICT_VALIDATION_ERROR_CODE,
                "message": (
                    "Strict real-data validation failed. "
                    "Fix dataset catalog integrity issues before queueing the run."
                ),
            }
        )
        return payload


@dataclass
class CatalogIntegrityIssue:
    """Dataset integrity issue discovered during startup audit."""

    dataset: str
    issues: List[ValidationIssue]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize issue bundle for logs."""
        return {
            "dataset": self.dataset,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass
class CatalogIntegrityReport:
    """Catalog-level integrity report generated at startup."""

    total_datasets: int
    valid_dataset_count: int
    invalid_dataset_count: int
    quarantined_count: int
    issues: List[CatalogIntegrityIssue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize report for logging and diagnostics."""
        return {
            "total_datasets": self.total_datasets,
            "valid_dataset_count": self.valid_dataset_count,
            "invalid_dataset_count": self.invalid_dataset_count,
            "quarantined_count": self.quarantined_count,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def _dataset_file_path_issue(
    dataset_name: str, message: str, file_path: Optional[str] = None
) -> ValidationIssue:
    """Build a standardized file_path-related validation issue."""
    code = "STRICT_DATASET_FILE_MISSING" if file_path else "STRICT_DATASET_FILE_PATH_INVALID"
    return ValidationIssue(
        code=code,
        message=message,
        dataset=dataset_name,
        file_path=file_path,
        hint="Update /datasets metadata.file_path to a valid local FITS file path.",
    )


def validate_dataset_record(dataset: Dataset) -> List[ValidationIssue]:
    """Validate integrity of a single dataset catalog row."""
    issues: List[ValidationIssue] = []
    dataset_name = dataset.name

    metadata = dataset.meta_data
    if not isinstance(metadata, dict):
        issues.append(
            ValidationIssue(
                code="STRICT_DATASET_METADATA_INVALID",
                message="Dataset metadata must be an object with metadata.file_path.",
                dataset=dataset_name,
                hint='Re-register dataset with metadata={..., "file_path": "..."}.',
            )
        )
        return issues

    file_path = metadata.get("file_path")
    if not isinstance(file_path, str) or not file_path.strip():
        issues.append(
            ValidationIssue(
                code="STRICT_DATASET_FILE_PATH_INVALID",
                message="metadata.file_path is missing or empty.",
                dataset=dataset_name,
                hint="Set metadata.file_path to an existing FITS file path.",
            )
        )
        return issues

    normalized = file_path.strip()
    path_obj = Path(normalized).expanduser()
    if not path_obj.exists():
        issues.append(
            _dataset_file_path_issue(
                dataset_name=dataset_name,
                message="metadata.file_path does not exist on disk.",
                file_path=normalized,
            )
        )
        return issues

    if not path_obj.is_file():
        issues.append(
            _dataset_file_path_issue(
                dataset_name=dataset_name,
                message="metadata.file_path exists but is not a file.",
                file_path=normalized,
            )
        )

    tags = dataset.tags or []
    integrity_status = str(metadata.get("integrity_status", "")).strip().lower()
    if "quarantined" in tags or integrity_status == "quarantined":
        issues.append(
            ValidationIssue(
                code="STRICT_DATASET_QUARANTINED",
                message="Dataset is quarantined due to previous integrity failures.",
                dataset=dataset_name,
                file_path=normalized,
                hint="Repair dataset metadata.file_path and remove quarantine markers.",
            )
        )

    return issues


def validate_strict_run_spec(db: Session, spec: ExperimentSpec) -> StrictValidationResult:
    """Validate strict run constraints against dataset catalog integrity."""
    constraints = spec.constraints or {}
    strict_real_data = bool(constraints.get("strict_real_data", False))
    datasets = list(spec.datasets or [])
    result = StrictValidationResult(
        strict_real_data=strict_real_data,
        checked_datasets=datasets,
    )

    if not strict_real_data:
        return result

    if not datasets:
        result.issues.append(
            ValidationIssue(
                code="STRICT_DATASETS_REQUIRED",
                message="Strict real-data mode requires at least one dataset from /datasets.",
                hint="Call GET /datasets and provide canonical dataset names in spec.datasets.",
            )
        )
        return result

    db_datasets = db.query(Dataset).filter(Dataset.name.in_(datasets)).all()
    dataset_lookup = {dataset.name: dataset for dataset in db_datasets}

    for dataset_name in datasets:
        dataset = dataset_lookup.get(dataset_name)
        if dataset is None:
            result.issues.append(
                ValidationIssue(
                    code="STRICT_DATASET_NOT_FOUND",
                    message="Dataset name is not registered in /datasets.",
                    dataset=dataset_name,
                    hint="Use canonical names from GET /datasets (jwst_* style).",
                )
            )
            continue

        result.issues.extend(validate_dataset_record(dataset))

    return result


def _apply_quarantine_markers(dataset: Dataset, issues: List[ValidationIssue]) -> None:
    """Apply quarantine metadata/tags to a dataset row."""
    metadata = dataset.meta_data if isinstance(dataset.meta_data, dict) else {}
    metadata = dict(metadata)
    metadata["integrity_status"] = "quarantined"
    metadata["integrity_checked_at"] = datetime.now(timezone.utc).isoformat()
    metadata["integrity_errors"] = [issue.code for issue in issues]
    dataset.meta_data = metadata

    tags = list(dataset.tags or [])
    if "quarantined" not in tags:
        tags.append("quarantined")
    dataset.tags = tags


def audit_dataset_catalog_integrity(
    db: Session,
    *,
    quarantine_invalid: bool = True,
) -> CatalogIntegrityReport:
    """Audit catalog dataset rows for strict integrity requirements."""
    datasets = db.query(Dataset).all()
    integrity_issues: List[CatalogIntegrityIssue] = []
    quarantined_count = 0

    for dataset in datasets:
        issues = validate_dataset_record(dataset)
        if not issues:
            continue

        integrity_issues.append(CatalogIntegrityIssue(dataset=dataset.name, issues=issues))

        if quarantine_invalid:
            _apply_quarantine_markers(dataset, issues)
            quarantined_count += 1

    if quarantine_invalid and integrity_issues:
        db.commit()

    total = len(datasets)
    invalid = len(integrity_issues)
    return CatalogIntegrityReport(
        total_datasets=total,
        valid_dataset_count=total - invalid,
        invalid_dataset_count=invalid,
        quarantined_count=quarantined_count,
        issues=integrity_issues,
    )
