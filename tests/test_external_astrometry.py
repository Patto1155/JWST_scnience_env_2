"""Synthetic unit controls only; these are not real external-frame evidence."""

import hashlib

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from data_pipeline.original_images import verify_image
from tools.jwst.astrometry import external_astrometry, match_sources


def _bundle():
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [50, 50]
    wcs.wcs.crval = [53, -27]
    wcs.wcs.cdelt = [-0.05 / 3600, 0.05 / 3600]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    rng = np.random.default_rng(91)
    science = rng.normal(0, 1, (100, 100))
    yy, xx = np.indices(science.shape)
    science += 100 * np.exp(-((xx - 50.0) ** 2 + (yy - 50.0) ** 2) / (2 * 1.5**2))
    return {
        "sci": science,
        "wcs": wcs,
        "err": np.ones_like(science),
        "validity_mask": np.ones_like(science, dtype=bool),
    }


def test_external_reference_offset_measured_instead_of_self_wcs_round_trip():
    bundle = _bundle()
    ra, dec = bundle["wcs"].pixel_to_world_values(54, 50)
    result = match_sources(bundle, np.array([[50, 50]]), [{"id": "external", "ra": ra, "dec": dec}])
    assert len(result["matches"]) == 1
    assert result["matches"][0]["dra_cosdec_arcsec"] == pytest.approx(0.2, abs=1e-5)
    assert result["matches"][0]["radial_arcsec"] == pytest.approx(0.2, abs=1e-5)


def test_one_to_one_matches_and_covered_denominator():
    bundle = _bundle()
    ra, dec = bundle["wcs"].pixel_to_world_values(50, 50)
    far_ra, far_dec = bundle["wcs"].pixel_to_world_values(200, 200)
    references = [
        {"id": "first", "ra": ra, "dec": dec},
        {"id": "repeat", "ra": ra, "dec": dec},
        {"id": "off_array", "ra": far_ra, "dec": far_dec},
    ]
    result = match_sources(bundle, np.array([[50, 50]]), references)
    assert result["covered_references"] == 2
    assert len(result["matches"]) == 1


def test_small_reference_sample_has_no_degenerate_confidence_interval():
    bundle = _bundle()
    ra, dec = bundle["wcs"].pixel_to_world_values(50, 50)
    result = external_astrometry(bundle, [{"id": "one", "ra": ra, "dec": dec}])
    assert result["matched_sources"] == 1
    assert result["sample_status"] == "insufficient_reference_matches"
    assert result["median_offset_bootstrap95_arcsec"] is None


def test_original_image_gate_rejects_psf_headers_and_checksum_mismatch(tmp_path):
    path = tmp_path / "fixture_i2d.fits"
    fits.PrimaryHDU().writeto(path)
    product = {"product_kind": "modeled_psf"}
    with pytest.raises(ValueError, match="not PSFs/headers/cutouts"):
        verify_image(path, product)
    product.update(product_kind="original_full_i2d", sha256="0" * 64)
    with pytest.raises(ValueError, match="checksum"):
        verify_image(path, product)
    product.update(
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(), expected_bytes=path.stat().st_size
    )
    with pytest.raises(ValueError, match="SCI, ERR and WHT"):
        verify_image(path, product)
