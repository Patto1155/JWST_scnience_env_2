"""Independent CSV oracle for the frozen CHIME Catalog 2 feasibility gate.

This operator workflow does not import the author analysis. It checks event
identity, selection attrition and temporal-split feasibility. Covariances are
reported only if the declared six-source gate passes, and are exploratory.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

REFERENCE_MHZ = 400.1953125
RESOLUTION_SECONDS = 0.000983
NOMINAL_FLAGS = ("excluded_flag", "sidelobe_flag", "intrachan_flag", "catalog1_param_flag")


def number(row: dict[str, str], key: str) -> float:
    """Reject limits/non-numeric/missing entries rather than invent detections."""
    try:
        value = float(row.get(key, ""))
    except (TypeError, ValueError):
        return math.nan
    return value if math.isfinite(value) else math.nan


def review(catalog: Path) -> dict[str, Any]:
    artifact = catalog.read_bytes()
    body = gzip.decompress(artifact) if catalog.suffix == ".gz" else artifact
    with io.StringIO(body.decode("utf-8-sig"), newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {
        "event_id",
        "sub_num",
        "repeater_name",
        "snr_fitb",
        "dm_fitb",
        "dm_fitb_err",
        "scat_time",
        "scat_time_err",
        "mjd_inf",
        "high_freq",
        "low_freq",
        "peak_freq",
        *NOMINAL_FLAGS,
    }
    fields = set(rows[0]) if rows else set()
    missing = sorted(required - fields)
    if missing:
        raise ValueError(f"Missing required fields: {missing}")
    events: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        event_id = row["event_id"].strip()
        if not event_id:
            raise ValueError("Missing event identity")
        events[event_id].append(row)
    representatives = []
    inconsistent_globals = []
    for event_id, components in events.items():
        chosen = min(components, key=lambda r: number(r, "sub_num"))
        representatives.append((chosen, len(components)))
        for field in ("dm_fitb", "scat_time", "repeater_name"):
            if len({r[field] for r in components}) != 1:
                inconsistent_globals.append({"event_id": event_id, "field": field})
    stages: list[tuple[str, Any]] = [
        (
            "identified_repeater",
            lambda r, n: r["repeater_name"].strip() not in {"", "-", "--", "None", "nan"},
        ),
        ("nominal_flags", lambda r, n: all(number(r, f) == 0 for f in NOMINAL_FLAGS)),
        ("single_component", lambda r, n: n == 1),
        ("fit_snr_20", lambda r, n: number(r, "snr_fitb") >= 20),
        (
            "finite_positive_fit_errors",
            lambda r, n: (
                all(number(r, f) > 0 for f in ("dm_fitb_err", "scat_time", "scat_time_err"))
                and math.isfinite(number(r, "dm_fitb"))
            ),
        ),
        ("scattering_snr_5", lambda r, n: number(r, "scat_time") >= 5 * number(r, "scat_time_err")),
        ("bandwidth_200_mhz", lambda r, n: number(r, "high_freq") - number(r, "low_freq") >= 200),
        (
            "resolved_scattering_at_peak",
            lambda r, n: (
                number(r, "peak_freq") > 0
                and number(r, "scat_time") * (number(r, "peak_freq") / REFERENCE_MHZ) ** -4
                >= 2 * RESOLUTION_SECONDS
            ),
        ),
        ("finite_chronology", lambda r, n: math.isfinite(number(r, "mjd_inf"))),
    ]
    selected = representatives
    attrition = [{"stage": "unique_events", "remaining": len(selected)}]
    for name, predicate in stages:
        selected = [(r, n) for r, n in selected if predicate(r, n)]
        attrition.append({"stage": name, "remaining": len(selected)})
    sources: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row, _ in selected:
        sources[row["repeater_name"].strip()].append(row)
    source_counts = []
    qualified: dict[str, list[dict[str, str]]] = {}
    for source, bursts in sorted(sources.items()):
        ordered = sorted(bursts, key=lambda r: (number(r, "mjd_inf"), r["event_id"]))
        early_count = len(ordered) // 2
        late_count = len(ordered) - early_count
        qualifies = early_count >= 3 and late_count >= 3
        source_counts.append(
            {
                "source": source,
                "events": len(ordered),
                "early": early_count,
                "late": late_count,
                "qualifies": qualifies,
            }
        )
        if qualifies:
            qualified[source] = ordered
    gate = len(qualified) >= 6
    statistics: list[dict[str, Any]] = []
    if gate:
        for source, bursts in qualified.items():
            halves = {
                "all": bursts,
                "early": bursts[: len(bursts) // 2],
                "late": bursts[len(bursts) // 2 :],
            }
            stats: dict[str, Any] = {"source": source}
            for name, subset in halves.items():
                dm = np.array([number(r, "dm_fitb") for r in subset])
                tau = np.array([number(r, "scat_time") for r in subset])
                logtau = np.log(tau)
                cross = np.sum((dm - dm.mean()) * (logtau - logtau.mean())) / (len(dm) - 1)
                bound = np.mean(
                    [
                        number(r, "dm_fitb_err")
                        * number(r, "scat_time_err")
                        / number(r, "scat_time")
                        for r in subset
                    ]
                )
                variance_product = np.var(dm, ddof=1) * np.var(logtau, ddof=1)
                stats[name] = {
                    "n": len(subset),
                    "covariance_ddof1": float(cross),
                    "conditional_noise_bound": float(bound),
                    "fivefold_error_sensitivity_bound": float(25 * bound),
                    "correlation": float(cross / np.sqrt(variance_product))
                    if variance_product > 0
                    else None,
                }
            statistics.append(stats)
    return {
        "schema_version": 1,
        "catalog_path": str(catalog.resolve()),
        "catalog_bytes": len(body),
        "catalog_sha256": hashlib.sha256(body).hexdigest(),
        "catalog_identity_scope": "Decompressed source CSV bytes",
        "input_artifact_bytes": len(artifact),
        "input_artifact_sha256": hashlib.sha256(artifact).hexdigest(),
        "scope": "Independent conditional feasibility oracle; no physical discovery inference",
        "row_count": len(rows),
        "unique_event_count": len(events),
        "component_count_histogram": dict(sorted(Counter(map(len, events.values())).items())),
        "inconsistent_shared_event_parameters": inconsistent_globals,
        "selection_attrition": attrition,
        "source_counts": source_counts,
        "selected_event_ids": sorted(row["event_id"] for row, _ in selected),
        "chronology_field": "mjd_inf",
        "scattering_reference_mhz": REFERENCE_MHZ,
        "scattering_frequency_exponent": -4,
        "qualified_source_count": len(qualified),
        "gate_requires_sources": 6,
        "gate_requires_each_temporal_half_events": 3,
        "feasibility_gate_passed": gate,
        "covariances_computed": gate,
        "source_statistics": statistics,
        "equal_source_mean_covariance": float(
            np.mean([s["all"]["covariance_ddof1"] for s in statistics])
        )
        if gate
        else None,
        "limitations": [
            "Detection-conditioned sample: missing errors/nondetections are not zero scattering "
            "or a population denominator.",
            "Joint DM/scattering fits share data; scalar errors omit cross covariance.",
            "Noise bound assumes independent unbiased errors and a first-order log transform. "
            "It does not bound model/morphology or time-correlated systematic bias.",
            "Fivefold error inflation is a sensitivity, not a calibrated systematic upper bound.",
            "Chronological halves are internal checks, not independently calibrated observations.",
        ],
        "GOODS_N_outcomes_opened": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--author-results", type=Path)
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    result = review(args.catalog)
    result["implementation_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if args.freeze:
        result["freeze_sha256"] = hashlib.sha256(args.freeze.read_bytes()).hexdigest()
    if args.author_results:
        author = json.loads(args.author_results.read_text())
        counts = {row["source"]: row["events"] for row in result["source_counts"]}
        checks = {
            "catalog_sha256": result["catalog_sha256"] == author["catalog_sha256"],
            "catalog_rows": result["row_count"] == author["catalog_rows"],
            "unique_events": result["unique_event_count"] == author["unique_events"],
            "selected_counts_by_source": counts == author["selected_counts_by_source"],
            "selected_events": len(result["selected_event_ids"]) == author["selected_events"],
            "qualified_sources": result["qualified_source_count"]
            == author["sources_with_six_events"],
            "associations_computed": result["covariances_computed"]
            == author["outcome_associations_computed"],
        }
        if "selected_event_ids" in author:
            checks["selected_event_ids"] = result["selected_event_ids"] == sorted(
                map(str, author["selected_event_ids"])
            )
        result["author_comparison"] = checks
        result["author_results_sha256"] = hashlib.sha256(
            args.author_results.read_bytes()
        ).hexdigest()
        if not all(checks.values()):
            raise ValueError(f"Author comparison mismatch: {checks}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "qualified_sources": result["qualified_source_count"],
                "gate_passed": result["feasibility_gate_passed"],
            }
        )
    )


if __name__ == "__main__":
    main()
