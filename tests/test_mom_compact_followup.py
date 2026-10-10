"""Independent selector timing and compact pixel identity/coverage guards."""

import pytest

from data_pipeline.mom_compact_followup import replay, select_wavecorr


def test_selector_uses_latest_eligible_date_and_correct_exposure_mode():
    text = """
selector = Match({
    'NRS_MSASPEC': UseAfter({'2020-01-01 00:00:00': 'old.asdf',
                           '2025-01-01 00:00:00': 'new.asdf'}),
    'NRS_FIXEDSLIT|NRS_BRIGHTOBJ': UseAfter({'2010-01-01 00:00:00': 'other.asdf'})
})
"""
    assert select_wavecorr(text, "NRS_MSASPEC", "2024-12-31 23:59:59") == "old.asdf"
    assert select_wavecorr(text, "NRS_MSASPEC", "2025-01-01 00:00:00") == "new.asdf"
    assert select_wavecorr(text, "NRS_BRIGHTOBJ", "2025-01-01 00:00:00") == "other.asdf"
    with pytest.raises(ValueError, match="before observation"):
        select_wavecorr(text, "NRS_MSASPEC", "2019-01-01 00:00:00")


def test_selector_rejects_ambiguous_modes_and_arbitrary_calls():
    with pytest.raises(ValueError, match="ambiguous"):
        select_wavecorr(
            "selector = Match({'A': UseAfter({}), 'A|B': UseAfter({})})", "A", "2020-01-01 00:00:00"
        )
    with pytest.raises(ValueError, match="Unexpected matching"):
        select_wavecorr("selector = exec('anything')", "A", "2020-01-01 00:00:00")


def test_compact_actual_coverage_does_not_measure_nitrogen():
    report = replay()
    assert report["contributor_count"] == 18 and report["usable_bins"] == 195
    assert report["response_bytes"] == 718228
    assert report["new_selected_payload_bytes"] == 701775
    assert report["pinned_reference_restoration_bytes"] == 16453
    assert report["pedigree"] == "DUMMY" and not report["empirical_calibration_gained"]
    assert all(not row["inside_usable_range"] for row in report["known_z14p44_UV_groups"].values())
    assert all(
        row["inside_usable_range"]
        for row in report["weak_catalog_z6p13832_conditional_lines"].values()
    )
