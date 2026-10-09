"""Synthetic end-to-end evidence controls, independent of local science files."""
from __future__ import annotations

import json
import os

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from core_api.startup import get_tool_definitions
from tools.jwst.fits_loader import load_fits_bundle
from tools.jwst.flux_calibration import pixel_solid_angle_sr
from tools.jwst.visualization import candidate_evidence_bundle


def _image(tmp_path, name, flux_jy, scale=.1, size=61, unit="MJy/sr", sky=True, offset=0):
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [53 + offset, -28]
    wcs.wcs.crpix = [size // 2 + 1] * 2
    wcs.wcs.cdelt = [-scale / 3600, scale / 3600]
    header = wcs.to_header() if sky else fits.Header()
    if unit:
        header["BUNIT"] = unit
    header["FILTER"] = name
    header["PIXAR_SR"] = float(pixel_solid_angle_sr(wcs, np.array(size // 2), np.array(size // 2)))
    data = np.full((size, size), 3.)
    data[size // 2, size // 2] += flux_jy / (1e6 * header["PIXAR_SR"])
    path = tmp_path / f"{name}.fits"
    fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(data, header=header, name="SCI"),
                  fits.ImageHDU(np.full_like(data, .1), name="ERR")]).writeto(path)
    return str(path)


def _evidence(tmp_path, reference, blue, **kwargs):
    options = dict(x=30, y=30, cutout_size=24, aperture_radii=[3],
                   output_dir=str(tmp_path / "panels"), output_prefix="control")
    options.update(kwargs)
    return candidate_evidence_bundle(reference, [blue], **options)


def test_evidence_colors_use_jy_and_common_sky_apertures_across_grids(tmp_path):
    red = _image(tmp_path, "F444W", 1e-6)
    blue = _image(tmp_path, "F090W", 1e-7, scale=.05, size=121)
    result = _evidence(tmp_path, red, blue)
    assert result["ratio_f090_f444"] == pytest.approx(.1, rel=1e-6)
    assert result["color_indices"]["F090W_F444W"]["color_index"] == pytest.approx(2.5, abs=1e-6)
    assert result["color_flux_unit"] == "Jy"
    assert result["aperture_matching"] == "same_sky_angular"
    r, b = result["photometry"][red]["3"], result["photometry"][blue]["3"]
    assert b["aperture_radius_arcsec"] == r["aperture_radius_arcsec"]
    assert b["valid_pixel_count"] > r["valid_pixel_count"]
    assert result["cache_hit"] is False
    assert _evidence(tmp_path, red, blue)["cache_hit"] is True


@pytest.mark.parametrize("blue_options", [{"offset": .1}, {"unit": None}, {"sky": False}])
def test_unobserved_uncalibrated_or_unregistered_band_has_no_physical_colour(tmp_path, blue_options):
    red = _image(tmp_path, "F444W", 1e-6)
    blue = _image(tmp_path, "F090W", 1e-7, **blue_options)
    result = _evidence(tmp_path, red, blue)
    assert result["ratio_f090_f444"] is None
    assert result["color_indices"] == {}
    assert result["color_status"] == "unavailable_or_nonpositive_fluxes"
    sidecar = json.loads(open(result["sidecar_path"]).read())
    if "offset" in blue_options:
        assert result["photometry"][blue]["3"]["background_subtracted_flux_jy"] is None
        assert result["photometry"][blue]["3"]["measurement_status"] == "off_image"
    if "sky" in blue_options:
        assert sidecar["datasets"][1]["astrometry_status"] == "pixel_only"


def test_unmeasured_reference_renders_without_numeric_none_coercion(tmp_path):
    red = _image(tmp_path, "F444W", 1e-6)
    blue = _image(tmp_path, "F090W", 1e-7)
    result = _evidence(tmp_path, red, blue, x=-100, y=-100)
    assert "unmeasured_reference" in result["quality_flags"]
    assert "nonpositive_reference_flux" not in result["quality_flags"]
    assert result["ratio_f090_f444"] is None
    assert result["photometry"][red]["3"]["flux"] is None


def test_legacy_cache_and_changed_center_do_not_return_old_science(tmp_path):
    red = _image(tmp_path, "F444W", 1e-6)
    blue = _image(tmp_path, "F090W", 1e-7)
    result = _evidence(tmp_path, red, blue)
    path = result["sidecar_path"]
    legacy = json.loads(open(path).read())
    legacy.pop("evidence_schema_version")
    legacy["ratio_f090_f444"] = 999
    open(path, "w").write(json.dumps(legacy))
    regenerated = _evidence(tmp_path, red, blue)
    assert regenerated["cache_hit"] is False
    assert regenerated["ratio_f090_f444"] == pytest.approx(.1, rel=1e-6)
    moved = _evidence(tmp_path, red, blue, x=40, y=40)
    assert moved["cache_hit"] is False
    assert moved["ratio_f090_f444"] is None


def test_modified_fits_reloads_data_and_invalidates_sidecar(tmp_path):
    red = _image(tmp_path, "F444W", 1e-6)
    blue = _image(tmp_path, "F090W", 1e-7)
    first = _evidence(tmp_path, red, blue)
    previous = os.stat(blue)
    with fits.open(blue, mode="update") as hdus:
        value = hdus["SCI"].data[30, 30]
        hdus["SCI"].data[30, 30] = 3 + 2 * (value - 3)
    os.utime(blue, ns=(previous.st_atime_ns, previous.st_mtime_ns + 10_000_000))
    assert load_fits_bundle(blue)["sci"][30, 30] == pytest.approx(3 + 2 * (value - 3))
    second = _evidence(tmp_path, red, blue)
    assert second["cache_hit"] is False
    assert first["ratio_f090_f444"] == pytest.approx(.1, rel=1e-6)
    assert second["ratio_f090_f444"] == pytest.approx(.2, rel=1e-6)


def test_api_contract_exposes_physical_fields_and_nullable_raw_measurements():
    definitions = {tool.name: tool for tool in get_tool_definitions()}
    photometry = definitions["extract_photometry"]
    for name in ["ra_deg", "dec_deg", "aperture_radius_arcsec", "background_annulus_inner_radius_arcsec", "background_annulus_outer_radius_arcsec"]:
        assert name in photometry.input_schema["properties"]
    for name in ["flux", "flux_error", "background_mean", "flux_jy", "background_subtracted_flux_jy", "flux_error_jy"]:
        assert "null" in photometry.output_schema["properties"][name]["type"]
    for name in ["calibration_status", "measurement_status", "uncertainty_method", "pixel_area_source"]:
        assert name in photometry.output_schema["properties"]
    evidence = definitions["candidate_evidence_bundle"]
    assert "aperture_radius_arcsec" in evidence.input_schema["properties"]
    assert "color_indices" in evidence.output_schema["properties"]


def test_explicit_angular_override_scales_all_reference_radius_keys(tmp_path):
    red = _image(tmp_path, "F444W", 1e-6)
    blue = _image(tmp_path, "F090W", 1e-7, scale=.05, size=121)
    result = _evidence(tmp_path, red, blue, aperture_radii=[2, 3, 5], aperture_radius_arcsec=.4)
    assert result["photometry"][red]["3"]["aperture_radius_arcsec"] == .4
    assert result["photometry"][blue]["5"]["aperture_radius_arcsec"] == pytest.approx(.4 * 5 / 3)
    assert result["photometry"][blue]["3"]["background_annulus_inner_radius_arcsec"] == pytest.approx(.8)
    assert result["ratio_f090_f444"] == pytest.approx(.1, rel=1e-6)
