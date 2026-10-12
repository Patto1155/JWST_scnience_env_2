"""Retained-model NIII+CIII design stress test; no source calibration or odds."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from tools.jwst.cloudy_observation_contrasts import (
    EXPECTED_LINES,
    GROUPS,
    NITROGEN_KEY,
    environment,
    screen,
    validate_models,
)
from tools.jwst.observation_design import ROOT, SOURCE, gaussian_gram, read_nominal_curves


def gain_discrimination(
    gram: np.ndarray,
    truth: np.ndarray,
    alternative: np.ndarray,
    nitrogen_components: int,
    half_width: float | None,
) -> dict:
    """Exact two-column cone fit with global amplitude and relative ion gain.

    Truth response is fixed at unity. Bounds apply to the alternative's NIII
    gain relative to CIII, not a prior or a measured instrument uncertainty.
    None allows the two ion amplitudes to vary independently and nonnegatively.
    """
    gram = np.asarray(gram, float)
    truth, alternative = np.asarray(truth, float), np.asarray(alternative, float)
    if (
        truth.ndim != 1
        or alternative.shape != truth.shape
        or gram.shape != (len(truth), len(truth))
        or not np.all(np.isfinite(gram))
        or not np.allclose(gram, gram.T)
        or np.min(np.linalg.eigvalsh(gram)) <= 0
        or not np.all(np.isfinite(truth))
        or not np.all(np.isfinite(alternative))
        or np.any(truth < 0)
        or np.any(alternative < 0)
        or not np.isclose(truth.sum(), 1)
        or not np.isclose(alternative.sum(), 1)
        or not 0 < nitrogen_components < len(truth)
        or (half_width is not None and (not np.isfinite(half_width) or not 0 <= half_width < 1))
    ):
        raise ValueError(
            "positive Gram, normalized nonnegative shapes and valid gain bound required"
        )
    columns = np.zeros((len(truth), 2))
    columns[:nitrogen_components, 0] = alternative[:nitrogen_components]
    columns[nitrogen_components:, 1] = alternative[nitrogen_components:]
    hessian = columns.T @ gram @ columns
    rhs = columns.T @ gram @ truth
    if np.min(np.linalg.eigvalsh(hessian)) <= 0:
        raise ValueError("both ion bundles require positive response")
    # A convex quadratic on this 2D cone attains its minimum at its stationary
    # point, a cone boundary or the origin. Enumerate these exactly.
    candidates = [np.zeros(2)]
    unconstrained = np.linalg.solve(hessian, rhs)
    if np.all(unconstrained >= 0) and (
        half_width is None
        or (1 - half_width) * unconstrained[1]
        <= unconstrained[0]
        <= (1 + half_width) * unconstrained[1]
    ):
        candidates.append(unconstrained)
    boundaries = (
        [np.array([1.0, 0.0]), np.array([0.0, 1.0])]
        if half_width is None
        else [np.array([1 - half_width, 1.0]), np.array([1 + half_width, 1.0])]
    )
    for direction in boundaries:
        amplitude = max(0.0, float(direction @ rhs / (direction @ hessian @ direction)))
        candidates.append(amplitude * direction)

    def objective(coefficients: np.ndarray) -> float:
        residual = truth - columns @ coefficients
        return float(residual @ gram @ residual)

    coefficients = min(candidates, key=objective)
    fraction = max(0.0, objective(coefficients) / float(truth @ gram @ truth))
    return {
        "profiled_NIII_amplitude": float(coefficients[0]),
        "profiled_CIII_amplitude": float(coefficients[1]),
        "profiled_NIII_relative_gain": None
        if coefficients[1] == 0
        else float(coefficients[0] / coefficients[1]),
        "shape_information_fraction": fraction,
        "required_truth_matched_SNR": None if fraction < 1e-14 else float(np.sqrt(9 / fraction)),
        "separation_status": "numerically_nonidentifiable"
        if fraction < 1e-14
        else "finite_conditional_separation",
        "expected_separation_lambda": 9.0,
    }


def run(pilot: dict, plan: dict) -> dict:
    validate_models(pilot)
    started = time.monotonic()
    indices = GROUPS["NIII"] + GROUPS["CIII"]
    rest = np.array([EXPECTED_LINES[i][1] for i in indices])
    observed = rest * 15.44 / 1e4
    w, r = read_nominal_curves()[plan["mode"]]
    gram = gaussian_gram(observed, np.interp(observed, w, r), plan["intrinsic_fwhm_km_s"])
    ordinary = [m for m in pilot["models"] if m["parameters"][NITROGEN_KEY] == 0]
    enhanced = [m for m in pilot["models"] if m["parameters"][NITROGEN_KEY] == 1]
    cases = []
    for response in plan["response_contracts"]:
        shapes = {}
        for model in pilot["models"]:
            for attenuation in plan["attenuation_A1500_mag"]:
                values = screen(np.array(model[response])[list(indices)], rest, attenuation)
                shapes[model["id"], attenuation] = values / values.sum()
        for half_width in plan["fractional_gain_half_widths"]:
            comparisons = []
            for truth in enhanced:
                for alternative in ordinary:
                    rows = []
                    for truth_A in plan["attenuation_A1500_mag"]:
                        for alt_A in plan["attenuation_A1500_mag"]:
                            result = gain_discrimination(
                                gram,
                                shapes[truth["id"], truth_A],
                                shapes[alternative["id"], alt_A],
                                len(GROUPS["NIII"]),
                                half_width,
                            )
                            rows.append(
                                {
                                    "enhanced_truth_model_id": truth["id"],
                                    "ordinary_alternative_model_id": alternative["id"],
                                    "enhanced_A1500_mag": truth_A,
                                    "ordinary_A1500_mag": alt_A,
                                    "same_environment": environment(truth)
                                    == environment(alternative),
                                    **result,
                                }
                            )
                    comparisons.append(min(rows, key=lambda row: row["shape_information_fraction"]))
            paired = [row for row in comparisons if row["same_environment"]]
            cases.append(
                {
                    "response": response,
                    "fractional_gain_half_width": half_width,
                    "gain_bounds": None if half_width is None else [1 - half_width, 1 + half_width],
                    "closest_cross_environment": min(
                        comparisons, key=lambda row: row["shape_information_fraction"]
                    ),
                    "matched_environment_pairs": paired,
                    "hardest_matched_environment": min(
                        paired, key=lambda row: row["shape_information_fraction"]
                    ),
                    "cross_environment_comparisons": len(comparisons),
                    "attenuation_pairs_per_comparison": len(plan["attenuation_A1500_mag"]) ** 2,
                }
            )
            if time.monotonic() - started > plan["computation_cap_seconds"]:
                raise RuntimeError("fixed experiment computation cap exceeded")
    return {
        "schema_version": 1,
        "plan": plan,
        "cases": cases,
        "observed_component_wavelengths_um": observed.tolist(),
        "truth_convention": "enhanced model at unit relative response; matched total bundle SNR",
        "measurement_scope": (
            "retained equilibrated model predictions; no new pixels or observed likelihood"
        ),
        "new_download_bytes": 0,
        "runtime_seconds": time.monotonic() - started,
        "calibration_errors_measured": False,
        "finite_counts_are_probabilities": False,
        "absolute_exposure_seconds": None,
        "interpretation": (
            "Finite-family nuisance stress bounds, not posterior odds, abundance "
            "or a demonstrated calibration requirement."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=ROOT / "research_output/mom_cloudy_pilot20_rate_v3.json"
    )
    parser.add_argument("--plan", type=Path, default=SOURCE / "ion_gain_plan.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = args.input.read_bytes()
    plan_payload = args.plan.read_bytes()
    plan = json.loads(plan_payload)
    actual_hash = hashlib.sha256(payload).hexdigest()
    if actual_hash != plan["input_sha256"]:
        raise ValueError("retained reviewed model identity changed")
    result = run(json.loads(payload), plan)
    result.update(input_sha256=actual_hash, plan_sha256=hashlib.sha256(plan_payload).hexdigest())
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
