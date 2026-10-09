"""Independent synthetic photometric controls; no real-galaxy discovery claims."""
from copy import deepcopy

import pytest

from discovery.audit_candidates import audit_candidate, summarize


def _candidate(blue_flux=0, blue_error=1e-9, red_flux=1e-7):
    def measurement(flux, error):
        return {"background_subtracted_flux_jy": flux, "flux_error_jy": error,
                "calibration_status": "calibrated", "measurement_status": "measured",
                "background_status": "measured", "coverage_fraction": 1,
                "aperture_radius_arcsec": 0.2}
    return {"photometry_by_filter": {
        "F090W": {"3": measurement(blue_flux, blue_error)},
        "F200W": {"3": measurement(5e-8, 5e-9)},
        "F444W": {"3": measurement(red_flux, 5e-9)},
    }}


def test_faint_equal_blue_red_flux_is_not_a_dropout():
    result = audit_candidate(_candidate(blue_flux=1e-7))
    assert result["audit_verdict"] == "falsified"
    assert "blue_band_detected_above_snr_2" in result["audit_blockers"]
    assert "blue_2sigma_limit_not_dropout_like" in result["audit_blockers"]


def test_synthetic_covered_dropout_survives_selection_only():
    result = audit_candidate(_candidate())
    assert result["audit_verdict"] == "survives"
    assert result["physical_blue_over_red_ratio"] == pytest.approx(0.02)


def test_low_blue_significance_is_insufficient_when_limit_is_shallow():
    result = audit_candidate(_candidate(blue_error=1e-8))
    assert result["audit_verdict"] == "falsified"
    assert result["blue_snr"] == 0
    assert result["physical_blue_over_red_ratio"] == pytest.approx(0.2)


def test_off_detector_zero_is_untestable_not_a_falsified_object():
    candidate = _candidate()
    candidate["photometry_by_filter"]["F090W"]["3"]["coverage_fraction"] = 0
    result = audit_candidate(candidate)
    assert result["audit_verdict"] == "untestable"
    assert result["physical_blue_over_red_ratio"] is None


@pytest.mark.parametrize("bad_error", [None, 0, -1, float("nan"), float("inf"), "bad"])
def test_invalid_blue_uncertainty_cannot_manufacture_an_upper_limit(bad_error):
    candidate = _candidate()
    candidate["photometry_by_filter"]["F090W"]["3"]["flux_error_jy"] = bad_error
    result = audit_candidate(candidate)
    assert result["audit_verdict"] == "untestable"
    assert result["blue_2sigma_limit_jy"] is None


@pytest.mark.parametrize("filter_name", ["F090W", "F200W", "F444W"])
def test_missing_physical_calibration_is_untestable(filter_name):
    candidate = _candidate()
    candidate["photometry_by_filter"][filter_name]["3"].pop("calibration_status")
    assert audit_candidate(candidate)["audit_verdict"] == "untestable"


def test_apertures_must_match_on_the_sky():
    candidate = _candidate()
    candidate["photometry_by_filter"]["F090W"]["3"]["aperture_radius_arcsec"] = 0.093
    assert audit_candidate(candidate)["audit_verdict"] == "untestable"


def test_very_bright_lensed_source_is_warning_not_hard_veto():
    result = audit_candidate(_candidate(red_flux=1e-4))
    assert result["audit_verdict"] == "survives"
    assert "bright_source_requires_lensing_and_contaminant_assessment" in result["audit_warnings"]


def test_different_module_names_cannot_override_measured_coverage():
    candidate = _candidate()
    candidate.update(f444_dataset="jw_visit1_nrcalong_i2d", f090_dataset="jw_visit2_nrcb1_i2d")
    result = audit_candidate(candidate)
    assert result["audit_verdict"] == "survives"
    assert result["module_mismatch"] is True


def test_legacy_nominal_detector_conversion_cannot_pass_physical_audit():
    candidate = _candidate()
    for filter_name in candidate["photometry_by_filter"]:
        measurement = candidate["photometry_by_filter"][filter_name]["3"]
        measurement.pop("background_subtracted_flux_jy")
        measurement["background_subtracted_flux"] = 10
    result = audit_candidate(candidate)
    assert result["audit_verdict"] == "untestable"
    assert result["legacy_nominal_reference_flux_jy"] > 0
    assert result["reference_flux_jy"] is None


def test_measured_blue_failure_does_not_claim_redshift_or_artifact_identity():
    results = [audit_candidate(_candidate()), audit_candidate(_candidate(blue_flux=1e-7))]
    missing = deepcopy(_candidate())
    missing["photometry_by_filter"].pop("F090W")
    results.append(audit_candidate(missing))
    summary = summarize(results)
    assert (summary["survivors"], summary["falsified"], summary["untestable"]) == (1, 1, 1)
