"""Synthetic controls for manifest trust, joint area and the real-image CLI chain."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from discovery.audit_candidates import audit_candidate, summarize
from discovery.image_photometry_rerun import (
    load_selection_measurements,
    run_rerun,
    sha256_file,
    verify_image_manifest,
)
from tools.jwst.common_coverage import joint_valid_coverage


def _bundle(mask: np.ndarray, *, scale: float = 0.1) -> dict:
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [53.0, -27.0]
    wcs.wcs.crpix = [1.0, 1.0]
    wcs.wcs.cdelt = [-scale / 3600.0, scale / 3600.0]
    return {
        "sci": np.zeros(mask.shape),
        "err": np.ones(mask.shape),
        "validity_mask": mask,
        "wcs": wcs,
    }


def test_separate_overlap_does_not_imply_joint_coverage():
    full = np.ones((12, 12), dtype=bool)
    left, right = full.copy(), full.copy()
    left[:, 6:] = False
    right[:, :6] = False
    report = joint_valid_coverage(_bundle(full), {"blue": _bundle(left), "mid": _bundle(right)})
    assert report["comparison_coverage"]["blue"]["pixel_count"] == 72
    assert report["comparison_coverage"]["mid"]["pixel_count"] == 72
    assert report["joint_valid_pixel_count"] == 0
    assert report["joint_valid_area_arcsec2"] == 0


def test_area_and_chunk_invariance_with_invalid_errors():
    mask = np.ones((12, 12), dtype=bool)
    reference, comparison = _bundle(mask), _bundle(mask)
    comparison["err"][4:8, 4:8] = 0
    small = joint_valid_coverage(reference, {"blue": comparison}, chunk_pixels=7)
    large = joint_valid_coverage(reference, {"blue": comparison}, chunk_pixels=1000)
    assert small["joint_valid_pixel_count"] == 128
    assert small["joint_valid_area_arcsec2"] == pytest.approx(1.28, rel=1e-5)
    assert small["joint_valid_area_arcsec2"] == pytest.approx(large["joint_valid_area_arcsec2"])


def test_coverage_requires_wcs():
    reference = _bundle(np.ones((4, 4), dtype=bool))
    reference["wcs"] = None
    with pytest.raises(ValueError, match="celestial"):
        joint_valid_coverage(reference, {})


def _write_control_image(path: Path, band: str) -> None:
    bundle = _bundle(np.ones((96, 96), dtype=bool))
    y, x = np.indices((96, 96))
    image = np.random.default_rng(63).normal(0, 0.001, (96, 96))
    if band == "F444W":
        image += 0.1 * np.exp(-((x - 48) ** 2 + (y - 48) ** 2) / 8)
    header = bundle["wcs"].to_header()
    header["BUNIT"] = "MJy/sr"
    primary = fits.PrimaryHDU()
    primary.header["FILTER"] = band
    primary.header["DATAMODL"] = "ImageModel"
    fits.HDUList(
        [
            primary,
            fits.ImageHDU(image, header=header, name="SCI"),
            fits.ImageHDU(np.full(image.shape, 0.001), name="ERR"),
        ]
    ).writeto(path)


def _manifest(tmp_path: Path) -> Path:
    rows = []
    for band in ("F090W", "F200W", "F444W"):
        path = tmp_path / f"{band}.fits"
        _write_control_image(path, band)
        rows.append(
            {
                "path": path.name,
                "sha256": sha256_file(path),
                "filter": band,
                "target": "synthetic_unit_control",
                "kind": "science_image",
            }
        )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"images": rows}))
    return manifest


def test_manifest_hash_and_template_fail_closed(tmp_path):
    manifest = _manifest(tmp_path)
    payload = json.loads(manifest.read_text())
    payload["images"][0]["sha256"] = "0" * 64
    payload["images"][1]["kind"] = "modeled_psf"
    manifest.write_text(json.dumps(payload))
    verified, blocked = verify_image_manifest(manifest)
    assert len(verified) == 1
    assert {row["reason"] for row in blocked} == {"sha256_mismatch", "not_declared_science_image"}


def test_missing_image_is_blocked_not_zero_survivors(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "images": [
                    {
                        "path": "absent.fits",
                        "sha256": None,
                        "filter": "F444W",
                        "target": "original",
                        "kind": "science_image",
                    }
                ]
            }
        )
    )
    output = tmp_path / "outputs"
    result = run_rerun(manifest, output)
    assert result["status"] == "blocked"
    assert result["proposal_count"] is None
    assert result["dropout_screen_survivors"] is None
    assert not (output / "exploratory_proposals.json").exists()


def test_detector_photometry_audit_chain_keeps_proposals_separate(tmp_path):
    manifest = _manifest(tmp_path)
    output = tmp_path / "outputs"
    result = run_rerun(manifest, output)
    assert result["status"] == "executed"
    assert result["proposal_count"] >= 1
    proposals = json.loads((output / "exploratory_proposals.json").read_text())
    assert all(row["screen_identity"] == "exploratory_proposal" for row in proposals)
    assert all(row["classifier_applied"] is False for row in proposals)
    assert all(
        row["photometry_by_filter"]["F444W"]["3"]["calibration_status"] == "calibrated"
        for row in proposals
    )
    assert result["audit_summary"]["total_candidates"] == result["proposal_count"]
    assert result["audit_summary"]["survivors"] == result["dropout_screen_survivors"]
    recovered = load_selection_measurements(
        output / "selection_measurements.csv", output / "selection_metadata.json"
    )
    assert summarize([audit_candidate(row) for row in recovered]) == result["audit_summary"]
    assert not (tmp_path / "highz_candidates.json").exists()
