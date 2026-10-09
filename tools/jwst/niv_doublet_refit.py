"""Version2 N IV1483+1486 total-flux contract and fresh native spectral fits.

The separate v1 single-line grids/reports are preserved. Here the N IV group
means the total doublet flux under an explicit optically thin ionic template.
Every temperature/density cell has a new spectral covariance before its new
summed N IV emissivity is used. This does not identify elemental N/C or an ICF.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np

from tools.jwst.atomic_grid import (
    ATOMIC_FILES,
    ATOMIC_MEMBER_PINS,
    check_fluxes,
    ionic_ratio,
    validate_grid,
)
from tools.jwst.line_sensitivity import read_resolution
from tools.jwst.multiplet_refit import (
    ATOMIC_GRID_SHA256,
    COMPONENT_GRID_SHA256,
    NATIVE_SHA256,
    digest,
    validate_component_grid,
)
from tools.jwst.native_reduction import fit_native, load_native_replay, replay_report
from tools.jwst.point_resolution import read_point_resolution

ROOT = Path(__file__).resolve().parents[2]
NIV_WAVES = (1483.321, 1486.496)
# Independently frozen after actual PyNeb execution; changes need a new experiment version.
ATOMIC_V2_SHA256 = "a48ea0076ae9f6ef4d76845644880776c266efce0a281b0866d12889e36b1e0e"
COMPONENT_V2_SHA256 = "692ce2fe0ca5463708abfa3c232378f3aebe22ff9b96f97d779091d54ac5f474"
V1_RESULT_SHA256 = "9248284f52552e88fa002351d9b39aec419cc27e76c631ab6cffae2c5e09e929"


def serialized(data: dict) -> bytes:
    return (json.dumps(data, indent=2, allow_nan=False) + "\n").encode()


def generate_inputs(atomic_path: Path, components_path: Path) -> tuple[dict, dict]:
    """Execute the verified N4 solver; other ionic components retain exact v1 values."""
    import pyneb as pn

    if (
        digest(atomic_path) != ATOMIC_GRID_SHA256
        or digest(components_path) != COMPONENT_GRID_SHA256
    ):
        raise ValueError("v1 source grid differs from independent experiment pin")
    base = json.loads(atomic_path.read_text())
    source_components = json.loads(components_path.read_text())
    validate_grid(base)
    validate_component_grid(source_components, base, digest(atomic_path))
    if pn.__version__ != "1.1.32":
        raise ValueError("v2 generation requires pinned PyNeb1.1.32")
    package = Path(pn.__file__).resolve().parent
    for name in ATOMIC_FILES["N4"]:
        size, expected_sha256 = ATOMIC_MEMBER_PINS[name]
        paths = list(package.rglob(name))
        if (
            len(paths) != 1
            or paths[0].stat().st_size != size
            or digest(paths[0]) != expected_sha256
        ):
            raise ValueError("N4 member differs from independent atomic pin")
        pn.atomicData.setDataFile(name)
    atom = pn.Atom("N", 4)
    transitions = [atom.getTransition(w) for w in NIV_WAVES]
    if len(set(transitions)) != 2:
        raise ValueError("N IV doublet needs two distinct atomic transitions")
    atomic, components = copy.deepcopy(base), copy.deepcopy(source_components)
    atomic["schema_version"] = components["schema_version"] = 2
    atomic["line_contract_version"] = components["line_contract_version"] = 2
    atomic["parent_v1_atomic_grid_sha256"] = components["parent_v1_atomic_grid_sha256"] = digest(
        atomic_path
    )
    components["parent_v1_component_grid_sha256"] = digest(components_path)
    atomic["transitions"]["NIV"] = [
        {
            "requested_vacuum_A": w,
            "upper_level": int(i),
            "lower_level": int(j),
            "atomic_wavelength_A": float(atom.wave_Ang[i - 1, j - 1]),
        }
        for w, (i, j) in zip(NIV_WAVES, transitions)
    ]
    atomic["assumptions"] = [
        "NIV means total1483.321+1486.496 doublet under a physical optically thin ionic template"
        if item.startswith("NIV uses")
        else item
        for item in atomic["assumptions"]
    ]
    atomic["NIV_1483_included"] = components["NIV_1483_included"] = True
    components["interpretation"] = (
        "Version2 physical N IV1483+1486 total-flux contract; no ionization correction"
    )
    for atomic_cell, template_cell, reference in zip(
        atomic["records"], components["records"], base["records"]
    ):
        emission = [
            float(
                atom.getEmissivity(
                    tem=atomic_cell["temperature_K"],
                    den=atomic_cell["electron_density_cm3"],
                    wave=w,
                )
            )
            for w in NIV_WAVES
        ]
        if not np.isclose(
            emission[1], reference["emissivity_erg_cm3_s"]["NIV"], rtol=1e-12, atol=0
        ):
            raise ValueError("v2 1486 emissivity does not reproduce the pinned v1 single line")
        atomic_cell["emissivity_erg_cm3_s"]["NIV"] = sum(emission)
        group = template_cell["components"][0]
        group["vacuum_wavelengths_A"] = list(NIV_WAVES)
        group["component_emissivity_erg_cm3_s"] = emission
        group["normalized_weights"] = (np.asarray(emission) / sum(emission)).tolist()
        group["assumption"] = "Version2 N IV total doublet at common fixed Te/ne; optically thin"
    components["atomic_grid_sha256"] = hashlib.sha256(serialized(atomic)).hexdigest()
    validate_inputs(atomic, components, base, source_components)
    return atomic, components


def validate_inputs(atomic: dict, components: dict, base: dict, source_components: dict) -> None:
    """Narrow version2 change: only N IV component/total response can differ from v1."""
    validate_grid(base)
    validate_component_grid(source_components, base, ATOMIC_GRID_SHA256)
    for grid in (atomic, components):
        if (
            grid.get("schema_version") != 2
            or grid.get("line_contract_version") != 2
            or grid.get("pyneb_version") != "1.1.32"
            or grid.get("parent_v1_atomic_grid_sha256") != ATOMIC_GRID_SHA256
            or grid.get("NIV_1483_included") is not True
            or grid.get("atomic_files") != base["atomic_files"]
            or len(grid.get("records", [])) != 28
        ):
            raise ValueError("v2 grid identity/coverage differs from independently pinned contract")
    if atomic.get("emissivity_definition") != base["emissivity_definition"]:
        raise ValueError("v2 atomic emissivity units differ from pinned physical contract")
    if components.get("parent_v1_component_grid_sha256") != COMPONENT_GRID_SHA256:
        raise ValueError("v2 source component lineage differs from v1 pin")
    if components.get("atomic_grid_sha256") != hashlib.sha256(serialized(atomic)).hexdigest():
        raise ValueError("v2 component/atomic lineage mismatch")
    transitions = atomic.get("transitions", {}).get("NIV", [])
    if [x.get("requested_vacuum_A") for x in transitions] != list(NIV_WAVES) or [
        (x.get("upper_level"), x.get("lower_level")) for x in transitions
    ] != [(4, 1), (3, 1)]:
        raise ValueError("v2 requires the distinct pinned 1483/1486 transitions")
    for name in base["transitions"]:
        if name != "NIV" and atomic["transitions"].get(name) != base["transitions"][name]:
            raise ValueError("non-NIV transition changed under the v2 contract")
    for cell, template, reference, old_template in zip(
        atomic["records"], components["records"], base["records"], source_components["records"]
    ):
        expected_cell = (reference["temperature_K"], reference["electron_density_cm3"])
        if any(
            (item.get("temperature_K"), item.get("electron_density_cm3")) != expected_cell
            for item in (cell, template)
        ):
            raise ValueError("v2 temperature/density cell order differs from v1")
        old_e, new_e = reference["emissivity_erg_cm3_s"], cell.get("emissivity_erg_cm3_s", {})
        if set(new_e) != set(old_e) or any(new_e[n] != old_e[n] for n in old_e if n != "NIV"):
            raise ValueError("only the N IV emissivity may change in this version")
        groups = template.get("components", [])
        if len(groups) != 5 or groups[1:] != old_template["components"][1:]:
            raise ValueError("non-NIV components differ from v1")
        group = groups[0]
        emission = np.asarray(group.get("component_emissivity_erg_cm3_s"), dtype=float)
        weights = np.asarray(group.get("normalized_weights"), dtype=float)
        if (
            group.get("group") != "NIV"
            or group.get("vacuum_wavelengths_A") != list(NIV_WAVES)
            or emission.shape != (2,)
            or weights.shape != (2,)
            or not np.all(np.isfinite(emission) & (emission > 0))
            or not np.all(np.isfinite(weights) & (weights > 0))
            or not np.isclose(emission[1], old_e["NIV"], rtol=1e-12, atol=0)
            or not np.isclose(emission.sum(), new_e["NIV"], rtol=1e-12, atol=0)
            or not np.allclose(weights, emission / emission.sum(), rtol=1e-12, atol=0)
        ):
            raise ValueError("invalid N IV doublet weights/emissivity closure")
    if any(
        components.get(key) is not False
        for key in ("HeII_OIII_mixing_calibrated", "CIV_transfer_calibrated")
    ):
        raise ValueError("N IV doublet cannot close unknown He/O mixing or CIV transfer")
    if (
        atomic.get("photoionization_grid") is not False
        or atomic.get("ion_fraction_correction_available") is not False
    ):
        raise ValueError("N IV atomic doublet cannot supply an ionization correction")


def run(
    native_path: Path, atomic_v2_path: Path, components_v2_path: Path, v1_result_path: Path
) -> dict:
    if digest(native_path) != NATIVE_SHA256 or digest(v1_result_path) != V1_RESULT_SHA256:
        raise ValueError("native/v1 physical-fit bytes differ from independently frozen input")
    if (
        digest(atomic_v2_path) != ATOMIC_V2_SHA256
        or digest(components_v2_path) != COMPONENT_V2_SHA256
    ):
        raise ValueError("v2 model bytes differ from independently pinned doublet experiment")
    base_path = ROOT / "research_output/mom_atomic_grid.json"
    base_components_path = ROOT / "research_output/mom_multiplet_components.json"
    if (
        digest(base_path) != ATOMIC_GRID_SHA256
        or digest(base_components_path) != COMPONENT_GRID_SHA256
    ):
        raise ValueError("v1 model lineage differs from independent experiment pins")
    atomic, components = (
        json.loads(atomic_v2_path.read_text()),
        json.loads(components_v2_path.read_text()),
    )
    validate_inputs(
        atomic,
        components,
        json.loads(base_path.read_text()),
        json.loads(base_components_path.read_text()),
    )
    native, v1_result = json.loads(native_path.read_text()), json.loads(v1_result_path.read_text())
    baseline = replay_report(native_path)
    replay = load_native_replay(native_path)
    rw, rr, nominal = read_resolution(ROOT / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
    pw, pr, point = read_point_resolution(
        ROOT / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    cases = [
        (rw, rr, None, 1),
        (pw, pr, None, 1),
        (rw, rr, replay["spectral_kernel"], replay["noise_scale_squared"]),
        (pw, pr, replay["spectral_kernel"], replay["noise_scale_squared"]),
    ]
    scenarios = []
    for source, previous, (resolution_wave, resolution, kernel, scale) in zip(
        native["scenarios"], v1_result["scenarios"], cases
    ):
        if source["name"] != previous["name"] or len(previous["records"]) != 28:
            raise ValueError("v1 spectral parent scenario/cell mismatch")
        records = []
        for cell, template, old in zip(
            atomic["records"], components["records"], previous["records"]
        ):
            if (cell["temperature_K"], cell["electron_density_cm3"]) != (
                old["temperature_K"],
                old["electron_density_cm3"],
            ):
                raise ValueError("v1 comparison does not have the same fixed Te/ne cell")
            fit = fit_native(
                replay["data"],
                replay["flux"],
                replay["covariance_blocks"],
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
            fit["line_contract_version"] = 2
            fit["NIV_flux_definition"] = (
                "Total1483.321+1486.496 under the normalized physical doublet template"
            )
            flux, covariance = check_fluxes(
                {
                    "lines": fit["lines"],
                    "line_covariance": fit["flux_covariance"],
                    "line_flux_unit": fit["flux_units"],
                }
            )
            ionic = ionic_ratio(
                flux, covariance, cell["emissivity_erg_cm3_s"], ("NIV", "NIII"), ("CIV", "CIII")
            )
            old_ionic = old["observed_two_stage_ionic_N_over_C"]
            records.append(
                {
                    "temperature_K": cell["temperature_K"],
                    "electron_density_cm3": cell["electron_density_cm3"],
                    "fit": fit,
                    "observed_two_stage_ionic_N_over_C": ionic,
                    "NIV_doublet_emissivity_over_v1_1486": sum(
                        template["components"][0]["component_emissivity_erg_cm3_s"]
                    )
                    / template["components"][0]["component_emissivity_erg_cm3_s"][1],
                    "NIV_total_flux_change_from_v1_1486_template": float(
                        flux[0] - old["fit"]["fluxes"][0]
                    ),
                    "ionic_ratio_change_from_v1": ionic["value"] - old_ionic["value"],
                    "conditional_chi2_change_from_v1": fit["conditional_chi2"]
                    - old["fit"]["conditional_chi2"],
                }
            )
        scenarios.append({"name": source["name"], "records": records})
    return {
        "schema_version": 2,
        "line_contract_version": 2,
        "native_report_sha256": digest(native_path),
        "native_replay_receipt": native["compact_native_replay"],
        "v1_physical_fit_sha256": digest(v1_result_path),
        "parent_v1_atomic_grid_sha256": digest(base_path),
        "atomic_grid_v2_sha256": digest(atomic_v2_path),
        "component_grid_v2_sha256": digest(components_v2_path),
        "baseline_default_template_replay": baseline,
        "resolution_provenance": {"nominal": nominal, "generic_point": point},
        "software_files": [
            {"filename": str(p.relative_to(ROOT)), "sha256": digest(p)}
            for p in (
                ROOT / "tools/jwst/niv_doublet_refit.py",
                ROOT / "tools/jwst/native_reduction.py",
                ROOT / "tools/jwst/line_sensitivity.py",
                ROOT / "tools/jwst/atomic_grid.py",
                ROOT / "tools/jwst/multiplet_refit.py",
            )
        ],
        "scenarios": scenarios,
        "NIV_1483_included": True,
        "v1_1486_only_report_relabelled": False,
        "line_flux_covariance_refit_for_each_template": True,
        "source_amplitude_noise_covariance_refit": False,
        "HeII_OIII_mixing_calibrated": False,
        "CIV_transfer_calibrated": False,
        "source_specific_LSF_calibrated": False,
        "ion_fraction_correction_available": False,
        "elemental_abundance_identified": False,
        "grid_axes_identified": False,
        "scenarios_are_independent_likelihoods": False,
        "interpretation": "Version2 N IV total doublet likelihoods and conditional ionic ratios, "
        "not relabelled v1 fluxes, elemental abundances or independent likelihoods",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate-inputs", type=Path)
    parser.add_argument(
        "--native", type=Path, default=ROOT / "research_output/mom_native_reduction.json"
    )
    parser.add_argument(
        "--atomic-v2",
        type=Path,
        default=ROOT / "research_output/mom_atomic_grid_niv_doublet_v2.json",
    )
    parser.add_argument(
        "--components-v2",
        type=Path,
        default=ROOT / "research_output/mom_multiplet_components_niv_doublet_v2.json",
    )
    parser.add_argument(
        "--v1-result", type=Path, default=ROOT / "research_output/mom_native_multiplet_refit.json"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "research_output/mom_native_niv_doublet_refit_v2.json"
    )
    args = parser.parse_args()
    if args.generate_inputs:
        atomic, components = generate_inputs(
            ROOT / "research_output/mom_atomic_grid.json",
            ROOT / "research_output/mom_multiplet_components.json",
        )
        args.generate_inputs.mkdir(parents=True, exist_ok=True)
        for name, data in (
            ("mom_atomic_grid_niv_doublet_v2.json", atomic),
            ("mom_multiplet_components_niv_doublet_v2.json", components),
        ):
            path = args.generate_inputs / name
            path.write_bytes(serialized(data))
            print(json.dumps({"output": str(path), "sha256": digest(path)}))
    else:
        result = run(args.native, args.atomic_v2, args.components_v2, args.v1_result)
        args.output.write_bytes(serialized(result))
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "spectral_fits": sum(len(s["records"]) for s in result["scenarios"]),
                }
            )
        )


if __name__ == "__main__":
    main()
