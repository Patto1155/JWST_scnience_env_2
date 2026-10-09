"""Summarize released spectroscopic observations without calling them recoveries.

Consumes the pinned compact DR4 table. Cohort labels are reference redshift labels,
not classifier labels; tier+ID keys describe observations, not unique galaxies.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def finite_number(value: str) -> float | None:
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) else None


def summarize_rows(rows: list[dict]) -> dict:
    flags = Counter()
    by_field = defaultdict(list)
    by_tier = defaultdict(list)
    cohorts = {
        "robust_high_z_ge_6": [],
        "robust_controls_0_le_z_lt_3": [],
        "secure_c_high_z_ge_6": [],
    }
    invalid_coordinates = invalid_redshifts = 0
    for row in rows:
        flag = row["z_Spec_flag"].strip()
        flags[flag] += 1
        by_field[row["Field"]].append(row)
        by_tier[row["TIER"]].append(row)
        ra, dec = finite_number(row["RA_TARG"]), finite_number(row["Dec_TARG"])
        z = finite_number(row["z_Spec"])
        valid_sky = ra is not None and dec is not None and 0 <= ra < 360 and -90 <= dec <= 90
        if not valid_sky:
            invalid_coordinates += 1
        if z is None or z < 0:
            invalid_redshifts += 1
        if flag not in {"A", "B", "C"} or z is None or z < 0 or not valid_sky:
            continue
        reference = {
            "observation_key": [row["TIER"], row["NIRSpec_ID"]],
            "unique_id": row["Unique_ID"],
            "field": row["Field"],
            "ra_deg": ra,
            "dec_deg": dec,
            "z_spec": z,
            "quality": flag,
            "obs_date": row["ObsDate"],
        }
        if flag == "C":
            if z >= 6:
                cohorts["secure_c_high_z_ge_6"].append(reference)
            continue
        if z >= 6:
            cohorts["robust_high_z_ge_6"].append(reference)
        elif z < 3:
            cohorts["robust_controls_0_le_z_lt_3"].append(reference)

    def group_summary(group):
        robust = [
            r
            for r in group
            if r["z_Spec_flag"].strip() in {"A", "B"}
            and finite_number(r["z_Spec"]) is not None
            and float(r["z_Spec"]) >= 0
        ]
        sky = [(finite_number(r["RA_TARG"]), finite_number(r["Dec_TARG"])) for r in group]
        sky = [(ra, dec) for ra, dec in sky if ra is not None and dec is not None]
        return {
            "observation_rows": len(group),
            "tier_id_keys": len({(r["TIER"], r["NIRSpec_ID"]) for r in group}),
            "unique_id_values": len({r["Unique_ID"] for r in group}),
            "quality_flags": dict(sorted(Counter(r["z_Spec_flag"].strip() for r in group).items())),
            "robust_ab_finite_nonnegative_z_rows": len(robust),
            "robust_ab_tier_id_keys": len({(r["TIER"], r["NIRSpec_ID"]) for r in robust}),
            "ra_range_deg": [min(p[0] for p in sky), max(p[0] for p in sky)] if sky else None,
            "dec_range_deg": [min(p[1] for p in sky), max(p[1] for p in sky)] if sky else None,
        }

    return {
        "schema_version": 1,
        "summary": group_summary(rows),
        "invalid_coordinates": invalid_coordinates,
        "invalid_or_negative_spec_redshifts": invalid_redshifts,
        "by_field": {k: group_summary(v) for k, v in sorted(by_field.items())},
        "by_tier": {k: group_summary(v) for k, v in sorted(by_tier.items())},
        "cohort_counts": {k: len(v) for k, v in cohorts.items()},
        "cohorts": cohorts,
        "interpretation": [
            "Rows and tier+ID keys are not unique galaxies.",
            "No imaging recovery or classification has been measured here.",
            "A/B are highly robust; C is retained in a separate secure-break/weak-line cohort.",
            "Controls are low-z references, not demonstrated high-z interlopers.",
            "These GOODS fields cannot provide MoM-z14 COSMOS data.",
        ],
    }


def build_report(reference_csv: str | Path) -> dict:
    reference_csv = Path(reference_csv)
    data = reference_csv.read_bytes()
    receipt = json.loads(
        reference_csv.with_name(reference_csv.name + ".provenance.json").read_text()
    )
    checksum = hashlib.sha256(data).hexdigest()
    if checksum != receipt["sha256"] or len(data) != receipt["bytes"]:
        raise ValueError("reference CSV checksum/size does not match acquisition provenance")
    with reference_csv.open(newline="") as handle:
        report = summarize_rows(list(csv.DictReader(handle)))
    report["input_provenance"] = {
        "reference_sha256": checksum,
        "reference_bytes": len(data),
        "source_sha256": receipt["source_sha256"],
        "source_version": receipt["source_version"],
        "source_url": receipt["source_url"],
    }
    report["candidate_crossmatch"] = {
        "status": "not_performed",
        "reason": (
            "Original candidate FITS WCS/frame has not been independently verified; "
            "saved catalog coordinates alone are insufficient."
        ),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(build_report(args.reference_csv), indent=2, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    main()
