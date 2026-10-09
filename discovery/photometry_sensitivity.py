"""Re-audit every saved proposal under explicit noise and point-PSF scenarios.

This is conditional sensitivity analysis, not a posterior on source identities.
The selection is F090W/F444W with measured F200W coverage; it has no F200W
colour/redshift criterion and cannot establish an early-galaxy population.
"""

from __future__ import annotations

import argparse
import copy
import csv
import itertools
import json
import math
from pathlib import Path
from typing import Any

from discovery.audit_candidates import audit_candidate, summarize
from discovery.image_photometry_rerun import (
    REQUIRED_FILTERS,
    load_selection_measurements,
    sha256_file,
)


def _matching_geometry(radius: float, annulus: list[float], metadata: dict[str, Any]) -> None:
    wanted = metadata["aperture_radius_arcsec_by_filter"]
    if any(not math.isclose(radius, wanted[band], rel_tol=1e-10) for band in REQUIRED_FILTERS):
        raise ValueError("Correction aperture does not match the saved measurement operator")
    desired_annulus = [metadata["annulus_radii_arcsec"][key] for key in ("inner", "outer")]
    if len(annulus) != 2 or any(
        not math.isclose(a, b, rel_tol=1e-10) for a, b in zip(annulus, desired_annulus, strict=True)
    ):
        raise ValueError("Correction annulus does not match the saved measurement operator")


def noise_inputs(
    report: dict[str, Any],
    metadata: dict[str, Any],
    receipts: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Require matching image bytes and actual aperture/annulus before transferring factors."""
    hashes = {row["sha256"]: row["filter"] for row in receipts if row["filter"] in REQUIRED_FILTERS}
    inputs = {}
    radius = metadata["aperture_radius_arcsec_by_filter"]["F444W"]
    for image in report["real_images"]:
        band = hashes.get(image["sha256"])
        if band is None:
            raise ValueError("Noise image hash does not match the saved science inputs")
        if image.get("angular_geometry") != "celestial_separation":
            raise ValueError("Noise operator must use actual celestial apertures")
        aperture = next(
            (
                row
                for row in image["apertures"]
                if math.isclose(row["radius_arcsec"], radius, rel_tol=1e-10)
            ),
            None,
        )
        if aperture is None or aperture["status"] != "measured":
            raise ValueError("No measured noise result at the saved aperture")
        _matching_geometry(radius, image["fixed_annulus_radii_arcsec"], metadata)
        median = float(aperture["noise_multiplier"])
        lower, upper = aperture["noise_multiplier_block_bootstrap_95"]
        if not all(
            math.isfinite(float(value)) and float(value) > 0 for value in (median, lower, upper)
        ):
            raise ValueError("Noise factors must be finite and positive")
        inputs[band] = {
            "median": median,
            "lower": lower,
            "upper": upper,
            "image_sha256": image["sha256"],
            "n_apertures": aperture["n_apertures"],
            "mask_method": image["mask_method"],
            "limits": image["limits"],
        }
    if set(inputs) != set(REQUIRED_FILTERS):
        raise ValueError("Noise report lacks a required filter")
    return inputs


def rescale_measurements(
    proposals: list[dict[str, Any]],
    noise: dict[str, float],
    point_multipliers: dict[tuple[int, str], float] | None = None,
) -> list[dict[str, Any]]:
    """Keep unavailable fluxes unavailable; rescale flux/error together for a PSF model."""
    changed = copy.deepcopy(proposals)
    for proposal in changed:
        fully_testable = audit_candidate(proposal)["audit_verdict"] != "untestable"
        for band in REQUIRED_FILTERS:
            item = proposal["photometry_by_filter"][band]["3"]
            factor = float(noise[band])
            if not math.isfinite(factor) or factor <= 0:
                raise ValueError("Noise factors must be finite and positive")
            point = 1.0
            if point_multipliers is not None:
                key = (proposal["source_id"], band)
                if fully_testable and key not in point_multipliers:
                    raise ValueError("Testable source lacks a native point-response model")
                point = point_multipliers.get(key, 1.0)
                if not math.isfinite(point) or point <= 0:
                    raise ValueError("Point-response multiplier must be finite and positive")
            if item["background_subtracted_flux_jy"] is not None:
                item["background_subtracted_flux_jy"] *= point
            if item["flux_error_jy"] is not None:
                item["flux_error_jy"] *= factor * point
    return changed


def load_point_response(
    report_path: Path,
    phase_csv: Path,
    catalog_sha: str,
    metadata: dict[str, Any],
    receipts: list[dict[str, Any]],
) -> dict[tuple[int, str], float]:
    """Verify native-model source catalog, phase artifact and image identities."""
    report = json.loads(report_path.read_text())
    if report["catalog_sha256"] != catalog_sha:
        raise ValueError("Native PSF source-catalog hash mismatch")
    if report["source_phase_csv"]["sha256"] != sha256_file(phase_csv):
        raise ValueError("Native PSF phase-CSV hash mismatch")
    _matching_geometry(report["radius_arcsec"], report["annulus_radii_arcsec"], metadata)
    images = {row["filter"]: row["sha256"] for row in receipts if row["filter"] in REQUIRED_FILTERS}
    for row in report["filters"]:
        if row["image_sha256"] != images.get(row["filter"]):
            raise ValueError("Native PSF image hash mismatch")
    if not report.get("model_not_observed"):
        raise ValueError("This scenario requires an explicitly declared modeled PSF")
    multipliers = {}
    with phase_csv.open(newline="") as handle:
        for row in csv.DictReader(handle):
            key = (int(row["source_id"]), row["band"])
            if key in multipliers:
                raise ValueError("Duplicate native PSF source/filter response")
            multipliers[key] = float(row["total_pointsource_multiplier"])
    return multipliers


def run_sensitivity(
    catalog_dir: Path,
    noise_path: Path,
    output: Path,
    *,
    psf_path: Path | None = None,
    phase_csv: Path | None = None,
) -> dict[str, Any]:
    """Retain all proposal denominators and save changed verdicts explicitly."""
    csv_path, metadata_path = (
        catalog_dir / "selection_measurements.csv",
        catalog_dir / "selection_metadata.json",
    )
    receipts = json.loads((catalog_dir / "rerun_summary.json").read_text())["image_receipts"]
    metadata = json.loads(metadata_path.read_text())
    replay = json.loads((catalog_dir / "compact_replay_verification.json").read_text())
    if (
        sha256_file(csv_path) != replay["selection_csv_sha256"]
        or sha256_file(metadata_path) != replay["selection_metadata_sha256"]
    ):
        raise ValueError("Compact measurements or operator metadata hash mismatch")
    proposals = load_selection_measurements(csv_path, metadata_path)
    baseline = [audit_candidate(row) for row in proposals]
    if summarize(baseline) != replay["audit_summary"]:
        raise ValueError("Baseline replay does not reproduce the frozen original audit")
    noise_report = json.loads(noise_path.read_text())
    inputs = noise_inputs(noise_report, metadata, receipts)
    scenarios = {
        "diagonal_baseline": {band: 1.0 for band in REQUIRED_FILTERS},
        "empirical_noise_median": {band: inputs[band]["median"] for band in REQUIRED_FILTERS},
    }
    for endpoints in itertools.product(("lower", "upper"), repeat=3):
        scenarios["noise_endpoints_" + "_".join(endpoints)] = {
            band: inputs[band][endpoint]
            for band, endpoint in zip(REQUIRED_FILTERS, endpoints, strict=True)
        }
    point = None
    if (psf_path is None) != (phase_csv is None):
        raise ValueError("Supply both native PSF report and phase CSV")
    if psf_path is not None:
        point = load_point_response(psf_path, phase_csv, sha256_file(csv_path), metadata, receipts)
    outputs = []
    initial_survivors = {row["source_id"] for row in baseline if row["audit_verdict"] == "survives"}
    initial_details = {source_id: {} for source_id in initial_survivors}
    for name, factors in scenarios.items():
        modes = [(name, None)]
        if point is not None:
            modes.append((name + "_unresolved_point_model", point))
        for scenario_name, point_factors in modes:
            audits = [
                audit_candidate(row)
                for row in rescale_measurements(proposals, factors, point_factors)
            ]
            summary = summarize(audits)
            changes = [
                {
                    "source_id": after["source_id"],
                    "before": before["audit_verdict"],
                    "after": after["audit_verdict"],
                    "after_reasons": after["audit_blockers"],
                }
                for before, after in zip(baseline, audits, strict=True)
                if before["audit_verdict"] != after["audit_verdict"]
            ]
            outputs.append(
                {
                    "name": scenario_name,
                    "error_multipliers": factors,
                    "point_source_assumption": point_factors is not None,
                    "summary": summary,
                    "changed_verdicts": changes,
                }
            )
            for audit in audits:
                if audit["source_id"] in initial_details:
                    initial_details[audit["source_id"]][scenario_name] = {
                        key: audit[key]
                        for key in (
                            "audit_verdict",
                            "reference_snr",
                            "blue_snr",
                            "physical_blue_over_red_ratio",
                            "audit_blockers",
                        )
                    }
    result = {
        "experiment": "conditional noise and unresolved-PSF selection sensitivity",
        "selection_description": (
            "F090W/F444W screen plus F200W coverage; no F200W colour/redshift cut"
        ),
        "posterior_or_discovery": False,
        "total_saved_proposals": len(proposals),
        "catalog_sha256": sha256_file(csv_path),
        "operator_metadata_sha256": sha256_file(metadata_path),
        "noise_report_sha256": sha256_file(noise_path),
        "noise_inputs": inputs,
        "psf_report_sha256": sha256_file(psf_path) if psf_path is not None else None,
        "native_phase_csv_sha256": sha256_file(phase_csv) if phase_csv is not None else None,
        "scenarios": outputs,
        "initial_seven_scenario_details": initial_details,
        "limitations": [
            "Noise factors describe selected empty sky; source noise and drizzle are not isolated.",
            "Scaling total errors is sensitivity analysis, not a validated Poisson replacement.",
            "Bootstrap endpoint combinations are sensitivity cases, not joint credible bounds.",
            "Native PSFs assume unresolved sources; extended galaxies require another model.",
            "No redshift, contamination prevalence, galaxy abundance or identity is inferred.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog_dir", type=Path)
    parser.add_argument("noise_report", type=Path)
    parser.add_argument("--psf-report", type=Path)
    parser.add_argument("--phase-csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_sensitivity(
        args.catalog_dir,
        args.noise_report,
        args.output,
        psf_path=args.psf_report,
        phase_csv=args.phase_csv,
    )
    print(json.dumps({row["name"]: row["summary"]["survivors"] for row in result["scenarios"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
