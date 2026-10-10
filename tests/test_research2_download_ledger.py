import copy
import hashlib
import json
from pathlib import Path

import pytest

from discovery.research2_download_ledger import aggregate

MANIFEST = Path(__file__).parents[1] / "data_sources/research2_download_ledger/manifest.json"


def test_actual_ledger_counts_retries_and_bounds_separately():
    report = aggregate(json.loads(MANIFEST.read_text()))
    assert report["conservative_new_transfer_charge_bytes"] == 1326134993
    assert report["remaining_cap_bytes"] == 821348655
    assert report["restored_unique_pinned_product_bytes_separate"] == 2072989504
    assert not report["new_transfer_charge_is_exact_measurement"]
    rows = {row["role"]: row for row in report["new_transfers"]}
    assert (
        rows["FLAME"]["transfer_charge_bytes"] - rows["FLAME"]["distinct_selected_payload_bytes"]
        == 73013302
    )
    assert (
        rows["selection_count"]["transfer_charge_bytes"]
        - rows["selection_count"]["distinct_selected_payload_bytes"]
        == 7703
    )
    assert rows["decoder_software"]["distinct_selected_payload_bytes"] is None


def test_duplicate_owner_cannot_charge_shared_restoration_twice():
    manifest = json.loads(MANIFEST.read_text())
    manifest["new_transfers"].append(copy.deepcopy(manifest["new_transfers"][0]))
    with pytest.raises(ValueError, match="Repeated acquisition"):
        aggregate(manifest)


def test_excess_cap_and_wrong_convention_fail_closed():
    manifest = json.loads(MANIFEST.read_text())
    manifest["initial_new_transfer_cap_bytes"] = 1
    with pytest.raises(ValueError, match="exceeds cap"):
        aggregate(manifest)
    manifest["new_transfers"][0]["transfer_kind"] = "installed_file_size"
    with pytest.raises(ValueError, match="convention"):
        aggregate(manifest)


def test_receipt_identity_is_not_satisfied_by_equal_size(tmp_path):
    manifest = {
        "new_transfers": [
            {
                "role": "pilot",
                "transfer_charge_bytes": 3,
                "transfer_kind": "exact",
                "distinct_selected_payload_bytes": 3,
                "source": "receipt",
                "source_bytes": 3,
                "source_sha256": hashlib.sha256(b"abc").hexdigest(),
            }
        ],
        "pinned_restorations": [],
        "initial_new_transfer_cap_bytes": 3,
        "scope": "test",
    }
    (tmp_path / "receipt").write_bytes(b"abc")
    assert aggregate(manifest, tmp_path)["remaining_cap_bytes"] == 0
    (tmp_path / "receipt").write_bytes(b"abd")
    with pytest.raises(ValueError, match="Source receipt changed"):
        aggregate(manifest, tmp_path)


def test_final_ledger_keeps_original_interim_and_adds_only_followup_transfers():
    original = aggregate(json.loads(MANIFEST.read_text()))
    revised = aggregate(json.loads(MANIFEST.with_name("manifest_v2.json").read_text()))
    assert revised["schema_version"] == 2
    assert revised["conservative_new_transfer_charge_bytes"] == 1327307019
    assert revised["remaining_cap_bytes"] == 820176629
    assert revised["restored_unique_pinned_product_bytes_separate"] == 2073005957
    assert (
        revised["conservative_new_transfer_charge_bytes"]
        - original["conservative_new_transfer_charge_bytes"]
    ) == 1172026
    assert (
        revised["restored_unique_pinned_product_bytes_separate"]
        - original["restored_unique_pinned_product_bytes_separate"]
    ) == 16453


def test_bounded_archive_followups_charge_bodies_once_and_preserve_restoration():
    previous = aggregate(json.loads(MANIFEST.with_name("manifest_v2.json").read_text()))
    final = aggregate(json.loads(MANIFEST.with_name("manifest_v3.json").read_text()))
    assert final["schema_version"] == 3
    assert final["conservative_new_transfer_charge_bytes"] == 1334355625
    assert final["remaining_cap_bytes"] == 813128023
    assert final["restored_unique_pinned_product_bytes_separate"] == 2073005957
    assert (
        final["conservative_new_transfer_charge_bytes"]
        - previous["conservative_new_transfer_charge_bytes"]
    ) == 4475520 + 1219486 + 1353600
    assert (
        final["restored_unique_pinned_product_bytes_separate"]
        == previous["restored_unique_pinned_product_bytes_separate"]
    )
