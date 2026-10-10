"""Independent positive/negative-nod forward response oracle on pinned CALs.

Uses native input guards, but reconstructs spatial profiles, subtraction,
weighted extraction and spectral normal equations separately from the author
implementation. Conditional scalar source-centered wavelength assumption remains.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.linalg import block_diag
from scipy.special import ndtr
from scipy.stats import norm

from discovery.continuation_review import digest
from discovery.continuation_wavecorr_review import bin_design, source_waves
from tools.jwst.line_sensitivity import read_resolution
from tools.jwst.native_reduction import read_inputs
from tools.jwst.point_resolution import read_point_resolution
from tools.jwst.shared_systematics import gls


def audit(root: Path, native_dir: Path) -> dict:
    paths = {
        name: root / "research_output" / name
        for name in (
            "mom_native_reduction.json",
            "mom_native_wavecorr.json",
            "mom_multiplet_components_niv_doublet_v2.json",
        )
    }
    baseline = json.loads(paths["mom_native_reduction.json"].read_text())
    wave_report = json.loads(paths["mom_native_wavecorr.json"].read_text())
    compact = root / "research_output" / wave_report["compact_replay"]["filename"]
    if digest(compact) != wave_report["compact_replay"]["sha256"]:
        raise ValueError("Frozen compact identity mismatch")
    with np.load(compact, allow_pickle=False) as archive:
        z = {name: archive[name].copy() for name in archive.files}
    data, _ = read_inputs(native_dir, root / "data_sources/pilot/mom_z14_dja_v4.spec.fits")
    sigma, offset = (baseline["geometry"][k] for k in ("sigma_pixels", "offset_pixels"))
    selected = z["selected_columns"]
    traces = np.array([d["trace_seed"] + offset for d in data])
    yy = np.arange(28)[None, :, None]
    positive = (
        ndtr((yy + 0.5 - traces[:, None]) / sigma) - ndtr((yy - 0.5 - traces[:, None]) / sigma)
    ) * np.array([np.where(d["good"], d["point_pathloss"], 0) for d in data])
    mixing = np.zeros((9, 9))
    for i, left in enumerate(data):
        for j, right in enumerate(data):
            if left["group"] == right["group"]:
                mixing[i, j] = 1.0 if i == j else -0.5
    signed = np.einsum("ij,jrc->irc", mixing, positive)
    operators = np.zeros_like(positive)
    extraction = np.zeros((9, len(selected)))
    rows = (np.arange(28) - 14) / 28
    for i, d in enumerate(data):
        for column in selected:
            valid = d["good"][:, column]
            basis = np.column_stack((signed[i, :, column], np.ones(28), rows))[valid]
            sd = np.sqrt(d["variance"][valid, column])
            # Independent SVD pseudo-inverse rather than the source normal-matrix
            # inverse. A whitened constant/slope is profiled with source weights.
            inverse = np.linalg.pinv(basis / sd[:, None], rcond=1e-14)
            operators[i, valid, column] = inverse[0] / sd
            extraction[i, np.searchsorted(selected, column)] = (
                operators[i, valid, column] @ d["science"][valid, column]
            )
    extraction_error = float(np.max(abs(extraction - z["flux"])))
    if extraction_error > 1e-12:
        raise ValueError("Independent spatial extraction differs from frozen amplitudes")
    waves = source_waves(z["native_wave"], z["native_good"], traces, sigma)
    templates = json.loads(paths["mom_multiplet_components_niv_doublet_v2.json"].read_text())
    reference = next(
        r
        for r in templates["records"]
        if (r["temperature_K"], r["electron_density_cm3"]) == (20000, 1000)
    )
    components = [
        (g["vacuum_wavelengths_A"], g["normalized_weights"]) for g in reference["components"]
    ]
    rw, rr, _ = read_point_resolution(
        root / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    design = bin_design(waves, selected, rw, rr, components)
    positive_response = design.reshape(len(selected), 9, 7)
    coupling = np.empty((len(selected), 9, 9))
    for i in range(9):
        for j in range(9):
            coupling[:, i, j] = mixing[i, j] * np.sum(
                operators[i][:, selected] * positive[j][:, selected], axis=0
            )
    coupled = np.einsum("cij,cjk->cik", coupling, positive_response).reshape(design.shape)
    truth = np.array([2.0, -0.5, 20.0, 15.0, 15.0, 5.0, 12.0])
    spectra = (design @ truth).reshape(len(selected), 9).T
    raw_source = positive[:, :, selected] * spectra[:, None, :]
    signed_image = np.einsum("ij,jrc->irc", mixing, raw_source)
    direct_values = np.sum(operators[:, :, selected] * signed_image, axis=1).T.ravel()
    closure_error = float(np.max(abs(direct_values - coupled @ truth)))
    factor = block_diag(*[np.linalg.cholesky(b) for b in z["spatial_covariance_blocks"]])
    covariance = factor @ np.kron(z["spectral_kernel"], np.eye(9)) @ factor.T
    covariance *= z["noise_scale_squared"][0]
    naive = gls(design, covariance, direct_values)
    corrected = gls(coupled, covariance, direct_values)
    actual = gls(coupled, covariance, extraction.T.ravel())
    formal = block_diag(*list(z["covariance_blocks"]))
    formal_naive = gls(design, formal, direct_values)
    formal_corrected = gls(coupled, formal, direct_values)
    author_path = root / "research_output/mom_native_measurement_validation.json"
    if digest(author_path) != "c7e31e81a6bb6b9b4b81bf48661ccfa28475be5cf6b226f85113c78fe73074ca":
        raise ValueError("Frozen c9cf5b2 spectroscopy artifact differs")
    author = json.loads(author_path.read_text())
    families = []
    atomic_path = root / "research_output/mom_atomic_grid_niv_doublet_v2.json"
    atomic = json.loads(atomic_path.read_text())
    cell = next(
        r
        for r in atomic["records"]
        if (r["temperature_K"], r["electron_density_cm3"]) == (20000, 1000)
    )
    epsilon = cell["emissivity_erg_cm3_s"]
    ionic_projection = np.array(
        [
            [epsilon["CIII"] / epsilon["NIV"], 0, 0, epsilon["CIII"] / epsilon["NIII"], 0],
            [0, epsilon["CIII"] / epsilon["CIV"], 0, 0, 1],
        ]
    )
    nominal_wave, nominal_r, _ = read_resolution(
        root / "data_sources/pilot/jwst_nirspec_prism_disp.fits"
    )
    for corrected_wave in (False, True):
        local_waves = source_waves(
            z["corrected_wave" if corrected_wave else "native_wave"],
            z["native_good"],
            traces,
            sigma,
        )
        for name, resolution_wave, resolution in (
            ("nominal", nominal_wave, nominal_r),
            ("generic_point", rw, rr),
        ):
            direct = bin_design(local_waves, selected, resolution_wave, resolution, components)
            joint = np.einsum(
                "cij,cjk->cik", coupling, direct.reshape(len(selected), 9, 7)
            ).reshape(direct.shape)
            answer = gls(joint, covariance, extraction.T.ravel())
            saved_family = next(
                r
                for r in author["signed_forward_corrected_baseline_fits"]
                if r["resolution_family"] == name
                and r["wavelength_hypothesis"]
                == ("pinned_toy_prediction" if corrected_wave else "original_native")
            )["fit"]
            error = float(np.max(abs(answer[0][2:] - saved_family["fluxes"])))
            cov_error = float(np.max(abs(answer[1][2:, 2:] - saved_family["flux_covariance"])))
            n, c = ionic_projection @ answer[0][2:]
            vc = ionic_projection @ answer[1][2:, 2:] @ ionic_projection.T
            roots = np.sort(
                np.roots(
                    [
                        c**2 - 3.84145882069 * vc[1, 1],
                        -2 * (n * c - 3.84145882069 * vc[0, 1]),
                        n**2 - 3.84145882069 * vc[0, 0],
                    ]
                )
            )
            ionic = saved_family["ionic_N_over_C"]
            if (
                error > 1e-8
                or cov_error > 1e-8
                or not np.allclose(
                    roots, ionic["conditional_gaussian_95_fieller_set"]["interval"], atol=1e-8
                )
            ):
                raise ValueError("One of four signed fixed-family likelihoods differs")
            families.append(
                {
                    "resolution": name,
                    "wavelength_hypothesis": "DUMMY sensitivity" if corrected_wave else "original",
                    "max_flux_difference": error,
                    "max_covariance_difference": cov_error,
                    "conditional_ionic_NC": float(n / c),
                    "conditional_signed_95_Fieller_interval": roots.tolist(),
                    "solar_ionic_reference_in_set": bool(roots[0] <= 10**-0.60 <= roots[1]),
                }
            )

    # Independently reconstruct the formal signed-pixel covariance. Failed
    # three-component demixing is reconciled by exhaustive nonnegative active
    # subsets rather than the author's NNLS routine.
    blocks = np.zeros((len(selected), 9, 9))
    reconciliation_count = 0
    for group in sorted({d["group"] for d in data}):
        members = [i for i, d in enumerate(data) if d["group"] == group]
        local_mix = mixing[np.ix_(members, members)]
        post = np.array([data[i]["variance"][:, selected] for i in members])
        good = np.all(np.array([data[i]["good"][:, selected] for i in members]), axis=0)
        safe = np.where(np.isfinite(post), post, 0)
        raw = np.linalg.solve(local_mix**2, safe.reshape(3, -1)).reshape(post.shape)
        failed = np.any(raw <= 0, axis=0) & good
        for row, col in zip(*np.nonzero(failed)):
            target = safe[:, row, col]
            candidates = [np.zeros(3)]
            for active in range(1, 8):
                indices = np.flatnonzero([(active >> k) & 1 for k in range(3)])
                value = np.linalg.lstsq((local_mix**2)[:, indices], target, rcond=None)[0]
                if np.min(value) >= 0:
                    candidate = np.zeros(3)
                    candidate[indices] = value
                    candidates.append(candidate)
            raw[:, row, col] = min(
                candidates, key=lambda v: np.sum(((local_mix**2) @ v - target) ** 2)
            )
            reconciliation_count += 1
        raw = np.where(good[None], np.maximum(raw, 0), 0)
        remainder = np.maximum(safe - np.einsum("ij,jrc->irc", local_mix**2, raw), 0)
        for left, i in enumerate(members):
            for right, j in enumerate(members):
                variance = np.einsum("k,krc->rc", local_mix[left] * local_mix[right], raw)
                blocks[:, i, j] = np.sum(
                    operators[i][:, selected] * operators[j][:, selected] * variance, axis=0
                )
                if i == j:
                    blocks[:, i, i] += np.sum(
                        operators[i][:, selected] ** 2 * remainder[left], axis=0
                    )
    pixel_cov_error = float(np.max(abs(blocks - z["covariance_blocks"])))
    if pixel_cov_error > 1e-12:
        raise ValueError("Independent signed pixel covariance reconstruction differs")
    propagated = formal_corrected[2] @ block_diag(*list(blocks)) @ formal_corrected[2].T
    coefficient_cov_error = float(np.max(abs(propagated - formal_corrected[1])))
    noise_cases = []
    seed, draws = 7771483, 10000
    rng = np.random.default_rng(seed)
    coeff_noise = rng.multivariate_normal(np.zeros(7), propagated, size=draws)
    sd = np.sqrt(np.diag(propagated))
    author_noise = author["signed_operator_injections"]
    for label, spatial_sigma, spatial_offset in (
        ("matched_signed_profile", sigma, offset),
        ("injected_broader_sigma0p95", 0.95, offset),
        ("injected_trace_offset_plus0p10", sigma, offset + 0.1),
    ):
        injection_trace = np.array([d["trace_seed"] + spatial_offset for d in data])
        profile = ndtr((yy + 0.5 - injection_trace[:, None]) / spatial_sigma) - ndtr(
            (yy - 0.5 - injection_trace[:, None]) / spatial_sigma
        )
        profile *= np.array([np.where(d["good"], d["point_pathloss"], 0) for d in data])
        image = np.einsum("ij,jrc->irc", mixing, profile[:, :, selected] * spectra[:, None, :])
        observed = np.sum(image * operators[:, :, selected], axis=1).T.ravel()
        recovered = formal_corrected[2] @ observed
        bias = recovered - truth
        standardized_bias = bias / sd
        z95 = norm.ppf(0.975)
        exact_coverage = norm.cdf(z95 - standardized_bias) - norm.cdf(-z95 - standardized_bias)
        simulated = np.mean(abs(coeff_noise + bias) <= z95 * sd, axis=0)
        saved_case = next(
            c for c in author_noise["pixel_signed_operator_injections"] if c["name"] == label
        )
        author_cov = np.array(saved_case["conditional_95_marginal_coverage"])
        author_se = np.sqrt(exact_coverage[2:] * (1 - exact_coverage[2:]) / author_noise["draws"])
        zmax = float(np.max(abs(author_cov - exact_coverage[2:]) / author_se))
        recovery_error = float(
            np.max(abs(recovered[2:] - saved_case["noise_free_recovered_fluxes"]))
        )
        if zmax > 5 or recovery_error > 1e-8:
            raise ValueError("Author detector-noise injection coverage/recovery differs")
        noise_cases.append(
            {
                "name": label,
                "independent_exact_conditional_coverage": exact_coverage[2:].tolist(),
                "independent_projected_gaussian_coverage": simulated[2:].tolist(),
                "author_draw_count": author_noise["draws"],
                "author_coverage_max_sampling_sigma_from_exact": zmax,
                "max_author_noiseless_recovery_difference": recovery_error,
                "scope": (
                    "Declared fixed formal signed-pixel covariance, "
                    "no source-Poisson/empirical calibration"
                ),
            }
        )
    saved = next(
        r
        for r in author["signed_forward_corrected_baseline_fits"]
        if (r["resolution_family"], r["wavelength_hypothesis"])
        == ("generic_point", "original_native")
    )["fit"]
    covariance_error = float(np.max(abs(actual[1][2:, 2:] - saved["flux_covariance"])))
    flux_error = float(np.max(abs(actual[0][2:] - saved["fluxes"])))
    if flux_error > 1e-8 or covariance_error > 1e-8:
        raise ValueError("Corrected independent actual-data solver differs from author")
    width_response = np.abs(coupling).sum(axis=2)
    result = {
        "schema_version": 1,
        "inputs_sha256": {str(p.relative_to(root)): digest(p) for p in (*paths.values(), compact)},
        "actual_native_hashes": [{"filename": d["filename"], "sha256": d["sha256"]} for d in data],
        "independent_spatial_SVD_extraction_max_error_uJy": extraction_error,
        "positive_center_wavelength_um_first_UV_column": waves[:, selected[0]].tolist(),
        "mixing_rank": int(np.linalg.matrix_rank(mixing)),
        "coupling_sum_to_one_max_error": float(np.max(abs(coupling.sum(axis=2) - 1))),
        "absolute_coupling_weight_range": [
            float(width_response.min()),
            float(width_response.max()),
        ],
        "direct_image_vs_coupled_response_max_error_uJy": closure_error,
        "truth_fluxes": truth[2:].tolist(),
        "positive_only_response_recovery": naive[0][2:].tolist(),
        "formal_covariance_positive_only_response_recovery": formal_naive[0][2:].tolist(),
        "formal_covariance_signed_contributor_response_recovery": formal_corrected[0][2:].tolist(),
        "all_signed_contributor_response_recovery": corrected[0][2:].tolist(),
        "corrected_noise_free_max_flux_error": float(np.max(abs(corrected[0][2:] - truth[2:]))),
        "corrected_actual_conditional_fluxes": actual[0][2:].tolist(),
        "corrected_actual_conditional_flux_covariance": actual[1][2:, 2:].tolist(),
        "corrected_actual_conditional_chi2": actual[3],
        "author_corrected_artifact_sha256": digest(author_path),
        "author_frozen_science_commit": "c9cf5b2",
        "maximum_author_corrected_flux_difference": flux_error,
        "maximum_author_corrected_covariance_difference": covariance_error,
        "all_four_fixed_family_independent_validation": families,
        "formal_signed_pixel_covariance_independent_validation": {
            "active_set_reconciled_pixels": reconciliation_count,
            "max_extracted_covariance_difference": pixel_cov_error,
            "max_coefficient_covariance_closure_error": coefficient_cov_error,
            "independent_projected_draws": draws,
            "seed": seed,
            "conditional_coverage_cases": noise_cases,
        },
        "conclusion": (
            "Frozen positive-source-only design omits contributor-specific ghost spectra. "
            "All-signed coupled response closes the declared noiseless injection."
        ),
        "scope": (
            "Independent SVD extraction, explicit image-level signed mixing and normal equations; "
            "known conditional source operator, not empirical source/LSF calibration. "
            "Scalar source-centered wavelengths do not calibrate full 2D wavelength response."
        ),
    }
    if closure_error > 1e-12 or result["corrected_noise_free_max_flux_error"] > 1e-8:
        raise ValueError("Signed operator correction fails independent noiseless closure")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--native-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.root, args.native_dir), indent=2) + "\n")


if __name__ == "__main__":
    main()
