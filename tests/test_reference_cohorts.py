import json
from pathlib import Path

import pytest

from data_pipeline.reference_cohorts import build_report, summarize_rows


def row(tier="one", identity="1", quality="A", z="7", ra="53", dec="-27"):
    return {
        "TIER": tier,
        "NIRSpec_ID": identity,
        "Unique_ID": tier + "_" + identity,
        "z_Spec_flag": quality,
        "z_Spec": z,
        "RA_TARG": ra,
        "Dec_TARG": dec,
        "Field": "GS",
        "ObsDate": "2025-01-01",
    }


def test_reused_source_id_is_not_silently_deduplicated():
    report = summarize_rows([row(), row(tier="two")])
    assert report["summary"]["tier_id_keys"] == 2
    assert report["cohort_counts"]["robust_high_z_ge_6"] == 2


def test_tentative_bad_redshift_and_bad_sky_never_enter_reference_cohort():
    report = summarize_rows(
        [
            row(),
            row(identity="2", quality="D"),
            row(identity="3", z="nan"),
            row(identity="4", z="-1"),
            row(identity="5", ra="nan"),
            row(identity="6", dec="91"),
            row(identity="7", quality="E", z="8"),
        ]
    )
    assert report["cohort_counts"]["robust_high_z_ge_6"] == 1
    assert report["invalid_coordinates"] == 2
    assert report["invalid_or_negative_spec_redshifts"] == 2


def test_cohort_boundaries_and_secure_c_separate():
    report = summarize_rows(
        [
            row(z="6"),
            row(identity="2", quality="B", z="0"),
            row(identity="3", z="3"),
            row(identity="4", quality="C", z="10"),
        ]
    )
    assert report["cohort_counts"] == {
        "robust_high_z_ge_6": 1,
        "robust_controls_0_le_z_lt_3": 1,
        "secure_c_high_z_ge_6": 1,
    }


def test_pinned_public_report_regenerates_without_network():
    root = Path(__file__).resolve().parents[1] / "data_sources" / "pilot"
    report = build_report(root / "jades_dr4_reference.csv")
    assert report == json.loads((root / "jades_dr4_cohorts.json").read_text())
    assert report["summary"]["observation_rows"] == 5190
    assert report["cohort_counts"]["robust_high_z_ge_6"] == 243
    assert report["candidate_crossmatch"]["status"] == "not_performed"


def test_modified_reference_bytes_refused(tmp_path):
    root = Path(__file__).resolve().parents[1] / "data_sources" / "pilot"
    target = tmp_path / "refs.csv"
    target.write_bytes((root / "jades_dr4_reference.csv").read_bytes() + b"tampered")
    target.with_name(target.name + ".provenance.json").write_bytes(
        (root / "jades_dr4_reference.csv.provenance.json").read_bytes()
    )
    with pytest.raises(ValueError, match="checksum/size"):
        build_report(target)
