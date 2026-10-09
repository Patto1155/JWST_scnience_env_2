"""Synthetic integration controls, not astrophysical recovery/completeness tests.

Use real WCS, calibration, angular photometry, proposal and audit code. Only the
registry, precomputed detection catalog and visual rendering are isolated. A
single-pixel source is intentional: it fixes the known injected integrated flux
independently of grid scale and avoids sharing a PSF generator with production.
"""
from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from discovery import build_universe_table as pipeline
from discovery.audit_candidates import audit_candidate
from tools.jwst.dropout import dropout_upper_limit_ratio


def _bundle(name, scale, size, source_flux_jy, ra=53.1):
    header = fits.Header()
    header.update(NAXIS=2, NAXIS1=size, NAXIS2=size, CTYPE1="RA---TAN", CTYPE2="DEC--TAN",
                  CRPIX1=(size + 1) / 2, CRPIX2=(size + 1) / 2, CRVAL1=ra,
                  CRVAL2=-27.8, CDELT1=-scale / 3600, CDELT2=scale / 3600, BUNIT="MJy/sr")
    image = np.zeros((size, size))
    # Independently specified integrated flux: infinitesimal TAN pixels at CRVAL.
    nominal_solid_angle = (scale * np.pi / (180 * 3600)) ** 2
    image[size // 2, size // 2] = source_flux_jy / (1e6 * nominal_solid_angle)
    return {"dataset_name": name, "sci": image, "header": header, "wcs": WCS(header),
            "err": np.full(image.shape, 1e-4), "validity_mask": np.ones(image.shape, dtype=bool)}


def _run_pipeline(monkeypatch, tmp_path, blue_flux_jy, blue_ra=53.1):
    names = {"F444W": "jw_visit1_nrcalong_i2d", "F090W": "jw_visit2_nrcb1_i2d",
             "F200W": "jw_visit1_nrca1_i2d"}
    bundles = {names["F444W"]: _bundle(names["F444W"], .06, 65, 1e-7),
               names["F090W"]: _bundle(names["F090W"], .03, 129, blue_flux_jy, ra=blue_ra),
               names["F200W"]: _bundle(names["F200W"], .03, 129, 5e-8)}
    catalog = [{"source_id": 1, "x": 32., "y": 32., "ra": 53.1, "dec": -27.8,
                "edge_distance_px": 32.}]
    monkeypatch.setattr(pipeline, "load_fits_bundle", lambda name: bundles[name])
    monkeypatch.setattr(pipeline, "detect_sources", lambda **kwargs: {
        "catalog_path": "synthetic", "source_count": 1, "segmentation_overlay_path": "synthetic"})
    monkeypatch.setattr(pipeline, "_load_catalog_sources", lambda path: catalog)
    monkeypatch.setattr(pipeline, "candidate_evidence_bundle", lambda **kwargs: {
        "artifacts": [], "output_path": "synthetic", "sidecar_path": "synthetic"})
    monkeypatch.setattr(pipeline, "render_field_overview", lambda **kwargs: {"output_path": "synthetic"})
    monkeypatch.setattr(pipeline, "save_color_diagnostic_plot", lambda **kwargs: "synthetic")
    monkeypatch.setattr(pipeline, "VISUALS_DIR", tmp_path)
    captured = []
    real_attach = pipeline.attach_proposal_metadata
    def capture_proposal(candidate, **kwargs):
        captured.append(candidate)  # same dict receives validation after attachment
        return real_attach(candidate, **kwargs)
    monkeypatch.setattr(pipeline, "attach_proposal_metadata", capture_proposal)
    grouped = {f: [{"name": name}] for f, name in names.items()}
    result = pipeline._analyze_target_sources("synthetic_control", grouped, anomalous_dataset_names=set())
    return (*result, captured)


def test_real_api_dropout_on_different_grids_and_modules_survives(monkeypatch, tmp_path):
    candidates, _, summary, _ = _run_pipeline(monkeypatch, tmp_path, 0.)
    assert summary["source_count"] == 1
    assert len(candidates) == 1
    candidate = candidates[0]
    assert "dropout_strict" in candidate["proposal_channels"]
    assert candidate["validation_status"] in {"keep", "strong_keep"}
    red = candidate["photometry_by_filter"]["F444W"]["3"]
    blue = candidate["photometry_by_filter"]["F090W"]["3"]
    assert red["background_subtracted_flux_jy"] == pytest.approx(1e-7, rel=1e-6)
    assert red["aperture_radius_arcsec"] == pytest.approx(blue["aperture_radius_arcsec"])
    assert blue["pixels_in_aperture"] > 3 * red["pixels_in_aperture"]
    assert audit_candidate(candidate)["audit_verdict"] == "survives"
    assert audit_candidate(candidate)["module_mismatch"] is True


def test_equal_physical_blue_red_is_never_a_kept_dropout(monkeypatch, tmp_path):
    candidates, _, summary, captured = _run_pipeline(monkeypatch, tmp_path, 1e-7)
    # Broader exploratory proposal channels may retain the ordinary source.
    assert summary["source_count"] == 1
    assert len(captured) == 1
    for candidate in captured:
        assert not {"dropout_strict", "dropout_loose"}.intersection(candidate["proposal_channels"])
        assert candidate["validation_status"] not in {"keep", "strong_keep"}
        red = candidate["photometry_by_filter"]["F444W"]["3"]
        blue = candidate["photometry_by_filter"]["F090W"]["3"]
        assert red["background_subtracted_flux_jy"] == pytest.approx(blue["background_subtracted_flux_jy"], rel=1e-6)
        assert audit_candidate(candidate)["audit_verdict"] == "falsified"


def test_nonoverlapping_blue_pointing_produces_no_dropout(monkeypatch, tmp_path):
    candidates, _, _, _ = _run_pipeline(monkeypatch, tmp_path, 0., blue_ra=54.)
    assert candidates == []


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -1., 1.01, "bad", None])
def test_dropout_upper_limit_requires_valid_coverage(invalid):
    def measurement(flux):
        return {"calibration_status": "calibrated", "measurement_status": "measured",
                "background_status": "measured", "coverage_fraction": 1.,
                "aperture_radius_arcsec": .2, "background_subtracted_flux_jy": flux,
                "flux_error_jy": 1e-9}
    blue, red = measurement(0.), measurement(1e-7)
    blue["coverage_fraction"] = invalid
    assert dropout_upper_limit_ratio(blue, red) is None
