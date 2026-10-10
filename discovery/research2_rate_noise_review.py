"""Independent actual RATE/CAL error-contract, donor-covariance and GLS audit."""

from __future__ import annotations

import argparse
import ast
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from astropy.io import fits
from scipy.linalg import block_diag, cho_factor, cho_solve
from scipy.special import erf
from scipy.stats import norm

from discovery.research2_medium_review import sha
from discovery.research2_row_response_review import contract, pixel_design
from tools.jwst.line_sensitivity import read_resolution
from tools.jwst.native_reduction import read_inputs
from tools.jwst.point_resolution import read_point_resolution
from tools.jwst.shared_systematics import gls


def source_check(path):
    tree = ast.parse(path.read_text())
    function = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "background_sub"
    )
    writes = []
    for node in ast.walk(function):
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            writes.append(ast.unparse(node))
    namespace = {"log": logging.getLogger(__name__)}
    donor = SimpleNamespace(
        data=np.array([[2.0, 3.0], [5.0, 7.0]]),
        dq=np.full((2, 2), 4, dtype=np.uint32),
        err=np.full((2, 2), 999.0),
    )
    namespace["average_background"] = lambda *args: donor
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
    target = SimpleNamespace(
        data=np.array([[13.0, 17.0], [23.0, 29.0]]),
        dq=np.full((2, 2), 2, dtype=np.uint32),
        err=np.array([[3.0, 5.0], [7.0, 11.0]]),
        var_poisson=np.array([[41.0, 43.0], [47.0, 53.0]]),
        var_rnoise=np.array([[59.0, 61.0], [67.0, 71.0]]),
        meta=SimpleNamespace(filename="independent_oracle"),
    )
    originals = {key: getattr(target, key) for key in ("err", "var_poisson", "var_rnoise")}
    _, result = namespace["background_sub"](target, [], 3.0, None)
    if not np.array_equal(result.data, [[11.0, 14.0], [18.0, 22.0]]) or not np.all(result.dq == 6):
        raise ValueError("Exact primary background function SCI/DQ behavior differs")
    if any(getattr(result, key) is not original for key, original in originals.items()):
        raise ValueError("Background function replaces an error/variance array")
    return {
        "stored_attributes": writes,
        "ERR_VAR_identity_preserved": True,
        "independent_donor_error": 999.0,
    }


def guarded_kernel(lags, positions):
    separation = abs(positions[:, None] - positions[None, :])
    result = np.zeros(separation.shape)
    for lag, value in enumerate(lags):
        result[separation == lag] = value * (1 - lag / len(lags))
    minimum = np.linalg.eigvalsh(result).min()
    shrink = max(0, (0.1 - minimum) / (1 - minimum)) if minimum < 0.1 else 0
    return (1 - shrink) * result + shrink * np.eye(len(positions))


def fresh_controls(data, post, traces, selected):
    blank = np.min(abs(np.arange(28)[None, :, None] - traces[:, None]), axis=0) > 2.5
    controls = np.full((9, 28, 423), np.nan)
    columns = np.zeros(423, bool)
    columns[selected] = True
    for i, d in enumerate(data):
        mask = blank & d["good"] & columns[None]
        raw = d["science"] / np.sqrt(np.where(post[i] > 0, post[i], np.nan))
        for row in range(28):
            valid = mask[row] & np.isfinite(raw[row])
            if valid.sum() >= 20:
                controls[i, row, valid] = raw[row, valid] - raw[row, valid].mean()
    scale = float(np.nanmean(controls**2))
    lags = []
    for dimension in ("spectral", "spatial"):
        moments = [1.0]
        for lag in range(1, 4):
            if dimension == "spectral":
                a, b = controls[:, :, :-lag], controls[:, :, lag:]
            else:
                a, b = controls[:, :-lag, :], controls[:, lag:, :]
            valid = np.isfinite(a) & np.isfinite(b)
            moments.append(float((a[valid] * b[valid]).mean() / scale))
        lags.append(moments)
    return scale, guarded_kernel(lags[0], selected), guarded_kernel(lags[1], np.arange(28)), lags


def donor_blocks(raw, gain, flat, operators, groups, row_kernel):
    covariance = np.zeros((423, 9, 9))
    post = np.zeros_like(raw)
    for group in sorted(set(groups)):
        members = [i for i, g in enumerate(groups) if g == group]
        weights = np.zeros((423, 3, 3, 28))
        for left, i in enumerate(members):
            for donor, j in enumerate(members):
                mix = 1 if left == donor else -0.5
                weights[:, left, donor, :] = (operators[i] * gain[i] * np.sqrt(raw[j]) * mix).T
                post[i] += gain[i] ** 2 * raw[j] * mix**2
            post[i] += flat[i]
        block = np.einsum("cikr,rs,cjks->cij", weights, row_kernel, weights)
        for left, i in enumerate(members):
            f = (operators[i] * np.sqrt(flat[i])).T
            block[:, left, left] += np.einsum("cr,rs,cs->c", f, row_kernel, f)
        covariance[:, np.array(members)[:, None], members] = block
    return covariance, post


def audit(root, native, rate, draws=5000):
    report_path = root / "research_output/mom_native_rate_noise.json"
    expected_hash = "5e9cc7e5e46870f0221c42f762a1186a1396f440e6b34f2b42d5c5fb259d9fc7"
    if sha(report_path) != expected_hash:
        raise ValueError("Frozen d2958d3 artifact differs")
    saved = json.loads(report_path.read_text())
    manifest_path = root / "data_sources/followup/mom_rate_noise_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if sha(manifest_path) != saved["manifest_sha256"]:
        raise ValueError("Frozen manifest identity differs")
    sources = {p["filename"]: p for p in manifest["sources"]}
    for name, pin in sources.items():
        if sha(rate / name) != pin["sha256"] or (rate / name).stat().st_size != pin["bytes"]:
            raise ValueError("Exact JWST2.0.1 primary source differs")
    source = source_check(rate / "background_background_sub.py")
    wrapper_writes = {}
    for name in ("background_background_step.py", "pipeline_calwebb_spec2.py"):
        tree = ast.parse((rate / name).read_text())
        writes = sorted(
            {
                ast.unparse(n)
                for n in ast.walk(tree)
                if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)
            }
        )
        if any(
            x.rsplit(".", 1)[-1] in ("err", "var_poisson", "var_rnoise")
            and not x.startswith("wfss_esec.")
            for x in writes
        ):
            raise ValueError("Pipeline wrapper writes target variance unexpectedly")
        wrapper_writes[name] = writes
    source["wrapper_stored_attributes"] = wrapper_writes
    source["excluded_unrelated_branch"] = (
        "Spec2 updates wfss_esec variance in its WFSS electron-conversion helper; "
        "all nine actual inputs are NRS_MSASPEC, so that branch is inapplicable"
    )
    data, _ = read_inputs(native, root / "data_sources/pilot/mom_z14_dja_v4.spec.fits")
    raw = []
    gains = []
    flats = []
    valid = []
    checks = []
    pins = {p["filename"]: p for p in manifest["products"]}
    for d in data:
        name = d["filename"].replace("_cal", "_rate")
        path = rate / name
        pin = pins[name]
        if sha(path) != pin["sha256"] or path.stat().st_size != pin["bytes"]:
            raise ValueError("Actual RATE whole-file identity differs")
        with fits.open(path, memmap=True) as h:
            primary = h[0].header.copy()
            if (
                primary["CAL_VER"],
                primary["CRDS_CTX"],
                primary["EXP_TYPE"],
                primary["SUBSTRT1"],
                primary["SUBSTRT2"],
                h["SCI"].header["BUNIT"],
            ) != ("2.0.1", "jwst_1535.pmap", "NRS_MSASPEC", 1, 1, "DN/s"):
                raise ValueError("RATE stage/context/unit identity differs")
            crop = {
                key: np.asarray(h[key].data[1292:1320, 439:862], float).copy()
                for key in ("SCI", "ERR", "VAR_RNOISE", "VAR_POISSON")
            }
        with fits.open(native / d["filename"], memmap=False) as h:
            target = next(
                x for x in h if x.name == "SCI" and x.header.get("SRCNAME") == "5224_277193"
            )
            if primary["EXPSTART"] != h[0].header["EXPSTART"] or (
                target.header["SLTSTRT1"],
                target.header["SLTSTRT2"],
            ) != (440, 1293):
                raise ValueError("RATE detector crop/exposure mapping differs")
            version = target.header["EXTVER"]
            conversion = (
                target.header["PIXAR_SR"]
                * 1e12
                * np.asarray(h["PATHLOSS_UN", version].data, float)
                * np.asarray(h["BARSHADOW", version].data, float)
            )
            v = {
                key: np.asarray(h[key, version].data, float) * conversion**2
                for key in ("VAR_RNOISE", "VAR_POISSON", "VAR_FLAT")
            }
        gain = np.sqrt(v["VAR_RNOISE"] / crop["VAR_RNOISE"])
        support = (
            d["good"]
            & np.isfinite(crop["SCI"])
            & np.isfinite(crop["ERR"])
            & (crop["ERR"] > 0)
            & np.isfinite(gain)
            & (gain > 0)
        )
        m = support
        poison = float(np.max(abs(crop["VAR_POISSON"][m] * gain[m] ** 2 / v["VAR_POISSON"][m] - 1)))
        err = float(
            np.max(
                abs((crop["ERR"][m] ** 2 * gain[m] ** 2 + v["VAR_FLAT"][m]) / d["variance"][m] - 1)
            )
        )
        if max(poison, err) > 2e-6:
            raise ValueError("Target-only CAL/RATE error or Poisson closure fails")
        checks.append(
            {
                "filename": name,
                "RATE_sha256": pin["sha256"],
                "target_only_poisson_relative_error": poison,
                "target_only_total_variance_relative_error": err,
            }
        )
        raw.append(crop)
        gains.append(gain)
        flats.append(v["VAR_FLAT"])
        valid.append(support)
    groups = [d["group"] for d in data]
    good = np.array(valid)
    gain = np.array(gains)
    flat = np.array(flats)
    rate_variance = np.array([r["ERR"] ** 2 for r in raw])
    group_checks = []
    for group in sorted(set(groups)):
        members = [i for i, g in enumerate(groups) if g == group]
        common = np.all(good[members], axis=0)
        for i in members:
            gain[i] = np.where(common, gain[i], 0)
            flat[i] = np.where(common, flat[i], 0)
            rate_variance[i] = np.where(common, rate_variance[i], 0)
        closure = []
        for i in members:
            difference = raw[i]["SCI"] - sum(raw[j]["SCI"] for j in members if j != i) / 2
            closure.append(
                float(
                    np.max(
                        abs(
                            (difference[common] * gain[i][common] - data[i]["science"][common])
                            / np.sqrt(data[i]["variance"][common])
                        )
                    )
                )
            )
        group_checks.append(
            {
                "group": group,
                "common_pixels": int(common.sum()),
                "maximum_SCI_error_CAL_sigma": max(closure),
            }
        )
        if max(closure) > 1e-4:
            raise ValueError("Actual RATE signed SCI closure fails")
    wave_report = json.loads((root / "research_output/mom_native_wavecorr.json").read_text())
    with np.load(
        root / "research_output" / wave_report["compact_replay"]["filename"], allow_pickle=False
    ) as cache:
        old = {name: cache[name].copy() for name in cache.files}
    selected = old["selected_columns"]
    geom = json.loads((root / "research_output/mom_native_reduction.json").read_text())["geometry"]
    traces = np.array([d["trace_seed"] + geom["offset_pixels"] for d in data])
    sigma = geom["sigma_pixels"]
    rows = np.arange(28)[None, :, None]
    profiles = 0.5 * (
        erf((rows + 0.5 - traces[:, None]) / (np.sqrt(2) * sigma))
        - erf((rows - 0.5 - traces[:, None]) / (np.sqrt(2) * sigma))
    )
    profiles *= np.array([np.where(d["good"], d["point_pathloss"], 0) for d in data])
    signed = np.array(
        [
            profiles[i]
            - sum(profiles[j] for j in range(9) if groups[i] == groups[j] and j != i) / 2
            for i in range(9)
        ]
    )
    operators = np.zeros_like(profiles)
    values = np.zeros((9, len(selected)))
    for i, d in enumerate(data):
        for cidx, c in enumerate(selected):
            good = d["good"][:, c]
            a = np.column_stack((signed[i, :, c], np.ones(28), (np.arange(28) - 14) / 28))[good]
            e = np.sqrt(d["variance"][good, c])
            inverse = np.linalg.pinv(a / e[:, None], rcond=1e-14)
            operators[i, good, c] = inverse[0] / e
            values[i, cidx] = operators[i, good, c] @ d["science"][good, c]
        if np.any((operators[i] != 0) & (gain[i] == 0)):
            raise ValueError("Frozen extraction weights touch unsupported RATE donor pixels")
    formal, post = donor_blocks(rate_variance, gain, flat, operators, groups, np.eye(28))
    scale, kernel, row_kernel, lags = fresh_controls(data, post, traces, selected)
    spatial, _ = donor_blocks(rate_variance, gain, flat, operators, groups, row_kernel)
    compact_path = root / "research_output" / saved["compact_replay"]["filename"]
    if sha(compact_path) != saved["compact_replay"]["sha256"]:
        raise ValueError("Frozen RATE compact receipt differs")
    with np.load(compact_path, allow_pickle=False) as cache:
        z = {name: cache[name].copy() for name in cache.files}
    compact_errors = {
        "formal_blocks": float(np.max(abs(formal[selected] - z["formal_covariance_blocks"]))),
        "spatial_blocks": float(np.max(abs(spatial[selected] - z["spatial_covariance_blocks"]))),
        "post_variance": float(np.max(abs(post - z["post_diagonal_variance"]))),
        "operators": float(np.max(abs(operators - z["operators"]))),
        "flux": float(np.max(abs(values - z["flux"]))),
        "noise_scale": abs(scale - float(z["noise_scale_squared"][0])),
        "spectral_kernel": float(np.max(abs(kernel - z["spectral_kernel"]))),
    }
    if max(compact_errors.values()) > 1e-9:
        raise ValueError(f"Independent pixel/noise/control arrays differ: {compact_errors}")
    for entry in group_checks:
        members = [i for i, g in enumerate(groups) if g == entry["group"]]
        common = np.all(np.array(valid)[members], axis=0)
        entry["full_over_target_variance_median"] = float(
            np.median((post[members] / np.array([data[i]["variance"] for i in members]))[:, common])
        )
    # Independent Gaussian detector realization pilot; same measured raw ERR, new seed.
    rng = np.random.default_rng(811205)
    detector = np.zeros((draws, len(selected), 9))
    for start in range(0, draws, 100):
        stop = min(start + 100, draws)
        rawdraw = (
            rng.normal(size=(stop - start, 9, 28, len(selected)))
            * np.sqrt(rate_variance[:, :, selected])[None]
        )
        flatdraw = rng.normal(size=rawdraw.shape) * np.sqrt(flat[:, :, selected])[None]
        for i in range(9):
            mixed = (
                rawdraw[:, i]
                - sum(rawdraw[:, j] for j in range(9) if groups[i] == groups[j] and i != j) / 2
            )
            observed = mixed * gain[i, :, selected].T + flatdraw[:, i]
            detector[start:stop, :, i] = np.sum(observed * operators[i][:, selected], axis=1)
    detector = detector.reshape(draws, -1)
    templates = json.loads(
        (root / "research_output/mom_multiplet_components_niv_doublet_v2.json").read_text()
    )
    reference = next(
        r
        for r in templates["records"]
        if (r["temperature_K"], r["electron_density_cm3"]) == (20000, 1000)
    )
    components = [
        (c["vacuum_wavelengths_A"], c["normalized_weights"]) for c in reference["components"]
    ]
    nw, nr, _ = read_resolution(root / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
    pw, pr, _ = read_point_resolution(
        root / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    likelihoods = []
    heldouts = []
    coverage = []
    flat_budgets = []
    atomic = json.loads((root / "research_output/mom_atomic_grid_niv_doublet_v2.json").read_text())
    emissivity = next(
        r["emissivity_erg_cm3_s"]
        for r in atomic["records"]
        if (r["temperature_K"], r["electron_density_cm3"]) == (20000, 1000)
    )
    ionic_projection = np.array(
        [
            [
                emissivity["CIII"] / emissivity["NIV"],
                0,
                0,
                emissivity["CIII"] / emissivity["NIII"],
                0,
            ],
            [0, emissivity["CIII"] / emissivity["CIV"], 0, 0, 1],
        ]
    )
    for corrected in (False, True):
        waves = old["corrected_wave" if corrected else "native_wave"]
        hypothesis = "pinned_toy_prediction" if corrected else "original_native"
        for name, rw, r in (("nominal", nw, nr), ("generic_point", pw, pr)):
            positive = pixel_design(waves, profiles, selected, rw, r, components)
            rawpositive = np.divide(
                positive,
                gain[:, :, :, None],
                out=np.zeros_like(positive),
                where=gain[:, :, :, None] > 0,
            )
            fresh = contract(rawpositive, operators * gain, selected, groups)
            historical = contract(positive, operators, selected, groups)
            for noise, blocks, k, s, d in (
                ("target_only_RATE_formal_v3", formal, np.eye(len(selected)), 1.0, fresh),
                ("target_only_RATE_control_transport_v3", spatial, kernel, scale, fresh),
                (
                    "historical_demixed_control_transport",
                    None,
                    old["spectral_kernel"],
                    old["noise_scale_squared"][0],
                    historical,
                ),
            ):
                b = old["spatial_covariance_blocks"] if blocks is None else blocks[selected]
                factor = block_diag(*[np.linalg.cholesky(block) for block in b])
                covariance = factor @ np.kron(k, np.eye(9)) @ factor.T * s
                answer = gls(d, covariance, values.T.ravel())
                expected = next(
                    x["fit"]
                    for x in saved["fits"]
                    if (x["noise_contract"], x["wavelength_hypothesis"], x["resolution_family"])
                    == (noise, hypothesis, name)
                )
                error = float(np.max(abs(answer[0][2:] - expected["fluxes"])))
                cerr = float(np.max(abs(answer[1][2:, 2:] - expected["flux_covariance"])))
                chi = abs(answer[3] - expected["conditional_chi2"])
                if max(error, cerr, chi) > 1e-7:
                    raise ValueError(
                        f"Independent v3 likelihood differs: {noise, name, error, cerr, chi}"
                    )
                numerator, denominator = ionic_projection @ answer[0][2:]
                ionic_covariance = ionic_projection @ answer[1][2:, 2:] @ ionic_projection.T
                quantile = norm.ppf(0.975) ** 2
                roots = np.sort(
                    np.roots(
                        [
                            denominator**2 - quantile * ionic_covariance[1, 1],
                            -2 * (numerator * denominator - quantile * ionic_covariance[0, 1]),
                            numerator**2 - quantile * ionic_covariance[0, 0],
                        ]
                    )
                )
                if not np.allclose(
                    roots,
                    expected["ionic_N_over_C"]["conditional_gaussian_95_fieller_set"]["interval"],
                    atol=1e-8,
                ):
                    raise ValueError("Independent signed ionic Fieller set differs")
                if noise == "target_only_RATE_control_transport_v3":
                    for group in sorted(set(groups)):
                        test_members = [i for i, g in enumerate(groups) if g == group]
                        train_members = [i for i in range(9) if i not in test_members]
                        subsets = []
                        for members in (train_members, test_members):
                            ids = np.array(
                                [c * 9 + i for c in range(len(selected)) for i in members]
                            )
                            subsets.append(
                                (d[ids], covariance[np.ix_(ids, ids)], values.T.ravel()[ids])
                            )
                        train_a, train_c, train_y = subsets[0]
                        test_a, test_c, test_y = subsets[1]
                        trained = gls(train_a, train_c, train_y)
                        predicted_c = test_c + test_a[:, 2:] @ trained[1][2:, 2:] @ test_a[:, 2:].T
                        residual = test_y - test_a[:, 2:] @ trained[0][2:]
                        precision = cho_factor(predicted_c, lower=True)
                        pa = cho_solve(precision, test_a[:, :2])
                        nuisance = np.linalg.solve(
                            test_a[:, :2].T @ pa, test_a[:, :2].T @ cho_solve(precision, residual)
                        )
                        residual -= test_a[:, :2] @ nuisance
                        statistic = float(residual @ cho_solve(precision, residual))
                        expected_prediction = next(
                            x
                            for x in saved["fresh_control_transport_heldout_predictions"]
                            if (x["group"], x["wavelength_hypothesis"], x["resolution_family"])
                            == (group, hypothesis, name)
                        )
                        difference = abs(statistic - expected_prediction["predictive_chi2"])
                        if difference > 1e-7:
                            raise ValueError("Independent fresh held-out prediction differs")
                        heldouts.append(
                            {
                                "group": group,
                                "wavelength": hypothesis,
                                "resolution": name,
                                "predictive_chi2": statistic,
                                "dof": len(residual) - 2,
                                "author_difference": difference,
                            }
                        )
                likelihoods.append(
                    {
                        "noise_contract": noise,
                        "wavelength": hypothesis,
                        "resolution": name,
                        "flux_max_difference": error,
                        "covariance_max_difference": cerr,
                        "chi2_difference": chi,
                        "signed_ionic_NC_95_Fieller_interval": roots.tolist(),
                        "ambient_ionic_reference_in_interval": bool(
                            roots[0] <= 10**-0.60 <= roots[1]
                        ),
                    }
                )
                if noise == "target_only_RATE_formal_v3":
                    sigma = np.sqrt(answer[1][2, 2])
                    errors = detector @ answer[2][2]
                    cv = float(np.mean(abs(errors) <= norm.ppf(0.975) * sigma))
                    zscore = abs(cv - 0.95) / np.sqrt(0.95 * 0.05 / draws)
                    ratio = float(np.std(errors, ddof=1) / sigma)
                    truth = np.array([2.0, -0.5, 20.0, 15.0, 15.0, 5.0, 12.0])
                    known_error = float(np.max(abs(answer[2] @ (d @ truth) - truth)))
                    if zscore > 4 or abs(ratio - 1) > 0.05 or known_error > 1e-9:
                        raise ValueError("Independent fixed-variance Gaussian pilot fails")
                    coverage.append(
                        {
                            "wavelength": hypothesis,
                            "resolution": name,
                            "draws": draws,
                            "seed": 811205,
                            "NIV_95_coverage": cv,
                            "binomial_sigma_from_95": zscore,
                            "noise_sd_over_formal_sigma": ratio,
                            "known_spectrum_coefficient_error": known_error,
                        }
                    )
                    amp = answer[2][2].reshape(len(selected), 9).T
                    weights = (
                        operators[:, :, selected] * amp[:, None, :] * np.sqrt(flat[:, :, selected])
                    )
                    independ = float(np.sum(weights**2) / sigma**2)
                    sign = np.sign(np.array([d0["science"][:, selected] for d0 in data]))
                    sign = np.where(np.isfinite(sign), sign, 0)
                    common = float(np.sum(np.sum(weights * sign, axis=0) ** 2) / sigma**2)
                    bound = float(np.sum(abs(weights)) ** 2 / sigma**2)
                    expected_flat = next(
                        x
                        for x in saved["recorded_flat_variance_budget"]
                        if (x["wavelength_hypothesis"], x["resolution_family"])
                        == (hypothesis, name)
                    )
                    if not np.allclose(
                        [independ, common, bound],
                        [
                            expected_flat["independent_flat_fraction_of_NIV_variance"],
                            expected_flat[
                                "same_detector_pixel_shared_flat_fraction_of_NIV_variance"
                            ],
                            expected_flat["any_correlation_flat_upper_fraction_of_NIV_variance"],
                        ],
                        rtol=1e-8,
                        atol=1e-12,
                    ):
                        raise ValueError("Independent recorded-flat variance bounds differ")
                    flat_budgets.append(
                        {
                            "wavelength": hypothesis,
                            "resolution": name,
                            "independent_fraction": independ,
                            "same_pixel_shared_fraction": common,
                            "arbitrary_correlation_upper_fraction": bound,
                        }
                    )
    basis = np.zeros((*profiles.shape, 9))
    for i in range(9):
        basis[i, :, :, i] = profiles[i]
    coupling = contract(
        np.divide(
            basis, gain[:, :, :, None], out=np.zeros_like(basis), where=gain[:, :, :, None] > 0
        ),
        operators * gain,
        selected,
        groups,
    ).reshape(len(selected), 9, 9)
    coupling_error = float(np.max(abs(coupling - z["signed_response_coupling"])))
    if coupling_error > 1e-12:
        raise ValueError("Independent gain-corrected donor response coupling differs")
    return {
        "schema_version": 1,
        "frozen_author_commit": "d2958d3d87e725b3e3159b461f75e4c51bb73610",
        "author_artifact_sha256": sha(report_path),
        "author_compact_sha256": sha(compact_path),
        "review_code_sha256": sha(Path(__file__)),
        "source_contract": source,
        "RATE_CAL_checks": checks,
        "group_checks": group_checks,
        "compact_max_differences": compact_errors,
        "signed_gain_response_coupling_max_difference": coupling_error,
        "fresh_offsource_scale_squared": scale,
        "fresh_spectral_and_spatial_lags": lags,
        "twelve_fixed_likelihoods": likelihoods,
        "twelve_fresh_heldout_predictions": heldouts,
        "independent_raw_Gaussian_coverage": coverage,
        "recorded_flat_variance_bounds": flat_budgets,
        "approval": (
            "Conditional target-only variance and fresh donor-noise transport validated; "
            "empirical source covariance remains assumed"
        ),
        "new_download_bytes": 0,
        "scope": [
            "Exact pipeline source and actual RATE/CAL falsify post-subtraction CALERR demixing",
            (
                "Measured target calibration gains transported through source ghosts "
                "and raw donor variance; no second CAL subtraction"
            ),
            (
                "RATE ERR Gaussian and independent recorded VAR_FLAT are fixed noise assumptions, "
                "not source Poisson recalibration"
            ),
            (
                "Off-source stationary row/column kernel transported to source is conditional; "
                "three groups do not calibrate shared systematics"
            ),
            "Recorded diagonal VAR_FLAT bounds do not bound unrecorded common calibration errors",
            "No empirical absolute wavelength/LSF or elemental abundance identification",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "native", "rate", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(audit(args.root, args.native, args.rate), indent=2, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    main()
