"""Frozen classifier checks on quality-selected public stars and grouped galaxies.

No refitting occurs. Catalogue quality is independent of the tested classifier;
it is an operational stellar reference, not infallible source identity. Imaging
coverage, ambiguous matches, detector recovery and classifier retention stay
separate. Related observations are never independent object trials.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from astropy.coordinates import SkyCoord, search_around_sky
from astropy.io import fits
from astropy.wcs.utils import proj_plane_pixel_scales

from data_pipeline.reference_cohorts import build_report
from discovery.validation_metrics import injection_metrics

STAR_POLICY: dict[str, Any] = {
    "object_types": [1],
    "minimum_snr": 10.0,
    "maximum_abs_sharpness": 0.2,
    "maximum_crowding_magnitude": 0.1,
    "quality_flags": [0],
    "interpretation": (
        "Conservative prespecified operational stellar quality cull; not published universal cuts."
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_receipt(path: Path) -> dict:
    receipt = json.loads(path.with_name(path.name + ".provenance.json").read_text())
    if path.stat().st_size != receipt["bytes"] or sha256(path) != receipt["sha256"]:
        raise ValueError(f"Receipt mismatch for {path.name}")
    return receipt


def sky_groups(rows: list[dict], radius_arcsec: float = 0.3) -> tuple[list[str], dict]:
    """Conservative leakage groups by shared positive DR5 ID or spherical proximity.

    Connected components are split groups, not asserted unique galaxies. Close
    neighbours can be merged conservatively; changing the radius is reported.
    IDs are field-scoped, negative/sentinel IDs never imply common identity.
    """
    if not math.isfinite(radius_arcsec) or radius_arcsec <= 0:
        raise ValueError("Grouping radius must be positive")
    parent = list(range(len(rows)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        a, b = root(i), root(j)
        parent[max(a, b)] = min(a, b)

    id_seen: dict[tuple[str, int], int] = {}
    id_edges = 0
    for i, row in enumerate(rows):
        identifier = int(row["NIRCam_DR5_ID"])
        if identifier > 0:
            key = row["Field"], identifier
            if key in id_seen:
                union(i, id_seen[key])
                id_edges += 1
            else:
                id_seen[key] = i
    coords = SkyCoord(
        [float(r["RA_TARG"]) for r in rows], [float(r["Dec_TARG"]) for r in rows], unit="deg"
    )
    first, second, _, _ = search_around_sky(coords, coords, radius_arcsec / 3600 * coords.ra.unit)
    proximity_edges = 0
    for a, b in zip(first, second):
        if a < b and rows[a]["Field"] == rows[b]["Field"]:
            union(int(a), int(b))
            proximity_edges += 1
    components = defaultdict(list)
    for i in range(len(rows)):
        components[root(i)].append(i)
    result = [""] * len(rows)
    summary: Counter[int] = Counter()
    wide_components = 0
    for indices in components.values():
        keys = sorted(rows[i]["Unique_ID"] for i in indices)
        group_id = "dr4-sky-" + hashlib.sha256("\n".join(keys).encode()).hexdigest()[:16]
        for i in indices:
            result[i] = group_id
        summary[len(indices)] += 1
        if len(indices) > 1:
            c = coords[indices]
            diameter = max(float(c.separation(point).arcsec.max()) for point in c)
            wide_components += diameter > radius_arcsec
    return result, {
        "radius_arcsec": radius_arcsec,
        "observation_rows": len(rows),
        "conservative_sky_groups": len(components),
        "group_size_histogram": dict(sorted(summary.items())),
        "shared_positive_dr5_id_edges": id_edges,
        "spherical_proximity_edges": proximity_edges,
        "components_wider_than_radius": wide_components,
        "meaning": (
            "Leakage prevention components; close/blended neighbours can merge, "
            "so these are not certified unique galaxies."
        ),
    }


def grouped_jades(reference_csv: Path, radius_arcsec: float = 0.3) -> tuple[list[dict], dict]:
    base = build_report(reference_csv)
    with reference_csv.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    ids, grouping = sky_groups(rows, radius_arcsec)
    components = defaultdict(list)
    for row, group in zip(rows, ids):
        components[group].append(row)
    references = []
    counts: Counter[str] = Counter()
    conflicts = []
    for group, observations in sorted(components.items()):
        usable = [
            r
            for r in observations
            if r["z_Spec_flag"] in {"A", "B", "C"}
            and math.isfinite(float(r["z_Spec"]))
            and float(r["z_Spec"]) >= 0
        ]
        robust = [r for r in usable if r["z_Spec_flag"] in {"A", "B"}]
        preferred = robust or usable
        if not preferred:
            continue
        zs = [float(r["z_Spec"]) for r in preferred]
        if max(zs) - min(zs) > 0.1 * (1 + min(zs)):
            conflicts.append(group)
            continue
        representative = min(preferred, key=lambda r: (r["z_Spec_flag"], r["Unique_ID"]))
        z = float(representative["z_Spec"])
        cohort = (
            (
                "robust_high_z_ge_6"
                if z >= 6
                else "robust_controls_0_le_z_lt_3"
                if z < 3
                else "robust_other"
            )
            if robust
            else "secure_c_high_z_ge_6"
            if z >= 6
            else "c_other"
        )
        counts[cohort] += 1
        references.append(
            {
                "source_id": group,
                "sky_group_id": group,
                "field_id": representative["Field"],
                "ra_deg": float(representative["RA_TARG"]),
                "dec_deg": float(representative["Dec_TARG"]),
                "cohort": cohort,
                "z_spec": z,
                "observation_ids": sorted(r["Unique_ID"] for r in observations),
                "quality_flags": sorted({r["z_Spec_flag"] for r in observations}),
                "label_basis": (
                    "external JADES DR4 spectroscopic catalogue; "
                    "target position can differ from imaging centroid"
                ),
            }
        )
    return references, {
        "input_provenance": base["input_provenance"],
        "observation_cohort_counts": base["cohort_counts"],
        "grouping": grouping,
        "group_cohort_counts": dict(sorted(counts.items())),
        "redshift_conflict_groups": conflicts,
    }


def star_references(catalogue: Path, filter_name: str = "F444W") -> tuple[list[dict], dict]:
    receipt = verify_receipt(catalogue)
    with fits.open(catalogue, memmap=True) as hdul:
        table = hdul[1].data
        names = {name.upper(): name for name in table.names}
        needed = ["NUMBER", "RA", "DEC", "OBJECT_TYPE"] + [
            filter_name + suffix
            for suffix in ("_SNR", "_SHARP", "_CROWD", "_FLAG", "_VEGA", "_ERR")
        ]
        absent = [name for name in needed if name not in names]
        if absent:
            raise ValueError(f"Missing catalogue columns: {absent}")
        cols = {key: np.asarray(table[names[key]]) for key in needed}
        mask = np.isin(cols["OBJECT_TYPE"], STAR_POLICY["object_types"])
        for key in ["RA", "DEC"] + needed[4:]:
            mask &= np.isfinite(cols[key])
        mask &= (cols["RA"] >= 0) & (cols["RA"] < 360)
        mask &= (cols["DEC"] >= -90) & (cols["DEC"] <= 90)
        mask &= cols[filter_name + "_SNR"] >= STAR_POLICY["minimum_snr"]
        mask &= np.abs(cols[filter_name + "_SHARP"]) <= STAR_POLICY["maximum_abs_sharpness"]
        mask &= cols[filter_name + "_CROWD"] >= 0
        mask &= cols[filter_name + "_CROWD"] <= STAR_POLICY["maximum_crowding_magnitude"]
        mask &= np.isin(cols[filter_name + "_FLAG"], STAR_POLICY["quality_flags"])
        mask &= (cols[filter_name + "_VEGA"] < 90) & (cols[filter_name + "_ERR"] > 0)
        mask &= cols[filter_name + "_ERR"] < 9
        selected = np.flatnonzero(mask)
        refs = [
            {
                "source_id": "jwststars-m92-" + str(int(cols["NUMBER"][i])),
                "sky_group_id": "jwststars-m92-" + str(int(cols["NUMBER"][i])),
                "field_id": "M92",
                "ra_deg": float(cols["RA"][i]),
                "dec_deg": float(cols["DEC"][i]),
                "cohort": "quality_selected_stars",
                "reference_snr": float(cols[filter_name + "_SNR"][i]),
                "vega_magnitude": float(cols[filter_name + "_VEGA"][i]),
                "label_basis": (
                    "independent DOLPHOT type1 plus prespecified quality cull; "
                    "Gaia DR3-tied astrometry"
                ),
            }
            for i in selected
        ]
        summary = {
            "input_provenance": receipt,
            "raw_rows": len(table),
            "selected_rows": len(refs),
            "filter": filter_name,
            "quality_policy": STAR_POLICY,
            "object_type_counts": dict(sorted(Counter(map(int, cols["OBJECT_TYPE"])).items())),
        }
    return refs, summary


def match_sky(references: list[dict], detections: list[dict], radius_arcsec: float) -> list[dict]:
    """One-to-one spherical matching; all ambiguous neighbourhoods stay unknown."""
    if radius_arcsec <= 0 or not math.isfinite(radius_arcsec):
        raise ValueError("Match radius must be positive")
    result: list[dict[str, Any]] = [
        {"status": "not_detected", "detection_index": None, "separation_arcsec": None}
        for _ in references
    ]
    if not references or not detections:
        return result
    a = SkyCoord([r["ra_deg"] for r in references], [r["dec_deg"] for r in references], unit="deg")
    b = SkyCoord([r["ra_deg"] for r in detections], [r["dec_deg"] for r in detections], unit="deg")
    ia, ib, sep, _ = search_around_sky(a, b, radius_arcsec / 3600 * a.ra.unit)
    ref_degree, det_degree = Counter(ia), Counter(ib)
    for i, j, distance in zip(ia, ib, sep.arcsec):
        if ref_degree[i] != 1 or det_degree[j] != 1:
            result[i]["status"] = "ambiguous"
        else:
            result[i] = {
                "status": "matched",
                "detection_index": int(j),
                "separation_arcsec": float(distance),
            }
    return result


def real_metrics(rows: list[dict]) -> dict:
    """Use tested binomial accounting without calling actual references injections."""
    result = injection_metrics(rows)
    result["counts"]["references"] = result["counts"].pop("injected")
    result["scope"] = "quality-selected, covered, unambiguous external references"
    return result


def combine_epochs(images: list[dict]) -> dict:
    """Count stable sky groups once; never pool repeated exposures as objects."""
    grouped = defaultdict(list)
    for image in images:
        for row in image["outcomes"]:
            grouped[row["sky_group_id"]].append(row)
    patterns: Counter[str] = Counter()
    any_accepted = all_accepted = unknown = repeated = 0
    for rows in grouped.values():
        repeated += len(rows) > 1
        states = []
        for row in rows:
            if row["status"] == "ambiguous" or (row["recovered"] and row["rejected"] is None):
                state = "unknown"
            else:
                state = (
                    "accepted"
                    if row["rejected"] is False
                    else "rejected"
                    if row["rejected"] is True
                    else "not_detected"
                )
            states.append(state)
        patterns["|".join(states)] += 1
        any_accepted += "accepted" in states
        all_accepted += all(s == "accepted" for s in states)
        unknown += "unknown" in states
    return {
        "covered_sky_groups": len(grouped),
        "groups_covered_in_multiple_images": repeated,
        "accepted_in_at_least_one_covered_image": any_accepted,
        "accepted_in_every_covered_image": all_accepted,
        "groups_with_unknown_epoch": unknown,
        "ordered_epoch_state_counts": dict(patterns),
        "interpretation": (
            "Same visit/dither trials are dependent; no pooled-binomial object confidence interval."
        ),
    }


def compact_report(report: dict) -> dict:
    """Keep reviewable summaries and rejection cases; full trials are reproducible locally."""
    result = {k: v for k, v in report.items() if k != "images"}
    full = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
    result["full_trial_output"] = {
        "sha256": hashlib.sha256(full).hexdigest(),
        "bytes": len(full),
        "reproduce": "Supply --full-output to retain actual per-source trials outside git.",
    }
    other = defaultdict(list)
    for image in report.get("images", []):
        for row in image["outcomes"]:
            other[row["sky_group_id"]].append(
                {
                    "image": image["image_provenance"]["filename"],
                    "status": row["status"],
                    "artifact_score": row["artifact_score"],
                    "rejected": row["rejected"],
                }
            )
    images = []
    for image in report.get("images", []):
        compact = {k: v for k, v in image.items() if k != "outcomes"}
        compact["catalogue_matched_rejections"] = [
            {
                **row,
                "other_image_decisions": [
                    p
                    for p in other[row["sky_group_id"]]
                    if p["image"] != image["image_provenance"]["filename"]
                ],
            }
            for row in image["outcomes"]
            if row["rejected"] is True
        ]
        if any("vega_magnitude" in r for r in image["outcomes"]):
            compact["by_reference_vega_magnitude"] = {
                f"{lo}_le_vega_lt_{hi}": real_metrics(
                    [
                        r
                        for r in image["outcomes"]
                        if r["status"] != "ambiguous" and lo <= r["vega_magnitude"] < hi
                    ]
                )
                for lo, hi in [(0, 20), (20, 22), (22, 24), (24, 27), (27, 99)]
            }
        else:
            # Keep the small galaxy references individually, including nondetections.
            compact["outcomes"] = image["outcomes"]
        images.append(compact)
    result["images"] = images
    return result


def evaluate_image(
    references: list[dict],
    image: Path,
    model_path: Path,
    radius_arcsec: float = 0.2,
    threshold: float = 0.5,
) -> dict[str, Any]:
    """Rerun frozen detection/morphology on actual bytes, retaining unknown trials."""
    from discovery.artifact_characterization import BORDER_MARGIN_PIXELS, detect_with_morphology
    from discovery.artifact_classifier import LONGWAVE_PIXEL_SCALE, classify
    from tools.jwst.fits_loader import load_fits_bundle

    if not 0 <= threshold <= 1:
        raise ValueError("Threshold must lie in [0,1]")
    model_hash = sha256(model_path)
    receipt_path = image.with_name(image.name + ".provenance.json")
    if receipt_path.exists():
        verify_receipt(image)
    bundle = load_fits_bundle(str(image.resolve()))
    wcs = bundle["wcs"]
    if wcs is None or not wcs.has_celestial:
        raise ValueError("Image has no celestial WCS")
    scales = proj_plane_pixel_scales(wcs.celestial) * 3600
    if not np.all(np.abs(scales / LONGWAVE_PIXEL_SCALE - 1) < 0.05):
        raise ValueError(
            (
                "Frozen classifier expects native long-wave pixels; "
                "resampled images require separate calibration"
            )
        )
    hdr = bundle["primary_header"]
    if str(hdr.get("PROGRAM", "")).lstrip("0") == "1334" and int(hdr.get("EXPOSURE", -1)) == 3:
        raise ValueError("Excluded third M92 exposure with documented astrometric jitter")
    validity = np.array(bundle["validity_mask"], copy=True)
    with fits.open(image, memmap=False) as hdul:
        if "DQ" in hdul and hdul["DQ"].data.shape == validity.shape:
            # DO_NOT_USE and SATURATED are independently masked, no classifier-informed masking.
            validity &= (np.asarray(hdul["DQ"].data, dtype=np.uint32) & 3) == 0
    bundle["validity_mask"] = validity
    xx, yy = wcs.world_to_pixel_values(
        [r["ra_deg"] for r in references], [r["dec_deg"] for r in references]
    )
    height, width = validity.shape
    eligible = []
    outside = masked = 0
    for row, x, y in zip(references, xx, yy):
        if (
            not np.isfinite(x + y)
            or x < BORDER_MARGIN_PIXELS
            or y < BORDER_MARGIN_PIXELS
            or x >= width - BORDER_MARGIN_PIXELS
            or y >= height - BORDER_MARGIN_PIXELS
        ):
            outside += 1
            continue
        ix, iy = int(round(x)), int(round(y))
        patch = validity[iy - 3 : iy + 4, ix - 3 : ix + 4]
        if np.mean(patch) < 0.9:
            masked += 1
            continue
        eligible.append(row)
    detections = detect_with_morphology(bundle)
    scores = classify(json.loads(model_path.read_text()), detections, bundle["filter"])
    sky = []
    for source in detections:
        ra, dec = wcs.pixel_to_world_values(source["x"], source["y"])
        sky.append({"ra_deg": float(ra), "dec_deg": float(dec)})
    matches = match_sky(eligible, sky, radius_arcsec)
    outcomes = []
    for reference, match in zip(eligible, matches):
        score = scores[match["detection_index"]] if match["status"] == "matched" else None
        outcomes.append(
            {
                **reference,
                **match,
                "artifact_score": score,
                "recovered": match["status"] == "matched",
                "rejected": None if score is None else score >= threshold,
            }
        )
    measured = [r for r in outcomes if r["status"] != "ambiguous"]
    ambiguity = sum(r["status"] == "ambiguous" for r in outcomes)
    accepted = sum(r["rejected"] is False for r in outcomes)
    unknown = ambiguity + sum(r["recovered"] and r["rejected"] is None for r in outcomes)
    separations = [r["separation_arcsec"] for r in measured if r["recovered"]]
    return {
        "image_provenance": {
            "filename": image.name,
            "sha256": sha256(image),
            "bytes": image.stat().st_size,
            "filter": bundle["filter"],
            "pixel_scales_arcsec": scales.tolist(),
            "visit_id": str(hdr.get("VISIT_ID", image.name[:14])),
            "CAL_VER": hdr.get("CAL_VER"),
            "CRDS_CTX": hdr.get("CRDS_CTX"),
        },
        "model_sha256": model_hash,
        "threshold": threshold,
        "matching_radius_arcsec": radius_arcsec,
        "counts": {
            "references_supplied": len(references),
            "outside_or_border": outside,
            "masked_reference_positions": masked,
            "covered_quality_references": len(eligible),
            "detections_in_image": len(detections),
            "ambiguous_references": ambiguity,
        },
        "unambiguous_metrics": real_metrics(measured),
        "full_covered_reference_recovery_bounds": {
            "confirmed_accepted": accepted,
            "ambiguous_or_unclassified": unknown,
            "denominator": len(eligible),
            "lower": accepted / len(eligible) if eligible else None,
            "upper": (accepted + unknown) / len(eligible) if eligible else None,
        },
        "astrometric_match_residual_arcsec": {
            "median": float(np.median(separations)) if separations else None,
            "p95": float(np.percentile(separations, 95)) if separations else None,
            "scope": (
                "Matched-source residuals, conditional on radius; "
                "not an external absolute-frame certificate"
            ),
        },
        "by_cohort": {
            c: real_metrics([r for r in measured if r["cohort"] == c])
            for c in sorted({r["cohort"] for r in measured})
        },
        "roc_auc": {
            "status": "not_estimable",
            "value": None,
            "reason": "External real sources provide only the real class",
        },
        "outcomes": outcomes,
        "limits": [
            (
                "DOLPHOT reference photometry is full-stack; "
                "individual-exposure recovery need not match full-stack SNR."
            ),
            "Close or blended matches are unknown, never silently counted as failed or passed.",
            (
                "Per-image intervals assume independent sources and "
                "omit crowding/PSF/background systematics."
            ),
            (
                "Repeat exposures of a source are grouped; "
                "these rows are not independent sky-object trials."
            ),
            (
                "Frozen training provenance is incomplete; "
                "metadata alone cannot certify full independent-validation status."
            ),
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("groups", "stars", "galaxies"))
    parser.add_argument("reference", type=Path)
    parser.add_argument("--image", type=Path, action="append", default=[])
    parser.add_argument(
        "--model", type=Path, default=Path("research_output/artifact_classifier.json")
    )
    parser.add_argument("--group-radius", type=float, default=0.3)
    parser.add_argument("--match-radius", type=float, default=0.2)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--full-output",
        type=Path,
        help="Write actual per-reference trials outside git as well as the compact report",
    )
    args = parser.parse_args()
    if args.mode == "stars":
        references, report = star_references(args.reference)
    else:
        references, report = grouped_jades(args.reference, args.group_radius)
        references = [
            r
            for r in references
            if r["cohort"]
            in {"robust_high_z_ge_6", "robust_controls_0_le_z_lt_3", "secure_c_high_z_ge_6"}
        ]
    if args.mode != "groups":
        if not args.image:
            parser.error("Actual image paths required; no image means no recovery experiment")
        report["images"] = [
            evaluate_image(references, image, args.model, args.match_radius) for image in args.image
        ]
        report["grouped_epoch_summary"] = combine_epochs(report["images"])
    report["schema_version"] = 1
    full = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.full_output:
        args.full_output.parent.mkdir(parents=True, exist_ok=True)
        args.full_output.write_text(full)
    if "images" in report:
        report = compact_report(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
