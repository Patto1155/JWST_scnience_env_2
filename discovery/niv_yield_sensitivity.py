"""Paired conditional yield profiles for immutable N IV line-contract versions.

Version1 physical templates define NIV as 1486-only; version2 fits define its
total1483+1486 flux. Each cell's own five-line fit and covariance are projected
with its own atomic response. Only generic two-dimensional Gaussian cone math
is shared with earlier enrichment work; no v1 spectral/grid validator sees v2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from discovery.atomic_enrichment import (
    SIGMA_95,
    check_ionic_measurement,
    positive,
    profile_ionic_ratio_interval,
    replay_ionic_operator,
)
from discovery.enrichment_constraints import DEFAULT_INPUT, ROOT, number_ratio
from tools.jwst.line_sensitivity import LINE_NAMES

PINS = {
    "v1_report": "9248284f52552e88fa002351d9b39aec419cc27e76c631ab6cffae2c5e09e929",
    "v1_grid": "b3923cd0084950e4b73a89a20848785188fc484287140c9f4d2720af43a5dc8d",
    "v2_report": "446c1f7a35ed8c8e272ba277576088f7a4dbbd6d75dcceb2dd6c1767b2891b63",
    "v2_grid": "a48ea0076ae9f6ef4d76845644880776c266efce0a281b0866d12889e36b1e0e",
    "v2_components": "692ce2fe0ca5463708abfa3c232378f3aebe22ff9b96f97d779091d54ac5f474",
}
NATIVE_SHA256 = "88e3cdbf5b7759eaad84dc21ead0974c38f392292d71ce605fa0f5b5951637ec"
V1_COMPONENTS_SHA256 = "cbd151a8274979f9378b0ce485f23793ca77ccc9eb1df8eae391012691d3fb8e"
FAMILY_NAMES = (
    "nominal_shared_formal",
    "point_shared_formal",
    "nominal_empirical_offtrace_transport",
    "point_empirical_offtrace_transport",
)
K_VALUES = (0.3, 1.0, 3.0)
REFERENCE_CELL = (20000, 1000)
UNIDENTIFIED = (
    "HeII_OIII_mixing_calibrated",
    "CIV_transfer_calibrated",
    "source_specific_LSF_calibrated",
    "ion_fraction_correction_available",
    "elemental_abundance_identified",
    "grid_axes_identified",
    "scenarios_are_independent_likelihoods",
)


def cell_key(record: dict[str, Any]) -> tuple[int, int]:
    return record["temperature_K"], record["electron_density_cm3"]


def indexed_cells(records: list[dict[str, Any]]) -> dict[tuple[int, int], dict[str, Any]]:
    indexed = {cell_key(record): record for record in records}
    if len(indexed) != len(records) or len(indexed) != 28:
        raise ValueError("the frozen experiment needs 28 unique temperature/density cells")
    return indexed


def project_cell(
    cell: dict[str, Any], emissivity: dict[str, float], line_contract_version: int
) -> tuple[np.ndarray, np.ndarray]:
    """Replay a cell's OWN fresh flux/covariance with the matching version response."""
    fit = cell["fit"]
    if line_contract_version == 2:
        if fit.get("line_contract_version") != 2 or not str(
            fit.get("NIV_flux_definition", "")
        ).startswith("Total1483.321+1486.496"):
            raise ValueError("v2 requires its explicit total-doublet flux definition")
    elif line_contract_version != 1 or fit.get("line_contract_version", 1) != 1:
        raise ValueError("v1 must keep its original 1486-only flux definition")
    flux = np.asarray(fit["fluxes"], dtype=float)
    covariance = np.asarray(fit["flux_covariance"], dtype=float)
    if (
        fit.get("line_order") != list(LINE_NAMES)
        or fit.get("flux_units") != "1e-20 erg s^-1 cm^-2"
        or flux.shape != (5,)
        or not np.all(np.isfinite(flux))
        or covariance.shape != (5, 5)
        or not np.all(np.isfinite(covariance))
        or not np.allclose(covariance, covariance.T, rtol=1e-12, atol=1e-12)
        or np.min(np.linalg.eigvalsh(covariance)) <= 0
    ):
        raise ValueError("each own fit needs signed five-line fluxes and full positive covariance")
    x, ionic_covariance = check_ionic_measurement(cell["observed_two_stage_ionic_N_over_C"])
    # This helper is only version-agnostic matrix algebra, not a v1 grid validator.
    replay_ionic_operator((flux, covariance), emissivity, x, ionic_covariance)
    return x, ionic_covariance


def validate_pair(reports: dict[str, dict[str, Any]]) -> None:
    """Enforce separate contracts and closure before any shared cone calculation."""
    v1, v2 = reports["v1_report"], reports["v2_report"]
    base, grid, components = reports["v1_grid"], reports["v2_grid"], reports["v2_components"]
    if (
        v1.get("schema_version") != 1
        or v1.get("NIV_1483_included") is not False
        or v1.get("atomic_grid_sha256") != PINS["v1_grid"]
        or v1.get("component_grid_sha256") != V1_COMPONENTS_SHA256
        or v2.get("schema_version") != 2
        or v2.get("line_contract_version") != 2
        or v2.get("NIV_1483_included") is not True
        or v2.get("v1_1486_only_report_relabelled") is not False
        or v2.get("v1_physical_fit_sha256") != PINS["v1_report"]
        or v2.get("atomic_grid_v2_sha256") != PINS["v2_grid"]
        or v2.get("component_grid_v2_sha256") != PINS["v2_components"]
        or v2.get("parent_v1_atomic_grid_sha256") != PINS["v1_grid"]
    ):
        raise ValueError("separate pinned v1/v2 physical-fit line contracts required")
    for report in (v1, v2):
        if (
            report.get("native_report_sha256") != NATIVE_SHA256
            or report.get("line_flux_covariance_refit_for_each_template") is not True
            or report.get("source_amplitude_noise_covariance_refit") is not False
            or any(report.get(key) is not False for key in UNIDENTIFIED)
            or tuple(s["name"] for s in report["scenarios"]) != FAMILY_NAMES
        ):
            raise ValueError("shared frozen native data and uncalibrated families required")
    if v1.get("native_replay_receipt") != v2.get("native_replay_receipt"):
        raise ValueError("paired reports must refer to the same frozen native amplitudes")
    if base.get("schema_version") != 1:
        raise ValueError("unchanged v1 atomic grid required")
    for versioned in (grid, components):
        if (
            versioned.get("schema_version") != 2
            or versioned.get("line_contract_version") != 2
            or versioned.get("NIV_1483_included") is not True
            or versioned.get("pyneb_version") != "1.1.32"
            or versioned.get("parent_v1_atomic_grid_sha256") != PINS["v1_grid"]
        ):
            raise ValueError("v2 requires a summed-doublet atomic and component grid")
    if (
        components.get("atomic_grid_sha256") != PINS["v2_grid"]
        or components.get("parent_v1_component_grid_sha256") != V1_COMPONENTS_SHA256
    ):
        raise ValueError("v2 component/atomic lineage mismatch")
    old_cells, new_cells, templates = (
        indexed_cells(reports[key]["records"]) for key in ("v1_grid", "v2_grid", "v2_components")
    )
    if old_cells.keys() != new_cells.keys() or new_cells.keys() != templates.keys():
        raise ValueError("atomic/template cells differ between line contracts")
    for key in old_cells:
        old_e = old_cells[key]["emissivity_erg_cm3_s"]
        new_e = new_cells[key]["emissivity_erg_cm3_s"]
        group = templates[key]["components"][0]
        emission = np.asarray(group["component_emissivity_erg_cm3_s"], dtype=float)
        weights = np.asarray(group["normalized_weights"], dtype=float)
        if (
            set(old_e) != set(new_e)
            or any(new_e[name] != old_e[name] for name in old_e if name != "NIV")
            or group.get("group") != "NIV"
            or group.get("vacuum_wavelengths_A") != [1483.321, 1486.496]
            or emission.shape != (2,)
            or weights.shape != (2,)
            or not np.all(np.isfinite(emission) & (emission > 0))
            or not np.allclose(weights, emission / emission.sum(), rtol=1e-12, atol=0)
            or not np.isclose(emission[1], old_e["NIV"], rtol=1e-12, atol=0)
            or not np.isclose(emission.sum(), new_e["NIV"], rtol=1e-12, atol=0)
        ):
            raise ValueError("N IV total emissivity/physical weights must close by version")
    for report in (v1, v2):
        for family in report["scenarios"]:
            if indexed_cells(family["records"]).keys() != old_cells.keys():
                raise ValueError("every family must contain the same 28 matched cells")


def yield_hypotheses(benchmarks: dict[str, Any]) -> list[dict[str, Any]]:
    """The same four discrete SMS ceilings and four rounded rotating benchmarks."""
    solar = benchmarks["solar_reference"]
    ambient = 10 ** (solar["log_n_o"] - solar["log_c_o"])
    hypotheses = []
    for row in benchmarks["sms_yields"]["rows"]:
        ceiling = number_ratio(row, "n", "c")
        if ceiling <= ambient:
            raise ValueError("selected SMS ceiling must exceed the assumed ambient N/C")
        hypotheses.append(
            {
                "id": f"SMS_{row['initial_mass']:g}_Msun",
                "kind": "equal_retention_SMS_mixture_ceiling",
                "elemental_ratio_interval": [ambient, ceiling],
                "initial_mass_msun": row["initial_mass"],
                "stellar_initial_z_solar": benchmarks["sms_yields"]["stellar_initial_z_solar"],
            }
        )
    for index, row in enumerate(benchmarks["rotating_models"]["rows"]):
        ratio = 10 ** (row["log_n_o"] - row["log_c_o"])
        hypotheses.append(
            {
                "id": f"rotator_{index + 1}",
                "kind": "selected_equal_retention_rotator_fixed_ratio",
                "elemental_ratio_interval": [ratio, ratio],
                "scenario": row["scenario"],
                "stellar_initial_z": row["z"],
                "log_C_over_O_prediction_not_fitted": row["log_c_o"],
                "log_C12_over_C13_prediction_not_fitted": row["log_c12_c13"],
            }
        )
    return hypotheses


def conditional_profile(
    x: np.ndarray, covariance: np.ndarray, elemental_interval: list[float], k: float
) -> dict[str, Any]:
    """Explicit fixed stage-fraction ratio; equal N/C retention is in the hypotheses."""
    k = positive(k, "stage fraction ratio k")
    return profile_ionic_ratio_interval(x, covariance, *[bound / k for bound in elemental_interval])


def summarize(
    cells: list[dict[str, Any]], hypotheses: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    summaries = []
    for index, k in enumerate(K_VALUES):
        models = []
        for hypothesis in hypotheses:
            pairs = np.array(
                [cell["profile_deviances"][hypothesis["id"]][index] for cell in cells], dtype=float
            )
            old_high, new_high = pairs[:, 0] > SIGMA_95**2, pairs[:, 1] > SIGMA_95**2
            models.append(
                {
                    "hypothesis_id": hypothesis["id"],
                    "v1_deviance_range": [float(pairs[:, 0].min()), float(pairs[:, 0].max())],
                    "v2_deviance_range": [float(pairs[:, 1].min()), float(pairs[:, 1].max())],
                    "v1_cells_above_reference": int(old_high.sum()),
                    "v2_cells_above_reference": int(new_high.sum()),
                    "cells_above_only_v1": int((old_high & ~new_high).sum()),
                    "cells_above_only_v2": int((~old_high & new_high).sum()),
                }
            )
        summaries.append({"k": k, "models": models})
    return summaries


def compare_reports(
    reports: dict[str, dict[str, Any]], benchmarks: dict[str, Any]
) -> list[dict[str, Any]]:
    validate_pair(reports)
    grids = [indexed_cells(reports[key]["records"]) for key in ("v1_grid", "v2_grid")]
    hypotheses = yield_hypotheses(benchmarks)
    families = []
    for old_family, new_family in zip(
        reports["v1_report"]["scenarios"], reports["v2_report"]["scenarios"]
    ):
        versions = [indexed_cells(family["records"]) for family in (old_family, new_family)]
        cells = []
        for key in sorted(grids[0]):
            measurements = [
                project_cell(versions[i][key], grids[i][key]["emissivity_erg_cm3_s"], i + 1)
                for i in range(2)
            ]
            ionic = [versions[i][key]["observed_two_stage_ionic_N_over_C"] for i in range(2)]
            deviations = {
                hypothesis["id"]: [
                    [
                        conditional_profile(
                            x, covariance, hypothesis["elemental_ratio_interval"], k
                        )["conditional_profile_deviance"]
                        for x, covariance in measurements
                    ]
                    for k in K_VALUES
                ]
                for hypothesis in hypotheses
            }
            cells.append(
                {
                    "temperature_K": key[0],
                    "electron_density_cm3": key[1],
                    "ionic_ratio_v1_v2": [value["value"] for value in ionic],
                    "signed_95_fieller_v1_v2": [
                        value["conditional_gaussian_95_fieller_set"] for value in ionic
                    ],
                    "profile_deviances": deviations,
                }
            )
        families.append(
            {
                "name": old_family["name"],
                "matched_cells": len(cells),
                "summaries_by_k": summarize(cells, hypotheses),
                "reference_20000K_1000cm3": next(c for c in cells if cell_key(c) == REFERENCE_CELL),
                "cells": cells,
            }
        )
    return families


def run(
    v1_report: Path,
    v1_grid: Path,
    v2_report: Path,
    v2_grid: Path,
    v2_components: Path,
    benchmarks: Path = DEFAULT_INPUT,
) -> dict[str, Any]:
    paths = {
        "v1_report": v1_report,
        "v1_grid": v1_grid,
        "v2_report": v2_report,
        "v2_grid": v2_grid,
        "v2_components": v2_components,
        "benchmarks": benchmarks,
    }
    receipts = {
        name: {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for name, path in paths.items()
    }
    for name, expected in PINS.items():
        if receipts[name]["sha256"] != expected:
            raise ValueError(f"{name} bytes differ from the independently frozen experiment")
    reports = {name: json.loads(paths[name].read_text()) for name in PINS}
    inputs = json.loads(benchmarks.read_text())
    return {
        "schema_version": 1,
        "experiment": "paired_NIV_line_contract_conditional_yield_sensitivity",
        "input_receipts": receipts,
        "line_contracts": {"v1": "NIV1486-only", "v2": "totalNIV1483.321+1486.496"},
        "cell_specific_ionic_operator_and_covariance_replayed": True,
        "native_pixel_or_spectral_fit_rerun_in_this_module": False,
        "old_fluxes_or_covariances_rescaled": False,
        "elemental_identity": "elemental_NC = ionic_NC * k; k=f_C_observed/f_N_observed",
        "k_values_in_order": list(K_VALUES),
        "k_values_status": "explicit_sensitivity_assumptions_not_calibrated_or_prior_weighted",
        "N_over_C_retention_ratio_assumed": 1.0,
        "profile_deviance_order": ["v1", "v2"],
        "reference_deviance": SIGMA_95**2,
        "reference_status": "one_ratio_conditional_Gaussian_reference_not_calibrated_test",
        "counts_status": "deterministic_matched_grid_counts_not_probabilities_or_trials",
        "shared_data_alternatives_multiplied": False,
        "hypotheses": yield_hypotheses(inputs),
        "hypothesis_sources": {
            "SMS": inputs["sms_yields"]["source_url"],
            "original_SMS_yields": inputs["sms_yields"]["original_yield_source_url"],
            "selected_rotators": inputs["rotating_models"]["source_url"],
        },
        "families": compare_reports(reports, inputs),
        "software_files": [
            {
                "filename": str(path.relative_to(ROOT)),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in (
                ROOT / "discovery/niv_yield_sensitivity.py",
                ROOT / "discovery/atomic_enrichment.py",
                ROOT / "discovery/enrichment_constraints.py",
                ROOT / "tools/jwst/line_sensitivity.py",
            )
        ],
        "identified_mechanism_exclusions": [],
        "elemental_abundance_identified": False,
        "mechanism_probabilities": None,
        "remaining_dependencies": [
            "Source-specific LSF, extraction/profile and covariance transport calibration",
            "Photoionization stage fractions, resonant CIV transfer and stellar contribution",
            "Emission-phase association with yields and element-dependent retention",
            "Complete yield grids, gas mass and formation histories for physical model tests",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    defaults = {
        "v1_report": "mom_native_multiplet_refit.json",
        "v1_grid": "mom_atomic_grid.json",
        "v2_report": "mom_native_niv_doublet_refit_v2.json",
        "v2_grid": "mom_atomic_grid_niv_doublet_v2.json",
        "v2_components": "mom_multiplet_components_niv_doublet_v2.json",
    }
    for name, filename in defaults.items():
        parser.add_argument(
            "--" + name.replace("_", "-"), type=Path, default=ROOT / "research_output" / filename
        )
    parser.add_argument("--benchmarks", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "research_output/niv_yield_sensitivity.json"
    )
    args = parser.parse_args()
    result = run(**{name: getattr(args, name) for name in (*defaults, "benchmarks")})
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"output": str(args.output), "paired_cells": 112}))


if __name__ == "__main__":
    main()
