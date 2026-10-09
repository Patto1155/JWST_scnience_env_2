"""Trust-boundary and conditional selection controls, not astrophysical simulations."""

from __future__ import annotations

import copy

import pytest

from discovery.audit_candidates import audit_candidate
from discovery.photometry_sensitivity import _matching_geometry, noise_inputs, rescale_measurements


def _source() -> dict:
    measurements = {}
    for band, flux, error in (("F090W", 0.0, 0.01), ("F200W", 0.2, 0.01), ("F444W", 1.0, 0.1)):
        measurements[band] = {
            "3": {
                "background_subtracted_flux_jy": flux,
                "flux_error_jy": error,
                "coverage_fraction": 1.0,
                "calibration_status": "calibrated",
                "measurement_status": "measured",
                "background_status": "measured",
                "aperture_radius_arcsec": 0.188,
            }
        }
    return {"source_id": 7, "target": "synthetic_control", "photometry_by_filter": measurements}


def test_noise_inflation_changes_only_conditional_uncertainty():
    source = _source()
    changed = rescale_measurements([source], {"F090W": 3, "F200W": 2, "F444W": 1.1})[0]
    assert audit_candidate(source)["audit_verdict"] == "survives"
    assert audit_candidate(changed)["audit_verdict"] == "falsified"
    assert changed["photometry_by_filter"]["F090W"]["3"]["background_subtracted_flux_jy"] == 0.0
    assert source["photometry_by_filter"]["F090W"]["3"]["flux_error_jy"] == 0.01


def test_point_model_preserves_band_snr_and_keeps_missing_flux_missing():
    source = _source()
    factors = {(7, band): value for band, value in (("F090W", 1.2), ("F200W", 1.3), ("F444W", 1.5))}
    changed = rescale_measurements([source], {"F090W": 1, "F200W": 1, "F444W": 1}, factors)[0]
    assert audit_candidate(changed)["reference_snr"] == pytest.approx(10)
    off = copy.deepcopy(source)
    off["photometry_by_filter"]["F090W"]["3"].update(
        background_subtracted_flux_jy=None,
        flux_error_jy=None,
        measurement_status="off_image",
        coverage_fraction=0.0,
    )
    altered = rescale_measurements([off], {"F090W": 2, "F200W": 2, "F444W": 2})[0]
    assert altered["photometry_by_filter"]["F090W"]["3"]["background_subtracted_flux_jy"] is None
    assert audit_candidate(altered)["audit_verdict"] == "untestable"


def test_point_model_needs_every_testable_band():
    with pytest.raises(ValueError, match="lacks a native"):
        rescale_measurements([_source()], {"F090W": 1, "F200W": 1, "F444W": 1}, {})


def _metadata() -> dict:
    return {
        "aperture_radius_arcsec_by_filter": {band: 0.188 for band in ("F090W", "F200W", "F444W")},
        "annulus_radii_arcsec": {"inner": 0.377, "outer": 0.629},
    }


def test_aperture_or_annulus_mismatch_cannot_transfer_factors():
    with pytest.raises(ValueError, match="aperture"):
        _matching_geometry(0.2, [0.377, 0.629], _metadata())
    with pytest.raises(ValueError, match="annulus"):
        _matching_geometry(0.188, [0.377, 0.8], _metadata())


def test_mismatched_image_bytes_are_rejected():
    report = {"real_images": [{"sha256": "unmatched"}]}
    receipts = [{"sha256": "correct", "filter": "F090W"}]
    with pytest.raises(ValueError, match="image hash"):
        noise_inputs(report, _metadata(), receipts)


def test_invalid_factor_does_not_make_observed_zero_a_detection():
    with pytest.raises(ValueError, match="finite and positive"):
        rescale_measurements([_source()], {"F090W": 0, "F200W": 1, "F444W": 1})
