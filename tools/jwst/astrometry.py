"""External source-centroid checks: an image's own WCS round trip is not evidence."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.stats import sigma_clipped_stats
from photutils.segmentation import SourceCatalog, detect_sources


def reference_sources(csv_path: str | Path) -> list[dict[str, Any]]:
    """Retain A/B GS target coordinates, group repeated NIRCam source identities."""
    unique: dict[str, dict[str, Any]] = {}
    with Path(csv_path).open() as stream:
        for row in csv.DictReader(stream):
            if row["Field"] != "GS" or row["z_Spec_flag"] not in {"A", "B"}:
                continue
            ra, dec = float(row["RA_TARG"]), float(row["Dec_TARG"])
            if not np.isfinite([ra, dec]).all():
                continue
            source_id = int(row["NIRCam_DR5_ID"])
            key = f"GS_DR5_{source_id}" if source_id > 0 else f"GS_sky_{ra:.6f}_{dec:.6f}"
            unique.setdefault(key, {"id": key, "ra": ra, "dec": dec})
    return list(unique.values())


def detect_centroids(bundle: dict[str, Any], *, threshold_sigma: float = 5) -> np.ndarray:
    """Segment actual image pixels; no catalog-coordinate forced peak centering."""
    science, valid = np.asarray(bundle["sci"]), np.asarray(bundle["validity_mask"]).copy()
    if bundle.get("err") is not None:
        error = np.asarray(bundle["err"])
        valid &= np.isfinite(error) & (error > 0)
    _, median, sigma = sigma_clipped_stats(science[valid], sigma=3)
    segments = detect_sources(
        np.where(valid, science - median, 0), threshold_sigma * sigma, npixels=5, mask=~valid
    )
    if segments is None:
        return np.empty((0, 2))
    catalog = SourceCatalog(np.where(valid, science - median, 0), segments, mask=~valid)
    points = np.column_stack([catalog.xcentroid, catalog.ycentroid]).astype(float)
    height, width = science.shape
    selected = np.isfinite(points).all(axis=1)
    selected &= (points[:, 0] > 16) & (points[:, 0] < width - 17)
    selected &= (points[:, 1] > 16) & (points[:, 1] < height - 17)
    return points[selected]


def match_sources(
    bundle: dict[str, Any],
    points: np.ndarray,
    references: list[dict[str, Any]],
    *,
    radius_arcsec: float = 0.5,
    offset_arcsec: tuple[float, float] = (0, 0),
) -> dict[str, Any]:
    """One-to-one angular matching with separate covered-reference denominator."""
    reference = SkyCoord(
        [r["ra"] for r in references] * u.deg, [r["dec"] for r in references] * u.deg
    )
    reference = reference.spherical_offsets_by(
        offset_arcsec[0] * u.arcsec, offset_arcsec[1] * u.arcsec
    )
    x, y = bundle["wcs"].world_to_pixel(reference)
    height, width = bundle["sci"].shape
    covered = np.isfinite(x) & np.isfinite(y)
    covered &= (x > 16) & (x < width - 17) & (y > 16) & (y < height - 17)
    for i in np.flatnonzero(covered):
        covered[i] &= bool(bundle["validity_mask"][int(round(y[i])), int(round(x[i]))])
    indices = np.flatnonzero(covered)
    if not len(indices) or not len(points):
        return {"covered_references": int(len(indices)), "matches": []}
    detected = bundle["wcs"].pixel_to_world(points[:, 0], points[:, 1])
    nearest, separation, _ = reference[indices].match_to_catalog_sky(detected)
    matches, used = [], set()
    for local in np.argsort(separation.arcsec):
        detector_index = int(nearest[local])
        if separation.arcsec[local] > radius_arcsec or detector_index in used:
            continue
        used.add(detector_index)
        reference_index = int(indices[local])
        dra, ddec = reference[reference_index].spherical_offsets_to(detected[detector_index])
        matches.append(
            {
                "source_id": references[reference_index]["id"],
                "detected_index": detector_index,
                "x": float(points[detector_index, 0]),
                "y": float(points[detector_index, 1]),
                "dra_cosdec_arcsec": float(dra.arcsec),
                "ddec_arcsec": float(ddec.arcsec),
                "radial_arcsec": float(separation.arcsec[local]),
            }
        )
    return {"covered_references": int(len(indices)), "matches": matches}


def external_astrometry(
    bundle: dict[str, Any],
    references: list[dict[str, Any]],
    *,
    seed: int = 20261009,
) -> dict[str, Any]:
    """Measure absolute offsets and shifted-catalog controls with uncertainty."""
    points = detect_centroids(bundle)
    result = match_sources(bundle, points, references)
    matches = result.pop("matches")
    result.update({"detected_centroids": len(points), "matched_sources": len(matches)})
    if matches:
        offsets = np.array([[m["dra_cosdec_arcsec"], m["ddec_arcsec"]] for m in matches])
        radial = np.array([m["radial_arcsec"] for m in matches])
        rng = np.random.default_rng(seed)
        interval = None
        if len(matches) >= 5:
            medians = np.median(
                offsets[rng.integers(0, len(matches), (2000, len(matches)))], axis=1
            )
            interval = np.percentile(medians, [2.5, 97.5], axis=0).tolist()
        result.update(
            {
                "median_offset_arcsec": np.median(offsets, axis=0).tolist(),
                "median_offset_bootstrap95_arcsec": interval,
                "radial_median_arcsec": float(np.median(radial)),
                "radial_p90_arcsec": float(np.percentile(radial, 90)),
            }
        )
    controls = []
    for offset in ((10, 0), (-10, 0), (0, 10), (0, -10)):
        null = match_sources(bundle, points, references, offset_arcsec=offset)
        controls.append(
            {
                "offset_arcsec": list(offset),
                "covered_references": null["covered_references"],
                "matched_sources": len(null["matches"]),
            }
        )
    result.update(
        {
            "matching_radius_arcsec": 0.5,
            "detection_threshold_sigma": 5,
            "sample_status": "measured" if len(matches) >= 5 else "insufficient_reference_matches",
            "shifted_catalog_controls": controls,
            "matches": matches,
            "interpretation": "external_released_JADES_target_coordinates_vs_image_centroids",
            "limitations": [
                "Released NIRSpec target coordinates are not a Gaia absolute-frame certification.",
                "Galaxy structure, blending and target-coordinate choices contribute to offsets.",
                "Bootstrap intervals capture finite-source sampling, not image-wide systematic error.",
                "Matching radius and segmentation are fixed; no offset was fitted then reapplied.",
            ],
        }
    )
    return result
