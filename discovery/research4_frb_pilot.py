"""Frozen CHIME catalog feasibility screen; no physical discovery inference."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REFERENCE_MHZ = 400.1953125
SAMPLE_SECONDS = 0.000983


def number(row: dict[str, str], key: str) -> float:
    """Missing or unparsable catalog entries never qualify numerically."""
    try:
        return float(row[key])
    except (ValueError, TypeError, KeyError):
        return math.nan


def quality(row: dict[str, str]) -> str | None:
    """Return first frozen rejection reason; None means selected."""
    if row.get("repeater_name", "").strip() in ("", "-9999", "None", "nan"):
        return "not_repeater"
    for flag in ("excluded_flag", "sidelobe_flag", "intrachan_flag", "catalog1_param_flag"):
        if number(row, flag) != 0:
            return flag
    if not number(row, "snr_fitb") >= 20:
        return "snr"
    fields = (
        "dm_fitb",
        "dm_fitb_err",
        "scat_time",
        "scat_time_err",
        "peak_freq",
        "low_freq",
        "high_freq",
        "mjd_inf",
    )
    if not all(math.isfinite(number(row, k)) for k in fields):
        return "missing_numeric"
    tau = number(row, "scat_time")
    tauerr = number(row, "scat_time_err")
    if not (number(row, "dm_fitb_err") > 0 and tau > 0 and tauerr > 0):
        return "not_positive_scattering_or_error"
    if tau / tauerr < 5:
        return "scattering_snr"
    if number(row, "high_freq") - number(row, "low_freq") < 200:
        return "bandwidth"
    peak = number(row, "peak_freq")
    if peak <= 0:
        return "invalid_peak_frequency"
    if tau * (peak / REFERENCE_MHZ) ** -4 < 2 * SAMPLE_SECONDS:
        return "unresolved_at_peak"
    return None


def covariance(rows: list[dict[str, str]]) -> dict[str, float | None]:
    """Conditional sample association and first-order random-error bound."""
    n = len(rows)
    xs = [number(r, "dm_fitb") for r in rows]
    ys = [math.log(number(r, "scat_time")) for r in rows]
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / (n - 1)
    vx = sum((x - mx) ** 2 for x in xs) / (n - 1)
    vy = sum((y - my) ** 2 for y in ys) / (n - 1)
    bound = (
        sum(
            number(r, "dm_fitb_err") * number(r, "scat_time_err") / number(r, "scat_time")
            for r in rows
        )
        / n
    )
    return {
        "sample_covariance": cov,
        "pearson_r": cov / math.sqrt(vx * vy) if vx * vy > 0 else None,
        "delta_method_random_error_covariance_bound": bound,
        "fivefold_error_sensitivity_bound": 25 * bound,
    }


def screen(rows: list[dict[str, str]]) -> dict[str, Any]:
    events: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        events[r["event_id"]].append(r)
    shared_inconsistencies = []
    for event, rr in events.items():
        for field in ("repeater_name", "dm_fitb", "dm_fitb_err", "scat_time", "scat_time_err"):
            if len({r.get(field) for r in rr}) != 1:
                shared_inconsistencies.append({"event_id": event, "field": field})
    if shared_inconsistencies:
        return {"status": "schema_stop", "shared_parameter_inconsistencies": shared_inconsistencies}
    rejection: Counter[str] = Counter()
    selected: dict[str, list[dict[str, str]]] = defaultdict(list)
    for rr in events.values():
        if len(rr) != 1:
            rejection["multiple_subbursts"] += 1
            continue
        row = min(rr, key=lambda r: number(r, "sub_num"))
        reason = quality(row)
        if reason:
            rejection[reason] += 1
        else:
            selected[row["repeater_name"]].append(row)
    sources = {k: v for k, v in selected.items() if len(v) >= 6}
    counts = {k: len(v) for k, v in sorted(selected.items())}
    result: dict[str, Any] = {
        "catalog_rows": len(rows),
        "unique_events": len(events),
        "unique_repeater_source_labels": len(
            {
                r["repeater_name"]
                for r in rows
                if r.get("repeater_name", "").strip() not in ("", "-9999", "None", "nan")
            }
        ),
        "rejection_counts_in_frozen_order": dict(rejection),
        "selected_events": sum(counts.values()),
        "selected_counts_by_source": counts,
        "selected_event_ids": sorted(r["event_id"] for rr in selected.values() for r in rr),
        "sources_with_six_events": len(sources),
        "required_sources": 6,
        "status": "coverage_stop" if len(sources) < 6 else "exploratory_association_only",
        "physical_discovery": False,
    }
    if len(sources) < 6:
        result["outcome_associations_computed"] = False
        return result
    per_source = {}
    for source, rr in sorted(sources.items()):
        rr = sorted(rr, key=lambda r: (number(r, "mjd_inf"), r["event_id"]))
        split = len(rr) // 2
        per_source[source] = {
            "n": len(rr),
            "full": covariance(rr),
            "early": covariance(rr[:split]),
            "late": covariance(rr[split:]),
            "early_event_ids": [r["event_id"] for r in rr[:split]],
            "late_event_ids": [r["event_id"] for r in rr[split:]],
        }
    values = [v["full"]["sample_covariance"] for v in per_source.values()]
    result["outcome_associations_computed"] = True
    result["per_source"] = per_source
    result["equal_source_mean_covariance"] = sum(values) / len(values)
    result["leave_one_source_out_means"] = [(sum(values) - x) / (len(values) - 1) for x in values]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    stored_body = args.catalog.read_bytes()
    body = gzip.decompress(stored_body) if args.catalog.suffix == ".gz" else stored_body
    rows = list(csv.DictReader(body.decode().splitlines()))
    result = screen(rows)
    result["catalog_sha256"] = hashlib.sha256(body).hexdigest()
    result["stored_catalog_sha256"] = hashlib.sha256(stored_body).hexdigest()
    freeze_body = Path("docs/RESEARCH4_FRB_FREEZE.md").read_bytes()
    result["freeze_sha256"] = hashlib.sha256(freeze_body).hexdigest()
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
