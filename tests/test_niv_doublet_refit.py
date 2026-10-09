"""Separate version2 doublet semantics, fixed lineage and covariant ionic controls."""

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from tools.jwst.atomic_grid import ionic_ratio
from tools.jwst.multiplet_refit import ATOMIC_GRID_SHA256, COMPONENT_GRID_SHA256, NATIVE_SHA256
from tools.jwst.niv_doublet_refit import (
    ATOMIC_V2_SHA256,
    COMPONENT_V2_SHA256,
    V1_RESULT_SHA256,
    run,
    serialized,
    validate_inputs,
)

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / "research_output" / name).read_text())


def inputs():
    return (
        read("mom_atomic_grid_niv_doublet_v2.json"),
        read("mom_multiplet_components_niv_doublet_v2.json"),
        read("mom_atomic_grid.json"),
        read("mom_multiplet_components.json"),
    )


def test_v1_inputs_remain_byte_identical_and_v2_inputs_are_independently_pinned():
    files = {
        "mom_native_reduction.json": NATIVE_SHA256,
        "mom_atomic_grid.json": ATOMIC_GRID_SHA256,
        "mom_multiplet_components.json": COMPONENT_GRID_SHA256,
        "mom_native_multiplet_refit.json": V1_RESULT_SHA256,
        "mom_atomic_grid_niv_doublet_v2.json": ATOMIC_V2_SHA256,
        "mom_multiplet_components_niv_doublet_v2.json": COMPONENT_V2_SHA256,
    }
    for filename, expected in files.items():
        assert (
            hashlib.sha256((ROOT / "research_output" / filename).read_bytes()).hexdigest()
            == expected
        )
    atomic, components, base, old_components = inputs()
    validate_inputs(atomic, components, base, old_components)
    for cell, template, old in zip(atomic["records"], components["records"], base["records"]):
        emissivities = template["components"][0]["component_emissivity_erg_cm3_s"]
        assert emissivities[1] == pytest.approx(old["emissivity_erg_cm3_s"]["NIV"], rel=1e-12)
        assert cell["emissivity_erg_cm3_s"]["NIV"] == sum(emissivities)


@pytest.mark.parametrize(
    "mutation", ["version", "units", "member", "transition", "cell", "weight", "otherion", "icf"]
)
def test_malformed_v2_contract_is_rejected(mutation):
    atomic, components, base, old_components = inputs()
    if mutation == "version":
        atomic["pyneb_version"] = "latest"
    elif mutation == "units":
        atomic["emissivity_definition"] = "counts"
    elif mutation == "member":
        atomic["atomic_files"][0]["sha256"] = "0" * 64
    elif mutation == "transition":
        atomic["transitions"]["NIV"][0]["upper_level"] = 3
    elif mutation == "cell":
        atomic["records"][0] = copy.deepcopy(atomic["records"][1])
    elif mutation == "weight":
        components["records"][0]["components"][0]["normalized_weights"] = [1, 0]
    elif mutation == "otherion":
        atomic["records"][0]["emissivity_erg_cm3_s"]["NIII"] *= 2
    else:
        atomic["ion_fraction_correction_available"] = True
    components["atomic_grid_sha256"] = hashlib.sha256(serialized(atomic)).hexdigest()
    with pytest.raises(ValueError):
        validate_inputs(atomic, components, base, old_components)


def test_internally_consistent_doublet_model_forgery_cannot_replace_pinned_bytes(tmp_path):
    atomic, components, base, old_components = inputs()
    group = components["records"][0]["components"][0]
    epsilon = np.array(group["component_emissivity_erg_cm3_s"])
    epsilon[0] *= 1.1
    group["component_emissivity_erg_cm3_s"] = epsilon.tolist()
    group["normalized_weights"] = (epsilon / epsilon.sum()).tolist()
    atomic["records"][0]["emissivity_erg_cm3_s"]["NIV"] = float(epsilon.sum())
    components["atomic_grid_sha256"] = hashlib.sha256(serialized(atomic)).hexdigest()
    validate_inputs(atomic, components, base, old_components)
    atomic_path, component_path = tmp_path / "atomic.json", tmp_path / "components.json"
    atomic_path.write_bytes(serialized(atomic))
    component_path.write_bytes(serialized(components))
    with pytest.raises(ValueError, match="independently pinned doublet"):
        run(
            ROOT / "research_output/mom_native_reduction.json",
            atomic_path,
            component_path,
            ROOT / "research_output/mom_native_multiplet_refit.json",
        )


def test_total_doublet_flux_cannot_use_the_single_line_ionic_response():
    # Equal true abundances emit unequal total fluxes. Using epsilon1486 for
    # the doublet total would introduce a spurious stage-specific factor.
    epsilon = {"NIV": 10.0, "CIV": 5.0, "HeII": 1.0, "OIII": 1.0, "NIII": 3.0, "CIII": 2.0}
    flux, covariance = np.array([10.0, 5.0, 1.0, 3.0, 2.0]), np.eye(5) * 0.01
    correct = ionic_ratio(flux, covariance, epsilon, ("NIV", "NIII"), ("CIV", "CIII"))
    wrong = ionic_ratio(flux, covariance, {**epsilon, "NIV": 4.0}, ("NIV", "NIII"), ("CIV", "CIII"))
    assert correct["value"] == pytest.approx(1)
    assert wrong["value"] == pytest.approx(1.75)


def test_saved_v2_fits_use_cell_specific_fresh_covariance_and_total_emissivity():
    atomic, _, _, _ = inputs()
    saved = read("mom_native_niv_doublet_refit_v2.json")
    parent = read("mom_native_multiplet_refit.json")
    assert saved["schema_version"] == saved["line_contract_version"] == 2
    assert saved["v1_1486_only_report_relabelled"] is False
    assert saved["elemental_abundance_identified"] is False
    assert saved["line_flux_covariance_refit_for_each_template"] is True
    assert saved["source_amplitude_noise_covariance_refit"] is False
    assert len(saved["scenarios"]) == 4
    assert saved["atomic_grid_v2_sha256"] == ATOMIC_V2_SHA256
    assert saved["component_grid_v2_sha256"] == COMPONENT_V2_SHA256
    for scenario, previous in zip(saved["scenarios"], parent["scenarios"]):
        assert scenario["name"] == previous["name"]
        assert len(scenario["records"]) == 28
        for cell, record, old in zip(atomic["records"], scenario["records"], previous["records"]):
            assert (cell["temperature_K"], cell["electron_density_cm3"]) == (
                record["temperature_K"],
                record["electron_density_cm3"],
            )
            assert record["fit"]["line_contract_version"] == 2
            assert record["fit"]["NIV_flux_definition"].startswith("Total1483.321+1486.496")
            flux = np.asarray(record["fit"]["fluxes"])
            covariance = np.asarray(record["fit"]["flux_covariance"])
            assert not np.allclose(covariance, old["fit"]["flux_covariance"], rtol=1e-4)
            e = cell["emissivity_erg_cm3_s"]
            projection = np.array(
                [
                    [e["CIII"] / e["NIV"], 0, 0, e["CIII"] / e["NIII"], 0],
                    [0, e["CIII"] / e["CIV"], 0, 0, 1],
                ]
            )
            numerator, denominator = projection @ flux
            projected = projection @ covariance @ projection.T
            answer = record["observed_two_stage_ionic_N_over_C"]
            assert answer["value"] == pytest.approx(numerator / denominator, rel=1e-12)
            assert np.allclose(answer["scaled_covariance"], projected, rtol=1e-12)
            z2 = 1.959963984540054**2
            roots = np.sort(
                np.roots(
                    [
                        denominator**2 - z2 * projected[1, 1],
                        -2 * numerator * denominator + 2 * z2 * projected[0, 1],
                        numerator**2 - z2 * projected[0, 0],
                    ]
                )
            )
            interval = answer["conditional_gaussian_95_fieller_set"]
            assert interval["type"] == "bounded"
            assert np.allclose(interval["interval"], roots, rtol=1e-11, atol=1e-12)
    # Measured result: the full empirical point-family grid admits zero numerator.
    assert all(
        r["observed_two_stage_ionic_N_over_C"]["conditional_gaussian_95_fieller_set"]["interval"][0]
        < 0
        for r in saved["scenarios"][-1]["records"]
    )
