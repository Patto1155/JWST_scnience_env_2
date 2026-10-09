"""Hash-verified real-image detection, calibrated photometry and dropout audit.

No database registration, API server, LLM key or dummy image is required.
Input: {"images": [{"path": ..., "sha256": ..., "target": ...,
"filter": "F444W", "kind": "science_image"}, ...]}.
Relative image paths are resolved against the manifest directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
from astropy.wcs.utils import proj_plane_pixel_scales

from discovery.audit_candidates import audit_candidate, summarize
from discovery.build_universe_table import (
    APERTURE_RADII,
    _build_target_dataset_map,
    _group_entries_by_target,
    build_universe_table,
)
from tools.jwst.common_coverage import joint_valid_coverage
from tools.jwst.dropout import dropout_upper_limit_ratio, physical_flux
from tools.jwst.fits_loader import load_fits_bundle
from tools.jwst.flux_calibration import celestial_wcs
from tools.jwst.photometry import extract_photometry
from tools.jwst.source_detection import detect_sources

REQUIRED_FILTERS = ("F090W", "F200W", "F444W")
STATUS_FIELDS = ("calibration_status", "measurement_status", "background_status")


def write_selection_measurements(proposals: list[dict[str, Any]], output_dir: Path) -> None:
    """Save compact round-trippable r3 measurements sufficient for a fresh audit."""
    statuses = sorted(
        {
            tuple(row["photometry_by_filter"][band]["3"][key] for key in STATUS_FIELDS)
            for row in proposals
            for band in REQUIRED_FILTERS
        }
    )
    status_ids = {status: number for number, status in enumerate(statuses)}
    radius_by_filter = {}
    if proposals:
        radius_by_filter = {
            band: proposals[0]["photometry_by_filter"][band]["3"]["aperture_radius_arcsec"]
            for band in REQUIRED_FILTERS
        }
    fields = ["source_id", "target", "ra", "dec"] + [
        band + "_" + quantity
        for band in REQUIRED_FILTERS
        for quantity in ("flux", "error", "coverage", "status")
    ]
    with (output_dir / "selection_measurements.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for proposal in proposals:
            row = {
                "source_id": proposal["source_id"],
                "target": proposal["target"],
                "ra": proposal["sky_center"]["ra"],
                "dec": proposal["sky_center"]["dec"],
            }
            for band in REQUIRED_FILTERS:
                measurement = proposal["photometry_by_filter"][band]["3"]
                if measurement["aperture_radius_arcsec"] != radius_by_filter[band]:
                    raise ValueError("Compact catalog requires constant per-filter aperture radius")
                row.update(
                    {
                        band + "_flux": measurement["background_subtracted_flux_jy"],
                        band + "_error": measurement["flux_error_jy"],
                        band + "_coverage": measurement["coverage_fraction"],
                        band + "_status": status_ids[
                            tuple(measurement[key] for key in STATUS_FIELDS)
                        ],
                    }
                )
            writer.writerow(row)
    metadata = {
        "schema_version": 1,
        "flux_unit": "Jy",
        "aperture_key": "3",
        "status_fields": list(STATUS_FIELDS),
        "status_values": statuses,
        "aperture_radius_arcsec_by_filter": radius_by_filter,
        "empty_numeric_field": "unavailable (None), never zero",
        "quantity_operator": "pixel-centre angular aperture minus mean native annulus",
        "annulus_radii_arcsec": {
            "inner": proposals[0]["photometry_by_filter"]["F444W"]["3"][
                "background_annulus_inner_radius_arcsec"
            ]
            if proposals
            else None,
            "outer": proposals[0]["photometry_by_filter"]["F444W"]["3"][
                "background_annulus_outer_radius_arcsec"
            ]
            if proposals
            else None,
        },
    }
    (output_dir / "selection_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")


def load_selection_measurements(csv_path: Path, metadata_path: Path) -> list[dict[str, Any]]:
    """Reconstruct audit inputs from the compact saved measurement artifact."""
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    proposals = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            photometry = {}
            for band in REQUIRED_FILTERS:
                codes = metadata["status_values"][int(row[band + "_status"])]
                measurement = dict(zip(metadata["status_fields"], codes, strict=True))
                measurement.update(
                    background_subtracted_flux_jy=float(row[band + "_flux"])
                    if row[band + "_flux"]
                    else None,
                    flux_error_jy=float(row[band + "_error"]) if row[band + "_error"] else None,
                    coverage_fraction=float(row[band + "_coverage"]),
                    aperture_radius_arcsec=metadata["aperture_radius_arcsec_by_filter"][band],
                )
                photometry[band] = {"3": measurement}
            proposals.append(
                {
                    "source_id": int(row["source_id"]),
                    "target": row["target"],
                    "sky_center": {"ra": float(row["ra"]), "dec": float(row["dec"])},
                    "photometry_by_filter": photometry,
                }
            )
    return proposals


def sha256_file(path: Path) -> str:
    """Hash bytes without holding a science mosaic in memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_image_manifest(manifest: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fail closed on missing science data, missing digests and metadata mismatch."""
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    rows = payload.get("images")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Manifest needs a nonempty images list")
    verified, blocked = [], []
    for raw in rows:
        row = dict(raw)
        raw_path = row.get("path")
        reason = None
        if row.get("kind") != "science_image":
            reason = "not_declared_science_image"
        elif not isinstance(raw_path, str) or not raw_path:
            reason = "missing_path"
        elif not row.get("target") or not row.get("filter"):
            reason = "missing_target_or_filter"
        else:
            path = Path(raw_path).expanduser()
            if not path.is_absolute():
                path = manifest.parent / path
            path = path.resolve()
            if not path.is_file():
                reason = "original_image_not_provisioned"
            elif not re.fullmatch(r"[0-9a-fA-F]{64}", str(row.get("sha256") or "")):
                reason = "missing_valid_sha256"
            elif sha256_file(path) != row["sha256"].lower():
                reason = "sha256_mismatch"
            else:
                try:
                    bundle = load_fits_bundle(str(path))
                    if np.asarray(bundle["sci"]).ndim != 2:
                        reason = "not_two_dimensional_image"
                    elif celestial_wcs(bundle) is None:
                        reason = "missing_celestial_wcs"
                    elif str(bundle.get("filter") or "").upper() != str(row["filter"]).upper():
                        reason = "filter_header_mismatch"
                    elif (
                        str(bundle["primary_header"].get("DATAMODL") or "").lower().find("psf") >= 0
                    ):
                        reason = "psf_template_not_science_image"
                    else:
                        verified.append({**row, "resolved_path": str(path)})
                except (OSError, ValueError, TypeError) as exc:
                    reason = f"fits_unreadable:{type(exc).__name__}"
        if reason:
            blocked.append({"path": raw_path, "filter": row.get("filter"), "reason": reason})
    return verified, blocked


def _measure_sources(
    target: str,
    dataset_map: dict[str, str],
    output_dir: Path,
    *,
    max_sources: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Use the existing detector and physical aperture implementation, no classifier."""
    reference_path = dataset_map["F444W"]
    bundles = {name: load_fits_bundle(path) for name, path in dataset_map.items()}
    reference_wcs = celestial_wcs(bundles["F444W"])
    scale = float(np.sqrt(np.prod(proj_plane_pixel_scales(reference_wcs))) * 3600.0)
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("Reference image has invalid angular pixel scale")
    prefix = re.sub(r"[^A-Za-z0-9._-]+", "_", target)
    # The legacy detector cache uses path/config identity. Key this experiment's
    # prefix to verified bytes so reusing an output directory cannot reuse a
    # catalog from different science pixels at the same filesystem path.
    prefix += "_" + sha256_file(Path(reference_path))[:16]
    detected = detect_sources(
        reference_path,
        threshold_sigma=3.0,
        min_pixels=9,
        border_margin=16,
        output_dir=str(output_dir / "source_catalogs"),
        output_prefix=prefix,
    )
    catalog = json.loads(Path(detected["catalog_path"]).read_text(encoding="utf-8"))
    sources = catalog["sources"]
    selected = sources[:max_sources] if max_sources else sources
    proposals = []
    for source in selected:
        ra, dec = source.get("ra"), source.get("dec")
        if ra is None or dec is None:
            continue
        photometry = {}
        for band in REQUIRED_FILTERS:
            bundle = bundles[band]
            photometry[band] = {
                str(radius): extract_photometry(
                    bundle,
                    ra_deg=ra,
                    dec_deg=dec,
                    aperture_radius_arcsec=radius * scale,
                    background_annulus_inner_radius_arcsec=6.0 * scale,
                    background_annulus_outer_radius_arcsec=10.0 * scale,
                    strict_data=True,
                )
                for radius in APERTURE_RADII
            }
        red, blue = photometry["F444W"]["3"], photometry["F090W"]["3"]
        proposals.append(
            {
                "target": target,
                "source_id": source["source_id"],
                "screen_identity": "exploratory_proposal",
                "sky_center": {"ra": ra, "dec": dec},
                "position": {"x": source["x"], "y": source["y"]},
                "reference_dataset": reference_path,
                "f444_dataset": reference_path,
                "f090_dataset": dataset_map["F090W"],
                "f200_dataset": dataset_map["F200W"],
                "photometry_by_filter": photometry,
                "f444_flux_jy": physical_flux(red),
                "ratio_f090_f444": dropout_upper_limit_ratio(blue, red),
                "selection_ratio_kind": "blue_2sigma_upper_limit_over_red_flux",
                "flux_unit": "Jy",
                "classifier_applied": False,
            }
        )
    return proposals, {
        "target": target,
        "detected_source_count": detected["source_count"],
        "measured_source_count": len(proposals),
        "source_limit": max_sources or None,
        "measurement_subset": "brightest_segment_flux" if max_sources else "all_detections",
        "reference_aperture_radii_arcsec": [radius * scale for radius in APERTURE_RADII],
        "detector_threshold_sigma": 3.0,
        "detector_min_pixels": 9,
        "coverage": joint_valid_coverage(
            bundles["F444W"], {band: bundles[band] for band in ("F090W", "F200W")}
        ),
    }


def run_rerun(manifest: Path, output_dir: Path, *, max_sources: int = 0) -> dict[str, Any]:
    """Create new artifacts without replacing any historical catalog."""
    if max_sources < 0:
        raise ValueError("max_sources cannot be negative")
    manifest_digest = sha256_file(manifest)
    verified, blocked = verify_image_manifest(manifest)
    if sha256_file(manifest) != manifest_digest:
        blocked.append({"reason": "manifest_changed_during_verification"})
    filters_by_target: dict[str, set[str]] = {}
    for row in verified:
        filters_by_target.setdefault(row["target"], set()).add(str(row["filter"]).upper())
    for target, filters in filters_by_target.items():
        for band in REQUIRED_FILTERS:
            if band not in filters:
                blocked.append(
                    {"target": target, "filter": band, "reason": "required_band_unavailable"}
                )
    result: dict[str, Any] = {
        "schema_version": 1,
        "manifest_sha256": manifest_digest,
        "status": "blocked" if blocked else "executed",
        "verified_image_count": len(verified),
        "blockers": blocked,
        "detection_count": None,
        "proposal_count": None,
        "dropout_screen_survivors": None,
        "interpretation": "Dropout-screen survivors are not redshift confirmations or discoveries",
        "software_versions": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "astropy", "photutils", "scipy", "scikit-image")
        },
        "image_receipts": [
            {
                key: row.get(key)
                for key in (
                    "path",
                    "sha256",
                    "filter",
                    "target",
                    "product_filename",
                    "product_kind",
                )
            }
            for row in verified
        ],
        "limitations": [
            "Matched angular apertures remain PSF-uncorrected",
            "ERR/noise estimates remain diagonal without empirical covariance correction",
            "No completeness, effective volume, redshift model or population abundance inferred",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    if not blocked:
        datasets = [
            SimpleNamespace(
                name=row["resolved_path"],
                meta_data={"target": row["target"], "filter": row["filter"]},
            )
            for row in verified
        ]
        entries = build_universe_table(datasets)
        proposals, targets = [], []
        for target, grouped in _group_entries_by_target(entries).items():
            dataset_map, overlap = _build_target_dataset_map(grouped)
            if any(band not in dataset_map for band in REQUIRED_FILTERS):
                blocked.append({"target": target, "reason": "no_overlapping_required_band_pairing"})
                continue
            measured, target_summary = _measure_sources(
                target,
                dataset_map,
                output_dir,
                max_sources=max_sources,
            )
            target_summary["selected_datasets"] = dataset_map
            target_summary["individual_footprint_overlap"] = overlap
            proposals.extend(measured)
            targets.append(target_summary)
        audits = [audit_candidate(proposal) for proposal in proposals]
        survivors = [
            proposal
            for proposal, audit in zip(proposals, audits, strict=True)
            if audit["audit_verdict"] == "survives"
        ]
        for filename, payload in (
            ("universe_table_summary.json", entries),
            ("exploratory_proposals.json", proposals),
            ("candidate_audit.json", {"summary": summarize(audits), "candidates": audits}),
            ("dropout_screen_survivors.json", survivors),
        ):
            (output_dir / filename).write_text(
                json.dumps(payload, indent=2, allow_nan=False) + "\n"
            )
        write_selection_measurements(proposals, output_dir)
        result.update(
            status="partial_blocked" if blocked else "executed",
            blockers=blocked,
            detection_count=sum(item["detected_source_count"] for item in targets),
            proposal_count=len(proposals),
            dropout_screen_survivors=len(survivors),
            audit_summary=summarize(audits),
            targets=targets,
        )
    (output_dir / "rerun_summary.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    lines = [
        "# Original-image calibrated photometry rerun",
        "",
        f"Execution status: **{result['status']}**. Input manifest SHA256: `{manifest_digest}`.",
        "",
        "Historical catalogs are preserved. Input bytes are verified before analysis.",
        "The existing Universe Table, WCS anchor selection, source detector, calibrated",
        "matched-angular-aperture photometry and physical candidate audit are used.",
        "",
    ]
    if result["status"] == "blocked":
        lines += ["No detection or survivor count was measured; unavailable results are null.", ""]
    else:
        audit = result["audit_summary"]
        lines += [
            f"- Detections: {result['detection_count']}",
            f"- Exploratory measured proposals: {result['proposal_count']}",
            f"- Untestable proposals: {audit['untestable']}",
            f"- Valid proposals failing the configured dropout cut: {audit['falsified']}",
            f"- Proposals surviving the dropout screen: {audit['survivors']}",
            "",
            "The morphology classifier is frozen and is not applied to this science selection.",
            "Selection requires all three covered calibrated bands, matched angular apertures,",
            "F444W SNR >= 5, F090W SNR <= 2, and (max(blue,0)+2 sigma)/red < 0.05.",
            "",
        ]
        for target in result["targets"]:
            area = target["coverage"]["joint_valid_area_arcmin2"]
            lines += [
                f"{target['target']}: joint valid pixel-centre area **{area:.6f} arcmin²**.",
                "This is not an aperture-safe or completeness-weighted survey area.",
                "",
            ]
    if blocked:
        lines += ["Blockers: " + ", ".join(str(row["reason"]) for row in blocked), ""]
    lines += [
        "Matched apertures retain filter-dependent PSFs and diagonal uncertainties.",
        "Empirical correlated-noise and aperture corrections must be assessed separately.",
        "Single-exposure i2d images remain single exposures; full spatial extent does not",
        "mean an observation-level deep mosaic or independent repeat confirmation.",
        "No redshift, galaxy abundance, contamination fraction or discovery is inferred.",
        "",
    ]
    (output_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--max-sources",
        type=int,
        default=0,
        help="0 measures every detection; >0 explicitly limits brightest-source subset",
    )
    args = parser.parse_args()
    result = run_rerun(args.manifest, args.output_dir, max_sources=args.max_sources)
    print(
        json.dumps(
            {key: result[key] for key in ("status", "proposal_count", "dropout_screen_survivors")}
        )
    )
    return 0 if result["status"] == "executed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
