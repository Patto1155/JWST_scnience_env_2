"""Scientific normalization and sampling controls for independent stellar review."""

import numpy as np
import pytest

from discovery.research5_stellar_review import EPOCH_BTJD, FREQUENCY, SIDEBANDS, fit_mode


def test_integration_aware_mode_recovers_semia_amplitude_with_trend_and_gaps():
    cadence = 1 / 48
    time = np.arange(1711, 1737, cadence)
    time = time[(time < 1723) | (time > 1724)]
    flux = (
        0.001
        * np.sinc(FREQUENCY * cadence)
        * np.cos(2 * np.pi * FREQUENCY * (time - EPOCH_BTJD) + 0.42)
    )
    flux += 0.004 + 0.0004 * (time - time.mean()) ** 2
    result = fit_mode(time, flux, cadence)
    assert result["amplitude_ppm"] == pytest.approx(1000, abs=1e-6)
    assert result["integration_aware_1000ppm_control_recovery"] == pytest.approx(1000, abs=1e-6)


def test_one_point_segment_does_not_make_zero_nuisance_columns_invalid():
    cadence = 1 / 48
    time = np.r_[np.arange(1711, 1736, cadence), 1737.0]
    flux = (
        0.001 * np.sinc(FREQUENCY * cadence) * np.cos(2 * np.pi * FREQUENCY * (time - EPOCH_BTJD))
    )
    result = fit_mode(time, flux, cadence)
    assert result["zero_nuisance_columns_removed"] == 2
    assert result["amplitude_ppm"] == pytest.approx(1000, abs=1e-6)
    assert result["all_parameters_identifiable"]


def test_exact_sideband_operator_envelope_covers_a_sampled_coherent_blend():
    cadence = 1 / 48
    time = np.arange(1711, 1737, cadence)
    flux = np.zeros_like(time)
    for phase, (frequency, amplitude) in zip((0.12, 1.75, -2.9), SIDEBANDS, strict=True):
        flux += (
            amplitude
            * 1e-6
            * np.sinc(frequency * cadence)
            * np.cos(2 * np.pi * frequency * (time - EPOCH_BTJD) + phase)
        )
    result = fit_mode(time, flux, cadence)
    assert result["amplitude_ppm"] <= result["known_sideband_phase_envelope_ppm"]
