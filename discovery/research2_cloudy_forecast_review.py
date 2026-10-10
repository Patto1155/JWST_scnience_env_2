"""Independent complete-model Gaussian forecast and extra-stage range oracle.

The CLI requires exact frozen input and output pins. It does not acquire inputs,
run Cloudy or inspect actual forecasts until those immutable artifacts exist.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

import numpy as np
from astropy.io import fits
from scipy.integrate import quad

from discovery.research2_medium_review import sha

GROUPS = {
    "NIV": (0, 1),
    "CIV": (2, 3),
    "HeII_OIII": (4, 5, 6),
    "NIII": (7, 8, 9, 10, 11),
    "CIII": (12, 13),
}
N_KEY = "log_NC_relative_minus060"
EXPECTED_UV = (
    ("N  4", 1483.32),
    ("N  4", 1486.50),
    ("C  4", 1548.19),
    ("C  4", 1550.77),
    ("He 2", 1640.41),
    ("O  3", 1660.81),
    ("O  3", 1666.15),
    ("N  3", 1746.82),
    ("N  3", 1748.65),
    ("N  3", 1749.67),
    ("N  3", 1752.16),
    ("N  3", 1753.99),
    ("C  3", 1906.68),
    ("C  3", 1908.73),
)


def normalized(models, indices, attenuation, response, rests):
    values = np.array([m[response] for m in models])[:, indices]
    result = []
    identities = []
    for index, model in enumerate(models):
        for screen in attenuation:
            energy = values[index] * np.exp(-np.log(10) * 0.4 * screen * (rests / 1500) ** -1.2)
            if not np.all(np.isfinite(energy)) or np.any(energy < 0) or energy.sum() <= 0:
                raise ValueError("Missing/negative or zero bundle energy")
            result.append(energy / energy.sum())
            identities.append((model["id"], screen))
    return np.array(result), identities


def product_integrals(centers, sigma):
    """Integrate Gaussian products by completing their quadratic square."""
    precisions = 1 / sigma**2
    combined_precision = precisions[:, None] + precisions[None, :]
    combined_center = (
        centers[:, None] * precisions[:, None] + centers[None, :] * precisions[None, :]
    ) / combined_precision
    offset = (
        precisions[:, None] * (centers[:, None] - combined_center) ** 2
        + precisions[None, :] * (centers[None, :] - combined_center) ** 2
    )
    return np.exp(-offset / 2) / (
        np.sqrt(2 * np.pi * combined_precision) * sigma[:, None] * sigma[None, :]
    )


def distances(truths, alternatives, gram):
    tnorm = np.einsum("ij,jk,ik->i", truths, gram, truths)
    anorm = np.einsum("ij,jk,ik->i", alternatives, gram, alternatives)
    cross = truths @ gram @ alternatives.T
    amplitudes = np.maximum(0, cross / anorm[None, :])
    residual = truths[:, None, :] - amplitudes[:, :, None] * alternatives[None, :, :]
    fractions = np.einsum("abj,jk,abk->ab", residual, gram, residual) / tnorm[:, None]
    return amplitudes, np.maximum(0, fractions)


def quadrature(centers, sigma, truth, alternative, amplitude):
    """Direct continuous profiles; no Gaussian overlap formula used."""
    low, high = float(np.min(centers - 12 * sigma)), float(np.max(centers + 12 * sigma))
    points = np.unique(
        np.clip((centers[:, None] + sigma[:, None] * [-8, -3, -1, 0, 1, 3, 8]).ravel(), low, high)
    )

    def spectrum(wavelength, weights):
        density = np.exp(-0.5 * ((wavelength - centers) / sigma) ** 2)
        return float(weights @ (density / (np.sqrt(2 * np.pi) * sigma)))

    def integrate(function):
        return quad(
            function,
            low,
            high,
            points=points,
            epsabs=1e-11,
            epsrel=1e-10,
            limit=500,
        )[0]

    tt = integrate(lambda wave: spectrum(wave, truth) ** 2)
    aa = integrate(lambda wave: spectrum(wave, alternative) ** 2)
    ta = integrate(lambda wave: spectrum(wave, truth) * spectrum(wave, alternative))
    optimum = max(0, ta / aa)
    residual_norm = integrate(
        lambda wave: (spectrum(wave, truth) - amplitude * spectrum(wave, alternative)) ** 2
    )
    return optimum, residual_norm / tt


def environment(model):
    return sorted((key, value) for key, value in model["parameters"].items() if key != N_KEY)


def audit(root, input_path, forecast_path, input_sha, forecast_sha, author_commit):
    started = time.monotonic()
    if len(author_commit) != 40:
        raise ValueError("Exact frozen author revision required")
    if sha(input_path) != input_sha or sha(forecast_path) != forecast_sha:
        raise ValueError("Frozen input/forecast hash differs")
    pilot = json.loads(input_path.read_text())
    saved = json.loads(forecast_path.read_text())
    frozen_output = subprocess.check_output(
        ["git", "show", f"{author_commit}:{forecast_path.resolve().relative_to(root.resolve())}"],
        cwd=root,
    )
    if frozen_output != forecast_path.read_bytes():
        raise ValueError("Forecast differs from exact author revision")
    merged_revision = saved["validated_merged_input_revision"]
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", merged_revision, "origin/master"],
        cwd=root,
        check=True,
    )
    committed_input = subprocess.check_output(
        ["git", "show", f"{merged_revision}:{input_path.resolve().relative_to(root.resolve())}"],
        cwd=root,
    )
    if committed_input != input_path.read_bytes():
        raise ValueError("Complete input differs from independently validated merged revision")
    report_path = root / "docs/MOM_CLOUDY_OBSERVATION_CONTRASTS.md"
    frozen_report = subprocess.check_output(
        ["git", "show", f"{author_commit}:docs/MOM_CLOUDY_OBSERVATION_CONTRASTS.md"], cwd=root
    )
    if frozen_report != report_path.read_bytes():
        raise ValueError("Author report differs from frozen reviewed snapshot")
    plan_path = root / "data_sources/pilot/observation_design/cloudy_contrast_plan.json"
    plan = json.loads(plan_path.read_text())
    if sha(plan_path) != saved["input_plan_sha256"] or saved["input_sha256"] != input_sha:
        raise ValueError("Author artifact pins differ")
    if len(pilot["models"]) != 20 or not pilot["complete_thermal_solution_per_composition"]:
        raise ValueError("Complete twenty-model thermal contract required")
    lines = pilot["lines"]
    if tuple(tuple(row) for row in lines[:14]) != EXPECTED_UV:
        raise ValueError("UV component identities differ")
    if lines[22:] != [
        ["N  5", 1238.82],
        ["N  5", 1242.80],
        ["C  2", 2323.50],
        ["C  2", 2324.69],
        ["C  2", 2325.40],
        ["C  2", 2326.93],
        ["C  2", 2328.12],
    ]:
        raise ValueError("Extra-stage component identities differ")
    if len(lines) != 29 or pilot["line_wavelength_medium"] != [
        "air" if wave > 2000 else "vacuum" for _, wave in lines
    ]:
        raise ValueError("Complete line/medium metadata required")
    if pilot["intrinsic_line_unit"] != "erg s^-1 cm^-2; Cloudy intensity geometry":
        raise ValueError("Unexpected energy unit")
    if pilot["ordinary_reference_log_NC"] != -0.60 or pilot["reference_log_CO"] != -0.37:
        raise ValueError("Declared custom composition reference differs")
    for model in pilot["models"]:
        abundance = model["actual_gas_abundances"]
        n = abundance["NITR"]["actual_printed_log_XH"]
        c = abundance["CARB"]["actual_printed_log_XH"]
        o = abundance["OXYG"]["actual_printed_log_XH"]
        if abs(n - c - (-0.60 + model["parameters"][N_KEY])) > 0.0101:
            raise ValueError("Printed composition nitrogen/carbon differs")
        if abs(c - o + 0.37) > 0.0101:
            raise ValueError("Printed composition carbon/oxygen differs")
    expected_cases = {
        (response, bundle["name"], mode, width)
        for response in ("intrinsic_line_values", "emergent_line_values")
        for bundle in plan["bundles"]
        for mode in ("g235m", "g235h")
        for width in plan["intrinsic_fwhm_km_s"]
    }
    actual_cases = {
        (case["response"], case["bundle"], case["mode"], case["intrinsic_fwhm_km_s"])
        for case in saved["cases"]
    }
    if len(saved["cases"]) != 48 or actual_cases != expected_cases:
        raise ValueError("Declared forecast cases differ")
    ordinary = [m for m in pilot["models"] if m["parameters"][N_KEY] == 0]
    enhanced = [m for m in pilot["models"] if m["parameters"][N_KEY] == 1]
    if len(ordinary) != 10 or len(enhanced) != 10:
        raise ValueError("Ten members of each composition required")
    receipt_path = plan_path.parent / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    curves = {}
    for record in receipt["records"]:
        if not record["name"].endswith(".fits"):
            continue
        path = plan_path.parent / record["name"]
        if sha(path) != record["sha256"] or path.stat().st_size != record["bytes"]:
            raise ValueError("Nominal response identity differs")
        with fits.open(path) as file:
            curves[record["name"].split("_")[2]] = (
                np.array(file[1].data["WAVELENGTH"], float),
                np.array(file[1].data["R"], float),
            )
    summaries = []
    for case in saved["cases"]:
        bundle = next(b for b in plan["bundles"] if b["name"] == case["bundle"])
        indices = tuple(i for group in bundle["groups"] for i in GROUPS[group])
        rests = np.array([lines[index][1] for index in indices])
        centers = rests * 15.44 / 1e4
        if list(indices) != case["component_indices"] or not np.allclose(
            centers, case["component_wavelengths_observed_um"], atol=1e-14, rtol=0
        ):
            raise ValueError("Component mapping or wavelength units differ")
        wavelength, resolving_power = curves[case["mode"]]
        if centers.min() < max(1.66, wavelength.min()) or centers.max() > min(
            3.17, wavelength.max()
        ):
            raise ValueError("Target outside nominal mode coverage")
        sigma = (
            centers
            / np.sqrt(8 * np.log(2))
            * np.hypot(
                1 / np.interp(centers, wavelength, resolving_power),
                case["intrinsic_fwhm_km_s"] / 299792.458,
            )
        )
        gram = product_integrals(centers, sigma)
        truth, tids = normalized(
            enhanced, indices, plan["attenuation_A1500_mag"], case["response"], rests
        )
        alternative, aids = normalized(
            ordinary, indices, plan["attenuation_A1500_mag"], case["response"], rests
        )
        amplitudes, fractions = distances(truth, alternative, gram)
        records = []
        count = len(plan["attenuation_A1500_mag"])
        for t, tmodel in enumerate(enhanced):
            for a, amodel in enumerate(ordinary):
                subset = fractions[t * count : (t + 1) * count, a * count : (a + 1) * count]
                tlocal, alocal = np.unravel_index(np.argmin(subset), subset.shape)
                ti, ai = int(t * count + tlocal), int(a * count + alocal)
                records.append(
                    {
                        "truth": tmodel["id"],
                        "alternative": amodel["id"],
                        "truth_attenuation": tids[ti][1],
                        "alternative_attenuation": aids[ai][1],
                        "fraction": float(fractions[ti, ai]),
                        "amplitude": float(amplitudes[ti, ai]),
                        "same_environment": environment(tmodel) == environment(amodel),
                        "truth_index": ti,
                        "alternative_index": ai,
                    }
                )
        closest = min(records, key=lambda row: row["fraction"])
        paired = [row for row in records if row["same_environment"]]
        hardest = min(paired, key=lambda row: row["fraction"])
        author_hardest = case["hardest_matched_environment"]
        if (hardest["truth"], hardest["alternative"]) != (
            author_hardest["enhanced_truth_model_id"],
            author_hardest["ordinary_alternative_model_id"],
        ):
            raise ValueError("Hardest matched pair differs")
        if (
            case["cross_environment_comparisons"],
            case["existing_attenuation_pairs_per_comparison"],
        ) != (100, 9):
            raise ValueError("Declared finite comparison counts differ")
        maximum_fraction_error = 0.0
        maximum_amplitude_error = 0.0
        maximum_snr_relative_error = 0.0
        for row, author in [(closest, case["closest_cross_environment"])] + [
            (
                row,
                next(
                    s
                    for s in case["matched_environment_pairs"]
                    if s["enhanced_truth_model_id"] == row["truth"]
                ),
            )
            for row in paired
        ]:
            if (
                (row["truth"], row["alternative"])
                != (author["enhanced_truth_model_id"], author["ordinary_alternative_model_id"])
                or row["truth_attenuation"] != author["enhanced_A1500_mag"]
                or row["alternative_attenuation"] != author["ordinary_A1500_mag"]
            ):
                raise ValueError("Independent closest-pair/model nuisance identity differs")
            maximum_fraction_error = max(
                maximum_fraction_error, abs(row["fraction"] - author["shape_information_fraction"])
            )
            maximum_amplitude_error = max(
                maximum_amplitude_error,
                abs(row["amplitude"] - author["profiled_alternative_amplitude"]),
            )
            snr = None if row["fraction"] < 1e-14 else np.sqrt(9 / row["fraction"])
            if (snr is None) != (author["required_truth_matched_SNR"] is None):
                raise ValueError("Indistinguishable-template SNR convention differs")
            if snr is not None:
                maximum_snr_relative_error = max(
                    maximum_snr_relative_error,
                    abs(snr / author["required_truth_matched_SNR"] - 1),
                )
        if maximum_fraction_error > 1e-10 or maximum_amplitude_error > 1e-10:
            raise ValueError("Independent shape distance or normalization profile differs")
        if maximum_snr_relative_error > 1e-5:
            raise ValueError("Required SNR differs beyond numerical cancellation tolerance")
        quadratures = []
        for row in (closest, hardest):
            optimum, fraction = quadrature(
                centers,
                sigma,
                truth[row["truth_index"]],
                alternative[row["alternative_index"]],
                row["amplitude"],
            )
            if abs(optimum - row["amplitude"]) > 1e-8 or abs(fraction - row["fraction"]) > 1e-10:
                raise ValueError("Direct spectral quadrature differs")
            quadratures.append(
                {
                    "truth": row["truth"],
                    "alternative": row["alternative"],
                    "amplitude_error": abs(optimum - row["amplitude"]),
                    "fraction_error": abs(fraction - row["fraction"]),
                }
            )
        summaries.append(
            {
                "bundle": case["bundle"],
                "mode": case["mode"],
                "response": case["response"],
                "intrinsic_FWHM_km_s": case["intrinsic_fwhm_km_s"],
                "cross_environment_pairs": len(records),
                "attenuation_pairs_per_pair": count**2,
                "maximum_fraction_error": maximum_fraction_error,
                "maximum_amplitude_error": maximum_amplitude_error,
                "maximum_SNR_relative_error": maximum_snr_relative_error,
                "closest_pair": closest,
                "hardest_matched_pair": hardest,
                "direct_spectral_quadratures": quadratures,
            }
        )
    ranges = []
    for response in ("intrinsic_line_values", "emergent_line_values"):
        for name, indices in (("NV", (22, 23)), ("CII", (24, 25, 26, 27, 28))):
            families = {}
            for composition, models in ((0, ordinary), (1, enhanced)):
                results = []
                indices_with_anchor = indices + (12, 13)
                rests = np.array([lines[i][1] for i in indices_with_anchor])
                for model in models:
                    energy = np.array(model[response])[list(indices_with_anchor)]
                    for attenuation in plan["attenuation_A1500_mag"]:
                        screened = energy * np.exp(
                            -np.log(10) * 0.4 * attenuation * (rests / 1500) ** -1.2
                        )
                        results.append(float(screened[:-2].sum() / screened[-2:].sum()))
                families[str(composition)] = {"minimum": min(results), "maximum": max(results)}
            author = next(
                s for s in saved["extra_stage_ranges"][response] if s["ion_group"] == name
            )
            for key in ("0", "1"):
                for bound in ("minimum", "maximum"):
                    if not np.isclose(
                        families[key][bound],
                        author["ratio_to_CIII"][key][bound],
                        rtol=1e-12,
                        atol=1e-14,
                    ):
                        raise ValueError("Independent extra-stage range differs")
            lower = max(families["0"]["minimum"], families["1"]["minimum"])
            upper = min(families["0"]["maximum"], families["1"]["maximum"])
            overlap = None if lower > upper else [lower, upper]
            if overlap is None:
                if author["finite_range_overlap"] is not None:
                    raise ValueError("Extra-stage overlap differs")
            elif not np.allclose(overlap, author["finite_range_overlap"], rtol=1e-12, atol=1e-14):
                raise ValueError("Extra-stage overlap differs")
            ranges.append(
                {
                    "response": response,
                    "ion_group": name,
                    "ratio_to_CIII": families,
                    "finite_range_overlap": overlap,
                }
            )
    if len(summaries) != 48:
        raise ValueError("Exactly 48 declared forecast cases required")
    return {
        "schema_version": 1,
        "approval": "independent numerical and scope review passed",
        "review_runtime_seconds": time.monotonic() - started,
        "author_commit": author_commit,
        "validated_merged_input_revision": merged_revision,
        "input_sha256": input_sha,
        "forecast_sha256": forecast_sha,
        "review_code_sha256": sha(Path(__file__)),
        "plan_sha256": sha(plan_path),
        "author_code_sha256": sha(root / "tools/jwst/cloudy_observation_contrasts.py"),
        "reviewed_author_report_sha256": sha(report_path),
        "cases": summaries,
        "independent_extra_stage_ranges": ranges,
        "total_distances_recomputed": 48 * 100 * 9,
        "direct_spectral_quadratures": 96,
        "new_download_bytes": 0,
        "scope": [
            "Energy line shapes in continuous observed-micron coordinates; Gaussian profiles",
            "White constant variance per wavelength; mode/template SNR normalizations differ",
            "Enhanced composition is truth, ordinary is alternative; reverse SNR may differ",
            "Free nonnegative total flux and finite attenuation alternatives; no nuisance prior",
            (
                "Nominal tabulated band coverage excludes aperture gaps "
                "and throughput/noise feasibility"
            ),
            "Known continuum/centroid/width/spatial profile; source calibration remains unmeasured",
            "Finite model/stage ranges are predictions, not posterior probabilities or intervals",
            (
                "All twenty models are unweighted; closest-family stress "
                "is not posterior-averaged expected information"
            ),
            "NV wavelengths vacuum; CII Cloudy air labels are approximate target locations",
            "No native measurement likelihood or calibrated exposure duration obtained",
            (
                "Different broadening changes template norms; lower matched-template SNR "
                "does not establish lower exposure time"
            ),
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "input", "forecast", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("input-sha256", "forecast-sha256", "author-commit"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = audit(
        args.root,
        args.input,
        args.forecast,
        args.input_sha256,
        args.forecast_sha256,
        args.author_commit,
    )
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
