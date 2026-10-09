"""Final336-fit v2 multiplet, wavelength and fixed-noise sensitivity experiment.

All alternatives reuse the same observations. No likelihood is pooled or given
posterior odds; the DUMMY reference remains a toy instrumental prediction.
The ambient reference below is ionic solar N/C, not an elemental abundance test.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from tools.jwst.atomic_grid import check_fluxes, ionic_ratio
from tools.jwst.line_sensitivity import read_resolution
from tools.jwst.multiplet_refit import digest
from tools.jwst.native_reduction import fit_native
from tools.jwst.native_wavecorr import load_wavecorr_replay, replay_wavecorr
from tools.jwst.niv_doublet_refit import (
    ATOMIC_V2_SHA256,
    COMPONENT_V2_SHA256,
    serialized,
    validate_inputs,
)
from tools.jwst.point_resolution import read_point_resolution

ROOT = Path(__file__).resolve().parents[2]
WAVECORR_REPORT_SHA256 = "80ca86e7969e82bca424a963b39282f2fec42d589fb055238b4ac18510ab3fe6"
V2_RESULT_SHA256 = "446c1f7a35ed8c8e272ba277576088f7a4dbbd6d75dcceb2dd6c1767b2891b63"
AMBIENT_IONIC_REFERENCE = 10**-0.60


def ratio_accepted(answer: dict, value: float) -> bool:
    """Direct Fieller quadratic membership; supports bounded/unbounded signed sets."""
    if not np.isfinite(value):
        raise ValueError("finite ionic reference required")
    n, d = answer["scaled_numerator"], answer["scaled_denominator"]
    v = np.asarray(answer["scaled_covariance"])
    return bool(
        (n - value * d) ** 2 <= 3.84145882069 * (v[0, 0] + value**2 * v[1, 1] - 2 * value * v[0, 1])
    )


def summarize(records: list[dict]) -> dict:
    answers = [record["observed_two_stage_ionic_N_over_C"] for record in records]
    logs = [a["log_ratio_relative_to_solar_NC_minus_0_60"] for a in answers]
    finite_logs = [value for value in logs if value is not None]
    return {
        "cells": len(records),
        "ionic_zero_accepted_95_count": sum(ratio_accepted(a, 0) for a in answers),
        "ionic_ambient_reference_accepted_95_count": sum(
            ratio_accepted(a, AMBIENT_IONIC_REFERENCE) for a in answers
        ),
        "fieller_set_type_counts": dict(
            Counter(a["conditional_gaussian_95_fieller_set"]["type"] for a in answers)
        ),
        "central_ionic_log_range_relative_to_solar": [min(finite_logs), max(finite_logs)]
        if finite_logs
        else None,
        "grid_range_is_confidence_interval": False,
    }


def plot_reference(result: dict, output: Path) -> None:
    """Signed conditional intervals; alternatives are not probabilistic bands."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(9.5, 5.8))
    labels = []
    for index, alternative in enumerate(result["alternatives"]):
        family = index % 6
        reference = alternative["reference_cell"]
        interval = reference["fieller_95"]
        if interval["type"] != "bounded":
            raise ValueError("reference figure requires actual finite Fieller endpoints")
        point = reference["ionic_ratio"]
        lower, upper = interval["interval"]
        dummy = alternative["wavelength_hypothesis"] == "pinned_toy_prediction"
        axis.errorbar(
            point,
            family + (0.11 if dummy else -0.11),
            xerr=[[point - lower], [upper - point]],
            fmt="s" if dummy else "o",
            color="#C65D28" if dummy else "#247A9F",
            capsize=3,
            markersize=5,
            label=("DUMMY wavelength prediction" if dummy else "Original wavelengths")
            if family == 0
            else None,
        )
        if not dummy:
            noise = {
                "formal_shared": "Formal shared",
                "empirical_columns": "Empirical columns",
                "empirical_rows_and_columns": "Empirical rows + columns",
            }[alternative["noise_family"]]
            labels.append(
                ("Nominal" if alternative["resolution_family"] == "nominal" else "Point")
                + " / "
                + noise
            )
    axis.axvline(0, color="#444444", linewidth=0.8)
    axis.axvline(
        AMBIENT_IONIC_REFERENCE, color="#777777", linestyle=":", label="Solar ionic reference 0.251"
    )
    axis.set_yticks(range(6), labels)
    axis.invert_yaxis()
    axis.set_xlabel("Conditional two-stage ionic N/C: signed 95% Fieller sets")
    axis.legend(frameon=False, ncol=3, fontsize=9, loc="lower center", bbox_to_anchor=(0.5, 1.02))
    figure.suptitle(
        "MoM-z14: version 2 N IV doublet at Te=20,000 K / ne=1,000 cm$^{-3}$", fontsize=12
    )
    figure.text(
        0.02,
        0.02,
        "Shared observations; fixed source and generic instrumental resolution. "
        "DUMMY reference is a toy prediction.\n"
        "Ionic solar reference assumes equal observed-stage fractions; "
        "no elemental N/C, calibrated wavelength/LSF or posterior model odds.",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.09, 1, 0.92))
    figure.savefig(output, dpi=160)
    plt.close(figure)


def run(
    wavecorr_path: Path, atomic_path: Path, components_path: Path, v2_result_path: Path
) -> dict:
    for path, expected in (
        (wavecorr_path, WAVECORR_REPORT_SHA256),
        (atomic_path, ATOMIC_V2_SHA256),
        (components_path, COMPONENT_V2_SHA256),
        (v2_result_path, V2_RESULT_SHA256),
    ):
        if digest(path) != expected:
            raise ValueError("composed experiment input differs from independent frozen pin")
    wavecorr, atomic, components, previous = (
        json.loads(p.read_text())
        for p in (wavecorr_path, atomic_path, components_path, v2_result_path)
    )
    validate_inputs(
        atomic,
        components,
        json.loads((ROOT / "research_output/mom_atomic_grid.json").read_text()),
        json.loads((ROOT / "research_output/mom_multiplet_components.json").read_text()),
    )
    if wavecorr["reference"]["pedigree"] != "DUMMY":
        raise ValueError("this sensitivity pins the DUMMY reference, not an empirical calibration")
    baseline = replay_wavecorr(wavecorr_path)
    rw, rr, nominal = read_resolution(ROOT / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
    pw, pr, point = read_point_resolution(
        ROOT / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    alternatives, v2_controls = [], []
    for corrected in (False, True):
        replay = load_wavecorr_replay(wavecorr_path, corrected=corrected)
        for resolution_label, resolution_wave, resolution in (
            ("nominal", rw, rr),
            ("generic_point", pw, pr),
        ):
            cases = [
                ("formal_shared", replay["covariance_blocks"], None, 1),
                (
                    "empirical_columns",
                    replay["covariance_blocks"],
                    replay["spectral_kernel"],
                    replay["noise_scale_squared"],
                ),
                (
                    "empirical_rows_and_columns",
                    replay["spatial_covariance_blocks"],
                    replay["spectral_kernel"],
                    replay["noise_scale_squared"],
                ),
            ]
            for noise_label, blocks, kernel, scale in cases:
                records = []
                for index, (cell, template) in enumerate(
                    zip(atomic["records"], components["records"])
                ):
                    fit = fit_native(
                        replay["data"],
                        replay["flux"],
                        blocks,
                        replay["selected"],
                        resolution_wave,
                        resolution,
                        kernel=kernel,
                        noise_scale=scale,
                        components=[
                            (g["vacuum_wavelengths_A"], g["normalized_weights"])
                            for g in template["components"]
                        ],
                    )
                    flux, covariance = check_fluxes(
                        {
                            "lines": fit["lines"],
                            "line_covariance": fit["flux_covariance"],
                            "line_flux_unit": fit["flux_units"],
                        }
                    )
                    ionic = ionic_ratio(
                        flux,
                        covariance,
                        cell["emissivity_erg_cm3_s"],
                        ("NIV", "NIII"),
                        ("CIV", "CIII"),
                    )
                    fit["line_contract_version"] = 2
                    fit["NIV_flux_definition"] = (
                        "Total1483.321+1486.496 under the normalized physical doublet template"
                    )
                    # Exposure covariance is already in the pinned compact input;
                    # Retain each fitted5x5 covariance without repeating the9x9 table.
                    fit.pop("median_exposure_amplitude_correlation", None)
                    records.append(
                        {
                            "temperature_K": cell["temperature_K"],
                            "electron_density_cm3": cell["electron_density_cm3"],
                            "fit": fit,
                            "observed_two_stage_ionic_N_over_C": ionic,
                        }
                    )
                    if not corrected and noise_label != "empirical_rows_and_columns":
                        old_index = (0 if resolution_label == "nominal" else 1) + (
                            2 if noise_label == "empirical_columns" else 0
                        )
                        old = previous["scenarios"][old_index]["records"][index]
                        if (cell["temperature_K"], cell["electron_density_cm3"]) != (
                            old["temperature_K"],
                            old["electron_density_cm3"],
                        ):
                            raise ValueError("v2 control cells differ")
                        df = float(np.max(np.abs(flux - np.asarray(old["fit"]["fluxes"]))))
                        dc = float(
                            np.max(np.abs(covariance - np.asarray(old["fit"]["flux_covariance"])))
                        )
                        if df > 1e-9 or dc > 1e-8:
                            raise ValueError(
                                "original-wavelength quartet does not reproduce frozenv2"
                            )
                        v2_controls.append(
                            {
                                "resolution_family": resolution_label,
                                "noise_family": noise_label,
                                "temperature_K": cell["temperature_K"],
                                "electron_density_cm3": cell["electron_density_cm3"],
                                "maximum_flux_difference": df,
                                "maximum_covariance_difference": dc,
                            }
                        )
                reference = next(
                    r
                    for r in records
                    if r["temperature_K"] == 20000 and r["electron_density_cm3"] == 1000
                )
                answer = reference["observed_two_stage_ionic_N_over_C"]
                alternatives.append(
                    {
                        "name": f"{replay['wavelength_hypothesis']}_"
                        f"{resolution_label}_{noise_label}",
                        "wavelength_hypothesis": replay["wavelength_hypothesis"],
                        "resolution_family": resolution_label,
                        "noise_family": noise_label,
                        "source_noise_frozen": replay["source_noise_frozen"],
                        "records": records,
                        "grid_summary": summarize(records),
                        "reference_cell": {
                            "temperature_K": 20000,
                            "electron_density_cm3": 1000,
                            "ionic_ratio": answer["value"],
                            "fieller_95": answer["conditional_gaussian_95_fieller_set"],
                            "ionic_zero_accepted_95": ratio_accepted(answer, 0),
                            "ionic_ambient_reference_accepted_95": ratio_accepted(
                                answer, AMBIENT_IONIC_REFERENCE
                            ),
                            "conditional_chi2": reference["fit"]["conditional_chi2"],
                        },
                    }
                )
    return {
        "schema_version": 1,
        "experiment_version": "mom_v2_wave_noise_composition_v1",
        "line_contract_version": 2,
        "input_wavecorr_report_sha256": digest(wavecorr_path),
        "compact_replay_receipt": wavecorr["compact_replay"],
        "atomic_v2_sha256": digest(atomic_path),
        "components_v2_sha256": digest(components_path),
        "previous_original_quartet_v2_sha256": digest(v2_result_path),
        "reference_metadata": wavecorr["reference"],
        "empirical_wavelength_calibration": False,
        "default_template_wavecorr_replay": baseline,
        "original_quartet_v2_controls": v2_controls,
        "resolution_provenance": {"nominal": nominal, "generic_point": point},
        "ambient_reference_ionic_NC": AMBIENT_IONIC_REFERENCE,
        "ambient_reference_is_elemental_test": False,
        "alternatives": alternatives,
        "spectral_fits": sum(len(a["records"]) for a in alternatives),
        "software_files": [
            {"filename": str(p.relative_to(ROOT)), "sha256": digest(p)}
            for p in (
                ROOT / "tools/jwst/composed_spectral_refit.py",
                ROOT / "tools/jwst/native_wavecorr.py",
                ROOT / "tools/jwst/native_reduction.py",
                ROOT / "tools/jwst/line_sensitivity.py",
                ROOT / "tools/jwst/niv_doublet_refit.py",
                ROOT / "tools/jwst/atomic_grid.py",
            )
        ],
        "line_flux_covariance_refit_for_each_template": True,
        "source_amplitude_noise_covariance_refit": False,
        "HeII_OIII_mixing_calibrated": False,
        "CIV_transfer_calibrated": False,
        "source_specific_LSF_calibrated": False,
        "ion_fraction_correction_available": False,
        "elemental_abundance_identified": False,
        "grid_axes_identified": False,
        "alternative_likelihoods_pooled": False,
        "posterior_weights_assigned": False,
        "interpretation": "Version2 physical multiplets across explicit "
        "wavelength/noise/resolution alternatives; DUMMY wavelength prediction "
        "and stationary empirical covariance remain assumptions; "
        "no elemental or mechanism identification",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wavecorr", type=Path, default=ROOT / "research_output/mom_native_wavecorr.json"
    )
    parser.add_argument(
        "--atomic", type=Path, default=ROOT / "research_output/mom_atomic_grid_niv_doublet_v2.json"
    )
    parser.add_argument(
        "--components",
        type=Path,
        default=ROOT / "research_output/mom_multiplet_components_niv_doublet_v2.json",
    )
    parser.add_argument(
        "--previous-v2",
        type=Path,
        default=ROOT / "research_output/mom_native_niv_doublet_refit_v2.json",
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "research_output/mom_composed_spectral_refit.json"
    )
    parser.add_argument(
        "--figure", type=Path, default=ROOT / "research_output/mom_composed_spectral_refit.png"
    )
    args = parser.parse_args()
    result = run(args.wavecorr, args.atomic, args.components, args.previous_v2)
    args.output.write_bytes(serialized(result))
    plot_reference(result, args.figure)
    print(json.dumps({"output": str(args.output), "spectral_fits": result["spectral_fits"]}))


if __name__ == "__main__":
    main()
