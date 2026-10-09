"""Independent mathematical controls for PSF/noise diagnostics; not real sky truth."""

import hashlib
import json

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS
from scipy.signal import fftconvolve

from discovery.psf_noise import (
    blank_aperture_report,
    circular_weights,
    overlap_resample,
    read_image,
    source_mask,
    verified_template,
)


def test_overlap_conserves_flux_at_subpixel_phase_and_crop_is_not_renormalized():
    kernel = np.arange(81, dtype=float).reshape(9, 9)
    kernel /= kernel.sum()
    for phase in ((0, 0), (0.4, -0.4)):
        large = overlap_resample(kernel, 0.03, 0.063, 15, phase)
        assert large.sum() == pytest.approx(1)
        small = overlap_resample(kernel, 0.03, 0.063, 3, phase)
        assert 0 < small.sum() < 1


@pytest.mark.parametrize("kwargs", [{"output_scale": 0}, {"size": 4}, {"phase": (np.nan, 0)}])
def test_invalid_resample_inputs(kwargs):
    parameters = dict(input_scale=0.03, output_scale=0.063, size=9)
    parameters.update(kwargs)
    with pytest.raises(ValueError):
        overlap_resample(np.ones((9, 9)), **parameters)


def test_circle_fractional_area_matches_geometry_and_pixel_center_membership():
    radius = 3.37
    area = circular_weights(15, radius, phase=(0.37, -0.13), subsamples=64)
    assert area.sum() == pytest.approx(np.pi * radius**2, rel=0.001)
    integer = circular_weights(15, 2, subsamples=1)
    assert integer.sum() == 13


def test_psf_receipt_and_filter_are_verified(tmp_path):
    path = tmp_path / "psf.fits"
    header = fits.Header({"FILTER": "F444W", "PIXELSCL": 0.03})
    fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(np.ones((9, 9)), header, name="SCI")]).writeto(
        path
    )
    raw = path.read_bytes()
    receipt = dict(
        sha256=hashlib.sha256(raw).hexdigest(),
        bytes=len(raw),
        requested_url="https://example.invalid/model.fits",
        retrieved_utc="2026-10-09",
    )
    path.with_name(path.name + ".provenance.json").write_text(json.dumps(receipt))
    image, metadata = verified_template(path, "F444W")
    assert image.sum() == pytest.approx(1)
    assert metadata["origin"].endswith("not observed-star measurement")
    with pytest.raises(ValueError, match="FILTER"):
        verified_template(path, "F090W")
    receipt["sha256"] = "0" * 64
    path.with_name(path.name + ".provenance.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="receipt"):
        verified_template(path, "F444W")


def noise_bundle(seed=8, shape=(512, 512), correlated=False):
    image = np.random.default_rng(seed).normal(size=shape)
    if correlated:
        kernel = np.outer([1, 2, 1], [1, 2, 1]).astype(float)
        kernel /= np.sqrt((kernel**2).sum())
        image = fftconvolve(image, kernel, mode="same")
    return dict(sci=image, err=np.ones(shape), header={"BUNIT": "nJy"})


def test_white_noise_unit_conversion_and_covariance_identity():
    bundle = noise_bundle()
    result = blank_aperture_report(
        bundle,
        radii=(0.189,),
        pixel_scale_arcsec=0.063,
        mask=np.zeros(bundle["sci"].shape, bool),
        bootstrap=50,
    )
    row = result["apertures"][0]
    assert row["n_apertures"] > 200
    assert 0.8 < row["noise_multiplier"] < 1.2
    assert row["ordinary_net_variance"] == pytest.approx(
        row["variance_identity_ap_plus_bg_minus_2cov"]
    )
    assert row["noise_multiplier_block_bootstrap_95"] is not None
    first = row["measurements"][0]
    assert first["flux_unit"] == "Jy"
    bundle["header"]["BUNIT"] = "Jy"
    second = blank_aperture_report(
        bundle,
        radii=(0.189,),
        pixel_scale_arcsec=0.063,
        mask=np.zeros(bundle["sci"].shape, bool),
        bootstrap=50,
    )["apertures"][0]
    assert second["noise_multiplier"] == pytest.approx(row["noise_multiplier"])
    assert second["robust_net_sigma"] == pytest.approx(row["robust_net_sigma"] * 1e9)


def test_correlated_noise_has_larger_net_aperture_variance_than_diagonal_errors():
    bundle = noise_bundle(correlated=True)
    row = blank_aperture_report(
        bundle,
        radii=(0.189,),
        pixel_scale_arcsec=0.063,
        mask=np.zeros(bundle["sci"].shape, bool),
        bootstrap=50,
    )["apertures"][0]
    assert row["noise_multiplier"] > 2
    assert row["ordinary_net_variance"] == pytest.approx(
        row["variance_identity_ap_plus_bg_minus_2cov"]
    )


def test_masked_apertures_and_bad_error_pixels_cannot_be_accepted():
    bundle = noise_bundle(shape=(128, 128))
    bundle["err"][:64] = 0
    bundle["dq"] = np.zeros(bundle["sci"].shape, int)
    bundle["dq"][:, :64] = 1
    result = blank_aperture_report(
        bundle,
        radii=(0.189,),
        pixel_scale_arcsec=0.063,
        mask=np.zeros(bundle["sci"].shape, bool),
        bootstrap=20,
    )
    assert result["valid_pixels"] == 64 * 64
    row = result["apertures"][0]
    assert row["status"] == "insufficient_blank_apertures"
    assert row["noise_multiplier"] is None
    assert all(r["x"] > 64 and r["y"] > 64 for r in row["measurements"])


def test_source_mask_detects_known_extended_control_without_clipping_blank_fluxes():
    bundle = noise_bundle(shape=(128, 128))
    yy, xx = np.mgrid[:128, :128]
    bundle["sci"] += 100 * np.exp(-((xx - 64) ** 2 + (yy - 64) ** 2) / 18)
    mask = source_mask(bundle["sci"], np.ones((128, 128), bool), dilation=5)
    assert mask[64, 64] and mask[64, 70]
    assert mask.sum() < 128 * 128 / 4


@pytest.mark.parametrize(
    "modify,error",
    [
        (lambda b: b.update(sci=np.ones((2, 2, 2))), "2D"),
        (lambda b: b.update(err=np.ones((2, 2))), "shape"),
    ],
)
def test_invalid_image_planes_fail_closed(modify, error):
    bundle = noise_bundle()
    modify(bundle)
    with pytest.raises(ValueError, match=error):
        blank_aperture_report(bundle, pixel_scale_arcsec=0.063)


def test_no_wcs_or_explicit_scale_cannot_define_angular_apertures():
    with pytest.raises(ValueError, match="WCS"):
        blank_aperture_report(noise_bundle())


def test_angular_wcs_not_nominal_scale_and_mjy_per_sr_conversion():
    bundle = noise_bundle(shape=(256, 256))
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crpix = [128, 128]
    wcs.wcs.crval = [53, -28]
    wcs.wcs.cdelt = [-0.063 / 3600, 0.063 / 3600]
    bundle.update(wcs=wcs, header={"BUNIT": "MJy/sr", "PIXAR_SR": 1})
    report = blank_aperture_report(
        bundle,
        radii=(0.188,),
        pixel_scale_arcsec=123,
        mask=np.zeros((256, 256), bool),
        bootstrap=20,
    )
    assert report["pixel_scale_arcsec"] == pytest.approx(0.063)
    assert report["angular_geometry"] == "celestial_separation"
    row = report["apertures"][0]["measurements"][0]
    assert row["calibration_status"] == "calibrated"
    assert row["diagonal_sigma"] < 1e-5


def test_strict_fits_reader_requires_named_sci_and_does_not_invent_err(tmp_path):
    path = tmp_path / "named.fits"
    fits.HDUList(
        [
            fits.PrimaryHDU(),
            fits.ImageHDU(np.ones((4, 4)), name="SCI"),
            fits.ImageHDU(np.ones((4, 4)), name="VAR_POISSON"),
        ]
    ).writeto(path)
    assert "err" not in read_image(path)
    unnamed = tmp_path / "unnamed.fits"
    fits.PrimaryHDU(np.ones((4, 4))).writeto(unnamed)
    with pytest.raises(ValueError, match="SCI"):
        read_image(unnamed)


def test_fixed_annulus_geometry_is_recorded_and_validated():
    bundle = noise_bundle()
    row = blank_aperture_report(
        bundle,
        radii=(0.126, 0.189),
        pixel_scale_arcsec=0.063,
        annulus_radii_arcsec=(0.378, 0.63),
        mask=np.zeros(bundle["sci"].shape, bool),
        bootstrap=20,
    )
    assert row["fixed_annulus_radii_arcsec"] == (0.378, 0.63)
    assert (
        row["apertures"][0]["measurements"][0]["n_annulus_pixels"]
        == row["apertures"][1]["measurements"][0]["n_annulus_pixels"]
    )
    with pytest.raises(ValueError, match="fixed annulus"):
        blank_aperture_report(
            bundle, radii=(0.189,), pixel_scale_arcsec=0.063, annulus_radii_arcsec=(0.1, 0.6)
        )
