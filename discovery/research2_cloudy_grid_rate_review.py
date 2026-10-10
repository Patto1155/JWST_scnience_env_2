"""Independent complete Cloudy-grid/RATE bridge oracle using component CDFs and direct GLS.

Does not call the author's Cloudy prediction, fitting, amplitude or held-out
functions. The previously independently validated RATE covariance is the input.
No download and no Cloudy run is performed.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from astropy.io import fits
from scipy.special import erf, log_ndtr, ndtr, ndtri

from tools.jwst.line_sensitivity import read_resolution
from tools.jwst.native_reduction import ROOT, sha256
from tools.jwst.native_wavecorr import load_wavecorr_replay
from tools.jwst.point_resolution import read_point_resolution

REST = np.array(
    [
        1483.32,
        1486.50,
        1548.19,
        1550.77,
        1640.41,
        1660.81,
        1666.15,
        1746.82,
        1748.65,
        1749.67,
        1752.16,
        1753.99,
        1906.68,
        1908.73,
    ]
)
INDICES = ((0, 1), (2, 3), (4, 5, 6), (7, 8, 9, 10, 11), (12, 13))


def wavelength_grid(d: dict) -> np.ndarray:
    yy = np.arange(28)[:, None]
    center = d["trace_refined"][None, :]
    width = d["sigma_refined"]
    profile = 0.5 * (
        erf((yy + 0.5 - center) / (width * np.sqrt(2)))
        - erf((yy - 0.5 - center) / (width * np.sqrt(2)))
    )
    denominator = np.sum(profile * d["good"], axis=0)
    grid = np.divide(
        np.sum(profile * np.where(d["good"], d["wave"], 0), axis=0),
        denominator,
        out=np.full(423, np.nan),
        where=denominator > 0,
    )
    valid = np.flatnonzero(np.isfinite(grid))
    result = np.interp(np.arange(423), valid, grid[valid])
    left, right = valid[0], valid[-1]
    result[:left] = grid[left] + (np.arange(left) - left) * (grid[valid[1]] - grid[left])
    result[right + 1 :] = grid[right] + (np.arange(right + 1, 423) - right) * (
        grid[right] - grid[valid[-2]]
    )
    return result


def component_design(
    data: list[dict],
    selected: np.ndarray,
    resolution_wave: np.ndarray,
    resolution: np.ndarray,
    intensities: np.ndarray,
    attenuation: float,
    coupling: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    attenuated = intensities[:14] * 10 ** (-0.4 * attenuation * (REST / 1500) ** -1.2)
    totals = np.array([sum(attenuated[list(indices)]) for indices in INDICES])
    if np.any(totals <= 0):
        raise ValueError(
            "review requires complete positive physical groups; no missing-line zero fill"
        )
    direct = np.zeros((len(selected), 9, 7))
    for i, d in enumerate(data):
        wave = wavelength_grid(d)
        mid = (wave[1:] + wave[:-1]) / 2
        edges = np.concatenate(([2 * wave[0] - mid[0]], mid, [2 * wave[-1] - mid[-1]]))
        continuum = np.column_stack((np.ones(423), (wave - 2.675) / 0.525)) / 100
        lines = np.zeros((423, 5))
        for group, indices in enumerate(INDICES):
            for j in indices:
                center = REST[j] * 1e-4 * 15.44
                sigma = (
                    center
                    / np.interp(center, resolution_wave, resolution)
                    / (2 * np.sqrt(2 * np.log(2)))
                )
                fractions = 0.5 * np.diff(erf((edges - center) / (sigma * np.sqrt(2))))
                lines[:, group] += fractions / np.diff(edges) * attenuated[j] / totals[group]
        lines *= wave[:, None] ** 2 / 299792.458
        direct[:, i] = np.column_stack((continuum, lines))[selected]
    # Independent contraction: each output exposure includes its signed donors.
    transported = np.zeros_like(direct)
    for i in range(9):
        for j in range(9):
            transported[:, i] += coupling[:, i, j, None] * direct[:, j]
    design = transported.reshape(len(selected) * 9, 7)
    ratios = totals / totals[-1]
    physical = np.column_stack((design[:, :2], design[:, 2:] @ ratios))
    return design, physical, ratios


def total_covariance(blocks: np.ndarray, kernel: np.ndarray, scale: float) -> np.ndarray:
    count = len(blocks)
    factors = [np.linalg.cholesky(block) for block in blocks]
    result = np.zeros((count * 9, count * 9))
    for i in range(count):
        for j in range(count):
            result[i * 9 : i * 9 + 9, j * 9 : j * 9 + 9] = (
                scale * kernel[i, j] * (factors[i] @ factors[j].T)
            )
    return result


def gram_fit(
    design: np.ndarray,
    covariance: np.ndarray,
    values: np.ndarray,
    nonnegative_last: bool = False,
    precision: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, float]:
    inverse_design = (
        np.linalg.solve(covariance, design) if precision is None else precision @ design
    )
    coefficient_covariance = np.linalg.inv(design.T @ inverse_design)
    coefficients = coefficient_covariance @ (inverse_design.T @ values)
    if nonnegative_last and coefficients[-1] < 0:
        coefficients[:-1] = np.linalg.solve(
            design[:, :-1].T @ inverse_design[:, :-1], inverse_design[:, :-1].T @ values
        )
        coefficients[-1] = 0
    residual = values - design @ coefficients
    inverse_residual = (
        np.linalg.solve(covariance, residual) if precision is None else precision @ residual
    )
    statistic = float(residual @ inverse_residual)
    return coefficients, coefficient_covariance, statistic


def gain_coupling(npz: dict, replay: dict, native_dir: Path) -> np.ndarray:
    inventory = json.loads((ROOT / "data_sources/followup/mom_native_inventory.json").read_text())
    pins = {p["filename"]: p for p in inventory["products"]}
    products = json.loads(
        (ROOT / "data_sources/followup/mom_rate_noise_manifest.json").read_text()
    )["products"]
    sources = [p["filename"].replace("_rate", "_cal") for p in products]
    result = np.zeros((len(npz["selected_columns"]), 9, 9))
    selected = npz["selected_columns"]
    gain = npz["calibration_gain"]
    operators = npz["operators"]
    for j, (name, d) in enumerate(zip(sources, replay["data"])):
        path = native_dir / name
        if sha256(path) != pins[name]["sha256"]:
            raise ValueError("original CAL pin differs")
        with fits.open(path) as h:
            sci = next(x for x in h if x.name == "SCI" and x.header.get("SRCNAME") == "5224_277193")
            pathloss = np.asarray(h["PATHLOSS_PS", sci.header["EXTVER"]].data, float)
        yy = np.arange(28)[:, None]
        trace = d["trace_refined"][None, :]
        sigma = d["sigma_refined"]
        positive = 0.5 * (
            erf((yy + 0.5 - trace) / (sigma * np.sqrt(2)))
            - erf((yy - 0.5 - trace) / (sigma * np.sqrt(2)))
        )
        positive *= np.where(d["good"], pathloss, 0)
        for i in range((j // 3) * 3, (j // 3) * 3 + 3):
            ratio = np.divide(gain[i], gain[j], out=np.zeros((28, 423)), where=gain[j] > 0)
            result[:, i, j] = (1.0 if i == j else -0.5) * np.sum(
                operators[i] * ratio * positive, axis=0
            )[selected]
    return result


def run(
    artifact_path: Path, rate_report: Path, native_dir: Path, expected_models: int = 20
) -> dict:
    started = time.monotonic()
    artifact = json.loads(artifact_path.read_text())
    rate = json.loads(rate_report.read_text())
    receipt = rate["compact_replay"]
    compact = rate_report.parent / receipt["filename"]
    if sha256(compact) != receipt["sha256"]:
        raise ValueError("noise receipt differs")
    with np.load(compact, allow_pickle=False) as saved:
        arrays = {name: saved[name].copy() for name in saved.files}
    selected = arrays["selected_columns"]
    values = arrays["flux"].T.reshape(-1)
    original = load_wavecorr_replay(
        ROOT / "research_output/mom_native_wavecorr.json", corrected=False
    )
    coupling = gain_coupling(arrays, original, native_dir)
    q_error = float(np.max(abs(coupling - arrays["signed_response_coupling"])))
    if q_error > 1e-12:
        raise ValueError("fresh coupling is not actual gain/profile/operator contraction")
    np.testing.assert_allclose(
        values, original["flux"][:, selected].T.reshape(-1), rtol=0, atol=1e-12
    )
    models = {m["id"]: m for m in artifact["models"]}
    if len(models) != len(artifact["models"]) or len(models) != expected_models:
        raise ValueError("expected complete unique declared physical model grid")
    for model in models.values():
        response = np.asarray(model["intrinsic_line_values"], dtype=float)
        if response.shape != (29,) or not np.all(np.isfinite(response) & (response >= 0)):
            raise ValueError(
                "all29 physical line responses must be explicit, finite and nonnegative"
            )
    if set(m["parameters"]["log_NC_relative_minus060"] for m in models.values()) != {0.0, 1.0}:
        raise ValueError("ordinary and enhanced composition families must remain separate")
    environments = {}
    for model in models.values():
        parameters = model["parameters"]
        environment = tuple(
            sorted(
                (key, value)
                for key, value in parameters.items()
                if key != "log_NC_relative_minus060"
            )
        )
        nitrogen = parameters["log_NC_relative_minus060"]
        environments.setdefault(environment, []).append(nitrogen)
    if len(environments) * 2 != expected_models or any(
        sorted(x) != [0.0, 1.0] for x in environments.values()
    ):
        raise ValueError("each environmental control must have a thermal composition partner")
    rw, rr, _ = read_resolution(ROOT / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
    pw, pr, _ = read_point_resolution(
        ROOT / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    configurations = {
        "RATE_formal_v3": total_covariance(
            arrays["formal_covariance_blocks"], np.eye(len(selected)), 1.0
        ),
        "RATE_empirical_rows_and_columns_v3": total_covariance(
            arrays["spatial_covariance_blocks"],
            arrays["spectral_kernel"],
            float(arrays["noise_scale_squared"][0]),
        ),
    }
    likelihood = artifact["native_likelihood"]
    if likelihood["noise_contract_version"] != 3 or len(likelihood["alternatives"]) != 8:
        raise ValueError("expected eight distinct v3 alternatives")
    if likelihood["signed_coupling"]["report_sha256"] != sha256(rate_report):
        raise ValueError("Cloudy likelihood uses a different RATE report")
    precision = {
        name: np.linalg.solve(cov, np.eye(len(cov))) for name, cov in configurations.items()
    }
    errors, family_reviews = [], []
    primary = {}
    for alternative in likelihood["alternatives"]:
        corrected = alternative["wavelength_hypothesis"] == "pinned_toy_prediction"
        replay = load_wavecorr_replay(
            ROOT / "research_output/mom_native_wavecorr.json", corrected=corrected
        )
        covariance = configurations[alternative["noise"]]
        inverse_covariance = precision[alternative["noise"]]
        w, r = (pw, pr) if alternative["resolution"] == "generic_point" else (rw, rr)
        independent_scores = []
        seen = set()
        for record in alternative["records"]:
            identity = (record["model_id"], record["A1500_mag"])
            if identity in seen:
                raise ValueError("duplicate model/attenuation likelihood record")
            seen.add(identity)
            model = models[record["model_id"]]
            design, physical, ratios = component_design(
                replay["data"],
                selected,
                w,
                r,
                np.asarray(model["intrinsic_line_values"]),
                record["A1500_mag"],
                coupling,
            )
            coefficients, vc, chi = gram_fit(
                design, covariance, values, precision=inverse_covariance
            )
            amplitude, _, total = gram_fit(
                physical, covariance, values, True, precision=inverse_covariance
            )
            author = record["native_fit"]
            differences = {
                "flux": float(np.max(abs(coefficients[2:] - author["fluxes"]))),
                "covariance": float(np.max(abs(vc[2:, 2:] - author["flux_covariance"]))),
                "profiled_total_chi2": abs(total - record["full_native_profiled_chi2"]),
                "amplitude": abs(float(amplitude[-1]) - record["common_nonnegative_normalization"]),
                "component_summed_prediction": float(
                    np.max(abs(ratios - record["prediction_relative_CIII"]))
                ),
            }
            if max(differences.values()) > 2e-6:
                raise ValueError(f"fresh complete-component bridge differs: {differences}")
            if time.monotonic() - started > 180:
                raise RuntimeError("independent likelihood review exceeded180s cap")
            errors.append(differences)
            independent_scores.append(
                (
                    total,
                    model["id"],
                    record["A1500_mag"],
                    model["parameters"]["log_NC_relative_minus060"],
                )
            )
            if (
                not corrected
                and alternative["resolution"] == "generic_point"
                and alternative["noise"] == "RATE_empirical_rows_and_columns_v3"
            ):
                primary[(model["id"], record["A1500_mag"])] = physical
        screens = {screen for _, screen in seen}
        if (
            len(seen) != expected_models * 3
            or len(screens) != 3
            or ({model_id for model_id, _ in seen} != set(models))
        ):
            raise ValueError("each distinct alternative must contain every model and three screens")
        best = min(independent_scores)
        ordinary = min(x for x in independent_scores if x[3] == 0.0)
        enhanced = min(x for x in independent_scores if x[3] == 1.0)
        for independent, label in ((best, "best"), (ordinary, "best_ordinary")):
            reported = alternative[label]
            if (independent[1], independent[2]) != (reported["model_id"], reported["A1500_mag"]):
                raise ValueError("independent family minimum selects a different model/screen")
        delta = ordinary[0] - best[0]
        if abs(delta - alternative["ordinary_minus_global_minimum_chi2"]) > 2e-6:
            raise ValueError("independent ordinary/global profile difference disagrees")
        family_reviews.append(
            {
                "wavelength_hypothesis": alternative["wavelength_hypothesis"],
                "noise": alternative["noise"],
                "resolution": alternative["resolution"],
                "global_minimum_chi2": best[0],
                "best_model_id": best[1],
                "ordinary_minimum_chi2": ordinary[0],
                "ordinary_model_id": ordinary[1],
                "enhanced_minimum_chi2": enhanced[0],
                "enhanced_model_id": enhanced[1],
                "ordinary_minus_enhanced_profile_chi2": ordinary[0] - enhanced[0],
                "ordinary_minus_global_profile_chi2": delta,
            }
        )
    if len(errors) != expected_models * 3 * 8:
        raise ValueError("complete480-record extension was not checked")
    held = []
    for record in artifact.get("held_out_likelihood", {}).get("records", []):
        covariance = configurations["RATE_empirical_rows_and_columns_v3"]
        train = record["training_exposures"]
        test = record["test_exposures"]

        def positions(members):
            return (np.arange(len(selected))[:, None] * 9 + members).reshape(-1)

        tpos, xpos = positions(train), positions(test)
        choices = []
        train_covariance = covariance[np.ix_(tpos, tpos)]
        train_precision = np.linalg.solve(train_covariance, np.eye(len(tpos)))
        for (model_id, attenuation), physical in primary.items():
            if (
                models[model_id]["parameters"]["log_NC_relative_minus060"]
                != record["nitrogen_enhancement_dex"]
            ):
                continue
            coef, vc, chi = gram_fit(
                physical[tpos], train_covariance, values[tpos], precision=train_precision
            )
            _, _, constrained = gram_fit(
                physical[tpos], train_covariance, values[tpos], True, precision=train_precision
            )
            choices.append((constrained, model_id, attenuation, coef[-1], np.sqrt(vc[-1, -1])))
        chi, model_id, attenuation, mu, sigma = min(choices)
        alpha = -mu / sigma
        qtail = ndtr(-alpha)
        hazard = np.exp(-(alpha**2) / 2 - np.log(2 * np.pi) / 2 - log_ndtr(-alpha))
        mean = mu + sigma * hazard
        variance = sigma**2 * (1 + alpha * hazard - hazard**2)
        interval = mu + sigma * ndtri(ndtr(alpha) + np.array([0.025, 0.975]) * qtail)
        physical = primary[(model_id, attenuation)][xpos]
        predictive_cov = covariance[np.ix_(xpos, xpos)] + variance * np.outer(
            physical[:, 2], physical[:, 2]
        )
        residual = values[xpos] - mean * physical[:, 2]
        _, _, statistic = gram_fit(physical[:, :2], predictive_cov, residual)
        delta = max(
            abs(chi - record["training_profiled_chi2"]),
            abs(mean - record["truncated_training_amplitude_mean"]),
            abs(variance - record["truncated_training_amplitude_variance"]),
            float(np.max(abs(interval - record["truncated_training_amplitude_95_interval"]))),
            abs(statistic - record["held_out_moment_matched_predictive_quadratic"]),
        )
        if (
            model_id != record["chosen_model_id"]
            or attenuation != record["chosen_A1500_mag"]
            or delta > 2e-6
        ):
            raise ValueError("heldout model choice/amplitude/prediction differs")
        if time.monotonic() - started > 180:
            raise RuntimeError("independent held-out review exceeded180s cap")
        held.append(
            {
                "group": record["held_out_RATE_group"],
                "nitrogen_dex": record["nitrogen_enhancement_dex"],
                "maximum_absolute_difference": delta,
            }
        )
    if len(held) != 6:
        raise ValueError("expected three held-out groups and both composition families")
    return {
        "schema_version": 2,
        "expected_models": expected_models,
        "family_profile_reviews": family_reviews,
        "selected_minimum_fixed_dof_tail_probabilities_computed": False,
        "model_counts_are_probabilities": False,
        "runtime_seconds": time.monotonic() - started,
        "artifact_filename": artifact_path.name,
        "artifact_sha256": sha256(artifact_path),
        "RATE_noise_report_sha256": sha256(rate_report),
        "RATE_compact_sha256": sha256(compact),
        "gain_coupling_max_difference": q_error,
        "complete_component_records": len(errors),
        "maximum_errors": {key: max(x[key] for x in errors) for key in errors[0]},
        "heldout_checks": held,
        "approved": True,
        "scope": (
            "Independent component-CDF integration, actual CAL profile/RATE gain coupling, "
            "direct Gram GLS and constrained all14-component likelihood; truncated-amplitude "
            "heldouts via independent moments and full predictive covariance. Numerical bridge "
            "approval only: scalar source-wave convention, conditional empirical transport, "
            "ionizing spectrum, C IV transfer and common source calibration remain assumptions. "
            "No elemental posterior or interval coverage certification."
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--expected-models", type=int, default=20)
    p.add_argument("--artifact", type=Path, required=True)
    p.add_argument("--rate-report", type=Path, required=True)
    p.add_argument("--native-dir", type=Path, required=True)
    p.add_argument(
        "--output",
        type=Path,
        default=ROOT / "research_output/research2_cloudy_grid_rate_review.json",
    )
    args = p.parse_args()
    result = run(args.artifact, args.rate_report, args.native_dir, args.expected_models)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "approved": result["approved"],
                "records": result["complete_component_records"],
                "runtime_seconds": result["runtime_seconds"],
            }
        )
    )


if __name__ == "__main__":
    main()
