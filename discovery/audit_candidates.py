"""Audit recorded photometry without inferring an astrophysical identity.

``untestable`` means the required calibrated measurements are missing or invalid;
``falsified`` means valid measurements fail the configured dropout selection;
``survives`` means that selection is passed, not that high redshift is confirmed.
Legacy pixel sums yield explicitly labelled nominal-scale estimates only.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

RESEARCH_DIR = Path("research_output")
DEFAULT_CANDIDATES = RESEARCH_DIR / "highz_candidates.json"
DEFAULT_SHORTLIST = RESEARCH_DIR / "highz_shortlist.json"
DEFAULT_OUTPUT = RESEARCH_DIR / "candidate_audit.json"
DEFAULT_REPORT = RESEARCH_DIR / "CANDIDATE_AUDIT.md"

BLUE_FILTER = "F090W"
MID_FILTER = "F200W"
REFERENCE_FILTER = "F444W"

# NIRCam nominal pixel scales, arcsec/pixel (JDox NIRCam imaging).
SHORTWAVE_PIXEL_SCALE = 0.031
LONGWAVE_PIXEL_SCALE = 0.063
ARCSEC_PER_RADIAN = 206264.806247

# Filters that land on the short-wave detectors; everything else is long-wave.
SHORTWAVE_FILTERS = {
    "F070W", "F090W", "F115W", "F140M", "F150W", "F150W2",
    "F162M", "F164N", "F182M", "F187N", "F200W", "F210M", "F212N",
}

# Brightness is advisory: lensing and unusual populations invalidate a hard veto.
BRIGHT_IMPLAUSIBLE_MAG = 24.5

MIN_MEANINGFUL_COVERAGE = 0.9
MAX_BLUE_SNR = 2.0
MIN_REFERENCE_SNR = 5.0
MAX_BLUE_RED_LIMIT_RATIO = 0.05

_DETECTOR_RE = re.compile(r"_(nrc[ab](?:long|[1-4]))_", re.IGNORECASE)


def pixel_scale_for_filter(filter_name: str) -> float:
    """Return the NIRCam pixel scale in arcsec for a filter name."""
    return (
        SHORTWAVE_PIXEL_SCALE
        if str(filter_name).upper() in SHORTWAVE_FILTERS
        else LONGWAVE_PIXEL_SCALE
    )


def pixel_solid_angle(filter_name: str) -> float:
    """Return the solid angle subtended by one pixel, in steradians."""
    return (pixel_scale_for_filter(filter_name) / ARCSEC_PER_RADIAN) ** 2


def detector_of(dataset_name: Optional[str]) -> Optional[str]:
    """Extract the NIRCam detector token (e.g. ``nrca1``) from a dataset name."""
    if not dataset_name:
        return None
    match = _DETECTOR_RE.search(str(dataset_name))
    return match.group(1).lower() if match else None


def module_of(dataset_name: Optional[str]) -> Optional[str]:
    """Return the NIRCam module letter (``a``/``b``) for a dataset name."""
    detector = detector_of(dataset_name)
    return detector[3] if detector else None


def surface_brightness_sum_to_jansky(pixel_sum: float, filter_name: str) -> float:
    """Legacy estimate of a summed MJy/sr aperture in Jy at nominal detector scale.

    This estimate is NOT authoritative for resampled i2d mosaics. Use the
    image header/WCS pixel area and matched angular apertures instead.
    ``extract_photometry`` sums raw ``i2d`` pixel values, which are surface
    brightness. Multiplying by the per-pixel solid angle turns that sum into a
    flux density. Skipping this step makes short-wave and long-wave sums
    non-comparable by a factor of ``(0.063 / 0.031)**2`` ~ 4.1.
    """
    return float(pixel_sum) * 1e6 * pixel_solid_angle(filter_name)


def ab_magnitude(flux_jy: Optional[float]) -> Optional[float]:
    """Return the AB magnitude for a flux density in Jy, or None if non-positive."""
    if flux_jy is None or not math.isfinite(flux_jy) or flux_jy <= 0:
        return None
    return -2.5 * math.log10(flux_jy / 3631.0)


def _aperture(candidate: Dict[str, Any], filter_name: str, radius: str = "3") -> Dict[str, Any]:
    """Return one aperture measurement block, or an empty dict when absent."""
    photometry = candidate.get("photometry_by_filter") or {}
    return ((photometry.get(filter_name) or {}).get(radius) or {})


def _finite(value: Any) -> Optional[float]:
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _coverage(measurement: Dict[str, Any]) -> float:
    value = _finite(measurement.get("coverage_fraction"))
    return value if value is not None and 0 <= value <= 1 else 0.0


def _physical_measurement(measurement: Dict[str, Any], filter_name: str) -> Dict[str, Any]:
    """Require explicit physical flux, positive error and calibration provenance.

    Never silently substitute nominal detector areas for absent mosaic calibration.
    A legacy estimate is retained separately so old archive records remain inspectable.
    """
    flux = _finite(measurement.get("background_subtracted_flux_jy"))
    error = _finite(measurement.get("flux_error_jy"))
    calibrated = (measurement.get("calibration_status") == "calibrated"
                  and measurement.get("measurement_status") == "measured"
                  and measurement.get("background_status") == "measured")
    raw = _finite(measurement.get("background_subtracted_flux"))
    return {
        "flux": flux, "error": error,
        "valid": calibrated and flux is not None and error is not None and error > 0,
        "legacy_flux": surface_brightness_sum_to_jansky(raw, filter_name) if raw is not None else None,
    }


def audit_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Apply an explicit measured dropout cut, with missing evidence kept separate."""
    apertures = {f: _aperture(candidate, f) for f in (REFERENCE_FILTER, BLUE_FILTER, MID_FILTER)}
    measurements = {f: _physical_measurement(a, f) for f, a in apertures.items()}
    covered = {f: _coverage(a) >= MIN_MEANINGFUL_COVERAGE for f, a in apertures.items()}
    reference, blue = measurements[REFERENCE_FILTER], measurements[BLUE_FILTER]
    untestable: List[str] = []
    failures: List[str] = []
    warnings: List[str] = []
    for f in apertures:
        if not covered[f]:
            untestable.append(f"{f.lower()}_not_measured_at_source_position")
        elif not measurements[f]["valid"]:
            untestable.append(f"{f.lower()}_invalid_or_uncalibrated_flux_uncertainty")
    # Same pixel radius is not the same sky aperture on SW and LW detectors.
    radii = [_finite(a.get("aperture_radius_arcsec")) for a in apertures.values()]
    if any(r is None or r <= 0 for r in radii) or not all(
        math.isclose(r, radii[0], rel_tol=1e-6, abs_tol=1e-9) for r in radii if r is not None
    ):
        untestable.append("angular_apertures_missing_or_unmatched")

    reference_jy = reference["flux"] if reference["valid"] else None
    reference_mag = ab_magnitude(reference_jy)
    reference_snr = reference["flux"] / reference["error"] if reference["valid"] else None
    blue_snr = blue["flux"] / blue["error"] if blue["valid"] else None
    blue_limit_jy = None
    physical_ratio = None
    break_magnitudes = None
    if not untestable:
        if reference_snr < MIN_REFERENCE_SNR:
            failures.append("reference_snr_below_5")
        if blue_snr > MAX_BLUE_SNR:
            failures.append("blue_band_detected_above_snr_2")
        if reference_jy > 0:
            blue_limit_jy = max(blue["flux"], 0.0) + 2.0 * blue["error"]
            physical_ratio = blue_limit_jy / reference_jy
            if physical_ratio >= MAX_BLUE_RED_LIMIT_RATIO:
                failures.append("blue_2sigma_limit_not_dropout_like")
            if physical_ratio > 0:
                break_magnitudes = -2.5 * math.log10(physical_ratio)

    reference_dataset = candidate.get("f444_dataset") or candidate.get("reference_dataset")
    blue_dataset = candidate.get("f090_dataset")
    reference_module, blue_module = module_of(reference_dataset), module_of(blue_dataset)
    module_mismatch = bool(reference_module and blue_module and reference_module != blue_module)
    if module_mismatch:
        warnings.append("different_detector_modules_verify_wcs_coverage")
    if reference_mag is not None and reference_mag < BRIGHT_IMPLAUSIBLE_MAG:
        warnings.append("bright_source_requires_lensing_and_contaminant_assessment")
    legacy_flux = reference["legacy_flux"]
    verdict = "untestable" if untestable else ("falsified" if failures else "survives")
    return {
        "target": candidate.get("target"), "source_id": candidate.get("source_id"),
        "pipeline_validation_status": candidate.get("validation_status"),
        "pipeline_validation_score": candidate.get("validation_score"),
        "pipeline_ratio_f090_f444": candidate.get("ratio_f090_f444"),
        "reference_dataset": reference_dataset, "blue_dataset": blue_dataset,
        "reference_detector": detector_of(reference_dataset), "blue_detector": detector_of(blue_dataset),
        "module_mismatch": module_mismatch,
        "blue_covered": covered[BLUE_FILTER], "mid_covered": covered[MID_FILTER],
        "reference_covered": covered[REFERENCE_FILTER],
        "reference_flux_jy": reference_jy, "reference_ab_magnitude": reference_mag,
        "reference_snr": reference_snr, "blue_snr": blue_snr,
        "legacy_nominal_reference_flux_jy": legacy_flux,
        "legacy_nominal_reference_ab_magnitude": ab_magnitude(legacy_flux),
        "blue_2sigma_limit_jy": blue_limit_jy, "physical_blue_over_red_ratio": physical_ratio,
        "implied_break_magnitudes": break_magnitudes,
        "audit_blockers": untestable + failures,
        "audit_untestable_reasons": untestable, "audit_falsified_reasons": failures,
        "audit_warnings": warnings, "audit_verdict": verdict,
        "selection": {"max_blue_snr": MAX_BLUE_SNR, "min_reference_snr": MIN_REFERENCE_SNR,
                      "max_blue_red_2sigma_ratio": MAX_BLUE_RED_LIMIT_RATIO},
    }


def summarize(audits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate per-candidate audits into catalog-level counts."""
    blocker_counts: Counter = Counter()
    for row in audits:
        blocker_counts.update(row["audit_blockers"])

    survivors = [row for row in audits if row["audit_verdict"] == "survives"]
    by_status: Counter = Counter(
        (row["pipeline_validation_status"], row["audit_verdict"]) for row in audits
    )

    return {
        "total_candidates": len(audits),
        "survivors": len(survivors),
        "blue_measured": sum(1 for row in audits if row["blue_covered"]),
        "mid_measured": sum(1 for row in audits if row["mid_covered"]),
        "blue_and_mid_measured": sum(
            1 for row in audits if row["blue_covered"] and row["mid_covered"]
        ),
        "module_mismatch_pairs": sum(1 for row in audits if row["module_mismatch"]),
        "untestable": sum(row["audit_verdict"] == "untestable" for row in audits),
        "falsified": sum(row["audit_verdict"] == "falsified" for row in audits),
        "blocker_counts": dict(blocker_counts.most_common()),
        "pipeline_status_vs_audit": {
            f"{status}|{verdict}": count for (status, verdict), count in sorted(
                by_status.items(), key=lambda item: str(item[0])
            )
        },
        "survivor_ids": [
            {"target": row["target"], "source_id": row["source_id"]} for row in survivors
        ],
    }


def _brightness_table(audits: List[Dict[str, Any]], limit: int = 20) -> List[Dict[str, Any]]:
    """Return the brightest blue-measured candidates for the report table."""
    measured = [row for row in audits if row["blue_covered"] and row["reference_ab_magnitude"]]
    measured.sort(key=lambda row: row["reference_ab_magnitude"])
    return measured[:limit]


def render_report(summary: Dict[str, Any], table: List[Dict[str, Any]]) -> str:
    """Render the distinction between missing measurements and measured failures."""
    lines = ["# Candidate Audit", "", "Recorded-photometry audit; no FITS rerun.", "",
             f"- Candidates: **{summary['total_candidates']}**",
             f"- Untestable (missing/invalid evidence): **{summary['untestable']}**",
             f"- Falsified by the configured dropout selection: **{summary['falsified']}**",
             f"- Survive selection (not redshift confirmations): **{summary['survivors']}**",
             f"- F090W covered: **{summary['blue_measured']}**",
             f"- F200W covered: **{summary['mid_measured']}**",
             f"- Both covered: **{summary['blue_and_mid_measured']}**",
             f"- Different-module names (advisory only): **{summary['module_mismatch_pairs']}**",
             "", "| blocker | count |", "| --- | ---: |"]
    lines.extend(f"| `{reason}` | {count} |" for reason, count in summary["blocker_counts"].items())
    lines.extend(["", "Selection requires calibrated finite Jy fluxes, positive errors, matched angular apertures,",
                  "at least 90% coverage in all three bands, F444W SNR >= 5, F090W SNR <= 2,",
                  "and (max(F090W flux, 0) + 2 sigma) / F444W flux < 0.05.",
                  "This is a screening cut, not a photometric-redshift model or proof of a Lyman break.",
                  "Legacy nominal detector-scale estimates are diagnostic only and cannot pass the audit.",
                  "Brightness and detector-name differences are warnings, not astrophysical vetoes.", ""])
    return "\n".join(lines)


def _load(path: Path) -> List[Dict[str, Any]]:
    """Load a candidate list from JSON."""
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    """Audit the candidate catalog and write JSON plus markdown outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--shortlist", type=Path, default=DEFAULT_SHORTLIST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    if not args.candidates.exists():
        print(f"No candidate catalog at {args.candidates}")
        return 1

    candidates = _load(args.candidates)
    audits = [audit_candidate(item) for item in candidates]
    summary = summarize(audits)

    shortlist_summary: Optional[Dict[str, Any]] = None
    if args.shortlist.exists():
        shortlist_audits = [audit_candidate(item) for item in _load(args.shortlist)]
        shortlist_summary = summarize(shortlist_audits)

    payload = {
        "summary": summary,
        "shortlist_summary": shortlist_summary,
        "candidates": audits,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    args.report.write_text(
        render_report(summary, _brightness_table(audits)), encoding="utf-8"
    )

    print(f"Audited {summary['total_candidates']} candidates -> {args.output}")
    print(f"  blue band measured:        {summary['blue_measured']}")
    print(f"  blue AND mid measured:     {summary['blue_and_mid_measured']}")
    print(f"  module-name mismatches:    {summary['module_mismatch_pairs']}")
    print(f"  untestable:                {summary['untestable']}")
    print(f"  falsified selection:       {summary['falsified']}")
    print(f"  survive full audit:        {summary['survivors']}")
    if shortlist_summary:
        print(
            f"  shortlist survivors:       {shortlist_summary['survivors']}"
            f" / {shortlist_summary['total_candidates']}"
        )
    print(f"Report written to {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
