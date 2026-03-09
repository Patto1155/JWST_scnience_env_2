"""Focused tests for candidate measurability and proposal channels."""

from __future__ import annotations

from discovery.proposal_channels import (
    attach_proposal_metadata,
    build_portfolio_shortlist,
    classify_measurement_status,
)


def _measurement(
    *,
    coverage_fraction: float,
    pixels_in_aperture: int = 28,
    valid_pixel_count: int = 28,
    background_subtracted_flux: float = 0.0,
    snr: float | None = 0.0,
) -> dict:
    return {
        "coverage_fraction": coverage_fraction,
        "pixels_in_aperture": pixels_in_aperture,
        "valid_pixel_count": valid_pixel_count,
        "background_subtracted_flux": background_subtracted_flux,
        "snr": snr,
    }


def _candidate() -> dict:
    return {
        "target": "GS-MEDIUM-HST",
        "source_id": 101,
        "reference_dataset": "demo_f444",
        "f090_dataset": "demo_f090",
        "f200_dataset": "demo_f200",
        "f444_flux": 120.0,
        "ratio_f090_f444": 0.02,
        "red_snr_r3": 12.0,
        "coverage_fraction_r3": 1.0,
        "edge_distance_px": 64.0,
        "aperture_checks": [
            {"dropout_lt_0p05": True},
            {"dropout_lt_0p05": True},
            {"dropout_lt_0p05": True},
        ],
        "photometry_by_filter": {
            "F090W": {"3": _measurement(coverage_fraction=1.0, background_subtracted_flux=0.0, snr=0.2)},
            "F200W": {"3": _measurement(coverage_fraction=1.0, background_subtracted_flux=35.0, snr=6.0)},
            "F444W": {"2": _measurement(coverage_fraction=1.0, background_subtracted_flux=70.0, snr=11.0),
                      "3": _measurement(coverage_fraction=1.0, background_subtracted_flux=120.0, snr=12.0),
                      "5": _measurement(coverage_fraction=1.0, background_subtracted_flux=165.0, snr=13.0)},
        },
    }


def test_classify_measurement_status_marks_low_coverage_as_unmeasured() -> None:
    """Low coverage should not be treated as a usable nondetection."""
    status = classify_measurement_status(
        _measurement(coverage_fraction=0.0, background_subtracted_flux=0.0, snr=None),
    )

    assert status == "unmeasured_low_coverage"


def test_attach_proposal_metadata_blocks_strict_dropout_when_blue_unmeasured() -> None:
    """Strict dropout should disappear when the blue band is not actually measured."""
    candidate = _candidate()
    candidate["photometry_by_filter"]["F090W"]["3"] = _measurement(
        coverage_fraction=0.0,
        background_subtracted_flux=0.0,
        snr=None,
    )

    metadata = attach_proposal_metadata(
        candidate,
        color_baseline=None,
        anomalous_dataset_names=set(),
    )

    assert metadata["measurement_status_by_filter"]["F090W"] == "unmeasured_low_coverage"
    assert "dropout_strict" not in metadata["proposal_channels"]
    assert "blue_unmeasured" in metadata["disqualifying_flags"]


def test_build_portfolio_shortlist_preserves_non_dropout_buckets() -> None:
    """Portfolio shortlist should retain novelty candidates instead of pure score sorting."""
    candidates = [
        {
            "target": "A",
            "source_id": 1,
            "validation_score": 0.95,
            "novelty_score": 0.1,
            "channel_scores": {"dropout_strict": 0.95},
            "f444_flux": 200.0,
            "portfolio_bucket": "conservative",
        },
        {
            "target": "A",
            "source_id": 2,
            "validation_score": 0.82,
            "novelty_score": 0.7,
            "channel_scores": {"color_color_outlier": 0.8},
            "f444_flux": 110.0,
            "portfolio_bucket": "alternative",
        },
        {
            "target": "B",
            "source_id": 3,
            "validation_score": 0.65,
            "novelty_score": 0.9,
            "channel_scores": {"anomaly_context": 0.85},
            "f444_flux": 90.0,
            "portfolio_bucket": "novelty",
        },
    ]

    shortlist = build_portfolio_shortlist(candidates, max_candidates=3)

    assert len(shortlist) == 3
    assert {item["portfolio_bucket"] for item in shortlist} == {
        "conservative",
        "alternative",
        "novelty",
    }
