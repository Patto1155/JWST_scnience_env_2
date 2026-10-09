"""Adversarial tests of frozen selection, geometry and denominator contracts."""
import json
from pathlib import Path

import numpy as np
import pytest
from astropy.wcs import WCS

import discovery.deep_control_recovery as module


def bundle():
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [101, 101]
    wcs.wcs.crval = [53, -27]
    wcs.wcs.cdelt = [-0.05/3600, 0.05/3600]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    values = np.random.default_rng(42).normal(size=(200, 200))
    return {"sci": values, "wcs": wcs, "validity_mask": np.ones(values.shape, bool)}


def reference(image, x, y, source="group", observation="new", cohort="robust_other"):
    sky = image["wcs"].pixel_to_world(x, y)
    return {"source_id": source, "sky_group_id": source, "ra_deg": float(sky.ra.deg),
            "dec_deg": float(sky.dec.deg), "cohort": cohort, "observation_ids": [observation]}


def test_area_matching_ceil_and_invalid_grids():
    assert module.minimum_pixels(0.063**2, 0.05**2) == 8
    assert module.minimum_pixels(0.05**2, 0.05**2) == 5
    with pytest.raises(ValueError):
        module.minimum_pixels(0, 1)
    with pytest.raises(ValueError):
        module.minimum_pixels(1, float("nan"))


def test_full_margin_includes_image_exterior_and_internal_mask():
    image = bundle()
    refs = [reference(image, 100, 100), reference(image, 1, 1), reference(image, -5, 100)]
    margin = module.covered_margin(image, refs)
    assert margin[0] > 4
    assert margin[1] < 0.1
    assert margin[2] is None
    image["validity_mask"][100, 101] = False
    assert module.covered_margin(image, refs)[0] == 0


def test_freeze_selects_one_geometry_primary_and_separates_seed(monkeypatch, tmp_path):
    image = bundle()
    refs = [reference(image, 100, 100), reference(image, 80, 80, "seed", "goods_20189546", "robust_high_z_ge_6"),
            reference(image, 0, 0, "edge")]
    provenance = lambda name: {"filename": name, "receipt": {"bytes": 1, "sha256": "checksum"}, "contributors": ["same-rate"]}
    images = [(image, provenance("z.fits")), (image, provenance("a.fits"))]
    monkeypatch.setattr(module, "load_inputs", lambda *a: (image, images))
    monkeypatch.setattr(module, "grouped_jades", lambda *a: (refs, {"count": 3}))
    monkeypatch.setattr(module, "verify", lambda *a: {})
    csv_path = tmp_path / "refs.csv"
    csv_path.write_text("catalogue")
    result = module.freeze(tmp_path, Path("original.fits"), csv_path)
    assert len(result["references"]) == 2  # two images never become four trials
    by_id = {r["source_id"]: r for r in result["references"]}
    assert by_id["group"]["primary_deep_image"] == "a.fits"
    assert by_id["seed"]["role"] == "previously_selected_failure_seed"
    assert by_id["group"]["role"] == "additional_geometry_control"
    image["sci"] *= 1e9
    assert result == module.freeze(tmp_path, Path("original.fits"), csv_path)


def test_frozen_mutation_fails_even_with_coherent_new_hash(monkeypatch, tmp_path):
    original = {"references": [{"source": "real"}], "hash": "original"}
    monkeypatch.setattr(module, "freeze", lambda *a: original)
    altered = {"references": [], "hash": module.json_hash([])}
    with pytest.raises(ValueError, match="Frozen cohort"):
        module.evaluate(altered, tmp_path, Path("original.fits"))


def test_json_hash_preserves_integer_key_normalization():
    original = {"histogram": {1: 4, 12: 2, 2: 8}}
    assert module.json_hash(original) == module.json_hash(json.loads(json.dumps(original)))


def test_missing_original_and_ambiguous_matches_keep_distinct_denominators():
    reference = {"role": "additional_geometry_control", "cohort": "robust_other"}
    rows = [{"reference": reference, "original": None},
            {"reference": reference, "original": {"status": "ambiguous"}},
            {"reference": reference, "original": {"status": "matched"}}]
    result = module.summarize(rows, "original")[0]
    assert result["groups_in_deep_union"] == 3
    assert result["covered_group_denominator"] == 2
    assert result["matched"] == result["ambiguous"] == 1
    assert result["conditional_recovery_fraction"] == 0.5


def test_area_detection_can_fail_real_aperture_signal():
    image = bundle()
    image["sci"][98:100, 98:101] = 20  # six bright pixels; fails 8-pixel connected gate
    assert len(module.detections(image, 5, 0.8)) == 1
    assert module.detections(image, 8, 0.8) == []
