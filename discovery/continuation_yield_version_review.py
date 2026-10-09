"""Independent fresh ionic projections and whitened NNLS for both N IV contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.linalg import solve_triangular
from scipy.optimize import nnls

from discovery.continuation_review import digest


def cone_deviance(x, covariance, lower, upper):
    x, covariance = np.asarray(x), np.asarray(covariance)
    if (
        x.shape != (2,)
        or covariance.shape != (2, 2)
        or not np.isfinite(x).all()
        or not np.isfinite(covariance).all()
        or not np.allclose(covariance, covariance.T)
        or np.linalg.eigvalsh(covariance).min() <= 0
        or not np.isfinite([lower, upper]).all()
        or not 0 <= lower <= upper
    ):
        raise ValueError("finite signed pair, SPD covariance and ordered nonnegative rays required")
    factor = np.linalg.cholesky(covariance)
    y = solve_triangular(factor, x, lower=True)
    unrestricted = solve_triangular(factor, np.eye(2), lower=True)
    rays = np.array([[lower, 1], [upper, 1]]).T if lower != upper else np.array([[lower, 1]]).T
    constrained = solve_triangular(factor, rays, lower=True)
    _, baseline = nnls(unrestricted, y)
    _, alternative = nnls(constrained, y)
    return max(0.0, float(alternative**2 - baseline**2))


def audit(root: Path):
    path = root / "research_output/niv_yield_sensitivity.json"
    saved = json.loads(path.read_text())
    receipts = saved["input_receipts"]
    inputs = {}
    for name, receipt in receipts.items():
        parent = "data_sources/pilot" if name == "benchmarks" else "research_output"
        source = root / parent / receipt["file"]
        if digest(source) != receipt["sha256"]:
            raise ValueError("versioned input receipt differs")
        inputs[name] = json.loads(source.read_text())
    benchmark = inputs["benchmarks"]
    ambient = 10 ** (
        benchmark["solar_reference"]["log_n_o"] - benchmark["solar_reference"]["log_c_o"]
    )
    expected_intervals = [
        [ambient, row["n"] / 14 / (row["c"] / 12)] for row in benchmark["sms_yields"]["rows"]
    ] + [
        [10 ** (row["log_n_o"] - row["log_c_o"])] * 2
        for row in benchmark["rotating_models"]["rows"]
    ]
    if not np.allclose(
        expected_intervals, [h["elemental_ratio_interval"] for h in saved["hypotheses"]]
    ):
        raise ValueError("mass-to-number yield or ambient interval differs")
    errors, covariance_errors, measurement_errors = [], [], []
    counts = []
    for index, family in enumerate(saved["families"]):
        measured = []
        for version in (1, 2):
            data = inputs[f"v{version}_report"]["scenarios"][index]
            grid = {
                tuple((r["temperature_K"], r["electron_density_cm3"])): r
                for r in inputs[f"v{version}_grid"]["records"]
            }
            projected = {}
            for cell in data["records"]:
                key = cell["temperature_K"], cell["electron_density_cm3"]
                fit = cell["fit"]
                if version == 2 and fit.get("line_contract_version") != 2:
                    raise ValueError("matching fresh total-doublet likelihood required")
                epsilon = grid[key]["emissivity_erg_cm3_s"]
                response = np.array(
                    [
                        [
                            epsilon["CIII"] / epsilon["NIV"],
                            0,
                            0,
                            epsilon["CIII"] / epsilon["NIII"],
                            0,
                        ],
                        [0, epsilon["CIII"] / epsilon["CIV"], 0, 0, 1],
                    ]
                )
                x = response @ np.asarray(fit["fluxes"])
                covariance = response @ np.asarray(fit["flux_covariance"]) @ response.T
                ionic = cell["observed_two_stage_ionic_N_over_C"]
                expected = [ionic["scaled_numerator"], ionic["scaled_denominator"]]
                measurement_errors.append(float(np.max(abs(x - expected))))
                covariance_errors.append(
                    float(np.max(abs(covariance - ionic["scaled_covariance"])))
                )
                if not np.allclose(x, expected, rtol=1e-12, atol=1e-12) or not np.allclose(
                    covariance, ionic["scaled_covariance"], rtol=1e-12, atol=1e-12
                ):
                    raise ValueError("fresh per-cell full covariance projection differs")
                projected[key] = x, covariance
            measured.append(projected)
        results = np.empty((28, 8, 3, 2))
        for cell_index, cell in enumerate(family["cells"]):
            key = cell["temperature_K"], cell["electron_density_cm3"]
            for model_index, hypothesis in enumerate(saved["hypotheses"]):
                for k_index, k in enumerate(saved["k_values_in_order"]):
                    lower, upper = np.asarray(hypothesis["elemental_ratio_interval"]) / k
                    for version in range(2):
                        x, covariance = measured[version][key]
                        value = cone_deviance(x, covariance, lower, upper)
                        expected = cell["profile_deviances"][hypothesis["id"]][k_index][version]
                        errors.append(abs(value - expected))
                        if not np.isfinite(value) or not np.isclose(
                            value, expected, rtol=1e-11, atol=1e-11
                        ):
                            raise ValueError("independent whitened NNLS cone differs")
                        results[cell_index, model_index, k_index, version] = value
        above = results > saved["reference_deviance"]
        for k_index, summary in enumerate(family["summaries_by_k"]):
            for model_index, model in enumerate(summary["models"]):
                old, new = above[:, model_index, k_index].T
                expected = [
                    int(old.sum()),
                    int(new.sum()),
                    int((old & ~new).sum()),
                    int((~old & new).sum()),
                ]
                reported = [
                    model[k]
                    for k in (
                        "v1_cells_above_reference",
                        "v2_cells_above_reference",
                        "cells_above_only_v1",
                        "cells_above_only_v2",
                    )
                ]
                if expected != reported:
                    raise ValueError("deterministic matched grid counts differ")
        counts.append(
            {
                "family": family["name"],
                "v1_counts_by_model_k": above[..., 0].sum(axis=0).tolist(),
                "v2_counts_by_model_k": above[..., 1].sum(axis=0).tolist(),
            }
        )
    if len(errors) != 5376:
        raise ValueError("complete paired 5376-cone experiment required")
    return {
        "schema_version": 1,
        "yield_bridge_sha256": digest(path),
        "input_receipts": receipts,
        "independent_fresh_ionic_projections": 224,
        "independent_whitened_NNLS_cones": len(errors),
        "maximum_deviance_absolute_difference": max(errors),
        "maximum_ionic_measurement_difference": max(measurement_errors),
        "maximum_ionic_covariance_difference": max(covariance_errors),
        "conditional_reference_counts": counts,
        "scope": (
            "Fixed k/equal retention/discrete benchmarks; deterministic sensitivity, "
            "no calibrated mechanism exclusion or probabilities"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.root), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
