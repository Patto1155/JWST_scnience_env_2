"""Independent normal-equation336-fit composition and signed Fieller audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.linalg import block_diag

from discovery.continuation_review import digest
from discovery.continuation_wavecorr_review import bin_design, normal_fit, source_waves
from tools.jwst.line_sensitivity import read_resolution
from tools.jwst.point_resolution import read_point_resolution


def audit(root: Path):
    path = root / "research_output/mom_composed_spectral_refit.json"
    saved = json.loads(path.read_text())
    wave_path = root / "research_output/mom_native_wavecorr.json"
    wave_report = json.loads(wave_path.read_text())
    compact = wave_path.parent / wave_report["compact_replay"]["filename"]
    atomic_path = root / "research_output/mom_atomic_grid_niv_doublet_v2.json"
    component_path = root / "research_output/mom_multiplet_components_niv_doublet_v2.json"
    for source, pin in [
        (wave_path, saved["input_wavecorr_report_sha256"]),
        (compact, saved["compact_replay_receipt"]["sha256"]),
        (atomic_path, saved["atomic_v2_sha256"]),
        (component_path, saved["components_v2_sha256"]),
        (
            root / "research_output/mom_native_niv_doublet_refit_v2.json",
            saved["previous_original_quartet_v2_sha256"],
        ),
    ]:
        if digest(source) != pin:
            raise ValueError("composed frozen input receipt differs")
    atomic = json.loads(atomic_path.read_text())
    components = json.loads(component_path.read_text())
    with np.load(compact, allow_pickle=False) as z:
        arrays = {key: z[key].copy() for key in z.files}
    hypotheses = ["original_native", "pinned_toy_prediction"]
    resolutions = ["nominal", "generic_point"]
    noises = ["formal_shared", "empirical_columns", "empirical_rows_and_columns"]
    expected = [(h, r, n) for h in hypotheses for r in resolutions for n in noises]
    actual = [
        (a["wavelength_hypothesis"], a["resolution_family"], a["noise_family"])
        for a in saved["alternatives"]
    ]
    if actual != expected or saved["line_contract_version"] != 2:
        raise ValueError("exact twelve ordered version2 alternatives required")
    inverse = {}
    for noise in noises:
        blocks = arrays[
            "spatial_covariance_blocks"
            if noise.endswith("rows_and_columns")
            else "covariance_blocks"
        ]
        factor = block_diag(*[np.linalg.cholesky(block) for block in blocks])
        kernel = np.eye(70) if noise == "formal_shared" else arrays["spectral_kernel"]
        scale = 1 if noise == "formal_shared" else arrays["noise_scale_squared"][0]
        inverse[noise] = np.linalg.inv(factor @ np.kron(kernel, np.eye(9)) @ factor.T * scale)
    values = arrays["flux"].T.ravel()
    errors, ionic_errors, summaries = [], [], []
    for alternative in saved["alternatives"]:
        corrected = alternative["wavelength_hypothesis"] == "pinned_toy_prediction"
        waves = source_waves(
            arrays["corrected_wave" if corrected else "native_wave"],
            arrays["native_good"],
            arrays["trace"],
            arrays["sigma"][0],
        )
        rw, rr, _ = (
            read_point_resolution(root / "data_sources/followup/unite_point_prism_resolution.csv")
            if alternative["resolution_family"] == "generic_point"
            else read_resolution(root / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
        )
        accepted: np.ndarray = np.zeros(2, dtype=int)
        for template, cell, record in zip(
            components["records"], atomic["records"], alternative["records"], strict=True
        ):
            if (record["temperature_K"], record["electron_density_cm3"]) != (
                cell["temperature_K"],
                cell["electron_density_cm3"],
            ) or record["fit"].get("line_contract_version") != 2:
                raise ValueError("matching per-cell total-doublet contracts required")
            groups = [
                (g["vacuum_wavelengths_A"], g["normalized_weights"]) for g in template["components"]
            ]
            if groups[0][0] != [1483.321, 1486.496]:
                raise ValueError("physical total-doublet components required")
            design = bin_design(waves, arrays["selected_columns"], rw, rr, groups)
            precision = inverse[alternative["noise_family"]]
            errors.append(normal_fit(design, precision, values, record["fit"]))
            covariance = np.linalg.inv(design.T @ precision @ design)
            coefficient = covariance @ (design.T @ precision @ values)
            epsilon = cell["emissivity_erg_cm3_s"]
            response = np.array(
                [
                    [epsilon["CIII"] / epsilon["NIV"], 0, 0, epsilon["CIII"] / epsilon["NIII"], 0],
                    [0, epsilon["CIII"] / epsilon["CIV"], 0, 0, 1],
                ]
            )
            x = response @ coefficient[2:]
            c = response @ covariance[2:, 2:] @ response.T
            ionic = record["observed_two_stage_ionic_N_over_C"]
            delta = float(abs(x[0] / x[1] - ionic["value"]))
            ionic_errors.append(delta)
            if delta > 1e-9 or not np.allclose(
                c, ionic["scaled_covariance"], rtol=1e-10, atol=1e-10
            ):
                raise ValueError("independent fresh ionic projection differs")
            q = 3.84145882069
            quadratic = [
                x[1] ** 2 - q * c[1, 1],
                -2 * (x[0] * x[1] - q * c[0, 1]),
                x[0] ** 2 - q * c[0, 0],
            ]
            roots = np.sort(np.roots(quadratic))
            fieller = ionic["conditional_gaussian_95_fieller_set"]
            if (
                quadratic[0] <= 0
                or fieller["type"] != "bounded"
                or not np.allclose(roots, fieller["interval"], rtol=1e-9, atol=1e-9)
            ):
                raise ValueError("independent signed Fieller roots differ")
            for index, test in enumerate([0, saved["ambient_reference_ionic_NC"]]):
                accepted[index] += bool(roots[0] <= test <= roots[1])
        summary = alternative["grid_summary"]
        if accepted.tolist() != [
            summary["ionic_zero_accepted_95_count"],
            summary["ionic_ambient_reference_accepted_95_count"],
        ]:
            raise ValueError("Fieller membership summary differs")
        summaries.append(
            {
                "name": alternative["name"],
                "zero_accepted": int(accepted[0]),
                "ambient_ionic_reference_accepted": int(accepted[1]),
            }
        )
    if len(errors) != 336:
        raise ValueError("complete336-fresh-fit experiment required")
    return {
        "schema_version": 1,
        "composed_report_sha256": digest(path),
        "compact_sha256": digest(compact),
        "independent_full_grid_GLS_fits": len(errors),
        "maximum_flux_difference": max(e[0] for e in errors),
        "maximum_covariance_difference_over_scale": max(e[1] for e in errors),
        "maximum_chi2_difference": max(e[2] for e in errors),
        "maximum_ionic_ratio_difference": max(ionic_errors),
        "signed_95_membership_summaries": summaries,
        "scope": (
            "Dependent original/DUMMY wavelength and fixed generic-R/noise hypotheses; "
            "no likelihood pooling, calibrated source LSF or elemental stage correction"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.root), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
