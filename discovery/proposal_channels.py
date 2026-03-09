"""Proposal-channel helpers for JWST candidate frontier construction."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from tools.jwst.photometry import compute_color_index

from discovery.proposal_schemas import (
    CandidateProposalMetadata,
    MeasurementStatus,
    PortfolioBucket,
    ProposalChannelName,
    ProposalChannelSummary,
)


BLUE_FILTER = "F090W"
MID_FILTER = "F200W"
REFERENCE_FILTER = "F444W"


def _clip_unit_interval(value: float) -> float:
    return float(max(0.0, min(1.0, float(value))))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _dropout_fraction(candidate: Dict[str, Any]) -> float:
    aperture_checks = list(candidate.get("aperture_checks") or [])
    if not aperture_checks:
        return 0.0
    hits = sum(1 for item in aperture_checks if item.get("dropout_lt_0p05"))
    return float(hits / len(aperture_checks))


def _reference_flux_growth(candidate: Dict[str, Any]) -> Optional[float]:
    photometry = candidate.get("photometry_by_filter") or {}
    reference = photometry.get(REFERENCE_FILTER) or {}
    r2 = _safe_float(((reference.get("2") or {}).get("background_subtracted_flux")))
    r5 = _safe_float(((reference.get("5") or {}).get("background_subtracted_flux")))
    if r2 <= 0.0 or r5 <= 0.0:
        return None
    return float(r5 / max(r2, 1e-6))


def _portfolio_bucket_for(
    primary_channel: Optional[str],
    *,
    disqualifying_flags: List[str],
) -> PortfolioBucket:
    if disqualifying_flags:
        return "edge_exploration"
    if primary_channel == "dropout_strict":
        return "conservative"
    if primary_channel in {"anomaly_context", "novel_high_snr_outlier"}:
        return "novelty"
    return "alternative"


def classify_measurement_status(
    measurement: Dict[str, Any],
    *,
    coverage_threshold: float = 0.9,
    detection_snr_threshold: float = 2.0,
) -> MeasurementStatus:
    """Classify whether a filter measurement is truly usable."""
    pixels_in_aperture = int(measurement.get("pixels_in_aperture") or 0)
    valid_pixel_count = int(measurement.get("valid_pixel_count") or 0)
    coverage_fraction = _safe_float(measurement.get("coverage_fraction"))
    flux = measurement.get("background_subtracted_flux")

    if pixels_in_aperture <= 0 or valid_pixel_count <= 0:
        return "unmeasured_offchip"
    if coverage_fraction < coverage_threshold:
        return "unmeasured_low_coverage"
    if flux is None:
        return "unmeasured_invalid"

    snr = measurement.get("snr")
    numeric_flux = _safe_float(flux)
    numeric_snr = _safe_float(snr)
    if numeric_flux > 0.0 and numeric_snr >= detection_snr_threshold:
        return "measured_detection"
    return "measured_nondetection"


def is_measured_status(status: str) -> bool:
    """Return whether a status counts as a real, usable measurement."""
    return status in {"measured_detection", "measured_nondetection"}


def build_measurement_status_by_filter(
    photometry_by_filter: Dict[str, Dict[str, Any]],
    *,
    radius_key: str = "3",
) -> Dict[str, MeasurementStatus]:
    """Build per-filter measurement usability states."""
    statuses: Dict[str, MeasurementStatus] = {}
    for filter_name, measurements in (photometry_by_filter or {}).items():
        measurement = (measurements or {}).get(radius_key) or {}
        statuses[str(filter_name)] = classify_measurement_status(measurement)
    return statuses


def compute_completeness_score(
    measurement_status_by_filter: Dict[str, str],
    *,
    required_filters: List[str],
) -> float:
    """Compute how much of the required evidence set is actually measured."""
    filtered = [name for name in required_filters if name in measurement_status_by_filter]
    if not filtered:
        return 0.0
    measured_count = sum(
        1 for filter_name in filtered if is_measured_status(measurement_status_by_filter[filter_name])
    )
    return float(measured_count / len(filtered))


def compute_falsification_flags(candidate: Dict[str, Any]) -> List[str]:
    """Record non-fatal ways a candidate can fail a hypothesis."""
    statuses = candidate.get("measurement_status_by_filter") or {}
    flags: List[str] = []

    blue_status = statuses.get(BLUE_FILTER)
    mid_status = statuses.get(MID_FILTER)
    reference_status = statuses.get(REFERENCE_FILTER)
    if blue_status and not is_measured_status(blue_status):
        flags.append(f"blue_{blue_status}")
    if mid_status and not is_measured_status(mid_status):
        flags.append(f"mid_{mid_status}")
    if reference_status and not is_measured_status(reference_status):
        flags.append(f"reference_{reference_status}")

    if _safe_float(candidate.get("red_snr_r3")) < 5.0:
        flags.append("reference_low_snr")
    if _safe_float(candidate.get("coverage_fraction_r3")) < 0.9:
        flags.append("reference_low_coverage")
    if _safe_float(candidate.get("edge_distance_px")) < 16.0:
        flags.append("near_edge")
    if _dropout_fraction(candidate) < (2.0 / 3.0):
        flags.append("aperture_instability")

    return list(dict.fromkeys(flags))


def compute_disqualifying_flags(candidate: Dict[str, Any]) -> List[str]:
    """Record strong reasons to distrust a candidate as a high-confidence keep."""
    flags: List[str] = []
    statuses = candidate.get("measurement_status_by_filter") or {}
    blue_status = statuses.get(BLUE_FILTER)
    reference_status = statuses.get(REFERENCE_FILTER)

    if reference_status and not is_measured_status(reference_status):
        flags.append("reference_unmeasured")
    if blue_status in {"unmeasured_low_coverage", "unmeasured_offchip"}:
        flags.append("blue_unmeasured")
    if _safe_float(candidate.get("f444_flux")) <= 0.0:
        flags.append("nonpositive_reference_flux")
    if _safe_float(candidate.get("red_snr_r3")) < 5.0:
        flags.append("reference_low_snr")
    return list(dict.fromkeys(flags))


def propose_dropout_strict(candidate: Dict[str, Any]) -> Optional[float]:
    """Score strong dropout-like candidates with full measurability."""
    statuses = candidate.get("measurement_status_by_filter") or {}
    if not is_measured_status(statuses.get(BLUE_FILTER, "")):
        return None
    if not is_measured_status(statuses.get(REFERENCE_FILTER, "")):
        return None

    ratio = candidate.get("ratio_f090_f444")
    if ratio is None or float(ratio) >= 0.05:
        return None

    dropout_fraction = _dropout_fraction(candidate)
    red_snr = _safe_float(candidate.get("red_snr_r3"))
    coverage = _safe_float(candidate.get("coverage_fraction_r3"))
    edge_distance = _safe_float(candidate.get("edge_distance_px"))
    score = (
        0.40 * _clip_unit_interval((0.05 - float(ratio)) / 0.05)
        + 0.25 * dropout_fraction
        + 0.20 * _clip_unit_interval((red_snr - 8.0) / 12.0)
        + 0.10 * _clip_unit_interval((coverage - 0.95) / 0.05)
        + 0.05 * _clip_unit_interval((edge_distance - 24.0) / 24.0)
    )
    return score if score > 0.0 else None


def propose_dropout_loose(candidate: Dict[str, Any]) -> Optional[float]:
    """Score plausible but weaker dropout-like candidates."""
    statuses = candidate.get("measurement_status_by_filter") or {}
    if not is_measured_status(statuses.get(BLUE_FILTER, "")):
        return None
    if not is_measured_status(statuses.get(REFERENCE_FILTER, "")):
        return None

    ratio = candidate.get("ratio_f090_f444")
    if ratio is None or float(ratio) >= 0.15:
        return None

    red_snr = _safe_float(candidate.get("red_snr_r3"))
    coverage = _safe_float(candidate.get("coverage_fraction_r3"))
    dropout_fraction = _dropout_fraction(candidate)
    score = (
        0.35 * _clip_unit_interval((0.15 - float(ratio)) / 0.15)
        + 0.25 * dropout_fraction
        + 0.20 * _clip_unit_interval((red_snr - 5.0) / 10.0)
        + 0.20 * _clip_unit_interval((coverage - 0.9) / 0.1)
    )
    return score if score >= 0.45 else None


def compute_target_color_baseline(all_sources: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Build a robust target-level color locus for outlier detection."""
    x_values: List[float] = []
    y_values: List[float] = []
    for candidate in all_sources:
        statuses = candidate.get("measurement_status_by_filter") or {}
        if not all(is_measured_status(statuses.get(filt, "")) for filt in (BLUE_FILTER, MID_FILTER, REFERENCE_FILTER)):
            continue

        photometry = candidate.get("photometry_by_filter") or {}
        blue = _safe_float((((photometry.get(BLUE_FILTER) or {}).get("3") or {}).get("background_subtracted_flux")))
        mid = _safe_float((((photometry.get(MID_FILTER) or {}).get("3") or {}).get("background_subtracted_flux")))
        red = _safe_float((((photometry.get(REFERENCE_FILTER) or {}).get("3") or {}).get("background_subtracted_flux")))
        c1 = compute_color_index(blue, mid)
        c2 = compute_color_index(mid, red)
        if c1.get("color_index") is None or c2.get("color_index") is None:
            continue
        x_values.append(float(c1["color_index"]))
        y_values.append(float(c2["color_index"]))

    if len(x_values) < 5:
        return None

    def _median(values: List[float]) -> float:
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2 == 1:
            return float(ordered[middle])
        return float((ordered[middle - 1] + ordered[middle]) / 2.0)

    def _mad(values: List[float], center: float) -> float:
        deviations = [abs(item - center) for item in values]
        return max(_median(deviations), 1e-6)

    x_center = _median(x_values)
    y_center = _median(y_values)
    return {
        "x_center": x_center,
        "y_center": y_center,
        "x_mad": _mad(x_values, x_center),
        "y_mad": _mad(y_values, y_center),
    }


def propose_color_color_outlier(
    candidate: Dict[str, Any],
    *,
    color_baseline: Optional[Dict[str, Any]],
) -> Optional[float]:
    """Score sources that sit far from the target's measured color locus."""
    if not color_baseline:
        return None

    statuses = candidate.get("measurement_status_by_filter") or {}
    if not all(is_measured_status(statuses.get(filt, "")) for filt in (BLUE_FILTER, MID_FILTER, REFERENCE_FILTER)):
        return None

    photometry = candidate.get("photometry_by_filter") or {}
    blue = _safe_float((((photometry.get(BLUE_FILTER) or {}).get("3") or {}).get("background_subtracted_flux")))
    mid = _safe_float((((photometry.get(MID_FILTER) or {}).get("3") or {}).get("background_subtracted_flux")))
    red = _safe_float((((photometry.get(REFERENCE_FILTER) or {}).get("3") or {}).get("background_subtracted_flux")))
    c1 = compute_color_index(blue, mid)
    c2 = compute_color_index(mid, red)
    if c1.get("color_index") is None or c2.get("color_index") is None:
        return None

    dx = abs(float(c1["color_index"]) - float(color_baseline["x_center"])) / float(color_baseline["x_mad"])
    dy = abs(float(c2["color_index"]) - float(color_baseline["y_center"])) / float(color_baseline["y_mad"])
    distance = max(dx, dy)
    if distance < 2.5:
        return None
    return _clip_unit_interval(distance / 6.0)


def propose_morphology_extended_red(candidate: Dict[str, Any]) -> Optional[float]:
    """Score sources with a strong red-band growth curve."""
    statuses = candidate.get("measurement_status_by_filter") or {}
    if not is_measured_status(statuses.get(REFERENCE_FILTER, "")):
        return None

    growth = _reference_flux_growth(candidate)
    if growth is None or growth < 1.4:
        return None
    red_snr = _safe_float(candidate.get("red_snr_r3"))
    score = (
        0.60 * _clip_unit_interval((growth - 1.4) / 1.2)
        + 0.40 * _clip_unit_interval((red_snr - 8.0) / 12.0)
    )
    return score if score >= 0.4 else None


def propose_anomaly_context(
    candidate: Dict[str, Any],
    *,
    anomalous_dataset_names: set[str],
) -> Optional[float]:
    """Score candidates drawn from globally odd datasets as an exploration bucket."""
    dataset_names = {
        str(candidate.get("reference_dataset") or ""),
        str(candidate.get("f090_dataset") or ""),
        str(candidate.get("f200_dataset") or ""),
    }
    if not anomalous_dataset_names.intersection(dataset_names):
        return None
    red_snr = _safe_float(candidate.get("red_snr_r3"))
    completeness_score = _safe_float(candidate.get("completeness_score"))
    score = 0.5 + 0.25 * _clip_unit_interval((red_snr - 5.0) / 10.0) + 0.25 * completeness_score
    return _clip_unit_interval(score)


def propose_novel_high_snr_outlier(candidate: Dict[str, Any]) -> Optional[float]:
    """Score well-measured sources that are unusual without being strict dropouts."""
    statuses = candidate.get("measurement_status_by_filter") or {}
    if not is_measured_status(statuses.get(REFERENCE_FILTER, "")):
        return None
    if not is_measured_status(statuses.get(BLUE_FILTER, "")):
        return None

    red_snr = _safe_float(candidate.get("red_snr_r3"))
    completeness_score = _safe_float(candidate.get("completeness_score"))
    ratio = candidate.get("ratio_f090_f444")
    growth = _reference_flux_growth(candidate) or 1.0
    if red_snr < 10.0 or completeness_score < 0.66:
        return None
    if ratio is not None and float(ratio) < 0.05:
        return None

    score = (
        0.45 * _clip_unit_interval((red_snr - 10.0) / 20.0)
        + 0.30 * completeness_score
        + 0.25 * _clip_unit_interval((growth - 1.2) / 1.0)
    )
    return score if score >= 0.5 else None


def attach_proposal_metadata(
    candidate: Dict[str, Any],
    *,
    color_baseline: Optional[Dict[str, Any]],
    anomalous_dataset_names: set[str],
) -> CandidateProposalMetadata:
    """Attach measurability and proposal-channel metadata to one candidate."""
    measurement_status_by_filter = build_measurement_status_by_filter(
        candidate.get("photometry_by_filter") or {},
        radius_key="3",
    )
    completeness_score = compute_completeness_score(
        measurement_status_by_filter,
        required_filters=[BLUE_FILTER, REFERENCE_FILTER, MID_FILTER],
    )

    working = dict(candidate)
    working["measurement_status_by_filter"] = measurement_status_by_filter
    working["completeness_score"] = completeness_score

    falsification_flags = compute_falsification_flags(working)
    disqualifying_flags = compute_disqualifying_flags(working)
    working["falsification_flags"] = falsification_flags
    working["disqualifying_flags"] = disqualifying_flags

    scorers: List[tuple[ProposalChannelName, Optional[float]]] = [
        ("dropout_strict", propose_dropout_strict(working)),
        ("dropout_loose", propose_dropout_loose(working)),
        ("color_color_outlier", propose_color_color_outlier(working, color_baseline=color_baseline)),
        ("morphology_extended_red", propose_morphology_extended_red(working)),
        ("anomaly_context", propose_anomaly_context(working, anomalous_dataset_names=anomalous_dataset_names)),
        ("novel_high_snr_outlier", propose_novel_high_snr_outlier(working)),
    ]

    channel_scores = {
        name: float(score)
        for name, score in scorers
        if score is not None
    }
    proposal_channels = [
        name
        for name, score in sorted(channel_scores.items(), key=lambda item: item[1], reverse=True)
    ]
    primary_channel = proposal_channels[0] if proposal_channels else None

    novelty_score = 0.0
    for name in ("color_color_outlier", "morphology_extended_red", "anomaly_context", "novel_high_snr_outlier"):
        novelty_score = max(novelty_score, float(channel_scores.get(name) or 0.0))

    measured_filters = [
        filter_name
        for filter_name, status in measurement_status_by_filter.items()
        if is_measured_status(status)
    ]
    unmeasured_filters = [
        filter_name
        for filter_name, status in measurement_status_by_filter.items()
        if not is_measured_status(status)
    ]
    return CandidateProposalMetadata(
        measurement_status_by_filter=measurement_status_by_filter,
        measured_filters=measured_filters,
        unmeasured_filters=unmeasured_filters,
        completeness_score=float(completeness_score),
        proposal_channels=proposal_channels,
        primary_channel=primary_channel,
        channel_scores=channel_scores,
        novelty_score=float(novelty_score),
        falsification_flags=falsification_flags,
        disqualifying_flags=disqualifying_flags,
        portfolio_bucket=_portfolio_bucket_for(primary_channel, disqualifying_flags=disqualifying_flags)
        if primary_channel
        else None,
    )


def build_portfolio_shortlist(
    candidates: List[Dict[str, Any]],
    *,
    max_candidates: int = 25,
) -> List[Dict[str, Any]]:
    """Build a diversified shortlist rather than a pure global ranking."""
    if max_candidates <= 0:
        return []

    quota_by_bucket = {
        "conservative": min(10, max_candidates),
        "alternative": min(7, max_candidates),
        "novelty": min(5, max_candidates),
        "edge_exploration": min(3, max_candidates),
    }
    per_target_cap = max(int((max_candidates * 0.6) + 0.999), 1)

    def sort_key(item: Dict[str, Any]) -> tuple[float, float, float, float]:
        channel_scores = item.get("channel_scores") or {}
        best_channel = max((float(score) for score in channel_scores.values()), default=0.0)
        return (
            float(item.get("validation_score") or 0.0),
            best_channel,
            float(item.get("novelty_score") or 0.0),
            float(item.get("f444_flux") or 0.0),
        )

    selected: List[Dict[str, Any]] = []
    seen_ids: set[tuple[str, Any]] = set()
    target_counts: Counter[str] = Counter()
    leftovers: List[Dict[str, Any]] = []

    for bucket in ("conservative", "alternative", "novelty", "edge_exploration"):
        bucket_candidates = [
            item
            for item in candidates
            if str(item.get("portfolio_bucket") or "") == bucket
        ]
        bucket_candidates.sort(key=sort_key, reverse=True)
        taken = 0
        for candidate in bucket_candidates:
            key = (str(candidate.get("target") or ""), candidate.get("source_id"))
            target = str(candidate.get("target") or "")
            if key in seen_ids or target_counts[target] >= per_target_cap:
                leftovers.append(candidate)
                continue
            if taken >= quota_by_bucket[bucket] or len(selected) >= max_candidates:
                leftovers.append(candidate)
                continue
            selected.append(candidate)
            seen_ids.add(key)
            target_counts[target] += 1
            taken += 1

    leftovers.extend(
        item for item in candidates
        if (str(item.get("target") or ""), item.get("source_id")) not in seen_ids
    )
    unique_leftovers: Dict[tuple[str, Any], Dict[str, Any]] = {}
    for candidate in leftovers:
        key = (str(candidate.get("target") or ""), candidate.get("source_id"))
        existing = unique_leftovers.get(key)
        if existing is None or sort_key(candidate) > sort_key(existing):
            unique_leftovers[key] = candidate

    for candidate in sorted(unique_leftovers.values(), key=sort_key, reverse=True):
        if len(selected) >= max_candidates:
            break
        target = str(candidate.get("target") or "")
        key = (target, candidate.get("source_id"))
        if key in seen_ids or target_counts[target] >= per_target_cap:
            continue
        selected.append(candidate)
        seen_ids.add(key)
        target_counts[target] += 1

    selected.sort(key=sort_key, reverse=True)
    return selected


def summarize_proposal_channels(
    candidates: List[Dict[str, Any]],
    shortlist: List[Dict[str, Any]],
) -> ProposalChannelSummary:
    """Summarize how much diversity the proposal frontier actually has."""
    candidate_channel_counts = Counter()
    shortlist_channel_counts = Counter()
    portfolio_bucket_counts = Counter(str(item.get("portfolio_bucket") or "none") for item in candidates)
    shortlist_bucket_counts = Counter(str(item.get("portfolio_bucket") or "none") for item in shortlist)
    measurement_status_counts = Counter()
    falsification_flag_counts = Counter()
    disqualifying_flag_counts = Counter()

    for candidate in candidates:
        for channel in candidate.get("proposal_channels") or []:
            candidate_channel_counts[str(channel)] += 1
        for filter_name, status in (candidate.get("measurement_status_by_filter") or {}).items():
            measurement_status_counts[f"{filter_name}:{status}"] += 1
        for flag in candidate.get("falsification_flags") or []:
            falsification_flag_counts[str(flag)] += 1
        for flag in candidate.get("disqualifying_flags") or []:
            disqualifying_flag_counts[str(flag)] += 1

    for candidate in shortlist:
        for channel in candidate.get("proposal_channels") or []:
            shortlist_channel_counts[str(channel)] += 1

    top_candidates_by_bucket: Dict[str, List[Dict[str, Any]]] = {}
    for bucket in ("conservative", "alternative", "novelty", "edge_exploration"):
        top_candidates_by_bucket[bucket] = [
            {
                "target": item.get("target"),
                "source_id": item.get("source_id"),
                "primary_channel": item.get("primary_channel"),
                "validation_score": item.get("validation_score"),
            }
            for item in shortlist
            if str(item.get("portfolio_bucket") or "") == bucket
        ][:5]

    return ProposalChannelSummary(
        candidate_count=len(candidates),
        shortlist_count=len(shortlist),
        candidate_channel_counts=dict(candidate_channel_counts),
        shortlist_channel_counts=dict(shortlist_channel_counts),
        portfolio_bucket_counts=dict(portfolio_bucket_counts),
        shortlist_bucket_counts=dict(shortlist_bucket_counts),
        measurement_status_counts=dict(measurement_status_counts),
        falsification_flag_counts=dict(falsification_flag_counts),
        disqualifying_flag_counts=dict(disqualifying_flag_counts),
        top_candidates_by_bucket=top_candidates_by_bucket,
    )
