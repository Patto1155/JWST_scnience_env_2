"""Independent linear likelihood checks on frozen native chemistry artifacts."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
NATIVE_SHA256 = "88e3cdbf5b7759eaad84dc21ead0974c38f392292d71ce605fa0f5b5951637ec"


def read(name):
    return json.loads((ROOT / "research_output" / name).read_text())


def test_frozen_native_ionic_likelihood_by_independent_projection():
    native_path = ROOT / "research_output/mom_native_reduction.json"
    assert hashlib.sha256(native_path.read_bytes()).hexdigest() == NATIVE_SHA256
    native, grid, saved = (
        read("mom_native_reduction.json"),
        read("mom_atomic_grid.json"),
        read("mom_native_ionic_fit.json"),
    )
    assert saved["spectrum_sha256"] == NATIVE_SHA256
    assert saved["grid_sha256"] == hashlib.sha256(
        (ROOT / "research_output/mom_atomic_grid.json").read_bytes()
    ).hexdigest()
    assert len(saved["models"]) == len(native["scenarios"]) == 4
    for source, model in zip(native["scenarios"], saved["models"]):
        assert model["resolution_family"] == source["name"]
        assert model["elemental_abundance_identified"] is False
        flux = np.asarray(source["fit"]["fluxes"])
        covariance = np.asarray(source["fit"]["flux_covariance"])
        assert len(model["records"]) == len(grid["records"]) == 28
        for cell, result in zip(grid["records"], model["records"]):
            assert (result["temperature_K"], result["electron_density_cm3"]) == (
                cell["temperature_K"], cell["electron_density_cm3"]
            )
            e = cell["emissivity_erg_cm3_s"]
            matrix = np.array(
                [[e["CIII"] / e["NIV"], 0, 0, e["CIII"] / e["NIII"], 0],
                 [0, e["CIII"] / e["CIV"], 0, 0, 1]]
            )
            numerator, denominator = matrix @ flux
            projected = matrix @ covariance @ matrix.T
            answer = result["observed_two_stage_ionic_N_over_C"]
            assert answer["value"] == pytest.approx(numerator / denominator, rel=1e-12)
            assert np.allclose(answer["scaled_covariance"], projected, rtol=1e-12)
            # Fieller roots independently solve Var(N-rD) = (N-rD)^2 / z^2.
            z2 = 1.959963984540054**2
            roots = np.sort(np.roots([
                denominator**2 - z2 * projected[1, 1],
                -2 * numerator * denominator + 2 * z2 * projected[0, 1],
                numerator**2 - z2 * projected[0, 0],
            ]))
            interval = answer["conditional_gaussian_95_fieller_set"]
            assert interval["type"] == "bounded"
            assert np.allclose(interval["interval"], roots, rtol=1e-12, atol=1e-12)
    assert saved["ion_fraction_correction_available"] is False
    assert saved["scenarios_are_independent_likelihoods"] is False


def test_native_cue_uses_four_group_marginal_covariance_and_omits_niv():
    native, saved = read("mom_native_reduction.json"), read("mom_native_cue_grid_fit.json")
    assert saved["input_spectrum_sha256"] == NATIVE_SHA256
    assert saved["provenance"]["missing_observed_groups"] == ["NIV"]
    assert saved["all_five_measured_groups_fit"] is False
    assert saved["source_specific_model_validated"] is False
    for source, result in zip(native["scenarios"], saved["scenarios"]):
        assert result["resolution_family"] == source["name"]
        assert result["line_order"] == ["CIV", "HeII_OIII", "NIII", "CIII"]
        covariance = np.asarray(source["fit"]["flux_covariance"])[1:, 1:]
        flux = np.asarray(source["fit"]["fluxes"])[1:]
        assert np.array_equal(result["input_covariance"], covariance)
        assert np.array_equal(result["input_fluxes"], flux)
        for point in result["ranked_grid_points"]:
            residual = flux - point["predicted_four_group_fluxes"]
            chi2 = residual @ np.linalg.solve(covariance, residual)
            assert point["chi2_four_groups"] == pytest.approx(chi2, rel=1e-12, abs=1e-13)
        assert result["delta_set_is_calibrated_confidence_region"] is False
