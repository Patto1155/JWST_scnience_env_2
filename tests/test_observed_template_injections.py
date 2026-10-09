"""Flux, centroid, footprint and frozen-design controls for actual-sky injections."""
import json
from pathlib import Path

import numpy as np
import pytest
from astropy.coordinates import SkyCoord

import discovery.observed_template_injections as module


def profile():
    yy, xx = np.mgrid[-6:7, -6:7]
    values = np.exp(-(xx**2+yy**2)/8)
    return values/values.sum()


def test_template_annulus_excludes_square_corners_and_invalid_pixels():
    yy, xx = np.mgrid[-20:21, -20:21]
    distance = np.hypot(xx, yy)*0.05
    valid = np.ones(distance.shape, bool)
    annulus = module.template_annulus_mask(distance, valid)
    assert annulus[20, 40]  # radius1.0arcsec is inside the outer boundary
    assert not annulus[0, 0]  # enclosing-square corner at1.414arcsec is excluded
    assert not annulus[20, 20]  # source core is excluded
    assert np.max(distance[annulus]) <= 1
    assert np.min(distance[annulus]) >= 0.7
    valid[20, 40] = False
    assert not module.template_annulus_mask(distance, valid)[20, 40]


def test_finite_flux_preserved_across_interpolated_sizes_and_input_unchanged():
    observed = profile()
    original = observed.copy()
    for scale in module.SPATIAL_SCALES:
        sized = module.sized_template(observed, scale)
        assert sized.shape[0] % 2 == 1
        assert sized.sum() == pytest.approx(1)
        assert np.all(sized >= 0)
        background = np.random.default_rng(1).normal(size=(49, 49))
        before = background.copy()
        injected = module.injected_crop(background, sized, 80)
        assert np.sum(injected-background)*10 == pytest.approx(80)
        np.testing.assert_array_equal(background, before)
    np.testing.assert_array_equal(observed, original)


def test_profile_zero_negative_and_flux_invalid_fail_closed():
    with pytest.raises(ValueError):
        module.sized_template(np.zeros((3, 3)), 1)
    with pytest.raises(ValueError):
        module.sized_template(-np.ones((3, 3)), 1)
    with pytest.raises(ValueError):
        module.sized_template(profile(), float("nan"))
    with pytest.raises(ValueError):
        module.injected_crop(np.zeros((49, 49)), profile(), -1)
    with pytest.raises(ValueError):
        module.injected_crop(np.zeros((5, 5)), profile(), 10)


def test_min_connected_area_is_different_from_aperture_flux():
    image = np.zeros((49, 49))
    image[23:25, 23:26] = 20
    assert module.local_detection(image, 0, 1, 5, 0.05)["status"] == "matched"
    assert module.local_detection(image, 0, 1, 8, 0.05)["status"] == "not_detected"
    assert image.sum() > 100


def test_centroid_shift_gives_nonrecovery_at_high_flux():
    stamp = np.zeros((21, 21))
    stamp[9:12, 14:17] = 1/9  # displaced centroid0.25arcsec exceeds0.2matchgate
    large = module.injected_crop(np.zeros((49, 49)), stamp, 3200)
    failed = module.local_detection(large, 0, 1, 5, 0.05)
    assert failed["status"] == "not_detected"
    assert failed["nearest_centroid_arcsec"] == pytest.approx(0.25)
    smaller = module.sized_template(stamp, 0.65)
    passed = module.local_detection(module.injected_crop(np.zeros((49, 49)), smaller, 3200), 0, 1, 5, 0.05)
    assert passed["status"] == "matched"


def test_pinned_actual_design_has_disjoint_backgrounds_and_fixed_trial_grid():
    path = Path("research_output/observed_template_injection_plan.json")
    plan = json.loads(path.read_text())
    assert plan["template_ids"] == list(module.TEMPLATE_IDS)
    assert plan["fluxes_finite_stamp_njy"] == list(module.FLUXES_NJY)
    assert plan["spatial_scales"] == list(module.SPATIAL_SCALES)
    sites = plan["sites"]
    coords = SkyCoord([s["ra_deg"] for s in sites], [s["dec_deg"] for s in sites], unit="deg")
    min_separation = (2*module.CROP_HALF_PIXELS+1)*0.05*np.sqrt(2)
    for i, coord in enumerate(coords[:-1]):
        assert np.all(coord.separation(coords[i+1:]).arcsec > min_separation)
    assert len({s["site_id"] for s in sites}) == len(sites)
    assert all(t["profile_caveat"].startswith("Observed noisy") for t in plan["templates"])


def test_plan_tampering_rejected_before_any_trial(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "build_plan", lambda *a: ({"frozen": 1}, {}, {}))
    with pytest.raises(ValueError, match="Frozen injection plan"):
        module.execute({"frozen": 2}, tmp_path, tmp_path/"original")


def test_bootstrap_resamples_whole_spatial_blocks_and_zero_is_not_certificate():
    incomplete = module.blocked_interval([True, False], ["same", "same"], 1)
    assert incomplete["status"] == "insufficient_spatial_blocks"
    successful = [True, True, False, False, True, False, True, False]
    blocks = ["a", "a", "b", "b", "c", "c", "d", "d"]
    result = module.blocked_interval(successful, blocks, 123)
    assert result == module.blocked_interval(successful, blocks, 123)
    assert result["lower"] < 0.5 < result["upper"]
    zero = module.blocked_interval([False]*8, blocks, 123)
    assert zero["lower"] == zero["upper"] == 0
    assert "do not bound unseen failures" in zero["interpretation"]


def test_flux_increase_losses_are_paired_and_never_erased_by_monotone_fit():
    trials = []
    for site, outcomes in [("one", ["matched", "not_detected"]), ("two", ["not_detected", "matched"])]:
        for flux, status in zip([80, 160], outcomes):
            trials.append({"site_id": site, "template_id": "observed", "spatial_scale": 1,
                           "finite_stamp_flux_njy": flux,
                           "detections": {mode: {"status": status} for mode in ("legacy", "angular_area")}})
    changes = module.adjacent_flux_changes(trials)
    assert len(changes) == 2
    assert all(c["matched_then_nonmatched"] == c["nonmatched_then_matched"] == 1 for c in changes)
    assert all(c["paired_sites"] == 2 for c in changes)
