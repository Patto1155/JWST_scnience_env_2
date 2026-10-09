"""Required-band selection must use simultaneous sky, not separate overlaps."""

from __future__ import annotations

import numpy as np
from astropy.wcs import WCS

import discovery.build_universe_table as pipeline
from tools.jwst.common_coverage import sampled_joint_valid_fraction


def _image(shape=(64, 64), offset_x=0):
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [53.0, -27.0]
    wcs.wcs.crpix = [1.0 - offset_x, 1.0]
    wcs.wcs.cdelt = [-0.1 / 3600, 0.1 / 3600]
    return {
        "sci": np.ones(shape),
        "err": np.ones(shape),
        "validity_mask": np.ones(shape, dtype=bool),
        "wcs": wcs,
    }


def test_slightly_smaller_common_quadrant_beats_larger_disjoint_quadrant(monkeypatch):
    bundles = {
        "reference_i2d": _image(),
        "blue_i2d": _image((64, 32)),
        "mid_disjoint_i2d": _image((64, 32), offset_x=32),
        "mid_joint_i2d": _image((64, 31)),
    }
    monkeypatch.setattr(pipeline, "load_fits_bundle", lambda name: bundles[name])
    grouped = {
        "F444W": [{"name": "reference_i2d"}],
        "F090W": [{"name": "blue_i2d"}],
        "F200W": [{"name": "mid_disjoint_i2d"}, {"name": "mid_joint_i2d"}],
    }
    old_choice, _ = pipeline._map_for_reference(grouped, "reference_i2d")
    assert old_choice["F200W"] == "mid_disjoint_i2d"
    selected, overlaps = pipeline._build_target_dataset_map(grouped)
    assert selected["F200W"] == "mid_joint_i2d"
    assert overlaps["F200W"] < overlaps["F090W"]
    assert (
        sampled_joint_valid_fraction(
            bundles["reference_i2d"], [bundles["blue_i2d"], bundles[selected["F200W"]]]
        )
        > 0.4
    )


def test_joint_selection_keeps_corrected_goods_reference_anchor(monkeypatch):
    bundles = {
        "goods_obs030_i2d": _image(offset_x=80),
        "goods_obs026_i2d": _image(),
        "blue_obs026_i2d": _image((64, 32)),
        "mid_obs026_i2d": _image((64, 32)),
    }
    monkeypatch.setattr(pipeline, "load_fits_bundle", lambda name: bundles[name])
    grouped = {
        "F444W": [{"name": "goods_obs030_i2d"}, {"name": "goods_obs026_i2d"}],
        "F090W": [{"name": "blue_obs026_i2d"}],
        "F200W": [{"name": "mid_obs026_i2d"}],
    }
    selected, _ = pipeline._build_target_dataset_map(grouped)
    assert selected["F444W"] == "goods_obs026_i2d"


def test_joint_rank_respects_invalid_native_pixels():
    reference, blue, middle = _image(), _image(), _image()
    blue["validity_mask"][:, 32:] = False
    middle["validity_mask"][:, :32] = False
    assert sampled_joint_valid_fraction(reference, [blue, middle]) == 0
    middle["validity_mask"][:] = True
    assert sampled_joint_valid_fraction(reference, [blue, middle]) == 0.5
