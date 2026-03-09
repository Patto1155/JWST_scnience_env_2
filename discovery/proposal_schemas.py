"""Shared proposal typing for candidate-generation helpers."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


MeasurementStatus = Literal[
    "measured_detection",
    "measured_nondetection",
    "unmeasured_offchip",
    "unmeasured_low_coverage",
    "unmeasured_invalid",
]

ProposalChannelName = Literal[
    "dropout_strict",
    "dropout_loose",
    "color_color_outlier",
    "morphology_extended_red",
    "anomaly_context",
    "novel_high_snr_outlier",
]

PortfolioBucket = Literal[
    "conservative",
    "alternative",
    "novelty",
    "edge_exploration",
]


class CandidateProposalMetadata(TypedDict, total=False):
    """Shared additive metadata attached to shortlist candidates."""

    measurement_status_by_filter: dict[str, MeasurementStatus]
    measured_filters: list[str]
    unmeasured_filters: list[str]
    completeness_score: float
    proposal_channels: list[ProposalChannelName]
    primary_channel: ProposalChannelName | None
    channel_scores: dict[str, float]
    novelty_score: float
    falsification_flags: list[str]
    disqualifying_flags: list[str]
    portfolio_bucket: PortfolioBucket | None


class ProposalChannelSummary(TypedDict):
    """JSON-friendly rollup of proposal frontier composition."""

    candidate_count: int
    shortlist_count: int
    candidate_channel_counts: dict[str, int]
    shortlist_channel_counts: dict[str, int]
    portfolio_bucket_counts: dict[str, int]
    shortlist_bucket_counts: dict[str, int]
    measurement_status_counts: dict[str, int]
    falsification_flag_counts: dict[str, int]
    disqualifying_flag_counts: dict[str, int]
    top_candidates_by_bucket: dict[str, list[dict[str, Any]]]
