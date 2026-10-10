"""Independent Gaussian shape and nuisance-projection invariants for the pilot."""

import numpy as np

from tools.jwst.line_sensitivity import C_KMS, line_matrix
from tools.jwst.native_local_identifiability import effective_resolution, projected_diagnostics


def test_gaussian_intrinsic_width_has_exact_unknown_lsf_counterexample():
    wave = np.linspace(2.24, 3.15, 100)
    rw = np.linspace(0.6, 5.3, 120)
    resolution = 60 + rw * 20
    components = [([w], [1.0]) for w in (1485, 1550, 1640, 1750, 1908)]
    centers = np.array([w[0][0] * 1e-4 * 15.44 for w in components])
    grid = np.unique(np.concatenate([rw, centers]))
    for width in (300.0, 1000.0):
        intrinsic = line_matrix(wave, rw, resolution, components=components, intrinsic_fwhm=width)
        # Direct variance formula, independently of the helper under test.
        observed_r = np.interp(grid, rw, resolution)
        expected = 1 / np.sqrt(observed_r**-2 + (width / C_KMS) ** 2)
        np.testing.assert_allclose(effective_resolution(observed_r, width), expected)
        calibration = line_matrix(wave, grid, expected, components=components)
        np.testing.assert_allclose(intrinsic, calibration, atol=3e-12, rtol=2e-13)


def test_centroid_calibration_equivalence_uses_fixed_detector_bins():
    wave = np.linspace(2.24, 3.15, 100)
    rw = np.array([0.6, 5.3])
    resolution = np.array([70.0, 170.0])
    components = [([w], [1.0]) for w in (1485, 1550, 1640, 1750, 1908)]
    for z in (14.42, 14.46):
        assigned = [(np.array(rest) * ((1 + z) / 15.44), weights) for rest, weights in components]
        physical = line_matrix(wave, rw, resolution, components=components, redshift=z)
        shifted = line_matrix(wave, rw, resolution, components=assigned)
        np.testing.assert_allclose(physical, shifted, atol=3e-12, rtol=2e-13)


def test_projection_removes_nuisance_and_preserves_orthogonal_change():
    design = np.array([[1.0], [1.0], [1.0]])
    result = projected_diagnostics(
        design, np.eye(3), {"absorbed": np.ones(3), "orthogonal": np.array([1.0, 0.0, -1.0])}
    )
    np.testing.assert_allclose(result["projected_plugin_SNR"], [0, np.sqrt(2)], atol=1e-14)
