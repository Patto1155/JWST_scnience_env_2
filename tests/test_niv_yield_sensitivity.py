"""Contract controls and independent numerical profiles for the bounded v2 bridge."""

import copy
import json

import numpy as np
import pytest
from scipy.optimize import nnls
from test_atomic_enrichment import assert_replay_close

from discovery.atomic_enrichment import SIGMA_95
from discovery.enrichment_constraints import DEFAULT_INPUT, ROOT
from discovery.niv_yield_sensitivity import (
    K_VALUES,
    conditional_profile,
    project_cell,
    run,
    validate_pair,
    yield_hypotheses,
)
from tools.jwst.line_sensitivity import fieller_set

PATHS = {
    "v1_report": ROOT / "research_output/mom_native_multiplet_refit.json",
    "v1_grid": ROOT / "research_output/mom_atomic_grid.json",
    "v2_report": ROOT / "research_output/mom_native_niv_doublet_refit_v2.json",
    "v2_grid": ROOT / "research_output/mom_atomic_grid_niv_doublet_v2.json",
    "v2_components": ROOT / "research_output/mom_multiplet_components_niv_doublet_v2.json",
}


@pytest.fixture
def frozen_reports():
    return {name: json.loads(path.read_text()) for name, path in PATHS.items()}


def test_frozen_yield_report_replays_with_tight_numeric_and_exact_structure_checks():
    result = run(**PATHS)
    expected = json.loads((ROOT / "research_output/niv_yield_sensitivity.json").read_text())
    assert_replay_close(result, expected)
    assert len(result["families"]) == 4
    assert sum(family["matched_cells"] for family in result["families"]) == 112
    assert result["old_fluxes_or_covariances_rescaled"] is False
    assert result["identified_mechanism_exclusions"] == []
    assert result["elemental_abundance_identified"] is False
    assert result["mechanism_probabilities"] is None


def test_all_real_versioned_cones_match_independent_whitened_scipy_nnls(frozen_reports):
    """No cached profiles feed the oracle; both contracts use their own fresh covariance."""
    hypotheses = yield_hypotheses(json.loads(DEFAULT_INPUT.read_text()))
    for version in (1, 2):
        grid = {
            (cell["temperature_K"], cell["electron_density_cm3"]): cell
            for cell in frozen_reports[f"v{version}_grid"]["records"]
        }
        for family in frozen_reports[f"v{version}_report"]["scenarios"]:
            for cell in family["records"]:
                key = cell["temperature_K"], cell["electron_density_cm3"]
                x, covariance = project_cell(cell, grid[key]["emissivity_erg_cm3_s"], version)
                # Directly whiten and solve nonnegative coefficients on cone endpoints.
                whitening = np.linalg.cholesky(np.linalg.inv(covariance)).T
                _, positive_norm = nnls(whitening, whitening @ x)
                for hypothesis in hypotheses:
                    for k in K_VALUES:
                        lower, upper = [v / k for v in hypothesis["elemental_ratio_interval"]]
                        if lower == upper:
                            rays = np.array([[lower], [1.0]])
                        else:
                            rays = np.array([[lower, upper], [1.0, 1.0]])
                        _, norm = nnls(whitening @ rays, whitening @ x)
                        fit = conditional_profile(
                            x, covariance, hypothesis["elemental_ratio_interval"], k
                        )
                        assert fit["chi2"] == pytest.approx(norm**2, rel=1e-11, abs=1e-11)
                        assert fit["positive_quadrant_minimum_chi2"] == pytest.approx(
                            positive_norm**2, abs=1e-11
                        )
                        assert fit["conditional_profile_deviance"] == pytest.approx(
                            max(0.0, norm**2 - positive_norm**2), rel=1e-11, abs=1e-11
                        )


@pytest.mark.parametrize(
    "target,key,value",
    [
        ("v2_report", "line_contract_version", 1),
        ("v2_report", "v1_1486_only_report_relabelled", True),
        ("v2_report", "line_flux_covariance_refit_for_each_template", False),
        ("v2_report", "ion_fraction_correction_available", True),
        ("v2_report", "scenarios_are_independent_likelihoods", True),
        ("v1_report", "NIV_1483_included", True),
        ("v2_grid", "NIV_1483_included", False),
    ],
)
def test_wrong_contract_or_calibration_claims_rejected(frozen_reports, target, key, value):
    frozen_reports[target][key] = value
    with pytest.raises(ValueError):
        validate_pair(frozen_reports)


def test_missing_duplicate_or_unmatched_cells_rejected(frozen_reports):
    malformed = copy.deepcopy(frozen_reports)
    malformed["v2_report"]["scenarios"][0]["records"][1] = copy.deepcopy(
        malformed["v2_report"]["scenarios"][0]["records"][0]
    )
    with pytest.raises(ValueError, match="unique"):
        validate_pair(malformed)
    frozen_reports["v2_grid"]["records"].pop()
    with pytest.raises(ValueError, match="unique"):
        validate_pair(frozen_reports)


def test_doublet_atomic_weight_closure_rejected_if_changed(frozen_reports):
    frozen_reports["v2_components"]["records"][0]["components"][0]["normalized_weights"] = [1, 0]
    with pytest.raises(ValueError, match="must close"):
        validate_pair(frozen_reports)


def test_v2_cannot_use_v1_emissivity_or_borrow_another_cells_fit(frozen_reports):
    cells = frozen_reports["v2_report"]["scenarios"][3]["records"]
    old_e = frozen_reports["v1_grid"]["records"][0]["emissivity_erg_cm3_s"]
    new_e = frozen_reports["v2_grid"]["records"][0]["emissivity_erg_cm3_s"]
    project_cell(cells[0], new_e, 2)
    with pytest.raises(ValueError, match="do not replay"):
        project_cell(cells[0], old_e, 2)
    changed = copy.deepcopy(cells[0])
    changed["fit"] = copy.deepcopy(cells[1]["fit"])
    with pytest.raises(ValueError, match="do not replay"):
        project_cell(changed, new_e, 2)
    changed["fit"].pop("NIV_flux_definition")
    with pytest.raises(ValueError, match="flux definition"):
        project_cell(changed, new_e, 2)


def test_self_consistent_cached_ionic_forgery_fails_source_operator_replay(frozen_reports):
    """Changing all downstream summaries cannot hide a mismatch to the own source fit."""
    cell = copy.deepcopy(frozen_reports["v2_report"]["scenarios"][0]["records"][0])
    ionic = cell["observed_two_stage_ionic_N_over_C"]
    ionic["scaled_numerator"] *= 2
    numerator, denominator = ionic["scaled_numerator"], ionic["scaled_denominator"]
    covariance = np.asarray(ionic["scaled_covariance"])
    ionic["value"] = numerator / denominator
    ionic["conditional_gaussian_95_fieller_set"] = fieller_set(
        numerator, denominator, covariance[0, 0], covariance[1, 1], covariance[0, 1], SIGMA_95**2
    )
    with pytest.raises(ValueError, match="do not replay"):
        project_cell(cell, frozen_reports["v2_grid"]["records"][0]["emissivity_erg_cm3_s"], 2)


def test_signed_fieller_endpoints_and_changed_rejections_remain_explicit():
    result = run(**PATHS)
    point = result["families"][3]
    assert all(cell["signed_95_fieller_v1_v2"][1]["interval"][0] < 0 for cell in point["cells"])
    reference = point["reference_20000K_1000cm3"]
    assert reference["ionic_ratio_v1_v2"] == pytest.approx([6.450934931443722, 2.7503773904965803])
    # These are deterministic conditional counts, not independent samples or mechanism exclusions.
    for summary in point["summaries_by_k"]:
        assert all(model["v2_cells_above_reference"] == 0 for model in summary["models"])
    formal = result["families"][1]["summaries_by_k"][1]["models"][0]
    assert formal["v1_cells_above_reference"] == 28
    assert formal["v2_cells_above_reference"] == 2
    assert (
        result["counts_status"] == "deterministic_matched_grid_counts_not_probabilities_or_trials"
    )


def test_frozen_file_pin_rejects_altered_result_even_with_unchanged_lineage(tmp_path):
    changed = tmp_path / "changed.json"
    data = json.loads(PATHS["v2_report"].read_text())
    data["interpretation"] += " modified"
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="frozen experiment"):
        run(**{**PATHS, "v2_report": changed})


@pytest.mark.parametrize("k", [0, -1, float("inf"), float("nan")])
def test_invalid_k_cannot_be_used_as_a_physical_stage_fraction_ratio(k):
    with pytest.raises(ValueError):
        conditional_profile(np.ones(2), np.eye(2), [0.25, 2.0], k)
