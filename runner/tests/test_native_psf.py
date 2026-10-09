"""Independent controls for native-grid PSF correction; not sky validation."""

import copy

import numpy as np
import pytest
from astropy.wcs import WCS

from discovery.native_psf import compact_noise, native_response, source_geometry


def gaussian_template(scale=0.03, sigma_arcsec=0.09, size=201):
    yy, xx = np.mgrid[:size, :size] - size // 2
    kernel = np.exp(-(xx**2 + yy**2) * scale**2 / (2 * sigma_arcsec**2))
    return kernel / kernel.sum()


def test_native_operator_gaussian_control_and_annulus_self_subtraction():
    template = gaussian_template(scale=0.003, size=401)
    row = native_response(
        template,
        input_scale=0.003,
        output_scale=0.003,
        phase=(0, 0),
        radius=0.18,
        annulus=(0.3, 0.5),
    )
    analytic = 1 - np.exp(-(0.18**2) / (2 * 0.09**2))
    assert row["encircled_energy"] == pytest.approx(analytic, abs=0.001)
    assert row["net_response"] < row["encircled_energy"]
    assert row["total_flux_multiplier"] == pytest.approx(1 / row["net_response"])


def test_fractional_phase_binary_response_depends_on_phase_and_does_not_renormalize_wings():
    template = gaussian_template()
    centered = native_response(template, input_scale=0.03, output_scale=0.063, phase=(0, 0))
    offset = native_response(template, input_scale=0.03, output_scale=0.063, phase=(0.37, -0.4))
    assert centered["encircled_energy"] != pytest.approx(offset["encircled_energy"], abs=0.0001)
    assert 0.8 < centered["net_response"] < 1
    scaled = native_response(template * 0.9, input_scale=0.03, output_scale=0.063, phase=(0, 0))
    assert scaled["net_response"] == pytest.approx(0.9 * centered["net_response"])


@pytest.mark.parametrize(
    "parameters",
    [dict(phase=(0.6, 0)), dict(output_scale=0), dict(radius=0.7), dict(phase=(np.nan, 0))],
)
def test_invalid_native_geometry(parameters):
    args = dict(input_scale=0.03, output_scale=0.063, phase=(0, 0))
    args.update(parameters)
    with pytest.raises(ValueError):
        native_response(gaussian_template(), **args)


def test_spherical_source_masks_and_jy_conversion_agree_with_flat_geometry_on_small_patch():
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [53, -28]
    wcs.wcs.crpix = [64, 64]
    wcs.wcs.cdelt = [-0.063 / 3600, 0.063 / 3600]
    bundle = dict(sci=np.ones((128, 128)), wcs=wcs, header={"BUNIT": "MJy/sr"})
    scale, phase, geometry = source_geometry(bundle, 63.37, 64.13)
    assert scale == pytest.approx(0.063)
    assert phase == pytest.approx((0.37, 0.13))
    template = gaussian_template()
    actual = native_response(
        template, input_scale=0.03, output_scale=scale, phase=phase, geometry=geometry
    )
    flat = native_response(template, input_scale=0.03, output_scale=scale, phase=phase)
    assert actual["net_response"] == pytest.approx(flat["net_response"], abs=1e-7)
    assert actual["n_aperture_pixels"] == flat["n_aperture_pixels"]


def test_anisotropic_grid_fails_instead_of_inventing_scalar_psf_resampling():
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [53, -28]
    wcs.wcs.cdelt = [-0.063 / 3600, 0.04 / 3600]
    with pytest.raises(ValueError, match="anisotropic"):
        source_geometry(dict(wcs=wcs, header={"BUNIT": "Jy"}), 63, 64)


def test_compact_noise_preserves_results_and_pins_regenerable_positions_without_mutation():
    row = {
        "status": "measured",
        "noise_multiplier": 1.4,
        "measurements": [{"x": 1, "y": 2, "net_flux": 3}],
        "spatial_blocks": [],
    }
    report = {"apertures": [row]}
    original = copy.deepcopy(report)
    compact = compact_noise(report)
    assert report == original
    assert compact["apertures"][0]["noise_multiplier"] == 1.4
    assert "measurements" not in compact["apertures"][0]
    assert compact["apertures"][0]["regenerable_blank_measurements"]["count"] == 1
    assert (
        len(compact["apertures"][0]["regenerable_blank_measurements"]["canonical_json_sha256"])
        == 64
    )


def test_native_geometry_matches_production_coverage_mask_for_nan_science_and_wht():
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [53, -28]
    wcs.wcs.crpix = [64, 64]
    wcs.wcs.cdelt = [-0.063 / 3600, 0.063 / 3600]
    science = np.ones((128, 128))
    weight = np.ones_like(science)
    bundle = dict(sci=science, wht=weight, wcs=wcs, header={"BUNIT": "Jy"})
    _, _, geometry = source_geometry(bundle, 63.37, 64.13)
    valid_count = geometry[0].sum()
    science[64, 63] = np.nan
    weight[64, 64] = 0
    _, _, masked = source_geometry(bundle, 63.37, 64.13)
    assert masked[0].sum() == valid_count - 2


@pytest.mark.parametrize("kind", ["negative", "nan", "even"])
def test_invalid_native_template_fails_closed(kind):
    kernel = gaussian_template()
    if kind == "even":
        kernel = kernel[:-1]
    else:
        kernel[0, 0] = -1 if kind == "negative" else np.nan
    with pytest.raises(ValueError, match="template"):
        native_response(kernel, input_scale=0.03, output_scale=0.063, phase=(0, 0))
