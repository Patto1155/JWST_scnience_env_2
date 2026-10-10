"""Versioned RATE-derived donor covariance; historical demixing is untouched.

Independent reduction: calibrated pixels, source geometry and generic LSF remain
conditional. Target-only CAL ERR is not post-subtraction total variance.
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from astropy.io import fits

from tools.jwst.line_sensitivity import read_resolution
from tools.jwst.native_measurement_validation import (
    held_out_prediction,
    serial_fit,
    solve_measurement,
    transported_covariance,
)
from tools.jwst.native_reduction import (
    ROOT,
    empirical_noise,
    extract_columns,
    gaussian_profile,
    mixing_matrix,
    read_inputs,
    sha256,
    signed_profiles,
)
from tools.jwst.native_row_response import (
    SIGNED_ARTIFACT_SHA256,
    row_source_design,
    signed_pixel_response,
)
from tools.jwst.native_spatial_covariance import stationary_spatial_kernel
from tools.jwst.native_wavecorr import load_wavecorr_replay
from tools.jwst.point_resolution import read_point_resolution

MANIFEST = ROOT / "data_sources/followup/mom_rate_noise_manifest.json"


def primary_source_stub(path: Path) -> dict:
    """Execute exact pinned background_sub AST with a background-model stub."""
    tree = ast.parse(path.read_text())
    node = next(
        x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == "background_sub"
    )
    namespace = {"log": logging.getLogger(__name__)}
    donor = SimpleNamespace(
        data=np.array([2.0]), dq=np.array([4], dtype=np.uint32), err=np.array([999.0])
    )
    namespace["average_background"] = lambda *args: donor
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    target = SimpleNamespace(
        data=np.array([10.0]),
        dq=np.array([0], dtype=np.uint32),
        err=np.array([3.0]),
        var_poisson=np.array([5.0]),
        var_rnoise=np.array([4.0]),
        meta=SimpleNamespace(filename="stub"),
    )
    _, result = namespace["background_sub"](target, [], 3.0, None)
    return {
        key: getattr(result, key).tolist()
        for key in ("data", "dq", "err", "var_poisson", "var_rnoise")
    }


def donor_covariance(
    raw_variance: np.ndarray,
    gains: np.ndarray,
    operators: np.ndarray,
    flat_variance: np.ndarray,
    spatial: np.ndarray | None = None,
) -> np.ndarray:
    """G_i M_ik raw_k covariance M_jk G_j; flat-reference remainder diagonal.

    Shared flat-reference uncertainty is unresolved. This independent residual
    treatment is a declared conditional assumption, not measured reference noise.
    """
    count, rows, columns = operators.shape
    if count != 3 or any(x.shape != operators.shape for x in (raw_variance, gains, flat_variance)):
        raise ValueError("one aligned three-nod group required")
    mix = mixing_matrix()
    result = np.zeros((columns, count, count))
    for i in range(count):
        for j in range(count):
            for k in range(count):
                a = operators[i] * gains[i] * np.sqrt(raw_variance[k])
                b = operators[j] * gains[j] * np.sqrt(raw_variance[k])
                contracted = (
                    np.sum(a * b, axis=0)
                    if spatial is None
                    else np.einsum("rc,rs,sc->c", a, spatial, b)
                )
                result[:, i, j] += mix[i, k] * mix[j, k] * contracted
        # No double donor propagation for flat-reference uncertainty.
        weighted = operators[i] * np.sqrt(flat_variance[i])
        result[:, i, i] += (
            np.sum(weighted**2, axis=0)
            if spatial is None
            else np.einsum("rc,rs,sc->c", weighted, spatial, weighted)
        )
    return result


def rate_signed_response(
    data: list[dict],
    positive: np.ndarray,
    gains: np.ndarray,
    operators: np.ndarray,
    selected: np.ndarray,
) -> np.ndarray:
    """Known per-pixel calibration gains enter both signed source and noise."""
    raw_positive = np.divide(
        positive,
        gains[:, :, :, None],
        out=np.zeros_like(positive),
        where=np.isfinite(gains[:, :, :, None]) & (gains[:, :, :, None] > 0),
    )
    mixed = np.zeros_like(positive)
    for group in sorted({d["group"] for d in data}):
        members = [i for i, d in enumerate(data) if d["group"] == group]
        mixed[members] = np.einsum("ij,jrck->irck", mixing_matrix(), raw_positive[members])
    gain = np.where(np.isfinite(gains), gains, 0)
    measured = np.sum(mixed * gain[:, :, :, None] * operators[:, :, :, None], axis=1)
    return measured[:, selected].transpose(1, 0, 2).reshape(len(selected) * len(data), -1)


def load_pixels(
    native_dir: Path, rate_dir: Path, data: list[dict]
) -> tuple[list[dict], list[dict]]:
    manifest = json.loads(MANIFEST.read_text())
    pins = {p["filename"]: p for p in manifest["products"]}
    pixels, checks = [], []
    for d in data:
        filename = d["filename"].replace("_cal", "_rate")
        path = rate_dir / filename
        pin = pins[filename]
        if path.stat().st_size != pin["bytes"] or sha256(path) != pin["sha256"]:
            raise ValueError("RATE hash/size mismatch")
        with fits.open(path) as h:
            primary = h[0].header
            if (
                primary["CAL_VER"],
                primary["CRDS_CTX"],
                primary["SUBSTRT1"],
                primary["SUBSTRT2"],
                h["SCI"].header["BUNIT"],
            ) != ("2.0.1", "jwst_1535.pmap", 1, 1, "DN/s"):
                raise ValueError("RATE identity/units/context mismatch")
            rate = {
                name: np.array(h[name].data[1292:1320, 439:862], dtype=float)
                for name in ("SCI", "ERR", "VAR_POISSON", "VAR_RNOISE", "DQ")
            }
        with fits.open(native_dir / d["filename"]) as h:
            sci = next(x for x in h if x.name == "SCI" and x.header.get("SRCNAME") == "5224_277193")
            v = sci.header["EXTVER"]
            if primary["EXPSTART"] != h[0].header["EXPSTART"]:
                raise ValueError("RATE/CAL exposure mismatch")
            conv = (
                sci.header["PIXAR_SR"]
                * 1e12
                * np.asarray(h["PATHLOSS_UN", v].data, dtype=float)
                * np.asarray(h["BARSHADOW", v].data, dtype=float)
            )
            cal = {
                name: np.array(h[name, v].data, dtype=float) * conv**2
                for name in ("VAR_POISSON", "VAR_RNOISE", "VAR_FLAT")
            }
        good = d["good"]
        gain = np.sqrt(cal["VAR_RNOISE"] / rate["VAR_RNOISE"])
        ratios = {}
        for name, pred in [
            ("poisson", rate["VAR_POISSON"] * gain**2),
            ("total_error", rate["ERR"] ** 2 * gain**2 + cal["VAR_FLAT"]),
        ]:
            obs = cal["VAR_POISSON"] if name == "poisson" else d["variance"]
            valid = good & np.isfinite(pred) & (obs > 0)
            ratios[name + "_max_relative_difference"] = float(
                np.max(np.abs(pred[valid] / obs[valid] - 1))
            )
        if max(ratios.values()) > 2e-6:
            raise ValueError("target-only RATE/CAL variance closure fails")
        valid = (
            good
            & np.isfinite(rate["SCI"])
            & np.isfinite(rate["ERR"])
            & (rate["ERR"] > 0)
            & np.isfinite(gain)
            & (gain > 0)
        )
        pixels.append({"rate": rate, "gain": gain, "flat": cal["VAR_FLAT"], "valid": valid})
        checks.append(
            {
                "filename": filename,
                "sha256": pin["sha256"],
                "exposure_start_mjd": primary["EXPSTART"],
                "CALERR_target_only_confirmed": True,
                **ratios,
            }
        )
    return pixels, checks


def run(native_dir: Path, rate_dir: Path, compact_path: Path) -> dict:
    manifest = json.loads(MANIFEST.read_text())
    signed_path = ROOT / "research_output/mom_native_measurement_validation.json"
    if sha256(signed_path) != SIGNED_ARTIFACT_SHA256:
        raise ValueError("merged signed dependency differs from frozen pin")
    dependencies = json.loads(signed_path.read_text())["inputs_sha256"]
    for name, expected in dependencies.items():
        if sha256(ROOT / name) != expected:
            raise ValueError("physical/wavelength dependency differs from frozen pin")
    for p in manifest["sources"]:
        if sha256(rate_dir / p["filename"]) != p["sha256"]:
            raise ValueError("primary source hash mismatch")
    stub = primary_source_stub(rate_dir / "background_background_sub.py")
    baseline = json.loads((ROOT / "research_output/mom_native_reduction.json").read_text())
    geom = baseline["geometry"]
    data, _ = read_inputs(native_dir, ROOT / "data_sources/pilot/mom_z14_dja_v4.spec.fits")
    for d in data:
        d["trace_refined"] = d["trace_seed"] + geom["offset_pixels"]
        d["sigma_refined"] = geom["sigma_pixels"]
    saved = load_wavecorr_replay(ROOT / "research_output/mom_native_wavecorr.json", corrected=False)
    selected = saved["selected"]
    profile = signed_profiles(data, geom["sigma_pixels"], geom["offset_pixels"])
    flux, operators, _ = extract_columns(data, profile, selected_columns=selected)
    if not np.allclose(flux[:, selected], saved["flux"][:, selected], rtol=0, atol=1e-12):
        raise ValueError("frozen source extraction differs from compact baseline")
    pixels, checks = load_pixels(native_dir, rate_dir, data)
    formal = np.zeros((423, 9, 9))
    post = np.zeros((9, 28, 423))
    groups = []
    # Actual SCI proves equal-half donors on the full common usable footprint.
    for group in sorted({d["group"] for d in data}):
        members = [i for i, d in enumerate(data) if d["group"] == group]
        raw = np.array([pixels[i]["rate"]["ERR"] ** 2 for i in members])
        gains = np.array([pixels[i]["gain"] for i in members])
        flat = np.array([pixels[i]["flat"] for i in members])
        valid = np.all([pixels[i]["valid"] for i in members], axis=0)
        if np.any((operators[members] != 0) & ~valid[None]):
            raise ValueError("unmodeled donor support in frozen measurement operator")
        raw = np.where(valid[None], raw, 0)
        gains = np.where(valid[None], gains, 0)
        flat = np.where(valid[None], flat, 0)
        block = donor_covariance(raw, gains, operators[members], flat)
        formal[:, np.array(members)[:, None], members] = block
        post[members] = gains**2 * np.einsum("ik,krc->irc", mixing_matrix() ** 2, raw) + flat
        sci = np.array([pixels[i]["rate"]["SCI"] for i in members])
        diff = np.einsum("ik,krc->irc", mixing_matrix(), np.where(valid[None], sci, 0)) * gains
        obs = np.array([data[i]["science"] for i in members])
        err = np.sqrt(np.array([data[i]["variance"] for i in members]))
        closure = float(
            np.max(
                np.abs(
                    (diff - obs)[np.broadcast_to(valid, obs.shape)]
                    / err[np.broadcast_to(valid, obs.shape)]
                )
            )
        )
        if closure > 1e-4:
            raise ValueError("equal-half SCI closure fails")
        groups.append(
            {
                "group": group,
                "members": members,
                "common_usable_pixels": int(valid.sum()),
                "equal_half_SCI_closure_max_CAL_sigma": closure,
                "new_post_over_target_variance_median": float(
                    np.median(
                        (post[members] / np.array([data[i]["variance"] for i in members]))[:, valid]
                    )
                ),
                "gain_max_relative_nod_spread": float(
                    np.max(np.abs(gains[:, valid] / gains[0, valid] - 1))
                ),
            }
        )
    corrected = [
        {**d, "variance": np.where(post[i] > 0, post[i], np.nan)} for i, d in enumerate(data)
    ]
    kernel, noise = empirical_noise(corrected, geom, selected)
    spatial_kernel, spatial_metadata = stationary_spatial_kernel(
        noise["measured_spatial_lag_correlations_0_to_3"], 28
    )
    spatial = np.zeros_like(formal)
    for g in groups:
        m = g["members"]
        valid = np.all([pixels[i]["valid"] for i in m], axis=0)
        raw = np.where(valid[None], np.array([pixels[i]["rate"]["ERR"] ** 2 for i in m]), 0)
        gains = np.where(valid[None], np.array([pixels[i]["gain"] for i in m]), 0)
        flat = np.where(valid[None], np.array([pixels[i]["flat"] for i in m]), 0)
        block = donor_covariance(raw, gains, operators[m], flat, spatial_kernel)
        spatial[:, np.array(m)[:, None], m] = block
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
    rw, rr, _ = read_resolution(ROOT / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
    pw, pr, _ = read_point_resolution(
        ROOT / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    records, formal_solutions, predictions = [], [], []
    values = flux[:, selected].T.reshape(-1)
    for corrected_wave in (False, True):
        old = load_wavecorr_replay(
            ROOT / "research_output/mom_native_wavecorr.json", corrected=corrected_wave
        )
        local = [{**d, "wave": w["wave"]} for d, w in zip(data, old["data"])]
        for family, w, r in [("nominal", rw, rr), ("generic_point", pw, pr)]:
            positive = row_source_design(
                local, w, r, components, geom["sigma_pixels"], geom["offset_pixels"]
            )
            historical_design = signed_pixel_response(local, positive, operators, selected)
            fresh_design = rate_signed_response(
                local, positive, np.array([p["gain"] for p in pixels]), operators, selected
            )
            for contract, blocks, k, scale in [
                ("target_only_RATE_formal_v3", formal, np.eye(len(selected)), 1.0),
                (
                    "target_only_RATE_control_transport_v3",
                    spatial,
                    kernel,
                    noise["pooled_scale_squared"],
                ),
                (
                    "historical_demixed_control_transport",
                    old["spatial_covariance_blocks"],
                    old["spectral_kernel"],
                    old["noise_scale_squared"],
                ),
            ]:
                design = (
                    historical_design
                    if contract == "historical_demixed_control_transport"
                    else fresh_design
                )
                covariance = transported_covariance(blocks, selected, k, scale, list(range(9)))
                solution = solve_measurement(design, covariance, values)
                fit = serial_fit(solution, emissivity, 1)
                if contract == "target_only_RATE_formal_v3":
                    formal_solutions.append(
                        (old["wavelength_hypothesis"], family, solution, design)
                    )
                if contract == "target_only_RATE_control_transport_v3":
                    for group in groups:
                        test_members = group["members"]
                        train_members = [i for i in range(9) if i not in test_members]
                        subsets = []
                        for members in (train_members, test_members):
                            positions = (np.arange(len(selected))[:, None] * 9 + members).reshape(
                                -1
                            )
                            local_c = covariance[np.ix_(positions, positions)]
                            local_d, local_y = design[positions], values[positions]
                            subsets.append(
                                {
                                    "solution": solve_measurement(local_d, local_c, local_y),
                                    "continuum_order": 1,
                                    "covariance": local_c,
                                    "design": local_d,
                                    "values": local_y,
                                }
                            )
                        predictions.append(
                            {
                                "group": group["group"],
                                "wavelength_hypothesis": old["wavelength_hypothesis"],
                                "resolution_family": family,
                                **held_out_prediction(*subsets),
                            }
                        )
                records.append(
                    {
                        "noise_contract": contract,
                        "wavelength_hypothesis": old["wavelength_hypothesis"],
                        "resolution_family": family,
                        "fit": fit,
                    }
                )
    draws = raw_detector_noise_draws(pixels, data, operators, selected, 4000)
    coverage, flat_budget = [], []
    truth = np.array([2.0, -0.5, 20.0, 15.0, 15.0, 5.0, 12.0])
    for wavelength, family, solution, design in formal_solutions:
        residual = draws @ solution["estimator"][2]
        sigma = float(np.sqrt(solution["covariance"][2, 2]))
        amplitude_weights = solution["estimator"][2].reshape(len(selected), 9).T
        pixel_weights = operators[:, :, selected] * amplitude_weights[:, None, :]
        flat = np.where(
            post[:, :, selected] > 0, np.array([p["flat"][:, selected] for p in pixels]), 0
        )
        weighted_flat = pixel_weights * np.sqrt(flat)
        independent = float(np.sum(weighted_flat**2))
        same_pixel_common = float(
            np.sum(
                np.sum(
                    weighted_flat
                    * np.nan_to_num(
                        np.sign(np.array([d["science"][:, selected] for d in data])), nan=0.0
                    ),
                    axis=0,
                )
                ** 2
            )
        )
        all_pixel_upper = float(np.sum(abs(weighted_flat)) ** 2)
        flat_budget.append(
            {
                "wavelength_hypothesis": wavelength,
                "resolution_family": family,
                "independent_flat_fraction_of_NIV_variance": independent / sigma**2,
                "same_detector_pixel_shared_flat_fraction_of_NIV_variance": same_pixel_common
                / sigma**2,
                "any_correlation_flat_upper_fraction_of_NIV_variance": all_pixel_upper / sigma**2,
                "scope": (
                    "Fixed GLS estimator and recorded VAR_FLAT diagonal; unrestricted "
                    "covariance bound is not an empirical calibration prior. "
                    "Does not bound unrecorded common calibration systematics."
                ),
            }
        )
        coverage.append(
            {
                "wavelength_hypothesis": wavelength,
                "resolution_family": family,
                "draws": 4000,
                "seed": 522414,
                "NIV_noise_standard_deviation_over_formal_sigma": float(
                    np.std(residual, ddof=1) / sigma
                ),
                "NIV_nominal_95_coverage": float(
                    np.mean(abs(residual) <= 1.959963984540054 * sigma)
                ),
                "noisefree_known_spectrum_max_coefficient_error": float(
                    np.max(abs(solution["estimator"] @ (design @ truth) - truth))
                ),
                "scope": (
                    "Fixed observed RATE_ERR Gaussian raw pixel realizations and "
                    "independent flat-reference residual; no source-Poisson "
                    "or empirical-transport coverage certification."
                ),
            }
        )
    basis = np.zeros((9, 28, 423, 9))
    for i, d in enumerate(data):
        basis[i, :, :, i] = gaussian_profile(
            d["trace_refined"], geom["sigma_pixels"], 28
        ) * np.where(d["good"], d["point_pathloss"], 0)
    coupling = rate_signed_response(
        data, basis, np.array([p["gain"] for p in pixels]), operators, selected
    ).reshape(len(selected), 9, 9)
    np.savez_compressed(
        compact_path,
        selected_columns=selected,
        signed_response_coupling=coupling,
        formal_covariance_blocks=formal[selected],
        spatial_covariance_blocks=spatial[selected],
        spectral_kernel=kernel,
        noise_scale_squared=np.array([noise["pooled_scale_squared"]]),
        post_diagonal_variance=post,
        raw_rate_variance=np.where(post > 0, np.array([p["rate"]["ERR"] ** 2 for p in pixels]), 0),
        calibration_gain=np.where(post > 0, np.array([p["gain"] for p in pixels]), 0),
        flat_variance=np.where(post > 0, np.array([p["flat"] for p in pixels]), 0),
        operators=operators,
        flux=flux[:, selected],
    )
    return {
        "schema_version": 3,
        "kind": "actual_RATE_target_only_CAL_variance_contract",
        "manifest_sha256": sha256(MANIFEST),
        "inputs_sha256": dependencies,
        "primary_source_stub": stub,
        "RATE_CAL_checks": checks,
        "groups": groups,
        "empirical_noise_after_donor_normalization": noise,
        "historical_empirical_scale_squared": saved["noise_scale_squared"],
        "spatial_kernel": spatial_metadata,
        "fits": records,
        "fresh_raw_detector_noise_coverage": coverage,
        "recorded_flat_variance_budget": flat_budget,
        "fresh_control_transport_heldout_predictions": predictions,
        "compact_replay": {
            "filename": compact_path.name,
            "sha256": sha256(compact_path),
            "bytes": compact_path.stat().st_size,
        },
        "scope": (
            "All nine actual RATE/CAL pixels validate equal-half SCI and target-only variance. "
            "Empirical row/column transport remains a conditional stationary model; source Poisson "
            "correctness, calibration-reference correlations and source-specific LSF "
            "are uncalibrated. "
            "Historical contracts unchanged; no likelihood pooling."
        ),
    }


def raw_detector_noise_draws(
    pixels: list[dict], data: list[dict], operators: np.ndarray, selected: np.ndarray, draws: int
) -> np.ndarray:
    """Independent raw-detector draws through signed nods and spatial operators."""
    rng = np.random.default_rng(522414)
    result = np.zeros((draws, len(selected), 9))
    for start in range(0, draws, 250):
        stop = min(start + 250, draws)
        for group in sorted({d["group"] for d in data}):
            members = [i for i, d in enumerate(data) if d["group"] == group]
            valid = np.all([pixels[i]["valid"] for i in members], axis=0)[:, selected]
            raw = np.sqrt(
                np.where(
                    valid[None],
                    np.array([pixels[i]["rate"]["ERR"][:, selected] ** 2 for i in members]),
                    0,
                )
            )
            gain = np.where(
                valid[None], np.array([pixels[i]["gain"][:, selected] for i in members]), 0
            )
            flat = np.sqrt(
                np.where(
                    valid[None], np.array([pixels[i]["flat"][:, selected] for i in members]), 0
                )
            )
            photon_read = rng.standard_normal((stop - start,) + raw.shape) * raw
            signed = np.einsum("ik,bkrc->birc", mixing_matrix(), photon_read) * gain
            signed += rng.standard_normal(signed.shape) * flat
            amplitudes = np.sum(signed * operators[members][:, :, selected], axis=2)
            result[start:stop, :, members] = amplitudes.transpose(0, 2, 1)
    return result.reshape(draws, -1)


def load_rate_noise_replay(report_path: Path, *, empirical: bool = True) -> dict:
    """Fresh v3 noise only, compatible with existing source/wavelength designs.

    Numerical artifact replay is not actual RATE/CAL reproduction.
    """
    report = json.loads(report_path.read_text())
    receipt = report["compact_replay"]
    path = report_path.parent / receipt["filename"]
    if path.stat().st_size != receipt["bytes"] or sha256(path) != receipt["sha256"]:
        raise ValueError("RATE noise snapshot mismatch")
    with np.load(path, allow_pickle=False) as arrays:
        selected = arrays["selected_columns"].copy()
        blocks = np.zeros((423, 9, 9))
        name = "spatial_covariance_blocks" if empirical else "formal_covariance_blocks"
        blocks[selected] = arrays[name]
        return {
            "selected": selected,
            "covariance_blocks": blocks,
            "spectral_kernel": arrays["spectral_kernel"].copy()
            if empirical
            else np.eye(len(selected)),
            "noise_scale_squared": float(arrays["noise_scale_squared"][0]) if empirical else 1.0,
            "flux": arrays["flux"].copy(),
            "signed_response_coupling": arrays["signed_response_coupling"].copy(),
            "noise_contract_version": 3,
            "empirical_transport_is_conditional": empirical,
        }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--native-dir", type=Path, required=True)
    p.add_argument("--rate-dir", type=Path, required=True)
    p.add_argument(
        "--output", type=Path, default=ROOT / "research_output/mom_native_rate_noise.json"
    )
    p.add_argument(
        "--compact-output",
        type=Path,
        default=ROOT / "research_output/mom_native_rate_noise_arrays.npz",
    )
    args = p.parse_args()
    started = time.monotonic()
    result = run(args.native_dir, args.rate_dir, args.compact_output)
    result["runtime_seconds"] = time.monotonic() - started
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "checks": len(result["RATE_CAL_checks"]),
                "scale_squared": result["empirical_noise_after_donor_normalization"][
                    "pooled_scale_squared"
                ],
                "fits": len(result["fits"]),
            }
        )
    )


if __name__ == "__main__":
    main()
