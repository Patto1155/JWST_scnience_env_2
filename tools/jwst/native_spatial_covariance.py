"""Follow-up on frozen native reduction: empirical spatial covariance transport.

The sparse off-trace moment estimates are transported through source operators
as explicit scenarios. They are not a calibrated source-noise posterior.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.special import ndtr

from .line_sensitivity import read_resolution
from .native_reduction import (
    ROOT,
    covariance_blocks,
    empirical_noise,
    extract_columns,
    fit_native,
    read_inputs,
    replay_report,
    sha256,
    signed_profiles,
)
from .point_resolution import read_point_resolution


def plot_comparison(result: dict, baseline: dict, output: Path) -> None:
    """Actual conditional fits; uncertainties are not calibration posteriors."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    old = json.loads((ROOT / "research_output/mom_z14_point_resolution.json").read_text())[
        "point_source_scenarios"
    ][0]
    fits_to_plot = [
        old,
        baseline["scenarios"][1]["fit"],
        result["scenarios"][0]["fit"],
        result["alternatives"][1]["fit"],
    ]
    labels = [
        "Stored DJA; diagonal formal",
        "Native; shared formal",
        "Native; empirical row+column",
        "Native; assumed lambda-scaled width",
    ]
    colors = ["#777777", "#278EA5", "#C55A11", "#694C9D"]
    lines = ["NIV", "CIV", "HeII_OIII", "NIII", "CIII"]
    figure, (upper, lower) = plt.subplots(
        2, 1, figsize=(10.5, 7.5), gridspec_kw={"height_ratios": [2, 1.2]}
    )
    x = np.arange(5)
    for i, (fit, label, color) in enumerate(zip(fits_to_plot, labels, colors)):
        flux = np.array([fit["lines"][n]["flux"] for n in lines])
        sigma = np.array([fit["lines"][n]["conditional_sigma"] for n in lines])
        upper.errorbar(
            x + (i - 1.5) * 0.12,
            flux,
            yerr=sigma,
            fmt="o",
            ms=5,
            capsize=3,
            color=color,
            label=label,
        )
        if i == 0:
            ratio = fit["nitrogen_lines_over_carbon_lines"]["value"]
            interval = fit["nitrogen_lines_over_carbon_lines"]["fieller_normal_68_and_95_sets"][
                "1.95996398454"
            ]["interval"]
        else:
            ratio, interval = (
                fit["nitrogen_carbon_line_flux_ratio"],
                fit["ratio_fieller_95"]["interval"],
            )
        lower.errorbar(
            ratio,
            i,
            xerr=np.array([[ratio - interval[0]], [interval[1] - ratio]]),
            fmt="o",
            capsize=4,
            color=color,
        )
    upper.axhline(0, color="#aaaaaa", lw=1)
    upper.set_xticks(x, ["N IV]", "C IV", "He II + O III]", "N III]", "C III]"])
    upper.set_ylabel("Integrated line flux (10$^{-20}$ erg s$^{-1}$ cm$^{-2}$)")
    upper.legend(frameon=False, ncol=2, fontsize=9)
    upper.set_title(
        "MoM-z14: independent reduction and covariance sensitivity", loc="left", fontsize=13
    )
    lower.axvline(0, color="#aaaaaa", lw=1)
    lower.set_yticks(np.arange(4), labels, fontsize=9)
    lower.set_xlabel(
        "(N IV] + N III]) / (C IV + C III]) line-flux ratio; conditional 95% Fieller set"
    )
    lower.invert_yaxis()
    figure.text(
        0.02,
        0.015,
        "Top: conditional 1-sigma errors. Generic point-source Gaussian R; fixed z=14.44. "
        "This is not elemental N/C or an independently calibrated detection.",
        fontsize=8,
    )
    figure.tight_layout(rect=(0, 0.045, 1, 1))
    figure.savefig(output, dpi=160)
    plt.close(figure)


def stationary_spatial_kernel(
    lags: list[float], rows: int, taper: bool = True
) -> tuple[np.ndarray, dict]:
    if not lags or lags[0] != 1 or not np.all(np.isfinite(lags)) or rows < 2:
        raise ValueError("Finite lag moments with unit lag-zero required")
    separation = np.abs(np.arange(rows)[:, None] - np.arange(rows)[None])
    kernel = np.zeros((rows, rows))
    for lag, value in enumerate(lags):
        kernel[separation == lag] = value * (1 - lag / len(lags) if taper else 1)
    minimum = float(np.linalg.eigvalsh(kernel).min())
    shrinkage = (0.1 - minimum) / (1 - minimum) if minimum < 0.1 else 0.0
    kernel = (1 - shrinkage) * kernel + shrinkage * np.eye(rows)
    return kernel, {
        "measured_lag_correlations": lags,
        "taper": "Bartlett through largest measured lag"
        if taper
        else "No taper; zero beyondlargestlag",
        "minimum_eigenvalue_before_guard": minimum,
        "identity_shrinkage_to_min_eigenvalue0p1": shrinkage,
        "minimum_eigenvalue": float(np.linalg.eigvalsh(kernel).min()),
    }


def offtrace_controls(data: list[dict], geometry: dict, selected: np.ndarray) -> np.ndarray:
    traces = np.array([d["trace_seed"] + geometry["offset_pixels"] for d in data])
    yy = np.arange(data[0]["science"].shape[0])[:, None]
    blank = np.all(abs(yy[None] - traces[:, None, :]) > 2.5, axis=0)
    columns = np.zeros(data[0]["science"].shape[1], bool)
    columns[selected] = True
    controls = []
    for d in data:
        mask = blank & d["good"] & columns[None]
        raw = d["science"] / np.sqrt(d["variance"])
        normalized = np.full_like(raw, np.nan)
        for row in range(len(raw)):
            good = mask[row]
            if good.sum() >= 20:
                normalized[row, good] = raw[row, good] - np.mean(raw[row, good])
        controls.append(normalized)
    return np.array(controls)


def spatial_moments(controls: np.ndarray) -> tuple[list[float], list[int]]:
    scale = float(np.nanmean(controls**2))
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("No finite off-trace noise ensemble")
    lags, pairs = [1.0], []
    for lag in range(1, 4):
        a, b = controls[:, :-lag, :], controls[:, lag:, :]
        valid = np.isfinite(a) & np.isfinite(b)
        if not np.any(valid):
            raise ValueError("Requested spatial lag has no observed control pairs")
        pairs.append(int(valid.sum()))
        lags.append(float(np.mean(a[valid] * b[valid]) / scale))
    return lags, pairs


def wavelength_scaled_profiles(data: list[dict], sigma_at3p9: float, offset: float) -> np.ndarray:
    """Explicit lambda-linear width sensitivity, not inferred source PSF."""
    profiles = []
    for d in data:
        wave = np.nanmedian(d["wave"], axis=0)
        sigma = sigma_at3p9 * wave / 3.9
        yy = np.arange(d["science"].shape[0])[:, None]
        trace = d["trace_seed"] + offset
        p = ndtr((yy + 0.5 - trace) / sigma) - ndtr((yy - 0.5 - trace) / sigma)
        profiles.append(p * d["point_pathloss"])
    profiles = np.array(profiles)
    result = np.zeros_like(profiles)
    for i, d in enumerate(data):
        members = [j for j, other in enumerate(data) if other["group"] == d["group"]]
        result[i] = profiles[i] - sum(profiles[j] for j in members if j != i) / 2
    return result


def below_break_control(
    data: list[dict], flux: np.ndarray, blocks: np.ndarray, uv_scale: float
) -> dict:
    """Source-operator null diagnostic below the assumed published Lyman break."""
    wave = np.nanmedian(data[0]["wave"], axis=0)
    selected = np.flatnonzero(
        (wave > 1.15)
        & (wave < 1.70)
        & np.all(np.isfinite(flux), axis=0)
        & np.all(np.diagonal(blocks, axis1=1, axis2=2) > 0, axis=1)
    )
    if len(selected) < 10:
        raise ValueError("Insufficient source-operator below-break controls")
    means, sigmas = [], []
    for column in selected:
        weights = np.linalg.solve(blocks[column], np.ones(len(data)))
        denominator = weights.sum()
        means.append(float(weights @ flux[:, column] / denominator))
        sigmas.append(float(1 / np.sqrt(denominator)))
    normalized = np.array(means) / sigmas
    weights = 1 / np.array(sigmas) ** 2
    return {
        "window_um": [1.15, 1.70],
        "source_operator_columns": len(selected),
        "wavelength_um": wave[selected].tolist(),
        "flux_uJy": means,
        "shared_formal_sigma_uJy": sigmas,
        "normalized_mean": float(normalized.mean()),
        "normalized_rms": float(np.sqrt(np.mean(normalized**2))),
        "normalized_variance_about_mean_ddof1": float(normalized.var(ddof=1)),
        "positive_formal_above3_count": int(np.sum(normalized > 3)),
        "negative_formal_below_minus3_count": int(np.sum(normalized < -3)),
        "mean_fnu_uJy": float(np.average(means, weights=weights)),
        "diagonal_column_formal_mean_sigma_uJy": float(1 / np.sqrt(weights.sum())),
        "rms_after_uv_noise_amplitude_transport": float(np.sqrt(np.mean(normalized**2) / uv_scale)),
        "interpretation": (
            "Conditional source-operator null at z14.44; IGM absorption assumed, "
            "foreground/residual light allowed; not independent blank apertures, "
            "Gaussian-tail calibration, or spectral-stationarity proof"
        ),
    }


def run(native_dir: Path, baseline_report: Path, output: Path) -> dict:
    baseline = json.loads(baseline_report.read_text())
    baseline_replay = replay_report(baseline_report)
    data, metadata = read_inputs(native_dir, ROOT / "data_sources/pilot/mom_z14_dja_v4.spec.fits")
    geometry = baseline["geometry"]
    selected = np.array(baseline["selected_native_columns"])
    for d in data:
        d["trace_refined"] = d["trace_seed"] + geometry["offset_pixels"]
        d["sigma_refined"] = geometry["sigma_pixels"]
    profile = signed_profiles(data, geometry["sigma_pixels"], geometry["offset_pixels"])
    flux, operators, _ = extract_columns(data, profile)
    blocks, _ = covariance_blocks(data, operators)
    spectral_kernel, noise = empirical_noise(data, geometry, selected)
    compact_path = baseline_report.parent / baseline["compact_native_replay"]["filename"]
    with np.load(compact_path, allow_pickle=False) as replay:
        if not np.allclose(flux[:, selected], replay["flux"], rtol=0, atol=1e-12):
            raise ValueError("Actual native source operators do not reproduce frozen extraction")
        if not np.allclose(blocks[selected], replay["covariance_blocks"], rtol=0, atol=1e-12):
            raise ValueError("Actual shared-nod variance does not reproduce frozen model")
    controls = offtrace_controls(data, geometry, selected)
    lags, pairs = spatial_moments(controls)
    if not np.allclose(
        lags, baseline["empirical_noise"]["measured_spatial_lag_correlations_0_to_3"]
    ):
        raise ValueError("Off-trace spatial moments do not replay first-phase measurements")
    rows = data[0]["science"].shape[0]
    spatial_kernel, kernel_metadata = stationary_spatial_kernel(lags, rows)
    spatial_blocks, spatial_metadata = covariance_blocks(data, operators, spatial_kernel)
    pw, pr, point_meta = read_point_resolution(
        ROOT / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    rw, rr, nominal_meta = read_resolution(ROOT / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
    scenarios = []
    for label, wave_r, r in [
        ("point_spatial_spectral_transport", pw, pr),
        ("nominal_spatial_spectral_transport", rw, rr),
    ]:
        fit = fit_native(
            data,
            flux,
            spatial_blocks,
            selected,
            wave_r,
            r,
            kernel=spectral_kernel,
            noise_scale=noise["pooled_scale_squared"],
        )
        scenarios.append({"name": label, "fit": fit})
    sigma_ratio = np.sqrt(
        np.diagonal(spatial_blocks[selected], axis1=1, axis2=2)
        / np.diagonal(blocks[selected], axis1=1, axis2=2)
    )
    group_leave_out = []
    for group in sorted({d["group"] for d in data}):
        members = [i for i, d in enumerate(data) if d["group"] != group]
        moment, count = spatial_moments(controls[members])
        changed_kernel, changed_metadata = stationary_spatial_kernel(moment, rows)
        changed_blocks, _ = covariance_blocks(data, operators, changed_kernel)
        changed_scale = float(np.nanmean(controls[members] ** 2))
        group_leave_out.append(
            {
                "left_out_group": group,
                "spatial_lag_pair_counts": count,
                "kernel": changed_metadata,
                "noise_scale_squared": changed_scale,
                "fit_all_source_groups": fit_native(
                    data,
                    flux,
                    changed_blocks,
                    selected,
                    pw,
                    pr,
                    kernel=spectral_kernel,
                    noise_scale=changed_scale,
                ),
            }
        )
    alternatives = []
    untapered, untapered_meta = stationary_spatial_kernel(lags, rows, taper=False)
    changed_blocks, _ = covariance_blocks(data, operators, untapered)
    alternatives.append(
        {
            "name": "untapered_spatial_lags",
            "kernel": untapered_meta,
            "fit": fit_native(
                data,
                flux,
                changed_blocks,
                selected,
                pw,
                pr,
                kernel=spectral_kernel,
                noise_scale=noise["pooled_scale_squared"],
            ),
        }
    )
    scaled_profile = wavelength_scaled_profiles(
        data, geometry["sigma_pixels"], geometry["offset_pixels"]
    )
    scaled_flux, scaled_operators, _ = extract_columns(data, scaled_profile)
    scaled_blocks, _ = covariance_blocks(data, scaled_operators, spatial_kernel)
    alternatives.append(
        {
            "name": "lambda_linear_spatial_width_sensitivity",
            "spatial_width": (
                "sigma(lambda)=0.8*lambda/3.9 nativepixels; assumed pure diffraction scaling"
            ),
            "geometry_inference": (
                "Red-continuum fit frozen; this hypothesis is not source-size inference"
            ),
            "fit": fit_native(
                data,
                scaled_flux,
                scaled_blocks,
                selected,
                pw,
                pr,
                kernel=spectral_kernel,
                noise_scale=noise["pooled_scale_squared"],
            ),
        }
    )
    result = {
        "schema_version": 1,
        "executable_source_sha256": sha256(Path(__file__)),
        "native_operator_source_sha256": sha256(Path(__file__).with_name("native_reduction.py")),
        "baseline_report_sha256": sha256(baseline_report),
        "baseline_replay": baseline_replay,
        "native_metadata": metadata,
        "spatial_kernel": kernel_metadata,
        "spatial_lag_pair_counts": pairs,
        "spatial_covariance": spatial_metadata,
        "conditional_source_sigma_multiplier_from_spatial_only": {
            "median": float(np.median(sigma_ratio)),
            "range": [float(sigma_ratio.min()), float(sigma_ratio.max())],
        },
        "scenarios": scenarios,
        "leave_one_control_group_out": group_leave_out,
        "alternatives": alternatives,
        "resolution": {"point": point_meta, "nominal": nominal_meta},
        "below_break_source_operator_control": below_break_control(
            data, flux, spatial_blocks, noise["pooled_scale_squared"]
        ),
        "limitations": [
            (
                "Stationary separable row/column covariance transported from "
                "few off-source spatial placements"
            ),
            (
                "Lag3 has189overlapping controlpairs, not189independent "
                "apertures; threegroups and sharednods"
            ),
            "Spatial source covariance remains assumed even after empirical moment transport",
            "No independent wavelength/LSF calibration, exactauthorPIXTAB or finitegalaxy profile",
            "Linefluxratio isnot elemental abundance; no source discovery or enrichment exclusion",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    figure_path = output.with_suffix(".png")
    plot_comparison(result, baseline, figure_path)
    result["figure"] = {
        "filename": figure_path.name,
        "sha256": sha256(figure_path),
        "comparison_report_sha256": sha256(ROOT / "research_output/mom_z14_point_resolution.json"),
    }
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-dir", type=Path, required=True)
    parser.add_argument(
        "--baseline-report", type=Path, default=ROOT / "research_output/mom_native_reduction.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.native_dir, args.baseline_report, args.output)


if __name__ == "__main__":
    main()
