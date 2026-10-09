"""Real-data regressions for JWST visual evidence tools."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from core_api.db import SessionLocal
from core_api.models.datasets import Dataset
from discovery import build_universe_table as universe_table
from tools.jwst.photometry import extract_photometry
from tools.jwst.source_detection import detect_sources
from tools.jwst.visualization import candidate_evidence_bundle, render_field_overview


ROOT = Path(__file__).resolve().parents[2]

BLUE_PATH = (
    ROOT
    / "data"
    / "jwst"
    / "mastDownload"
    / "JWST"
    / "jw01180026001_03201_00003_nrca1"
    / "jw01180026001_03201_00003_nrca1_i2d.fits"
)
MID_PATH = (
    ROOT
    / "data"
    / "jwst"
    / "mastDownload"
    / "JWST"
    / "jw01180025001_07201_00002_nrca1"
    / "jw01180025001_07201_00002_nrca1_i2d.fits"
)
REFERENCE_PATH = (
    ROOT
    / "data"
    / "jwst"
    / "mastDownload"
    / "JWST"
    / "jw01180026001_09201_00003_nrcalong"
    / "jw01180026001_09201_00003_nrcalong_i2d.fits"
)


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def require_local_archive():
    missing = [path for path in (BLUE_PATH, MID_PATH, REFERENCE_PATH) if not path.is_file()]
    if missing:
        pytest.skip("Local JWST archive not provisioned: " + ", ".join(str(p) for p in missing))


def _register_pipeline_datasets() -> dict[str, str]:
    """Insert temporary dataset aliases for batch-pipeline coverage."""
    suffix = uuid4().hex[:8]
    dataset_map = {
        "F090W": f"jwst_test_gs_visual_f090w_{suffix}",
        "F200W": f"jwst_test_gs_visual_f200w_{suffix}",
        "F444W": f"jwst_test_gs_visual_f444w_{suffix}",
    }
    metadata_map = {
        dataset_map["F090W"]: {
            "target": "GS-MEDIUM-HST",
            "filter": "F090W",
            "instrument": "NIRCam",
            "file_path": str(BLUE_PATH),
        },
        dataset_map["F200W"]: {
            "target": "GS-MEDIUM-HST",
            "filter": "F200W",
            "instrument": "NIRCam",
            "file_path": str(MID_PATH),
        },
        dataset_map["F444W"]: {
            "target": "GS-MEDIUM-HST",
            "filter": "F444W",
            "instrument": "NIRCam",
            "file_path": str(REFERENCE_PATH),
        },
    }

    db = SessionLocal()
    try:
        for name, metadata in metadata_map.items():
            db.add(
                Dataset(
                    name=name,
                    description="temporary JWST fixture for visualization tests",
                    meta_data=metadata,
                    tags=["test", "jwst", "real-data"],
                )
            )
        db.commit()
    finally:
        db.close()

    return dataset_map


def _delete_pipeline_datasets(dataset_names: list[str]) -> None:
    """Delete temporary dataset aliases created for a test."""
    db = SessionLocal()
    try:
        for dataset_name in dataset_names:
            row = db.query(Dataset).filter(Dataset.name == dataset_name).first()
            if row is not None:
                db.delete(row)
        db.commit()
    finally:
        db.close()


def test_real_jwst_visual_tools_generate_catalog_evidence_and_overview(tmp_path: Path):
    """The real-data visual workflow should produce catalog, evidence, and overview artifacts."""
    catalog_dir = tmp_path / "catalogs"
    visual_dir = tmp_path / "visuals"

    catalog = detect_sources(
        image_data=str(REFERENCE_PATH),
        threshold_sigma=3.0,
        min_pixels=9,
        top_n=5,
        output_dir=str(catalog_dir),
        output_prefix="gs_reference",
        strict_data=True,
    )
    assert catalog["source_count"] > 0
    assert Path(catalog["catalog_path"]).exists()
    assert Path(catalog["segmentation_overlay_path"]).exists()
    assert catalog["top_sources"]
    assert len({item["source_id"] for item in catalog["top_sources"]}) == len(catalog["top_sources"])
    assert max(item["area"] for item in catalog["top_sources"]) > 100.0

    top_source = catalog["top_sources"][0]
    photometry = extract_photometry(
        image_data=str(REFERENCE_PATH),
        x=float(top_source["x"]),
        y=float(top_source["y"]),
        aperture_radius=3.0,
        strict_data=True,
    )
    assert photometry["dataset_name"] == str(REFERENCE_PATH)
    assert photometry["valid_pixel_count"] > 0
    assert photometry["coverage_fraction"] > 0.9
    assert "flux_error" in photometry
    assert "snr" in photometry

    evidence = candidate_evidence_bundle(
        reference_dataset=str(REFERENCE_PATH),
        comparison_datasets=[str(BLUE_PATH), str(MID_PATH)],
        catalog_path=catalog["catalog_path"],
        source_id=int(top_source["source_id"]),
        aperture_radii=[3],
        output_dir=str(visual_dir),
        output_prefix="gs_candidate",
        strict_data=True,
    )
    assert Path(evidence["output_path"]).exists()
    assert Path(evidence["sidecar_path"]).exists()
    assert len(evidence["artifacts"]) == 2
    assert str(REFERENCE_PATH) in evidence["photometry"]
    assert evidence["photometry"][str(REFERENCE_PATH)]["3"]["coverage_fraction"] > 0.0

    sidecar = json.loads(Path(evidence["sidecar_path"]).read_text(encoding="utf-8"))
    assert sidecar["source_id"] == int(top_source["source_id"])
    assert any(item["dataset_name"] == str(MID_PATH) for item in sidecar["datasets"])
    assert all("off_chip" in item for item in sidecar["datasets"])

    overview = render_field_overview(
        image_data=str(REFERENCE_PATH),
        catalog_path=catalog["catalog_path"],
        highlight_source_ids=[int(top_source["source_id"])],
        output_dir=str(visual_dir),
        output_prefix="gs_field",
        strict_data=True,
    )
    assert Path(overview["output_path"]).exists()
    assert overview["highlight_count"] == 1


def test_build_universe_table_pipeline_returns_source_level_candidate_artifacts(
    tmp_path: Path,
    monkeypatch,
):
    """The batch discovery pipeline should emit source-level candidate fields and visual artifacts."""
    research_dir = tmp_path / "research_output"
    visuals_dir = research_dir / "visuals"
    catalogs_dir = research_dir / "source_catalogs"
    visuals_dir.mkdir(parents=True, exist_ok=True)
    catalogs_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(universe_table, "RESEARCH_DIR", research_dir)
    monkeypatch.setattr(universe_table, "VISUALS_DIR", visuals_dir)
    monkeypatch.setattr(universe_table, "SOURCE_CATALOG_DIR", catalogs_dir)
    monkeypatch.setattr(universe_table, "APERTURE_RADII", [3])
    dataset_map = _register_pipeline_datasets()
    try:
        db = SessionLocal()
        try:
            datasets = db.query(Dataset).filter(Dataset.name.in_(dataset_map.values())).all()
        finally:
            db.close()

        entries = universe_table.build_universe_table(datasets)
        grouped = universe_table._group_entries_by_target(entries)
        candidates, validation_top, summary = universe_table._analyze_target_sources(
            "GS-MEDIUM-HST",
            grouped["GS-MEDIUM-HST"],
        )

        assert summary["target"] == "GS-MEDIUM-HST"
        assert Path(summary["catalog_path"]).exists()
        assert Path(summary["field_overview_path"]).exists()
        assert Path(summary["color_diagnostic_path"]).exists()
        assert summary["source_count"] > 0
        assert candidates
        assert validation_top

        candidate = validation_top[0]
        for key in (
            "target",
            "position",
            "f444_flux",
            "f090_flux",
            "ratio_f090_f444",
            "source_id",
            "reference_dataset",
            "sky_center",
            "quality_flags",
            "red_snr_r3",
            "coverage_fraction",
            "artifacts",
            "validation",
            "validation_score",
            "validation_status",
            "keep_reasons",
            "reject_reasons",
        ):
            assert key in candidate

        assert candidate["reference_dataset"] == dataset_map["F444W"]
        assert isinstance(candidate["quality_flags"], list)
        assert isinstance(candidate["keep_reasons"], list)
        assert isinstance(candidate["reject_reasons"], list)
        assert isinstance(candidate["validation"], dict)
        assert candidate["validation"]["validation_score"] == candidate["validation_score"]
        assert candidate["validation"]["validation_status"] == candidate["validation_status"]
        assert "component_scores" in candidate["validation"]
        assert candidate["artifacts"]
        for artifact in candidate["artifacts"]:
            assert Path(artifact["path"]).exists()
    finally:
        _delete_pipeline_datasets(list(dataset_map.values()))
