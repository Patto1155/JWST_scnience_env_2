from discovery.research7_yso_poles import gate, inventory


def test_unknown_source_wavelength_does_not_pass():
    result = gate([{"eligible_visits": None, "eligible_matched_controls": 100}] * 5)
    assert not result["passes"]
    assert result["unknown_coverage_targets"] == 5


def test_gate_requires_targets_visits_and_controls():
    qualifying = {"eligible_visits": 8, "eligible_matched_controls": 5}
    assert gate([qualifying] * 5)["passes"]
    assert not gate([qualifying] * 4)["passes"]
    assert not gate([{"eligible_visits": 7, "eligible_matched_controls": 5}] * 5)["passes"]
    assert not gate([{"eligible_visits": 8, "eligible_matched_controls": 4}] * 5)["passes"]


def test_release_deduplication_is_not_visit_eligibility():
    row = {
        "obs_id": "one",
        "energy_bandpassname": "D4",
        "t_min": "60000.1",
        "obs_collection": "qr2",
        "em_min": "2.8e-6",
        "em_max": "3.9e-6",
    }
    result = inventory([row, dict(row, obs_collection="qr3")])
    assert result["physical_exposures"] == 1
    assert result["utc_day_bins"] == 1
    assert result["source_eligible_visit_count"] is None


def test_frame_count_and_K_are_necessary_not_sufficient():
    from discovery.research7_yso_poles import necessary_metadata_gate

    def target(name, k, frames):
        return {"identity": {"main_id": name, "K": k}, "inventory": {"exposures": frames}}

    enough = [{"mjd": float(day) + 0.1} for day in range(8) for _ in range(8)]
    sparse = [{"mjd": float(day) + 0.1} for day in range(20) for _ in range(7)]
    targets = [target(str(i), "12", enough) for i in range(4)]
    targets += [target("missing K", "", enough), target("sparse", "12", sparse)]
    result = necessary_metadata_gate(targets)
    assert result["upper_bound_qualifying_targets"] == 5
    assert result["currently_K_assignable_possible_targets"] == 4
    assert not result["fails_necessary_gate"]
    assert targets[-1]["necessary_condition_metadata"]["upper_bound_source_qualified_visits"] == 0


def test_packaged_actual_inventory_replays_byte_exactly(tmp_path):
    import gzip
    import hashlib
    import json
    from pathlib import Path

    from discovery.research7_yso_poles import load_json, necessary_metadata_gate

    archive = (
        Path(__file__).resolve().parents[1]
        / "research_output/calibrated_20261014/e_poles_final/e_summary.json.gz"
    )
    receipt = json.loads(archive.with_name("e_summary_packaging_receipt.json").read_text())
    compressed = archive.read_bytes()
    plain_bytes = gzip.decompress(compressed)
    assert hashlib.sha256(plain_bytes).hexdigest() == receipt["uncompressed_sha256"]
    assert hashlib.sha256(compressed).hexdigest() == receipt["compressed_sha256"]
    plain = tmp_path / "replay.json"
    plain.write_bytes(plain_bytes)
    from_plain, from_gzip = load_json(plain), load_json(archive)
    assert from_plain == from_gzip
    assert len(from_gzip["targets"]) == 13
    assert necessary_metadata_gate(from_plain["targets"]) == necessary_metadata_gate(
        from_gzip["targets"]
    )
    assert from_gzip["science_product_bytes"] == 0
