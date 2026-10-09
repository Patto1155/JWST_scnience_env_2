"""Adversarial denominator, spherical matching and leakage-group contracts."""

import hashlib
import json

import numpy as np
import pytest
from astropy.io import fits

from discovery.real_validation import (
    combine_epochs,
    grouped_jades,
    match_sky,
    real_metrics,
    sky_groups,
    star_references,
)


def coord(ra, dec=0):
    return {"ra_deg": ra, "dec_deg": dec}


def test_matching_uses_sphere_across_ra_wrap_and_at_pole():
    assert match_sky([coord(359.99999)], [coord(0.00001)], 0.1)[0]["status"] == "matched"
    assert match_sky([coord(0, 89.99999)], [coord(180, 89.99999)], 0.1)[0]["status"] == "matched"


def test_blend_is_unknown_for_both_references_and_no_sources_is_empty():
    result = match_sky([coord(1), coord(1.00001)], [coord(1.000005)], 0.2)
    assert [r["status"] for r in result] == ["ambiguous", "ambiguous"]
    assert match_sky([coord(1)], [], 0.2)[0]["status"] == "not_detected"
    assert match_sky([], [coord(1)], 0.2) == []
    with pytest.raises(ValueError):
        match_sky([], [], 0)


def test_conservative_split_groups_field_scope_ids_and_sentinels():
    rows = [
        {
            "Unique_ID": str(i),
            "Field": field,
            "NIRCam_DR5_ID": str(identifier),
            "RA_TARG": str(ra),
            "Dec_TARG": "0",
        }
        for i, (field, identifier, ra) in enumerate(
            [
                ("GS", 100, 1),
                ("GS", 100, 1.01),
                ("GN", 100, 189),
                ("GS", -1, 2),
                ("GS", -1, 2.1),
                ("GS", 0, 1.00001),
            ]
        )
    ]
    groups, result = sky_groups(rows)
    assert groups[0] == groups[1] == groups[5]
    assert len({groups[2], groups[3], groups[4], groups[0]}) == 4
    assert result["components_wider_than_radius"] == 1
    reordered, _ = sky_groups(list(reversed(rows)))
    assert reordered == list(reversed(groups))


def test_unknown_classification_never_becomes_retained_reference():
    metrics = real_metrics(
        [{"recovered": True, "rejected": None}, {"recovered": False, "rejected": None}]
    )
    assert metrics["counts"]["references"] == 2
    assert metrics["counts"]["accepted"] == 0
    assert metrics["end_to_end_completeness"]["estimate"] == 0
    assert metrics["unknown_survival_fraction_bounds"] == {
        "lower": 0,
        "upper": 0.5,
        "meaning": "bounds if every unclassified detection fails or passes the cut",
    }
    assert real_metrics([])["detection_completeness"]["status"] == "not_estimable"


def test_repeated_epoch_counts_sky_group_once():
    a = {"sky_group_id": "same", "status": "matched", "recovered": True, "rejected": False}
    b = {"sky_group_id": "same", "status": "matched", "recovered": True, "rejected": True}
    result = combine_epochs([{"outcomes": [a]}, {"outcomes": [b]}])
    assert result["covered_sky_groups"] == 1
    assert result["groups_covered_in_multiple_images"] == 1
    assert result["accepted_in_at_least_one_covered_image"] == 1
    assert result["accepted_in_every_covered_image"] == 0


def test_pinned_dr4_grouped_counts_and_independent_cohort_quality():
    from pathlib import Path

    refs, result = grouped_jades(Path("data_sources/pilot/jades_dr4_reference.csv"))
    assert result["group_cohort_counts"]["robust_high_z_ge_6"] == 226
    assert result["group_cohort_counts"]["robust_controls_0_le_z_lt_3"] == 1440
    assert result["group_cohort_counts"]["secure_c_high_z_ge_6"] == 41
    assert all(r["observation_ids"] for r in refs)


def test_star_catalogue_cull_rejects_nonstellar_types_and_bad_quality(tmp_path):
    # Test-only synthetic table verifies the cull; it is never called observed sky data.
    cols = [
        fits.Column(name="Number", format="K", array=np.arange(1, 6)),
        fits.Column(name="RA", format="D", array=np.ones(5)),
        fits.Column(name="DEC", format="D", array=np.zeros(5)),
        fits.Column(name="OBJECT_TYPE", format="J", array=[1, 4, 1, 1, 1]),
    ]
    data = {
        "SNR": [20, 20, 9, 20, 20],
        "SHARP": [0, 0, 0, 0.3, 0],
        "CROWD": [0, 0, 0, 0, 0],
        "FLAG": [0, 0, 0, 0, 1],
        "VEGA": [20] * 5,
        "ERR": [0.05] * 5,
    }
    for name, values in data.items():
        cols.append(fits.Column(name="F444W_" + name, format="D", array=values))
    path = tmp_path / "test-table.fits"
    fits.HDUList([fits.PrimaryHDU(), fits.BinTableHDU.from_columns(cols)]).writeto(path)
    receipt = {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
    }
    path.with_name(path.name + ".provenance.json").write_text(json.dumps(receipt))
    refs, report = star_references(path)
    assert report["raw_rows"] == 5
    assert len(refs) == 1
    assert refs[0]["source_id"] == "jwststars-m92-1"
    path.write_bytes(path.read_bytes() + b"corrupt")
    with pytest.raises(ValueError, match="Receipt mismatch"):
        star_references(path)
