"""Conditional geometric MOS prior, not empirically calibrated coverage."""

from __future__ import annotations

import numpy as np
from scipy.linalg import cholesky, solve_triangular
from scipy.special import logsumexp


def shift_row_wavelength(wave: np.ndarray, delta: float) -> np.ndarray:
    from tools.jwst.native_row_response import complete_row_wavelength

    result = np.empty_like(wave, dtype=float)
    for i, row in enumerate(wave):
        if np.count_nonzero(np.isfinite(row) & (row > 0)) < 3:
            # Unusable rows are skipped by the fixed source operator; do not invent coverage.
            result[i] = row
            continue
        completed = complete_row_wavelength(row)
        index = np.arange(len(row))
        at = index + delta
        shifted = np.interp(at, index, completed)
        shifted[at < 0] = completed[0] + at[at < 0] * (completed[1] - completed[0])
        shifted[at > index[-1]] = completed[-1] + (at[at > index[-1]] - index[-1]) * (
            completed[-1] - completed[-2]
        )
        result[i] = shifted
    return result


def marginal_coefficient_moments(designs, covariance, values, prior_weights):
    """Integrate linear Gaussian likelihoods with flat common coefficient prior.

    Includes the determinant from integrating coefficients; no positivity prior.
    Fieller applied to returned moments is an approximation, not mixture coverage.
    """
    chol = cholesky(covariance, lower=True)
    y = solve_triangular(chol, values, lower=True)
    means, covariances, chi2s, logweights = [], [], [], []
    for design, prior in zip(designs, prior_weights, strict=True):
        a = solve_triangular(chol, design, lower=True)
        q, r = np.linalg.qr(a, mode="reduced")
        if np.linalg.matrix_rank(r) < r.shape[0]:
            raise ValueError("rank deficient nuisance design")
        mean = np.linalg.solve(r, q.T @ y)
        inv = np.linalg.inv(r)
        cov = inv @ inv.T
        residual = y - a @ mean
        statistic = float(residual @ residual)
        logweight = np.log(prior) - statistic / 2 - np.log(np.abs(np.diag(r))).sum()
        means.append(mean)
        covariances.append(cov)
        chi2s.append(statistic)
        logweights.append(logweight)
    weights = np.exp(np.array(logweights) - logsumexp(logweights))
    means, covariances = np.array(means), np.array(covariances)
    mean = np.einsum("n,ni->i", weights, means)
    centered = means - mean
    total = np.einsum("n,nij->ij", weights, covariances) + np.einsum(
        "n,ni,nj->ij", weights, centered, centered
    )
    return {
        "coefficients": mean,
        "covariance": total,
        "weights": weights,
        "node_coefficients": means,
        "node_covariance": covariances,
        "node_chi2": np.array(chi2s),
        "chi2": float(weights @ chi2s),
        "dof": len(values) - len(mean),
    }


def main():
    import argparse
    import json
    from pathlib import Path

    from tools.jwst.native_measurement_validation import serial_fit

    parser = argparse.ArgumentParser(
        description="Replay assumed-prior mixture, not raw calibration"
    )
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--replay", type=Path)
    inputs.add_argument("--normalized", type=Path)
    parser.add_argument("--nodes", type=int, default=41)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.nodes not in (41, 81):
        raise ValueError("use frozen41 or separately labelled81-node numerical diagnostic")
    with np.load(args.replay or args.normalized, allow_pickle=False) as saved:
        if args.replay:
            designs = saved["nuisance_designs"]
            if len(designs) != 41 or args.nodes != 41:
                raise ValueError("compact is not frozen41-node mixture")
        else:
            from tools.jwst.native_rate_noise import rate_signed_response
            from tools.jwst.native_row_response import row_source_design

            geom = json.loads(str(saved["geometry_json"]))
            components = json.loads(str(saved["components_json"]))
            data = [
                dict(wave=w, good=g, point_pathloss=p, trace_seed=t, group=str(group))
                for w, g, p, t, group in zip(
                    saved["source_wave"],
                    saved["source_good"],
                    saved["source_point_pathloss"],
                    saved["source_trace_seed"],
                    saved["groups"],
                    strict=True,
                )
            ]
            nodes, _ = np.polynomial.legendre.leggauss(args.nodes)
            designs = []
            for node in nodes:
                shifted = [dict(d, wave=shift_row_wavelength(d["wave"], node - 0.25)) for d in data]
                positive = row_source_design(
                    shifted,
                    saved["resolution_wave"],
                    saved["resolution"],
                    components,
                    geom["sigma_pixels"],
                    geom["offset_pixels"],
                )
                designs.append(
                    rate_signed_response(
                        shifted,
                        positive,
                        saved["gains"],
                        saved["operators"],
                        saved["selected_columns"],
                    )
                )
        _, weights = np.polynomial.legendre.leggauss(args.nodes)
        fitted = marginal_coefficient_moments(
            designs,
            saved["transported_covariance"],
            saved["source_flux"].T.reshape(-1),
            weights / 2,
        )
        emissivity = json.loads(str(saved["emissivity_json"]))
    result = serial_fit(fitted, emissivity, 1)
    result["method"] = "Moment Fieller approximation under assumed geometric wavelength prior"
    result["quadrature_nodes"] = args.nodes
    result["primary_frozen_statistic"] = args.nodes == 41
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
