"""Aggregate pinned-input restoration and conservative new-transfer accounting."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def aggregate(manifest, source_root=None):
    roles = set()
    exact = 0
    allowances = 0
    selected_known = 0
    for row in manifest["new_transfers"]:
        role = row["role"]
        if role in roles:
            raise ValueError("Repeated acquisition owner: " + role)
        roles.add(role)
        charge = row["transfer_charge_bytes"]
        if not isinstance(charge, int) or charge < 0:
            raise ValueError("Invalid transfer charge")
        if row["transfer_kind"] == "exact":
            exact += charge
        elif row["transfer_kind"] == "upper_bound":
            allowances += charge
        else:
            raise ValueError("Unknown transfer-accounting convention")
        unique = row["distinct_selected_payload_bytes"]
        if unique is not None:
            if not isinstance(unique, int) or not 0 <= unique <= charge:
                raise ValueError("Distinct payload exceeds charged transfer")
            selected_known += unique
    restored_roles = [row["role"] for row in manifest["pinned_restorations"]]
    if len(set(restored_roles)) != len(restored_roles) or set(restored_roles) & roles:
        raise ValueError("Repeated restoration or acquisition/restoration owner")
    restored = sum(row["unique_restored_product_bytes"] for row in manifest["pinned_restorations"])
    if source_root is not None:
        for row in manifest["new_transfers"] + manifest["pinned_restorations"]:
            raw = (source_root / row["source"]).read_bytes()
            if (
                len(raw) != row["source_bytes"]
                or hashlib.sha256(raw).hexdigest() != row["source_sha256"]
            ):
                raise ValueError("Source receipt changed: " + row["source"])
    total = exact + allowances
    cap = manifest["initial_new_transfer_cap_bytes"]
    if total > cap:
        raise ValueError("New-transfer conservative charge exceeds cap")
    return {
        "schema_version": manifest.get("schema_version", 1),
        "initial_new_transfer_cap_bytes": cap,
        "exact_transfer_body_subtotal_bytes": exact,
        "upper_bound_category_charges_bytes": allowances,
        "conservative_new_transfer_charge_bytes": total,
        "new_transfer_charge_is_exact_measurement": allowances == 0,
        "remaining_cap_bytes": cap - total,
        "known_distinct_selected_payload_bytes_excluding_unmeasured_software": selected_known,
        "restored_unique_pinned_product_bytes_separate": restored,
        "restoration_transfer_retry_accounting_complete": False,
        "new_transfers": manifest["new_transfers"],
        "pinned_restorations": manifest["pinned_restorations"],
        "scope": manifest["scope"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = aggregate(json.loads(args.manifest.read_text()), args.source_root)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
