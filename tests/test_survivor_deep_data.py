"""Pinned acquisition controls independent of model-specific routines."""

import hashlib
import json

import pytest

from data_pipeline.survivor_deep_data import acquire, verify_pinned


def test_self_consistent_changed_receipt_is_rejected(tmp_path):
    path = tmp_path / "changed.fits"
    path.write_bytes(b"changed")
    receipt = {"bytes": 7, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    path.with_name(path.name + ".provenance.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="pinned"):
        verify_pinned(path, {"expected_bytes": 7, "sha256": "0" * 64})


def test_matching_pinned_cached_bytes_are_reused_without_network(tmp_path):
    path = tmp_path / "curve.xml"
    path.write_bytes(b"observed")
    receipt = {"bytes": 8, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    path.with_name(path.name + ".provenance.json").write_text(json.dumps(receipt))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "products": [
                    {
                        "filename": path.name,
                        "max_bytes": 64,
                        "kind": "photon_throughput_votable",
                        "expected_bytes": 8,
                        "sha256": receipt["sha256"],
                    }
                ]
            }
        )
    )
    result = acquire(tmp_path, manifest)
    assert result["actual_bytes"] == 8


def test_cached_product_cannot_evade_product_ceiling(tmp_path):
    path = tmp_path / "curve.xml"
    path.write_bytes(b"observed")
    receipt = {"bytes": 8, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    path.with_name(path.name + ".provenance.json").write_text(json.dumps(receipt))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "products": [
                    {
                        "filename": path.name,
                        "max_bytes": 7,
                        "kind": "photon_throughput_votable",
                        "expected_bytes": 8,
                        "sha256": receipt["sha256"],
                    }
                ]
            }
        )
    )
    with pytest.raises(ValueError, match="ceiling"):
        acquire(tmp_path, manifest)
