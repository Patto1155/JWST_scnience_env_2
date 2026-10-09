"""Repeat-exposure vetting for JWST candidates.

A source detected in only one independent exposure requires follow-up: detector
artifacts, unequal depth, genuine variability, and moving objects can all
produce apparent non-persistence. Single-exposure Stage-2b
products carry no cross-dither rejection, so this check is the difference
between a candidate catalog and a list of transient detector events.

The module does three things:

1. ``find_repeat_pairs`` - discover which same-target, same-filter exposures
   actually share sky, using WCS footprints rather than file names, and record
   the time baseline between them.
2. ``veto_candidate`` - measure one candidate at the same sky position in both
   exposures of a pair and decide whether it persists.
3. A CLI that applies the veto to ``highz_candidates.json`` and writes
   ``research_output/multi_epoch_veto.json``.

The time baseline matters for interpretation and is reported, not assumed. A
few hours can identify suspect detector events, but baseline alone never proves
an instrumental origin or excludes genuine variability. Depth and calibration
must be accounted for before making a transient or microlensing claim.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core_api.db import SessionLocal
from core_api.models.datasets import Dataset
from tools.jwst.fits_loader import load_fits_bundle
from tools.jwst.footprints import (
    MIN_USEFUL_OVERLAP,
    overlap_fraction,
    sky_to_pixel,
)
from tools.jwst.photometry import extract_photometry
from tools.jwst.dropout import physical_flux
from astropy.wcs.utils import proj_plane_pixel_scales

RESEARCH_DIR = Path("research_output")
DEFAULT_CANDIDATES = RESEARCH_DIR / "highz_candidates.json"
DEFAULT_OUTPUT = RESEARCH_DIR / "multi_epoch_veto.json"
DEFAULT_PAIRS_OUTPUT = RESEARCH_DIR / "repeat_exposure_pairs.json"

APERTURE_RADIUS = 3.0
BACKGROUND_INNER_RADIUS = 6.0
BACKGROUND_OUTER_RADIUS = 10.0

# A source is required to reappear at this significance in the second exposure.
PERSISTENCE_SNR = 3.0

# Below this the two epochs share too little sky to be worth pairing.
MIN_PAIR_OVERLAP = MIN_USEFUL_OVERLAP

# Hours below which a pair rejects detector artifacts but says nothing about
# astrophysical variability.
ARTIFACT_ONLY_BASELINE_HOURS = 72.0


def _product_rank(dataset_name: str) -> int:
    """Rank calibration product flavors, preferring resampled i2d mosaics."""
    name = dataset_name.lower()
    if "i2d" in name:
        return 3
    if "_crf" in name:
        return 2
    if "_cal" in name:
        return 1
    return 0


def _exposure_key(dataset_name: str) -> str:
    """Strip the product-flavor suffix so cal/i2d/crf collapse to one exposure.

    ``cal``, ``i2d`` and ``crf`` renderings of one exposure are not independent
    looks at the sky. Treating them as separate epochs would let an artifact
    veto itself.
    """
    name = str(dataset_name)
    for marker in ("_i2d", "_cal", "_crf"):
        index = name.rfind(marker)
        if index != -1:
            name = name[:index]
    # Trailing association ids such as ``_o026`` are part of the crf naming.
    parts = name.rsplit("_", 1)
    if len(parts) == 2 and parts[1].startswith("o") and parts[1][1:].isdigit():
        name = parts[0]
    return name


def _observation_time(bundle: Dict[str, Any]) -> Optional[float]:
    """Return the exposure mid-time in MJD from the FITS header, if present."""
    header = dict(bundle.get("primary_header") or {})
    header.update(dict(bundle.get("header") or {}))
    for key in ("EXPMID", "EXPSTART", "MJD-BEG", "MJD-AVG"):
        value = header.get(key)
        if value is not None:
            try:
                result = float(value)
                if np.isfinite(result):
                    return result
            except (TypeError, ValueError):
                continue
    return None


def find_repeat_pairs(datasets: List[Dataset]) -> List[Dict[str, Any]]:
    """Find same-target, same-filter exposure pairs that genuinely share sky.

    Returns one record per usable pair, with the measured overlap fraction and
    the time baseline in hours.
    """
    grouped: Dict[Tuple[str, str], Dict[str, str]] = defaultdict(dict)
    for dataset in datasets:
        meta = dataset.meta_data or {}
        target = meta.get("target")
        filter_name = str(meta.get("filter") or "").upper()
        if not target or not filter_name:
            continue
        key = (target, filter_name)
        exposure = _exposure_key(dataset.name)
        current = grouped[key].get(exposure)
        if current is None or _product_rank(dataset.name) > _product_rank(current):
            grouped[key][exposure] = dataset.name

    pairs: List[Dict[str, Any]] = []
    for (target, filter_name), by_exposure in sorted(grouped.items()):
        names = sorted(by_exposure.values())
        if len(names) < 2:
            continue
        for index, name_a in enumerate(names):
            for name_b in names[index + 1 :]:
                try:
                    bundle_a = load_fits_bundle(name_a)
                    bundle_b = load_fits_bundle(name_b)
                except Exception:
                    continue
                overlap = overlap_fraction(bundle_a, bundle_b)
                if overlap < MIN_PAIR_OVERLAP:
                    continue
                time_a = _observation_time(bundle_a)
                time_b = _observation_time(bundle_b)
                baseline_hours = (
                    abs(time_a - time_b) * 24.0
                    if time_a is not None and time_b is not None
                    else None
                )
                pairs.append(
                    {
                        "target": target,
                        "filter": filter_name,
                        "epoch_a": name_a,
                        "epoch_b": name_b,
                        "overlap_fraction": float(overlap),
                        "baseline_hours": baseline_hours,
                        "supports": _pair_capability(baseline_hours),
                    }
                )
    return pairs


def _pair_capability(baseline_hours: Optional[float]) -> str:
    """Describe what science a given time baseline can and cannot support."""
    if baseline_hours is None:
        return "artifact_rejection_only_unknown_baseline"
    if baseline_hours < ARTIFACT_ONLY_BASELINE_HOURS:
        return "artifact_rejection_only"
    return "artifact_rejection_and_variability"


def veto_candidate(
    candidate: Dict[str, Any],
    pair: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Re-measure one candidate in both epochs of a pair and judge persistence.

    Returns None when the candidate's sky position is not on both detectors, so
    an absent measurement is never mistaken for a non-detection.
    """
    sky = candidate.get("sky_center") or {}
    ra, dec = sky.get("ra"), sky.get("dec")
    if ra is None or dec is None:
        return None

    measurements: Dict[str, Dict[str, Any]] = {}
    angular_scale = None
    for role, dataset_name in (("epoch_a", pair["epoch_a"]), ("epoch_b", pair["epoch_b"])):
        try:
            bundle = load_fits_bundle(dataset_name)
        except Exception:
            return None
        position = sky_to_pixel(bundle, float(ra), float(dec))
        if position is None:
            return None
        if angular_scale is None:
            wcs = bundle.get("wcs")
            if wcs is None or not wcs.has_celestial:
                return None
            angular_scale = float(np.sqrt(np.prod(proj_plane_pixel_scales(wcs.celestial))) * 3600)
            if not np.isfinite(angular_scale) or angular_scale <= 0:
                return None
        photometry = extract_photometry(
            image_data=bundle,
            ra_deg=float(ra),
            dec_deg=float(dec),
            aperture_radius_arcsec=APERTURE_RADIUS * angular_scale,
            background_annulus_inner_radius_arcsec=BACKGROUND_INNER_RADIUS * angular_scale,
            background_annulus_outer_radius_arcsec=BACKGROUND_OUTER_RADIUS * angular_scale,
        )
        if (
            photometry.get("measurement_status") != "measured"
            or photometry.get("background_status") != "measured"
        ):
            return None
        flux = physical_flux(photometry)
        error = physical_flux(photometry, "flux_error_jy")
        if flux is None or error is None or error <= 0:
            return None
        measurements[role] = photometry

    snr_a = measurements["epoch_a"].get("snr")
    snr_b = measurements["epoch_b"].get("snr")
    flux_a = float(measurements["epoch_a"]["background_subtracted_flux_jy"])
    flux_b = float(measurements["epoch_b"]["background_subtracted_flux_jy"])
    error_a = float(measurements["epoch_a"]["flux_error_jy"])
    error_b = float(measurements["epoch_b"]["flux_error_jy"])

    detected_a = snr_a is not None and float(snr_a) >= PERSISTENCE_SNR
    detected_b = snr_b is not None and float(snr_b) >= PERSISTENCE_SNR

    combined_error = float(np.hypot(error_a, error_b))
    difference_significance = (
        float(abs(flux_a - flux_b) / combined_error) if combined_error > 0 else None
    )

    if detected_a and detected_b:
        verdict = "persistent"
    elif detected_a or detected_b:
        verdict = (
            "single_epoch_only"
            if difference_significance is not None and difference_significance >= PERSISTENCE_SNR
            else "inconclusive_depth"
        )
    else:
        verdict = "undetected_in_both"

    return {
        "target": candidate.get("target"),
        "source_id": candidate.get("source_id"),
        "filter": pair["filter"],
        "epoch_a": pair["epoch_a"],
        "epoch_b": pair["epoch_b"],
        "baseline_hours": pair.get("baseline_hours"),
        "flux_unit": "Jy",
        "aperture_radius_arcsec": APERTURE_RADIUS * angular_scale,
        "flux_epoch_a": flux_a,
        "flux_epoch_b": flux_b,
        "snr_epoch_a": snr_a,
        "snr_epoch_b": snr_b,
        "difference_significance": difference_significance,
        "verdict": verdict,
        # A time baseline alone cannot distinguish artifacts from astrophysics.
        "interpretation": (
            "requires_artifact_depth_and_variability_checks"
            if verdict == "single_epoch_only" and pair.get("supports") == "artifact_rejection_only"
            else verdict
        ),
    }


def _pairs_for_candidate(
    candidate: Dict[str, Any],
    pairs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Select the repeat pairs that apply to one candidate's target."""
    return [pair for pair in pairs if pair["target"] == candidate.get("target")]


def main() -> int:
    """Discover repeat-exposure pairs and apply the veto to the candidate catalog."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pairs-output", type=Path, default=DEFAULT_PAIRS_OUTPUT)
    parser.add_argument(
        "--pairs-only",
        action="store_true",
        help="Report the available repeat-exposure pairs without vetting candidates.",
    )
    args = parser.parse_args()

    session = SessionLocal()
    try:
        datasets = session.query(Dataset).all()
    finally:
        session.close()

    pairs = find_repeat_pairs(datasets)
    args.pairs_output.parent.mkdir(parents=True, exist_ok=True)
    args.pairs_output.write_text(json.dumps(pairs, indent=2), encoding="utf-8")

    print(f"Repeat-exposure pairs with real sky overlap: {len(pairs)}")
    for pair in pairs:
        baseline = pair["baseline_hours"]
        baseline_text = f"{baseline:.1f} h" if baseline is not None else "unknown"
        print(
            f"  {pair['target']:22s} {pair['filter']:6s} "
            f"overlap={pair['overlap_fraction']:.3f} baseline={baseline_text} "
            f"({pair['supports']})"
        )

    if args.pairs_only:
        return 0

    if not args.candidates.exists():
        print(f"No candidate catalog at {args.candidates}")
        return 1

    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    results: List[Dict[str, Any]] = []
    verdict_counts: Dict[str, int] = defaultdict(int)
    unvettable = 0

    for candidate in candidates:
        applicable = _pairs_for_candidate(candidate, pairs)
        vetted = False
        for pair in applicable:
            outcome = veto_candidate(candidate, pair)
            if outcome is None:
                continue
            results.append(outcome)
            verdict_counts[outcome["verdict"]] += 1
            vetted = True
        if not vetted:
            unvettable += 1

    payload = {
        "pairs": pairs,
        "vetted_measurements": results,
        "summary": {
            "candidates_total": len(candidates),
            "candidates_with_no_repeat_coverage": unvettable,
            "verdict_counts": dict(verdict_counts),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print()
    print(f"Candidates: {len(candidates)}")
    print(f"  no repeat coverage available: {unvettable}")
    for verdict, count in sorted(verdict_counts.items()):
        print(f"  {verdict}: {count}")
    print(f"Written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
