"""Independent algebraic controls for the ionic-to-yield comparison."""

import copy
import hashlib
import json

import numpy as np
import pytest
from scipy.optimize import nnls

from discovery.atomic_enrichment import (
    ATOMIC_MASS,
    SIGMA_95,
    check_ionic_measurement,
    profile_ionic_ratio_interval,
    retained_mixture,
    run_comparison,
    stage_requirements,
)
from discovery.enrichment_constraints import DEFAULT_INPUT, ROOT, background_nuclei_per_msun
from tools.jwst.line_sensitivity import fieller_set


def measurement(numerator=8.0, denominator=1.0, covariance=None):
    covariance = np.asarray([[1.0, 0.1], [0.1, 0.04]] if covariance is None else covariance)
    return {
        "value": numerator / denominator if denominator else None,
        "scaled_numerator": numerator,
        "scaled_denominator": denominator,
        "scaled_covariance": covariance.tolist(),
        "conditional_gaussian_95_fieller_set": fieller_set(
            numerator,
            denominator,
            covariance[0, 0],
            covariance[1, 1],
            covariance[0, 1],
            SIGMA_95**2,
        ),
    }


def test_profile_matches_independent_gaussian_ratio_residual_with_covariance():
    observed = measurement()
    x, covariance = check_ionic_measurement(observed)
    tested_ratio = 1.5
    fitted = profile_ionic_ratio_interval(x, covariance, tested_ratio, tested_ratio)
    # Eliminating the common normalization independently gives this expression.
    expected = (x[0] - tested_ratio * x[1]) ** 2 / (
        covariance[0, 0] - 2 * tested_ratio * covariance[0, 1] + tested_ratio**2 * covariance[1, 1]
    )
    assert fitted["normalization"] > 0
    assert fitted["conditional_profile_deviance"] == pytest.approx(expected)
    diagonal = profile_ionic_ratio_interval(
        x, np.diag(np.diag(covariance)), tested_ratio, tested_ratio
    )
    assert diagonal["chi2"] != pytest.approx(fitted["chi2"])


def test_convex_ratio_profile_attains_exact_positive_data_if_feasible():
    x, covariance = check_ionic_measurement(measurement())
    fit = profile_ionic_ratio_interval(x, covariance, 0.25, 9.0)
    assert fit["best_ionic_ratio_in_interval"] == 8.0
    assert fit["chi2"] == pytest.approx(0.0, abs=1e-12)
    assert fit["predicted_scaled_numerator_denominator"] == pytest.approx(x)
    constrained = profile_ionic_ratio_interval(x, covariance, 0.25, 2.0)
    assert constrained["best_ionic_ratio_in_interval"] == 2.0
    assert constrained["chi2"] > SIGMA_95**2


def test_profile_matches_independent_whitened_convex_cone_nnls():
    """Independent numerical optimizer covers positive, signed and correlated controls."""
    rng = np.random.default_rng(6302)
    for _ in range(50):
        transform = rng.normal(size=(2, 2))
        covariance = transform @ transform.T + np.eye(2) * 0.1
        observed = rng.normal(size=2) * 3
        lower, upper = sorted(np.exp(rng.normal(size=2)))
        fitted = profile_ionic_ratio_interval(observed, covariance, lower, upper)
        # Positive mixtures of the two boundary directions span the entire ratio cone.
        whitening = np.linalg.cholesky(np.linalg.inv(covariance)).T
        directions = np.array([[lower, upper], [1.0, 1.0]])
        _, residual_norm = nnls(whitening @ directions, whitening @ observed)
        assert fitted["chi2"] == pytest.approx(residual_norm**2, abs=1e-9)


def test_signed_data_are_not_independently_clipped_or_silently_positive():
    covariance = np.array([[2.0, 0.4], [0.4, 0.5]])
    x = np.array([-2.0, 1.0])
    fitted = profile_ionic_ratio_interval(x, covariance, 0.5, 3.0)
    assert fitted["positive_quadrant_minimum_chi2"] > 0
    assert fitted["chi2"] >= fitted["positive_quadrant_minimum_chi2"]
    assert fitted["predicted_scaled_numerator_denominator"][0] >= 0
    altered = profile_ionic_ratio_interval(np.maximum(x, 0), covariance, 0.5, 3.0)
    assert fitted["chi2"] != pytest.approx(altered["chi2"])
    negative = profile_ionic_ratio_interval(np.array([-2.0, -1.0]), np.eye(2), 0.5, 3.0)
    assert negative["normalization"] == 0
    assert negative["conditional_profile_deviance"] == 0


def test_signed_fieller_does_not_create_a_conditional_yield_exclusion():
    observed = measurement(0.5, 1.0, [[1.0, 0.0], [0.0, 0.1]])
    assert observed["conditional_gaussian_95_fieller_set"]["interval"][0] < 0
    requirements = stage_requirements(observed, 1.5)
    assert requirements["largest_k_reaching_positive_ionic_point"] == 3.0
    assert requirements["largest_k_with_overlap_at_conditional_95_lower_endpoint"] is None
    assert requirements["unbounded_or_signed_95_set"] is True


def test_cached_ratio_and_confidence_topology_are_verified():
    good = measurement()
    for key, replacement in [
        ("value", 999.0),
        ("scaled_covariance", [[1.0, 0.5], [0.1, 0.04]]),
        ("scaled_covariance", [[1.0, 0.0], [0.0, -1.0]]),
        ("conditional_gaussian_95_fieller_set", {"type": "all_real"}),
    ]:
        bad = copy.deepcopy(good)
        bad[key] = replacement
        with pytest.raises(ValueError):
            check_ionic_measurement(bad)


def test_retained_mixing_closes_nuclei_and_differential_retention_changes_ceiling():
    inputs = json.loads(DEFAULT_INPUT.read_text())
    row = inputs["sms_yields"]["rows"][0]
    background = background_nuclei_per_msun(inputs["solar_reference"], -1.38, -0.65, 0.0)
    background["he"] = 0.25 / 4
    uniform = dict.fromkeys(ATOMIC_MASS, 1.0)
    assert retained_mixture(row, background, 2.0, uniform)["status"] == (
        "retained_ejecta_cannot_reach_target"
    )
    selective = {**dict.fromkeys(ATOMIC_MASS, 0.3), "n": 0.9}
    result = retained_mixture(row, background, 2.0, selective)
    assert result["status"] == "reachable_conditionally"
    mass = result["ambient_mass_msun"]
    n = mass * background["n"] + 0.9 * row["n"] / 14
    c = mass * background["c"] + 0.3 * row["c"] / 12
    assert n / c == pytest.approx(2.0)
    assert result["elemental_N_over_C"] == pytest.approx(2.0)
    assert result["He_over_H"] == pytest.approx(
        (mass * 0.25 / 4 + 0.3 * row["he"] / 4) / (mass * 0.75 + 0.3 * row["h"])
    )
    scaled = retained_mixture(row, background, 2.0, {k: v * 0.1 for k, v in selective.items()})
    assert scaled["ambient_mass_msun"] == pytest.approx(mass * 0.1)
    for key in ("elemental_N_over_C", "log_C_over_O", "He_over_H"):
        assert scaled[key] == pytest.approx(result[key])


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_bad_ratio_interval_rejected(bad):
    with pytest.raises(ValueError):
        profile_ionic_ratio_interval(np.ones(2), np.eye(2), bad, 3.0)


@pytest.fixture
def synthetic_reports(tmp_path):
    """A small synthetic grid exercises receipt/family handling; not scientific data."""
    grid = tmp_path / "grid.json"
    grid.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "temperature_K": 20000,
                        "electron_density_cm3": 1000,
                        "emissivity_erg_cm3_s": dict.fromkeys(("NIV", "NIII", "CIV", "CIII"), 1.0),
                    }
                ]
            }
        )
    )
    spectrum = tmp_path / "spectrum.json"
    covariance_strong = np.diag([0.5, 0.02, 1.0, 0.5, 0.02])
    for n in (0, 3):
        for c in (1, 4):
            covariance_strong[n, c] = covariance_strong[c, n] = 0.025
    spectrum.write_text(
        json.dumps(
            {
                "scenarios": [
                    {
                        "name": "synthetic_strong",
                        "fit": {
                            "line_order": ["NIV", "CIV", "HeII_OIII", "NIII", "CIII"],
                            "fluxes": [6.0, 0.4, 0.0, 2.0, 0.6],
                            "flux_covariance": covariance_strong.tolist(),
                            "lines": {
                                name: {"flux": value}
                                for name, value in zip(
                                    ["NIV", "CIV", "HeII_OIII", "NIII", "CIII"],
                                    [6.0, 0.4, 0.0, 2.0, 0.6],
                                )
                            },
                        },
                    },
                    {
                        "name": "synthetic_weak",
                        "fit": {
                            "line_order": ["NIV", "CIV", "HeII_OIII", "NIII", "CIII"],
                            "fluxes": [0.25, 0.5, 0.0, 0.25, 0.5],
                            "flux_covariance": np.diag([0.5, 0.05, 1.0, 0.5, 0.05]).tolist(),
                        },
                    },
                ]
            }
        )
    )
    ionic = tmp_path / "ionic.json"
    record = {
        "temperature_K": 20000,
        "electron_density_cm3": 1000,
        "observed_two_stage_ionic_N_over_C": measurement(),
    }
    ionic.write_text(
        json.dumps(
            {
                "grid_sha256": hashlib.sha256(grid.read_bytes()).hexdigest(),
                "spectrum_sha256": hashlib.sha256(spectrum.read_bytes()).hexdigest(),
                "models": [
                    {"model_label": "synthetic_strong", "records": [record]},
                    {
                        "model_label": "synthetic_weak",
                        "records": [
                            {
                                **record,
                                "observed_two_stage_ionic_N_over_C": measurement(
                                    0.5, 1.0, [[1.0, 0.0], [0.0, 0.1]]
                                ),
                            }
                        ],
                    },
                ],
                "ion_fraction_correction_available": False,
                "scenarios_are_independent_likelihoods": False,
            }
        )
    )
    return ionic, grid, spectrum


def test_report_preserves_strong_and_weak_shared_data_families(synthetic_reports):
    report = run_comparison(*synthetic_reports)
    assert report["identified_mechanism_exclusions"] == []
    assert report["mechanism_probabilities"] is None
    assert report["ion_fraction_ratio_k_calibrated"] is False
    assert report["ionic_operator_lineage_independently_replayed"] is True
    first, second = report["spectrum_families"]
    assert first["summaries"][0]["atomic_cells_exceeding_conditional_95_reference_deviance"] == 1
    assert second["summaries"][0]["atomic_cells_exceeding_conditional_95_reference_deviance"] == 0
    assert (
        second["summaries"][0]["largest_k_with_overlap_at_conditional_95_lower_endpoint_range"]
        is None
    )
    assert len(first["reference_20000K_1000cm3_mixing"]["records"]) == 160
    assert report["formation_clocks"]["yield_clock_link_identified"] is False


def test_report_rejects_receipt_mismatch_empty_and_duplicate_atomic_cells(synthetic_reports):
    ionic, grid, spectrum = synthetic_reports
    original = json.loads(ionic.read_text())
    for mutate in (
        lambda x: x.update(grid_sha256="bad"),
        lambda x: x.update(scenarios_are_independent_likelihoods=True),
        lambda x: x.update(models=[]),
        lambda x: x["models"][0]["records"].append(x["models"][0]["records"][0]),
    ):
        changed = copy.deepcopy(original)
        mutate(changed)
        ionic.write_text(json.dumps(changed))
        with pytest.raises(ValueError):
            run_comparison(ionic, grid, spectrum)


def test_self_consistent_ionic_forgery_fails_independent_source_operator_replay(synthetic_reports):
    ionic, grid, spectrum = synthetic_reports
    original = json.loads(ionic.read_text())
    original["models"][0]["records"][0]["observed_two_stage_ionic_N_over_C"] = measurement(
        16.0, 1.0
    )
    ionic.write_text(json.dumps(original))
    with pytest.raises(ValueError, match="do not replay"):
        run_comparison(ionic, grid, spectrum)


def test_versioned_real_coadd_output_replays_without_download_cache():
    observed = run_comparison(
        ROOT / "research_output/mom_ionic_fit.json",
        ROOT / "research_output/mom_atomic_grid.json",
        ROOT / "research_output/mom_z14_point_resolution.json",
    )
    saved = json.loads((ROOT / "research_output/atomic_enrichment_coadd.json").read_text())
    assert_replay_close(observed, saved)


def assert_replay_close(observed, saved):
    """Keep exact receipt/schema/count identity; tolerate only negligible BLAS roundoff."""
    if isinstance(saved, dict):
        assert isinstance(observed, dict) and set(observed) == set(saved)
        for key in saved:
            assert_replay_close(observed[key], saved[key])
    elif isinstance(saved, list):
        assert isinstance(observed, list) and len(observed) == len(saved)
        for actual, expected in zip(observed, saved):
            assert_replay_close(actual, expected)
    elif isinstance(saved, float):
        assert observed == pytest.approx(saved, rel=1e-12, abs=1e-12)
    else:
        assert type(observed) is type(saved) and observed == saved


def test_replay_tolerance_keeps_receipts_structure_and_material_numerics_exact():
    saved = {"receipt": "abc123", "n": 28, "values": [3.90, 0.145]}
    negligible = copy.deepcopy(saved)
    negligible["values"][0] += 1e-15
    assert_replay_close(negligible, saved)
    for change in (
        lambda x: x.update(receipt="wrong"),
        lambda x: x.update(n=28.0),
        lambda x: x["values"].append(0.0),
        lambda x: x["values"].__setitem__(0, 3.90 + 1e-8),
    ):
        changed = copy.deepcopy(saved)
        change(changed)
        with pytest.raises(AssertionError):
            assert_replay_close(changed, saved)
