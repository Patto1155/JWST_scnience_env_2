"""Independent arithmetic and scientific-contract checks for the bounded pilot."""

import numpy as np
import pytest

from discovery.selection_pilot import aperture_operator, classify, poisson_profile, profiles


def test_signed_aperture_annulus_rejects_constant_and_plane():
    weights = aperture_operator(49, 0.05)
    yy, xx = np.mgrid[:49, :49] - 24
    assert np.sum(weights) == pytest.approx(0, abs=1e-13)
    assert np.sum(weights * (2 + xx * 0.3 - yy * 0.2)) == pytest.approx(0, abs=1e-12)
    assert np.any(weights < 0)


def test_source_counts_moments_and_gain_dependence():
    profile = np.zeros((3, 3))
    profile[1, 1] = 1
    for gain in (1.0, 10.0):
        rng = np.random.default_rng(100)
        totals = np.array([poisson_profile(profile, 20.0, gain, rng).sum() for _ in range(12000)])
        assert abs(totals.mean() - 20) < 0.15
        assert totals.var() == pytest.approx(20 / gain, rel=0.04)


def test_fresh_counts_are_not_flux_renormalized():
    profile = np.ones((3, 3)) / 9
    rng = np.random.default_rng(8)
    values = [poisson_profile(profile, 10.0, 1.0, rng).sum() for _ in range(20)]
    assert len(set(values)) > 1
    assert np.mean(values) > 0


def test_profile_variants_conserve_declared_finite_stamp_flux():
    yy, xx = np.mgrid[:49, :49] - 24
    psf = np.exp(-(xx**2 + yy**2) / 8)
    psf /= psf.sum()
    result = profiles(psf, 0.05)
    for profile in result.values():
        assert profile.sum() == pytest.approx(1)
        assert np.min(profile) >= 0
    assert result["pair"][24, 24] < result["point"][24, 24]
    assert np.sum(result["extended"] * (xx**2 + yy**2)) > np.sum(psf * (xx**2 + yy**2))


def test_signed_blue_measurement_and_explicit_red_gate():
    assert classify({"F090W": -2.0, "F200W": 0.0, "F444W": 20.0}, 5) == "red"
    assert classify({"F090W": -2.0, "F200W": 0.0, "F444W": 20.0}, 4.9) == "below_red_gate"
    assert classify({"F090W": 20.0, "F200W": 20.0, "F444W": 20.0}, 8) == "blue"
    assert classify({"F090W": 2.0, "F200W": 4.0, "F444W": -1.0}, 8) == "below_red_gate"


def test_poisson_fails_closed_on_unphysical_nuisance():
    rng = np.random.default_rng(1)
    for profile, flux, gain in [
        (np.ones((3, 3)), 10, 1),
        (np.ones((3, 3)) / 9, -1, 1),
        (np.ones((3, 3)) / 9, 10, 0),
    ]:
        with pytest.raises(ValueError):
            poisson_profile(profile, flux, gain, rng)


def test_execution_checks_frozen_plan_before_any_measurement(monkeypatch, tmp_path):
    import discovery.selection_pilot as pilot

    monkeypatch.setattr(pilot, "build_plan", lambda *_: ({"fixed": 1}, {}, {}))
    with pytest.raises(ValueError, match="Frozen selection plan"):
        pilot.execute({"fixed": 2}, tmp_path, tmp_path)


def test_native_poisson_transport_counterexample_has_shared_photon_covariance():
    from discovery.selection_pilot import count_transport_counterexample

    result = count_transport_counterexample()
    covariance = np.array(result["transported_covariance"])
    assert covariance[0, 1] == pytest.approx(5)
    assert np.ones(2) @ covariance @ np.ones(2) == pytest.approx(20)
    assert result["signed_difference_variance_transport_vs_output"] == [0.0, 20.0]
