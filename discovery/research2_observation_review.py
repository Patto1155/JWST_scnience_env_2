"""Independent quadrature and profiled-shape observation-design review."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from astropy.io import fits
from scipy.integrate import quad
from scipy.optimize import brentq, minimize_scalar


def numeric_gram(wavelength, resolving_power, intrinsic_width):
    wave = np.array(wavelength)
    # Separate instrumental and astrophysical standard deviations.
    instrumental = wave / np.array(resolving_power) / (8 * np.log(2)) ** 0.5
    intrinsic = wave * intrinsic_width / 299792.458 / (8 * np.log(2)) ** 0.5
    sigma = np.hypot(instrumental, intrinsic)
    gram = np.zeros((len(wave), len(wave)))
    for i in range(len(wave)):
        for j in range(i, len(wave)):
            midpoint = (wave[i] + wave[j]) / 2
            scale = max(sigma[i], sigma[j])

            def integrand(t):
                x = midpoint + scale * t
                first = np.exp(-0.5 * ((x - wave[i]) / sigma[i]) ** 2) / (
                    np.sqrt(2 * np.pi) * sigma[i]
                )
                second = np.exp(-0.5 * ((x - wave[j]) / sigma[j]) ** 2) / (
                    np.sqrt(2 * np.pi) * sigma[j]
                )
                return first * second * scale

            value = quad(integrand, -30, 30, epsabs=1e-11, epsrel=1e-11, limit=200)[0]
            gram[i, j] = gram[j, i] = value
    return gram


def audit(root, cloudy_source=None):
    report_path = root / "research_output/mom_observation_design.json"
    report = json.loads(report_path.read_text())
    base = root / "data_sources/pilot/observation_design"
    receipt = json.loads((base / "receipt.json").read_text())
    curves = {}
    for entry in receipt["records"]:
        if not entry["name"].endswith(".fits"):
            continue
        path = base / entry["name"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
        with fits.open(path) as h:
            assert h[1].columns["WAVELENGTH"].unit.lower() in ("um", "micron", "microns")
            w = np.array(h[1].data["WAVELENGTH"])
            r = np.array(h[1].data["R"])
            assert np.all(np.diff(w) > 0) and np.all(r > 0)
            curves[entry["name"].split("_")[2]] = (w, r)
    targets = {row["group"]: row["observed_wavelengths_um"] for row in report["line_targets"]}
    max_corr = 0.0
    max_snr = 0.0
    audited = []
    for record in report["response_cases"]:
        waves = np.array(targets[record["group"]])
        grid, response = curves[record["mode"]]
        assert np.all(waves >= grid.min()) and np.all(waves <= grid.max())
        low, high = (1.66, 3.17) if record["mode"].startswith("g235") else (2.87, 5.27)
        assert np.all(waves >= low) and np.all(waves <= high)
        resolving = np.interp(waves, grid, response)
        assert np.max(abs(resolving - record["nominal_R_at_components"])) < 1e-8
        gram = numeric_gram(waves, resolving, record["intrinsic_fwhm_km_s"])
        correlation = gram / np.sqrt(np.outer(np.diag(gram), np.diag(gram)))
        err = float(np.max(abs(correlation - record["correlation_matrix"])))
        assert err < 1e-9
        max_corr = max(max_corr, err)
        inflation = float(np.sqrt(np.diag(np.linalg.inv(correlation)).max()))
        assert abs(inflation - record["worst_component_error_inflation"]) < 1e-8
        if "density_contrast" in record:
            truth = np.array(record["truth_weights_ne1000"])
            other = np.array(record["alternative_weights_ne100000"])

            def loss(amplitude):
                residual = truth - amplitude * other
                return float(residual @ gram @ residual)

            answer = minimize_scalar(
                loss, bounds=(0, 3), method="bounded", options={"xatol": 1e-12}
            )
            assert answer.success
            fraction = answer.fun / (truth @ gram @ truth)
            snr = float(np.sqrt(9 / fraction))
            assert abs(snr - record["density_contrast"]["required_truth_matched_SNR"]) < 1e-7
            max_snr = max(
                max_snr, abs(snr - record["density_contrast"]["required_truth_matched_SNR"])
            )
        audited.append([record["group"], record["mode"], record["intrinsic_fwhm_km_s"]])
    exposure = report["exposure_scaling_example"]
    # Numerically solve the noise equation with a fixed fractional floor.
    required, reference, floor = 20.0, 5.0, 30.0
    time = brentq(lambda t: 1 / (1 / reference**2 / t + 1 / floor**2) ** 0.5 - required, 1, 100)
    assert abs(time - exposure["fixed_floor_SNR30_t_over_t0"]) < 1e-10
    assert exposure["fixed_floor_SNR10_t_over_t0"] is None
    assert exposure["absolute_seconds"] is None
    reviewed = {
        "schema_version": 1,
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "four_primary_response_curves_verified": True,
        "actual_cases": audited,
        "maximum_quadrature_correlation_error": max_corr,
        "maximum_profiled_SNR_error": max_snr,
        "independent_fixed_floor_time_ratio": time,
        "scope": (
            "Continuous white-noise Gaussian design under nominal curves; "
            "no empirical source LSF, detector-gap coverage, "
            "line sensitivity or absolute time"
        ),
    }
    if cloudy_source is not None:
        convention_path = base / "cloudy_line_convention.json"
        convention = json.loads(convention_path.read_text())
        for item in convention["members"]:
            raw = (cloudy_source / item["member"]).read_bytes()
            assert len(raw) == item["bytes"]
            assert hashlib.sha256(raw).hexdigest() == item["sha256"]
        target = next(row for row in report["additional_stage_targets"] if row["ion"] == "CII")
        assert (
            target["rest_wavelength_convention"] == "Cloudy air wavelength; approximate target only"
        )
        reviewed["cloudy_line_convention_sha256"] = hashlib.sha256(
            convention_path.read_bytes()
        ).hexdigest()
        reviewed["four_cloudy_source_members_verified"] = True
    return reviewed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cloudy-source", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.root, args.cloudy_source), indent=2) + "\n")


if __name__ == "__main__":
    main()
