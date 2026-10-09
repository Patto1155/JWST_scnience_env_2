"""Synthetic calibration controls; no observations or astrophysical discoveries."""
from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from tools.jwst.flux_calibration import ARCSEC2_TO_SR, ab_magnitude, pixel_solid_angle_sr
from tools.jwst.photometry import extract_photometry


def _wcs(scale: float = 0.1, size: int = 61) -> WCS:
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [53.0, -28.0]
    wcs.wcs.crpix = [size // 2 + 1] * 2
    wcs.wcs.cdelt = [-scale / 3600, scale / 3600]
    return wcs


def _bundle(unit="MJy/sr", area=1e-12):
    image = np.full((61, 61), 3.0)
    image[30, 30] += 10.0
    header = fits.Header({"BUNIT": unit}) if unit else fits.Header()
    if area is not None:
        header["PIXAR_SR"] = area
    return {"sci": image, "err": np.full_like(image, 0.2), "header": header}


def _measure(bundle, **kwargs):
    return extract_photometry(bundle, x=30, y=30, aperture_radius=2,
                              background_annulus_inner_radius=3, background_annulus_outer_radius=5, **kwargs)


@pytest.mark.parametrize("unit,factor", [("MJy/sr", 1e-6), ("Jy/sr", 1e-12),
                                           ("Jy", 1.0), ("uJy", 1e-6), ("nJy/pixel", 1e-9)])
def test_recognized_unit_conversions(unit, factor):
    result = _measure(_bundle(unit))
    assert result["background_subtracted_flux"] == pytest.approx(10.0)
    assert result["background_subtracted_flux_jy"] == pytest.approx(10 * factor)
    assert result["flux_jy"] == pytest.approx(result["flux"] * factor)
    assert result["flux_error_jy"] == pytest.approx(result["flux_error"] * factor)
    assert result["magnitude"] == pytest.approx(ab_magnitude(result["flux_jy"]))
    assert result["calibration_status"] == "calibrated"


@pytest.mark.parametrize("unit,area,status", [(None, 1e-12, "missing_bunit"),
    ("DN/s", 1e-12, "unsupported_bunit"), ("MJy/sr", None, "missing_pixel_area"),
    ("MJy/sr", -1e-12, "invalid_pixel_area")])
def test_missing_calibration_preserves_only_explicit_raw_values(unit, area, status):
    result = _measure(_bundle(unit, area))
    assert result["flux"] > 0
    assert result["background_subtracted_flux_jy"] is None
    assert result["magnitude"] is None
    assert result["calibration_status"] == status


def test_primary_header_metadata_fallback_and_arcsec_area():
    bundle = _bundle("MJy/sr", None)
    bundle["primary_header"] = fits.Header({"PIXAR_A2": 0.01})
    result = _measure(bundle)
    assert result["mean_pixel_area_sr"] == pytest.approx(0.01 * ARCSEC2_TO_SR)
    assert result["pixel_area_source"] == "header_PIXAR_A2"


def test_wcs_grid_area_overrides_stale_detector_metadata():
    bundle = _bundle()
    bundle["wcs"] = _wcs(0.1)
    result = _measure(bundle)
    assert result["mean_pixel_area_sr"] == pytest.approx(0.01 * ARCSEC2_TO_SR, rel=1e-7)
    assert result["pixel_area_source"] == "celestial_wcs_pixel_corners"
    assert result["background_subtracted_flux_jy"] == pytest.approx(10e6 * .01 * ARCSEC2_TO_SR, rel=1e-7)


def test_same_physical_flux_recovered_on_two_grids_with_same_sky_aperture():
    results = []
    for scale, size in [(0.1, 61), (0.05, 121)]:
        wcs = _wcs(scale, size)
        yy, xx = np.indices((size, size))
        area = pixel_solid_angle_sr(wcs, xx, yy)
        image = np.full((size, size), 3.)
        image[size // 2, size // 2] += 1e-6 / (1e6 * area[size // 2, size // 2])
        result = extract_photometry({"sci": image, "wcs": wcs, "header": {"BUNIT": "MJy/sr"}, "err": np.full_like(image, .1)},
            ra_deg=53, dec_deg=-28, aperture_radius_arcsec=.4,
            background_annulus_inner_radius_arcsec=.6, background_annulus_outer_radius_arcsec=1.)
        assert result["background_subtracted_flux_jy"] == pytest.approx(1e-6, rel=1e-7)
        assert result["coverage_fraction"] == 1
        results.append(result)
    assert results[0]["background_subtracted_magnitude"] == pytest.approx(results[1]["background_subtracted_magnitude"])
    assert results[1]["valid_pixel_count"] > results[0]["valid_pixel_count"]


def test_err_uncertainty_includes_background_estimator_not_double_counted():
    result = _measure(_bundle())
    n, m = result["valid_pixel_count"], result["annulus_pixel_count"]
    expected = .2 * np.sqrt(n + n ** 2 / m)
    assert result["flux_error"] == pytest.approx(expected)
    assert result["flux_error_jy"] == pytest.approx(expected * 1e-6)
    assert result["uncertainty_method"] == "err_diagonal_plus_background_mean"


def test_invalid_err_does_not_become_zero_precision():
    bundle = _bundle()
    bundle["err"][30, 30] = np.nan
    result = _measure(bundle)
    assert result["flux_error"] is None
    assert result["flux_error_jy"] is None
    assert result["snr"] is None
    assert result["uncertainty_method"] == "invalid_err"


def test_measured_zero_distinct_from_missing_or_off_image():
    bundle = _bundle()
    bundle["sci"][:] = 0
    measured = _measure(bundle)
    assert measured["measurement_status"] == "measured"
    assert measured["background_subtracted_flux_jy"] == 0
    assert measured["background_subtracted_magnitude"] is None
    missing = _measure(dict(bundle, validity_mask=np.zeros((61, 61), dtype=bool)))
    assert missing["measurement_status"] == "no_valid_pixels"
    assert missing["flux"] is None and missing["flux_jy"] is None
    outside = extract_photometry(bundle, x=-100, y=-100)
    assert outside["measurement_status"] == "off_image"
    assert outside["flux"] is None and outside["flux_error"] is None


def test_edge_coverage_counts_aperture_pixels_outside_image():
    result = extract_photometry(_bundle(), x=0, y=0, aperture_radius=2)
    assert result["measurement_status"] == "partial_coverage"
    assert 0 < result["coverage_fraction"] < .6


def test_missing_annulus_does_not_invent_background_or_snr():
    bundle = _bundle()
    validity = np.zeros((61, 61), dtype=bool)
    validity[29:32, 29:32] = True
    result = _measure(dict(bundle, validity_mask=validity))
    assert result["flux_jy"] is not None
    assert result["background_subtracted_flux_jy"] is None
    assert result["background_mean"] is None and result["snr"] is None


def test_fits_loader_header_wcs_and_err_survive_calibration(tmp_path):
    bundle = _bundle()
    header = _wcs().to_header()
    header["BUNIT"] = "MJy/sr"
    path = tmp_path / "synthetic_control.fits"
    fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(bundle["sci"], header=header, name="SCI"),
                  fits.ImageHDU(bundle["err"], name="ERR")]).writeto(path)
    result = _measure(str(path))
    assert result["calibration_status"] == "calibrated"
    assert result["pixel_area_source"] == "celestial_wcs_pixel_corners"
    assert result["flux_error_jy"] > 0


@pytest.mark.parametrize("kwargs", [{"aperture_radius": -1}, {"aperture_radius": 6},
    {"ra_deg": 53}, {"aperture_radius_arcsec": .4}])
def test_invalid_aperture_specifications_rejected(kwargs):
    with pytest.raises(ValueError):
        extract_photometry(_bundle(), **kwargs)


def test_flux_density_units_need_no_pixel_area():
    result = _measure(_bundle("uJy", None))
    assert result["calibration_status"] == "calibrated"
    assert result["mean_pixel_area_sr"] is None
    assert result["background_subtracted_flux_jy"] == pytest.approx(10e-6)


def test_annulus_empirical_uncertainty_explicitly_labelled():
    bundle = _bundle()
    bundle.pop("err")
    yy, xx = np.indices(bundle["sci"].shape)
    bundle["sci"] += np.where((xx + yy) % 2, .1, -.1)
    result = _measure(bundle)
    n, m = result["valid_pixel_count"], result["annulus_pixel_count"]
    assert result["flux_error"] == pytest.approx(result["background_std"] * np.sqrt(n + n ** 2 / m))
    assert result["uncertainty_method"] == "annulus_empirical_diagonal"


def test_constant_image_without_err_does_not_establish_zero_uncertainty():
    bundle = _bundle()
    bundle.pop("err")
    bundle["sci"][:] = 0
    result = _measure(bundle)
    assert result["background_subtracted_flux_jy"] == 0
    assert result["flux_error_jy"] is None
    assert result["snr"] is None
    assert result["uncertainty_method"] == "zero_noise_not_estimated"


def test_spherical_areas_safe_across_ra_zero_and_near_pole():
    wcs = _wcs(.03)
    wcs.wcs.crval = [0, 89.9]
    area = pixel_solid_angle_sr(wcs, np.array([29, 30, 31]), np.array([30, 30, 30]))
    np.testing.assert_allclose(area, .03 ** 2 * ARCSEC2_TO_SR, rtol=1e-6)


def test_cube_not_silently_averaged_into_2d_photometry():
    with pytest.raises(ValueError, match="2D"):
        extract_photometry(np.ones((2, 20, 20)))
