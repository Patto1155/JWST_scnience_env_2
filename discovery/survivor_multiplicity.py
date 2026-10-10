"""Bounded source46 finite-atmosphere blend test with a convex dual witness.

Arbitrary positive mixtures form a superset of binaries from the same grid.
A bad cone fit rules out rescuing this finite grid merely by multiplicity,
conditional on the adopted measured fluxes and nuisance covariance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from scipy.optimize import nnls

from discovery.survivor_atmosphere import BANDS, load_grid


def whiten(flux, covariance, shapes, retained=None):
    keep = np.arange(len(flux)) if retained is None else np.asarray(retained)
    covariance = np.asarray(covariance)
    if not np.allclose(covariance, covariance.T):
        raise ValueError("Covariance must be symmetric")
    lower = np.linalg.cholesky(covariance[np.ix_(keep, keep)])
    return (
        np.linalg.solve(lower, np.asarray(flux)[keep]),
        np.linalg.solve(lower, np.asarray(shapes)[keep]),
        lower,
    )


def best_pair(flux, covariance, shapes, retained=None):
    """Exact bounded enumeration of all two-column nonnegative GLS models.

    Each pair includes its boundary single-member solutions. All rows are
    considered; shortlist fitting cannot silently exclude an improving pair.
    """
    data, design, _ = whiten(flux, covariance, shapes, retained)
    gram = design.T @ design
    score = design.T @ data
    diagonal = np.diag(gram)
    if np.any(diagonal <= 0):
        raise ValueError("Nonidentifiable model column")
    amplitude = np.maximum(score / diagonal, 0)
    objective = data @ data - 2 * amplitude * score + amplitude**2 * diagonal
    single = int(np.argmin(objective))
    answer = (float(objective[single]), single, single, amplitude[single], 0.0)
    for first in range(design.shape[1] - 1):
        second = np.arange(first + 1, design.shape[1])
        cross = gram[first, second]
        determinant = diagonal[first] * diagonal[second] - cross**2
        valid = determinant > 1e-12 * diagonal[first] * diagonal[second]
        a = np.zeros(len(second))
        b = a.copy()
        a[valid] = (
            score[first] * diagonal[second[valid]] - score[second[valid]] * cross[valid]
        ) / determinant[valid]
        b[valid] = (
            score[second[valid]] * diagonal[first] - score[first] * cross[valid]
        ) / determinant[valid]
        valid &= (a >= 0) & (b >= 0)
        loss = np.where(valid, data @ data - a * score[first] - b * score[second], np.inf)
        j = int(np.argmin(loss))
        if loss[j] < answer[0]:
            answer = (float(loss[j]), first, int(second[j]), float(a[j]), float(b[j]))
    _, first, second, a, b = answer
    coefficients = np.zeros(design.shape[1])
    coefficients[first] += a
    coefficients[second] += b
    prediction = shapes @ coefficients
    residual = data - design @ coefficients
    return {
        "chi2_conditional": float(residual @ residual),
        "component_indices": [first, second],
        "component_f444_amplitudes_njy": [float(a), float(b)],
        "prediction_njy": prediction.tolist(),
    }


def cone_fit(flux, covariance, shapes):
    """NNLS fit plus directly verifiable separating-hyperplane certificate."""
    data, design, lower = whiten(flux, covariance, shapes)
    coefficients, norm = nnls(design, data, maxiter=20000)
    residual = data - design @ coefficients
    witness = residual / norm if norm else np.zeros(len(flux))
    products = design.T @ witness
    # Any nonnegative mixture must lie on the nonpositive side if this dual
    # inequality holds. The bound remains numerical and is tolerance-reported.
    return {
        "chi2_conditional": float(residual @ residual),
        "active_indices": np.flatnonzero(coefficients > 0).tolist(),
        "active_f444_amplitudes_njy": coefficients[coefficients > 0].tolist(),
        "prediction_njy": (shapes @ coefficients).tolist(),
        "dual_whitened_witness": witness.tolist(),
        "dual_band_weights_per_njy": np.linalg.solve(lower.T, witness).tolist(),
        "dual_max_grid_projection": float(products.max()),
        "dual_observed_projection": float(data @ witness),
        "dual_model_projection": float((design @ coefficients) @ witness),
        "dual_normalization": float(witness @ witness),
        "kkt_max_positive_projection": float(np.maximum(products, 0).max()),
        "kkt_active_absolute_projection": float(np.abs(products[coefficients > 0]).max(initial=0)),
    }


def run(directory: Path, photometry: Path, output: Path):
    started = time.perf_counter()
    grid, provenance = load_grid(directory)
    photo = json.loads(photometry.read_text())
    source = next(s for s in photo["sources"] if s["source_id"] == 46)
    if tuple(photo["bands"]) != BANDS:
        raise ValueError("Wrong band identities")
    flux = np.array([b["fixed_extended_fit"]["flux_njy"] for b in source["bands"]])
    absolute = np.array([row["flux_njy_at_10pc"] for row in grid])
    shapes = (absolute / absolute[:, -1, None]).T
    rows = []
    for scenario in source["phenomenological_continuum_sensitivity"]:
        covariance = np.array(scenario["flux_covariance_njy2"])
        pair = best_pair(flux, covariance, shapes)
        pair["components"] = [grid[i] for i in pair["component_indices"]]
        cone = cone_fit(flux, covariance, shapes)
        cone["components"] = [grid[i] for i in cone["active_indices"]]
        held = []
        for omitted in range(len(BANDS)):
            keep = np.delete(np.arange(len(BANDS)), omitted)
            result = best_pair(flux, covariance, shapes, keep)
            cross = covariance[omitted, keep]
            sub = covariance[np.ix_(keep, keep)]
            sigma = np.sqrt(covariance[omitted, omitted] - cross @ np.linalg.solve(sub, cross))
            prediction = np.array(result["prediction_njy"])
            adjusted = (
                flux[omitted]
                - prediction[omitted]
                - cross @ np.linalg.solve(sub, flux[keep] - prediction[keep])
            )
            held.append(
                {
                    "omitted_band": BANDS[omitted],
                    **result,
                    "conditional_residual_over_assumed_sigma": float(adjusted / sigma),
                }
            )
        rows.append(
            {
                "fractional_floor_assumed": scenario["independent_fractional_floor"],
                "covariance_njy2": covariance.tolist(),
                "all_pairs": pair,
                "unrestricted_positive_grid_cone": cone,
                "held_out_pairs": held,
            }
        )
    result = {
        "schema_version": 1,
        "source_id": 46,
        "bands": BANDS,
        "question": (
            "Can positive multiplicity within the finite Bobcat grid rescue its "
            "seven-band discrepancy?"
        ),
        "new_selected_download_bytes": 0,
        "photometry_sha256": hashlib.sha256(photometry.read_bytes()).hexdigest(),
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "input_provenance": provenance,
        "observed_njy": flux.tolist(),
        "grid_rows": len(grid),
        "pairs_with_single_boundaries": len(grid) * (len(grid) - 1) // 2,
        "scenarios": rows,
        "runtime_seconds": time.perf_counter() - started,
        "limits": [
            "Finite cloudless equilibrium grid only; no general atmosphere exclusion.",
            "Arbitrary positive amplitudes need not describe a coeval physical binary.",
            "Conditional covariance includes assumed floors, not measured calibration.",
            "No class likelihood, distance, identity or grid-count probability.",
            "Held-out bands retain selected morphology and dependent observations.",
        ],
    }
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--photometry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.input, args.photometry, args.output)
    print(
        json.dumps(
            [
                (
                    s["fractional_floor_assumed"],
                    s["all_pairs"]["chi2_conditional"],
                    s["unrestricted_positive_grid_cone"]["chi2_conditional"],
                )
                for s in result["scenarios"]
            ]
        )
    )


if __name__ == "__main__":
    main()
