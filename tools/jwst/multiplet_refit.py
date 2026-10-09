"""Fresh native flux likelihoods using versioned density-dependent multiplets.

This refits source amplitudes, not raw SCI pixels. The measured amplitude noise
covariance is preserved per scenario; line-flux covariance is recomputed for
every physical template. No elemental abundance, temperature or density is
identified. HeII/OIII mixing, CIV transfer and instrumental LSF remain assumed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from tools.jwst.atomic_grid import (
    ATOMIC_FILES,
    ATOMIC_MEMBER_PINS,
    LINES,
    check_fluxes,
    ionic_ratio,
    validate_grid,
)
from tools.jwst.line_sensitivity import LINE_COMPONENTS, LINE_NAMES, read_resolution
from tools.jwst.native_reduction import fit_native, load_native_replay, replay_report
from tools.jwst.point_resolution import read_point_resolution

ROOT = Path(__file__).resolve().parents[2]
NATIVE_SHA256 = "88e3cdbf5b7759eaad84dc21ead0974c38f392292d71ce605fa0f5b5951637ec"
ATOMIC_GRID_SHA256 = "b3923cd0084950e4b73a89a20848785188fc484287140c9f4d2720af43a5dc8d"
COMPONENT_GRID_SHA256 = "cbd151a8274979f9378b0ce485f23793ca77ccc9eb1df8eae391012691d3fb8e"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_component_grid(atomic: dict, atomic_sha256: str) -> dict:
    """Optional pinned PyNeb execution; the saved component grid is sufficient to replay."""
    import pyneb as pn

    validate_grid(atomic)
    if pn.__version__ != "1.1.32":
        raise ValueError("physical templates require pinned PyNeb1.1.32")
    package = Path(pn.__file__).resolve().parent
    for filename, (size, sha256) in ATOMIC_MEMBER_PINS.items():
        paths = list(package.rglob(filename))
        if len(paths) != 1 or paths[0].stat().st_size != size or digest(paths[0]) != sha256:
            raise ValueError("PyNeb member differs from independent atomic pin")
    atoms = {}
    for ion in ("N4", "C4", "N3", "C3"):
        for filename in ATOMIC_FILES[ion]:
            pn.atomicData.setDataFile(filename)
        atoms[ion] = pn.Atom(ion[0], int(ion[1:]))
    records = []
    for cell in atomic["records"]:
        temperature, density = cell["temperature_K"], cell["electron_density_cm3"]
        components = []
        for index, name in enumerate(LINE_NAMES):
            if name == "HeII_OIII":
                waves, raw_weights = LINE_COMPONENTS[index]
                weights = list(raw_weights)
                emissivities = None
                assumption = "Fixed equal HeII/OIII blend weights; ionic mixing not identified"
            else:
                ion, waves = LINES[name]
                emissivities = [
                    float(atoms[ion].getEmissivity(tem=temperature, den=density, wave=w))
                    for w in waves
                ]
                if not np.isclose(
                    sum(emissivities), cell["emissivity_erg_cm3_s"][name], rtol=1e-12, atol=0
                ):
                    raise ValueError("individual emissivity sum differs from merged atomic grid")
                weights = emissivities
                assumption = "Optically thin ionic emission at common fixed Te/ne"
            components.append(
                {
                    "group": name,
                    "vacuum_wavelengths_A": list(waves),
                    "component_emissivity_erg_cm3_s": emissivities,
                    "normalized_weights": (np.asarray(weights) / np.sum(weights)).tolist(),
                    "assumption": assumption,
                }
            )
        records.append(
            {
                "temperature_K": temperature,
                "electron_density_cm3": density,
                "components": components,
            }
        )
    result = {
        "schema_version": 1,
        "pyneb_version": "1.1.32",
        "atomic_grid_sha256": atomic_sha256,
        "atomic_files": atomic["atomic_files"],
        "records": records,
        "NIV_1483_included": False,
        "HeII_OIII_mixing_calibrated": False,
        "CIV_transfer_calibrated": False,
        "interpretation": "Physical weights for single-ion multiplets only; "
        "no ionization correction",
    }
    validate_component_grid(result, atomic, atomic_sha256)
    return result


def validate_component_grid(components: dict, atomic: dict, atomic_sha256: str) -> None:
    """Require the exact atomic contract and positive normalized physical weights."""
    validate_grid(atomic)
    if (
        components.get("schema_version") != 1
        or components.get("pyneb_version") != "1.1.32"
        or components.get("atomic_grid_sha256") != atomic_sha256
        or components.get("atomic_files") != atomic["atomic_files"]
        or components.get("NIV_1483_included") is not False
        or components.get("HeII_OIII_mixing_calibrated") is not False
        or components.get("CIV_transfer_calibrated") is not False
        or len(components.get("records", [])) != len(atomic["records"])
    ):
        raise ValueError("component grid identity/coverage differs from physical contract")
    for cell, reference in zip(components["records"], atomic["records"]):
        if (cell.get("temperature_K"), cell.get("electron_density_cm3")) != (
            reference["temperature_K"],
            reference["electron_density_cm3"],
        ):
            raise ValueError("component cells differ from atomic grid order")
        groups = cell.get("components", [])
        if len(groups) != 5:
            raise ValueError("five complete components required")
        for index, (name, group) in enumerate(zip(LINE_NAMES, groups)):
            waves = LINE_COMPONENTS[index][0] if name == "HeII_OIII" else LINES[name][1]
            weights = np.asarray(group.get("normalized_weights"), dtype=float)
            if (
                group.get("group") != name
                or group.get("vacuum_wavelengths_A") != list(waves)
                or weights.shape != (len(waves),)
                or not np.all(np.isfinite(weights) & (weights > 0))
                or not np.isclose(weights.sum(), 1, rtol=1e-12, atol=0)
            ):
                raise ValueError("invalid physical component wavelengths/weights")
            emission = group.get("component_emissivity_erg_cm3_s")
            if name == "HeII_OIII":
                if emission is not None or not np.allclose(weights, [1 / 3] * 3, rtol=1e-12):
                    raise ValueError("unknown He/O mixing cannot be supplied by ionic emissivities")
            else:
                emission = np.asarray(emission, dtype=float)
                if (
                    emission.shape != weights.shape
                    or not np.all(np.isfinite(emission) & (emission > 0))
                    or not np.isclose(
                        emission.sum(), reference["emissivity_erg_cm3_s"][name], rtol=1e-12, atol=0
                    )
                    or not np.allclose(emission / emission.sum(), weights, rtol=1e-12, atol=0)
                ):
                    raise ValueError(
                        "component emissivities must match physical weights and totals"
                    )


def run(native_path: Path, atomic_path: Path, components_path: Path) -> dict:
    """Bounded112 fits, with baseline numerical replay and complete receipts."""
    if digest(native_path) != NATIVE_SHA256:
        raise ValueError(
            "this experiment requires the independently frozen four-scenario native report"
        )
    if digest(atomic_path) != ATOMIC_GRID_SHA256:
        raise ValueError("atomic grid differs from independently frozen experiment input")
    if digest(components_path) != COMPONENT_GRID_SHA256:
        raise ValueError("component grid differs from independently frozen PyNeb output")
    native = json.loads(native_path.read_text())
    atomic = json.loads(atomic_path.read_text())
    components = json.loads(components_path.read_text())
    validate_component_grid(components, atomic, digest(atomic_path))
    baseline_control = replay_report(native_path)
    replay = load_native_replay(native_path)
    rw, rr, nominal_receipt = read_resolution(
        ROOT / "data_sources/pilot/jwst_nirspec_prism_disp.fits"
    )
    pw, pr, point_receipt = read_point_resolution(
        ROOT / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    scenarios = []
    noise_cases = [
        (rw, rr, None, 1),
        (pw, pr, None, 1),
        (rw, rr, replay["spectral_kernel"], replay["noise_scale_squared"]),
        (pw, pr, replay["spectral_kernel"], replay["noise_scale_squared"]),
    ]
    for source, (wave_r, resolution, kernel, scale) in zip(native["scenarios"], noise_cases):
        records = []
        for cell, atomic_cell in zip(components["records"], atomic["records"]):
            template = [
                (g["vacuum_wavelengths_A"], g["normalized_weights"]) for g in cell["components"]
            ]
            fit = fit_native(
                replay["data"],
                replay["flux"],
                replay["covariance_blocks"],
                replay["selected"],
                wave_r,
                resolution,
                kernel=kernel,
                noise_scale=scale,
                components=template,
            )
            converted = {
                "lines": fit["lines"],
                "line_covariance": fit["flux_covariance"],
                "line_flux_unit": fit["flux_units"],
            }
            flux, covariance = check_fluxes(converted)
            epsilon = atomic_cell["emissivity_erg_cm3_s"]
            ionic = ionic_ratio(flux, covariance, epsilon, ("NIV", "NIII"), ("CIV", "CIII"))
            records.append(
                {
                    "temperature_K": cell["temperature_K"],
                    "electron_density_cm3": cell["electron_density_cm3"],
                    "fit": fit,
                    "observed_two_stage_ionic_N_over_C": ionic,
                    "maximum_line_flux_change_from_fixed_template": float(
                        np.max(np.abs(flux - np.asarray(source["fit"]["fluxes"])))
                    ),
                    "maximum_line_covariance_change_from_fixed_template": float(
                        np.max(np.abs(covariance - np.asarray(source["fit"]["flux_covariance"])))
                    ),
                }
            )
        scenarios.append({"name": source["name"], "records": records})
    return {
        "schema_version": 1,
        "native_report_sha256": digest(native_path),
        "native_replay_receipt": native["compact_native_replay"],
        "atomic_grid_sha256": digest(atomic_path),
        "component_grid_sha256": digest(components_path),
        "baseline_default_template_replay": baseline_control,
        "resolution_provenance": {"nominal": nominal_receipt, "generic_point": point_receipt},
        "software_files": [
            {"filename": str(p.relative_to(ROOT)), "sha256": digest(p)}
            for p in (
                ROOT / "tools/jwst/multiplet_refit.py",
                ROOT / "tools/jwst/native_reduction.py",
                ROOT / "tools/jwst/line_sensitivity.py",
                ROOT / "tools/jwst/atomic_grid.py",
            )
        ],
        "scenarios": scenarios,
        "source_amplitude_noise_covariance_refit": False,
        "line_flux_covariance_refit_for_each_template": True,
        "NIV_1483_included": False,
        "HeII_OIII_mixing_calibrated": False,
        "source_specific_LSF_calibrated": False,
        "CIV_transfer_calibrated": False,
        "ion_fraction_correction_available": False,
        "elemental_abundance_identified": False,
        "grid_axes_identified": False,
        "scenarios_are_independent_likelihoods": False,
        "interpretation": "Conditional density-dependent ionic multiplet refits; "
        "shared observations, "
        "fixed geometry/covariance/HeO mixing, uncalibrated source-specific LSF and CIV transfer",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate-components", type=Path)
    parser.add_argument(
        "--atomic", type=Path, default=ROOT / "research_output/mom_atomic_grid.json"
    )
    parser.add_argument(
        "--native", type=Path, default=ROOT / "research_output/mom_native_reduction.json"
    )
    parser.add_argument(
        "--components", type=Path, default=ROOT / "research_output/mom_multiplet_components.json"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "research_output/mom_native_multiplet_refit.json"
    )
    args = parser.parse_args()
    if args.generate_components:
        result = make_component_grid(json.loads(args.atomic.read_text()), digest(args.atomic))
        target = args.generate_components
    else:
        result = run(args.native, args.atomic, args.components)
        target = args.output
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(target),
                "records": len(result.get("records", [])),
                "scenarios": len(result.get("scenarios", [])),
            }
        )
    )


if __name__ == "__main__":
    main()
