"""Synthetic coverage guards preserve signed rows and reject invalid noise."""

import numpy as np

from data_pipeline.capers_pixtab_coverage import counts
from data_pipeline.mom_author_provenance import FIELDS


def test_usable_coverage_is_not_positive_flux_or_positive_profile_selection():
    table = np.ones(5, dtype=[(name, float) for name in FIELDS])
    table["wave"] = [2.5, 2.5, 2.5, 4.5, 2.5]
    table["yslit"] = 0
    table["profile"] = [-1, 1, 0, 1, 1]
    table["sci"] = [-99, -99, 10, 1, 1]
    table["var_total"][1] = -1
    table["pathloss"][4] = np.nan
    result = counts(table, np.ones(5, dtype=bool))
    assert result["uv_rows"] == 4
    assert result["usable_rows"] == 2
    assert result["usable_uv_rows"] == 1
    assert result["negative_profile_rows"] == 1
    assert result["finite_all_fields_rows"] == 4


def test_cross_dispersion_contract_retains_boundary_and_excludes_outer_rows():
    table = np.ones(3, dtype=[(name, float) for name in FIELDS])
    table["wave"] = 2.5
    table["yslit"] = [-3, 3, 3.0001]
    result = counts(table, np.ones(3, dtype=bool))
    assert result["usable_uv_rows"] == 2
