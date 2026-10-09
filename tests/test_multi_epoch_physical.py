"""Repeat-epoch controls through real FITS loading/WCS/photometry, no mocks."""

from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from core_api.models.datasets import Dataset
from discovery.multi_epoch import find_repeat_pairs, veto_candidate
from tools.jwst.flux_calibration import pixel_solid_angle_sr


SKY = {"ra": 53.0, "dec": -28.0}
CANDIDATE = {"target": "SYNTHETIC", "source_id": 7, "sky_center": SKY}


def epoch(
    tmp_path: Path,
    name: str,
    *,
    scale=0.1,
    flux=1e-6,
    noise=0.1,
    unit="MJy/sr",
    radius=0.0,
    mjd=60000.0,
    offset=0.0,
    no_background=False,
) -> str:
    """Inject an analytically specified Jy flux into a local synthetic image."""
    size = 121
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [SKY["ra"] + offset, SKY["dec"]]
    wcs.wcs.crpix = [size // 2 + 1] * 2
    wcs.wcs.cdelt = [-scale / 3600, scale / 3600]
    yy, xx = np.indices((size, size))
    areas = pixel_solid_angle_sr(wcs, xx, yy)
    region = np.hypot(xx - size // 2, yy - size // 2) * scale <= radius
    image = np.full((size, size), 3.0)
    image[region] += flux / (np.sum(region) * areas[region] * 1e6)
    header = wcs.to_header()
    header["BUNIT"] = unit
    # Stale detector metadata deliberately differs from actual WCS grid areas.
    header["PIXAR_SR"] = 1e-10
    primary = fits.PrimaryHDU(header=fits.Header({"EXPMID": mjd, "FILTER": "F444W"}))
    planes = [
        primary,
        fits.ImageHDU(image, header=header, name="SCI"),
        fits.ImageHDU(np.full_like(image, noise), name="ERR"),
    ]
    if no_background:
        weight = np.zeros_like(image)
        weight[np.hypot(xx - size // 2, yy - size // 2) <= 4] = 1
        planes.append(fits.ImageHDU(weight, name="WHT"))
    path = tmp_path / f"{name}_i2d.fits"
    fits.HDUList(planes).writeto(path)
    return str(path)


def pair(a, b):
    return {
        "target": "SYNTHETIC",
        "filter": "F444W",
        "epoch_a": a,
        "epoch_b": b,
        "baseline_hours": 24.0,
        "supports": "artifact_rejection_only",
    }


def test_same_extended_source_has_same_jy_flux_on_different_grids(tmp_path):
    a = epoch(tmp_path, "a", scale=0.1, radius=0.22)
    b = epoch(tmp_path, "b", scale=0.05, radius=0.22)
    measured = veto_candidate(CANDIDATE, pair(a, b))
    assert measured is not None
    assert measured["aperture_radius_arcsec"] == pytest.approx(0.3)
    assert measured["flux_epoch_a"] == pytest.approx(1e-6, rel=1e-7)
    assert measured["flux_epoch_b"] == pytest.approx(1e-6, rel=1e-7)
    assert measured["flux_unit"] == "Jy"
    assert measured["difference_significance"] < 1e-3
    assert measured["verdict"] == "persistent"


@pytest.mark.parametrize("noise", [0.0, -0.1])
def test_unknown_or_invalid_noise_is_unvettable(tmp_path, noise):
    a = epoch(tmp_path, "a")
    b = epoch(tmp_path, "b", noise=noise)
    assert veto_candidate(CANDIDATE, pair(a, b)) is None


def test_uncalibrated_counts_are_unvettable(tmp_path):
    a = epoch(tmp_path, "a")
    b = epoch(tmp_path, "b", unit="DN/s")
    assert veto_candidate(CANDIDATE, pair(a, b)) is None


@pytest.mark.parametrize("flux_b", [1e-6, 0.0])
def test_shallow_epoch_cannot_veto_a_detected_source(tmp_path, flux_b):
    a = epoch(tmp_path, "a", flux=1e-6)
    b = epoch(tmp_path, "b", flux=flux_b, noise=100)
    measured = veto_candidate(CANDIDATE, pair(a, b))
    assert measured is not None
    assert measured["snr_epoch_a"] > 3
    assert measured["snr_epoch_b"] < 3
    assert measured["difference_significance"] < 3
    assert measured["verdict"] == "inconclusive_depth"


def test_significant_single_epoch_difference_requires_follow_up(tmp_path):
    a = epoch(tmp_path, "a", flux=1e-6)
    b = epoch(tmp_path, "b", flux=0)
    measured = veto_candidate(CANDIDATE, pair(a, b))
    assert measured is not None
    assert measured["difference_significance"] >= 3
    assert measured["verdict"] == "single_epoch_only"
    assert measured["interpretation"] == "requires_artifact_depth_and_variability_checks"


def test_primary_header_times_and_real_overlap_make_pair(tmp_path):
    a = epoch(tmp_path, "a", mjd=60000.0)
    b = epoch(tmp_path, "b", mjd=60000.5)
    datasets = [
        Dataset(name=p, meta_data={"target": "SYNTHETIC", "filter": "F444W"}) for p in (a, b)
    ]
    pairs = find_repeat_pairs(datasets)
    assert len(pairs) == 1
    assert pairs[0]["baseline_hours"] == pytest.approx(12.0)
    assert pairs[0]["overlap_fraction"] > 0.9
    assert pairs[0]["supports"] == "artifact_rejection_only"


@pytest.mark.parametrize("kwargs", [{"offset": 0.1}, {"no_background": True}])
def test_no_shared_sky_or_background_does_not_create_non_detection(tmp_path, kwargs):
    a = epoch(tmp_path, "a")
    b = epoch(tmp_path, "b", **kwargs)
    assert veto_candidate(CANDIDATE, pair(a, b)) is None
