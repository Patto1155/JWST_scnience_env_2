"""Independent whitened NNLS audits of actual Cue and retained-yield likelihoods.

These oracles audit Gaussian algebra and conditional model contracts. They do
not calibrate the noise, ionization correction, stellar yields or emulator.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.linalg import cholesky, solve_triangular
from scipy.optimize import nnls

from discovery.continuation_review import digest


def cue_audit(archive: Path, spectrum: Path, comparison: Path) -> list:
    # The primary solver/model contract is separately inspected and reproduced;
    # this alternate optimizer does not use its covariance inverse or ray fitter.
    from tools.jwst.cue_grid import FITTED_GROUPS, group_predictions, parameters, read_models
    from tools.jwst.atomic_grid import spectral_scenarios
    from tools.jwst.line_sensitivity import LINE_NAMES

    models, _ = read_models(archive)
    theta, _ = parameters()
    predicted = group_predictions(theta, models)
    saved = json.loads(comparison.read_text())
    if saved["input_spectrum_sha256"] != digest(spectrum):
        raise ValueError("Cue comparison lineage differs from specified spectrum")
    inputs = spectral_scenarios(json.loads(spectrum.read_text()))
    indices = [LINE_NAMES.index(x) for x in FITTED_GROUPS]
    output = []
    for (label, fit), result in zip(inputs, saved["scenarios"], strict=True):
        covariance = np.asarray(fit["line_covariance"])[np.ix_(indices, indices)]
        flux = np.array([fit["lines"][name]["flux"] for name in FITTED_GROUPS])
        factor = cholesky(covariance, lower=True)
        values = solve_triangular(factor, flux, lower=True)
        design = solve_triangular(factor, (predicted / predicted[:, -1, None]).T, lower=True)
        chi2 = np.array([nnls(candidate[:, None], values)[1] ** 2 for candidate in design.T])
        best = float(chi2.min())
        count = int(np.sum(chi2 <= best + 3.84145882069))
        discrepancy = abs(best - result["best_chi2_four_groups"])
        if discrepancy > 1e-10 or count != result["grid_points_with_delta_chi2_le_3_841"]:
            raise ValueError("independent four-group Cue optimizer disagrees")
        output.append(
            {
                "family": label,
                "max_best_chi2_error": discrepancy,
                "independent_NNLS_grid_threshold_count": count,
                "models": len(predicted),
                "NIV_included": False,
            }
        )
    return output


def yield_audit(ionic: Path, comparison: Path) -> dict:
    records = json.loads(ionic.read_text())
    saved = json.loads(comparison.read_text())
    if saved["input_receipts"]["ionic"]["sha256"] != digest(ionic):
        raise ValueError("yield comparison lineage differs from specified ionic measurements")
    errors = []
    for model, family in zip(records["models"], saved["spectrum_families"], strict=True):
        cells = {
            (r["temperature_K"], r["electron_density_cm3"]): r["observed_two_stage_ionic_N_over_C"]
            for r in model["records"]
        }
        for result in family["cell_comparisons"]:
            record = cells[result["temperature_K"], result["electron_density_cm3"]]
            values = np.array([record["scaled_numerator"], record["scaled_denominator"]])
            factor = cholesky(np.asarray(record["scaled_covariance"]), lower=True)
            whitened = solve_triangular(factor, values, lower=True)
            profile = result["profile_if_k1_equal_retention_ambient_solar_NC"]
            lower, upper = profile["ratio_interval"]
            cone = solve_triangular(factor, np.array([[lower, upper], [1, 1]]), lower=True)
            _, restricted_residual = nnls(cone, whitened)
            _, unrestricted_residual = nnls(
                solve_triangular(factor, np.eye(2), lower=True), whitened
            )
            difference = restricted_residual**2 - unrestricted_residual**2
            errors.append(abs(difference - profile["conditional_profile_deviance"]))
    if not errors or max(errors) > 1e-9:
        raise ValueError("independent retained-yield convex-cone optimizer disagrees")
    return {
        "actual_cell_yield_profiles": len(errors),
        "maximum_deviance_absolute_error": max(errors),
        "mechanism_probability_supplied": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("cue", "yield"))
    parser.add_argument("--model-input", type=Path, required=True)
    parser.add_argument("--spectrum", type=Path)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "cue":
        if args.spectrum is None:
            parser.error("Cue audit requires --spectrum")
        results = cue_audit(args.model_input, args.spectrum, args.comparison)
    else:
        results = yield_audit(args.model_input, args.comparison)
    paths = {
        k: v
        for k, v in vars(args).items()
        if k in ("model_input", "spectrum", "comparison") and v is not None
    }
    output = {
        "schema_version": 1,
        "inputs_sha256": {k: digest(v) for k, v in paths.items()},
        "mode": args.mode,
        "independent_NNLS_audit": results,
    }
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
