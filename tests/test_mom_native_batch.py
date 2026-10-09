from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import data_pipeline.mom_native_batch as batch
from data_pipeline.rotating_benchmarks import TableParser


def test_products_come_from_identity_verified_actual_spectrum():
    root = Path(__file__).resolve().parents[1]
    products, _ = batch.exposure_products(root / "data_sources/pilot/mom_z14_dja_v4.spec.fits")
    assert len(products) == len({r["filename"] for r in products}) == 9
    assert sorted(p["position_number"] for p in products) == [1, 1, 1, 2, 2, 2, 3, 3, 3]
    assert sum(p["exposure_time_s"] for p in products) == pytest.approx(15756.003)


def test_batch_refuses_total_budget_before_any_download(monkeypatch, tmp_path):
    product = {"filename": "exposure.fits", "url": "https://example.org/a", "source_slits_filename": "actual_metadata"}
    inventory = {"source_spectrum_sha256": "spectrum", "products": [{**product, "expected_bytes": 20, "sha256": "a" * 64}]}
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(inventory))
    monkeypatch.setattr(batch, "INVENTORY", path)
    monkeypatch.setattr(batch, "exposure_products", lambda _: ([product], {"sha256": "spectrum"}))
    monkeypatch.setattr(batch, "probe_product", lambda *a, **kw: {"status": 200, "content_length": "20"})
    monkeypatch.setattr(batch, "fetch_product", lambda *a, **kw: pytest.fail("Download must not start"))
    with pytest.raises(ValueError, match="Aggregate"):
        batch.acquire_batch(tmp_path / "spectrum", tmp_path / "output", max_bytes=19)
    with pytest.raises(ValueError, match="600MiB"):
        batch.acquire_batch(tmp_path / "spectrum", tmp_path / "output", max_bytes=batch.TOTAL_CAP + 1)


def test_coherent_cached_native_original_cannot_replace_pinned_inventory(monkeypatch, tmp_path):
    product = {"filename": "exposure.fits", "url": "https://example.org/a", "source_slits_filename": "actual_metadata"}
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps({"source_spectrum_sha256": "spectrum", "products": [{**product,
        "expected_bytes": 7, "sha256": hashlib.sha256(b"correct").hexdigest()}]}))
    monkeypatch.setattr(batch, "INVENTORY", path)
    monkeypatch.setattr(batch, "exposure_products", lambda _: ([product], {"sha256": "spectrum"}))
    out = tmp_path / "output"
    out.mkdir()
    source = out / "exposure.fits"
    source.write_bytes(b"altered")
    source.with_name(source.name + ".provenance.json").write_text(json.dumps({
        "bytes": 7, "sha256": hashlib.sha256(b"altered").hexdigest()}))
    monkeypatch.setattr(batch, "probe_product", lambda *a, **kw: pytest.fail("No network on cached inputs"))
    with pytest.raises(ValueError, match="pinned inventory"):
        batch.acquire_batch(tmp_path / "spectrum", out)


def test_coherent_wrong_fresh_download_rejected_before_extraction(monkeypatch, tmp_path):
    product = {"filename": "exposure.fits", "url": "https://example.org/a", "source_slits_filename": "actual_metadata"}
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"source_spectrum_sha256": "spectrum", "products": [{**product,
        "expected_bytes": 7, "sha256": hashlib.sha256(b"correct").hexdigest()}]}))
    monkeypatch.setattr(batch, "INVENTORY", inventory)
    monkeypatch.setattr(batch, "exposure_products", lambda _: ([product], {"sha256": "spectrum"}))
    monkeypatch.setattr(batch, "probe_product", lambda *a, **kw: {"status": 200, "content_length": "7"})

    def wrong_download(product, path, **kwargs):
        path.write_bytes(b"altered")
        receipt = {"bytes": 7, "sha256": hashlib.sha256(b"altered").hexdigest()}
        path.with_name(path.name + ".provenance.json").write_text(json.dumps(receipt))
        return receipt

    monkeypatch.setattr(batch, "fetch_product", wrong_download)
    monkeypatch.setattr(batch, "extract_native_slit", lambda *a, **kw: pytest.fail("Wrong input must not reach extraction"))
    with pytest.raises(ValueError, match="Retrieved native original differs from pinned inventory"):
        batch.acquire_batch(tmp_path / "spectrum", tmp_path / "output")


def test_primary_table_parser_avoids_duplicate_mathml_annotation():
    parser = TableParser()
    parser.feed('<table id="S3.T2.2.1"><tr><td><math alttext="10^{-5}"><mi>10</mi><annotation>10^{-5}</annotation></math></td></tr></table>')
    assert parser.rows == [["10^{-5}"]]


def test_numeric_benchmarks_have_full_model_denominator_and_pinned_bytes():
    import csv
    from data_pipeline.followup_data import verify

    root = Path(__file__).resolve().parents[1]
    table = root / "data_sources/followup/nandal_rotating_mixed_ism_v1.csv"
    assert verify(table)["rows"] == 24
    rows = list(csv.DictReader(table.open()))
    assert len({row["scenario"] for row in rows}) == 4
    assert all(len([r for r in rows if r["scenario"] == s]) == 6 for s in {r["scenario"] for r in rows})
    emp = next(r for r in rows if r["scenario"] == "Top-heavy above remnant" and r["metallicity_source"] == "10^{-5}")
    assert float(emp["bracket_NC_lower"]) == pytest.approx(.76)
    assert float(emp["bracket_NC_upper"]) == pytest.approx(.76)
    assert float(emp["log_NC_lower"]) == pytest.approx(.13)
    assert float(emp["mom_bracket_NC_lower"]) == pytest.approx(.73)
    popiii = next(r for r in rows if r["scenario"] == "Salpeter above remnant" and r["metallicity_source"] == "0")
    assert float(popiii["log_NC_lower"]) == pytest.approx(-.35)
    assert float(popiii["bracket_NC_lower"]) == pytest.approx(.28)
    assert float(popiii["mom_bracket_NC_lower"]) == pytest.approx(.25)
    assert float(popiii["mom_bracket_NC_upper"]) < .27
