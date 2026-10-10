"""Complete composition-aware Cloudy pilot and native full-covariance likelihood.

A bounded set of explicit HII-region alternatives is not a posterior or an
exhaustive ionization correction. Each composition executes thermal equilibrium.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import re
import subprocess
import time
from pathlib import Path

import numpy as np
from scipy.linalg import cholesky, solve_triangular

from data_pipeline.cloudy_inputs import verify
from tools.jwst.line_sensitivity import read_resolution
from tools.jwst.native_reduction import fit_native
from tools.jwst.native_reduction import extract_columns, read_inputs, signed_profiles
from tools.jwst.native_measurement_validation import (
    apply_signed_response,
    response,
    signed_response_coupling,
    transported_covariance,
)
from tools.jwst.native_wavecorr import load_wavecorr_replay
from tools.jwst.point_resolution import read_point_resolution

ROOT = Path(__file__).resolve().parents[2]
WAVECORR_SHA256 = "80ca86e7969e82bca424a963b39282f2fec42d589fb055238b4ac18510ab3fe6"
# Exact Cloudy identities: <2000A vacuum, >2000A AIR (Cloudy default).
LINES = (
    ("N  4", 1483.32),
    ("N  4", 1486.50),
    ("C  4", 1548.19),
    ("C  4", 1550.77),
    ("He 2", 1640.41),
    ("O  3", 1660.81),
    ("O  3", 1666.15),
    ("N  3", 1746.82),
    ("N  3", 1748.65),
    ("N  3", 1749.67),
    ("N  3", 1752.16),
    ("N  3", 1753.99),
    ("C  3", 1906.68),
    ("C  3", 1908.73),
    ("Blnd", 1486.00),
    ("Blnd", 1549.00),
    ("Blnd", 1650.00),
    ("Blnd", 1750.00),
    ("Blnd", 1909.00),
    ("H  1", 4861.32),
    ("O  3", 5006.84),
    ("N  2", 6583.45),
    ("N  5", 1238.82),
    ("N  5", 1242.80),
    ("C  2", 2323.50),
    ("C  2", 2324.69),
    ("C  2", 2325.40),
    ("C  2", 2326.93),
    ("C  2", 2328.12),
)
SLICES = (slice(0, 2), slice(2, 4), slice(4, 7), slice(7, 12), slice(12, 14))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pilot_parameters() -> list[dict]:
    """Declared before outcomes: paired N/C controls plus one-axis perturbations."""
    base = {
        "log_nH_cm3": 3.0,
        "log_U": -2.0,
        "blackbody_K": 60000.0,
        "metallicity_scale": 0.2,
        "log_CO": -0.37,
        "log_NC_relative_minus060": 0.0,
    }
    geometries = [base]
    for key, values in (
        ("log_nH_cm3", (2.0, 4.0, 5.0)),
        ("log_U", (-3.0, -1.0)),
        ("blackbody_K", (40000.0, 100000.0)),
        ("metallicity_scale", (0.05, 0.5)),
    ):
        geometries.extend(dict(base, **{key: value}) for value in values)
    return [
        dict(row, log_NC_relative_minus060=nitrogen)
        for row in geometries
        for nitrogen in (0.0, 1.0)
    ]


def input_text(parameters: dict, name: str, *, refinement: bool = False) -> str:
    z = parameters["metallicity_scale"]
    if z <= 0 or parameters["blackbody_K"] <= 0:
        raise ValueError("positive physical parameters required")
    oxygen = math.log10(4.90e-4)
    # Cloudy applies global metals scaling after all abundance commands.
    # These overrides must be the unscaled base pattern, not Z-scaled twice.
    carbon = oxygen + parameters["log_CO"]
    nitrogen = carbon - 0.60 + parameters["log_NC_relative_minus060"]
    commands = [
        f"title Independent MoM composition pilot {name}",
        f"blackbody {parameters['blackbody_K']:.8g} K",
        f"ionization parameter {parameters['log_U']:.8g}",
        f"hden {parameters['log_nH_cm3']:.8g}",
        "abundances GASS10",
        f"metals {z:.8g} linear",
        f"element carbon abundance {carbon:.12g}",
        f"element nitrogen abundance {nitrogen:.12g}",
        f"element oxygen abundance {oxygen:.12g}",
        "radius 19",
        "sphere",
        "CMB redshift 14.44",
        "stop efrac -2",
        "stop temperature 1000 K",
        "stop zone 3000",
        "iterate to convergence",
        "print line precision 6",
        f'save last line list "{name}.lin" "pilot-lines.dat" absolute',
        f'save last line list "{name}.emergent.lin" "pilot-lines.dat" absolute emergent',
        f'save last overview "{name}.ovr"',
        f'save last abundances "{name}.abn"',
        f'save last averages "{name}.avr"',
        "temperature hydrogen 2",
        "temperature nitrogen 3",
        "temperature nitrogen 4",
        "temperature carbon 3",
        "temperature carbon 4",
        "end of averages",
    ]
    if refinement:
        commands[0] += " tighter spatial zoning"
        commands.insert(20, "set continuum resolution 0.5")
        commands.insert(21, "set temperature convergence 0.001")
        commands.insert(22, "set eden convergence 0.003")
    return "\n".join(commands) + "\n"


def read_line_output(path: Path) -> np.ndarray:
    """Missing/misidentified lines fail; a physical model zero is kept explicit."""
    rows = [row for row in path.read_text().splitlines() if row.startswith("iteration ")]
    if len(rows) != 1:
        raise ValueError("exactly one final intrinsic line row required")
    values = np.asarray([float(item) for item in rows[0].split()[2:]])
    if values.shape != (len(LINES),) or not np.all(np.isfinite(values) & (values >= 0)):
        raise ValueError("complete finite nonnegative intrinsic line response required")
    header = next(row for row in path.read_text().splitlines() if row.startswith("#"))
    actual_identities = header.split("\t")[1:]
    expected_identities = [f"{label} {wavelength:.2f}A" for label, wavelength in LINES]
    if actual_identities != expected_identities:
        raise ValueError("required ordered line identity absent or misplaced")
    totals = np.asarray([values[selection].sum() for selection in SLICES])
    if not np.allclose(totals, values[14:19], rtol=1e-4, atol=1e-30):
        raise ValueError("Cloudy blends do not equal independently summed components")
    if np.any(totals <= 0):
        raise ValueError("model with zero required group cannot define normalized template")
    return values


def validate_abundances(path: Path, parameters: dict) -> dict:
    """Check actual gas densities, not the input-command ordering interpretation."""
    labels = path.read_text().splitlines()[0].removeprefix("#abund ").split()
    values = np.loadtxt(path, comments="#", ndmin=2)
    if values.shape[1] != len(labels) or not np.all(np.isfinite(values)):
        raise ValueError("actual gas abundance table is incomplete")
    expected_oxygen = math.log10(4.90e-4 * parameters["metallicity_scale"])
    expected = {
        "OXYG": expected_oxygen,
        "CARB": expected_oxygen + parameters["log_CO"],
        "NITR": expected_oxygen
        + parameters["log_CO"]
        - 0.60
        + parameters["log_NC_relative_minus060"],
    }
    actual = {}
    for label, target in expected.items():
        ratios = values[:, labels.index(label)] - values[:, labels.index("H")]
        if not np.all(np.abs(ratios - target) <= 0.0101):
            raise ValueError(f"actual {label}/H differs from declared gas composition")
        actual[label] = {
            "declared_log_XH": target,
            "actual_log_XH_range": [float(ratios.min()), float(ratios.max())],
            "output_rounding_tolerance_dex": 0.0101,
        }
    return actual


def execute_model(
    executable: Path, run_dir: Path, parameters: dict, name: str, *, refinement: bool = False
) -> dict:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "pilot-lines.dat").write_text(
        "".join(f"{label} {wave:.2f}A\n" for label, wave in LINES)
    )
    input_path = run_dir / f"{name}.in"
    input_path.write_text(input_text(parameters, name, refinement=refinement))
    started = time.monotonic()
    result = subprocess.run(
        [str(executable.resolve()), "-s319", "-r", name],
        cwd=run_dir,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    seconds = time.monotonic() - started
    (run_dir / f"{name}.console").write_text(result.stdout + result.stderr)
    output = run_dir / f"{name}.out"
    text = output.read_text() if output.exists() else result.stdout + result.stderr
    summary = re.findall(r"Cloudy ends:[^\n]+", text)
    if (
        result.returncode
        or not summary
        or re.search(r"\bDISASTER\b|\bPROBLEM\b|\bwarning[s]?\b", summary[-1])
    ):
        raise ValueError(f"Cloudy {name} failed: {summary[-1:]}; inspect actual output")
    if "Failures:" in summary[-1]:
        raise ValueError(f"Cloudy {name} convergence failures: {summary[-1]}")
    stops = re.findall(r"Calculation stopped because[^\n]+", text)
    if not stops or "not converged" in stops[-1] or "zone limit" in stops[-1].lower():
        raise ValueError(f"Cloudy {name} unconverged or truncated: {stops[-1:]}")
    abundances = validate_abundances(run_dir / f"{name}.abn", parameters)
    gas_header = text.split("Gas Phase Chemical Composition", 1)[1].split("####", 1)[0]
    for element, label in (("C", "CARB"), ("N", "NITR"), ("O", "OXYG")):
        match = re.search(r"(?<!\w)" + element + r"\s*:\s*(-?\d+\.\d+)", gas_header)
        if match is None or abs(float(match[1]) - abundances[label]["declared_log_XH"]) > 0.00006:
            raise ValueError(f"exact printed gas {element}/H differs from declared composition")
        abundances[label]["actual_printed_log_XH"] = float(match[1])
    values = read_line_output(run_dir / f"{name}.lin")
    emergent = read_line_output(run_dir / f"{name}.emergent.lin")
    overview = np.loadtxt(run_dir / f"{name}.ovr", comments="#")
    return {
        "id": name,
        "parameters": parameters,
        "actual_gas_abundances": abundances,
        "runtime_seconds": seconds,
        "convergence_summary": summary[-1],
        "intrinsic_line_values": values.tolist(),
        "emergent_line_values": emergent.tolist(),
        "hydrogen_weighted_temperature_output": (run_dir / f"{name}.avr").read_text(),
        "zone_temperature_K_range": [float(overview[:, 1].min()), float(overview[:, 1].max())],
        "zones": len(overview),
        "refined_continuum_and_convergence": refinement,
        "files": [
            {"name": p.name, "bytes": p.stat().st_size, "sha256": digest(p)}
            for p in (
                input_path,
                output,
                run_dir / f"{name}.lin",
                run_dir / f"{name}.emergent.lin",
                run_dir / f"{name}.ovr",
                run_dir / f"{name}.abn",
                run_dir / f"{name}.avr",
            )
        ],
    }


def group_predictions(model: dict, attenuation_A1500: float = 0.0) -> tuple[np.ndarray, list]:
    """Foreground screen sensitivity only; composition always changes thermal solution."""
    values = np.asarray(model["intrinsic_line_values"])[:14].copy()
    waves = np.asarray([wave for _, wave in LINES[:14]])
    if attenuation_A1500 < 0:
        raise ValueError("nonnegative attenuation required")
    # Explicit power-law UV screen; not a fitted attenuation law or dust depletion.
    values *= 10 ** (-0.4 * attenuation_A1500 * (waves / 1500.0) ** -1.2)
    totals = np.asarray([values[selection].sum() for selection in SLICES])
    components = [
        (waves[selection].tolist(), (values[selection] / total).tolist())
        for selection, total in zip(SLICES, totals)
    ]
    return totals / totals[-1], components


def profile_normalization(flux: np.ndarray, covariance: np.ndarray, prediction: np.ndarray) -> dict:
    if flux.shape != (5,) or covariance.shape != (5, 5) or prediction.shape != (5,):
        raise ValueError("five complete line groups and full covariance required")
    if (
        not np.all(np.isfinite(flux))
        or not np.all(np.isfinite(prediction))
        or np.any(prediction < 0)
    ):
        raise ValueError("signed finite observations and nonnegative physical predictions required")
    chol = np.linalg.cholesky(covariance)
    y, m = np.linalg.solve(chol, flux), np.linalg.solve(chol, prediction)
    normalization = max(0.0, float(m @ y / (m @ m)))
    residual = y - normalization * m
    return {
        "common_nonnegative_normalization": normalization,
        "profiled_group_chi2": float(residual @ residual),
        "predicted_group_fluxes": (normalization * prediction).tolist(),
        "conditional_normalization_sigma": float(1 / np.linalg.norm(m)),
    }


def signed_coupling(native_directory: Path | None = None) -> tuple[np.ndarray, dict]:
    """Rebuild from verified CAL pixels or verify a compact numerical replay."""
    artifact = ROOT / "research_output/mom_cloudy_signed_coupling.npz"
    receipt_path = artifact.with_suffix(".json")
    dependencies = {
        "wavecorr_sha256": digest(ROOT / "research_output/mom_native_wavecorr.json"),
        "geometry_sha256": digest(ROOT / "research_output/mom_native_reduction.json"),
    }
    if dependencies["wavecorr_sha256"] != WAVECORR_SHA256:
        raise ValueError("native likelihood dependency changed")
    replay = load_wavecorr_replay(
        ROOT / "research_output/mom_native_wavecorr.json", corrected=False
    )
    if native_directory is not None:
        data, metadata = read_inputs(
            native_directory, ROOT / "data_sources/pilot/mom_z14_dja_v4.spec.fits"
        )
        geometry = json.loads((ROOT / "research_output/mom_native_reduction.json").read_text())[
            "geometry"
        ]
        profiles = signed_profiles(data, geometry["sigma_pixels"], geometry["offset_pixels"])
        _, operators, _ = extract_columns(data, profiles, selected_columns=replay["selected"])
        coupling = signed_response_coupling(
            data, operators, replay["selected"], geometry["sigma_pixels"], geometry["offset_pixels"]
        )
        np.savez_compressed(artifact, coupling=coupling, selected=replay["selected"])
        receipt = {
            "filename": artifact.name,
            "bytes": artifact.stat().st_size,
            "sha256": digest(artifact),
            **dependencies,
            "actual_pixel_generation": metadata,
            "scope": "Actual signed operators and source-plus-negative-nod response; no double subtraction or pathloss correction.",
        }
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        mode = "actual_pinned_CAL_pixels"
    else:
        receipt = json.loads(receipt_path.read_text())
        if any(receipt[key] != value for key, value in dependencies.items()):
            raise ValueError("signed coupling dependency receipt changed")
        if digest(artifact) != receipt["sha256"] or artifact.stat().st_size != receipt["bytes"]:
            raise ValueError("signed coupling compact replay differs from receipt")
        with np.load(artifact, allow_pickle=False) as saved:
            coupling = saved["coupling"].copy()
            if not np.array_equal(saved["selected"], replay["selected"]):
                raise ValueError("signed coupling selected columns changed")
        mode = "compact_numerical_replay_not_actual_pixel_reproduction"
    if coupling.shape != (len(replay["selected"]), 9, 9) or not np.all(np.isfinite(coupling)):
        raise ValueError("signed source-response coupling incomplete")
    return coupling, {**receipt, "execution_mode": mode}


def projected_native_fit(design: np.ndarray, chol: np.ndarray, whitened_values: np.ndarray) -> dict:
    """Fresh template covariance using one fixed full-native noise likelihood."""
    a = solve_triangular(chol, design, lower=True)
    q, r = np.linalg.qr(a, mode="reduced")
    if np.linalg.matrix_rank(r) != 7:
        raise ValueError("physical line measurement is rank deficient")
    coefficients = np.linalg.solve(r, q.T @ whitened_values)
    inverse = np.linalg.inv(r)
    covariance = inverse @ inverse.T
    residual = whitened_values - a @ coefficients
    return {
        "fluxes": coefficients[2:].tolist(),
        "flux_covariance": covariance[2:, 2:].tolist(),
        "continuum_coefficients": coefficients[:2].tolist(),
        "conditional_chi2": float(residual @ residual),
        "dof": len(whitened_values) - 7,
        "flux_units": "1e-20 erg s^-1 cm^-2",
    }


def native_likelihood(models: list[dict], native_directory: Path | None = None) -> dict:
    """Primary physical predictions through the independently validated signed Q."""
    coupling, receipt = signed_coupling(native_directory)
    wavecorr = ROOT / "research_output/mom_native_wavecorr.json"
    rw, rr, _ = read_resolution(ROOT / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
    pw, pr, _ = read_point_resolution(
        ROOT / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    alternatives = []
    for corrected in (False, True):
        replay = load_wavecorr_replay(wavecorr, corrected=corrected)
        selected = replay["selected"]
        values = replay["flux"][:, selected].T.reshape(-1)
        for noise, blocks, kernel, scale in (
            ("formal_shared", replay["covariance_blocks"], np.eye(len(selected)), 1.0),
            (
                "empirical_columns",
                replay["covariance_blocks"],
                replay["spectral_kernel"],
                replay["noise_scale_squared"],
            ),
            (
                "empirical_rows_and_columns",
                replay["spatial_covariance_blocks"],
                replay["spectral_kernel"],
                replay["noise_scale_squared"],
            ),
        ):
            covariance = transported_covariance(blocks, selected, kernel, scale, list(range(9)))
            chol = cholesky(covariance, lower=True)
            y = solve_triangular(chol, values, lower=True)
            for family, wave, resolution in (("nominal", rw, rr), ("generic_point", pw, pr)):
                records = []
                for model in models:
                    for attenuation in (0.0, 0.5, 1.0):
                        prediction, components = group_predictions(model, attenuation)
                        direct = response(replay["data"], selected, wave, resolution, components)
                        fit = projected_native_fit(apply_signed_response(direct, coupling), chol, y)
                        profile = profile_normalization(
                            np.asarray(fit["fluxes"]),
                            np.asarray(fit["flux_covariance"]),
                            prediction,
                        )
                        records.append(
                            {
                                "model_id": model["id"],
                                "A1500_mag": attenuation,
                                "parameters": model["parameters"],
                                "prediction_relative_CIII": prediction.tolist(),
                                "component_weights": components,
                                "native_fit": fit,
                                **profile,
                                "full_native_profiled_chi2": fit["conditional_chi2"]
                                + profile["profiled_group_chi2"],
                                "constrained_native_dof": len(values) - 3,
                            }
                        )
                best = min(records, key=lambda item: item["full_native_profiled_chi2"])
                ordinary = min(
                    (
                        item
                        for item in records
                        if item["parameters"]["log_NC_relative_minus060"] == 0
                    ),
                    key=lambda item: item["full_native_profiled_chi2"],
                )
                alternatives.append(
                    {
                        "wavelength_hypothesis": replay["wavelength_hypothesis"],
                        "noise": noise,
                        "resolution": family,
                        "records": records,
                        "best": best,
                        "best_ordinary": ordinary,
                        "ordinary_minus_global_minimum_chi2": ordinary["full_native_profiled_chi2"]
                        - best["full_native_profiled_chi2"],
                    }
                )
    return {
        "alternatives": alternatives,
        "signed_coupling": receipt,
        "spectral_response_contract": "Signed source-plus-ghost transport v1",
        "alternatives_pooled": False,
        "model_counts_are_probabilities": False,
        "native_group_covariance_and_template_refitted_per_model": True,
        "interpretation": "Conditional profiled full-native likelihood. Original wavelengths and DUMMY sensitivity stay separate; unknown source LSF, shared calibration and ionizing spectrum preclude an elemental abundance posterior.",
    }


def legacy_native_likelihood(models: list[dict]) -> dict:
    wavecorr = ROOT / "research_output/mom_native_wavecorr.json"
    if digest(wavecorr) != WAVECORR_SHA256:
        raise ValueError("native baseline report changed")
    rw, rr, _ = read_resolution(ROOT / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
    pw, pr, _ = read_point_resolution(
        ROOT / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    alternatives = []
    for corrected in (False, True):
        replay = load_wavecorr_replay(wavecorr, corrected=corrected)
        for resolution_name, resolution_wave, resolution in (
            ("nominal", rw, rr),
            ("generic_point", pw, pr),
        ):
            for noise, blocks, kernel, scale in (
                ("formal_shared", replay["covariance_blocks"], None, 1.0),
                (
                    "empirical_columns",
                    replay["covariance_blocks"],
                    replay["spectral_kernel"],
                    replay["noise_scale_squared"],
                ),
                (
                    "empirical_rows_and_columns",
                    replay["spatial_covariance_blocks"],
                    replay["spectral_kernel"],
                    replay["noise_scale_squared"],
                ),
            ):
                records = []
                for model in models:
                    for attenuation in (0.0, 0.5, 1.0):
                        prediction, components = group_predictions(model, attenuation)
                        fit = fit_native(
                            replay["data"],
                            replay["flux"],
                            blocks,
                            replay["selected"],
                            resolution_wave,
                            resolution,
                            kernel=kernel,
                            noise_scale=scale,
                            components=components,
                        )
                        profile = profile_normalization(
                            np.asarray(fit["fluxes"]),
                            np.asarray(fit["flux_covariance"]),
                            prediction,
                        )
                        records.append(
                            {
                                "model_id": model["id"],
                                "A1500_mag": attenuation,
                                "parameters": model["parameters"],
                                "prediction_relative_CIII": prediction.tolist(),
                                "component_weights": components,
                                "native_fit": fit,
                                **profile,
                                "full_native_profiled_chi2": fit["conditional_chi2"]
                                + profile["profiled_group_chi2"],
                            }
                        )
                ranked = sorted(records, key=lambda row: row["full_native_profiled_chi2"])
                ordinary = min(
                    (row for row in ranked if row["parameters"]["log_NC_relative_minus060"] == 0),
                    key=lambda row: row["full_native_profiled_chi2"],
                )
                alternatives.append(
                    {
                        "wavelength_hypothesis": replay["wavelength_hypothesis"],
                        "resolution": resolution_name,
                        "noise": noise,
                        "records": records,
                        "best": ranked[0],
                        "best_ordinary": ordinary,
                        "ordinary_minus_global_minimum_chi2": ordinary["full_native_profiled_chi2"]
                        - ranked[0]["full_native_profiled_chi2"],
                    }
                )
    return {
        "alternatives": alternatives,
        "input_wavecorr_sha256": WAVECORR_SHA256,
        "alternatives_pooled": False,
        "model_counts_are_probabilities": False,
        "native_group_covariance_and_template_refitted_per_model": True,
        "interpretation": "Historical positive-only measurement control. Signed nod injection demonstrates bias; do not use as the primary abundance likelihood.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cloudy-directory", type=Path)
    parser.add_argument("--run-directory", type=Path)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "research_output/mom_cloudy_pilot.json"
    )
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--fit-native", action="store_true")
    parser.add_argument("--native-directory", type=Path)
    parser.add_argument("--legacy-control", action="store_true")
    parser.add_argument("--replay-models", type=Path)
    parser.add_argument("--resume-models", type=Path)
    args = parser.parse_args()
    if args.replay_models:
        result = json.loads(args.replay_models.read_text())
    else:
        if args.cloudy_directory is None or args.run_directory is None or not 1 <= args.limit <= 20:
            parser.error("execution requires bounded Cloudy/run directories and limit1..20")
        executable = args.executable or args.cloudy_directory / "c23.01/source/sys_pilot/cloudy.exe"
        if not 1 <= args.workers <= 4:
            parser.error("bounded workers1..4 required")
        models = []
        if args.resume_models:
            models = json.loads(args.resume_models.read_text())["models"]
            for index, model in enumerate(models):
                if (
                    model["parameters"] != pilot_parameters()[index]
                    or model["id"] != f"model{index:03}"
                ):
                    raise ValueError("resume model identity differs from declared pilot")
                for item in model["files"]:
                    path = args.run_directory / item["name"]
                    if digest(path) != item["sha256"]:
                        raise ValueError("actual resume model file differs from frozen output")
                validate_abundances(args.run_directory / f"{model['id']}.abn", model["parameters"])
                if (args.run_directory / f"{model['id']}.in").read_text() != input_text(
                    model["parameters"], model["id"]
                ):
                    raise ValueError("resume input differs from corrected declared composition")
        receipt = verify(args.cloudy_directory / "c23.01.tar.gz")

        def calculate(item):
            index, parameters = item
            return execute_model(executable, args.run_directory, parameters, f"model{index:03}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
            for model in executor.map(
                calculate, list(enumerate(pilot_parameters()[: args.limit]))[len(models) :]
            ):
                models.append(model)
                print(
                    model["id"], model["runtime_seconds"], model["convergence_summary"], flush=True
                )
                args.output.write_text(json.dumps({"models": models}, indent=2) + "\n")
        result = {
            "schema_version": 1,
            "archive": receipt,
            "cloudy_release": "C23.01",
            "random_seed_hex": "319",
            "executable_sha256": digest(executable),
            "models": models,
            "line_contract_version": 2,
            "lines": LINES,
            "line_wavelength_medium": ["vacuum" if wave < 2000 else "air" for _, wave in LINES],
            "ordinary_reference_log_NC": -0.60,
            "reference_log_CO": -0.37,
            "dust_depletion": False,
            "complete_thermal_solution_per_composition": True,
            "intrinsic_line_unit": "erg s^-1 cm^-2; Cloudy intensity geometry",
            "solar_metal_pattern": "GASS10 with explicit gas-phase C/N/O overrides",
            "sphere_inner_radius_cm": 1e19,
            "constant_hydrogen_density": True,
            "elemental_abundance_identified": False,
            "interpretation": "Independent composition-aware HII pilot; blackbody controls are assumptions, not measured ionizing spectrum or full abundance posterior.",
        }
    if args.fit_native:
        result["native_likelihood"] = native_likelihood(result["models"], args.native_directory)
    if args.legacy_control:
        result["legacy_positive_only_control"] = legacy_native_likelihood(result["models"])
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
