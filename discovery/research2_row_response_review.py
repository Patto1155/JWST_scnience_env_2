"""Independent pixel-row spectral-bin, nod, GLS and held-out-group oracle."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import numpy as np
from astropy.io import fits
from scipy.linalg import block_diag, cho_factor, cho_solve
from scipy.special import erf
from scipy.stats import norm

from discovery.continuation_wavecorr_review import bin_design, linear_extrapolation, source_waves
from discovery.research2_medium_review import sha
from tools.jwst.line_sensitivity import read_resolution
from tools.jwst.native_reduction import read_inputs
from tools.jwst.point_resolution import read_point_resolution
from tools.jwst.shared_systematics import gls


def pixel_design(waves, profiles, selected, rw, resolution, components):
    """Explicit erf integration on full row edges, without production line_matrix."""
    designs = np.zeros((*profiles.shape, 7))
    for i in range(len(waves)):
        for row in range(waves.shape[1]):
            if not np.any(profiles[i, row]):
                continue
            raw = waves[i, row]
            finite = np.flatnonzero(np.isfinite(raw) & (raw > 0))
            wave = linear_extrapolation(np.arange(len(raw)), finite, raw[finite])
            edges = np.concatenate(
                (
                    [wave[0] - (wave[1] - wave[0]) / 2],
                    (wave[:-1] + wave[1:]) / 2,
                    [wave[-1] + (wave[-1] - wave[-2]) / 2],
                )
            )
            line_columns = []
            for rest, weights in components:
                profile = np.zeros(len(wave))
                weights = np.array(weights) / np.sum(weights)
                for wavelength, weight in zip(rest, weights, strict=True):
                    center = wavelength * 0.0001 * 15.44
                    sigma = (
                        center / np.interp(center, rw, resolution) / (2 * np.sqrt(2 * np.log(2)))
                    )
                    fractions = 0.5 * np.diff(erf((edges - center) / (np.sqrt(2) * sigma)))
                    profile += weight * fractions / np.diff(edges)
                line_columns.append(profile * wave**2 / 299792.458)
            basis = np.column_stack(
                (np.ones(len(wave)) / 100, (wave - 2.675) / 0.525 / 100, np.array(line_columns).T)
            )
            designs[i, row] = basis * profiles[i, row, :, None]
    return designs


def contract(positive, operators, selected, groups):
    """Explicit donor subtraction and row contractions, retaining all ghosts."""
    output = []
    for i in range(len(positive)):
        mixed = positive[i].copy()
        for j in range(len(positive)):
            if groups[i] == groups[j] and j != i:
                mixed -= 0.5 * positive[j]
        output.append(np.einsum("rc,rck->ck", operators[i], mixed)[selected])
    return np.stack(output, axis=1).reshape(-1, positive.shape[-1])


def audit(root, native):
    artifact = root / "research_output/mom_native_row_response.json"
    expected = "ee0a79bcc65ff60da25cbd97ad8e9aca895a70d9c7f222dca7039da29036ab00"
    if sha(artifact) != expected:
        raise ValueError("Frozen dc9cb69 row-response artifact differs")
    author = json.loads(artifact.read_text())
    baseline = json.loads((root / "research_output/mom_native_reduction.json").read_text())
    report = json.loads((root / "research_output/mom_native_wavecorr.json").read_text())
    archive = root / "research_output" / report["compact_replay"]["filename"]
    if sha(archive) != report["compact_replay"]["sha256"]:
        raise ValueError("Compact covariance/wavelength identity differs")
    with np.load(archive, allow_pickle=False) as cache:
        arrays = {k: cache[k].copy() for k in cache.files}
    data, _ = read_inputs(native, root / "data_sources/pilot/mom_z14_dja_v4.spec.fits")
    wave = np.array([d["wave"] for d in data])
    if not np.allclose(wave, arrays["native_wave"], rtol=0, atol=0, equal_nan=True):
        raise ValueError("Actual native WAVELENGTH differs from covariance replay")
    wcs_checks = []
    try:
        import asdf
    except ImportError:
        asdf = None
    for index, d in enumerate(data if asdf is not None else []):
        with fits.open(native / d["filename"], memmap=False) as hdul:
            content = hdul["ASDF"].data["ASDF_METADATA"][0].tobytes()
        with asdf.open(io.BytesIO(content), lazy_load=True, lazy_tree=True) as tree:
            slit = next(s for s in tree["slits"] if s.get("source_name") == "5224_277193")
            wcs = slit["meta"]["wcs"]
            y, x = np.indices(d["wave"].shape, dtype=float)
            gwcs_wave = np.asarray(wcs(x, y)[2])
            if not np.array_equal(np.isfinite(gwcs_wave), np.isfinite(d["wave"])):
                raise ValueError("Actual CAL GWCS valid pixels differ")
            error = float(np.nanmax(abs(gwcs_wave - d["wave"])))
            if error > 3e-7 or "wavecorr_frame" in wcs.available_frames:
                raise ValueError("Original full-row GWCS disagrees beyond float32 tolerance")
            dispersion = (np.asarray(wcs(x + 0.5, y)[2]) - np.asarray(wcs(x - 0.5, y)[2])) * 1e-6
            dispersion_error = float(np.nanmax(abs(dispersion - arrays["dispersion_m"][index])))
            if dispersion_error > 1e-15:
                raise ValueError("Actual GWCS dispersion differs from DUMMY transform input")
            wcs_checks.append(
                {
                    "filename": d["filename"],
                    "GWCS_vs_WAVELENGTH_max_um": error,
                    "GWCS_dispersion_max_difference_m": dispersion_error,
                }
            )
    dummy_errors = []
    if asdf is not None:
        reference_path = root / "data_sources/followup/jwst_nirspec_wavecorr_0004.asdf"
        if sha(reference_path) != report["reference"]["sha256"]:
            raise ValueError("DUMMY reference identity differs")
        with asdf.open(reference_path, lazy_load=False) as reference:
            if reference["meta"]["pedigree"] != "DUMMY":
                raise ValueError("Sensitivity reference pedigree changed")
            model = reference["apertures"][0]["zero_point_offset"]
            model.bounds_error = False
            model.fill_value = None
            for native_wave, dispersion, position, corrected_wave in zip(
                arrays["native_wave"],
                arrays["dispersion_m"],
                arrays["source_xpos"],
                arrays["corrected_wave"],
                strict=True,
            ):
                centers = np.nanmean(native_wave, axis=0) * 1e-6
                derivatives = np.nanmean(dispersion, axis=0)
                valid = np.isfinite(centers) & np.isfinite(derivatives)
                mapped = centers[valid] + model(centers[valid], position) * derivatives[valid]
                independent = linear_extrapolation(native_wave * 1e-6, centers[valid], mapped) * 1e6
                error = float(np.nanmax(abs(independent - corrected_wave)))
                if error > 1e-13:
                    raise ValueError("Independent DUMMY column transform differs")
                dummy_errors.append(error)
    selected = arrays["selected_columns"]
    sigma, offset = (baseline["geometry"][k] for k in ("sigma_pixels", "offset_pixels"))
    traces = np.array([d["trace_seed"] + offset for d in data])
    rows = np.arange(wave.shape[1])[None, :, None]
    profiles = 0.5 * (
        erf((rows + 0.5 - traces[:, None]) / (np.sqrt(2) * sigma))
        - erf((rows - 0.5 - traces[:, None]) / (np.sqrt(2) * sigma))
    )
    profiles *= np.array([np.where(d["good"], d["point_pathloss"], 0) for d in data])
    groups = [d["group"] for d in data]
    signed = np.empty_like(profiles)
    for i in range(9):
        signed[i] = (
            profiles[i]
            - sum(profiles[j] for j in range(9) if groups[i] == groups[j] and i != j) / 2
        )
    operators = np.zeros_like(profiles)
    values = np.zeros((9, len(selected)))
    background_row = (np.arange(28) - 14) / 28
    for i, d in enumerate(data):
        for idx, c in enumerate(selected):
            good = d["good"][:, c]
            design = np.column_stack((signed[i, :, c], np.ones(28), background_row))[good]
            error = np.sqrt(d["variance"][good, c])
            inverse = np.linalg.pinv(design / error[:, None], rcond=1e-14)
            operators[i, good, c] = inverse[0] / error
            values[i, idx] = operators[i, good, c] @ d["science"][good, c]
    extraction_difference = float(np.max(abs(values - arrays["flux"])))
    if extraction_difference > 1e-12:
        raise ValueError("Independent extraction changed frozen amplitudes")
    factor = block_diag(*[np.linalg.cholesky(c) for c in arrays["spatial_covariance_blocks"]])
    covariance = factor @ np.kron(arrays["spectral_kernel"], np.eye(9)) @ factor.T
    covariance *= arrays["noise_scale_squared"][0]
    templates = json.loads(
        (root / "research_output/mom_multiplet_components_niv_doublet_v2.json").read_text()
    )
    record = next(
        r
        for r in templates["records"]
        if (r["temperature_K"], r["electron_density_cm3"]) == (20000, 1000)
    )
    components = [
        (c["vacuum_wavelengths_A"], c["normalized_weights"]) for c in record["components"]
    ]
    nw, nr, _ = read_resolution(root / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
    pw, pr, _ = read_point_resolution(
        root / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    truth = np.array([2.0, -0.5, 20.0, 15.0, 15.0, 5.0, 12.0])
    families = []
    heldouts = []
    for corrected in (False, True):
        waves = arrays["corrected_wave" if corrected else "native_wave"]
        hypothesis = "pinned_toy_prediction" if corrected else "original_native"
        for name, rw, resolution in (("nominal", nw, nr), ("generic_point", pw, pr)):
            positive = pixel_design(waves, profiles, selected, rw, resolution, components)
            design = contract(positive, operators, selected, groups)
            answer = gls(design, covariance, values.T.ravel())
            saved = next(
                r
                for r in author["row_resolved_fits"]
                if r["resolution_family"] == name and r["wavelength_hypothesis"] == hypothesis
            )["fit"]
            flux_difference = float(np.max(abs(answer[0][2:] - saved["fluxes"])))
            cov_difference = float(np.max(abs(answer[1][2:, 2:] - saved["flux_covariance"])))
            chi_difference = abs(answer[3] - saved["conditional_chi2"])
            if max(flux_difference, cov_difference, chi_difference) > 1e-7:
                raise ValueError(
                    f"Independent row-bin likelihood disagrees {name}: "
                    f"{flux_difference, cov_difference, chi_difference}"
                )
            source = np.einsum("irck,k->irc", positive, truth)
            injected = contract(source[:, :, :, None], operators, selected, groups).ravel()
            closure = float(np.max(abs(injected - design @ truth)))
            recovered = answer[2] @ injected
            scalar = bin_design(
                source_waves(waves, arrays["native_good"], traces, sigma),
                selected,
                rw,
                resolution,
                components,
            ).reshape(len(selected), 9, 7)
            coupling = np.zeros((len(selected), 9, 9))
            for i in range(9):
                for j in range(9):
                    if groups[i] == groups[j]:
                        coupling[:, i, j] = (1 if i == j else -0.5) * np.sum(
                            operators[i][:, selected] * profiles[j][:, selected], axis=0
                        )
            scalar = np.einsum("cij,cjk->cik", coupling, scalar).reshape(design.shape)
            scalar_answer = gls(scalar, covariance, values.T.ravel())
            scalar_recovered = scalar_answer[2] @ injected
            bias = (scalar_recovered[2:] - truth[2:]) / np.sqrt(np.diag(scalar_answer[1]))[2:]
            coverage = norm.cdf(norm.ppf(0.975) - bias) - norm.cdf(-norm.ppf(0.975) - bias)
            control = next(
                r
                for r in author["row_source_injection_controls"]
                if r["resolution_family"] == name and r["wavelength_hypothesis"] == hypothesis
            )
            if (
                not np.allclose(scalar_recovered[2:], control["scalar_recovered_fluxes"], atol=1e-8)
                or not np.allclose(
                    coverage, control["assumed_gaussian_scalar_95_coverage"], atol=1e-10
                )
                or np.max(abs(recovered - truth)) > 1e-9
                or closure > 1e-12
            ):
                raise ValueError("Independent row/scalar closure or declared coverage differs")
            families.append(
                {
                    "resolution": name,
                    "wavelength": hypothesis,
                    "max_flux_difference": flux_difference,
                    "max_covariance_difference": cov_difference,
                    "chi2_difference": chi_difference,
                    "row_injected_NIV_recovery": float(recovered[2]),
                    "scalar_injected_NIV_recovery": float(scalar_recovered[2]),
                    "pixel_vs_matrix_closure_error": closure,
                    "maximum_scalar_bias_over_sigma": float(max(abs(bias))),
                    "declared_Gaussian_fixed_covariance_scalar_95_coverage": coverage.tolist(),
                }
            )
            if not corrected and name == "generic_point":
                grid = design.reshape(len(selected), 9, 7)
                for group in sorted(set(groups)):
                    test_members = [i for i, g in enumerate(groups) if g == group]
                    train_members = [i for i in range(9) if i not in test_members]

                    def subset(members):
                        ids = np.array([c * 9 + i for c in range(len(selected)) for i in members])
                        return (
                            grid[:, members].reshape(-1, 7),
                            covariance[np.ix_(ids, ids)],
                            values[members].T.ravel(),
                        )

                    train_a, train_c, train_y = subset(train_members)
                    test_a, test_c, test_y = subset(test_members)
                    trained = gls(train_a, train_c, train_y)
                    predicted_c = test_c + test_a[:, 2:] @ trained[1][2:, 2:] @ test_a[:, 2:].T
                    residual = test_y - test_a[:, 2:] @ trained[0][2:]
                    chol = cho_factor(predicted_c, lower=True)
                    precision_y = cho_solve(chol, residual)
                    precision_a = cho_solve(chol, test_a[:, :2])
                    nuisance = np.linalg.solve(
                        test_a[:, :2].T @ precision_a, test_a[:, :2].T @ precision_y
                    )
                    residual -= test_a[:, :2] @ nuisance
                    statistic = float(residual @ cho_solve(chol, residual))
                    expected_pred = next(
                        r
                        for r in author["held_out_rate_group_predictions"]
                        if r["held_out_group"] == group
                    )["prediction"]
                    if abs(statistic - expected_pred["predictive_chi2"]) > 1e-7:
                        raise ValueError("Independent held-out prediction differs")
                    heldouts.append(
                        {
                            "group": group,
                            "conditional_predictive_chi2": statistic,
                            "dof": len(residual) - 2,
                            "difference": abs(statistic - expected_pred["predictive_chi2"]),
                        }
                    )
    return {
        "schema_version": 1,
        "frozen_author_commit": "dc9cb69",
        "artifact_sha256": expected,
        "review_code_sha256": sha(Path(__file__)),
        "actual_CAL_GWCS_checks": wcs_checks,
        "GWCS_redecoded_this_review": asdf is not None,
        "DUMMY_reference_transform_max_differences_um": dummy_errors,
        "GWCS_decoder_status": (
            "available"
            if asdf is not None
            else "Optional ASDF/GWCS packages absent from locked environment; direct original "
            "WAVELENGTH read from all nine hash-verified actual CALs checked against replay"
        ),
        "extraction_max_difference_uJy": extraction_difference,
        "four_fixed_families": families,
        "three_RATE_group_predictions": heldouts,
        "new_download_bytes": 0,
        "approval": "Approved conditional row-resolved response and scalar-approximation budget",
        "independence": (
            "Direct actual CAL WAVELENGTH checks, optional ASDF/GWCS decoding; "
            "explicit erf-integrated full pixel-row bins; "
            "donor-by-donor signed subtraction; SVD extraction; independent normal GLS "
            "and profiled held-out prediction. Production row response is not imported."
        ),
        "limits": [
            (
                "Point spatial profile/pathloss and generic LSF remain assumed; "
                "full-row WAVELENGTH is extended-source calibration"
            ),
            (
                "DUMMY reference is a sensitivity experiment; no empirical "
                "wavelength or LSF calibration"
            ),
            (
                "Coverage is analytic conditional Gaussian fixed-covariance, "
                "not measured source noise or empirical coverage"
            ),
            "Three held-out RATE groups cannot bound shared systematic distributions",
            "No elemental N/C identification or likelihood pooling",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "native", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(audit(args.root, args.native), indent=2, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    main()
