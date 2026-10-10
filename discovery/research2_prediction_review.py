"""Independent conditional held-out tail normalization control.

The simulation is a known Gaussian linear model, not native detector noise or
empirical coverage. Actual saved tails are independently recalculated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import chi2


def predictive_statistic(values, design, measurement_covariance, trained_lines, trained_covariance):
    lines = design[:, 2:]
    c = measurement_covariance + lines @ trained_covariance @ lines.T
    precision = np.linalg.inv(c)
    nuisance = design[:, :2]
    projected = (
        precision
        - precision
        @ nuisance
        @ np.linalg.inv(nuisance.T @ precision @ nuisance)
        @ nuisance.T
        @ precision
    )
    residual = values - lines @ trained_lines
    return float(residual @ projected @ residual)


def audit(root):
    rng = np.random.default_rng(6144)
    training = rng.normal(size=(61, 7))
    testing = rng.normal(size=(48, 7))
    truth = np.array([11.0, -4.0, 20.0, 15.0, 15.0, 5.0, 12.0])
    information = np.linalg.inv(training.T @ training)
    estimator = information @ training.T
    actual_cov = np.eye(48)
    predicted_cov = actual_cov + testing[:, 2:] @ information[2:, 2:] @ testing[:, 2:].T
    precision = np.linalg.inv(predicted_cov)
    nuisance = testing[:, :2]
    projector = (
        precision
        - precision
        @ nuisance
        @ np.linalg.inv(nuisance.T @ precision @ nuisance)
        @ nuisance.T
        @ precision
    )
    draws = 4000
    train_values = training @ truth + rng.normal(size=(draws, 61))
    fitted = train_values @ estimator.T
    test_truth = truth.copy()
    test_truth[:2] = [-100.0, 200.0]
    test_values = testing @ test_truth + rng.normal(size=(draws, 48))
    residual = test_values - fitted[:, 2:] @ testing[:, 2:].T
    statistics = np.einsum("ij,ij->i", residual @ projector, residual)
    df = 46
    mean = float(statistics.mean())
    central_95 = float(np.mean(statistics < chi2.ppf(0.95, df)))
    assert abs(mean - df) < 5 * np.sqrt(2 * df / draws)
    assert abs(central_95 - 0.95) < 5 * np.sqrt(0.95 * 0.05 / draws)
    path = root / "research_output/mom_native_measurement_validation.json"
    report = json.loads(path.read_text())
    actual = []
    for row in report["signed_forward_corrected_group_checks"]:
        p = row["prediction"]
        assert p["dof"] == 208
        tail = float(chi2.sf(p["predictive_chi2"], p["dof"]))
        assert abs(tail - p["conditional_gaussian_tail_probability"]) < 1e-14
        actual.append(
            {
                "held_out_group": row["held_out_group"],
                "chi2": p["predictive_chi2"],
                "dof": p["dof"],
                "independently_calculated_tail": tail,
            }
        )
    return {
        "schema_version": 1,
        "report_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "synthetic_draws": draws,
        "seed": 6144,
        "synthetic_dof": df,
        "synthetic_statistic_mean": mean,
        "synthetic_fraction_below95percentile": central_95,
        "actual_recalculated_tails": actual,
        "scope": (
            "Independent precision nuisance projection and Gaussian tail normalization; "
            "source/empirical covariance calibration not established"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.root), indent=2) + "\n")


if __name__ == "__main__":
    main()
