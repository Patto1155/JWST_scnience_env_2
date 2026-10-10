"""Count-calibration identifiability and physically explicit conditional bounds."""

import numpy as np
import pytest

from discovery.selection_count_audit import (
    coadd_nonidentifiability,
    scalar_variance_bounds,
    weighted_source_variance,
)


def test_identical_scene_mean_and_background_weight_hide_source_variance():
    witness = coadd_nonidentifiability()
    first, second = witness["hypotheses"]
    assert (
        first["expected_calibrated_source_flux_njy"]
        == second["expected_calibrated_source_flux_njy"]
        == 20
    )
    assert first["full_err_variance_njy2"] == pytest.approx(second["full_err_variance_njy2"])
    assert first["source_component_variance_njy2"] == pytest.approx(4)
    assert second["source_component_variance_njy2"] == pytest.approx(13)


def test_exact_conditional_bounds_have_attainable_endpoints():
    counts = np.array([1.0, 3.0, 8.0])
    low, high = scalar_variance_bounds(100.0, counts)
    assert weighted_source_variance(100.0, counts, counts / counts.sum()) == pytest.approx(low)
    assert weighted_source_variance(100.0, counts, np.array([1.0, 0.0, 0.0])) == pytest.approx(high)
    rng = np.random.default_rng(27)
    for weights in rng.dirichlet(np.ones(3), size=100):
        variance = weighted_source_variance(100.0, counts, weights)
        assert low <= variance <= high


def test_independent_input_photon_draws_match_both_variance_hypotheses():
    counts = np.array([1.0, 4.0])
    rng = np.random.default_rng(300)
    photons = rng.poisson(20 * counts, size=(25000, 2))
    calibrated = photons / counts
    for weights in (np.array([0.2, 0.8]), np.array([0.8, 0.2])):
        measured = calibrated @ weights
        assert measured.mean() == pytest.approx(20, abs=0.05)
        assert measured.var() == pytest.approx(
            weighted_source_variance(20, counts, weights), rel=0.035
        )


def test_count_and_weight_constraints_fail_closed():
    for counts, weights in [
        (np.array([0.0, 4.0]), np.array([0.2, 0.8])),
        (np.array([1.0, 4.0]), np.array([0.2, 0.7])),
        (np.array([1.0, 4.0]), np.array([-0.2, 1.2])),
        (np.array([1.0, np.nan]), np.array([0.2, 0.8])),
    ]:
        with pytest.raises(ValueError):
            weighted_source_variance(20.0, counts, weights)
    with pytest.raises(ValueError):
        scalar_variance_bounds(-1.0, np.array([1.0, 4.0]))


def test_background_weight_is_not_scalar_exposure_time():
    # Same total time/given count conversion but different effective source exposure.
    first = weighted_source_variance(20.0, np.array([1.0, 4.0]), np.array([0.2, 0.8]))
    second = weighted_source_variance(20.0, np.array([1.0, 4.0]), np.array([0.8, 0.2]))
    assert 20 / first == pytest.approx(5)
    assert 20 / second == pytest.approx(20 / 13)
    assert 20 / first != pytest.approx(20 / second)


def test_public_probe_stops_at_prefix_even_when_server_ignores_range(tmp_path, monkeypatch):
    import discovery.selection_count_audit as module

    (tmp_path / 'dja_center_assoc_mosaics.html').write_text(
        '<a href="https://s3.amazonaws.com/example/association_sci.fits.gz">SCI</a>'
    )
    reads = []

    class PrefixResponse:
        status = 200
        headers = {'Content-Length': '1000000000', 'Content-Type': 'application/octet-stream'}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, size):
            reads.append(size)
            return b'x' * size

    monkeypatch.setattr(module, 'urlopen', lambda *_args, **_kwargs: PrefixResponse())
    result = module.probe_variance_products(tmp_path)
    assert reads == [4096] * 4
    assert result['actual_acquired_body_bytes'] == result['bounded_probe_cap_body_bytes']
    assert all(
        record['requests'][1]['content_range'] is None for record in result['records']
    )
