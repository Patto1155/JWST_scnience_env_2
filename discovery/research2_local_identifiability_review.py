"""Independent full-row twelve-case and calibration-equivalence oracle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.linalg import block_diag, cho_factor, cho_solve, solve_triangular
from scipy.special import erf
from scipy.stats import norm

from discovery.continuation_wavecorr_review import linear_extrapolation
from discovery.research2_medium_review import sha
from discovery.research2_row_response_review import contract
from tools.jwst.native_reduction import read_inputs
from tools.jwst.point_resolution import read_point_resolution
from tools.jwst.shared_systematics import gls

SCENARIOS = (
    ("baseline", 14.44, 0.0, 1),
    ("redshift_low", 14.42, 0.0, 1),
    ("redshift_high", 14.46, 0.0, 1),
    ("width_300", 14.44, 300.0, 1),
    ("width_1000", 14.44, 1000.0, 1),
    ("quadratic_continuum", 14.44, 0.0, 2),
)


def forward(
    waves,
    profiles,
    operators,
    gains,
    groups,
    selected,
    rw,
    r,
    components,
    redshift=14.44,
    width=0.0,
    order=1,
    lsf_scale=1.0,
    equivalent_width=0.0,
):
    count, rows, columns = profiles.shape
    result = np.zeros((count, rows, columns, order + 6))
    for i in range(count):
        for row in range(rows):
            if not np.any(profiles[i, row]):
                continue
            raw = waves[i, row]
            where = np.flatnonzero(np.isfinite(raw) & (raw > 0))
            wave = linear_extrapolation(np.arange(columns), where, raw[where])
            edges = np.r_[
                wave[0] - (wave[1] - wave[0]) / 2,
                (wave[:-1] + wave[1:]) / 2,
                wave[-1] + (wave[-1] - wave[-2]) / 2,
            ]
            x = (wave - 2.675) / 0.525
            continuum = [np.ones(columns) / 100, x / 100]
            if order == 2:
                continuum.append((3 * x * x - 1) / 200)
            lines = []
            for rests, weights in components:
                density = np.zeros(columns)
                weights = np.array(weights) / np.sum(weights)
                for rest, weight in zip(rests, weights, strict=True):
                    center = rest * 1e-4 * (1 + redshift)
                    resolving = np.interp(center, rw, r)
                    if equivalent_width:
                        resolving = 1 / np.hypot(1 / resolving, equivalent_width / 299792.458)
                    fwhm = center * np.hypot(lsf_scale / resolving, width / 299792.458)
                    sd = fwhm / (2 * np.sqrt(2 * np.log(2)))
                    density += (
                        weight
                        * 0.5
                        * np.diff(erf((edges - center) / (np.sqrt(2) * sd)))
                        / np.diff(edges)
                    )
                lines.append(density * wave**2 / 299792.458)
            result[i, row] = np.column_stack(continuum + lines) * profiles[i, row, :, None]
    raw = np.divide(
        result, gains[:, :, :, None], out=np.zeros_like(result), where=gains[:, :, :, None] > 0
    )
    return contract(raw, operators * gains, selected, groups)


def audit(root, native):
    path = root / "research_output/mom_native_local_identifiability.json"
    if sha(path) != "36538f611670eed232c07064fc731e90c88211e384a34b5054fa35441cb45ce2":
        raise ValueError("Frozen local-identifiability author artifact differs")
    author = json.loads(path.read_text())
    if author["fitted_comparisons"] != 12:
        raise ValueError("Declared fitted comparison count differs")
    rate_path = root / "research_output/mom_native_rate_noise.json"
    if sha(rate_path) != "5e9cc7e5e46870f0221c42f762a1186a1396f440e6b34f2b42d5c5fb259d9fc7":
        raise ValueError("Frozen previously independently validated RATE v3 input differs")
    rate = json.loads(rate_path.read_text())
    compact = rate_path.parent / rate["compact_replay"]["filename"]
    if sha(compact) != "4d679850b44b28ed3d8fc71f0e7fd41f0aa7a7cfcd95aff896de97b728bdfa5e":
        raise ValueError("Frozen gain/operator/covariance snapshot differs")
    with np.load(compact, allow_pickle=False) as cache:
        a = {k: cache[k].copy() for k in cache.files}
    selected = a["selected_columns"]
    values = a["flux"].T.ravel()
    factor = block_diag(*[np.linalg.cholesky(block) for block in a["spatial_covariance_blocks"]])
    covariance = (
        factor @ np.kron(a["spectral_kernel"], np.eye(9)) @ factor.T * a["noise_scale_squared"][0]
    )
    data, _ = read_inputs(native, root / "data_sources/pilot/mom_z14_dja_v4.spec.fits")
    waves = np.array([d["wave"] for d in data])
    groups = [d["group"] for d in data]
    geometry = json.loads((root / "research_output/mom_native_reduction.json").read_text())[
        "geometry"
    ]
    traces = np.array([d["trace_seed"] + geometry["offset_pixels"] for d in data])
    sigma = geometry["sigma_pixels"]
    yy = np.arange(28)[None, :, None]
    profiles = 0.5 * (
        erf((yy + 0.5 - traces[:, None]) / (np.sqrt(2) * sigma))
        - erf((yy - 0.5 - traces[:, None]) / (np.sqrt(2) * sigma))
    )
    profiles *= np.array([np.where(d["good"], d["point_pathloss"], 0) for d in data])
    table = json.loads(
        (root / "research_output/mom_multiplet_components_niv_doublet_v2.json").read_text()
    )
    cell = next(
        x
        for x in table["records"]
        if (x["temperature_K"], x["electron_density_cm3"]) == (20000, 1000)
    )
    components = [(g["vacuum_wavelengths_A"], g["normalized_weights"]) for g in cell["components"]]
    rw, r, _ = read_point_resolution(
        root / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    atomic = json.loads((root / "research_output/mom_atomic_grid_niv_doublet_v2.json").read_text())
    e = next(
        x["emissivity_erg_cm3_s"]
        for x in atomic["records"]
        if (x["temperature_K"], x["electron_density_cm3"]) == (20000, 1000)
    )
    projection = np.array(
        [[e["CIII"] / e["NIV"], 0, 0, e["CIII"] / e["NIII"], 0], [0, e["CIII"] / e["CIV"], 0, 0, 1]]
    )

    def mean(**kwargs):
        return forward(
            waves,
            profiles,
            a["operators"],
            a["calibration_gain"],
            groups,
            selected,
            rw,
            r,
            components,
            **kwargs,
        )

    fits = []
    designs = {}
    answers = {}
    predictions = []
    counterexamples = []
    for name, z, width, order in SCENARIOS:
        design = mean(redshift=z, width=width, order=order)
        answer = gls(design, covariance, values)
        designs[name] = design
        answers[name] = answer
        saved = next(x["fit"] for x in author["fits"] if x["scenario"] == name)
        start = order + 1
        df = float(np.max(abs(answer[0][start:] - saved["fluxes"])))
        dc = float(np.max(abs(answer[1][start:, start:] - saved["flux_covariance"])))
        chi = abs(answer[3] - saved["conditional_chi2"])
        if max(df, dc, chi) > 1e-7:
            raise ValueError(f"Independent twelve-case likelihood differs {name}: {df, dc, chi}")
        n, c = projection @ answer[0][start:]
        v = projection @ answer[1][start:, start:] @ projection.T
        q = norm.ppf(0.975) ** 2
        roots = np.sort(
            np.roots([c * c - q * v[1, 1], -2 * (n * c - q * v[0, 1]), n * n - q * v[0, 0]])
        )
        fieller = saved["ionic_N_over_C"]["conditional_gaussian_95_fieller_set"]
        if c * c - q * v[1, 1] <= 0 or "interval" not in fieller:
            raise ValueError("Declared bounded signed ionic set is not bounded")
        if not np.allclose(roots, fieller["interval"], atol=1e-8):
            raise ValueError("Independent ionic Fieller set differs")
        fits.append(
            {
                "scenario": name,
                "flux_max_difference": df,
                "covariance_max_difference": dc,
                "chi2_difference": chi,
                "NIV_flux": float(answer[0][start]),
                "NIV_conditional_sigma": float(np.sqrt(answer[1][start, start])),
                "signed_ionic_Fieller_roots": roots.tolist(),
                "denominator_quadratic_coefficient": float(c * c - q * v[1, 1]),
            }
        )
    for group in sorted(set(groups)):
        test = [i for i, g in enumerate(groups) if g == group]
        train = [i for i in range(9) if i not in test]
        ti = np.array([c * 9 + i for c in range(len(selected)) for i in train])
        vi = np.array([c * 9 + i for c in range(len(selected)) for i in test])
        for name in ("baseline", "width_1000"):
            design = designs[name]
            trained = gls(design[ti], covariance[np.ix_(ti, ti)], values[ti])
            test_a = design[vi]
            predcov = (
                covariance[np.ix_(vi, vi)] + test_a[:, 2:] @ trained[1][2:, 2:] @ test_a[:, 2:].T
            )
            residual = values[vi] - test_a[:, 2:] @ trained[0][2:]
            precision = cho_factor(predcov, lower=True)
            nuisance = np.linalg.solve(
                test_a[:, :2].T @ cho_solve(precision, test_a[:, :2]),
                test_a[:, :2].T @ cho_solve(precision, residual),
            )
            residual -= test_a[:, :2] @ nuisance
            chi = float(residual @ cho_solve(precision, residual))
            saved = next(
                x["prediction"]
                for x in author["held_out_predictions"]
                if (x["scenario"], x["held_out_RATE_group"]) == (name, group)
            )
            difference = abs(chi - saved["predictive_chi2"])
            if difference > 1e-7:
                raise ValueError("Independent held-out group prediction differs")
            predictions.append(
                {"scenario": name, "group": group, "predictive_chi2": chi, "difference": difference}
            )
    for width in (300.0, 1000.0):
        equivalent = mean(equivalent_width=width)
        error = float(np.max(abs(equivalent - designs[f"width_{int(width)}"])))
        if error > 1e-12:
            raise ValueError("Independent pointwise Gaussian LSF equivalence fails")
        counterexamples.append({"intrinsic_FWHM_kms": width, "equivalent_response_error": error})
    centroid = []
    for z, name in ((14.42, "redshift_low"), (14.46, "redshift_high")):
        epsilon = (1 + z) / 15.44 - 1
        shifted = [(np.array(rest) * (1 + epsilon), weight) for rest, weight in components]
        equivalent = forward(
            waves, profiles, a["operators"], a["calibration_gain"], groups, selected, rw, r, shifted
        )
        error = float(np.max(abs(equivalent - designs[name])))
        if error > 1e-12:
            raise ValueError("Independent centroid convention equivalence fails")
        centroid.append({"redshift": z, "epsilon": epsilon, "equivalent_response_error": error})
    beta = answers["baseline"][0]
    changes = np.column_stack(
        [
            (designs["redshift_high"] - designs["redshift_low"]) @ beta / 2,
            (designs["width_300"] - designs["baseline"]) @ beta,
            (mean(lsf_scale=1.01) - mean(lsf_scale=0.99)) @ beta / 2,
            designs["quadratic_continuum"][:, 2],
        ]
    )
    chol = np.linalg.cholesky(covariance)
    basis = solve_triangular(chol, designs["baseline"], lower=True)
    white = solve_triangular(chol, changes, lower=True)
    residual = white - basis @ np.linalg.solve(basis.T @ basis, basis.T @ white)
    norms = np.linalg.norm(residual, axis=0)
    cosines = residual.T @ residual / np.outer(norms, norms)
    singular = np.linalg.svd(residual, compute_uv=False)
    local = author["local_plugin_diagnostics"]
    if (
        not np.allclose(norms, local["projected_plugin_SNR"], atol=1e-8)
        or not np.allclose(cosines, local["projected_cosines"], atol=1e-8)
        or not np.allclose(singular, local["projected_singular_values"], atol=1e-8)
    ):
        raise ValueError("Independent normal projection local diagnostics differ")
    return {
        "schema_version": 1,
        "approval": "independent numerical and scope review passed",
        "author_commit": "b44f2192538ae23ccc822901d2d20982ca750d87",
        "author_artifact_sha256": sha(path),
        "review_code_sha256": sha(Path(__file__)),
        "frozen_RATE_json_sha256": sha(rate_path),
        "frozen_RATE_npz_sha256": sha(compact),
        "six_full_likelihoods": fits,
        "six_heldout_predictions": predictions,
        "independent_width_LSF_counterexamples": counterexamples,
        "independent_centroid_counterexamples": centroid,
        "local_plugin_projected_SNR": norms.tolist(),
        "local_plugin_cosines": cosines.tolist(),
        "local_plugin_singular_values": singular.tolist(),
        "new_download_bytes": 0,
        "scope": [
            (
                "Actual nine CAL wavelength rows/profiles; reused exact RATE gain/operator/"
                "covariance snapshot already independently reproduced from nine RATE/CAL pairs"
            ),
            (
                "Independent erf bin integration, donor contraction, normal GLS, precision-profile "
                "predictions and normal nuisance projection"
            ),
            (
                "The Gaussian LSF and centroid conventions are mathematical confounders, "
                "not empirical calibration"
            ),
            (
                "Sensitivity scales and line amplitudes are conditional plug-in choices; "
                "no invariant Fisher or calibrated posterior"
            ),
            (
                "Pooled off-source covariance uses all groups; amplitude prediction is not "
                "wholly held-out calibration"
            ),
            (
                "No source Poisson coverage, elemental abundance, source-specific LSF or "
                "absolute redshift identified"
            ),
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
