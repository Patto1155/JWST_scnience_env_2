"""Offline tests for integrity and bounded acquisition; never call remote services."""

import hashlib
import io
import json
from pathlib import Path

import pytest

from data_pipeline import research_sources as sources


class Response(io.BytesIO):
    status = 200
    url = "https://example.org/resolved.fits"

    def __init__(self, content, headers=None):
        super().__init__(content)
        self.headers = headers or {}


def test_committed_manifest_is_valid():
    manifest = sources.load_manifest()
    assert len(manifest["sources"]) >= 8
    # A missing source is not silently replaced by a guessed URL.
    with pytest.raises(ValueError, match="unknown source"):
        sources.selected_product(manifest, "missing", "f444w")


def test_manifest_refuses_duplicate_sources():
    manifest = sources.load_manifest()
    manifest["sources"].append(manifest["sources"][0])
    with pytest.raises(ValueError, match="duplicate source"):
        sources.validate_manifest(manifest)


def test_known_huge_product_refused_before_network(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("network should not be called")

    monkeypatch.setattr(sources, "urlopen", forbidden)
    with pytest.raises(ValueError, match="manifest size"):
        sources.fetch_product({"expected_bytes": 10}, tmp_path / "x", max_bytes=5)


@pytest.mark.parametrize("headers", [{}, {"Content-Length": "6"}])
def test_byte_ceiling_leaves_no_partial_file(monkeypatch, tmp_path, headers):
    monkeypatch.setattr(sources, "urlopen", lambda *a, **k: Response(b"abcdef", headers))
    with pytest.raises(ValueError, match="byte ceiling"):
        sources.fetch_product(
            {"id": "x", "url": "https://example.org/x"}, tmp_path / "x", max_bytes=5
        )
    assert list(tmp_path.iterdir()) == []


def test_checksum_mismatch_leaves_no_partial_file(monkeypatch, tmp_path):
    monkeypatch.setattr(sources, "urlopen", lambda *a, **k: Response(b"abc"))
    with pytest.raises(ValueError, match="checksum mismatch"):
        sources.fetch_product(
            {"id": "x", "url": "https://example.org/x", "sha256": "bad"}, tmp_path / "x"
        )
    assert list(tmp_path.iterdir()) == []


def test_truncated_body_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(
        sources, "urlopen", lambda *a, **k: Response(b"abc", {"Content-Length": "4"})
    )
    with pytest.raises(ValueError, match="Content-Length"):
        sources.fetch_product({"id": "x", "url": "https://example.org/x"}, tmp_path / "x")
    assert list(tmp_path.iterdir()) == []


def test_download_receipt_records_actual_bytes(monkeypatch, tmp_path):
    monkeypatch.setattr(sources, "urlopen", lambda *a, **k: Response(b"abc", {"ETag": "opaque"}))
    product = {"id": "x", "url": "https://example.org/x", "expected_bytes": 3}
    receipt = sources.fetch_product(product, tmp_path / "x")
    assert (tmp_path / "x").read_bytes() == b"abc"
    assert receipt["sha256"] == hashlib.sha256(b"abc").hexdigest()
    assert receipt["resolved_url"] != receipt["requested_url"]
    assert json.loads((tmp_path / "x.provenance.json").read_text()) == receipt
    with pytest.raises(FileExistsError):
        sources.fetch_product(product, tmp_path / "x")


def test_downloaded_pilot_integrity():
    root = Path(__file__).resolve().parents[1] / "data_sources" / "pilot"
    receipts = list(root.glob("*.provenance.json"))
    assert receipts, "pilot receipts are part of the checked-in source inventory"
    for path in receipts:
        receipt = json.loads(path.read_text())
        data = path.with_name(path.name.removesuffix(".provenance.json")).read_bytes()
        assert len(data) == receipt["bytes"]
        assert hashlib.sha256(data).hexdigest() == receipt["sha256"]
