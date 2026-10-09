"""Same-sky F444W dither tests of the frozen PR16 seven-proposal screen.

Persistence is an operational measurement, not detector/astrophysical identity.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from data_pipeline.original_images import file_sha256, verify_image
from discovery.image_photometry_rerun import load_selection_measurements
from discovery.multi_epoch import find_repeat_pairs
from tools.jwst.dropout import physical_flux
from tools.jwst.fits_loader import load_fits_bundle
from tools.jwst.photometry import extract_photometry


def classify_pair(reference: dict, comparison: dict, *, error_scale: float = 1) -> dict:
    """Require covered calibrated measurements and adequate difference sensitivity."""
    if not np.isfinite(error_scale) or error_scale <= 0:
        raise ValueError("error_scale must be positive and finite")
    fluxes, errors = [], []
    for measurement in (reference, comparison):
        if (
            measurement.get("measurement_status") != "measured"
            or measurement.get("background_status") != "measured"
            or not 0.9 <= float(measurement.get("coverage_fraction") or 0) <= 1
        ):
            return {"status": "untestable_coverage_or_measurement"}
        flux = physical_flux(measurement)
        error = physical_flux(measurement, "flux_error_jy")
        if flux is None or error is None or error <= 0:
            return {"status": "untestable_calibration_or_error"}
        fluxes.append(flux)
        errors.append(error * error_scale)
    snr = np.asarray(fluxes) / errors
    discrepancy = float(abs(fluxes[1] - fluxes[0]) / np.hypot(*errors))
    if min(snr) >= 3:
        status = "persistent_detection"
    elif max(snr) >= 3 and discrepancy >= 3:
        status = "single_epoch_only"
    else:
        status = "inconclusive_depth"
    return {
        "status": status,
        "error_scale": error_scale,
        "reference_snr": float(snr[0]),
        "comparison_snr": float(snr[1]),
        "absolute_flux_difference_sigma": discrepancy,
        "comparison_reference_flux_ratio": fluxes[1] / fluxes[0] if fluxes[0] > 0 else None,
        "comparison_3sigma_limit_jy": max(fluxes[1], 0) + 3 * errors[1],
    }


def _measure(bundle: dict, sky: dict, aperture: dict) -> dict:
    return extract_photometry(
        image_data=bundle,
        ra_deg=sky["ra"],
        dec_deg=sky["dec"],
        aperture_radius_arcsec=aperture["aperture_radius_arcsec"],
        background_annulus_inner_radius_arcsec=aperture["background_annulus_inner_radius_arcsec"],
        background_annulus_outer_radius_arcsec=aperture["background_annulus_outer_radius_arcsec"],
    )


def _controls(
    reference: dict, comparisons: list[tuple[dict, dict]], astrometry: dict, aperture: dict
) -> list[dict]:
    """Independent JADES-identified reference detections check depth/registration."""
    reference_name = Path(reference["file_path"]).name
    image = next(row for row in astrometry["images"] if row["product_filename"] == reference_name)
    controls = []
    for product, bundle in comparisons:
        rows = []
        reference_bright_statuses = []
        for match in image["external_astrometry"]["matches"]:
            ra, dec = reference["wcs"].pixel_to_world_values(match["x"], match["y"])
            sky = {"ra": float(ra), "dec": float(dec)}
            original, repeat = _measure(reference, sky, aperture), _measure(bundle, sky, aperture)
            paired = classify_pair(original, repeat)
            original_flux = physical_flux(original)
            original_error = physical_flux(original, "flux_error_jy")
            if (
                original_flux is not None
                and original_error
                and original_flux / original_error >= 10
            ):
                reference_bright_statuses.append(paired["status"])
            if paired.get("reference_snr", 0) < 10 or paired.get("comparison_snr", 0) < 10:
                continue
            rows.append({"source_id": match["source_id"], **paired})
        ratios = [row["comparison_reference_flux_ratio"] for row in rows]
        interval = None
        if len(ratios) >= 5:
            values = np.asarray(ratios)
            rng = np.random.default_rng(20261009)
            medians = np.median(values[rng.integers(0, len(values), (2000, len(values)))], axis=1)
            interval = np.percentile(medians, [2.5, 97.5]).tolist()
        controls.append(
            {
                "product_filename": product["product_filename"],
                "bright_covered_control_count": len(rows),
                "reference_bright_control_count": len(reference_bright_statuses),
                "reference_bright_repeat_statuses": dict(Counter(reference_bright_statuses)),
                "flux_ratio_median": float(np.median(ratios)) if ratios else None,
                "flux_ratio_median_bootstrap95": interval,
                "flux_ratio_p16_p84": np.percentile(ratios, [16, 84]).tolist() if ratios else None,
                "controls": rows,
                "selection": "JADES-identified detections with >=10 diagonal SNR in both images",
            }
        )
    return controls


def run(
    manifest_path: Path,
    survivors_path: Path,
    astrometry_path: Path,
    additional_source_ids: list[int] | None = None,
) -> dict[str, Any]:
    payload = json.loads(manifest_path.read_text())
    products = []
    bundles = {}
    for row in payload["images"]:
        verify_image(row["path"], row)
        if row["target"] == "GS-MEDIUM-HST" and row["filter"] == "F444W":
            products.append(row)
            bundles[row["product_filename"]] = load_fits_bundle(row["path"])
    survivors = json.loads(survivors_path.read_text())
    frozen_ids = {source["source_id"] for source in survivors}
    additional_inputs = {}
    if additional_source_ids:
        catalog_path = survivors_path.parent / "selection_measurements.csv"
        metadata_path = survivors_path.parent / "selection_metadata.json"
        catalog = load_selection_measurements(catalog_path, metadata_path)
        metadata = json.loads(metadata_path.read_text())
        requested = set(additional_source_ids) - frozen_ids
        selected = [source for source in catalog if source["source_id"] in requested]
        if {source["source_id"] for source in selected} != requested:
            raise ValueError("additional source identifier missing from frozen proposal catalog")
        for source in selected:
            source["reference_dataset"] = survivors[0]["reference_dataset"]
            aperture = source["photometry_by_filter"]["F444W"]["3"]
            aperture["background_annulus_inner_radius_arcsec"] = metadata["annulus_radii_arcsec"][
                "inner"
            ]
            aperture["background_annulus_outer_radius_arcsec"] = metadata["annulus_radii_arcsec"][
                "outer"
            ]
        survivors.extend(selected)
        additional_inputs = {
            "requested_source_ids": additional_source_ids,
            "compact_catalog_sha256": file_sha256(catalog_path),
            "compact_metadata_sha256": file_sha256(metadata_path),
        }
    source_rows = []
    for source in survivors:
        reference_name = Path(source["reference_dataset"]).name
        reference = bundles[reference_name]
        aperture = source["photometry_by_filter"]["F444W"]["3"]
        measurements = []
        for product in products:
            bundle = bundles[product["product_filename"]]
            measured = _measure(bundle, source["sky_center"], aperture)
            baseline = (
                abs(
                    float(bundle["primary_header"]["EXPMID"])
                    - float(reference["primary_header"]["EXPMID"])
                )
                * 24
            )
            measurements.append(
                {
                    "product_filename": product["product_filename"],
                    "sha256": product["sha256"],
                    "baseline_hours": baseline,
                    "exposure_time_s": bundle["primary_header"].get("EFFEXPTM"),
                    "measurement": measured,
                }
            )
        replay = next(
            m["measurement"] for m in measurements if m["product_filename"] == reference_name
        )
        replay_ok = np.isclose(physical_flux(replay), physical_flux(aperture), rtol=1e-12, atol=0)
        if not replay_ok:
            raise ValueError("frozen source reference measurement did not reproduce")
        comparisons = []
        for measured in measurements:
            if measured["product_filename"] == reference_name:
                continue
            comparisons.append(
                {
                    "product_filename": measured["product_filename"],
                    "error_scale_sensitivity": [
                        classify_pair(replay, measured["measurement"], error_scale=scale)
                        for scale in (1, 3, 10)
                    ],
                }
            )
        testable = [
            c["error_scale_sensitivity"][0]["status"]
            for c in comparisons
            if not c["error_scale_sensitivity"][0]["status"].startswith("untestable")
        ]
        status = (
            "persistent_in_repeat"
            if "persistent_detection" in testable
            else "not_persistent_at_measured_depth"
            if testable and all(s == "single_epoch_only" for s in testable)
            else "inconclusive"
        )
        source_rows.append(
            {
                "source_id": source["source_id"],
                "selection_origin": "frozen_uncorrected_dropout_screen"
                if source["source_id"] in frozen_ids
                else "additional_conditional_point_source_proposal",
                "sky_center": source["sky_center"],
                "status": status,
                "reference_replay_verified": bool(replay_ok),
                "measurements": measurements,
                "comparisons": comparisons,
            }
        )
    rows = [
        SimpleNamespace(name=r["path"], meta_data={"target": r["target"], "filter": r["filter"]})
        for r in products
    ]
    pairs = find_repeat_pairs(rows)
    for pair in pairs:
        pair["epoch_a"], pair["epoch_b"] = Path(pair["epoch_a"]).name, Path(pair["epoch_b"]).name
    first = survivors[0]
    reference_name = Path(first["reference_dataset"]).name
    comparisons = [
        (r, bundles[r["product_filename"]])
        for r in products
        if r["product_filename"] != reference_name
    ]
    controls = _controls(
        bundles[reference_name],
        comparisons,
        json.loads(astrometry_path.read_text()),
        first["photometry_by_filter"]["F444W"]["3"],
    )
    return {
        "schema_version": 1,
        "manifest_sha256": file_sha256(manifest_path),
        "frozen_survivors_sha256": file_sha256(survivors_path),
        "external_astrometry_sha256": file_sha256(astrometry_path),
        "source_count": len(source_rows),
        "frozen_screen_source_count": len(frozen_ids),
        "additional_inputs": additional_inputs,
        "summary_by_selection_origin": {
            origin: dict(
                Counter(row["status"] for row in source_rows if row["selection_origin"] == origin)
            )
            for origin in sorted({row["selection_origin"] for row in source_rows})
        },
        "summary": dict(Counter(r["status"] for r in source_rows)),
        "f444w_repeat_pairs": pairs,
        "independent_source_controls": controls,
        "sources": source_rows,
        "limitations": [
            "Single-epoch-only does not establish detector-artifact identity or exclude variability.",
            "Diagonal errors omit covariance/PSF/calibration effects; 3x/10x are sensitivity assumptions.",
            "No redshift, abundance, new-galaxy identity or population-purity estimate established.",
            "Partial apertures are untestable, never zero-flux nondetections.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--survivors",
        type=Path,
        default=Path("research_output/original_image_rerun/dropout_screen_survivors.json"),
    )
    parser.add_argument(
        "--astrometry", type=Path, default=Path("research_output/original_image_astrometry.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("research_output/f444w_repeat_screen.json")
    )
    parser.add_argument(
        "--additional-source-ids",
        type=int,
        nargs="+",
        help="Explicit conditional entrants from the frozen compact proposal catalog",
    )
    args = parser.parse_args()
    result = run(args.manifest, args.survivors, args.astrometry, args.additional_source_ids)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result["summary"]))
    for control in result["independent_source_controls"]:
        print(
            control["product_filename"],
            control["bright_covered_control_count"],
            control["flux_ratio_median"],
        )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
