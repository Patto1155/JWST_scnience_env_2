"""Mathematical controls for observed finite-aperture stellar response."""

import copy

import numpy as np
import pytest
from astropy.wcs import WCS

from discovery.stellar_aperture import (
    centroid,
    compact,
    grouped_summary,
    measure,
    ratio,
    valid_pixels,
)
from tools.jwst.photometry import extract_photometry


def bundle():
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crpix = [64, 64]
    wcs.wcs.crval = [53, -28]
    wcs.wcs.cdelt = [-0.031 / 3600, 0.031 / 3600]
    yy, xx = np.mgrid[:128, :128]
    science = 1e-7 + 2e-5 * np.exp(-((xx - 63.37) ** 2 + (yy - 64.13) ** 2) / 2)
    b = dict(
        sci=science,
        err=np.full(science.shape, 1e-8),
        dq=np.zeros(science.shape, np.uint32),
        wcs=wcs,
        header={"BUNIT": "Jy"},
    )
    b["validity_mask"] = valid_pixels(b)
    return b


def test_ratio_propagates_nested_aperture_covariance_analytically():
    a = dict(flux_jy=2, weights={0: 1})
    b = dict(flux_jy=4, weights={0: 1, 1: 1})
    result = ratio(a, b, np.ones((1, 2)))
    assert result["finite_aperture_ratio"] == 0.5
    assert result["shared_pixel_flux_covariance_jy2"] == 1
    assert result["diagonal_ratio_sigma"] == pytest.approx(np.sqrt(1 / 32))
    identical = ratio(b, b, np.ones((1, 2)))
    assert identical["finite_aperture_ratio"] == 1
    assert identical["diagonal_ratio_sigma"] == 0


def test_signed_small_aperture_is_preserved_but_nonpositive_reference_fails():
    errors = np.ones((1, 2))
    assert (
        ratio(dict(flux_jy=-2, weights={0: 1}), dict(flux_jy=4, weights={1: 1}), errors)[
            "finite_aperture_ratio"
        ]
        == -0.5
    )
    with pytest.raises(ValueError, match="reference"):
        ratio(dict(flux_jy=2, weights={0: 1}), dict(flux_jy=0, weights={1: 1}), errors)


def test_native_physical_operator_matches_production_on_synthetic_control():
    b = bundle()
    measured = measure(b, 63.37, 64.13, 0.189, (0.378, 0.63))
    production = extract_photometry(
        b,
        x=63.37,
        y=64.13,
        aperture_radius_arcsec=0.189,
        background_annulus_inner_radius_arcsec=0.378,
        background_annulus_outer_radius_arcsec=0.63,
    )
    assert measured["flux_jy"] == pytest.approx(production["background_subtracted_flux_jy"])
    assert measured["diagonal_sigma_jy"] == pytest.approx(production["flux_error_jy"])
    assert measured["aperture_coverage"] == 1


def test_dq_policy_masks_saturation_and_unusable_but_retains_corrected_jump_pixels():
    b = bundle()
    b["dq"][64, 63] = 2
    b["dq"][64, 64] = 1
    b["dq"][64, 65] = 4
    b["err"][65, 65] = 0
    valid = valid_pixels(b)
    assert not valid[64, 63] and not valid[64, 64]
    assert valid[64, 65]
    assert not valid[65, 65]
    b["validity_mask"] = valid
    assert measure(b, 63.37, 64.13, 0.189, (0.378, 0.63))["aperture_coverage"] < 1


def test_background_neighbor_mask_changes_annulus_but_never_source_aperture():
    b = bundle()
    ordinary = measure(b, 63.37, 64.13, 0.189, (0.378, 0.63))
    mask = np.zeros(b["sci"].shape, bool)
    mask[64, :] = True
    masked = measure(b, 63.37, 64.13, 0.189, (0.378, 0.63), mask)
    assert masked["aperture_pixels"] == ordinary["aperture_pixels"]
    assert masked["annulus_pixels"] < ordinary["annulus_pixels"]
    assert masked["annulus_coverage"] < ordinary["annulus_coverage"]


def test_subpixel_core_centroid_recovers_independent_gaussian_location():
    b = bundle()
    x, y = centroid(b, 64, 64, radius=3)
    assert x == pytest.approx(63.37, abs=0.035)
    assert y == pytest.approx(64.13, abs=0.035)
    with pytest.raises(ValueError, match="off image"):
        centroid(b, 1, 1)


def test_source_group_bootstrap_keeps_two_dependent_dithers_as_one_star():
    rows = [
        dict(
            source_id=str(i),
            epoch=e,
            finite_aperture_ratio=0.7 + i * 0.01 + e * 0.003,
            diagonal_ratio_sigma=0.001,
        )
        for i in range(6)
        for e in (0, 1)
    ]
    summary = grouped_summary(rows)
    assert summary["stars"] == 6 and summary["dependent_exposure_measurements"] == 12
    assert summary["median_epoch2_minus_epoch1_ratio"] == pytest.approx(0.003)
    assert summary["median_source_bootstrap_95"] is not None
    assert summary["median_star_mean_ratio"] == pytest.approx(0.7265)


def test_compact_report_pins_raw_records_without_mutating_observations():
    report = dict(stars=2, records=[dict(source_id="a", ratio=0.7)])
    original = copy.deepcopy(report)
    result = compact(report)
    assert result["stars"] == 2 and "records" not in result
    assert result["regenerable_records"]["count"] == 1
    assert report == original


@pytest.mark.parametrize("radii", [(0.7, (0.3, 0.6)), (0.2, (0.3, 0.3)), (0, (0.3, 0.6))])
def test_invalid_or_missing_native_aperture_geometry_fails(radii):
    with pytest.raises(ValueError, match="geometry"):
        measure(bundle(), 63, 64, radii[0], radii[1])
