"""Scientific regressions for frozen pilot eligibility and gray-scale cancellation."""

import io
import json

import numpy as np
import pytest

from tools.jwst.research4_jades_pilot import coverage, endpoint, run, validate_product


def test_masked_line_is_unavailable_despite_finite_sideband():
    w = np.arange(1.65, 1.75, 0.0005)
    flux = np.ones_like(w)
    flux[abs(w - 1.7) < 0.004] = np.nan
    data = dict(WAVELENGTH=w, FLUX=flux, FLUX_ERR=np.ones_like(w))
    result = coverage(data, 1.7, "FLUX", "FLUX_ERR")
    assert result["red_sideband_bins"] >= 4
    assert result["primary_box_fraction"] == 0
    assert not result["eligible"]


def test_gray_grating_scale_cancels_and_negative_is_retained_but_not_logged():
    measurements = {}
    for config, scale in (("f070lp-g140m", 1), ("f170lp-g235m", 1.8)):
        for line, flux in (("Hb", 5), ("OIII", 20)):
            measurements[f"{config}_5pix_FLUX_{line}"] = dict(
                coverage=dict(eligible=True),
                fit=dict(covariance_valid=True, flux_1e20=flux * scale),
            )
    assert abs(endpoint(measurements)) < 1e-14
    measurements["f170lp-g235m_5pix_FLUX_Hb"]["fit"]["flux_1e20"] = -1
    assert endpoint(measurements) is None
    assert measurements["f170lp-g235m_5pix_FLUX_Hb"]["fit"]["flux_1e20"] == -1


def test_nonuniform_grid_rejected_instead_of_fabricating_coverage():
    data = dict(WAVELENGTH=np.array([1.69, 1.7, 1.701, 1.71]), FLUX=np.ones(4), FLUX_ERR=np.ones(4))
    with pytest.raises(ValueError, match="uniform"):
        coverage(data, 1.7, "FLUX", "FLUX_ERR")


def test_cached_product_substitution_rejected_before_fits_or_network(tmp_path):
    name = "hlsp_jades_jwst_nirspec_goods-s-deepjwst-00000001_f070lp-g140m_v1.0_x1d.fits"
    (tmp_path / name).write_bytes(b"substituted product")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            dict(
                targets=[dict(tier="goods-s-deepjwst", target=1, unique_id="goods-s-deepjwst_1")],
                max_download_bytes=1000,
            )
        )
    )
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(dict(downloads=[dict(name=name, sha256="bad hash")])))
    with pytest.raises(ValueError, match="hash disagrees"):
        run(manifest, tmp_path, tmp_path / "fresh" / "output.json", receipt)


def test_wrong_grating_rejected_before_scientific_measurement():
    from types import SimpleNamespace

    hdus = [SimpleNamespace(header=dict(TARGET="1", GRATING="G395M"))]
    with pytest.raises(ValueError, match="GRATING"):
        validate_product(hdus, dict(target=1, tier="goods-s-deepjwst"), "f070lp-g140m")


def test_reacquired_known_product_must_match_original_hash(tmp_path, monkeypatch):
    name = "hlsp_jades_jwst_nirspec_goods-s-deepjwst-00000001_f070lp-g140m_v1.0_x1d.fits"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            dict(
                targets=[dict(tier="goods-s-deepjwst", target=1, unique_id="goods-s-deepjwst_1")],
                max_download_bytes=1000,
            )
        )
    )
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(dict(downloads=[dict(name=name, sha256="original hash")])))
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: io.BytesIO(b"new bytes"))
    with pytest.raises(ValueError, match="hash disagrees"):
        run(manifest, tmp_path, tmp_path / "output.json", receipt)
