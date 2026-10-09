"""Conditional continuum and catalog association controls."""

from __future__ import annotations

import pytest

from discovery.survivor_continuum import continuum_slope, reference_matches


def _measurement(flux):
    return {
        "background_subtracted_flux_jy": flux,
        "flux_error_jy": 1e-8,
        "calibration_status": "calibrated",
        "measurement_status": "measured",
        "background_status": "measured",
        "coverage_fraction": 1.0,
    }


def test_powerlaw_diagnostic_recovers_frequency_slope():
    flux = 1e-6
    report = continuum_slope(
        _measurement(flux),
        _measurement(flux * (3.56 / 2.77) ** 2),
        _measurement(flux * (4.44 / 2.77) ** 2),
    )
    assert report["alpha_fnu_frequency"] == pytest.approx(-2)
    assert report["observed_minus_predicted_fraction"] == pytest.approx(0)
    assert report["alpha_diagonal_error"] > 0


@pytest.mark.parametrize("flux", [-1e-6, 0, None, float("nan")])
def test_no_logarithmic_continuum_from_unmeasured_or_nonpositive_flux(flux):
    report = continuum_slope(_measurement(flux), _measurement(1e-6), _measurement(1e-6))
    assert report["alpha_fnu_frequency"] is None


def test_partial_or_uncalibrated_aperture_is_not_a_continuum_measurement():
    first = _measurement(1e-6)
    first["measurement_status"] = "partial_coverage"
    report = continuum_slope(first, _measurement(1e-6), _measurement(1e-6))
    assert report["alpha_fnu_frequency"] is None


def test_catalog_nearest_neighbour_is_not_an_association():
    references = [
        {
            "RA_TARG": "1",
            "Dec_TARG": "0",
            "Unique_ID": "distant",
            "z_Spec": "3.1",
            "z_Spec_flag": "A",
            "NIRCam_DR5_ID": "45",
        }
    ]
    report = reference_matches(0, 0, references)
    assert report["nearest_observation"]["separation_arcsec"] == pytest.approx(3600)
    assert report["association_status_0p5arcsec"] == "unmatched"
    assert report["within_0p3arcsec"] == []


def test_catalog_match_wraps_ra_and_retains_multiple_observations():
    references = [
        {
            "RA_TARG": "359.99995",
            "Dec_TARG": "0",
            "Unique_ID": str(index),
            "z_Spec": "3.1",
            "z_Spec_flag": "A",
            "NIRCam_DR5_ID": "45",
        }
        for index in range(2)
    ]
    report = reference_matches(0, 0, references)
    assert len(report["within_0p3arcsec"]) == 2
    assert report["association_status_0p5arcsec"].startswith("multiple_observations")
