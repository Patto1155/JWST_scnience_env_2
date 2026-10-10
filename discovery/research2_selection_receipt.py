"""Independent raw-trial counts, uncertainty and baseline receipt validation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(coordinator: Path, selection: Path, trial_path: Path) -> dict:
    release_path = coordinator / "research_output/continuation_final_validation.json"
    baseline_path = coordinator / "research_output/research2_baseline.json"
    original = json.loads(release_path.read_text())
    baseline = json.loads(baseline_path.read_text())
    xml = coordinator / "research_output/research2_baseline_tests.xml"
    log = coordinator / "research_output/research2_baseline_quality.log"
    counts = ET.parse(xml).getroot().find("testsuite").attrib
    if counts["tests"] != "582" or counts["failures"] != "0" or counts["skipped"] != "3":
        raise ValueError("Original release counts differ")
    if (
        sha(xml) != baseline["baseline_quality_gate"]["junit_sha256"]
        or sha(log) != baseline["baseline_quality_gate"]["quality_log_sha256"]
    ):
        raise ValueError("Baseline execution receipts differ")
    checks = []
    for name in ("science_artifact_hash_index", "tested_python_and_configuration_sha256"):
        for filename, pin in original[name].items():
            expected = pin if isinstance(pin, str) else pin["sha256"]
            if sha(coordinator / filename) != expected:
                raise ValueError("Original scientific artifact/code hash changed")
        checks.append({"index": name, "verified": len(original[name])})
    if sha(coordinator / "requirements-research.lock") != baseline["lock_sha256"]:
        raise ValueError("Dependency lock differs")
    for package in baseline["locked_distributions"]:
        if importlib.metadata.version(package["name"]) != package["expected"]:
            raise ValueError("Installed baseline dependency differs")

    response_path = selection / "research_output/selection_pilot_response.json"
    plan_path = selection / "research_output/selection_pilot_plan.json"
    response = json.loads(response_path.read_text())
    plan = json.loads(plan_path.read_text())
    trials = json.loads(trial_path.read_text())
    canonical_hash = hashlib.sha256(
        json.dumps(trials, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    if canonical_hash != response["full_trial_content_sha256"] or len(trials) != 1152:
        raise ValueError("Full-trial content/count differs")
    errors = []
    for group in response["groups"]:
        rows = [
            t
            for t in trials
            if all(
                t[k] == group[k]
                for k in (
                    "split",
                    "morphology",
                    "flux_njy",
                    "truth_color",
                    "assumed_electrons_per_njy",
                )
            )
        ]
        sites = sorted({t["site_id"] for t in rows})
        if len(rows) != group["realizations"] or len(sites) != group["sites"]:
            raise ValueError("Group denominators differ")
        for metric in ("centroid_recovery", "red_selection"):

            def value(t: dict) -> bool:
                return (
                    t["centroid_status"] == "matched"
                    if metric == "centroid_recovery"
                    else t["selected_red"]
                )

            values = np.array(
                [np.mean([value(t) for t in rows if t["site_id"] == site]) for site in sites]
            )
            rng = np.random.default_rng(271828)
            interval = np.quantile(
                values[rng.integers(0, len(sites), (1000, len(sites)))].mean(1), [0.025, 0.975]
            )
            if not np.allclose(
                interval, group["metrics"][metric]["conditional_site_bootstrap_interval"]
            ) or not np.isclose(values.mean(), group["metrics"][metric]["fraction"]):
                raise ValueError("Independent site bootstrap differs")
        for t in rows:
            null = next(n for n in response["null_site_controls"] if n["site_id"] == t["site_id"])
            for band in ("F090W", "F200W", "F444W"):
                errors.append(
                    abs(
                        t["aperture_flux_njy"][band]
                        - null["flux_njy"][band]
                        - t["paired_source_response_njy"][band]
                    )
                )
    null_passes = sum(
        n["red_bin"] == "red" and n["centroid_status"] == "matched"
        for n in response["null_site_controls"]
    )
    if any(
        n["selected_red"] != (n["red_bin"] == "red" and n["centroid_status"] == "matched")
        for n in response["null_site_controls"]
    ):
        raise ValueError("Null joint selection differs")
    transport = np.array([[0.5], [0.5]])
    covariance = transport @ np.array([[20.0]]) @ transport.T
    toy = response["uncalibrated_drizzle_counterexample"]
    if not np.allclose(covariance, toy["transported_covariance"]):
        raise ValueError("Photon-transport covariance counterexample differs")
    return {
        "schema_version": 1,
        "baseline_review": {
            "receipt_sha256": sha(baseline_path),
            "hash_indexes": checks,
            "installed_versions_verified": 65,
            "tests": 582,
            "passed": 579,
            "explicit_skips": 3,
            "junit_sha256": sha(xml),
            "log_sha256": sha(log),
            "approval": "Preserved baseline and explicit artifact-versus-pixel scope",
        },
        "selection_review": {
            "frozen_design_commit": "ca5e16e",
            "scientific_response_commit": "7e941db",
            "plan_sha256": sha(plan_path),
            "response_sha256": sha(response_path),
            "raw_trial_file_sha256": sha(trial_path),
            "canonical_trials_sha256": canonical_hash,
            "sites": len(plan["sites"]),
            "trials": len(trials),
            "independently_recomputed_groups": len(response["groups"]),
            "all_bootstrap_intervals_reproduced": True,
            "maximum_paired_arithmetic_error_njy": max(errors),
            "joint_null_red_passes": null_passes,
            "photon_transport_counterexample_covariance": covariance.tolist(),
            "approval": "Conditional bounded response pilot only",
            "required_limitations": [
                "Finite modeled PSFs and uncalibrated output-grid electrons/nJy",
                (
                    "Spatial diagnostic strata share global threshold, "
                    "no independent calibration validation"
                ),
                (
                    "Repeated count realizations share background; "
                    "intervals have no calibrated coverage"
                ),
                (
                    "No true astronomical labels, survey completeness, "
                    "contamination or cosmology likelihood"
                ),
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coordinator", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--trials", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(audit(args.coordinator, args.selection, args.trials), indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
