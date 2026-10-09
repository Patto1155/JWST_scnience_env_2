"""Independent full-native spectral likelihood and formation quadrature review.

These checks preserve explicit source/noise/history assumptions, and audit
numerical predictions rather than add astrophysical calibration or observations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.integrate import quad
from scipy.linalg import block_diag
from scipy.special import ndtr

from discovery.continuation_followup_review import LINE_ORDER, NATIVE_SCENARIOS, check_native_arrays
from tools.jwst.line_sensitivity import read_resolution
from tools.jwst.point_resolution import read_point_resolution


def formation_audit(root):
    path = root / "research_output/formation_predictions.json"
    report = json.loads(path.read_text())
    mass_quote = report["model_dependent_observational_input"]["quoted_log_stellar_mass_msun"]
    errors = []
    for history in report["history_predictions"]:
        duration = history["duration_myr"]
        tau = history["rising_efold_myr"]
        duty = history["time_duty_fraction"]
        active = history["required_current_active_sfr_msun_per_year"]
        returned = history["effective_returned_fraction"]
        surviving = history["surviving_stellar_mass_assumed_msun"]

        def rate(time):
            return duty * active * (1 if tau is None else np.exp((time - duration) / tau)) * 1e6

        formed = quad(rate, 0, duration, epsabs=1e-5, epsrel=1e-12)[0]
        error = abs((1 - returned) * formed - surviving) / surviving
        errors.append(error)
        if not np.isfinite(error) or error > 1e-11:
            raise ValueError("independently integrated surviving mass disagrees")
        if not np.isclose(formed, history["formed_stellar_mass_msun"], rtol=1e-11, atol=1e-8):
            raise ValueError("formed/surviving mass convention disagrees")
        for window in (5, 50):
            mean = quad(rate, max(0, duration - window), duration)[0] / (window * 1e6)
            if not np.isclose(
                mean, history[f"sfr_last_{window}_myr_msun_per_year"], rtol=1e-11, atol=1e-9
            ):
                raise ValueError("independently integrated trailing mean disagrees")
        half = quad(rate, duration - history["halfmass_lookback_myr"], duration)[0] / formed
        if not np.isclose(half, 0.5, rtol=1e-11, atol=1e-11):
            raise ValueError("independently integrated half-mass time disagrees")
    for budget in report["closed_parcel_baryon_budgets"]:
        surviving = budget["surviving_stellar_mass_assumed_msun"]
        formed = surviving / (1 - budget["effective_returned_fraction"])
        minimum = (
            surviving
            + budget["remaining_gas_mass_msun_assumed"]
            + budget["wind_mass_per_formed_stellar_mass"] * formed
        )
        halo = minimum / budget["cosmic_baryon_fraction_Planck18"]
        halo /= budget["initial_available_baryon_fraction"]
        if not np.allclose(
            [minimum, halo],
            [
                budget["minimum_initial_gas_mass_msun"],
                budget["minimum_halo_mass_msun_under_closed_allowance"],
            ],
            rtol=1e-12,
        ):
            raise ValueError("closed-parcel conservation disagrees")
    for inverse in report["inverse_history_tests"]:
        duration = inverse["required_duration_myr"]
        tau = inverse["rising_efold_myr_assumed"]
        active = inverse["active_sfr_msun_per_year_assumed"]
        returned = inverse["effective_returned_fraction_assumed"]
        duty = inverse["time_duty_fraction_assumed"]
        surviving = 10 ** mass_quote["median"]
        if inverse["quoted_mass_convention_assumed"] == "cumulative_formed":
            surviving *= 1 - returned
        if duration is None:
            if tau is None or (1 - returned) * duty * active * tau * 1e6 > surviving * (1 + 1e-12):
                raise ValueError("inverse-history asymptotic ceiling disagrees")
        else:

            def rate(time):
                return duty * active * (1 if tau is None else np.exp((time - duration) / tau)) * 1e6

            formed = quad(rate, 0, duration)[0]
            if not np.isclose((1 - returned) * formed, surviving, rtol=1e-11):
                raise ValueError("inverse-history integrated mass disagrees")
    if not errors:
        raise ValueError("nonempty formation histories required")
    return {
        "schema_version": 1,
        "formation_report_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "independently_integrated_histories": len(errors),
        "maximum_surviving_mass_relative_error": max(errors),
        "checked_inverse_histories": len(report["inverse_history_tests"]),
        "checked_closed_baryon_budgets": len(report["closed_parcel_baryon_budgets"]),
        "scope": (
            "independent quadrature and conservation under stated mass/history/duty/return "
            "assumptions; no new SED or cosmology likelihood"
        ),
    }


def multiplet_audit(root, version=1):
    if version not in (1, 2):
        raise ValueError("explicit single-line v1 or doublet v2 contract required")
    report_name = (
        "mom_native_multiplet_refit.json"
        if version == 1
        else "mom_native_niv_doublet_refit_v2.json"
    )
    atomic_name = "mom_atomic_grid.json" if version == 1 else "mom_atomic_grid_niv_doublet_v2.json"
    component_name = (
        "mom_multiplet_components.json"
        if version == 1
        else "mom_multiplet_components_niv_doublet_v2.json"
    )
    z = np.load(root / "research_output/mom_native_reduction.npz", allow_pickle=False)
    saved = json.loads((root / "research_output" / report_name).read_text())
    grid = json.loads((root / "research_output" / component_name).read_text())
    atomic = json.loads((root / "research_output" / atomic_name).read_text())
    native_path = root / "research_output/mom_native_reduction.json"
    native = json.loads(native_path.read_text())
    check_native_arrays(z, native)
    pins = (
        (
            root / "research_output/mom_native_reduction.npz",
            native["compact_native_replay"]["sha256"],
        ),
        (native_path, saved["native_report_sha256"]),
        (
            root / "research_output" / atomic_name,
            saved["atomic_grid_sha256" if version == 1 else "atomic_grid_v2_sha256"],
        ),
        (
            root / "research_output" / component_name,
            saved["component_grid_sha256" if version == 1 else "component_grid_v2_sha256"],
        ),
    )
    if any(hashlib.sha256(path.read_bytes()).hexdigest() != pin for path, pin in pins):
        raise ValueError("multiplet input provenance receipts differ")
    if tuple(scenario["name"] for scenario in saved["scenarios"]) != NATIVE_SCENARIOS:
        raise ValueError("exactly four ordered native likelihood scenarios required")
    if saved["NIV_1483_included"] != (version == 2):
        raise ValueError("N IV doublet presence differs from explicit line contract")
    expected_waves = [1486.496] if version == 1 else [1483.321, 1486.496]
    if any(
        cell["components"][0]["vacuum_wavelengths_A"] != expected_waves for cell in grid["records"]
    ):
        raise ValueError("N IV template wavelengths differ from the versioned contract")
    wave, good, trace, sigma = (z[k] for k in ("native_wave", "native_good", "trace", "sigma"))
    yy = np.arange(wave.shape[1])[None, :, None]
    p = ndtr((yy + 0.5 - trace[:, None, :]) / sigma[0]) - ndtr(
        (yy - 0.5 - trace[:, None, :]) / sigma[0]
    )
    den = (p * good).sum(axis=1)
    num = (np.where(good, wave, 0) * p).sum(axis=1)
    waves = np.divide(num, den, out=np.full_like(den, np.nan), where=den > 0)
    for w in waves:
        valid = np.flatnonzero(np.isfinite(w))
        w[:] = np.interp(np.arange(len(w)), valid, w[valid])
        left, right = (valid[0], valid[-1])
        w[:left] = w[left] + (np.arange(left) - left) * (w[left + 1] - w[left])
        w[right + 1 :] = w[right] + (np.arange(right + 1, len(w)) - right) * (
            w[right] - w[right - 1]
        )
    selected = z["selected_columns"]
    factor = block_diag(*[np.linalg.cholesky(x) for x in z["covariance_blocks"]])
    values = z["flux"].T.ravel()
    errors = []
    coverrors = []
    ionicerrors = []
    checked = 0
    formal = factor @ factor.T
    emp = factor @ np.kron(z["spectral_kernel"], np.eye(9)) @ factor.T * z["noise_scale_squared"][0]
    inverse = [np.linalg.inv(formal), np.linalg.inv(emp)]
    for index, scenario in enumerate(saved["scenarios"]):
        rw, rr, _ = (
            read_point_resolution(root / "data_sources/followup/unite_point_prism_resolution.csv")
            if index % 2
            else read_resolution(root / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
        )
        P = inverse[index // 2]
        for cell, acell, record in zip(
            grid["records"], atomic["records"], scenario["records"], strict=True
        ):
            if not (cell["temperature_K"], cell["electron_density_cm3"]) == (
                record["temperature_K"],
                record["electron_density_cm3"],
            ):
                raise ValueError("independent multiplet numerical audit disagrees")
            designs = []
            for w in waves:
                edge = np.r_[
                    w[0] - (w[1] - w[0]) / 2, (w[1:] + w[:-1]) / 2, w[-1] + (w[-1] - w[-2]) / 2
                ]
                width = np.diff(edge)
                lines = []
                for group in cell["components"]:
                    model = np.zeros(len(w))
                    for rest, weight in zip(
                        group["vacuum_wavelengths_A"], group["normalized_weights"], strict=True
                    ):
                        center = rest * 0.0001 * 15.44
                        R = np.interp(center, rw, rr)
                        s = center / R / (2 * np.sqrt(2 * np.log(2)))
                        model += weight * np.diff(ndtr((edge - center) / s)) / width
                    lines.append(model / (299792.458 / w**2))
                designs.append(
                    np.column_stack(
                        (np.ones(len(w)) / 100, (w - 2.675) / 0.525 / 100, np.array(lines).T)
                    )[selected]
                )
            X = np.transpose(designs, (1, 0, 2)).reshape(-1, 7)
            cov = np.linalg.inv(X.T @ P @ X)
            coef = cov @ (X.T @ P @ values)
            f = record["fit"]
            expected_flux = np.asarray(f["fluxes"])
            expected_covariance = np.asarray(f["flux_covariance"])
            if (
                f["flux_units"] != "1e-20 erg s^-1 cm^-2"
                or tuple(f["line_order"]) != LINE_ORDER
                or expected_flux.shape != (5,)
                or expected_covariance.shape != (5, 5)
                or not np.isfinite(expected_flux).all()
                or not np.isfinite(expected_covariance).all()
                or not np.allclose(expected_covariance, expected_covariance.T)
                or np.linalg.eigvalsh(expected_covariance).min() <= 0
            ):
                raise ValueError("finite aligned five-group signed likelihood required")
            if version == 2 and f.get("line_contract_version") != 2:
                raise ValueError("doublet likelihood must declare its total-flux version")
            delta = np.max(abs(coef[2:] - f["fluxes"]))
            covdelta = np.max(abs(cov[2:, 2:] - f["flux_covariance"])) / np.max(
                abs(np.array(f["flux_covariance"]))
            )
            if not (delta < 1e-09 and covdelta < 1e-09):
                raise ValueError("independent multiplet numerical audit disagrees")
            errors.append(float(delta))
            coverrors.append(float(covdelta))
            epsilon = acell["emissivity_erg_cm3_s"]
            projection = np.array(
                [
                    [epsilon["CIII"] / epsilon["NIV"], 0, 0, epsilon["CIII"] / epsilon["NIII"], 0],
                    [0, epsilon["CIII"] / epsilon["CIV"], 0, 0, 1],
                ]
            )
            u = projection @ coef[2:]
            C = projection @ cov[2:, 2:] @ projection.T
            ionic = record["observed_two_stage_ionic_N_over_C"]
            ratio = u[0] / u[1]
            ionicerrors.append(abs(ratio - ionic["value"]))
            if not np.isclose(ratio, ionic["value"], rtol=1e-10, atol=1e-10):
                raise ValueError("independent ionic point estimate disagrees")
            if not np.allclose(C, ionic["scaled_covariance"], rtol=1e-10, atol=1e-10):
                raise ValueError("independent multiplet numerical audit disagrees")
            quadratic = [
                u[1] ** 2 - 3.84145882069 * C[1, 1],
                -2 * (u[0] * u[1] - 3.84145882069 * C[0, 1]),
                u[0] ** 2 - 3.84145882069 * C[0, 0],
            ]
            roots = sorted(np.roots(quadratic))
            if not np.allclose(
                roots,
                ionic["conditional_gaussian_95_fieller_set"]["interval"],
                rtol=1e-09,
                atol=1e-09,
            ):
                raise ValueError("independent multiplet numerical audit disagrees")
            checked += 1
    if checked != 112:
        raise ValueError("complete112-cell spectral refit contract required")
    receipt = {
        "schema_version": 1,
        "native_npz_sha256": hashlib.sha256(
            (root / "research_output/mom_native_reduction.npz").read_bytes()
        ).hexdigest(),
        "multiplet_report_sha256": hashlib.sha256(
            (root / "research_output" / report_name).read_bytes()
        ).hexdigest(),
        "independent_full_native_bin_GLS_fits": checked,
        "maximum_flux_absolute_difference": max(errors),
        "maximum_covariance_difference_over_scale": max(coverrors),
        "maximum_ionic_ratio_absolute_difference": max(ionicerrors),
        "scope": (
            "independent full-grid Gaussian integration and normal equations with fixed "
            "native source amplitudes/noise; no source LSF, elemental or axes inference"
        ),
    }
    if version == 2:
        receipt["line_contract_version"] = 2
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("multiplet", "niv_doublet", "formation"))
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "formation":
        result = formation_audit(args.directory)
    else:
        result = multiplet_audit(args.directory, 2 if args.mode == "niv_doublet" else 1)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
