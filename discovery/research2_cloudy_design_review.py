"""Independent synthetic all-pair shape arithmetic control, not model science."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar

from discovery.research2_independent_review import digest
from discovery.research2_observation_review import numeric_gram
from tools.jwst.cloudy_observation_contrasts import compare_family


def audit(root):
    rng = np.random.default_rng(4595)
    models = []
    for env in range(10):
        for nitrogen in (0, 1):
            models.append(
                {
                    "id": f"synthetic_{env}_{nitrogen}",
                    "parameters": {"environment": env, "log_NC_relative_minus060": nitrogen},
                    "intrinsic_line_values": np.exp(rng.normal(size=29)).tolist(),
                }
            )
    waves = np.array([1483.32, 1486.50, 1906.68, 1908.73])
    indices = (0, 1, 12, 13)
    gram = numeric_gram(waves * 15.44 / 1e4, np.array([2000, 2500, 2800, 3000]), 400)
    attenuation = (0.0, 0.5, 1.0)
    result = compare_family(models, indices, gram, attenuation, "intrinsic_line_values")
    pair_results = []
    for truth in models[1::2]:
        for alternative in models[::2]:
            fractions = []
            for first in attenuation:
                for second in attenuation:
                    shapes = []
                    for model, a in ((truth, first), (alternative, second)):
                        values = np.array(model["intrinsic_line_values"])[list(indices)]
                        values *= np.exp(-0.4 * np.log(10) * a * (waves / 1500) ** -1.2)
                        shapes.append(values / values.sum())
                    t, m = shapes
                    optimum = minimize_scalar(
                        lambda amplitude: (t - amplitude * m) @ gram @ (t - amplitude * m),
                        bounds=(0, 10),
                        method="bounded",
                        options={"xatol": 1e-12},
                    )
                    fractions.append(float(optimum.fun / (t @ gram @ t)))
            pair_results.append((truth["id"], alternative["id"], min(fractions)))
    closest = min(pair_results, key=lambda row: row[-1])
    reported = result["closest_cross_environment"]
    assert closest[:2] == (
        reported["enhanced_truth_model_id"],
        reported["ordinary_alternative_model_id"],
    )
    errors = [abs(closest[-1] - reported["shape_information_fraction"])]
    for row in result["matched_environment_pairs"]:
        expected = next(
            p[-1]
            for p in pair_results
            if p[:2] == (row["enhanced_truth_model_id"], row["ordinary_alternative_model_id"])
        )
        errors.append(abs(expected - row["shape_information_fraction"]))
    assert max(errors) < 1e-12
    return {
        "schema_version": 1,
        "author_code_sha256": digest(root / "tools/jwst/cloudy_observation_contrasts.py"),
        "synthetic_seed": 4595,
        "synthetic_pair_count": len(pair_results),
        "attenuation_pairs_per_comparison": 9,
        "max_fraction_error": max(errors),
        "scope": (
            "Randomized synthetic all100 pair minima and ten matched pairs; independent "
            "numerical Gaussian quadrature and bounded amplitude optimization. "
            "No actual Cloudy output or observing forecast."
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
