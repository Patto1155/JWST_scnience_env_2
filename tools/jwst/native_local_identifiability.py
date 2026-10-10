"""Predeclared twelve-fit v3 signed-row sensitivity and calibration counterexamples."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from scipy.linalg import cholesky, solve_triangular

from tools.jwst.line_sensitivity import C_KMS, line_matrix
from tools.jwst.native_measurement_validation import (
    held_out_prediction,
    serial_fit,
    solve_measurement,
    transported_covariance,
)
from tools.jwst.native_rate_noise import load_rate_noise_replay, rate_signed_response
from tools.jwst.native_reduction import ROOT, gaussian_profile, read_inputs, sha256
from tools.jwst.native_row_response import complete_row_wavelength
from tools.jwst.point_resolution import read_point_resolution

SCENARIOS = (
    ("baseline", 14.44, 0.0, 1),
    ("redshift_low", 14.42, 0.0, 1),
    ("redshift_high", 14.46, 0.0, 1),
    ("width_300", 14.44, 300.0, 1),
    ("width_1000", 14.44, 1000.0, 1),
    ("quadratic_continuum", 14.44, 0.0, 2),
)


def effective_resolution(r: np.ndarray, intrinsic_fwhm: float) -> np.ndarray:
    """Equivalent zero-intrinsic Gaussian LSF; width is FWHM km/s."""
    return 1 / np.hypot(1 / np.asarray(r, dtype=float), intrinsic_fwhm / C_KMS)


def source_design(
    data,
    rw,
    resolution,
    components,
    geometry,
    *,
    redshift=14.44,
    intrinsic_fwhm=0.0,
    continuum_order=1,
    lsf_scale=1.0,
):
    """Full row bins with physical multiplets; calibrated mean, no pixel resubtraction."""
    result = np.zeros((len(data), *data[0]["wave"].shape, continuum_order + 6))
    for i, d in enumerate(data):
        profile = gaussian_profile(
            d["trace_seed"] + geometry["offset_pixels"],
            geometry["sigma_pixels"],
            d["wave"].shape[0],
        )
        profile *= np.where(d["good"], d["point_pathloss"], 0)
        for row in range(d["wave"].shape[0]):
            if not np.any(profile[row]):
                continue
            wave = complete_row_wavelength(d["wave"][row])
            continuum = (
                np.polynomial.legendre.legvander((wave - 2.675) / 0.525, continuum_order) / 100
            )
            line = (
                line_matrix(
                    wave,
                    rw,
                    resolution,
                    components=components,
                    redshift=redshift,
                    intrinsic_fwhm=intrinsic_fwhm,
                    lsf_scale=lsf_scale,
                )
                / (C_KMS / wave**2)[:, None]
            )
            result[i, row] = np.column_stack([continuum, line]) * profile[row, :, None]
    return result


def projected_diagnostics(design, covariance, changes):
    """Plug-in model-change vectors after projecting fitted nuisance amplitudes."""
    c = cholesky(covariance, lower=True)
    q, _ = np.linalg.qr(solve_triangular(c, design, lower=True), mode="reduced")
    whitened = solve_triangular(c, np.column_stack(list(changes.values())), lower=True)
    projected = whitened - q @ (q.T @ whitened)
    norms = np.linalg.norm(projected, axis=0)
    gram = projected.T @ projected
    cosine = np.divide(
        gram,
        norms[:, None] * norms[None, :],
        out=np.zeros_like(gram),
        where=norms[:, None] * norms[None, :] > 0,
    )
    return {
        "directions": list(changes),
        "projected_plugin_SNR": norms.tolist(),
        "projected_cosines": cosine.tolist(),
        "projected_singular_values": np.linalg.svd(projected, compute_uv=False).tolist(),
        "interpretation": (
            "amplitude-conditioned finite contrasts with declared scales; "
            "not invariant Fisher information, power or confidence"
        ),
    }


def run(native_dir: Path) -> dict:
    started = time.monotonic()
    report_path = ROOT / "research_output/mom_native_rate_noise.json"
    reference = json.loads(report_path.read_text())
    for name, expected in reference["inputs_sha256"].items():
        if sha256(ROOT / name) != expected:
            raise ValueError("v3 dependency hash changed")
    saved = load_rate_noise_replay(report_path, empirical=True)
    with np.load(
        report_path.parent / reference["compact_replay"]["filename"], allow_pickle=False
    ) as a:
        gains, operators = a["calibration_gain"].copy(), a["operators"].copy()
    data, metadata = read_inputs(native_dir, ROOT / "data_sources/pilot/mom_z14_dja_v4.spec.fits")
    geometry = json.loads((ROOT / "research_output/mom_native_reduction.json").read_text())[
        "geometry"
    ]
    atomic = json.loads((ROOT / "research_output/mom_atomic_grid_niv_doublet_v2.json").read_text())
    templates = json.loads(
        (ROOT / "research_output/mom_multiplet_components_niv_doublet_v2.json").read_text()
    )
    index = next(
        i
        for i, x in enumerate(atomic["records"])
        if x["temperature_K"] == 20000 and x["electron_density_cm3"] == 1000
    )
    emissivity = atomic["records"][index]["emissivity_erg_cm3_s"]
    components = [
        (x["vacuum_wavelengths_A"], x["normalized_weights"])
        for x in templates["records"][index]["components"]
    ]
    rw, r, _ = read_point_resolution(
        ROOT / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    selected = saved["selected"]
    covariance = transported_covariance(
        saved["covariance_blocks"],
        selected,
        saved["spectral_kernel"],
        saved["noise_scale_squared"],
        list(range(9)),
    )
    values = saved["flux"].T.reshape(-1)

    def mean(*, local_rw=rw, local_r=r, local_components=components, **kwargs):
        positive = source_design(data, local_rw, local_r, local_components, geometry, **kwargs)
        return rate_signed_response(data, positive, gains, operators, selected)

    designs, solutions, records = {}, {}, []
    for name, z, width, order in SCENARIOS:
        design = mean(redshift=z, intrinsic_fwhm=width, continuum_order=order)
        solution = solve_measurement(design, covariance, values)
        designs[name], solutions[name] = design, solution
        records.append(
            {
                "scenario": name,
                "redshift": z,
                "intrinsic_FWHM_km_s": width,
                "continuum_order": order,
                "fit": serial_fit(solution, emissivity, order),
            }
        )
        if time.monotonic() - started > 180:
            raise RuntimeError("preregistered computation limit exceeded")
    golden = next(
        x["fit"]
        for x in reference["fits"]
        if x["noise_contract"] == "target_only_RATE_control_transport_v3"
        and x["wavelength_hypothesis"] == "original_native"
        and x["resolution_family"] == "generic_point"
    )
    closure = float(np.max(np.abs(np.asarray(records[0]["fit"]["fluxes"]) - golden["fluxes"])))
    if closure > 1e-8:
        raise ValueError("fresh baseline differs from frozen v3 signed row contract")
    heldouts = []
    for group in sorted({d["group"] for d in data}):
        train_members = [i for i, d in enumerate(data) if d["group"] != group]
        test_members = [i for i, d in enumerate(data) if d["group"] == group]
        train_index = np.array([c * 9 + i for c in range(len(selected)) for i in train_members])
        test_index = np.array([c * 9 + i for c in range(len(selected)) for i in test_members])
        for name in ("baseline", "width_1000"):
            design = designs[name]
            train_c = covariance[np.ix_(train_index, train_index)]
            solution = solve_measurement(design[train_index], train_c, values[train_index])
            result = held_out_prediction(
                {"continuum_order": 1, "solution": solution},
                {
                    "design": design[test_index],
                    "covariance": covariance[np.ix_(test_index, test_index)],
                    "values": values[test_index],
                },
            )
            heldouts.append({"scenario": name, "held_out_RATE_group": group, "prediction": result})
    centers = np.concatenate([np.asarray(rest) * 1e-4 * 15.44 for rest, _ in components])
    grid = np.unique(np.concatenate([rw, centers]))
    counterexamples = []
    for width in (300.0, 1000.0):
        equivalent_r = effective_resolution(np.interp(grid, rw, r), width)
        equivalent = mean(local_rw=grid, local_r=equivalent_r)
        error = float(np.max(np.abs(equivalent - designs[f"width_{int(width)}"])))
        if error > 1e-10:
            raise ValueError("Gaussian source-LSF equivalence failed")
        counterexamples.append(
            {
                "intrinsic_FWHM_km_s": width,
                "zero_intrinsic_unknown_LSF_max_response_difference": error,
                "effective_resolution_at_components": effective_resolution(
                    np.interp(centers, rw, r), width
                ).tolist(),
            }
        )
    centroid_checks = []
    for z in (14.42, 14.46):
        epsilon = (1 + z) / 15.44 - 1
        # This changes assigned centroids only, not physical atomic identities or detector WAVE.
        assigned = [(np.asarray(rest) * (1 + epsilon), weight) for rest, weight in components]
        equivalent = mean(local_components=assigned)
        target = designs["redshift_low" if z < 14.44 else "redshift_high"]
        error = float(np.max(np.abs(equivalent - target)))
        if error > 1e-10:
            raise ValueError("centroid calibration/redshift equivalence failed")
        centroid_checks.append(
            {
                "redshift": z,
                "fractional_centroid_calibration": epsilon,
                "maximum_response_difference": error,
            }
        )
    coefficients = solutions["baseline"]["coefficients"]
    changes = {
        "redshift_delta_0.02": (designs["redshift_high"] - designs["redshift_low"])
        @ coefficients
        / 2,
        "broadening_finite_u_0.09": (designs["width_300"] - designs["baseline"]) @ coefficients,
        "LSF_scale_delta_0.01": (mean(lsf_scale=1.01) - mean(lsf_scale=0.99)) @ coefficients / 2,
        "quadratic_continuum_unit_coefficient": designs["quadratic_continuum"][:, 2],
    }
    elapsed = time.monotonic() - started
    if elapsed > 180:
        raise RuntimeError("preregistered computation limit exceeded")
    return {
        "schema_version": 1,
        "noise_contract_version": 3,
        "question": (
            "Can local spectral alternatives separate line measurement from unknown calibration?"
        ),
        "data_scope": (
            "actual nine CAL wavelength/profile inputs; "
            "hash-verified RATE v3 compact covariance and gain operators"
        ),
        "inputs_sha256": {
            "research_output/mom_native_rate_noise.json": sha256(report_path),
            **reference["inputs_sha256"],
        },
        "native_metadata": metadata,
        "baseline_replay_max_flux_difference": closure,
        "fits": records,
        "held_out_predictions": heldouts,
        "width_LSF_counterexamples": counterexamples,
        "centroid_redshift_counterexamples": centroid_checks,
        "centroid_convention": (
            "assigned centers multiplied by 1+epsilon; fixed detector "
            "WAVE/Fnu bins; LSF evaluated at assigned center"
        ),
        "local_plugin_diagnostics": projected_diagnostics(designs["baseline"], covariance, changes),
        "fitted_comparisons": 12,
        "new_download_bytes": 0,
        "runtime_seconds": elapsed,
        "absolute_redshift_or_intrinsic_width_identified": False,
        "empirical_coverage_or_power_established": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--native-dir", type=Path, required=True)
    p.add_argument(
        "--output",
        type=Path,
        default=ROOT / "research_output/mom_native_local_identifiability.json",
    )
    a = p.parse_args()
    result = run(a.native_dir)
    a.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {"fits": result["fitted_comparisons"], "runtime_seconds": result["runtime_seconds"]}
        )
    )


if __name__ == "__main__":
    main()
