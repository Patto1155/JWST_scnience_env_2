"""Independent source-spectrum coverage and complete-pagination invariants."""

import numpy as np

from data_pipeline.capers_companion_coverage import replay, spectrum_counts


def test_coverage_retains_negative_flux_and_requires_actual_support():
    table = np.ones(
        4,
        dtype=[
            ("WAVELENGTH", float),
            ("FLUX", float),
            ("FLUX_ERROR", float),
            ("NPIXELS", float),
            ("DQ", int),
        ],
    )
    table["WAVELENGTH"] = [2.3, 2.4, 2.5, 4.5]
    table["FLUX"] = -9
    table["DQ"] = [0, 1, 0, 0]
    table["NPIXELS"][2] = 0
    result = spectrum_counts(table)
    assert result["uv_rows"] == 3 and result["usable_uv_rows"] == 1
    assert result["usable_rows"] == 2


def test_actual_combined_source_inventory_has_real_gap():
    report = replay()
    assert report["association_product_rows"] == 630
    assert report["unique_product_filenames"] == 553
    assert report["nrs1_science_members"] == report["nrs2_science_members"] == 18
    assert report["target_acquisition_member_count"] == 8
    assert report["source"]["SOURCEID"] == 102896
    assert report["coverage"] == {
        "rows": 277,
        "usable_rows": 249,
        "uv_rows": 0,
        "usable_uv_rows": 0,
        "nonpositive_npixels_rows": 28,
    }
    assert report["largest_adjacent_gap_um"][0] < 2.15
    assert report["largest_adjacent_gap_um"][1] > 3.2
