"""Independent full-data SVD review of a physical Cloudy likelihood.

Uses the previously reviewed bin integration helper, but not the author's
composition prediction, covariance transport, or two-stage fitting functions.
This is compact numerical replay, not a new detector reduction.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from astropy.io import fits
from scipy.linalg import block_diag
from scipy.stats import chi2

from discovery.continuation_wavecorr_review import bin_design, source_waves
from discovery.research2_cloudy_model_review import UV_GROUPS
from discovery.research2_independent_review import digest, svd_fit


def constrained_full_fit(design, covariance, values, ratios):
    physical = np.column_stack((design[:, :2], design[:, 2:] @ ratios))
    beta, parameter_covariance, _, statistic = svd_fit(physical, covariance, values)
    if beta[-1] < 0:
        nuisance, _, _, statistic = svd_fit(physical[:, :2], covariance, values)
        beta = np.r_[nuisance, 0.0]
    return beta, parameter_covariance, statistic


def audit(root, report_path):
    report = json.loads(report_path.read_text())
    wave_report = json.loads((root / "research_output/mom_native_wavecorr.json").read_text())
    compact = root / "research_output" / wave_report["compact_replay"]["filename"]
    assert digest(compact) == wave_report["compact_replay"]["sha256"]
    with np.load(compact, allow_pickle=False) as saved:
        z = {key: saved[key].copy() for key in saved.files}
    receipt = json.loads((root / "research_output/mom_cloudy_signed_coupling.json").read_text())
    coupling_path = root / "research_output" / receipt["filename"]
    assert digest(coupling_path) == receipt["sha256"]
    with np.load(coupling_path, allow_pickle=False) as saved:
        coupling = saved["coupling"].copy()
        assert np.array_equal(saved["selected"], z["selected_columns"])
    with fits.open(root / "data_sources/pilot/jwst_nirspec_prism_disp.fits") as hdul:
        nominal = (np.asarray(hdul[1].data["WAVELENGTH"]), np.asarray(hdul[1].data["R"]))
    point = np.loadtxt(
        root / "data_sources/followup/unite_point_prism_resolution.csv",
        delimiter=",",
        skiprows=1,
        usecols=(0, 1),
    ).T
    models = {model["id"]: model for model in report["models"]}
    wavelengths = np.array(
        [float(line.rsplit(" ", 1)[1][:-1]) for group in UV_GROUPS for line in group]
    )
    selections = [slice(0, 2), slice(2, 4), slice(4, 7), slice(7, 12), slice(12, 14)]
    records = []
    for alternative in report["native_likelihood"]["alternatives"]:
        corrected = alternative["wavelength_hypothesis"] == "pinned_toy_prediction"
        waves = source_waves(
            z["corrected_wave"] if corrected else z["native_wave"],
            z["native_good"],
            z["trace"],
            z["sigma"][0],
        )
        blocks = (
            z["spatial_covariance_blocks"]
            if alternative["noise"] == "empirical_rows_and_columns"
            else z["covariance_blocks"]
        )
        factor = block_diag(*[np.linalg.cholesky(block) for block in blocks])
        empirical = alternative["noise"] != "formal_shared"
        kernel = z["spectral_kernel"] if empirical else np.eye(70)
        covariance = factor @ np.kron(kernel, np.eye(9)) @ factor.T
        covariance *= z["noise_scale_squared"][0] if empirical else 1.0
        values = z["flux"].T.ravel()
        rw, rr = point if alternative["resolution"] == "generic_point" else nominal
        for row in alternative["records"]:
            model = models[row["model_id"]]
            lines = np.asarray(model["intrinsic_line_values"])[:14].copy()
            if len(lines) != 14 or np.any(lines < 0) or not np.isfinite(lines).all():
                raise ValueError("Complete finite physical line vector required")
            lines *= np.exp(-0.4 * np.log(10) * row["A1500_mag"] * (wavelengths / 1500) ** -1.2)
            totals = np.array([lines[selection].sum() for selection in selections])
            if np.any(totals <= 0):
                raise ValueError("Missing group cannot be replaced with zero")
            ratios = totals / totals[-1]
            components = [
                (wavelengths[s], lines[s] / total) for s, total in zip(selections, totals)
            ]
            assert np.max(abs(ratios - row["prediction_relative_CIII"])) < 1e-14
            direct = bin_design(waves, z["selected_columns"], rw, rr, components)
            design = np.einsum("cij,cjk->cik", coupling, direct.reshape(70, 9, 7)).reshape(630, 7)
            unconstrained, pcov, _, q = svd_fit(design, covariance, values)
            beta, physical_covariance, statistic = constrained_full_fit(
                design, covariance, values, ratios
            )
            errors = [
                abs(statistic - row["full_native_profiled_chi2"]),
                abs(q - row["native_fit"]["conditional_chi2"]),
                float(np.max(abs(unconstrained[2:] - row["native_fit"]["fluxes"]))),
                float(np.max(abs(pcov[2:, 2:] - row["native_fit"]["flux_covariance"]))),
                abs(beta[2] - row["common_nonnegative_normalization"]),
                abs(physical_covariance[2, 2] ** 0.5 - row["conditional_normalization_sigma"]),
            ]
            assert max(errors) < 1e-8, errors
            records.append(
                {
                    "wavelength": alternative["wavelength_hypothesis"],
                    "noise": alternative["noise"],
                    "resolution": alternative["resolution"],
                    "model_id": row["model_id"],
                    "A1500_mag": row["A1500_mag"],
                    "full_data_chi2": statistic,
                    "group_restriction_delta_chi2": statistic - q,
                    "fixed_model_conditional_tail_627df": float(chi2.sf(statistic, 627)),
                    "max_numerical_error": max(errors),
                }
            )
    return {
        "schema_version": 1,
        "report_sha256": digest(report_path),
        "coupling_sha256": digest(coupling_path),
        "compact_sha256": digest(compact),
        "records": records,
        "max_numerical_error": max(r["max_numerical_error"] for r in records),
        "scope": (
            "Independent direct full-630-datum constrained SVD solve; shared reviewed bin "
            "helper and frozen signed Q. Fixed-model Gaussian tails are conditional "
            "diagnostics, not calibration, model-selection probabilities or an abundance posterior."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.root, args.report), indent=2) + "\n")


if __name__ == "__main__":
    main()
