"""Independent alternate-solver audits for the second research continuation.

No downloads. Grid headers are decoded directly; no production parser or fit
helper is used. Spectral design is reused but the solve/covariance/nullspace
checks use whitened SVD rather than normal equations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path

import numpy as np
from scipy.linalg import block_diag, solve_triangular
from scipy.optimize import minimize
from scipy.stats import chi2, norm

from discovery.continuation_wavecorr_review import bin_design, source_waves

BANDS = ("F090W", "F115W", "F150W", "F200W", "F277W", "F356W", "F444W")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def svd_fit(x, covariance, y):
    lower = np.linalg.cholesky(covariance)
    a = solve_triangular(lower, x, lower=True)
    b = solve_triangular(lower, y, lower=True)
    u, s, vt = np.linalg.svd(a, full_matrices=False)
    if s[-1] <= 1e-12 * s[0]:
        raise ValueError("Rank-deficient measurement design")
    inverse = (vt.T / s) @ u.T
    coefficient = inverse @ b
    parameter_covariance = (vt.T / s**2) @ vt
    operator = solve_triangular(lower.T, inverse.T, lower=False).T
    residual = b - a @ coefficient
    return coefficient, parameter_covariance, operator, float(residual @ residual)


def spectral_audit(root):
    output = root / "research_output"
    report = json.loads((output / "mom_shared_systematics_v1.json").read_text())
    wave = json.loads((output / "mom_native_wavecorr.json").read_text())
    pin = output / wave["compact_replay"]["filename"]
    z = np.load(pin, allow_pickle=False)
    rw, rr = np.loadtxt(
        root / "data_sources/followup/unite_point_prism_resolution.csv",
        delimiter=",",
        skiprows=1,
        usecols=(0, 1),
    ).T
    template = next(
        r
        for r in json.loads((output / "mom_multiplet_components_niv_doublet_v2.json").read_text())[
            "records"
        ]
        if (r["temperature_K"], r["electron_density_cm3"]) == (20000, 1000)
    )
    waves = source_waves(z["native_wave"], z["native_good"], z["trace"], z["sigma"][0])
    x = bin_design(
        waves,
        z["selected_columns"],
        rw,
        rr,
        [(c["vacuum_wavelengths_A"], c["normalized_weights"]) for c in template["components"]],
    )
    factor = block_diag(*[np.linalg.cholesky(b) for b in z["spatial_covariance_blocks"]])
    c = (factor @ np.kron(z["spectral_kernel"], np.eye(9)) @ factor.T) * z["noise_scale_squared"][0]
    y = z["flux"].T.ravel()
    beta, v, h, q = svd_fit(x, c, y)
    reference = report["independent_reference_reproduction"]
    assert abs(beta[2] - reference["NIV_total_flux"]) < 1e-8
    assert abs(v[2, 2] ** 0.5 - reference["NIV_conditional_sigma"]) < 1e-8
    native = json.loads((output / "mom_native_reduction.json").read_text())
    groups = np.array([e["group"] for e in native["exposures"]])
    injection = x[:, 2] * v[2, 2] ** 0.5
    group_checks = []
    for row in report["heldout_group_diagnostics"]:
        mask = np.tile(groups == row["heldout_group"], len(y) // 9)
        fits = []
        responses = []
        for use in (mask, ~mask):
            f, cv, op, _ = svd_fit(x[use], c[np.ix_(use, use)], y[use])
            fits.append((f, cv))
            responses.append(op @ injection[use])
        delta = fits[0][0][2:] - fits[1][0][2:]
        cov = fits[0][1][2:, 2:] + fits[1][1][2:, 2:]
        statistic = float(delta @ np.linalg.solve(cov, delta))
        assert abs(statistic - row["heldout_minus_training_five_flux_chi2"]) < 1e-8
        assert np.max(abs(fits[0][0][2:] - row["group_fluxes"])) < 1e-8
        group_checks.append(
            {
                "group": row["heldout_group"],
                "chi2": statistic,
                "common_mode_response_difference": float(np.max(abs(responses[0] - responses[1]))),
            }
        )
    augmented = np.column_stack((x, injection))
    rank = int(np.linalg.matrix_rank(augmented))
    assert rank == 7
    assert np.max(abs((np.eye(len(y)) - x @ h) @ injection)) < 1e-12
    # Full data covariance, not scalar resampling: recover the low-rank
    # covariance increment induced by one shared amplitude.
    added = h @ np.outer(injection, injection) @ h.T
    target = np.zeros_like(v)
    target[2, 2] = v[2, 2]
    assert np.max(abs(added - target)) < 1e-8
    for r in report["prescribed_gaussian_common_mode_coverage"]:
        expected = (
            2
            * norm.cdf(
                norm.ppf(0.975)
                / np.sqrt(1 + r["prescribed_common_sigma_over_conditional_sigma"] ** 2)
            )
            - 1
        )
        assert abs(expected - r["omitted_systematic_exact_95_coverage"]) < 1e-14
    expected = [np.sqrt(2 / chi2.ppf(p, 2)) for p in (0.975, 0.025)]
    assert np.allclose(
        expected,
        report["idealized_independent_equal_variance_group_sigma_interval"][
            "95_population_sigma_over_sample_sigma"
        ],
        rtol=0,
        atol=1e-14,
    )
    return {
        "report_sha256": digest(output / "mom_shared_systematics_v1.json"),
        "compact_sha256": digest(pin),
        "NIV_flux": float(beta[2]),
        "NIV_sigma": float(v[2, 2] ** 0.5),
        "chi2": q,
        "group_checks": group_checks,
        "augmented_design_rank": rank,
        "shared_covariance_propagation_max_error": float(np.max(abs(added - target))),
        "scope": (
            "Independent whitened-SVD solve of frozen extracted likelihood; "
            "design shared, no pixel calibration"
        ),
    }


def actual_grid(root, directory):
    manifest = json.loads((root / "data_sources/survivor_atmosphere/manifest.json").read_text())
    archive = directory / manifest["product"]["filename"]
    assert digest(archive) == manifest["product"]["sha256"]
    values = []
    with tarfile.open(archive) as tar:
        for entry in manifest["tables"]:
            raw = tar.extractfile(entry["member"]).read()
            assert hashlib.sha256(raw).hexdigest() == entry["sha256"]
            text = raw.decode("ascii")
            assert "log(fluxes) (in mJy) computed for d=" in text and "10.00pc" in text
            lines = text.splitlines()
            header = next(i for i, line in enumerate(lines) if line.strip().startswith("Teff"))
            filters = lines[header].split()[8:]
            if not set(BANDS) <= set(filters):
                assert entry["expected_status"] == "rejected_missing_jwst_header"
                continue
            assert len(filters) == len(set(filters))
            indices = [6 + filters.index(b) for b in BANDS]
            for line in lines[header + 1 :]:
                if not line.strip():
                    continue
                numbers = np.array([float(v.rstrip("*")) for v in line.split()])
                assert len(numbers) == 6 + len(filters)
                if 200 <= numbers[0] <= 2400 and 3.25 <= numbers[1] <= 5.5:
                    values.append(10 ** numbers[indices] * 1e6)
    return np.asarray(values), digest(archive)


def dual_projection(a, y):
    # The cone-polar projection has seven variables rather than 1,052
    # amplitudes. It independently supplies the primal optimal distance.
    directions = a / np.linalg.norm(a, axis=0)
    result = minimize(
        lambda r: 0.5 * np.sum((r - y) ** 2),
        np.zeros(len(y)),
        jac=lambda r: r - y,
        method="SLSQP",
        constraints={
            "type": "ineq",
            "fun": lambda r: -(directions.T @ r),
            "jac": lambda r: -directions.T,
        },
        options={"ftol": 1e-11, "maxiter": 1000},
    )
    if not result.success:
        raise ValueError(result.message)
    return result.x


def atmosphere_audit(root, directory):
    grid, archive_pin = actual_grid(root, directory)
    report_path = root / "research_output/survivor46_multiplicity_v1.json"
    report = json.loads(report_path.read_text())
    assert grid.shape == (1052, 7)
    shapes = (grid / grid[:, -1, None]).T
    photo = json.loads((root / "research_output/survivor_deep_model.json").read_text())
    source = next(s for s in photo["sources"] if s["source_id"] == 46)
    y = np.array([b["fixed_extended_fit"]["flux_njy"] for b in source["bands"]])
    assert np.array_equal(y, report["observed_njy"])
    checks = []
    for scenario in report["scenarios"]:
        cov = np.array(scenario["covariance_njy2"])
        lower = np.linalg.cholesky(cov)
        a = solve_triangular(lower, shapes, lower=True)
        target = solve_triangular(lower, y, lower=True)
        saved = scenario["unrestricted_positive_grid_cone"]
        weights = np.array(saved["dual_band_weights_per_njy"])
        projections = shapes.T @ weights
        assert projections.max() < 1e-8
        assert abs(weights @ cov @ weights - 1) < 1e-9
        assert abs((weights @ y) ** 2 - saved["chi2_conditional"]) < 1e-8
        coeff = np.zeros(1052)
        coeff[saved["active_indices"]] = saved["active_f444_amplitudes_njy"]
        prediction = shapes @ coeff
        assert np.max(abs(prediction - saved["prediction_njy"])) < 1e-8
        assert abs(np.sum((target - a @ coeff) ** 2) - saved["chi2_conditional"]) < 1e-8
        polar = dual_projection(a, target)
        assert abs(float(polar @ polar) - saved["chi2_conditional"]) < 1e-6
        pair = scenario["all_pairs"]
        columns = a[:, pair["component_indices"]]
        # Direct QR least squares on the asserted optimum; original exhaustive
        # implementation uses a Gram determinant instead.
        optimum = np.linalg.lstsq(columns, target, rcond=None)[0]
        assert np.all(optimum >= 0)
        pair_loss = float(np.sum((target - columns @ optimum) ** 2))
        assert abs(pair_loss - pair["chi2_conditional"]) < 1e-8
        # Random independent QR interior/boundary pair controls reject a
        # shortlist-only claim; the all-row polar bound certifies the class.
        rng = np.random.default_rng(46)
        minimum = np.inf
        for _ in range(4000):
            idx = rng.choice(1052, 2, replace=False)
            x = a[:, idx]
            b = np.linalg.lstsq(x, target, rcond=None)[0]
            losses = [float(target @ target)]
            if np.all(b >= 0):
                losses.append(float(np.sum((target - x @ b) ** 2)))
            for j in (0, 1):
                amplitude = max(0, float(x[:, j] @ target / (x[:, j] @ x[:, j])))
                losses.append(float(np.sum((target - x[:, j] * amplitude) ** 2)))
            minimum = min(minimum, *losses)
        assert minimum >= pair_loss - 1e-7
        checks.append(
            {
                "floor": scenario["fractional_floor_assumed"],
                "cone_chi2": saved["chi2_conditional"],
                "independent_polar_chi2": float(polar @ polar),
                "all1052_max_dual_projection": float(projections.max()),
                "direct_QR_pair_chi2": pair_loss,
                "random4000_pairs_min": minimum,
            }
        )
    return {
        "archive_sha256": archive_pin,
        "report_sha256": digest(report_path),
        "actual_grid_rows": len(grid),
        "scenarios": checks,
        "scope": (
            "Independent actual-header/unit parsing, all-row dual certificate "
            "and seven-variable polar solver; photometry/floors remain conditional"
        ),
    }


def pixtab_audit(root, directory):
    from astropy.io import fits

    manifest = json.loads((root / "data_sources/author_provenance/manifest.json").read_text())
    pins = {p["id"]: p for p in manifest["products"]}
    table_path = directory / pins["mom-pixtab"]["filename"]
    spectrum_path = root / pins["mom-spectrum"]["repo_path"]
    source_path = directory / pins["msaexp-source"]["filename"]
    for path, key in [
        (table_path, "mom-pixtab"),
        (spectrum_path, "mom-spectrum"),
        (source_path, "msaexp-source"),
    ]:
        assert digest(path) == pins[key]["sha256"]
    with fits.open(table_path, memmap=False) as hdul:
        table = hdul["PIXTAB"].data.copy()
        header = hdul["PIXTAB"].header.copy()
    with fits.open(spectrum_path, memmap=False) as hdul:
        spec = hdul["SPEC1D"].data.copy()
        slits = hdul["SLITS"].data.copy()
        sh = hdul["SCI"].header.copy()
    assert len(table) == 56734 and len(slits) == 9
    assert header["VERSION"] == sh["VERSION"] == "0.9.5.dev8+ge2b237b"
    assert sh["WEIGHT_TYPE"] == "ivm"
    for index, row in enumerate(slits):
        assert str(row["filename"]) == sh[f"SFILE{index:03d}"]
        subset = table[table["exposure_index"] == index]
        assert np.all(subset["exptime"] == row["exposure_time"])
        assert row["source_id"] == 277193
    wave = spec["wave"]
    edges = np.r_[
        wave[0] - (wave[1] - wave[0]) / 2,
        (wave[:-1] + wave[1:]) / 2,
        wave[-1] + (wave[-1] - wave[-2]) / 2,
    ]
    mask = (table["yslit"] >= header["YMIN1D"]) & (table["yslit"] <= header["YMAX1D"])
    t = table[mask]
    bins = np.searchsorted(edges, t["wave"], side="right") - 1
    bins[t["wave"] == edges[-1]] = len(wave) - 1
    use = (bins >= 0) & (bins < len(wave))
    t = t[use]
    bins = bins[use]
    # Direct per-bin coefficient matrix and dot products; no histogram helper.
    counts = np.bincount(bins, minlength=len(wave))
    output = np.full(len(wave), np.nan)
    error = output.copy()
    clipped = output.copy()
    double_pathloss = output.copy()
    for i in range(len(wave)):
        row = t[bins == i]
        if not len(row):
            continue
        w = 1 / row["var_rnoise"]
        profile = row["profile"]
        pathloss = row["pathloss"]
        denominator = np.dot(w, profile**2)
        if denominator == 0:
            continue
        coefficient = w * profile / pathloss / denominator
        output[i] = coefficient @ row["sci"]
        error[i] = np.sqrt((coefficient**2) @ row["var_total"])
        positive = np.maximum(profile, 0)
        clipped[i] = (
            np.sum(row["sci"] * w * positive / pathloss) / np.sum(w * positive**2)
            if np.sum(w * positive**2) > 0
            else np.nan
        )
        double_pathloss[i] = (coefficient / pathloss) @ row["sci"]
    valid = np.isfinite(spec["flux"])
    assert np.array_equal(valid, np.isfinite(output))
    flux_error = float(np.max(abs(output[valid] - spec["flux"][valid])))
    uncertainty_error = float(np.max(abs(error[valid] - spec["err"][valid])))
    assert flux_error < 1e-8 and uncertainty_error < 1e-8
    assert np.array_equal(counts, spec["npix"])
    shared = []
    for i, j in [(0, 3), (0, 6), (1, 4), (2, 5)]:
        a = table[table["exposure_index"] == i]
        b = table[table["exposure_index"] == j]
        values, ia, ib = np.intersect1d(a["sky"], b["sky"], return_indices=True)
        nonzero = values != 0
        different_science = a["sci"][ia] != b["sci"][ib]
        # Many unique nonzero measured sky values recur with *different*
        # science. This cannot be explained by common coordinates/zero fills.
        assert nonzero.sum() > 6200 and different_science.sum() > 6200
        assert np.unique(values).size == len(values)
        assert np.std(values) > 0
        shared.append(
            {
                "pair": [i, j],
                "exact_nonzero_shared_sky_values": int(nonzero.sum()),
                "different_science_at_matching_sky_values": int(different_science.sum()),
                "shared_sky_std": float(np.std(values)),
            }
        )
    for i, j in [(0, 1), (0, 2), (1, 2)]:
        assert (
            np.intersect1d(
                table["sky"][table["exposure_index"] == i],
                table["sky"][table["exposure_index"] == j],
            ).size
            == 0
        )
    source = source_path.read_text()
    assert "ineg = ~self.unp[exp]" in source
    assert "flat_diff.append(self.data[i, :] - neg)" in source
    assert "flat_sky.append(neg)" in source
    clipped_delta = float(np.nanmax(abs(clipped - output)))
    double_delta = float(np.nanmax(abs(double_pathloss - output)))
    assert clipped_delta > 1e-3 and double_delta > 1e-3
    return {
        "pixtab_sha256": digest(table_path),
        "source_sha256": digest(source_path),
        "spectrum_sha256": digest(spectrum_path),
        "direct_dot_flux_max_error_uJy": flux_error,
        "direct_dot_diagonal_error_max_error_uJy": uncertainty_error,
        "exact_all473_bin_counts": True,
        "nonzero_shared_sky_witnesses": shared,
        "clipping_negative_profiles_max_change_uJy": clipped_delta,
        "double_pathloss_max_change_uJy": double_delta,
        "scope": (
            "Actual public intermediate/operator validation; shared background witness, "
            "not recovered masks or covariance or source calibration"
        ),
    }


def deep_replay_audit(root, directory, replay):
    """Compare a new actual-pixel replay without asserting bitwise stability."""
    old = json.loads((root / "research_output/survivor_deep_model.json").read_text())
    fresh = json.loads(replay.read_text())
    differences = []

    def compare(a, b, path=""):
        if isinstance(a, dict):
            assert a.keys() == b.keys()
            for key in a:
                compare(a[key], b[key], path + "/" + key)
        elif isinstance(a, list):
            assert len(a) == len(b)
            for index, (x, y) in enumerate(zip(a, b, strict=True)):
                compare(x, y, path + "/" + str(index))
        elif a != b:
            differences.append((path, a, b))

    compare(old, fresh)
    metadata = [
        item
        for item in differences
        if any(word in item[0] for word in ("acquired", "etag", "last_modified", "utc"))
    ]
    science = [item for item in differences if item not in metadata]
    nonnumeric = [
        item for item in science if not all(isinstance(value, (int, float)) for value in item[1:])
    ]
    numeric = sorted(
        (abs(a - b), path)
        for path, a, b in science
        if isinstance(a, (int, float)) and isinstance(b, (int, float))
    )
    flux_changes = []
    for a, b in zip(old["sources"], fresh["sources"], strict=True):
        deltas = [
            y["fixed_extended_fit"]["flux_njy"] - x["fixed_extended_fit"]["flux_njy"]
            for x, y in zip(a["bands"], b["bands"], strict=True)
        ]
        flux_changes.append(
            {
                "source_id": a["source_id"],
                "fixed_extended_signed_flux_differences_njy": deltas,
                "maximum_fixed_extended_flux_difference_njy": max(map(abs, deltas)),
            }
        )
    grid, _ = actual_grid(root, directory)
    shapes = (grid / grid[:, -1, None]).T
    source = next(row for row in fresh["sources"] if row["source_id"] == 46)
    historical = next(row for row in old["sources"] if row["source_id"] == 46)
    values = np.array([row["fixed_extended_fit"]["flux_njy"] for row in source["bands"]])
    checks = []
    for current, earlier in zip(
        source["phenomenological_continuum_sensitivity"],
        historical["phenomenological_continuum_sensitivity"],
        strict=True,
    ):
        covariance = np.array(current["flux_covariance_njy2"])
        covariance_delta = covariance - np.array(earlier["flux_covariance_njy2"])
        lower = np.linalg.cholesky(covariance)
        a = np.linalg.solve(lower, shapes)
        y = np.linalg.solve(lower, values)
        residual = dual_projection(a, y)
        checks.append(
            {
                "floor": current["independent_fractional_floor"],
                "fresh_thread1_cone_chi2": float(residual @ residual),
                "seven_by_seven_covariance_difference_njy2": covariance_delta.tolist(),
                "maximum_absolute_covariance_difference_njy2": float(np.max(abs(covariance_delta))),
            }
        )
    return {
        "actual_input_pixels": True,
        "replay_sha256": digest(replay),
        "replay_command": "OPENBLAS_NUM_THREADS=1 python -m discovery.survivor_deep_model "
        "--input CACHE/deep --output /tmp/review-deep-replay.json",
        "metadata_difference_count": len(metadata),
        "scientific_numeric_difference_count": len(numeric),
        "maximum_absolute_numeric_difference": numeric[-1][0] if numeric else 0,
        "maximum_difference_path": numeric[-1][1] if numeric else None,
        "non_numeric_scientific_differences": nonnumeric,
        "scientific_flux_sensitivity": flux_changes,
        "source46_refit_cone_sensitivity": checks,
        "scope": "Actual-pixel same-implementation replay and independent polar sensitivity; "
        "no bitwise equality or separate pixel extraction implementation claimed",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--deep", type=Path, required=True)
    parser.add_argument("--author", type=Path, required=True)
    parser.add_argument("--deep-replay", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {
        "schema_version": 1,
        "spectral": spectral_audit(args.root),
        "atmosphere": atmosphere_audit(args.root, args.deep),
        "pixtab": pixtab_audit(args.root, args.author),
        "new_download_bytes": 0,
    }
    if args.deep_replay is not None:
        result["actual_deep_replay"] = deep_replay_audit(args.root, args.deep, args.deep_replay)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
