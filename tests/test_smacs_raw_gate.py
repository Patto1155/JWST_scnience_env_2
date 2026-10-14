"""A failed dependency gate cannot be relabeled a null or promoted discovery."""

from pathlib import Path

import pytest

from discovery.smacs_raw_gate import evaluate, replay
from discovery.smacs_raw_preflight import DATA_CAP, FREEZE_COMMIT, RAW_NAMES


def receipts():
    downloads = {
        "freeze_commit": FREEZE_COMMIT,
        "receipts": [{"product_id": n, "bytes": 75_556_800} for n in RAW_NAMES],
    }
    headers = {"products": [{"header": {"FILENAME": n, "FILTER": "F444W"}} for n in RAW_NAMES]}
    selector = {"context": "jwst_1596.pmap", "references": {"dark": "dark.fits"}}
    heads = {"products": [{"filename": "dark.fits", "status": 200, "content_length": "4378878720"}]}
    return downloads, headers, selector, heads


def test_required_oversized_dark_is_blocked_not_null():
    result = evaluate(*receipts())
    assert result["status"].startswith("blocked")
    assert result["control_artifacts"] == {
        "null": None,
        "injection_recovery": None,
        "independent_repeat": None,
    }
    assert "not measured" in result["scientific_verdict"]


def test_no_block_when_minimum_calibration_is_within_cap():
    inputs = receipts()
    inputs[3]["products"][0]["content_length"] = str(DATA_CAP - 151_113_600)
    with pytest.raises(ValueError, match="does not establish"):
        evaluate(*inputs)


def test_wrong_frozen_raw_product_is_rejected():
    inputs = receipts()
    inputs[0]["receipts"][0]["product_id"] = "other.fits"
    with pytest.raises(ValueError, match="frozen pair"):
        evaluate(*inputs)


def test_actual_compact_gate_replays_as_blocked():
    result = replay(Path(__file__).parents[1] / "research_output/session_20261014")
    assert result["dark_reference_bytes"] == 4_378_878_720
    assert result["verified_raw_body_bytes"] == 151_113_600
    assert result["dark_plus_raw_minimum_bytes"] > DATA_CAP
