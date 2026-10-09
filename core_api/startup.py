"""Startup script to register tools and initialize sample datasets."""

from __future__ import annotations

from copy import deepcopy

from core_api.db import SessionLocal, init_db
from core_api.models.datasets import Dataset
from core_api.models.tools import Tool
from core_api.schemas.tools import ToolCreate
from core_api.services.strict_validation import (
    LEGACY_SAMPLE_DATASET_NAME,
    audit_dataset_catalog_integrity,
)


def get_tool_definitions():
    """Get definitions of all tools to register."""
    return [
        ToolCreate(
            name="extract_photometry",
            description="Measure raw and calibrated Jy/AB aperture photometry with explicit coverage, calibration status and diagonal noise limits",
            input_schema={
                "type": "object",
                "properties": {
                    "image_data": {"description": "Image array data or dataset name", "type": ["array", "string", "null"]},
                    "x": {"description": "X coordinate of source", "type": "number"},
                    "y": {"description": "Y coordinate of source", "type": "number"},
                    "aperture_radius": {"description": "Aperture radius in pixels", "type": "number", "default": 5.0},
                    "background_annulus_inner_radius": {
                        "description": "Inner radius for local background annulus in pixels",
                        "type": "number",
                        "default": 6.0,
                    },
                    "background_annulus_outer_radius": {
                        "description": "Outer radius for local background annulus in pixels",
                        "type": "number",
                        "default": 10.0,
                    },
                    "ra_deg": {"description": "ICRS right ascension in degrees; use with dec_deg instead of x/y", "type": "number"},
                    "dec_deg": {"description": "ICRS declination in degrees; requires ra_deg and celestial WCS", "type": "number"},
                    "aperture_radius_arcsec": {"description": "Matched sky aperture radius; requires celestial WCS", "type": ["number", "null"]},
                    "background_annulus_inner_radius_arcsec": {"description": "Angular background inner radius; defaults to 1.2 times angular aperture", "type": ["number", "null"]},
                    "background_annulus_outer_radius_arcsec": {"description": "Angular background outer radius; defaults to 2 times angular aperture", "type": ["number", "null"]},
                    "strict_data": {
                        "description": "Disable dummy fallback and require real dataset loading",
                        "type": "boolean",
                    },
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "flux": {"type": ["number", "null"]},
                    "magnitude": {"type": ["number", "null"]},
                    "background_subtracted_flux": {"type": ["number", "null"]},
                    "background_subtracted_magnitude": {"type": ["number", "null"]},
                    "flux_error": {"type": ["number", "null"]},
                    "snr": {"type": ["number", "null"]},
                    "background_mean": {"type": ["number", "null"]},
                    "background_std": {"type": ["number", "null"]},
                    "flux_jy": {"description": "Calibrated aperture flux density in Jy, or unavailable", "type": ["number", "null"]},
                    "background_subtracted_flux_jy": {"type": ["number", "null"]},
                    "flux_error_jy": {"description": "Diagonal uncertainty, excluding drizzle covariance and systematics", "type": ["number", "null"]},
                    "raw_flux_unit": {"type": "string"},
                    "calibration_status": {"type": "string"},
                    "measurement_status": {"type": "string"},
                    "background_status": {"type": "string"},
                    "magnitude_system": {"type": ["string", "null"]},
                    "pixel_area_source": {"type": ["string", "null"]},
                    "mean_pixel_area_sr": {"type": ["number", "null"]},
                    "uncertainty_method": {"type": "string"},
                    "uncertainty_assumptions": {"type": "string"},
                    "snr_basis": {"type": ["string", "null"]},
                    "aperture_radius_arcsec": {"type": ["number", "null"]},
                    "background_annulus_inner_radius_arcsec": {"type": ["number", "null"]},
                    "background_annulus_outer_radius_arcsec": {"type": ["number", "null"]},
                    "coverage_fraction": {"type": "number"},
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "aperture_radius": {"type": "number"},
                    "pixels_in_aperture": {"type": "integer"},
                    "valid_pixel_count": {"type": "integer"},
                    "annulus_pixel_count": {"type": "integer"},
                },
            },
            tags=["jwst", "photometry", "aperture", "uncertainty"],
            module_path="tools.jwst.photometry",
            function_name="extract_photometry",
        ),
        ToolCreate(
            name="compute_color_index",
            description="Compute an AB colour and flux ratio from positive flux densities in the same physical unit (prefer calibrated Jy; never unmatched raw image sums)",
            input_schema={
                "type": "object",
                "properties": {
                    "flux_band1": {"description": "Positive first-band flux density in the same physical unit as band two (prefer Jy)", "type": "number"},
                    "flux_band2": {"description": "Positive second-band flux density in the same physical unit as band one (prefer Jy)", "type": "number"},
                },
                "required": ["flux_band1", "flux_band2"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "color_index": {"type": ["number", "null"]},
                    "flux_ratio": {"type": ["number", "null"]},
                    "band1_flux": {"type": "number"},
                    "band2_flux": {"type": "number"},
                    "error": {"type": "string"},
                },
            },
            tags=["jwst", "photometry", "color"],
            module_path="tools.jwst.photometry",
            function_name="compute_color_index",
        ),
        ToolCreate(
            name="image_statistics",
            description="Compute basic statistics for JWST image data",
            input_schema={
                "type": "object",
                "properties": {
                    "image_data": {"description": "Image array data or dataset name", "type": ["array", "string", "null"]},
                    "region": {
                        "description": "Optional region with x_min/x_max/y_min/y_max",
                        "type": "object",
                    },
                    "strict_data": {"description": "Disable dummy fallback and require real dataset loading", "type": "boolean"},
                },
                "required": ["image_data"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "mean": {"type": "number"},
                    "median": {"type": "number"},
                    "std": {"type": "number"},
                    "min": {"type": "number"},
                    "max": {"type": "number"},
                },
            },
            tags=["jwst", "statistics"],
            module_path="tools.jwst.basic_stats",
            function_name="image_statistics",
        ),
        ToolCreate(
            name="brightness_distribution",
            description="Compute brightness histogram for JWST image data",
            input_schema={
                "type": "object",
                "properties": {
                    "image_data": {"description": "Image array data or dataset name", "type": ["array", "string", "null"]},
                    "bins": {"description": "Number of histogram bins", "type": "integer", "default": 50},
                    "strict_data": {"description": "Disable dummy fallback and require real dataset loading", "type": "boolean"},
                },
                "required": ["image_data"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "bin_centers": {"type": "array", "items": {"type": "number"}},
                    "counts": {"type": "array", "items": {"type": "integer"}},
                    "bin_edges": {"type": "array", "items": {"type": "number"}},
                    "total_pixels": {"type": "integer"},
                },
            },
            tags=["jwst", "statistics", "histogram"],
            module_path="tools.jwst.basic_stats",
            function_name="brightness_distribution",
        ),
        ToolCreate(
            name="compare_images",
            description="Compare two JWST images and summarize differences",
            input_schema={
                "type": "object",
                "properties": {
                    "image1_data": {"description": "First image array or dataset name", "type": ["array", "string", "null"]},
                    "image2_data": {"description": "Second image array or dataset name", "type": ["array", "string", "null"]},
                    "strict_data": {"description": "Disable dummy fallback and require real dataset loading", "type": "boolean"},
                },
                "required": ["image1_data", "image2_data"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "image1_mean": {"type": "number"},
                    "image2_mean": {"type": "number"},
                    "mean_difference": {"type": "number"},
                    "std_difference": {"type": "number"},
                    "rms_difference": {"type": "number"},
                    "correlation": {"type": "number"},
                },
            },
            tags=["jwst", "statistics", "comparison"],
            module_path="tools.jwst.basic_stats",
            function_name="compare_images",
        ),
        ToolCreate(
            name="detect_sources",
            description="Detect de-duplicated astronomical sources in a JWST image and save a reusable JSON catalog",
            input_schema={
                "type": "object",
                "properties": {
                    "image_data": {"description": "Dataset name to segment", "type": "string"},
                    "threshold_sigma": {"description": "Detection threshold in sigma above the local background", "type": "number", "default": 3.0},
                    "min_pixels": {"description": "Minimum connected pixels per source", "type": "integer", "default": 9},
                    "deblend": {"description": "Whether to deblend overlapping detections", "type": "boolean", "default": True},
                    "top_n": {"description": "Maximum number of top sources to summarize inline", "type": "integer", "default": 50},
                    "border_margin": {"description": "Exclude detections this close to the image edge", "type": "integer", "default": 16},
                    "output_dir": {"description": "Directory for JSON catalogs and segmentation overlays", "type": "string", "default": "catalogs"},
                    "output_prefix": {"description": "Optional filename prefix for outputs", "type": ["string", "null"]},
                    "strict_data": {"description": "Disable dummy fallback and require real dataset loading", "type": "boolean"},
                },
                "required": ["image_data"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "source_count": {"type": "integer"},
                    "catalog_path": {"type": "string"},
                    "segmentation_overlay_path": {"type": "string"},
                    "top_sources": {"type": "array", "items": {"type": "object"}},
                },
            },
            tags=["jwst", "segmentation", "catalog"],
            module_path="tools.jwst.source_detection",
            function_name="detect_sources",
        ),
        ToolCreate(
            name="candidate_evidence_bundle",
            description="Create calibrated multi-band evidence with matched sky apertures and Jy colour diagnostics; PSFs remain uncorrected",
            input_schema={
                "type": "object",
                "properties": {
                    "reference_dataset": {"description": "Reference dataset used for centroiding and S/N panels", "type": "string"},
                    "comparison_datasets": {
                        "description": "Datasets to render as science cutout panels",
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "x": {"description": "Reference pixel X coordinate", "type": "number"},
                    "y": {"description": "Reference pixel Y coordinate", "type": "number"},
                    "catalog_path": {"description": "Optional source catalog JSON path", "type": ["string", "null"]},
                    "source_id": {"description": "Optional source identifier from detect_sources catalog", "type": ["integer", "null"]},
                    "cutout_size": {"description": "Square cutout size in pixels", "type": "integer", "default": 64},
                    "aperture_radii": {
                        "description": "Reference-grid aperture radius keys (must include 3); mapped to common angular radii when WCS exists",
                        "type": "array",
                        "items": {"type": "integer"},
                        "default": [2, 3, 5],
                    },
                    "background_annulus_inner_radius": {"description": "Inner radius for local background annulus", "type": "number", "default": 6.0},
                    "background_annulus_outer_radius": {"description": "Outer radius for local background annulus", "type": "number", "default": 10.0},
                    "aperture_radius_arcsec": {"description": "Override angular radius for key 3 (other keys scale proportionally); defaults to reference WCS area", "type": ["number", "null"]},
                    "background_annulus_inner_radius_arcsec": {"description": "Matched angular background inner radius", "type": ["number", "null"]},
                    "background_annulus_outer_radius_arcsec": {"description": "Matched angular background outer radius", "type": ["number", "null"]},
                    "output_dir": {"description": "Directory for panels and sidecars", "type": "string", "default": "visuals"},
                    "output_prefix": {"description": "Optional filename prefix for outputs", "type": ["string", "null"]},
                    "strict_data": {"description": "Disable dummy fallback and require real dataset loading", "type": "boolean"},
                },
                "required": ["reference_dataset", "comparison_datasets"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "output_path": {"type": "string"},
                    "sidecar_path": {"type": "string"},
                    "quality_flags": {"type": "array", "items": {"type": "string"}},
                    "ratio_f090_f444": {"type": ["number", "null"]},
                    "photometry": {"type": "object"},
                    "color_indices": {"type": "object"},
                    "color_flux_unit": {"type": "string"},
                    "color_status": {"type": "string"},
                    "aperture_matching": {"type": "string"},
                    "cache_hit": {"type": "boolean"},
                },
            },
            tags=["jwst", "visualization", "candidate"],
            module_path="tools.jwst.visualization",
            function_name="candidate_evidence_bundle",
        ),
        ToolCreate(
            name="render_field_overview",
            description="Render a JWST field overview with detected sources and highlighted candidates",
            input_schema={
                "type": "object",
                "properties": {
                    "image_data": {"description": "Dataset name for the overview image", "type": "string"},
                    "catalog_path": {"description": "Source catalog JSON from detect_sources", "type": "string"},
                    "highlight_source_ids": {
                        "description": "Optional list of source ids or objects with source_id/suspect keys",
                        "type": "array",
                        "items": {"type": ["integer", "object"]},
                    },
                    "top_n": {"description": "Maximum number of brightest sources to annotate", "type": "integer", "default": 50},
                    "output_dir": {"description": "Directory for saved overview image", "type": "string", "default": "visuals"},
                    "output_prefix": {"description": "Optional filename prefix for outputs", "type": ["string", "null"]},
                    "strict_data": {"description": "Disable dummy fallback and require real dataset loading", "type": "boolean"},
                },
                "required": ["image_data", "catalog_path"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "output_path": {"type": "string"},
                    "highlight_count": {"type": "integer"},
                    "artifacts": {"type": "array", "items": {"type": "object"}},
                },
            },
            tags=["jwst", "visualization", "overview"],
            module_path="tools.jwst.visualization",
            function_name="render_field_overview",
        ),
        ToolCreate(
            name="compute_mean",
            description="Compute mean of a list of values",
            input_schema={
                "type": "object",
                "properties": {
                    "values": {"description": "List of numeric values", "type": "array", "items": {"type": "number"}},
                },
                "required": ["values"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "mean": {"type": "number"},
                    "count": {"type": "integer"},
                },
            },
            tags=["core", "statistics"],
            module_path="tools.core.stats",
            function_name="compute_mean",
        ),
    ]


def get_sample_datasets():
    """Get sample dataset definitions.

    Intentionally empty: strict science workflows require real catalog entries with
    valid metadata.file_path mappings. Legacy dummy-like samples are quarantined by
    startup integrity checks instead of auto-registered.
    """
    return []


def register_tools(db):
    """Register or update all tools in the database."""
    tool_defs = get_tool_definitions()
    registered = 0
    updated = 0

    for tool_def in tool_defs:
        existing = db.query(Tool).filter(Tool.name == tool_def.name).first()
        if existing:
            new_values = {
                "description": tool_def.description,
                "input_schema": deepcopy(tool_def.input_schema),
                "output_schema": deepcopy(tool_def.output_schema),
                "tags": list(tool_def.tags or []),
                "module_path": tool_def.module_path,
                "function_name": tool_def.function_name,
            }
            changed = False
            for attr, value in new_values.items():
                if getattr(existing, attr) != value:
                    setattr(existing, attr, value)
                    changed = True
            if changed:
                updated += 1
            continue

        db.add(
            Tool(
                name=tool_def.name,
                description=tool_def.description,
                input_schema=deepcopy(tool_def.input_schema),
                output_schema=deepcopy(tool_def.output_schema),
                tags=list(tool_def.tags or []),
                module_path=tool_def.module_path,
                function_name=tool_def.function_name,
            )
        )
        registered += 1

    db.commit()
    return registered, updated


def register_datasets(db):
    """Register sample datasets in the database (currently none)."""
    dataset_defs = get_sample_datasets()
    registered = 0
    skipped = 0

    for dataset_def in dataset_defs:
        existing = db.query(Dataset).filter(Dataset.name == dataset_def.name).first()
        if existing:
            skipped += 1
            continue

        db.add(
            Dataset(
                name=dataset_def.name,
                description=dataset_def.description,
                meta_data=dataset_def.metadata,
                tags=dataset_def.tags,
            )
        )
        registered += 1

    db.commit()
    return registered, skipped


def validate_dataset_catalog_integrity(db):
    """Validate and quarantine datasets with integrity failures."""
    report = audit_dataset_catalog_integrity(db, quarantine_invalid=True)
    if report.invalid_dataset_count == 0:
        print("[INTEGRITY] Dataset catalog passed strict integrity checks")
        return report

    print(
        "[INTEGRITY] Quarantined "
        f"{report.quarantined_count} invalid dataset(s) "
        f"(invalid={report.invalid_dataset_count}, total={report.total_datasets})"
    )
    for issue_bundle in report.issues[:10]:
        dataset_name = issue_bundle.dataset
        issue_codes = ", ".join(issue.code for issue in issue_bundle.issues)
        if dataset_name == LEGACY_SAMPLE_DATASET_NAME:
            print(
                f"[INTEGRITY] Legacy dataset '{dataset_name}' quarantined: {issue_codes}"
            )
        else:
            print(f"[INTEGRITY] Dataset '{dataset_name}' quarantined: {issue_codes}")

    return report


def initialize_system():
    """Initialize the system with tools and datasets."""
    print("Initializing Science OS...")
    init_db()

    db = SessionLocal()
    try:
        reg_count, upd_count = register_tools(db)
        print(f"  Tool sync complete: registered {reg_count}, updated {upd_count}")

        reg_count, skip_count = register_datasets(db)
        print(f"  Registered {reg_count} datasets, skipped {skip_count} existing")

        validate_dataset_catalog_integrity(db)

        print("Initialization complete!")
    finally:
        db.close()


if __name__ == "__main__":
    initialize_system()
