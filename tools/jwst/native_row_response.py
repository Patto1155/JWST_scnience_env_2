"""Bounded row-resolved signed spectral response, preserving scalar contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.special import ndtr

from tools.jwst.line_sensitivity import line_matrix, read_resolution
from tools.jwst.native_measurement_validation import (
    apply_signed_response,
    held_out_prediction,
    response,
    serial_fit,
    signed_response_coupling,
    solve_measurement,
    transported_covariance,
)
from tools.jwst.native_reduction import (
    ROOT,
    extract_columns,
    gaussian_profile,
    mixing_matrix,
    read_inputs,
    sha256,
    signed_profiles,
)
from tools.jwst.native_wavecorr import load_wavecorr_replay
from tools.jwst.point_resolution import read_point_resolution

SIGNED_ARTIFACT_SHA256 = "c7e31e81a6bb6b9b4b81bf48661ccfa28475be5cf6b226f85113c78fe73074ca"


def complete_row_wavelength(wave: np.ndarray) -> np.ndarray:
    """Complete model edges on full native grid, never on science-quality subset."""
    wave = np.asarray(wave, dtype=float).copy()
    finite = np.isfinite(wave) & (wave > 0)
    where = np.flatnonzero(finite)
    if len(where) < 3:
        raise ValueError("row has insufficient calibrated wavelength coverage")
    wave = np.interp(np.arange(len(wave)), where, wave[finite])
    left = (wave[where[1]] - wave[where[0]]) / (where[1] - where[0])
    right = (wave[where[-1]] - wave[where[-2]]) / (where[-1] - where[-2])
    wave[: where[0]] = wave[where[0]] + (np.arange(where[0]) - where[0]) * left
    wave[where[-1] + 1 :] = (
        wave[where[-1]] + (np.arange(where[-1] + 1, len(wave)) - where[-1]) * right
    )
    if np.any(np.diff(wave) <= 0) or np.any(wave <= 0):
        raise ValueError("row wavelength grid must be positive and strictly increasing")
    return wave


def row_source_design(
    data: list[dict], rw: np.ndarray, r: np.ndarray, components: list, sigma: float, offset: float
) -> np.ndarray:
    """Raw positive-source pixel response in the common pre-point calibration."""
    result = np.zeros((len(data), *data[0]["wave"].shape, 7))
    for i, d in enumerate(data):
        positive = gaussian_profile(d["trace_seed"] + offset, sigma, d["wave"].shape[0])
        positive *= np.where(d["good"], d["point_pathloss"], 0)
        for row in range(d["wave"].shape[0]):
            if not np.any(positive[row]):
                continue
            wave = complete_row_wavelength(d["wave"][row])
            continuum = np.polynomial.legendre.legvander((wave - 2.675) / 0.525, 1) / 100
            line = (
                line_matrix(wave, rw, r, components=components) / (2.99792458e5 / wave**2)[:, None]
            )
            result[i, row] = np.column_stack([continuum, line]) * positive[row, :, None]
    return result


def signed_pixel_response(
    data: list[dict], positive: np.ndarray, operators: np.ndarray, selected: np.ndarray
) -> np.ndarray:
    """Explicit donor mixing, then frozen extraction weights, before spectral fit."""
    mixed = np.zeros_like(positive)
    for group in sorted({d["group"] for d in data}):
        members = [i for i, d in enumerate(data) if d["group"] == group]
        mixed[members] = np.einsum("ij,jrck->irck", mixing_matrix(), positive[members])
    measured = np.sum(mixed * operators[:, :, :, None], axis=1)
    return measured[:, selected].transpose(1, 0, 2).reshape(len(selected) * len(data), -1)


def conditional_coverage_from_bias(bias: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    """Exact marginal95% coverage for specified Gaussian error and fixed bias."""
    return ndtr(1.959963984540054 - bias / sigma) - ndtr(-1.959963984540054 - bias / sigma)


def run(native_dir: Path) -> dict:
    signed_path = ROOT / "research_output/mom_native_measurement_validation.json"
    if sha256(signed_path) != SIGNED_ARTIFACT_SHA256:
        raise ValueError("merged signed-response artifact differs from frozen dependency")
    previous = json.loads(signed_path.read_text())
    for name, expected in previous["inputs_sha256"].items():
        if sha256(ROOT / name) != expected:
            raise ValueError("physical/wavelength input differs from merged dependency")
    atomic = json.loads((ROOT / "research_output/mom_atomic_grid_niv_doublet_v2.json").read_text())
    templates = json.loads(
        (ROOT / "research_output/mom_multiplet_components_niv_doublet_v2.json").read_text()
    )
    index = next(
        i
        for i, c in enumerate(atomic["records"])
        if c["temperature_K"] == 20000 and c["electron_density_cm3"] == 1000
    )
    emissivity = atomic["records"][index]["emissivity_erg_cm3_s"]
    components = [
        (g["vacuum_wavelengths_A"], g["normalized_weights"])
        for g in templates["records"][index]["components"]
    ]
    baseline = json.loads((ROOT / "research_output/mom_native_reduction.json").read_text())
    geometry = baseline["geometry"]
    data, metadata = read_inputs(native_dir, ROOT / "data_sources/pilot/mom_z14_dja_v4.spec.fits")
    for d in data:
        d["trace_refined"] = d["trace_seed"] + geometry["offset_pixels"]
        d["sigma_refined"] = geometry["sigma_pixels"]
    rw, rr, _ = read_resolution(ROOT / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
    pw, pr, _ = read_point_resolution(
        ROOT / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    wpath = ROOT / "research_output/mom_native_wavecorr.json"
    original = load_wavecorr_replay(wpath, corrected=False)
    selected = original["selected"]
    profiles = signed_profiles(data, geometry["sigma_pixels"], geometry["offset_pixels"])
    flux, operators, _ = extract_columns(data, profiles, selected_columns=selected)
    if not np.allclose(flux[:, selected], original["flux"][:, selected], rtol=0, atol=1e-12):
        raise ValueError("actual native extraction does not match merged amplitudes")
    coupling = signed_response_coupling(
        data, operators, selected, geometry["sigma_pixels"], geometry["offset_pixels"]
    )
    records, controls, held_out = [], [], []
    truth = np.array([2.0, -0.5, 20.0, 15.0, 15.0, 5.0, 12.0])
    for corrected in (False, True):
        saved = load_wavecorr_replay(wpath, corrected=corrected)
        local = [{**d, "wave": w["wave"]} for d, w in zip(data, saved["data"])]
        covariance = transported_covariance(
            saved["spatial_covariance_blocks"],
            selected,
            saved["spectral_kernel"],
            saved["noise_scale_squared"],
            list(range(9)),
        )
        values = saved["flux"][:, selected].T.reshape(-1)
        for family, w, r in (("nominal", rw, rr), ("generic_point", pw, pr)):
            scalar = apply_signed_response(
                response(saved["data"], selected, w, r, components), coupling
            )
            scalar_solution = solve_measurement(scalar, covariance, values)
            old = next(
                c
                for c in previous["signed_forward_corrected_baseline_fits"]
                if c["resolution_family"] == family
                and c["wavelength_hypothesis"] == saved["wavelength_hypothesis"]
            )["fit"]
            error = float(np.max(np.abs(scalar_solution["coefficients"][2:] - old["fluxes"])))
            if error > 1e-9:
                raise ValueError("scalar signed-response replay differs from merged baseline")
            positive = row_source_design(
                local, w, r, components, geometry["sigma_pixels"], geometry["offset_pixels"]
            )
            row_design = signed_pixel_response(local, positive, operators, selected)
            solution = solve_measurement(row_design, covariance, values)
            fit = serial_fit(solution, emissivity, 1)
            records.append(
                {
                    "resolution_family": family,
                    "wavelength_hypothesis": saved["wavelength_hypothesis"],
                    "fit": fit,
                    "scalar_reference_fit": old,
                    "scalar_flux_replay_max_difference": error,
                    "flux_difference_from_scalar": (
                        np.array(fit["fluxes"]) - old["fluxes"]
                    ).tolist(),
                    "redshift_fixed": 14.44,
                    "intrinsic_width_fixed_kms": 0,
                    "continuum_order": 1,
                }
            )
            # Independent image contraction, separate from constructing a response matrix.
            source = np.einsum("irck,k->irc", positive, truth)
            difference = np.zeros_like(source)
            for group in sorted({d["group"] for d in local}):
                members = [i for i, d in enumerate(local) if d["group"] == group]
                for i in members:
                    difference[i] = source[i] - sum(source[j] for j in members if j != i) / 2
            injected = np.sum(difference * operators, axis=1)[:, selected].T.reshape(-1)
            recovered = solution["estimator"] @ injected
            scalar_recovered = scalar_solution["estimator"] @ injected
            bias = scalar_recovered[2:] - truth[2:]
            sigma = np.sqrt(np.diag(scalar_solution["covariance"]))[2:]
            controls.append(
                {
                    "resolution_family": family,
                    "wavelength_hypothesis": saved["wavelength_hypothesis"],
                    "injected_truth_fluxes": truth[2:].tolist(),
                    "row_recovered_fluxes": recovered[2:].tolist(),
                    "scalar_recovered_fluxes": scalar_recovered[2:].tolist(),
                    "scalar_bias_fluxes": bias.tolist(),
                    "scalar_bias_over_conditional_sigma": (bias / sigma).tolist(),
                    "assumed_gaussian_scalar_95_coverage": conditional_coverage_from_bias(
                        bias, sigma
                    ).tolist(),
                    "image_vs_row_design_maximum_difference": float(
                        np.max(np.abs(injected - row_design @ truth))
                    ),
                    "empirical_interval_coverage_established": False,
                }
            )
            if not corrected and family == "generic_point":
                grid = row_design.reshape(len(selected), 9, -1)
                for group, test_members in (
                    ("03", [0, 1, 2]),
                    ("05", [3, 4, 5]),
                    ("07", [6, 7, 8]),
                ):
                    train_members = [i for i in range(9) if i not in test_members]
                    train, test = {"continuum_order": 1}, {}
                    for target, members in ((train, train_members), (test, test_members)):
                        target["design"] = grid[:, members].reshape(
                            len(selected) * len(members), -1
                        )
                        target["covariance"] = transported_covariance(
                            saved["spatial_covariance_blocks"],
                            selected,
                            saved["spectral_kernel"],
                            saved["noise_scale_squared"],
                            members,
                        )
                        target["values"] = saved["flux"][members][:, selected].T.reshape(-1)
                        target["solution"] = solve_measurement(
                            target["design"], target["covariance"], target["values"]
                        )
                    held_out.append(
                        {
                            "held_out_group": group,
                            "prediction": held_out_prediction(train, test),
                            "training_fit": serial_fit(train["solution"], emissivity, 1),
                            "held_out_fit": serial_fit(test["solution"], emissivity, 1),
                        }
                    )
    reference = next(
        a
        for a in records
        if a["resolution_family"] == "generic_point"
        and a["wavelength_hypothesis"] == "original_native"
    )
    budget = {
        "reference_NIV_row_minus_scalar_flux": reference["flux_difference_from_scalar"][0],
        "reference_NIV_row_conditional_sigma": float(
            np.sqrt(reference["fit"]["flux_covariance"][0][0])
        ),
        "maximum_all_family_flux_change_over_row_conditional_sigma": max(
            float(
                np.max(
                    np.abs(a["flux_difference_from_scalar"])
                    / np.sqrt(np.diag(a["fit"]["flux_covariance"]))
                )
            )
            for a in records
        ),
        "maximum_declared_scalar_injection_bias_over_conditional_sigma": max(
            max(np.abs(c["scalar_bias_over_conditional_sigma"])) for c in controls
        ),
        "row_vs_scalar_range_is_empirical_calibration_interval": False,
        "unbounded_by_this_test": [
            "source-specific instrumental LSF and along-dispersion illumination",
            "absolute wavelength calibration",
            "common intergroup source/systematic calibration",
            "unknown ion fractions and radiative transfer",
        ],
    }
    return {
        "schema_version": 1,
        "merged_signed_dependency": "f0a9fd8ce6e2e3dbe6225bbd1cdfca2a0754b4b9",
        "inputs_sha256": {
            "signed_measurement": sha256(signed_path),
            "wavecorr": sha256(wpath),
            "atomic": sha256(ROOT / "research_output/mom_atomic_grid_niv_doublet_v2.json"),
            "components": sha256(
                ROOT / "research_output/mom_multiplet_components_niv_doublet_v2.json"
            ),
            "module": sha256(Path(__file__)),
        },
        "actual_native_input_hashes": previous["actual_pixel_input_hashes"],
        "actual_pixel_metadata": metadata,
        "row_resolved_fits": records,
        "row_source_injection_controls": controls,
        "held_out_rate_group_predictions": held_out,
        "uncertainty_budget": budget,
        "new_download_bytes": 0,
        "native_source_specific_LSF_empirically_calibrated": False,
        "absolute_wavelength_assignment_empirically_calibrated": False,
        "source_Poisson_recomputed": False,
        "elemental_abundance_identified": False,
        "alternative_likelihoods_pooled": False,
        "interpretation": (
            "Row-resolved extended-source WAVELENGTH mapping plus assumed point profile/pathloss "
            "and generic GaussianLSF; revised conditional independent native alternatives, "
            "not exact author reproduction or empirical source calibration."
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--native-dir", type=Path, required=True)
    p.add_argument(
        "--output", type=Path, default=ROOT / "research_output/mom_native_row_response.json"
    )
    args = p.parse_args()
    result = run(args.native_dir)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "fits": len(result["row_resolved_fits"]),
                "controls": len(result["row_source_injection_controls"]),
            }
        )
    )


if __name__ == "__main__":
    main()
