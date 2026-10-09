"""Cross-implementation aperture-response controls, with no public-data download."""

import numpy as np
import pytest
from astropy.wcs import WCS

from discovery.native_psf import ANNULUS, RADIUS, native_response, source_geometry
from discovery.psf_noise import overlap_resample
from tools.jwst.photometry import extract_photometry


@pytest.mark.parametrize("unit", ["Jy", "MJy/sr"])
@pytest.mark.parametrize("masked", [False, True])
def test_native_psf_response_agrees_with_production_photometer(unit, masked):
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [53, -28]
    wcs.wcs.crpix = [64, 64]
    angle = np.deg2rad(19)
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    wcs.wcs.cd = rotation @ np.diag([-0.063 / 3600, 0.063 / 3600])
    image = np.zeros((128, 128))
    weights = np.ones_like(image)
    if masked:
        image[64, 63] = np.nan
        weights[64, 64] = 0
    bundle = dict(sci=image, wht=weights, err=np.ones_like(image), wcs=wcs, header={"BUNIT": unit})
    x, y = 63.37, 64.13
    scale, phase, geometry = source_geometry(bundle, x, y)
    yy, xx = np.mgrid[-100:101, -100:101]
    input_scale = 0.03
    template = np.exp(-0.5 * ((xx * input_scale / 0.09) ** 2 + (yy * input_scale / 0.10) ** 2))
    template /= template.sum()
    native = native_response(
        template, input_scale=input_scale, output_scale=scale, phase=phase, geometry=geometry
    )
    # Insert an integrated one-Jy model directly into SCI's declared units.
    # The production photometer independently owns WCS geometry, valid pixels,
    # physical conversion and annulus subtraction; it does not call native_response.
    size = geometry[0].shape[0]
    model = overlap_resample(template, input_scale, scale, size, phase)
    patch_y, patch_x = np.mgrid[:size, :size] - size // 2
    grid_y, grid_x = patch_y + round(y), patch_x + round(x)
    bad_science = ~np.isfinite(image[grid_y, grid_x])
    image[grid_y, grid_x] = model / geometry[2]
    image[grid_y[bad_science], grid_x[bad_science]] = np.nan
    measured = extract_photometry(
        bundle,
        x=x,
        y=y,
        aperture_radius_arcsec=RADIUS,
        background_annulus_inner_radius_arcsec=ANNULUS[0],
        background_annulus_outer_radius_arcsec=ANNULUS[1],
    )
    assert measured["background_subtracted_flux_jy"] == pytest.approx(
        native["net_response"], abs=1e-12
    )
    assert measured["valid_pixel_count"] == native["n_aperture_pixels"]
    assert measured["annulus_pixel_count"] == native["n_annulus_pixels"]
