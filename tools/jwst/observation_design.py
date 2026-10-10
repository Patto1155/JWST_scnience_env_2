"""Conditional UV observation design; no measured LSF or absolute ETC forecast."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from astropy.io import fits

from tools.jwst.niv_doublet_refit import COMPONENT_V2_SHA256

ROOT = Path(__file__).resolve().parents[2]
C_KM_S = 299792.458
FWHM_TO_SIGMA = 2 * np.sqrt(2 * np.log(2))
SOURCE = ROOT / "data_sources/pilot/observation_design"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gaussian_gram(
    wavelengths_um: np.ndarray,
    resolving_power: float | np.ndarray,
    intrinsic_fwhm_km_s: float = 0.0,
) -> np.ndarray:
    """Exact continuous white-noise inner products of unit-area Gaussian lines.

    Equal flux in two differently broadened lines does not have equal SNR.
    The Gram matrix retains that norm difference; no source response is calibrated.
    """
    wave = np.asarray(wavelengths_um, dtype=float)
    resolution = np.broadcast_to(np.asarray(resolving_power, dtype=float), wave.shape)
    if (
        wave.ndim != 1
        or not len(wave)
        or not np.all(np.isfinite(wave))
        or np.any(wave <= 0)
        or not np.all(np.isfinite(resolution))
        or np.any(resolution <= 0)
        or not np.isfinite(intrinsic_fwhm_km_s)
        or intrinsic_fwhm_km_s < 0
    ):
        raise ValueError("finite positive wavelengths and R; finite nonnegative width required")
    sigma = wave * np.sqrt(resolution**-2 + (intrinsic_fwhm_km_s / C_KM_S) ** 2) / FWHM_TO_SIGMA
    variance = sigma[:, None] ** 2 + sigma[None, :] ** 2
    return np.exp(-((wave[:, None] - wave[None, :]) ** 2) / (2 * variance)) / np.sqrt(
        2 * np.pi * variance
    )


def shape_discrimination(
    gram: np.ndarray, truth: np.ndarray, alternative: np.ndarray, target_lambda: float = 9.0
) -> dict:
    """Profile a free nonnegative alternative total flux under known shapes.

    Returned SNR is matched-template total SNR of the truth. Lambda is an
    expected squared separation, not a calibrated model-selection p-value.
    """
    gram = np.asarray(gram, dtype=float)
    truth, alternative = np.asarray(truth, dtype=float), np.asarray(alternative, dtype=float)
    if (
        gram.shape != (len(truth), len(truth))
        or alternative.shape != truth.shape
        or not np.all(np.isfinite(gram))
        or not np.allclose(gram, gram.T)
        or np.min(np.linalg.eigvalsh(gram)) <= 0
        or np.any(truth < 0)
        or np.any(alternative < 0)
        or not np.isclose(truth.sum(), 1)
        or not np.isclose(alternative.sum(), 1)
        or not np.isfinite(target_lambda)
        or target_lambda <= 0
    ):
        raise ValueError("positive Gram and normalized nonnegative weights required")
    tt = float(truth @ gram @ truth)
    aa = float(alternative @ gram @ alternative)
    ta = float(truth @ gram @ alternative)
    amplitude = max(0.0, ta / aa)
    fraction = max(0.0, (tt - 2 * amplitude * ta + amplitude * amplitude * aa) / tt)
    return {
        "profiled_alternative_amplitude": amplitude,
        "shape_information_fraction": fraction,
        "required_truth_matched_SNR": None
        if fraction < 1e-14
        else float(np.sqrt(target_lambda / fraction)),
        "expected_separation_lambda": target_lambda,
    }


def exposure_scale(
    required_snr: float, reference_snr: float, systematic_snr_limit: float | None = None
) -> float | None:
    """t/t0 assuming random variance falls as1/t and optional fixed floor.

    Reference SNR is the random-noise SNR at t0 in the SAME mode/template.
    The separate systematic limit is a maximal achievable total SNR.
    """
    if (
        not np.isfinite(required_snr)
        or not np.isfinite(reference_snr)
        or min(required_snr, reference_snr) <= 0
    ):
        raise ValueError("positive finite SNR values required")
    if systematic_snr_limit is None:
        return (required_snr / reference_snr) ** 2
    if not np.isfinite(systematic_snr_limit) or systematic_snr_limit <= 0:
        raise ValueError("positive finite systematic SNR limit required")
    remaining = required_snr**-2 - systematic_snr_limit**-2
    return None if remaining <= 0 else float(reference_snr**-2 / remaining)


def read_nominal_curves() -> dict:
    receipt = json.loads((SOURCE / "receipt.json").read_text())
    curves = {}
    for item in receipt["records"]:
        if not item["name"].endswith(".fits"):
            continue
        path = SOURCE / item["name"]
        if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            raise ValueError("nominal response input hash/size mismatch")
        with fits.open(path) as hdul:
            table = hdul[1].data
            curves[item["name"].split("_")[2]] = (
                np.array(table["WAVELENGTH"], float),
                np.array(table["R"], float),
            )
    return curves


def run() -> dict:
    plan = json.loads((SOURCE / "plan.json").read_text())
    path = ROOT / "research_output/mom_multiplet_components_niv_doublet_v2.json"
    if digest(path) != COMPONENT_V2_SHA256:
        raise ValueError("version2 component grid pin mismatch")
    grid = json.loads(path.read_text())
    z = plan["redshift_assumed"]
    selected = {
        row["electron_density_cm3"]: row
        for row in grid["records"]
        if row["temperature_K"] == plan["temperature_K"]
    }
    groups = {item["group"]: item for item in selected[1000]["components"]}
    curves = read_nominal_curves()
    results, density = [], []
    for name, group in groups.items():
        wave = np.array(group["vacuum_wavelengths_A"]) * (1 + z) / 1e4
        closest = int(np.argmin(np.diff(wave)))
        minimum_separation = wave[closest + 1] - wave[closest]
        closest_midpoint = np.mean(wave[closest : closest + 2])
        results.append(
            {
                "group": name,
                "observed_wavelengths_um": wave.tolist(),
                "closest_pair_one_FWHM_R": float(closest_midpoint / minimum_separation),
                "closest_pair_velocity_separation_km_s": float(
                    C_KM_S * minimum_separation / closest_midpoint
                ),
            }
        )
        for mode, (curvewave, curver) in curves.items():
            band_low, band_high = (1.66, 3.17) if mode.startswith("g235") else (2.87, 5.27)
            if np.any(wave < max(curvewave.min(), band_low)) or np.any(
                wave > min(curvewave.max(), band_high)
            ):
                continue
            localr = np.interp(wave, curvewave, curver)
            for width in plan["intrinsic_fwhm_km_s"]:
                gram = gaussian_gram(wave, localr, width)
                correlation = gram / np.sqrt(np.outer(np.diag(gram), np.diag(gram)))
                entry = {
                    "group": name,
                    "mode": mode,
                    "intrinsic_fwhm_km_s": width,
                    "nominal_R_at_components": localr.tolist(),
                    "correlation_matrix": correlation.tolist(),
                    "normalized_gram_condition_number": float(np.linalg.cond(correlation)),
                    "worst_component_error_inflation": float(
                        np.sqrt(np.max(np.diag(np.linalg.inv(correlation))))
                    ),
                }
                if name in ("NIV", "CIII"):
                    alternative = next(
                        item for item in selected[100000]["components"] if item["group"] == name
                    )
                    entry["density_contrast"] = shape_discrimination(
                        gram, group["normalized_weights"], alternative["normalized_weights"]
                    )
                    entry["truth_weights_ne1000"] = group["normalized_weights"]
                    entry["alternative_weights_ne100000"] = alternative["normalized_weights"]
                density.append(entry)
    # Additional stages are wavelength targets; no zero substituted for absent predicted flux.
    additional = [
        {
            "ion": ion,
            "rest_wavelength_convention": convention,
            "rest_A": wavelength,
            "observed_um": wavelength * (1 + z) / 1e4,
            "inside_nominal_NIRSpec_0p6_5p3": 0.6 <= wavelength * (1 + z) / 1e4 <= 5.3,
        }
        for ion, wavelength, convention in [
            ("NV", 1238.82, "vacuum"),
            ("NV", 1242.80, "vacuum"),
            ("CII", 2326.93, "Cloudy air wavelength; approximate target only"),
            ("Hbeta", 4861.32, "Cloudy air wavelength; approximate target only"),
            ("OIII", 5006.84, "Cloudy air wavelength; approximate target only"),
            ("NII", 6583.45, "Cloudy air wavelength; approximate target only"),
        ]
    ]
    return {
        "schema_version": 1,
        "plan": plan,
        "inputs_sha256": {
            "components": digest(path),
            "plan": digest(SOURCE / "plan.json"),
            "response_receipt": digest(SOURCE / "receipt.json"),
        },
        "line_targets": results,
        "response_cases": density,
        "additional_stage_targets": additional,
        "exposure_scaling_example": {
            "required_truth_SNR": 20,
            "random_reference_SNR_at_t0": 5,
            "no_floor_t_over_t0": exposure_scale(20, 5),
            "fixed_floor_SNR30_t_over_t0": exposure_scale(20, 5, 30),
            "fixed_floor_SNR10_t_over_t0": exposure_scale(20, 5, 10),
            "absolute_seconds": None,
            "illustrative_inputs_not_ETC": True,
        },
        "interpretation": "Optimistic conditional design, not empirically calibrated response, density inference, new observation or exposure feasibility. No elemental abundance/polluter/cosmology inference.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "research_output/mom_observation_design.json"
    )
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
