"""Independent photon-response integration and contributor dependence guards."""

import numpy as np
import pytest

from discovery.survivor46_medium import contributors, line_response_ratio
from discovery.survivor_deep_model import band_average


def test_single_line_response_matches_direct_photon_band_integrals():
    wide_wave = np.linspace(3.7, 5.0, 26001)
    medium_wave = np.linspace(4.0, 4.2, 4001)
    medium = (medium_wave, np.ones_like(medium_wave))
    wide = (wide_wave, np.ones_like(wide_wave))
    center, width = 4.1, 0.0003

    def spectrum(wave):
        # Arbitrary F_lambda Gaussian converted to F_nu; common c cancels.
        return wave**2 * np.exp(-0.5 * ((wave - center) / width) ** 2)

    directly_integrated = band_average(*medium, spectrum(medium_wave)) / band_average(
        *wide, spectrum(wide_wave)
    )
    predicted = float(line_response_ratio(center, medium, wide))
    assert predicted == pytest.approx(directly_integrated, rel=1e-7)
    assert float(line_response_ratio(4.5, medium, wide)) == 0.0
    assert np.isnan(line_response_ratio(5.2, medium, wide))


def test_contributors_retain_exact_files_and_cannot_prove_visit_independence():
    bundle = {
        "header": {"FLT00002": "jw-a2_rate.fits", "FLT00001": "jw-a1_rate.fits", "OTHER": "jw-no"}
    }
    assert contributors(bundle) == ["jw-a1_rate.fits", "jw-a2_rate.fits"]
