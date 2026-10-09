"""Controls for the calibration replay, sample leverage and actual DQ accounting."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from tools.jwst.line_sensitivity import Extraction, SOURCE_HASH
from tools.jwst import point_resolution
from tools.jwst.point_resolution import (
    leave_one_bin_out,
    native_batch_quality,
    native_quality_support,
    read_point_resolution,
    render_summary,
)


def test_point_curve_replay_rejects_corrupt_transform(tmp_path):
    path = tmp_path / "point.csv"
    path.write_text("wavelength_um,point_R\n1,100\n2,200\n3,300\n")
    receipt = {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "coefficients_descending": [100, 0],
        "source_receipt": {"requested_url": "https://example.invalid/pinned", "sha256": "abc"},
        "grid_receipt": {"sha256": "def"},
        "citation": "test fixture",
    }
    provenance = Path(str(path) + ".provenance.json")
    provenance.write_text(json.dumps(receipt))
    wave, resolution, metadata = read_point_resolution(path)
    assert np.allclose(wave, [1, 2, 3])
    assert np.allclose(resolution, [100, 200, 300])
    assert metadata["transform_replayed"]
    receipt["coefficients_descending"] = [101, 0]
    provenance.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="cannot be replayed"):
        read_point_resolution(path)
    path.write_text(path.read_text() + "4,400\n")
    with pytest.raises(ValueError, match="does not match receipt"):
        read_point_resolution(path)


def test_leverage_omits_each_good_bin_once_preserving_original_grid():
    wave = np.linspace(2.15, 3.2, 55)
    error = np.full_like(wave, 0.002)
    mask = np.ones(len(wave), dtype=bool)
    mask[10] = False
    # Independent smooth known continuum. Omitting individual bins should never
    # invent line flux even though those bins define the sampling geometry.
    ext = Extraction("flat", wave, 0.02 + 0.003 * (wave - 2.675), error, mask, {})
    result = leave_one_bin_out(ext, np.array([0.5, 6]), np.array([100, 100]))
    assert result["full_bin_grid_preserved"]
    assert result["deletions"] == 54
    assert {r["omitted_full_grid_index"] for r in result["records"]} == set(np.flatnonzero(mask))
    assert all(r["remaining_fit_bins"] == 53 for r in result["records"])
    assert all(np.max(np.abs(r["line_fluxes"])) < 1e-9 for r in result["records"])
    assert mask[10] == 0  # input mask was not mutated


def test_native_dq_support_rejects_saturated_and_nonfinite(tmp_path):
    wave = np.array([[2.296, 2.299, 2.394], [2.297, 2.298, 2.395]])
    science = np.ones_like(wave)
    error = np.ones_like(wave)
    science[1, 1] = np.nan
    dq = np.array([[0, 1, 0], [2, 0, 0]], dtype=np.uint32)
    primary = fits.PrimaryHDU()
    primary.header["CAL_VER"] = "test"
    primary.header["CRDS_CTX"] = "test"
    sci = fits.ImageHDU(science, name="SCI")
    sci.header["SRCNAME"] = "5224_277193"
    sci.header["SRCTYPE"] = "EXTENDED"
    sci.header["BUNIT"] = "MJy/sr"
    path = tmp_path / "native.fits"
    fits.HDUList(
        [
            primary,
            sci,
            fits.ImageHDU(error, name="ERR"),
            fits.ImageHDU(wave, name="WAVELENGTH"),
            fits.ImageHDU(dq, name="DQ"),
        ]
    ).writeto(path)
    Path(str(path) + ".provenance.json").write_text(
        json.dumps(
            {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "input_receipt": {"requested_url": "https://example.invalid/native"},
                "exposure_time_s": 100,
            }
        )
    )
    source_wave = np.linspace(2.15, 3.2, 100)
    leverage = {
        "per_line_extrema": {
            n: {"minimum_omitted_index": int(np.argmin(np.abs(source_wave - center)))}
            for n, center in [("NIV", 2.297), ("CIV", 2.394)]
        }
    }
    result = native_quality_support(
        path, np.array([0.5, 6]), np.array([100, 100]), leverage, source_wave
    )
    assert result["usable_native_pixels"] == 3
    assert result["line_window_quality_support"]["NIV"]["do_not_use_pixels_all_rows"] == 1
    assert result["line_window_quality_support"]["NIV"]["saturated_pixels_all_rows"] == 1
    assert (
        result["highest_leverage_bin_native_overlap"]["NIV"]["native_usable_pixels_in_bin_all_rows"]
        == 1
    )
    # Counting the same exposure twice must not turn one native quality control
    # into two independent observations.
    batch_path = tmp_path / "batch.json"
    record = {
        "derived_slit_filename": path.name,
        "identity_quality": {"sha256": result["input_sha256"]},
        "metadata": {"position_number": 1},
    }
    batch_path.write_text(
        json.dumps(
            {
                "source_spectrum_receipt": {"sha256": SOURCE_HASH},
                "exposures": [record, record],
                "budget": {"actual_original_bytes": 100},
            }
        )
    )
    with pytest.raises(ValueError, match="Duplicate exposure"):
        native_batch_quality(
            batch_path, tmp_path, np.array([0.5, 6]), np.array([100, 100]), leverage, source_wave
        )


@pytest.fixture
def pinned_batch_control(tmp_path, monkeypatch):
    """Small real-byte fixtures; source nod identities come from the verified FITS.

    This isolates archive certification from detector-DQ tests above. Untrusted
    manifests can be rewritten, but independent inventory/derivative pins remain.
    """
    spectrum = Path(__file__).resolve().parents[1] / "data_sources/pilot/mom_z14_dja_v4.spec.fits"
    products, records, nods = [], [], {}
    with fits.open(spectrum, memmap=False) as h:
        slits = [(r["filename"], int(r["position_number"])) for r in h["SLITS"].data]
    for index, (slit, nod) in enumerate(slits):
        original = slit.split("_nrs2_")[0] + "_nrs2_cal.fits"
        derived = original.replace("_cal.fits", "_277193_native.fits")
        url = "https://example.invalid/pinned/" + original
        raw = ("original known bytes %d" % index).encode()
        (tmp_path / original).write_bytes(raw)
        receipt = {
            "requested_url": url,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        data = ("derived known bytes %d" % index).encode()
        (tmp_path / derived).write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        Path(str(tmp_path / derived) + ".provenance.json").write_text(
            json.dumps({"input_receipt": receipt, "sha256": digest})
        )
        products.append(
            {
                "filename": original,
                "source_slits_filename": slit,
                "url": url,
                "sha256": receipt["sha256"],
                "expected_bytes": len(raw),
            }
        )
        records.append(
            {
                "metadata": {
                    "filename": original,
                    "source_slits_filename": slit,
                    "url": url,
                    "position_number": nod,
                },
                "derived_slit_filename": derived,
                "native_exposure_receipt": receipt,
                "identity_quality": {"sha256": digest},
            }
        )
        nods[derived] = nod
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"source_spectrum_sha256": SOURCE_HASH, "products": products}))
    batch = {
        "source_spectrum_receipt": {"sha256": SOURCE_HASH},
        "exposures": records,
        "budget": {"actual_original_bytes": sum(p["expected_bytes"] for p in products)},
    }
    pinned = tmp_path / "pinned.json"
    pinned.write_text(json.dumps(batch))
    incoming = tmp_path / "incoming.json"

    def support(path, *args):
        return {
            "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "nod_position_header": nods[path.name],
            "line_window_quality_support": {
                n: {"native_pixels_in_window_all_rows": 2, "finite_usable_dq_pixels_all_rows": 2}
                for n in point_resolution.LINE_NAMES
            },
            "highest_leverage_bin_native_overlap": {
                n: {
                    "dja_bin_center_um": 2.3 if n == "NIV" else 2.4,
                    "native_pixels_in_bin_all_rows": 2,
                    "native_usable_pixels_in_bin_all_rows": 2,
                    "do_not_use_pixels_all_rows": 0,
                    "saturated_pixels_all_rows": 0,
                }
                for n in ("NIV", "CIV")
            },
        }

    monkeypatch.setattr(point_resolution, "native_quality_support", support)

    def check(data=None):
        incoming.write_text(json.dumps(batch if data is None else data))
        return native_batch_quality(
            incoming,
            tmp_path,
            np.array([1.0, 4.0]),
            np.array([100.0, 100.0]),
            {},
            np.array([2.0, 3.0]),
            inventory_path=inventory,
            pinned_batch_path=pinned,
            spectrum_path=spectrum,
        )

    return batch, check, tmp_path, support


def test_exact_pinned_nine_with_actual_original_bytes_certifies(pinned_batch_control):
    _, check, _, _ = pinned_batch_control
    result = check()
    assert result["exposure_count"] == 9
    assert result["all_uv_window_pixels_usable"] is True
    assert result["all_high_leverage_overlap_pixels_usable"] is True
    assert result["uv_support_status"] == "estimable"
    assert [e["nod_position_header"] for e in result["exposures"]] == [1, 2, 3] * 3


@pytest.mark.parametrize("count", [0, 1, 8])
def test_empty_or_partial_batch_cannot_certify_archive(pinned_batch_control, count):
    batch, check, _, _ = pinned_batch_control
    bad = deepcopy(batch)
    bad["exposures"] = bad["exposures"][:count]
    bad["budget"]["actual_original_bytes"] = 0
    with pytest.raises(ValueError, match="exactly nine"):
        check(bad)


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate",
        "identity",
        "source",
        "parent_sha",
        "parent_size",
        "parent_url",
        "nod",
        "derived_name",
        "budget",
    ],
)
def test_untrusted_manifest_cannot_substitute_pinned_inputs(pinned_batch_control, fault):
    batch, check, _, _ = pinned_batch_control
    bad = deepcopy(batch)
    r = bad["exposures"][0]
    if fault == "duplicate":
        bad["exposures"][0] = deepcopy(bad["exposures"][1])
    elif fault == "identity":
        r["metadata"]["filename"] = "substituted_cal.fits"
    elif fault == "source":
        bad["source_spectrum_receipt"]["sha256"] = "0" * 64
    elif fault == "parent_sha":
        r["native_exposure_receipt"]["sha256"] = "0" * 64
    elif fault == "parent_size":
        r["native_exposure_receipt"]["bytes"] += 1
    elif fault == "parent_url":
        r["native_exposure_receipt"]["requested_url"] = "https://example.invalid/wrong"
    elif fault == "nod":
        r["metadata"]["position_number"] = 2
    elif fault == "derived_name":
        r["derived_slit_filename"] = "substituted_native.fits"
    else:
        bad["budget"]["actual_original_bytes"] = 0
    with pytest.raises(ValueError):
        check(bad)


@pytest.mark.parametrize("kind", ["original", "derived"])
def test_rewritten_manifest_and_receipt_cannot_hide_byte_corruption(pinned_batch_control, kind):
    batch, check, directory, _ = pinned_batch_control
    bad = deepcopy(batch)
    r = bad["exposures"][0]
    name = r["metadata"]["filename"] if kind == "original" else r["derived_slit_filename"]
    path = directory / name
    raw = path.read_bytes().replace(b"known", b"other")  # preserves size
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    if kind == "original":
        r["native_exposure_receipt"]["sha256"] = digest
    else:
        r["identity_quality"]["sha256"] = digest
        receipt_path = Path(str(path) + ".provenance.json")
        receipt = json.loads(receipt_path.read_text())
        receipt["sha256"] = digest
        receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="pinned|inventory"):
        check(bad)
    # The original file must also be hashed, not merely trusted via its receipt.
    if kind == "original":
        with pytest.raises(ValueError, match="Actual native original bytes"):
            check()


@pytest.mark.parametrize("kind", ["window", "overlap"])
def test_zero_native_support_is_not_estimable_and_prose_follows(
    pinned_batch_control, monkeypatch, kind
):
    _, check, directory, support = pinned_batch_control

    def empty(path, *args):
        actual = support(path)
        if kind == "window":
            actual["line_window_quality_support"]["NIV"] = {
                "native_pixels_in_window_all_rows": 0,
                "finite_usable_dq_pixels_all_rows": 0,
            }
        else:
            actual["highest_leverage_bin_native_overlap"]["NIV"].update(
                native_pixels_in_bin_all_rows=0, native_usable_pixels_in_bin_all_rows=0
            )
        return actual

    monkeypatch.setattr(point_resolution, "native_quality_support", empty)
    result = check()
    key = (
        "all_uv_window_pixels_usable"
        if kind == "window"
        else "all_high_leverage_overlap_pixels_usable"
    )
    status = "uv_support_status" if kind == "window" else "high_leverage_support_status"
    assert result[key] is None
    assert result[status] == "not_estimable"
    report = json.loads(
        (
            Path(__file__).resolve().parents[1] / "research_output/mom_z14_point_resolution.json"
        ).read_text()
    )
    report["native_batch_quality"] = result
    render_summary(report, directory / "report.json")
    text = (directory / "report.md").read_text()
    assert "**not estimable**" in text
    if kind == "window":
        assert "All pixels in the five" not in text
    else:
        assert "All highest-leverage" not in text
        assert "These native samples supply no flag-based justification" not in text


@pytest.mark.parametrize("kind", ["window", "overlap"])
def test_missing_uv_group_cannot_certify_quality(pinned_batch_control, monkeypatch, kind):
    _, check, _, support = pinned_batch_control

    def incomplete(path, *args):
        actual = support(path)
        key = (
            "line_window_quality_support"
            if kind == "window"
            else "highest_leverage_bin_native_overlap"
        )
        del actual[key]["NIV"]
        return actual

    monkeypatch.setattr(point_resolution, "native_quality_support", incomplete)
    with pytest.raises(ValueError, match="missing required UV groups"):
        check()


def test_actual_nod_header_must_match_verified_source(pinned_batch_control, monkeypatch):
    _, check, _, support = pinned_batch_control

    def wrong_nod(path, *args):
        actual = support(path)
        actual["nod_position_header"] = 4
        return actual

    monkeypatch.setattr(point_resolution, "native_quality_support", wrong_nod)
    with pytest.raises(ValueError, match="nod header differs"):
        check()


def test_supported_failed_quality_is_false_not_unknown(pinned_batch_control, monkeypatch):
    _, check, directory, support = pinned_batch_control

    def failed_quality(path, *args):
        actual = support(path)
        actual["line_window_quality_support"]["NIV"]["finite_usable_dq_pixels_all_rows"] = 1
        actual["highest_leverage_bin_native_overlap"]["NIV"][
            "native_usable_pixels_in_bin_all_rows"
        ] = 1
        return actual

    monkeypatch.setattr(point_resolution, "native_quality_support", failed_quality)
    result = check()
    assert result["all_uv_window_pixels_usable"] is False
    assert result["all_high_leverage_overlap_pixels_usable"] is False
    assert result["uv_support_status"] == "estimable"
    report = json.loads(
        (
            Path(__file__).resolve().parents[1] / "research_output/mom_z14_point_resolution.json"
        ).read_text()
    )
    report["native_batch_quality"] = result
    render_summary(report, directory / "report.json")
    text = (directory / "report.md").read_text()
    assert "At least one supported UV-window pixel fails" in text
    assert "All pixels in the five" not in text
    assert "All highest-leverage" not in text
