"""Independent oracles for signed author-release operator/provenance guards."""

import numpy as np
import pytest

from data_pipeline.mom_author_provenance import (
    FIELDS,
    pixel_table_replay,
    shared_sky_counts,
    verify_pin,
)


def toy_table():
    table = np.ones(4, dtype=[(k, "i8" if k == "exposure_index" else "f8") for k in FIELDS])
    table["wave"] = [1.0, 1.0, 2.0, 2.0]
    table["profile"] = [0.8, -0.4, 0.5, -0.5]
    table["pathloss"] = 0.5
    table["sci"] = 7 * table["profile"] * table["pathloss"]
    table["var_total"] = 4
    table["var_rnoise"] = [1.0, 2.0, 3.0, 4.0]
    table["yslit"] = [0.0, 1.0, -2.0, 3.0]
    return table


def test_known_signed_flux_pathloss_once_and_independent_linear_variance():
    table = toy_table()
    result = pixel_table_replay(table, np.array([1.0, 2.0]))
    np.testing.assert_allclose(result["flux"], [7.0, 7.0])
    for i in range(2):
        rows = table[2 * i : 2 * i + 2]
        w = 1 / rows["var_rnoise"]
        operator = w * rows["profile"] / rows["pathloss"] / np.dot(w, rows["profile"] ** 2)
        expected_variance = operator @ np.diag(rows["var_total"]) @ operator
        assert result["err"][i] ** 2 == pytest.approx(expected_variance)


@pytest.mark.parametrize("field", ["pathloss", "var_total", "var_rnoise", "exptime", "dwave_dx"])
def test_nonpositive_correction_and_variance_rejected(field):
    table = toy_table()
    table[field][0] = 0
    with pytest.raises(ValueError, match="Nonpositive"):
        pixel_table_replay(table, [1.0, 2.0])


def test_mask_range_and_wave_grid_guard():
    table = toy_table()
    for wave in ([2.0, 1.0], [1.0, 1.0], [1.0, np.nan]):
        with pytest.raises(ValueError, match="wavelengths"):
            pixel_table_replay(table, wave)
    table["yslit"][2:] = 10
    result = pixel_table_replay(table, [1.0, 2.0])
    assert not np.isfinite(result["flux"][1])
    assert result["npix"][1] == 0


def test_shared_sky_dependency_witness_is_set_count_not_covariance():
    table = np.ones(18, dtype=[(k, "i8" if k == "exposure_index" else "f8") for k in FIELDS])
    table["exposure_index"] = np.repeat(np.arange(9), 2)
    table["sky"] = np.tile([10.0, 11.0, 20.0, 21.0, 30.0, 31.0], 3)
    counts = np.array(shared_sky_counts(table))
    assert counts[0, 3] == 2
    assert counts[0, 1] == 0
    np.testing.assert_array_equal(counts, counts.T)
    table["exposure_index"][-1] = 10
    with pytest.raises(ValueError, match="nine"):
        shared_sky_counts(table)


def test_stale_or_corrupt_public_input_rejected(tmp_path):
    path = tmp_path / "pixtab.fits"
    path.write_bytes(b"wrong")
    with pytest.raises(ValueError, match="Pinned"):
        verify_pin(path, {"expected_bytes": 5, "sha256": "0" * 64})
