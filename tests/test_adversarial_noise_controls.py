"""Known signed covariance counterexamples; assertions are not implementation mirrors."""

import numpy as np
import pytest
from scipy.signal import fftconvolve

from discovery.adversarial_noise_controls import aperture_operator, exact_noise_multiplier
from discovery.psf_noise import blank_aperture_report


def test_white_identity_and_uniform_sky_cancellation():
    operator = aperture_operator()
    assert exact_noise_multiplier(operator, np.ones((1, 1))) == pytest.approx(1)
    assert operator.sum() == pytest.approx(0, abs=1e-13)
    # A perfectly coherent constant fluctuation cancels, despite positive covariance.
    coherent_variance = float(
        operator.ravel() @ np.ones((operator.size, operator.size)) @ operator.ravel()
    )
    assert abs(coherent_variance) < 1e-12


@pytest.mark.parametrize("axis, expected_region", [([1, 2, 1], (2, 3)), ([-1, 2, -1], (0.2, 0.6))])
def test_empirical_noise_handles_inflation_and_deflation(axis, expected_region):
    kernel = np.outer(axis, axis).astype(float)
    expected = exact_noise_multiplier(aperture_operator(), kernel)
    assert expected_region[0] < expected < expected_region[1]
    kernel /= np.sqrt(np.sum(kernel**2))
    image = fftconvolve(np.random.default_rng(23).normal(size=(768, 768)), kernel, mode="same")
    measured = blank_aperture_report(
        {"sci": image, "err": np.ones(image.shape), "header": {"BUNIT": "nJy"}},
        radii=(0.189,),
        pixel_scale_arcsec=0.063,
        mask=np.zeros(image.shape, bool),
        synthetic=True,
        bootstrap=100,
    )["apertures"][0]
    assert measured["noise_multiplier"] == pytest.approx(expected, rel=0.08)
    # Numerical covariance identity alone would pass even with a wrong noise model;
    # agreement with this independently specified stochastic oracle is the test.
    interval = measured["noise_multiplier_block_bootstrap_95"]
    assert interval[0] <= expected <= interval[1]
