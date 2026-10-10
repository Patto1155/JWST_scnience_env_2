"""Actual-output guards fail for the observed double-Z engineering error."""

import pytest

from discovery.research2_cloudy_composition_review import (
    actual_out_composition,
    actual_zone_composition,
)

PARAMETERS = {"metallicity_scale": 0.2, "log_CO": -0.37, "log_NC_relative_minus060": 0.0}


def test_actual_gas_output_passes_expected_composition_and_rejects_double_z():
    prefix = "Gas Phase Chemical Composition\n"
    correct = prefix + " H : 0.0000 C : -4.3788 N : -4.9788 O : -4.0088\n"
    assert actual_out_composition(correct, PARAMETERS)["actual_printed_log_CNO_over_H"]
    incorrect = prefix + " H : 0.0000 C : -5.0777 N : -5.6777 O : -4.7077\n"
    with pytest.raises(ValueError, match="disagrees"):
        actual_out_composition(incorrect, PARAMETERS)


def test_zone_numbers_are_divided_by_hydrogen_and_rounding_is_explicit():
    correct = "#abund H CARB NITR OXYG\n3.00 -1.38 -1.98 -1.01\n"
    assert actual_zone_composition(correct, PARAMETERS)["actual_zone_rows"] == 1
    incorrect = "#abund H CARB NITR OXYG\n3.00 -2.08 -2.68 -1.71\n"
    with pytest.raises(ValueError, match="disagrees"):
        actual_zone_composition(incorrect, PARAMETERS)


def test_incomplete_actual_abundance_header_fails_closed():
    with pytest.raises(ValueError, match="missing"):
        actual_out_composition("Gas Phase Chemical Composition\nC : -4.3788\n", PARAMETERS)
