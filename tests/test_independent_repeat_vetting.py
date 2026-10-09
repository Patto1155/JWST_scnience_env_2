"""Synthetic counterexamples for native independence and held-out astrometry."""

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.io import fits

from discovery.independent_repeat_vetting import (
    centroid_diagnostic,
    contributor_metadata,
    heldout_frame,
    independent_pair,
)


def _write(path, exposure="00003", *, ndriz=1, extra="", filename=None):
    stem = f"jw02736001001_02105_{exposure}_nrcalong"
    primary = fits.PrimaryHDU()
    for key, value in {
        "NDRIZ": ndriz,
        "FILENAME": filename or stem + "_i2d.fits",
        "EXPMID": 59737.25,
        "EFFEXPTM": 837.468,
        "FILTER": "F444W",
        "DETECTOR": "NRCALONG",
    }.items():
        primary.header[key] = value
    text = f"Step Detector1Pipeline running with args ('{stem}_uncal.fits',). {extra}"
    blob = fits.ImageHDU(np.frombuffer(text.encode(), dtype=np.uint8), name="ASDF")
    fits.HDUList([primary, blob]).writeto(path)


def test_same_detector_input_cannot_veto_itself(tmp_path):
    path = tmp_path / "fixture.fits"
    _write(path)
    metadata = contributor_metadata(path)
    second = {**metadata, "expmid_mjd": metadata["expmid_mjd"] + 0.02}
    with pytest.raises(ValueError, match="disjoint"):
        independent_pair(metadata, second)


@pytest.mark.parametrize("ndr", [0, 2])
def test_mosaic_contributor_count_fails_closed(tmp_path, ndr):
    path = tmp_path / "fixture.fits"
    _write(path, ndriz=ndr)
    with pytest.raises(ValueError, match="single-contributor"):
        contributor_metadata(path)


def test_multiple_logged_inputs_fail_closed(tmp_path):
    path = tmp_path / "fixture.fits"
    _write(path, extra="jw02736001001_02105_00004_nrcalong_uncal.fits")
    with pytest.raises(ValueError, match="exactly one"):
        contributor_metadata(path)


def test_changed_filename_cannot_disguise_reused_input(tmp_path):
    path = tmp_path / "fixture.fits"
    _write(path, filename="jw02736001001_02105_00004_nrcalong_i2d.fits")
    with pytest.raises(ValueError, match="identity"):
        contributor_metadata(path)


def test_translation_is_evaluated_on_disjoint_holdout():
    matches = [
        {
            "source_id": f"reference_{i}",
            "dra_cosdec_arcsec": 0.03,
            "ddec_arcsec": -0.02 if i % 2 == 0 else 0.04,
        }
        for i in range(40)
    ]
    result = heldout_frame(matches)
    assert result["training"] == result["holdout"] == 20
    assert result["training_median_offset_east_north_arcsec"] == [0.03, -0.02]
    # The odd references have a deliberately different offset. A same-source
    # fit/evaluation would conceal this residual.
    assert result["holdout_corrected_radial_median_p90_arcsec"] == pytest.approx([0.06, 0.06])


def test_no_degenerate_interval_for_tiny_frame():
    result = heldout_frame([{"source_id": "reference_0"}])
    assert result["status"] == "insufficient_matches"


def test_centroid_distance_preserves_scalar_and_empty_catalog():
    sky = SkyCoord(110 * u.deg, -73 * u.deg)
    detections = SkyCoord([110, 111] * u.deg, [-73, -73] * u.deg)
    assert centroid_diagnostic(sky, detections)["nearest_distance_arcsec"] == 0
    empty = SkyCoord([] * u.deg, [] * u.deg)
    assert centroid_diagnostic(sky, empty)["status"] == "no_segmented_detection"
