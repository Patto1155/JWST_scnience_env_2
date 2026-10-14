"""The raw-repeat preflight must stop before overspending or relabeling data."""

import pytest

from discovery.smacs_raw_preflight import DATA_CAP, planned_budget


def test_raw_pair_leaves_exact_reference_allowance():
    result = planned_budget([100, 200], already_charged=30)
    assert result["remaining_for_calibration_and_epoch_bytes"] == DATA_CAP - 330


def test_raw_pair_over_cap_fails_before_transfer():
    with pytest.raises(ValueError, match="exceeds"):
        planned_budget([DATA_CAP, 1])


@pytest.mark.parametrize("sizes", [[0, 1], [-1, 1], [1], [1, 2, 3], [1.0, 2], [True, 2]])
def test_unknown_or_invalid_product_lengths_block_transfer(sizes):
    with pytest.raises(ValueError, match="positive integer"):
        planned_budget(sizes)
