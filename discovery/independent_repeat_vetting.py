"""Hash-verified single-contributor repeat vetting with held-out astrometry.

This operator workflow measures source persistence, never redshift or identity.
Distinct pixels do not imply independent instrumental calibration systematics.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits

from data_pipeline.original_images import file_sha256, verify_image
from discovery.f444w_repeat_screen import classify_pair
from discovery.image_photometry_rerun import load_selection_measurements
from tools.jwst.astrometry import detect_centroids, match_sources
from tools.jwst.fits_loader import load_fits_bundle
from tools.jwst.photometry import extract_photometry


def contributor_metadata(path: Path) -> dict[str, Any]:
    """Require explicit single-exposure upstream detector1 provenance.

    The readable ASDF calibration log is inspected as bytes, never executed.
    We deliberately reject mosaics: filename/time alone cannot establish their
    contributor independence. This supports the actual single-exposure i2ds.
    """
    with fits.open(path, memmap=True) as hdul:
        header = hdul[0].header
        if header.get("NDRIZ") != 1 or "ASDF" not in hdul:
            raise ValueError("single-contributor NDRIZ=1 with ASDF provenance required")
        text = hdul["ASDF"].data.tobytes().decode("utf-8", errors="replace")
        inputs = sorted(set(re.findall(r"jw\d{11}_\d{5}_\d{5}_nrc[a-z0-9]+_uncal\.fits", text)))
        if len(inputs) != 1 or "Step Detector1Pipeline" not in text:
            raise ValueError("exactly one logged upstream detector1 input required")
        if inputs[0].removesuffix("_uncal.fits") != str(header["FILENAME"]).removesuffix(
            "_i2d.fits"
        ):
            raise ValueError("upstream detector input disagrees with image identity")
        return {
            "filename": header["FILENAME"],
            "detector_inputs": inputs,
            "expmid_mjd": float(header["EXPMID"]),
            "exposure_time_s": float(header["EFFEXPTM"]),
            "filter": header["FILTER"],
            "detector": header["DETECTOR"],
            "cal_ver": header.get("CAL_VER"),
            "crds_context": header.get("CRDS_CTX"),
            "association_table": header.get("ASNTABLE"),
        }


def independent_pair(reference: dict, comparison: dict) -> dict:
    """Disjoint declared native contributors are mandatory before any veto."""
    left, right = set(reference["detector_inputs"]), set(comparison["detector_inputs"])
    if not left or not right or left & right:
        raise ValueError("repeat images require nonempty disjoint native contributors")
    if reference["filter"] != comparison["filter"]:
        raise ValueError("repeat test requires the same filter")
    baseline = abs(reference["expmid_mjd"] - comparison["expmid_mjd"]) * 24
    if baseline == 0:
        raise ValueError("repeat requires distinct observing times")
    return {
        "native_contributor_overlap": [],
        "baseline_hours": baseline,
        "exposure_time_ratio": comparison["exposure_time_s"] / reference["exposure_time_s"],
        "interpretation": "distinct detector integrations; shared calibration remains possible",
    }


def heldout_frame(matches: list[dict], *, seed: int = 20261009) -> dict:
    """Fit a robust translation on even references, evaluate odd references.

    Source ordering is fixed by independently segmented reference centroids.
    This is a relative same-band galaxy frame, not absolute Gaia astrometry.
    """
    train = [m for m in matches if int(m["source_id"].split("_")[-1]) % 2 == 0]
    holdout = [m for m in matches if int(m["source_id"].split("_")[-1]) % 2 == 1]
    if len(train) < 10 or len(holdout) < 10:
        return {"status": "insufficient_matches", "training": len(train), "holdout": len(holdout)}
    offsets = np.asarray([[m["dra_cosdec_arcsec"], m["ddec_arcsec"]] for m in train])
    validation = np.asarray([[m["dra_cosdec_arcsec"], m["ddec_arcsec"]] for m in holdout])
    shift = np.median(offsets, axis=0)
    rng = np.random.default_rng(seed)
    bootstrap = np.median(offsets[rng.integers(0, len(offsets), (2000, len(offsets)))], axis=1)
    corrected = validation - shift
    return {
        "status": "measured",
        "training": len(train),
        "holdout": len(holdout),
        "training_median_offset_east_north_arcsec": shift.tolist(),
        "training_median_bootstrap95_arcsec": np.percentile(
            bootstrap, [2.5, 97.5], axis=0
        ).tolist(),
        "holdout_raw_radial_median_p90_arcsec": np.percentile(
            np.linalg.norm(validation, axis=1), [50, 90]
        ).tolist(),
        "holdout_corrected_radial_median_p90_arcsec": np.percentile(
            np.linalg.norm(corrected, axis=1), [50, 90]
        ).tolist(),
        "holdout_corrected_component_mad_sigma_arcsec": (
            1.4826 * np.median(np.abs(corrected - np.median(corrected, axis=0)), axis=0)
        ).tolist(),
        "limitations": [
            "Finite-source bootstrap omits shared calibration and galaxy structure.",
            "No fitted offset is applied to the forced-photometry measurements.",
            "The matched-source distribution is conditional on two detections within 0.2 arcsec.",
        ],
    }


def _measure(bundle: dict, sky: dict, aperture: dict) -> dict:
    return extract_photometry(image_data=bundle, ra_deg=sky["ra"], dec_deg=sky["dec"], **aperture)


def _compact_measurement(measured: dict) -> dict:
    return {
        key: measured.get(key)
        for key in (
            "background_subtracted_flux_jy",
            "flux_error_jy",
            "coverage_fraction",
            "measurement_status",
            "background_status",
            "calibration_status",
        )
    }


def centroid_diagnostic(sky: SkyCoord, detections: SkyCoord) -> dict:
    """Nearest independently segmented position; preserve absent detections."""
    if len(detections) == 0:
        return {"status": "no_segmented_detection", "is_association": False}
    separations = detections.separation(sky)
    nearest = int(np.argmin(separations.arcsec))
    distance = float(separations[nearest].arcsec)
    offset = sky.spherical_offsets_to(detections[nearest])
    return {
        "nearest_distance_arcsec": distance,
        "offset_east_north_arcsec": [float(x.arcsec) for x in offset],
        "within_0p2_arcsec": distance <= 0.2,
        "detection_threshold_sigma": 5,
        "is_association": distance <= 0.2,
    }


def run(manifest_path: Path, selection_dir: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text())
    if len(manifest["images"]) != 2:
        raise ValueError("exactly two single-contributor original images required")
    products = manifest["images"]
    verified, metadata, bundles = [], [], []
    for product in products:
        path = Path(product["path"])
        verified.append(verify_image(path, product))
        metadata.append(contributor_metadata(path))
        bundles.append(load_fits_bundle(str(path)))
    independence = independent_pair(*metadata)
    csv_path, meta_path = (
        selection_dir / "selection_measurements.csv",
        selection_dir / "selection_metadata.json",
    )
    proposals = load_selection_measurements(csv_path, meta_path)
    summary_path = selection_dir / "rerun_summary.json"
    summary = json.loads(summary_path.read_text())
    ref_name = products[0]["product_filename"]
    original = next(r for r in summary["image_receipts"] if r["product_filename"] == ref_name)
    if original["sha256"] != products[0]["sha256"]:
        raise ValueError("candidate selection and reference image hashes disagree")
    selected_ids = {int(r["source_id"]) for r in summary["audit_summary"]["survivor_ids"]}
    sources = [p for p in proposals if p["source_id"] in selected_ids]
    if len(sources) != len(selected_ids):
        raise ValueError("selected source identities missing or duplicated")
    selection_metadata = json.loads(meta_path.read_text())
    aperture = {
        "aperture_radius_arcsec": selection_metadata["aperture_radius_arcsec_by_filter"]["F444W"],
        "background_annulus_inner_radius_arcsec": selection_metadata["annulus_radii_arcsec"][
            "inner"
        ],
        "background_annulus_outer_radius_arcsec": selection_metadata["annulus_radii_arcsec"][
            "outer"
        ],
    }
    points = [detect_centroids(b) for b in bundles]
    ref_sky = bundles[0]["wcs"].pixel_to_world(points[0][:, 0], points[0][:, 1])
    references = [
        {"id": f"reference_{i}", "ra": c.ra.deg, "dec": c.dec.deg} for i, c in enumerate(ref_sky)
    ]
    # Exclude selected proposals from the control frame before fitting/validation.
    candidates = SkyCoord(
        [s["sky_center"]["ra"] for s in sources] * u.deg,
        [s["sky_center"]["dec"] for s in sources] * u.deg,
    )
    _, distance, _ = ref_sky.match_to_catalog_sky(candidates)
    references = [r for r, d in zip(references, distance.arcsec, strict=True) if d > 1.0]
    match = match_sources(bundles[1], points[1], references, radius_arcsec=0.2)
    frame = heldout_frame(match["matches"])
    repeat_sky = bundles[1]["wcs"].pixel_to_world(points[1][:, 0], points[1][:, 1])
    rows = []
    for source in sources:
        measured = [_measure(b, source["sky_center"], aperture) for b in bundles]
        frozen = source["photometry_by_filter"]["F444W"]["3"]
        for key in ("background_subtracted_flux_jy", "flux_error_jy"):
            if not np.isclose(frozen[key], measured[0][key], rtol=1e-9, atol=1e-20):
                raise ValueError("reference photometry failed frozen-input reproduction")
        sky = SkyCoord(source["sky_center"]["ra"] * u.deg, source["sky_center"]["dec"] * u.deg)
        paired = classify_pair(*measured)
        sensitivities = []
        # Fixed +/-0.05 arcsec tests assess plausible registration perturbations;
        # they are scenarios, not a confidence interval on a source's position.
        for east, north in ((0.05, 0), (-0.05, 0), (0, 0.05), (0, -0.05)):
            shifted = sky.spherical_offsets_by(east * u.arcsec, north * u.arcsec)
            test = _measure(bundles[1], {"ra": shifted.ra.deg, "dec": shifted.dec.deg}, aperture)
            sensitivities.append(
                {"offset_east_north_arcsec": [east, north], **classify_pair(measured[0], test)}
            )
        rows.append(
            {
                "source_id": source["source_id"],
                "sky_center": source["sky_center"],
                "reference": _compact_measurement(measured[0]),
                "repeat": _compact_measurement(measured[1]),
                "paired": paired,
                "error_scale3_scenario": classify_pair(*measured, error_scale=3),
                "repeat_independent_centroid": centroid_diagnostic(sky, repeat_sky),
                "registration_perturbation_scenarios": sensitivities,
            }
        )
    return {
        "schema_version": 1,
        "kind": "observed_hash_verified_repeat_measurements",
        "input_manifest_sha256": file_sha256(manifest_path),
        "selection_inputs": {p.name: file_sha256(p) for p in (csv_path, meta_path, summary_path)},
        "images": [
            {
                "product_filename": p["product_filename"],
                "sha256": p["sha256"],
                "readiness": v,
                "native_provenance": m,
            }
            for p, v, m in zip(products, verified, metadata, strict=True)
        ],
        "independence": independence,
        "aperture": aperture,
        "astrometry_control_match_radius_arcsec": 0.2,
        "astrometry_control_covered": match["covered_references"],
        "astrometry_control_matched": len(match["matches"]),
        "heldout_relative_astrometry": frame,
        "selected_proposal_count": len(rows),
        "repeat_statuses": dict(Counter(r["paired"]["status"] for r in rows)),
        "sources": rows,
        "not_established": [
            "redshift",
            "new astrophysical objects",
            "artifact identity",
            "population completeness",
            "independence of calibration systematics",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("selection_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = run(args.manifest, args.selection_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "repeat_statuses": payload["repeat_statuses"],
                "astrometry": payload["heldout_relative_astrometry"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
