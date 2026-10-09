"""Synthetic independent point/background identifiability and boundary controls."""

import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.wcs import WCS

from discovery.source_patch_diagnostics import background_basis, fit_patch, linear_fit


def model():
    y, x = np.mgrid[-30:31, -30:31] * 0.025
    psf = np.exp(-(x * x + y * y) / (2 * 0.07**2))
    psf /= psf.sum()
    background = 2 + 3 * x - 4 * y + 10 * y * y
    return x, y, psf, background


def test_quadratic_background_recovers_signed_point_flux_without_absorption():
    x, y, psf, background = model()
    for flux in (-300, 0, 1000):
        report = linear_fit(
            background + flux * psf, np.ones(x.shape), psf, x, y, np.ones(x.shape, bool), degree=2
        )
        assert report["status"] == "fit"
        assert report["signed_point_amplitude_njy"] == pytest.approx(flux, abs=1e-8)
        assert report["source_excluded_background_point_amplitude_njy"] == pytest.approx(
            flux, abs=0.05
        )
        assert report["fitted_background_core_sum_njy"] == pytest.approx(
            report["source_excluded_background_core_sum_njy"], abs=0.05
        )


def test_simple_background_can_bias_amplitude_and_not_form_source_truth():
    x, y, psf, background = model()
    common = (background, np.ones(x.shape), psf, x, y, np.ones(x.shape, bool))
    naive = linear_fit(*common, degree=0)
    corrected = linear_fit(*common, degree=2)
    assert abs(naive["signed_point_amplitude_njy"]) > 50
    assert abs(corrected["signed_point_amplitude_njy"]) < 1e-8


def test_grouped_correlated_residual_uncertainty_and_masks_are_explicit():
    x, y, psf, background = model()
    rng = np.random.default_rng(31)
    block_ids = np.floor((x + 0.75) / 0.2).astype(int) + 10 * np.floor((y + 0.75) / 0.2).astype(int)
    noise = rng.normal(size=100)[block_ids]
    valid = np.ones(x.shape, bool)
    valid[:5] = False
    report = linear_fit(
        background + 200 * psf + noise,
        np.ones(x.shape),
        psf,
        x,
        y,
        valid,
        degree=2,
        cluster_width=0.2,
    )
    assert report["fit_pixels"] == valid.sum()
    assert report["residual_cluster_sigma_njy"] > report["formal_diagonal_sigma_njy"]
    assert (
        "conditional" in report["confidence_scope"] or "approximation" in report["confidence_scope"]
    )
    with pytest.raises(ValueError):
        linear_fit(background, np.ones(x.shape), psf, x, y, valid, degree=2, cluster_width=0)
    with pytest.raises(ValueError):
        background_basis(x, y, 3)


def test_off_image_window_does_not_wrap_negative_pixel_indices():
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crpix = [2, 2]
    wcs.wcs.crval = [100, -40]
    wcs.wcs.cdelt = [-0.063 / 3600, 0.063 / 3600]
    bundle = {"sci": np.zeros((8, 8)), "err": np.ones((8, 8)), "wcs": wcs}
    report = fit_patch(
        bundle,
        SkyCoord(100, -40, unit="deg"),
        np.ones((21, 21)) / 441,
        0.02,
        SkyCoord([], [], unit="deg"),
        halfwidth=0.65,
        degree=2,
    )
    assert report["status"] == "fit_window_off_image"
