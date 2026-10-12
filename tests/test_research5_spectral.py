"""Input-boundary regressions; these synthetic arrays are not science evidence."""

import numpy as np
import pytest

from discovery.research5_spectral_pilot import measure


def test_nonfinite_or_nonmonotonic_wavelength_is_rejected():
    row = {
        "wavelength": [6000, np.nan, 6100],
        "flux": [0, 0, 0],
        "ivar": [1, 1, 1],
        "mask": [0, 0, 0],
    }
    with pytest.raises(ValueError, match="finite and strictly increasing"):
        measure(row, 6088.64, 8, (20, 40), redshift=0)


def test_truncated_line_cannot_report_full_coverage():
    wave = np.arange(6085.0, 6093.0, 0.5)
    row = {
        "wavelength": wave,
        "flux": np.ones(len(wave)),
        "ivar": np.ones(len(wave)),
        "mask": np.zeros(len(wave), dtype=int),
    }
    result = measure(row, 6088.64, 8, (20, 40), redshift=0)
    assert result["status"] == "unavailable_coverage"
    assert result["reason"] == "requested line window truncated"
