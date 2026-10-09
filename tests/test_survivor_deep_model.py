"""Independent analytic controls for signed flux, spatial deblending and throughput."""

import json

import numpy as np
import pytest

from data_pipeline.survivor_deep_data import verify_pinned
from discovery.survivor_deep_model import (
    band_average,
    continuum_shape,
    elliptical_gaussian,
    fit_mask,
    image_template,
    linear_fit,
)


def test_blank_deblend_operator_keeps_actual_science_relative_geometry(monkeypatch):
    """A target-only recentering must not alter its separation from a companion."""
    from astropy.wcs import WCS

    from discovery import survivor_deep_model as model

    scale, size, half = 0.05, 41, 20
    psf = elliptical_gaussian(size, 1.4, 1.0, 0.0)
    params = np.array([0.073, -0.046, 0.08, 0.6, 0.4])
    expected = image_template(psf, scale, params)
    companion = image_template(psf, scale, np.array([-0.27, -0.2, 0.03, 1.0, 0.0]))
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crpix = [151, 151]
    wcs.wcs.crval = [53, -27]
    wcs.wcs.cdelt = [-scale / 3600, scale / 3600]
    rng = np.random.default_rng(871)
    bundle = {
        "sci": rng.normal(size=(300, 300)),
        "err": np.ones((300, 300)),
        "validity_mask": np.ones((300, 300), bool),
        "wcs": wcs,
        "header": {"BUNIT": "nanoJansky"},
    }
    monkeypatch.setattr(model, "detect_sources", lambda *args, **kwargs: None)
    original_fit = model.linear_fit
    sampled = []

    def checked_fit(data, error, target, mask, pixel_scale, companion_arg=None):
        # Validate against the independently constructed science target + companion.
        np.testing.assert_allclose(target, expected, atol=1e-15)
        np.testing.assert_array_equal(companion_arg, companion)
        sampled.append(True)
        return original_fit(data, error, target, mask, pixel_scale, companion_arg)

    monkeypatch.setattr(model, "linear_fit", checked_fit)
    measured = model.blank_operator_noise(bundle, psf, params, scale, half, companion)
    assert measured["count"] >= 20
    assert len(sampled) == measured["count"]


def analytic_image(flux=120.0):
    size, scale = 41, 0.05
    psf = elliptical_gaussian(size, 1.8, 1.0, 0.0)
    params = np.array([0.013, -0.025, 0.07, 0.6, 0.4])
    template = image_template(psf, scale, params)
    yy, xx = np.mgrid[:size, :size] - size // 2
    data = flux * template + 3.0 + 0.3 * xx * scale - 0.2 * yy * scale
    error = np.full((size, size), 0.5)
    return data, error, template, fit_mask(size, scale), scale


@pytest.mark.parametrize("flux", [120.0, -7.0])
def test_signed_flux_and_background_plane_exact(flux):
    data, error, template, mask, scale = analytic_image(flux)
    fit = linear_fit(data, error, template, mask, scale)
    assert fit["flux_njy"] == pytest.approx(flux, abs=1e-10)
    assert fit["background_njy_per_pixel"] == pytest.approx(3.0)
    assert fit["background_gradient_njy_per_pixel_per_arcsec"] == pytest.approx([0.3, -0.2])
    assert fit["chi2_diagonal"] < 1e-20


def test_empirical_shape_operator_with_two_components():
    data, error, template, mask, scale = analytic_image()
    companion = image_template(
        elliptical_gaussian(41, 1.3, 1.0, 0.0), scale, np.array([-0.35, -0.2, 0.02, 1.0, 0.0])
    )
    data += 50 * companion
    fit = linear_fit(data, error, template, mask, scale, companion)
    assert fit["flux_njy"] == pytest.approx(120.0, abs=1e-9)
    assert fit["companion_flux_njy"] == pytest.approx(50.0, abs=1e-9)
    assert fit["target_companion_flux_covariance_njy2"] != 0
    assert fit["chi2_diagonal"] < 1e-20
    wrong = linear_fit(data, error, template, mask, scale)
    assert wrong["chi2_diagonal"] > 1


def test_exact_covariance_against_independent_lstsq():
    data, error, template, mask, scale = analytic_image()
    yy, xx = np.mgrid[:41, :41] - 20
    design = np.stack(
        [template[mask], np.ones(mask.sum()), xx[mask] * scale, yy[mask] * scale], axis=1
    )
    _, _, _, singular = np.linalg.lstsq(
        design / error[mask, None], data[mask] / error[mask], rcond=None
    )
    # Direct SVD on weighted design supplies an independent inverse Fisher diagonal.
    _, s, vt = np.linalg.svd(design / error[mask, None], full_matrices=False)
    covariance = (vt.T / s**2) @ vt
    fitted = linear_fit(data, error, template, mask, scale)
    assert np.all(singular > 0)
    assert fitted["diagonal_error_njy"] == pytest.approx(np.sqrt(covariance[0, 0]))


def test_masked_missing_pixels_and_rejected_empty_model():
    data, error, template, mask, scale = analytic_image()
    data[20, 20] = np.nan
    fit = linear_fit(data, error, template, mask, scale)
    assert fit["flux_njy"] == pytest.approx(120.0)
    with pytest.raises(ValueError, match="Too few"):
        linear_fit(data, error, template, np.zeros_like(mask), scale)


def test_finite_psf_cropped_wings_are_not_renormalized():
    psf = elliptical_gaussian(41, 10, 1.0, 0.0)
    broadened = image_template(psf, 0.05, np.array([0.0, 0.0, 0.3, 1.0, 0.0]))
    assert 0 < broadened.sum() < psf.sum()
    with pytest.raises(ValueError):
        elliptical_gaussian(40, 1.0, 1.0, 0.0)


def test_photon_integral_constant_fnu_and_in_band_step():
    wave = np.linspace(0.8, 1.2, 1001)
    transmission = np.ones_like(wave)
    assert band_average(wave, transmission, np.ones_like(wave) * 3.7) == pytest.approx(3.7)
    shape = continuum_shape(
        [(wave, transmission)], "lyman_step_powerlaw", np.array([1 / 0.1216 - 1, 0.0])
    )
    expected = np.log(1.2 / 1.0) / np.log(1.2 / 0.8)
    assert shape[0] == pytest.approx(expected, abs=1e-3)
    with pytest.raises(ValueError, match="Unknown"):
        continuum_shape([(wave, transmission)], "invented", np.zeros(2))


def test_cached_receipt_cannot_override_pinned_inventory(tmp_path):
    import hashlib

    path = tmp_path / "file.fits"
    path.write_bytes(b"altered")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_name("file.fits.provenance.json").write_text(
        json.dumps({"sha256": digest, "bytes": 7})
    )
    with pytest.raises(ValueError, match="pinned"):
        verify_pinned(path, {"sha256": "0" * 64, "expected_bytes": 7})
