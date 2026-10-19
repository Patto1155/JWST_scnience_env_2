"""Selection invariants matter before outcome access."""

import numpy as np
import pytest

from data_pipeline.independent_line_selection import covariance_sensitivity, select, summarize


def records(n=70):
    return [{"unique_id": f"goods-s-mediumjwst_{i:06d}", "field": "GS", "z": 3.,
             "lines": {name: {"flux": 7., "error": 1., "configuration": "g235m_f170lp"}
                       for name in ("O3_5007", "HBaB_4861")}} for i in range(n)]


def test_target_nan_negative_and_zero_snr_are_not_selection_cuts():
    data = records()
    for row in data:
        row["lines"]["HBaB_4861"]["flux"] = np.nan
        row["lines"]["HBaB_4861"]["error"] = -1.
    # Reverse direction lacks eligible selectors: exact quota fails, never quietly replaces.
    with pytest.raises(ValueError, match="Fewer than 30"):
        select(data, set())
    for row in data[35:]:
        row["lines"]["HBaB_4861"].update(flux=7., error=1.)
        row["lines"]["O3_5007"].update(flux=-10., error=1.)
    chosen = select(data, set())["rows"]
    assert len(chosen) == 30
    assert sum(np.isnan(r["published_flux"]) for r in chosen) == 15
    assert sum(r["published_flux"] < 0 for r in chosen) == 15


def test_old_object_exclusion_and_no_reuse_are_deterministic():
    data = records()
    excluded = {r["unique_id"] for r in data[:30]}
    first = select(data, excluded)
    assert first == select(data[::-1], excluded)
    ids = [r["unique_id"] for r in first["rows"]]
    assert len(set(ids)) == 30
    assert not set(ids) & excluded


def test_mixed_field_cannot_leak_and_duplicate_identity_rejected():
    data = records()
    for row in data[:40]:
        row["field"] = "GN"
        row["unique_id"] = row["unique_id"].replace("goods-s", "goods-n")
    chosen = select(data, set())
    assert all(r["unique_id"].startswith("goods-s") for r in chosen["rows"])
    with pytest.raises(ValueError, match="Duplicate"):
        select(data + [data[0]], set())


def test_log_invalid_rows_remain_in_denominator_and_no_claim_of_independence():
    rows = [{"unique_id": str(i), "fit_flux": flux, "published_flux": 10.,
             "published_error": 1.} for i, flux in enumerate([-1., 8., 9., 10.])]
    result = summarize(rows, -.04, -.96, repeats=50)
    assert result["selected"] == 4
    assert result["positive_pairs"] == 3
    assert result["omitted_log_pairs"] == 1
    assert result["decision"] == "INCONCLUSIVE"
    assert "pull" not in result


def test_synthetic_covariance_grid_is_labeled_and_denominators_preserved():
    report = covariance_sensitivity(1000)
    assert "Synthetic" in report["scope"]
    assert len(report["cells"]) == 15
    assert all(0 <= c["invalid_log_pairs"] <= c["selected"] <= 1000 for c in report["cells"])
