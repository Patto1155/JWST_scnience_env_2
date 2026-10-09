"""Independent controls for provenance, covariance, ionic closure and blends."""

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from data_pipeline.atomic_inputs import acquire_file, verify_bytes
from tools.jwst.atomic_grid import analyze_fit, check_fluxes, ionic_ratio, validate_grid
from tools.jwst.line_sensitivity import LINE_NAMES


def fit(flux=None, covariance=None):
    return {
        "line_flux_unit": "1e-20 erg s^-1 cm^-2",
        "lines": {
            k: {"flux": v}
            for k, v in zip(LINE_NAMES, [10, 20, 15, 5, 10] if flux is None else flux)
        },
        "line_covariance": (np.eye(5) if covariance is None else covariance).tolist(),
    }


def epsilon():
    return {"NIV": 1e-21, "CIV": 2e-21, "NIII": 1e-21, "CIII": 2e-21, "OIII": 1e-21, "HeII": 1e-24}


def assert_compact_equal(actual, expected):
    """Exact structure/lineage, tight floating tolerance across supported BLAS/NumPy."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and actual.keys() == expected.keys()
        for key in expected:
            assert_compact_equal(actual[key], expected[key])
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected)
        for value, reference in zip(actual, expected):
            assert_compact_equal(value, reference)
    elif isinstance(expected, float):
        assert isinstance(actual, (float, np.floating))
        assert actual == pytest.approx(expected, rel=1e-12, abs=1e-13)
    else:
        assert type(actual) is type(expected)
        assert actual == expected


def test_equal_ionic_abundances_have_unequal_fluxes():
    flux, cov = check_fluxes(fit())
    answer = ionic_ratio(flux, cov, epsilon(), ("NIV", "NIII"), ("CIV", "CIII"))
    # Flux N/C is 0.5, but per-ion emissivities make this ionic ratio 1.
    assert answer["value"] == pytest.approx(1)
    assert answer["log_ratio_relative_to_solar_NC_minus_0_60"] == pytest.approx(0.6)


def test_full_covariance_changes_fieller_limits():
    covariance = np.eye(5)
    covariance[0, 3] = covariance[3, 0] = 0.8
    flux, cov = check_fluxes(fit(covariance=covariance))
    correlated = ionic_ratio(flux, cov, epsilon(), ("NIV", "NIII"), ("CIV", "CIII"))
    diagonal = ionic_ratio(flux, np.eye(5), epsilon(), ("NIV", "NIII"), ("CIV", "CIII"))
    assert correlated["value"] == diagonal["value"]
    assert (
        correlated["conditional_gaussian_95_fieller_set"]
        != (diagonal["conditional_gaussian_95_fieller_set"])
    )


@pytest.mark.parametrize("covariance", [np.ones((5, 5)), np.eye(4), np.eye(5) * np.nan])
def test_invalid_covariance_is_rejected(covariance):
    with pytest.raises(ValueError):
        check_fluxes(fit(covariance=covariance))


def test_negative_ratio_does_not_become_log_abundance():
    grid = json.loads(
        (Path(__file__).resolve().parents[1] / "research_output/mom_atomic_grid.json").read_text()
    )
    answer = analyze_fit(fit([-10, 20, 15, -5, 10]), grid)
    assert answer["grid_point_ionic_log_ratio_relative_to_solar_range"] is None
    assert not answer["elemental_abundance_identified"]
    assert not answer["helium_oxygen_ionic_operator"]["HeII_OIII_separated"]


@pytest.mark.parametrize("mutation", ["nan", "negative", "cell", "unit", "transition", "version"])
def test_malformed_grid_is_rejected(mutation):
    grid = json.loads(
        (Path(__file__).resolve().parents[1] / "research_output/mom_atomic_grid.json").read_text()
    )
    grid = copy.deepcopy(grid)
    if mutation in ("nan", "negative"):
        grid["records"][0]["emissivity_erg_cm3_s"]["NIV"] = (
            float("nan") if mutation == "nan" else -1
        )
    elif mutation == "cell":
        grid["records"][0] = grid["records"][1]
    elif mutation == "unit":
        grid["emissivity_definition"] = "incorrect"
    elif mutation == "version":
        grid["pyneb_version"] = "latest"
    else:
        grid["transitions"]["NIV"][0]["requested_vacuum_A"] = 1483
    with pytest.raises(ValueError):
        validate_grid(grid)


def test_flux_units_and_sigmas_are_checked():
    malformed = fit()
    malformed["line_flux_unit"] = "Jy"
    with pytest.raises(ValueError, match="units"):
        check_fluxes(malformed)
    malformed = fit()
    malformed["lines"]["NIV"]["conditional_sigma"] = 100
    with pytest.raises(ValueError, match="sigma"):
        check_fluxes(malformed)


def test_self_consistent_atomic_member_receipt_forgery_is_rejected():
    grid = json.loads(
        (Path(__file__).resolve().parents[1] / "research_output/mom_atomic_grid.json").read_text()
    )
    grid["atomic_files"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="independently pinned"):
        validate_grid(grid)


def test_helium_oxygen_blend_operator_has_null_direction():
    e = epsilon()
    design = np.zeros((5, 6))
    design[0, 0], design[1, 1], design[3, 2], design[4, 3] = (
        e["NIV"],
        e["CIV"],
        e["NIII"],
        e["CIII"],
    )
    design[2, 4], design[2, 5] = e["HeII"], e["OIII"]
    assert np.linalg.matrix_rank(design / np.max(design)) == 5
    null = np.array([0, 0, 0, 0, e["OIII"], -e["HeII"]])
    assert np.allclose(design @ null, 0, atol=1e-60)


def test_cached_bytes_ignore_self_consistent_forged_receipt(tmp_path):
    content = b"author-pinned-version"
    target = tmp_path / "model.bin"
    target.write_bytes(b"altered-version-xxxxx")
    pinned = hashlib.sha256(content).hexdigest()
    with pytest.raises(ValueError, match="independently pinned"):
        acquire_file(tmp_path, target.name, "https://unused.invalid", pinned, len(content))
    target.write_bytes(content)
    verify_bytes(target, pinned, len(content))


def test_committed_atomic_grid_and_saved_fit_replay():
    root = Path(__file__).resolve().parents[1]
    grid = json.loads((root / "research_output/mom_atomic_grid.json").read_text())
    spectrum = json.loads((root / "research_output/mom_z14_point_resolution.json").read_text())
    saved = json.loads((root / "research_output/mom_ionic_fit.json").read_text())
    assert len(grid["records"]) == 28
    assert len(grid["atomic_files"]) == 11
    assert not grid["photoionization_grid"]
    for fit_record, result in zip(
        [spectrum["nominal_reference_fit"], spectrum["point_source_scenarios"][0]], saved["models"]
    ):
        assert_compact_equal(
            analyze_fit(fit_record, grid),
            {k: v for k, v in result.items() if k != "resolution_family"},
        )
    assert (
        saved["grid_sha256"]
        == hashlib.sha256((root / "research_output/mom_atomic_grid.json").read_bytes()).hexdigest()
    )
    assert (
        saved["spectrum_sha256"]
        == hashlib.sha256(
            (root / "research_output/mom_z14_point_resolution.json").read_bytes()
        ).hexdigest()
    )


def test_replay_tolerance_rejects_meaningful_changes_and_preserves_lineage():
    source = {"value": 8.828314179330988, "lineage": "actual-source", "identified": False}
    assert_compact_equal({**source, "value": source["value"] + 1e-14}, source)
    with pytest.raises(AssertionError):
        assert_compact_equal({**source, "value": source["value"] + 1e-5}, source)
    with pytest.raises(AssertionError):
        assert_compact_equal({**source, "lineage": "changed-source"}, source)
    with pytest.raises(AssertionError):
        assert_compact_equal({**source, "identified": 0}, source)
