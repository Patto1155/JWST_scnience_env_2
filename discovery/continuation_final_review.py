"""Independent finite-model algebra for the final continuation review.

Actual source geometry, extraction and physical grid assumptions are reused.
These alternate matrix/optimizer checks are not additional observations or
calibration of the astrophysical model or covariance coverage.
"""

from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path

import numpy as np
from scipy.linalg import block_diag, cholesky, solve_triangular
from scipy.optimize import nnls

from discovery.continuation_review import digest


def latent_nod_covariance(raw, remainder, operators, spatial):
    """Explicit latent-pixel matrix, nod mixing and source extraction, one column."""
    raw, remainder, operators, spatial = map(np.asarray, (raw, remainder, operators, spatial))
    if (
        raw.ndim != 2
        or raw.shape[0] != 3
        or remainder.shape != raw.shape
        or operators.shape != raw.shape
        or spatial.shape != (raw.shape[1], raw.shape[1])
        or not all(np.isfinite(x).all() for x in (raw, remainder, operators, spatial))
        or np.min(raw) < 0
        or np.min(remainder) < 0
        or not np.allclose(spatial, spatial.T)
        or np.linalg.eigvalsh(spatial).min() < -1e-10
        or not np.allclose(np.diag(spatial), 1)
    ):
        raise ValueError(
            "finite nonnegative aligned latent variances and unit-diagonal PSD kernel required"
        )
    rows = raw.shape[1]
    mixing = np.full((3, 3), -0.5)
    np.fill_diagonal(mixing, 1)
    latent = block_diag(*[np.diag(np.sqrt(v)) @ spatial @ np.diag(np.sqrt(v)) for v in raw])
    mapping = np.kron(mixing, np.eye(rows))
    propagated = mapping @ latent @ mapping.T
    propagated += block_diag(
        *[np.diag(np.sqrt(v)) @ spatial @ np.diag(np.sqrt(v)) for v in remainder]
    )
    extraction = np.zeros((3, 3 * rows))
    for nod in range(3):
        extraction[nod, nod * rows : (nod + 1) * rows] = operators[nod]
    return extraction @ propagated @ extraction.T


def active_set_raw_variance(post):
    """Analytic three-nod inverse, then exhaustive nonnegative active sets."""
    post = np.asarray(post)
    if post.shape != (3,) or not np.isfinite(post).all() or np.any(post < 0):
        raise ValueError("finite nonnegative three-nod diagonal variances required")
    mixing_squared = np.full((3, 3), 0.25)
    np.fill_diagonal(mixing_squared, 1)
    raw = (np.eye(3) * 4 / 3 - np.ones((3, 3)) * 2 / 9) @ post
    if np.all(raw > 0):
        return raw
    scale = float(np.max(post))
    if scale == 0:
        return np.zeros(3)
    options = []
    for mask in range(8):
        keep = np.flatnonzero([(mask >> k) & 1 for k in range(3)])
        candidate = np.zeros(3)
        if len(keep):
            candidate[keep] = np.linalg.lstsq(mixing_squared[:, keep], post / scale, rcond=None)[0]
        if np.min(candidate) >= -1e-12:
            options.append((np.sum((mixing_squared @ candidate - post / scale) ** 2), candidate))
    return np.maximum(min(options, key=lambda entry: entry[0])[1], 0) * scale


def spatial_audit(native_dir: Path, baseline_path: Path, comparison_path: Path):
    from tools.jwst.native_reduction import (
        ROOT,
        covariance_blocks,
        extract_columns,
        read_inputs,
        signed_profiles,
    )
    from tools.jwst.native_spatial_covariance import stationary_spatial_kernel

    baseline = json.loads(baseline_path.read_text())
    saved = json.loads(comparison_path.read_text())
    if saved["baseline_report_sha256"] != digest(baseline_path):
        raise ValueError("spatial report baseline receipt differs")
    data, _ = read_inputs(native_dir, ROOT / "data_sources/pilot/mom_z14_dja_v4.spec.fits")
    geometry = baseline["geometry"]
    selected = np.array(baseline["selected_native_columns"])
    for record in data:
        record["trace_refined"] = record["trace_seed"] + geometry["offset_pixels"]
        record["sigma_refined"] = geometry["sigma_pixels"]
    _, operators, _ = extract_columns(
        data, signed_profiles(data, geometry["sigma_pixels"], geometry["offset_pixels"])
    )
    spatial, _ = stationary_spatial_kernel(
        saved["spatial_kernel"]["measured_lag_correlations"], operators.shape[1]
    )
    production, _ = covariance_blocks(data, operators, spatial)
    oracle = np.zeros_like(production)
    reconciled = 0
    for group in sorted({record["group"] for record in data}):
        members = [i for i, record in enumerate(data) if record["group"] == group]
        if len(members) != 3:
            raise ValueError("exactly three native nods per group required")
        post = np.nan_to_num(
            np.array([data[i]["variance"] for i in members]), nan=0, posinf=0, neginf=0
        )
        good = np.all([data[i]["good"] for i in members], axis=0)
        inverse = np.eye(3) * 4 / 3 - np.ones((3, 3)) * 2 / 9
        raw = np.einsum("ij,jrc->irc", inverse, post)
        negative = np.any(raw <= 0, axis=0) & good
        reconciled += int(np.sum(negative[:, selected]))
        for row, column in zip(*np.nonzero(negative)):
            raw[:, row, column] = active_set_raw_variance(post[:, row, column])
        raw = np.where(good[None], np.maximum(raw, 0), 0)
        squared = np.full((3, 3), 0.25)
        np.fill_diagonal(squared, 1)
        remainder = np.maximum(post - np.einsum("ij,jrc->irc", squared, raw), 0)
        for column in selected:
            oracle[column][np.ix_(members, members)] = latent_nod_covariance(
                raw[:, :, column], remainder[:, :, column], operators[members, :, column], spatial
            )
    scale = float(np.max(abs(production[selected])))
    difference = float(np.max(abs(oracle[selected] - production[selected])) / scale)
    if not np.isfinite(difference) or difference > 1e-10:
        raise ValueError("independent latent spatial matrix disagrees with transported covariance")
    return {
        "actual_groups": len({record["group"] for record in data}),
        "actual_selected_columns": len(selected),
        "reconciled_selected_pixels": reconciled,
        "source_latent_spatial_block_max_difference_over_scale": difference,
        "scope": (
            "alternate covariance construction; extraction and "
            "separable-kernel assumptions reused"
        ),
    }


def atmosphere_audit(archive_path: Path, manifest_path: Path, comparison_path: Path):
    """Independent actual author-row parse, whitened NNLS and precision residuals."""
    manifest = json.loads(manifest_path.read_text())
    saved = json.loads(comparison_path.read_text())
    if digest(archive_path) != manifest["product"]["sha256"]:
        raise ValueError("actual atmosphere archive receipt differs")
    rows, counts = [], {}
    with tarfile.open(archive_path, "r:gz") as archive:
        for pin in manifest["tables"]:
            if pin["expected_status"].startswith("rejected"):
                continue
            lines = archive.extractfile(pin["member"]).read().decode("ascii").splitlines()
            if "10.00pc" not in "\n".join(lines) or "(in mJy)" not in "\n".join(lines):
                raise ValueError("actual author table lacks the required unit convention")
            header = next(i for i, line in enumerate(lines) if line.strip().startswith("Teff"))
            bands = lines[header].split()[8:]
            counts[pin["member"]] = 0
            for number, line in enumerate(lines[header + 1 :], header + 2):
                if not line.strip():
                    continue
                values = np.array([float(token.rstrip("*")) for token in line.split()])
                if not (200 <= values[0] <= 2400 and 3.25 <= values[1] <= 5.5):
                    continue
                flux = np.array(
                    [10.0 ** values[6 + bands.index(band)] * 1e6 for band in saved["bands"]]
                )
                if not np.isfinite(flux).all() or np.any(flux <= 0):
                    raise ValueError("nonpositive/nonfinite atmosphere band flux")
                rows.append((pin["member"], number, flux))
                counts[pin["member"]] += 1
    if len(rows) != saved["provenance"]["valid_grid_rows"]:
        raise ValueError("independent actual atmosphere row count disagrees")
    flux = np.array(saved["observed_flux_njy"])
    results = []
    for scenario in saved["scenarios"]:
        covariance = np.array(scenario["assumed_flux_covariance_njy2"])
        fits = []
        for omitted in [None] + list(range(len(flux))):
            keep = (
                np.arange(len(flux))
                if omitted is None
                else np.delete(np.arange(len(flux)), omitted)
            )
            factor = cholesky(covariance[np.ix_(keep, keep)], lower=True)
            whitened = solve_triangular(factor, flux[keep], lower=True)
            candidates = []
            for _, _, shape in rows:
                design = solve_triangular(factor, shape[keep, None], lower=True)
                amplitude, residual = nnls(design, whitened)
                candidates.append((residual**2, float(amplitude[0]), shape))
            best = min(range(len(candidates)), key=lambda i: candidates[i][0])
            chi2, amplitude, shape = candidates[best]
            record = (
                scenario["top_10_grid_rows"][0]
                if omitted is None
                else scenario["band_held_out_predictions"][omitted]["best_retained_model"]
            )
            if (
                rows[best][:2] != (record["table_member"], record["author_row"])
                or not np.allclose(
                    amplitude * shape, record["model_flux_njy"], rtol=1e-12, atol=1e-10
                )
                or not np.isfinite(chi2)
                or abs(chi2 - record["chi2_conditional"]) > 1e-10
            ):
                raise ValueError("independent actual atmosphere optimizer disagrees")
            if omitted is not None:
                precision = np.linalg.inv(covariance)
                residual = flux - amplitude * shape
                z = (precision @ residual)[omitted] / np.sqrt(precision[omitted, omitted])
                expected = scenario["band_held_out_predictions"][omitted][
                    "conditional_residual_over_assumed_sigma"
                ]
                if not np.isfinite(z) or abs(z - expected) > 1e-10:
                    raise ValueError("independent precision-matrix conditional residual differs")
            fits.append(
                {
                    "omitted_band": None if omitted is None else saved["bands"][omitted],
                    "best_chi2": float(chi2),
                    "prediction_njy": (amplitude * shape).tolist(),
                }
            )
        results.append(
            {"independent_floor": scenario["independent_fractional_floor"], "fits": fits}
        )
    return {
        "independently_parsed_rows": len(rows),
        "per_table_rows": counts,
        "independent_actual_fits": results,
        "scope": (
            "same pinned source and assumed covariance; selection uncertainty omitted; "
            "no class or distance inference"
        ),
    }


def patch_fit_oracle(data, error, psf, x, y, valid, degree, cluster_width):
    """Independent SVD pseudoinverse and cluster-influence (rather than meat) algebra."""
    valid = valid & np.isfinite(data + error + psf + x + y) & (error > 0)
    terms = [np.ones_like(x)] + ([] if degree == 0 else [x, y])
    terms += [] if degree < 2 else [x * x, x * y, y * y]
    polynomial = np.stack(terms, axis=-1)
    design = np.column_stack((psf[valid], polynomial[valid])) / error[valid, None]
    values = data[valid] / error[valid]
    inverse = np.linalg.pinv(design)
    coefficient = inverse @ values
    covariance = inverse @ inverse.T
    residual = values - design @ coefficient
    cells = list(
        zip(
            np.floor(x[valid] / cluster_width).astype(int),
            np.floor(y[valid] / cluster_width).astype(int),
        )
    )
    unique = sorted(set(cells))
    if len(unique) < 2 or len(values) <= design.shape[1]:
        raise ValueError("residual grouping and degrees of freedom are insufficient")
    score = np.stack(
        [
            design[[value == cell for value in cells]].T
            @ residual[[value == cell for value in cells]]
            for cell in unique
        ]
    )
    influence = score @ covariance
    groups, observations, parameters = len(unique), len(values), design.shape[1]
    sigma = np.sqrt(
        np.sum(influence[:, 0] ** 2)
        * groups
        / (groups - 1)
        * (observations - 1)
        / (observations - parameters)
    )
    offsource = valid & (np.hypot(x, y) >= 0.3)
    off_coefficient = np.linalg.pinv(polynomial[offsource] / error[offsource, None]) @ (
        data[offsource] / error[offsource]
    )
    off_background = polynomial @ off_coefficient
    core = valid & (np.hypot(x, y) <= 0.18873115150197345)
    weights = error[valid] ** -2
    return {
        "signed_point_amplitude_njy": float(coefficient[0]),
        "formal_diagonal_sigma_njy": float(np.sqrt(covariance[0, 0])),
        "residual_cluster_sigma_njy": float(sigma),
        "source_excluded_background_point_amplitude_njy": float(
            np.dot(psf[valid] * weights, (data - off_background)[valid])
            / np.dot(psf[valid] * weights, psf[valid])
        ),
        "source_excluded_background_core_aperture_njy": float((data - off_background)[core].sum()),
        "joint_background_core_aperture_njy": float(
            (data - polynomial @ coefficient[1:])[core].sum()
        ),
        "clusters": groups,
    }


def patch_audit(original_dir, repeat_dir, short_psf, long_psf, comparison_path, output):
    """Replay actual geometry while intercepting arrays for a separate fit oracle."""
    from discovery import source_patch_diagnostics as production

    original = production.linear_fit
    errors, groups = [], []

    def audited_call(data, error, psf, x, y, valid, *, degree, cluster_width=0.2):
        expected = original(
            data, error, psf, x, y, valid, degree=degree, cluster_width=cluster_width
        )
        if expected["status"] != "fit":
            return expected
        alternate = patch_fit_oracle(data, error, psf, x, y, valid, degree, cluster_width)
        for key, value in alternate.items():
            if key == "clusters":
                if value != expected[key]:
                    raise ValueError("independent residual-group count differs")
                groups.append(value)
                continue
            difference = abs(value - expected[key])
            if not np.isfinite(difference) or difference > 1e-7:
                raise ValueError("independent SVD/background/cluster-influence fit differs")
            errors.append(difference)
        return expected

    production.linear_fit = audited_call
    try:
        result = production.run(
            original_dir,
            repeat_dir,
            short_psf,
            long_psf,
            output.with_name(output.stem + "_science.json"),
        )
    finally:
        production.linear_fit = original
    saved = json.loads(comparison_path.read_text())
    saved["actual_pixel_figure"]["filename"] = result["actual_pixel_figure"]["filename"]
    if saved != result or not groups:
        raise ValueError("full actual patch replay disagrees with saved science")
    blue = result["images"][0]["local_point_background_fits"][:9]
    return {
        "actual_full_science_replay_exact": True,
        "independent_svd_checked_actual_fits": len(groups),
        "tested_fit_quantities": 6,
        "maximum_absolute_difference_njy": max(errors),
        "residual_group_count_range": [min(groups), max(groups)],
        "blue_joint_point_parameter_range_njy": [
            min(fit["signed_point_amplitude_njy"] for fit in blue),
            max(fit["signed_point_amplitude_njy"] for fit in blue),
        ],
        "blue_source_excluded_aperture_range_njy": [
            min(fit["source_excluded_background_core_aperture_njy"] for fit in blue),
            max(fit["source_excluded_background_core_aperture_njy"] for fit in blue),
        ],
        "scope": (
            "actual geometry, calibration and finite transported PSF reused; "
            "alternate SVD and cluster influence algebra, not a calibrated detection"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    spatial = subparsers.add_parser("spatial")
    spatial.add_argument("--native-dir", type=Path, required=True)
    spatial.add_argument("--baseline", type=Path, required=True)
    spatial.add_argument("--comparison", type=Path, required=True)
    atmosphere = subparsers.add_parser("atmosphere")
    atmosphere.add_argument("--archive", type=Path, required=True)
    atmosphere.add_argument("--manifest", type=Path, required=True)
    atmosphere.add_argument("--comparison", type=Path, required=True)
    patch = subparsers.add_parser("patch")
    patch.add_argument("--original-dir", type=Path, required=True)
    patch.add_argument("--repeat-dir", type=Path, required=True)
    patch.add_argument("--short-psf", type=Path, required=True)
    patch.add_argument("--long-psf", type=Path, required=True)
    patch.add_argument("--comparison", type=Path, required=True)
    for subparser in (spatial, atmosphere, patch):
        subparser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "spatial":
        result = spatial_audit(args.native_dir, args.baseline, args.comparison)
        paths = {"baseline": args.baseline, "comparison": args.comparison}
    elif args.mode == "atmosphere":
        result = atmosphere_audit(args.archive, args.manifest, args.comparison)
        paths = {"archive": args.archive, "manifest": args.manifest, "comparison": args.comparison}
    else:
        result = patch_audit(
            args.original_dir,
            args.repeat_dir,
            args.short_psf,
            args.long_psf,
            args.comparison,
            args.output,
        )
        paths = {"comparison": args.comparison}
    args.output.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "inputs_sha256": {key: digest(path) for key, path in paths.items()},
                "audit": result,
            },
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
