"""Counterexamples to confusing a recent rate or a half-mass time with all-star age."""

import json

import pytest

from discovery.continuation_physical_review import formation_audit


def controlled_history(tmp_path):
    directory = tmp_path / "research_output"
    directory.mkdir()
    path = directory / "formation_predictions.json"
    report = {
        "model_dependent_observational_input": {"quoted_log_stellar_mass_msun": {"median": 2}},
        "history_predictions": [
            {
                "duration_myr": 10.0,
                "rising_efold_myr": None,
                "time_duty_fraction": 0.5,
                "required_current_active_sfr_msun_per_year": 2e-5,
                "effective_returned_fraction": 0.0,
                "surviving_stellar_mass_assumed_msun": 100,
                "formed_stellar_mass_msun": 100,
                "sfr_last_5_myr_msun_per_year": 1e-5,
                "sfr_last_50_myr_msun_per_year": 2e-6,
                "halfmass_lookback_myr": 5.0,
            }
        ],
        "closed_parcel_baryon_budgets": [],
        "inverse_history_tests": [],
    }
    return path, report


def test_trailing50_mean_includes_preonset_zero_time(tmp_path):
    path, report = controlled_history(tmp_path)
    path.write_text(json.dumps(report))
    assert formation_audit(tmp_path)["independently_integrated_histories"] == 1
    report["history_predictions"][0]["sfr_last_50_myr_msun_per_year"] = 1e-5
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="trailing mean"):
        formation_audit(tmp_path)


def test_last_bright_phase_does_not_become_halfmass_time(tmp_path):
    path, report = controlled_history(tmp_path)
    report["history_predictions"][0]["halfmass_lookback_myr"] = 2.0
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="half-mass"):
        formation_audit(tmp_path)
