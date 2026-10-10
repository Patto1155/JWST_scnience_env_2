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


def test_replayed_model_cannot_omit_a_line_or_substitute_zero_template():
    from tools.jwst.cloudy_pilot import group_predictions

    for values in (np.ones(13), np.ones(14), np.r_[np.ones(28), np.nan]):
        with pytest.raises(ValueError, match="29line thermal response"):
            group_predictions({"intrinsic_line_values": values})
    values = np.ones(29)
    values[:2] = 0
    with pytest.raises(ValueError, match="explicit direct-template"):
        group_predictions({"intrinsic_line_values": values})


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


def test_model_timeout_retains_exception_receipt_without_incomplete_flux(tmp_path, monkeypatch):
    import json
    import subprocess

    from tools.jwst.cloudy_pilot import execute_model, pilot_parameters

    executable = tmp_path / "model.exe"
    executable.write_bytes(b"pinned model executable")

    def capped(*args, **kwargs):
        assert kwargs["timeout"] == 1200
        assert kwargs["env"]["OPENBLAS_NUM_THREADS"] == "1"
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", capped)
    run = tmp_path / "run"
    with pytest.raises(subprocess.TimeoutExpired):
        execute_model(executable, run, pilot_parameters()[0], "model000", timeout_seconds=1200)
    receipt = json.loads((run / "model000.failure.json").read_text())
    assert receipt["status"] == "hard_wall_time_cap"
    assert receipt["wall_time_cap_seconds"] == 1200
    assert receipt["complete_thermal_prediction_used"] is False
    assert "intrinsic_line_values" not in receipt
    assert len(receipt["input_sha256"]) == len(receipt["executable_sha256"]) == 64


def test_failed_preflight_cancels_unstarted_grid_and_keeps_failure_artifact(tmp_path, monkeypatch):
    import json
    import sys
    import time

    import tools.jwst.cloudy_pilot as pilot

    executable = tmp_path / "model.exe"
    executable.write_bytes(b"pinned model executable")
    run = tmp_path / "run"
    run.mkdir()
    output = tmp_path / "pilot.json"
    attempted = []

    def controlled(executable, directory, parameters, name, **kwargs):
        attempted.append(name)
        if name == "model000":
            raise ValueError("independent injected convergence failure")
        # Already-started work can finish, but the unstarted grid must cancel.
        time.sleep(0.05)
        return {
            "id": name,
            "parameters": parameters,
            "runtime_seconds": 0.05,
            "convergence_summary": "controlled successful engineering task",
        }

    monkeypatch.setattr(pilot, "execute_model", controlled)
    monkeypatch.setattr(pilot, "verify", lambda path: {"verified_test_archive": True})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pilot",
            "--cloudy-directory",
            str(tmp_path),
            "--run-directory",
            str(run),
            "--executable",
            str(executable),
            "--workers",
            "1",
            "--limit",
            "20",
            "--output",
            str(output),
        ],
    )
    with pytest.raises(SystemExit) as failure:
        pilot.main()
    assert failure.value.code == 1
    receipt = json.loads(output.read_text())
    assert receipt["failed_models"][0]["id"] == "model000"
    assert receipt["failed_models"][0]["complete_thermal_prediction_used"] is False
    assert len(attempted) <= 2
    assert (
        len(receipt["models"]) + len(receipt["failed_models"]) + len(receipt["cancelled_models"])
        == 20
    )
    assert (run / "model000.failure.json").exists()


def test_rate_bridge_rejects_changed_physical_operator_between_noise_alternatives(monkeypatch):
    import tools.jwst.cloudy_pilot as pilot
    import tools.jwst.native_rate_noise as rate

    def changed(report, *, empirical):
        return {"signed_response_coupling": np.eye(3)[None] + float(empirical)}

    monkeypatch.setattr(rate, "load_rate_noise_replay", changed)
    with pytest.raises(ValueError, match="changed physical operator"):
        pilot.native_likelihood([], rate_noise_report=Path("unused-report.json"))


def test_rate_heldout_uses_fresh_operator_without_legacy_receipt(monkeypatch):
    import json

    import tools.jwst.cloudy_pilot as pilot

    report = pilot.ROOT / "research_output/mom_native_rate_noise.json"
    model = json.loads((pilot.ROOT / "research_output/mom_cloudy_first_model.json").read_text())[
        "models"
    ][0]

    def unavailable_legacy(*args, **kwargs):
        raise AssertionError("fresh RATE inference must not require the obsolete operator")

    monkeypatch.setattr(pilot, "signed_coupling", unavailable_legacy)
    result = pilot.held_out_likelihood([model], rate_noise_report=report)
    assert "RATE_empirical_v3" in result["configuration"]
    assert result["noise_contract_report_sha256"] == pilot.digest(report)
    assert len(result["records"]) == 3
    assert {item["held_out_RATE_group"] for item in result["records"]} == {"03", "05", "07"}
