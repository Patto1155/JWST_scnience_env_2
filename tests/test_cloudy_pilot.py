"""Independent numerical identities and fail-closed full-line model contracts."""

from pathlib import Path

import numpy as np
import pytest
from scipy.optimize import lsq_linear

from tools.jwst.cloudy_pilot import (
    LINES,
    SLICES,
    profile_normalization,
    projected_native_fit,
    read_line_output,
)
from tools.jwst.native_measurement_validation import apply_signed_response


def test_projected_line_constraint_equals_direct_full_native_fit():
    """Alternative-template covariance is a projection, not new evidence/determinant."""
    rng = np.random.default_rng(319)
    continuum = rng.normal(size=(35, 2))
    lines = rng.normal(size=(35, 5))
    design = np.column_stack((continuum, lines))
    factor = rng.normal(size=(35, 35))
    covariance = factor @ factor.T + np.eye(35)
    whitening = np.linalg.cholesky(covariance)
    observed = rng.normal(size=35)
    a = np.linalg.solve(whitening, design)
    y = np.linalg.solve(whitening, observed)
    coefficients = np.linalg.lstsq(a, y, rcond=None)[0]
    coefficient_covariance = np.linalg.inv(a.T @ a)
    residual = y - a @ coefficients
    for prediction in (np.array([0.2, 0.4, 2.0, 0.05, 1.0]), np.arange(1.0, 6.0)):
        projected = profile_normalization(
            coefficients[2:], coefficient_covariance[2:, 2:], prediction
        )
        restricted = np.column_stack((a[:, :2], a[:, 2:] @ prediction))
        independent = lsq_linear(
            restricted, y, bounds=([-np.inf, -np.inf, 0.0], np.inf), tol=1e-13, lsq_solver="exact"
        )
        expected = np.sum((restricted @ independent.x - y) ** 2)
        assert np.isclose(
            residual @ residual + projected["profiled_group_chi2"], expected, rtol=1e-11, atol=1e-11
        )


def test_signed_flux_and_offdiagonal_covariance_are_retained():
    flux = np.array([-0.5, 0.2, -0.1, 0.3, 0.5])
    covariance = 0.3 * np.ones((5, 5)) + np.eye(5)
    prediction = np.arange(1.0, 6.0)
    full = profile_normalization(flux, covariance, prediction)
    diagonal = profile_normalization(flux, np.diag(np.diag(covariance)), prediction)
    clipped = profile_normalization(np.maximum(flux, 0), covariance, prediction)
    assert full["profiled_group_chi2"] != diagonal["profiled_group_chi2"]
    assert full["profiled_group_chi2"] != clipped["profiled_group_chi2"]
    negative = profile_normalization(-np.ones(5), np.eye(5), prediction)
    assert negative["common_nonnegative_normalization"] == 0
    assert negative["profiled_group_chi2"] == 5


def _fixture(path: Path, *, missing=False, blend_error=False):
    values = np.ones(len(LINES))
    values[14:19] = [values[selection].sum() for selection in SLICES]
    if blend_error:
        values[14] += 1
    labels = LINES[:-1] if missing else LINES
    header = "#lineslist\t" + "\t".join(f"{label} {wave:.2f}A" for label, wave in labels)
    path.write_text(header + "\niteration 3\t" + "\t".join(str(v) for v in values) + "\n")


def test_complete_line_identities_and_sums(tmp_path):
    path = tmp_path / "model.lin"
    _fixture(path)
    assert len(read_line_output(path)) == len(LINES)
    _fixture(path, missing=True)
    with pytest.raises(ValueError, match="identity absent"):
        read_line_output(path)
    _fixture(path)
    text = path.read_text().replace("N  4 1483.32A\tN  4 1486.50A", "N  4 1486.50A\tN  4 1483.32A")
    path.write_text(text)
    with pytest.raises(ValueError, match="misplaced"):
        read_line_output(path)
    _fixture(path, blend_error=True)
    with pytest.raises(ValueError, match="independently summed"):
        read_line_output(path)


def test_actual_abundance_output_rejects_double_metallicity_scaling(tmp_path):
    from tools.jwst.cloudy_pilot import pilot_parameters, validate_abundances

    parameters = pilot_parameters()[0]
    path = tmp_path / "actual.abn"
    path.write_text("#abund H CARB NITR OXYG\n3.00 -1.38 -1.98 -1.01\n")
    assert validate_abundances(path, parameters)["OXYG"]["actual_log_XH_range"] == [-4.01, -4.01]
    path.write_text("#abund H CARB NITR OXYG\n3.00 -2.08 -2.68 -1.71\n")
    with pytest.raises(ValueError, match="declared gas composition"):
        validate_abundances(path, parameters)


def test_signed_native_physical_constraint_matches_independent_direct_fit():
    """Signed ghosts act before full-native likelihood, with no determinant shortcut."""
    rng = np.random.default_rng(319)
    source_design = rng.normal(size=(60, 7))
    coupling = np.broadcast_to(
        np.array([[1, -0.2, -0.3], [-0.3, 1, -0.2], [-0.2, -0.3, 1]]), (20, 3, 3)
    ).copy()
    design = apply_signed_response(source_design, coupling)
    factor = rng.normal(size=(60, 60))
    covariance = factor @ factor.T + np.eye(60)
    chol = np.linalg.cholesky(covariance)
    observed = rng.normal(size=60)
    y = np.linalg.solve(chol, observed)
    fit = projected_native_fit(design, chol, y)
    prediction = np.array([0.03, 0.8, 0.4, 0.2, 1.0])
    profile = profile_normalization(
        np.asarray(fit["fluxes"]), np.asarray(fit["flux_covariance"]), prediction
    )
    full_physical_design = np.column_stack((design[:, :2], design[:, 2:] @ prediction))
    whitened = np.linalg.solve(chol, full_physical_design)
    independent = lsq_linear(
        whitened, y, bounds=([-np.inf, -np.inf, 0.0], np.inf), tol=1e-13, lsq_solver="exact"
    )
    assert np.isclose(
        fit["conditional_chi2"] + profile["profiled_group_chi2"],
        np.sum((whitened @ independent.x - y) ** 2),
        rtol=1e-11,
    )
    assert not np.allclose(design, source_design)
