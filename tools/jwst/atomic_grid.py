"""Versioned UV ionic emissivities and covariant conditional ionic ratios.

This supplies a missing atomic map but NEVER supplies an ionization correction.
The same homogeneous Te/ne for all ions, collision-only CIV, no resonant transfer,
no differential attenuation, and line-group templates are explicit assumptions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from tools.jwst.line_sensitivity import LINE_NAMES, fieller_set

ATOMIC_FILES = {
    "N4": ("n_iv_atom_WFD96.dat", "n_iv_coll_RBHB94.dat"),
    "N3": ("n_iii_atom_GMZ98.dat", "n_iii_coll_BP92.dat"),
    "C4": ("c_iv_atom_WFD96.dat", "c_iv_coll_AK04.dat"),
    "C3": ("c_iii_atom_G83-NS78-WFD96.dat", "c_iii_coll_Bal85.dat"),
    # The default 5-level collision set lacks the UV 1661/1666 upper level.
    "O3": ("o_iii_atom_FFT04-SZ00.dat", "o_iii_coll_TZ17.dat"),
    # FITS and case B are explicit; no optional HDF5 dependency is required.
    "He2": ("he_ii_rec_SH95.fits",),
}
LINES = {
    "NIV": ("N4", (1486.496,)),
    "CIV": ("C4", (1548.204, 1550.781)),
    "NIII": ("N3", (1746.823, 1748.646, 1749.674, 1752.16, 1753.995)),
    "CIII": ("C3", (1906.683, 1908.734)),
    "OIII": ("O3", (1660.809, 1666.15)),
    "HeII": ("He2", (1640.42,)),
}
TEMPERATURES = (5000, 7500, 10000, 15000, 20000, 25000, 30000)
DENSITIES = (100, 1000, 10000, 100000)


# Independently frozen members of the publisher-hash-verified PyNeb wheel.
ATOMIC_MEMBER_PINS = {
    "n_iv_atom_WFD96.dat": (
        581,
        "52c5db33fe42acf6501cddd44eea9d8bef18bc2ea9ba103556a5c17ffca6323f",
    ),
    "n_iv_coll_RBHB94.dat": (
        1470,
        "90700c6d32c807b6acc0c975892335751ce1de545398e34549fc2563f2973339",
    ),
    "n_iii_atom_GMZ98.dat": (
        1129,
        "8ae8cbd0c38753c3f5617973bff58b611d3392438e7bdef3fa3d10af328b32bc",
    ),
    "n_iii_coll_BP92.dat": (
        8148,
        "977024d9a257c2bfdb42cae3e6e7e6a9c974d1b510af9ccab595416869430c5c",
    ),
    "c_iv_atom_WFD96.dat": (
        333,
        "fa5d2c45bf74d8b38759e88503d265e4be7bdd5350dd27b017c2ac865f64f752",
    ),
    "c_iv_coll_AK04.dat": (
        335,
        "be270bc39589b41a20f7c9331e38dc6ac9ed35a6e06cb96cb1ab72d070dcd1a3",
    ),
    "c_iii_atom_G83-NS78-WFD96.dat": (
        732,
        "078f5127fef00ad336cc885650ff3a73ad2755155ab51da0fa3045f54fb61d80",
    ),
    "c_iii_coll_Bal85.dat": (
        1249,
        "c19b8c06a3ea9257db83c8aef0f4c8415684b2748c9587479a7a428c5cae96ab",
    ),
    "o_iii_atom_FFT04-SZ00.dat": (
        808,
        "f802375827fa91d68ff6cc6f0cb811397d5358811207ae90b52996820a612ff1",
    ),
    "o_iii_coll_TZ17.dat": (
        1989841,
        "a2857d2f4cd211ed263039beb9dcc6dbf7dbe0e8fe665529236798c3eb9e53b7",
    ),
    "he_ii_rec_SH95.fits": (
        1480320,
        "798f38646be61942eb01820c3c6be7f0a3f8eaa1744c7f1acacfb19cd048e7a8",
    ),
}


def validate_grid(grid: dict[str, Any]) -> None:
    """Reject malformed/silently substituted line-contract or physical inputs."""
    if grid.get("schema_version") != 1 or grid.get("pyneb_version") != "1.1.32":
        raise ValueError("unsupported atomic grid schema/version")
    if grid.get("emissivity_definition") != "j_line / (n_e n_ion), erg cm^3 s^-1":
        raise ValueError("atomic emissivity units differ from pinned contract")
    if grid.get("photoionization_grid") is not False:
        raise ValueError("ionic grid must not claim a photoionization correction")
    expected_files = {x for files in ATOMIC_FILES.values() for x in files}
    files = grid.get("atomic_files", [])
    if len(files) != len(expected_files) or {x.get("filename") for x in files} != expected_files:
        raise ValueError("atomic file inventory differs from pinned contract")
    for record in files:
        expected_size, expected_digest = ATOMIC_MEMBER_PINS[record["filename"]]
        if record.get("bytes") != expected_size or record.get("sha256") != expected_digest:
            raise ValueError("atomic provenance differs from independently pinned package member")
        digest = record.get("sha256", "")
        if len(digest) != 64 or any(x not in "0123456789abcdef" for x in digest):
            raise ValueError("missing atomic-file SHA256 provenance")
        if not isinstance(record.get("bytes"), int) or record["bytes"] <= 0:
            raise ValueError("missing atomic-file byte provenance")
    transitions = grid.get("transitions", {})
    for name, (ion, waves) in LINES.items():
        if ion == "He2":
            continue
        selected = transitions.get(name, [])
        if len(selected) != len(waves) or [x.get("requested_vacuum_A") for x in selected] != list(
            waves
        ):
            raise ValueError("atomic grid wavelengths differ from observed-group contract")
        levels = [(x.get("upper_level"), x.get("lower_level")) for x in selected]
        if len(set(levels)) != len(levels) or any(
            not isinstance(i, int) or not isinstance(j, int) or i <= j or j < 1 for i, j in levels
        ):
            raise ValueError("invalid or duplicate atomic transitions")
    cells = grid.get("records", [])
    expected_cells = {(t, d) for t in TEMPERATURES for d in DENSITIES}
    if (
        len(cells) != len(expected_cells)
        or {(x.get("temperature_K"), x.get("electron_density_cm3")) for x in cells}
        != expected_cells
    ):
        raise ValueError("atomic grid temperature/density cells missing or duplicated")
    for cell in cells:
        emissivity = cell.get("emissivity_erg_cm3_s", {})
        if set(emissivity) != set(LINES) or any(
            not isinstance(x, (float, int)) or not math.isfinite(x) or x <= 0
            for x in emissivity.values()
        ):
            raise ValueError("all six ionic emissivities must be finite and positive")


def make_grid() -> dict[str, Any]:
    """Run the optional pinned PyNeb solver and record every actual atomic file."""
    import pyneb as pn

    if pn.__version__ != "1.1.32":
        raise ValueError("grid generation requires pinned PyNeb 1.1.32")
    atoms = {}
    for ion, files in ATOMIC_FILES.items():
        for filename in files:
            pn.atomicData.setDataFile(filename)
        if ion == "He2":
            atoms[ion] = pn.RecAtom("He", 2, case="B")
        else:
            atoms[ion] = pn.Atom(ion[0], int(ion[1:]))
    package = Path(pn.__file__).resolve().parent
    provenance = []
    for ion, files in ATOMIC_FILES.items():
        for filename in files:
            matches = list(package.rglob(filename))
            if len(matches) != 1:
                raise ValueError("atomic file must have one package location")
            data = matches[0].read_bytes()
            provenance.append(
                {
                    "ion": ion,
                    "filename": filename,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "sources": atoms[ion].getSources() if ion != "He2" else atoms[ion].sources,
                }
            )
    records = []
    transitions = {}
    for temperature in TEMPERATURES:
        for density in DENSITIES:
            emission = {}
            for name, (ion, waves) in LINES.items():
                atom = atoms[ion]
                values = [
                    float(atom.getEmissivity(tem=temperature, den=density, wave=w)) for w in waves
                ]
                if not all(math.isfinite(v) and v > 0 for v in values):
                    raise ValueError("finite positive emissivities required")
                emission[name] = sum(values)
                if ion != "He2":
                    actual = [atom.getTransition(w) for w in waves]
                    if len(set(actual)) != len(actual):
                        raise ValueError("line wavelengths ambiguously reuse a transition")
                    transitions[name] = [
                        {
                            "requested_vacuum_A": w,
                            "upper_level": int(i),
                            "lower_level": int(j),
                            "atomic_wavelength_A": float(atom.wave_Ang[i - 1, j - 1]),
                        }
                        for w, (i, j) in zip(waves, actual)
                    ]
            records.append(
                {
                    "temperature_K": temperature,
                    "electron_density_cm3": density,
                    "emissivity_erg_cm3_s": emission,
                }
            )
    return {
        "schema_version": 1,
        "pyneb_version": pn.__version__,
        "emissivity_definition": "j_line / (n_e n_ion), erg cm^3 s^-1",
        "atomic_files": provenance,
        "transitions": transitions,
        "records": records,
        "photoionization_grid": False,
        "ion_fraction_correction_available": False,
        "assumptions": [
            "Homogeneous common electron temperature and density for all emitting ions",
            "NIV uses 1486.496 only, matching stored flux template; 1483 is not added",
            "NIII five specified UV lines; CIII/CIV doublets; OIII 1661/1666",
            "Collisionally excited, optically thin CIV; no stellar/resonant transfer component",
            "HeII case B recombination; no HeII/OIII blend decomposition from observations",
            "No differential attenuation, elemental closure, ion fractions, or gas mass measured",
        ],
    }


def check_fluxes(fit: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    if fit.get("line_flux_unit") != "1e-20 erg s^-1 cm^-2":
        raise ValueError("flux units differ from pinned covariance contract")
    if list(fit["lines"]) != list(LINE_NAMES):
        raise ValueError("flux/covariance order differs from five pinned groups")
    flux = np.asarray([fit["lines"][x]["flux"] for x in LINE_NAMES], dtype=float)
    covariance = np.asarray(fit["line_covariance"], dtype=float)
    if covariance.shape != (5, 5) or not np.all(np.isfinite(covariance)):
        raise ValueError("full finite five-group covariance required")
    if not np.all(np.isfinite(flux)) or not np.allclose(covariance, covariance.T):
        raise ValueError("finite flux and symmetric covariance required")
    if np.min(np.linalg.eigvalsh(covariance)) <= 0:
        raise ValueError("positive definite covariance required")
    for index, name in enumerate(LINE_NAMES):
        if "conditional_sigma" in fit["lines"][name]:
            sigma = fit["lines"][name]["conditional_sigma"]
            if (
                not math.isfinite(sigma)
                or sigma <= 0
                or not np.isclose(sigma**2, covariance[index, index], rtol=1e-8)
            ):
                raise ValueError("stated line sigma disagrees with covariance diagonal")
    return flux, covariance


def ionic_ratio(
    flux: np.ndarray,
    covariance: np.ndarray,
    emissivity: dict[str, float],
    numerator: tuple[str, ...],
    denominator: tuple[str, ...],
) -> dict[str, Any]:
    """Apply the emissivity map linearly, preserving negative/unbounded Fieller sets."""
    # Scale the operator to avoid huge 1/emissivity values; the ratio is unchanged.
    scale = emissivity["CIII"]
    a = np.array([scale / emissivity[x] if x in numerator else 0 for x in LINE_NAMES])
    b = np.array([scale / emissivity[x] if x in denominator else 0 for x in LINE_NAMES])
    nf, df = float(a @ flux), float(b @ flux)
    nv, dv, nd = float(a @ covariance @ a), float(b @ covariance @ b), float(a @ covariance @ b)
    value = nf / df if df != 0 else None
    confidence = fieller_set(nf, df, nv, dv, nd, 1.95996398454**2)
    return {
        "value": value,
        "log_ratio_relative_to_solar_NC_minus_0_60": math.log10(value) + 0.60
        if value is not None and value > 0
        else None,
        "conditional_gaussian_95_fieller_set": confidence,
        "scaled_numerator": nf,
        "scaled_denominator": df,
        "scaled_covariance": [[nv, nd], [nd, dv]],
    }


def analyze_fit(fit: dict[str, Any], grid: dict[str, Any]) -> dict[str, Any]:
    validate_grid(grid)
    flux, covariance = check_fluxes(fit)
    rows = []
    for record in grid["records"]:
        epsilon = record["emissivity_erg_cm3_s"]
        rows.append(
            {
                "temperature_K": record["temperature_K"],
                "electron_density_cm3": record["electron_density_cm3"],
                "N2_over_C2": ionic_ratio(flux, covariance, epsilon, ("NIII",), ("CIII",)),
                "N3_over_C3": ionic_ratio(flux, covariance, epsilon, ("NIV",), ("CIV",)),
                "observed_two_stage_ionic_N_over_C": ionic_ratio(
                    flux, covariance, epsilon, ("NIV", "NIII"), ("CIV", "CIII")
                ),
            }
        )
    points = [
        x["observed_two_stage_ionic_N_over_C"]["log_ratio_relative_to_solar_NC_minus_0_60"]
        for x in rows
    ]
    positive_points = [x for x in points if x is not None]
    return {
        "extraction": fit.get("extraction"),
        "assumed_rho": fit.get("rho_assumed"),
        "flux_unit": fit.get("line_flux_unit"),
        "records": rows,
        "grid_point_ionic_log_ratio_relative_to_solar_range": [
            min(positive_points),
            max(positive_points),
        ]
        if positive_points
        else None,
        "grid_range_is_confidence_interval": False,
        "elemental_abundance_identified": False,
        "helium_oxygen_ionic_operator": {
            "observed_groups": 5,
            "ionic_amplitudes": 6,
            "rank": 5,
            "HeII_OIII_separated": False,
        },
        "interpretation": "Conditional (N2+ + N3+) / (C2+ + C3+) only. Elemental N/C "
        "also needs ratio of observed carbon/nitrogen ion fractions; unconstrained here.",
    }


def spectral_scenarios(spectrum: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Adapt independent native flux likelihoods without weakening order/units guards."""
    if "nominal_reference_fit" in spectrum:
        return [
            ("nominal_illuminated_slit", spectrum["nominal_reference_fit"]),
            ("generic_point_source", spectrum["point_source_scenarios"][0]),
        ]
    result = []
    for scenario in spectrum["scenarios"]:
        fit = scenario["fit"]
        if fit["line_order"] != list(LINE_NAMES) or len(fit["fluxes"]) != 5:
            raise ValueError("native fit line order/length differs from atomic contract")
        converted = {
            "lines": {
                name: {
                    "flux": value,
                    **(
                        {"conditional_sigma": fit["lines"][name]["conditional_sigma"]}
                        if "lines" in fit
                        else {}
                    ),
                }
                for name, value in zip(LINE_NAMES, fit["fluxes"])
            },
            "line_covariance": fit["flux_covariance"],
            "line_flux_unit": fit["flux_units"],
            "extraction": "independent_native_nod_reconstruction",
            "rho_assumed": None,
        }
        check_fluxes(converted)
        result.append((scenario["name"], converted))
    if not result:
        raise ValueError("native spectrum has no fit scenarios")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate-grid", type=Path)
    parser.add_argument("--grid", type=Path, default=Path("research_output/mom_atomic_grid.json"))
    parser.add_argument(
        "--spectrum", type=Path, default=Path("research_output/mom_z14_point_resolution.json")
    )
    parser.add_argument("--output", type=Path, default=Path("research_output/mom_ionic_fit.json"))
    args = parser.parse_args()
    if args.generate_grid:
        args.generate_grid.write_text(json.dumps(make_grid(), indent=2) + "\n")
        return
    grid = json.loads(args.grid.read_text())
    spectrum = json.loads(args.spectrum.read_text())
    output = {
        "schema_version": 1,
        "grid_sha256": hashlib.sha256(args.grid.read_bytes()).hexdigest(),
        "spectrum_sha256": hashlib.sha256(args.spectrum.read_bytes()).hexdigest(),
        "models": [
            {"resolution_family": label, **analyze_fit(fit, grid)}
            for label, fit in spectral_scenarios(spectrum)
        ],
        "ion_fraction_correction_available": False,
        "scenarios_are_independent_likelihoods": False,
    }
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "models": len(output["models"])}, indent=2))


if __name__ == "__main__":
    main()
