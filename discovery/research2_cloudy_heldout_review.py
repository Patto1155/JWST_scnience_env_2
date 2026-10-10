"""Independent SVD, quadrature-amplitude and full predictive-precision checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.integrate import quad
from scipy.linalg import block_diag
from scipy.optimize import brentq

from discovery.continuation_wavecorr_review import bin_design, source_waves
from discovery.research2_cloudy_likelihood_review import constrained_full_fit
from discovery.research2_independent_review import digest, svd_fit
from discovery.research2_prediction_review import predictive_statistic


def moments_and_interval(mean, sigma):
    center = mean / sigma

    def density(x):
        return np.exp(-0.5 * (x - center) ** 2)

    normalizer = quad(density, 0, np.inf, epsabs=1e-12)[0]
    expected = quad(lambda x: x * density(x), 0, np.inf, epsabs=1e-12)[0] / normalizer
    second = quad(lambda x: x * x * density(x), 0, np.inf, epsabs=1e-12)[0] / normalizer
    upper = max(20, center + 12)
    interval = [
        sigma * brentq(lambda q: quad(density, 0, q, epsabs=1e-12)[0] / normalizer - p, 0, upper)
        for p in (0.025, 0.975)
    ]
    return sigma * expected, sigma**2 * (second - expected**2), interval


def audit(root, report_path):
    report = json.loads(report_path.read_text())
    with np.load(root / "research_output/mom_native_wavecorr.npz", allow_pickle=False) as saved:
        z = {key: saved[key].copy() for key in saved.files}
    with np.load(
        root / "research_output/mom_cloudy_signed_coupling.npz", allow_pickle=False
    ) as saved:
        coupling = saved["coupling"].copy()
    waves = source_waves(z["native_wave"], z["native_good"], z["trace"], z["sigma"][0])
    rw, rr = np.loadtxt(
        root / "data_sources/followup/unite_point_prism_resolution.csv",
        delimiter=",",
        skiprows=1,
        usecols=(0, 1),
    ).T
    factor = block_diag(*[np.linalg.cholesky(block) for block in z["spatial_covariance_blocks"]])
    covariance = factor @ np.kron(z["spectral_kernel"], np.eye(9)) @ factor.T
    covariance *= z["noise_scale_squared"][0]
    values = z["flux"].T.ravel()
    family = next(
        a
        for a in report["native_likelihood"]["alternatives"]
        if a["wavelength_hypothesis"] == "original_native"
        and a["noise"] == "empirical_rows_and_columns"
        and a["resolution"] == "generic_point"
    )
    prepared = []
    for row in family["records"]:
        direct = bin_design(waves, z["selected_columns"], rw, rr, row["component_weights"])
        design = np.einsum("cij,cjk->cik", coupling, direct.reshape(70, 9, 7)).reshape(630, 7)
        prepared.append((row, design, np.array(row["prediction_relative_CIII"])))
    checked = []
    for record in report["held_out_likelihood"]["records"]:
        test = np.tile(np.isin(np.arange(9), record["test_exposures"]), 70)
        train = ~test
        trials = []
        for row, design, ratios in prepared:
            if row["parameters"]["log_NC_relative_minus060"] != record["nitrogen_enhancement_dex"]:
                continue
            beta, _, statistic = constrained_full_fit(
                design[train], covariance[np.ix_(train, train)], values[train], ratios
            )
            physical = np.column_stack((design[train, :2], design[train, 2:] @ ratios))
            unrestricted, pcov, _, _ = svd_fit(
                physical, covariance[np.ix_(train, train)], values[train]
            )
            trials.append((statistic, row, design, ratios, unrestricted[-1], pcov[-1, -1] ** 0.5))
        statistic, row, design, ratios, mean, sigma = min(trials, key=lambda item: item[0])
        assert (
            row["model_id"] == record["chosen_model_id"]
            and row["A1500_mag"] == record["chosen_A1500_mag"]
        )
        expected, variance, interval = moments_and_interval(mean, sigma)
        predictive = predictive_statistic(
            values[test],
            design[test],
            covariance[np.ix_(test, test)],
            expected * ratios,
            variance * np.outer(ratios, ratios),
        )
        errors = [
            abs(statistic - record["training_profiled_chi2"]),
            abs(mean - record["unrestricted_training_amplitude"]),
            abs(sigma - record["training_amplitude_sigma"]),
            abs(expected - record["truncated_training_amplitude_mean"]),
            abs(variance - record["truncated_training_amplitude_variance"]),
            float(
                np.max(abs(np.array(interval) - record["truncated_training_amplitude_95_interval"]))
            ),
            abs(predictive - record["held_out_moment_matched_predictive_quadratic"]),
        ]
        assert max(errors) < 1e-7, errors
        checked.append(
            {
                "group": record["held_out_RATE_group"],
                "nitrogen": record["nitrogen_enhancement_dex"],
                "chosen_model_id": row["model_id"],
                "A1500_mag": row["A1500_mag"],
                "predictive_quadratic": predictive,
                "max_numerical_error": max(errors),
            }
        )
    return {
        "schema_version": 1,
        "report_sha256": digest(report_path),
        "records": checked,
        "max_numerical_error": max(row["max_numerical_error"] for row in checked),
        "scope": (
            "Direct constrained training SVD; numerically normalized nonnegative amplitude "
            "moments/quantiles; independent full predictive covariance and nuisance precision "
            "projector. Moment-matched quadratic is not a calibrated p-value."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "report", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.root, args.report), indent=2) + "\n")


if __name__ == "__main__":
    main()
