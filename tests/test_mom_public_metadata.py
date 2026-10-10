"""Independent geometry and frozen inventory/budget invariants."""

import hashlib
import json

import pytest

from data_pipeline.mom_public_metadata import (
    angular_separation_arcsec,
    replay,
    verify_responses,
)


def test_great_circle_geometry():
    assert angular_separation_arcsec(0, 0, 1 / 3600, 0) == pytest.approx(1)
    assert angular_separation_arcsec(359.999, 0, 0.001, 0) == pytest.approx(7.2)
    assert angular_separation_arcsec(0, 90, 180, 90) < 1e-8


def test_receipt_rejects_corrupted_bytes(tmp_path):
    payload = b"original"
    (tmp_path / "one.response").write_bytes(payload)
    receipt = {
        "response_bytes": len(payload),
        "cap_bytes": 100,
        "endpoint_cap": 1,
        "queries": [
            {
                "path": "one.response",
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        ],
    }
    (tmp_path / "receipt.json").write_text(json.dumps(receipt))
    assert verify_responses(tmp_path) == receipt
    (tmp_path / "one.response").write_bytes(b"corrupt!")
    with pytest.raises(ValueError, match="differs"):
        verify_responses(tmp_path)


def test_frozen_archive_is_incomplete_and_no_new_measurement():
    report = replay()
    assert report["endpoint_count"] == 12
    assert report["response_bytes"] == 470251
    assert report["cached_CAL_hash_verified_count"] == 9
    capers, mom = report["released_extractions"]
    assert capers["program"] == "6368" and capers["offset_arcsec"] < 0.04
    assert capers["disjoint_from_baseline_exposure_roots"]
    assert not mom["disjoint_from_baseline_exposure_roots"]
    assert report["public_reference_metadata_dummy"]
    assert report["footprint_null_time_programs"] == ["10361", "11892"]
    assert not report["public_product_samples_and_program_page"]["mast_program"][
        "complete_pagination"
    ]
