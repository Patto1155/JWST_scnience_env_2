"""Independent falsification audit of the high-z candidate catalog.

This module deliberately reads only the committed JSON products in
``research_output/`` - it never touches the FITS archive and never re-runs the
pipeline. The point is to be able to check the pipeline's own conclusions from
its own recorded evidence, on any machine, with no data download.

It answers three questions the main pipeline currently does not ask:

1. Is the blue band actually *measured* at the candidate position, or is the
   "dropout" a division by a zero that was produced by an off-detector
   aperture? A ratio of 0/x is not a non-detection.
2. Are the two filters being compared physically capable of covering the same
   sky? NIRCam module A and module B footprints are disjoint, and a NIRCam
   short-wave detector covers one quadrant of the long-wave field.
3. What is the candidate's actual brightness in physical units? JWST ``i2d``
   pixels are surface brightness (MJy/sr), and short-wave pixels subtend a
   quarter of the solid angle of long-wave pixels, so a raw sum of pixel values
   is not a flux and a ratio of two such sums is not a color.

Run:
    python discovery/audit_candidates.py
    python discovery/audit_candidates.py --candidates research_output/highz_candidates.json
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

# Above this AB magnitude a z > 10 interpretation is not merely unlikely, it is
# brighter than any spectroscopically confirmed z > 10 galaxy by a wide margin.
# GN-z11 sits near m_AB ~ 26; the JADES/CEERS z > 10 population is m_AB ~ 26-29.
BRIGHT_IMPLAUSIBLE_MAG = 24.5

MIN_MEANINGFUL_COVERAGE = 0.5

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
    """Convert a summed MJy/sr aperture into a flux density in Jy.

    ``extract_photometry`` sums raw ``i2d`` pixel values, which are surface
    brightness. Multiplying by the per-pixel solid angle turns that sum into a
    flux density. Skipping this step makes short-wave and long-wave sums
    non-comparable by a factor of ``(0.063 / 0.031)**2`` ~ 4.1.
    """
    return float(pixel_sum) * 1e6 * pixel_solid_angle(filter_name)


def ab_magnitude(flux_jy: Optional[float]) -> Optional[float]:
    """Return the AB magnitude for a flux density in Jy, or None if non-positive."""
    if flux_jy is None or flux_jy <= 0:
        return None
    return -2.5 * math.log10(flux_jy / 3631.0)


def _aperture(candidate: Dict[str, Any], filter_name: str, radius: str = "3") -> Dict[str, Any]:
    """Return one aperture measurement block, or an empty dict when absent."""
    photometry = candidate.get("photometry_by_filter") or {}
    return ((photometry.get(filter_name) or {}).get(radius) or {})


def _coverage(measurement: Dict[str, Any]) -> float:
    """Return the aperture coverage fraction, defaulting to zero."""
    try:
        return float(measurement.get("coverage_fraction") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def audit_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Re-derive physical quantities and falsification verdicts for one candidate."""
    reference = _aperture(candidate, REFERENCE_FILTER)
    blue = _aperture(candidate, BLUE_FILTER)
    mid = _aperture(candidate, MID_FILTER)

    reference_sum = float(reference.get("background_subtracted_flux") or 0.0)
    reference_jy = surface_brightness_sum_to_jansky(reference_sum, REFERENCE_FILTER)
    reference_mag = ab_magnitude(reference_jy)

    blue_covered = _coverage(blue) >= MIN_MEANINGFUL_COVERAGE
    mid_covered = _coverage(mid) >= MIN_MEANINGFUL_COVERAGE
    reference_covered = _coverage(reference) >= MIN_MEANINGFUL_COVERAGE

    # A dropout limit is only defined where the blue band was actually observed.
    blue_limit_jy: Optional[float] = None
    physical_ratio: Optional[float] = None
    break_magnitudes: Optional[float] = None
    if blue_covered and reference_jy > 0:
        blue_sum = float(blue.get("background_subtracted_flux") or 0.0)
        blue_error = float(blue.get("flux_error") or 0.0)
        blue_limit_jy = surface_brightness_sum_to_jansky(
            max(blue_sum, 0.0) + 2.0 * blue_error, BLUE_FILTER
        )
        physical_ratio = blue_limit_jy / reference_jy
        if physical_ratio > 0:
            break_magnitudes = -2.5 * math.log10(physical_ratio)

    reference_dataset = candidate.get("f444_dataset") or candidate.get("reference_dataset")
    blue_dataset = candidate.get("f090_dataset")
    reference_module = module_of(reference_dataset)
    blue_module = module_of(blue_dataset)
    disjoint_modules = bool(
        reference_module and blue_module and reference_module != blue_module
    )

    blockers: List[str] = []
    if disjoint_modules:
        blockers.append("blue_and_reference_on_disjoint_nircam_modules")
    if not blue_covered:
        blockers.append("blue_band_never_measured_at_source_position")
    if not mid_covered:
        blockers.append("mid_band_never_measured_at_source_position")
    if not reference_covered:
        blockers.append("reference_band_not_measured")
    if not (blue_covered and mid_covered):
        blockers.append("insufficient_bands_for_lyman_break_test")
    if reference_mag is not None and reference_mag < BRIGHT_IMPLAUSIBLE_MAG:
        blockers.append("too_bright_for_high_redshift_interpretation")
    if float(candidate.get("ratio_f090_f444") or 0.0) == 0.0 and not blue_covered:
        blockers.append("dropout_ratio_is_divide_by_unmeasured_zero")

    return {
        "target": candidate.get("target"),
        "source_id": candidate.get("source_id"),
        "pipeline_validation_status": candidate.get("validation_status"),
        "pipeline_validation_score": candidate.get("validation_score"),
        "pipeline_ratio_f090_f444": candidate.get("ratio_f090_f444"),
        "reference_dataset": reference_dataset,
        "blue_dataset": blue_dataset,
        "reference_detector": detector_of(reference_dataset),
        "blue_detector": detector_of(blue_dataset),
        "disjoint_modules": disjoint_modules,
        "blue_covered": blue_covered,
        "mid_covered": mid_covered,
        "reference_covered": reference_covered,
        "reference_flux_jy": reference_jy,
        "reference_ab_magnitude": reference_mag,
        "blue_2sigma_limit_jy": blue_limit_jy,
        "physical_blue_over_red_ratio": physical_ratio,
        "implied_break_magnitudes": break_magnitudes,
        "audit_blockers": blockers,
        "audit_verdict": "survives" if not blockers else "falsified",
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
        "disjoint_module_pairs": sum(1 for row in audits if row["disjoint_modules"]),
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
    """Render a human-readable markdown audit report."""
    total = summary["total_candidates"] or 1
    lines = [
        "# Candidate Audit",
        "",
        "Independent falsification pass over `highz_candidates.json`, computed from",
        "the committed photometry blocks only. No FITS access, no pipeline rerun.",
        "",
        "## Catalog-level result",
        "",
        f"- Candidates audited: **{summary['total_candidates']}**",
        f"- Candidates where F090W was actually measured at the source position: "
        f"**{summary['blue_measured']}** "
        f"({100.0 * summary['blue_measured'] / total:.1f}%)",
        f"- Candidates where F200W was actually measured: **{summary['mid_measured']}**",
        f"- Candidates with **both** F090W and F200W measured (the minimum for a",
        f"  two-color Lyman-break test): **{summary['blue_and_mid_measured']}**",
        f"- Candidates whose blue and reference images sit on disjoint NIRCam",
        f"  modules (physically non-overlapping sky): **{summary['disjoint_module_pairs']}**",
        f"- Candidates surviving every audit check: **{summary['survivors']}**",
        "",
        "## Why candidates fail",
        "",
        "| blocker | count |",
        "| --- | ---: |",
    ]
    for blocker, count in summary["blocker_counts"].items():
        lines.append(f"| `{blocker}` | {count} |")

    lines += [
        "",
        "## Brightest blue-measured candidates, in physical units",
        "",
        "`m_F444W` is an AB magnitude inside the r=3 px aperture after converting",
        "MJy/sr to Jy with the long-wave pixel solid angle. `break` is the 2-sigma",
        "lower limit on the F090W/F444W break after the short-wave/long-wave pixel",
        "area correction the pipeline omits.",
        "",
        "| target | source | m_F444W (r=3px) | break (mag) | pipeline status | verdict |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in table:
        break_text = (
            f"{row['implied_break_magnitudes']:.2f}"
            if row["implied_break_magnitudes"] is not None
            else "n/a"
        )
        lines.append(
            f"| {row['target']} | {row['source_id']} | "
            f"{row['reference_ab_magnitude']:.2f} | {break_text} | "
            f"{row['pipeline_validation_status']} | {row['audit_verdict']} |"
        )

    lines += [
        "",
        "For scale: the brightest spectroscopically confirmed z > 10 galaxies are",
        f"near m_AB ~ 26. Anything brighter than m_AB ~ {BRIGHT_IMPLAUSIBLE_MAG} in F444W is",
        "orders of magnitude too luminous for that interpretation and is far more",
        "likely a low-redshift source, a star, or an uncorrected detector artifact.",
        "",
    ]
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
    print(f"  disjoint-module pairs:     {summary['disjoint_module_pairs']}")
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
