"""Independent signed-tail and covariance controls, explicitly synthetic."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.wcs import WCS
from scipy.signal import fftconvolve

from discovery.empirical_imaging_controls import (
    binomial_interval,
    heldout_tails,
    mirrored_screen,
    pixel_covariance,
    selected_images,
)


def rows(values):
    return [
        {"net_flux": float(value), "diagonal_sigma": 1.0, "spatial_block": f"{i % 16}:{i // 16}"}
        for i, value in enumerate(values)
    ]


def test_zero_tail_has_finite_sample_upper_bound_and_no_five_sigma_claim():
    report = heldout_tails(rows(np.random.default_rng(81).normal(size=512)))
    five = [r for r in report["tails"] if r["threshold"] == 5]
    assert all(r["events"] == 0 for r in five)
    assert all(r["nominal_binomial_95"][1] > 0.005 for r in five)
    assert report["five_sigma_gaussian_certified"] is False
    assert binomial_interval(0, 0) is None
    with pytest.raises(ValueError):
        binomial_interval(3, 2)


def test_heavy_tails_are_counted_and_sign_inversion_swaps_tails():
    values = np.random.default_rng(27).normal(size=1024)
    values[:9] = [12, -12, 15, -15, 16, -16, 17, -17, 20]
    positive = heldout_tails(rows(values))
    negative = heldout_tails(rows(-values))
    counts = {(r["sign"], r["threshold"]): r["events"] for r in positive["tails"]}
    reversed_counts = {(r["sign"], r["threshold"]): r["events"] for r in negative["tails"]}
    assert counts[("positive", 5)] == 5
    assert counts[("negative", 5)] == 4
    for threshold in (2, 3, 4, 5):
        assert counts[("positive", threshold)] == reversed_counts[("negative", threshold)]
    for fold in positive["fold_calibrations"]:
        assert fold["n_training"] == 1024 - fold["n_heldout"]


def test_empty_or_one_checkerboard_does_not_certify_tail():
    assert heldout_tails([])["status"] == "insufficient_heldout_apertures"
    one = rows(np.random.default_rng(41).normal(size=100))
    for row in one:
        row["spatial_block"] = "0:0"
    assert heldout_tails(one)["status"] == "insufficient_checkerboard_fold"
    invalid = rows(np.random.default_rng(23).normal(size=100))
    invalid[0]["diagonal_sigma"] = 0
    with pytest.raises(ValueError, match="positive finite error"):
        heldout_tails(invalid)


def test_covariance_detects_positive_and_negative_neighbours_without_clipping():
    white = np.random.default_rng(92).normal(size=(384, 384))
    results = []
    for kernel in (
        np.array([[1.0]]),
        np.array([[1, 1]]) / np.sqrt(2),
        np.array([[1, -1]]) / np.sqrt(2),
    ):
        image = fftconvolve(white, kernel, mode="same")
        report = pixel_covariance(
            {"sci": image, "err": np.ones_like(image)}, np.zeros_like(image, dtype=bool)
        )
        results.append(
            next(
                r["covariance_over_zero_lag"]
                for r in report["lags"]
                if (r["dx"], r["dy"]) == (1, 0)
            )
        )
    assert abs(results[0]) < 0.02
    assert results[1] == pytest.approx(0.5, abs=0.02)
    assert results[2] == pytest.approx(-0.5, abs=0.02)
    assert (
        pixel_covariance({"sci": white}, np.zeros_like(white, dtype=bool))["status"]
        == "explicit_ERR_missing"
    )
    assert (
        pixel_covariance(
            {"sci": white, "err": np.ones_like(white)}, np.ones_like(white, dtype=bool)
        )["status"]
        == "insufficient_off_source_pixels"
    )
    isolated = np.ones_like(white, dtype=bool)
    isolated[::16, ::16] = False
    sparse = pixel_covariance({"sci": white, "err": np.ones_like(white)}, isolated)
    adjacent = next(r for r in sparse["lags"] if (r["dx"], r["dy"]) == (1, 0))
    assert adjacent["pairs"] == 0
    assert adjacent["covariance_over_zero_lag"] is None


def test_blind_mirrored_multiband_screen_finds_injected_negative_excursion():
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crpix = [32, 32]
    wcs.wcs.crval = [100, -40]
    wcs.wcs.cdelt = [-0.063 / 3600, 0.063 / 3600]
    header = wcs.to_header()
    header["BUNIT"] = "nJy"
    rng = np.random.default_rng(211)
    bundles = {}
    for band in ("F090W", "F200W", "F444W"):
        image = rng.normal(size=(64, 64))
        if band == "F444W":
            image[29:34, 29:34] -= 40
        bundles[band] = {"sci": image, "err": np.ones_like(image), "header": header, "wcs": wcs}
    report = mirrored_screen(bundles, radius=0.189, annulus=(0.378, 0.63))
    assert report["n_negative_detections"] == 1
    assert report["summary"]["survivors"] == 1
    assert report["contamination_rate"] is None
    assert report["audits"][0]["reference_snr"] > 100


def test_frozen_image_identity_is_portable_and_rejects_altered_or_duplicate_inputs():
    bands = ("F090W", "F200W", "F444W")
    verified = [
        {"resolved_path": f"/new/cache/{band}.fits", "filter": band, "sha256": band}
        for band in bands
    ]
    old_paths = {band: f"/old/cache/{band}.fits" for band in bands}
    receipts = {band: {"sha256": band} for band in bands}
    assert (
        selected_images(verified, old_paths, receipts)["F444W"]["resolved_path"]
        == "/new/cache/F444W.fits"
    )
    with pytest.raises(ValueError, match="duplicated"):
        selected_images(verified + [verified[0]], old_paths, receipts)
    altered = [{**r, "sha256": "changed"} for r in verified]
    with pytest.raises(ValueError, match="disagree"):
        selected_images(altered, old_paths, receipts)
