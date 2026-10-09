"""Physical-template receipt, independent quadrature and fresh covariance controls."""

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from tools.jwst.line_sensitivity import LINE_COMPONENTS, bin_edges, line_matrix
from tools.jwst.multiplet_refit import run, validate_component_grid
from tools.jwst.native_reduction import fit_native, load_native_replay, replay_report

ROOT = Path(__file__).resolve().parents[1]


def inputs():
    atomic_path = ROOT / "research_output/mom_atomic_grid.json"
    return (
        json.loads(atomic_path.read_text()),
        json.loads((ROOT / "research_output/mom_multiplet_components.json").read_text()),
        hashlib.sha256(atomic_path.read_bytes()).hexdigest(),
    )


@pytest.mark.parametrize("mutation", ["negative", "nan", "zero", "length", "wave", "blend"])
def test_explicit_components_reject_invalid_shapes_and_blend_rewrites(mutation):
    components = [[list(w), list(a)] for w, a in LINE_COMPONENTS]
    if mutation in ("negative", "nan", "zero"):
        components[0][1] = [{"negative": -1, "nan": np.nan, "zero": 0}[mutation]]
    elif mutation == "length":
        components[1][1] = [1]
    elif mutation == "wave":
        components[0][0] = [np.inf]
    with pytest.raises(ValueError):
        line_matrix(
            np.linspace(2.15, 3.2, 300),
            np.array([1, 5]),
            np.array([100, 100]),
            components=components,
            blend="HeII_only" if mutation == "blend" else "equal_HeO",
        )


def test_normalized_components_do_not_mutate_caller_weights_or_defaults():
    wave = np.linspace(2.15, 3.2, 300)
    components = [(w, np.array(a, dtype=float)) for w, a in LINE_COMPONENTS]
    before = [weights.copy() for _, weights in components]
    explicit = line_matrix(wave, np.array([1, 5]), np.array([100, 100]), components=components)
    default = line_matrix(wave, np.array([1, 5]), np.array([100, 100]))
    assert np.array_equal(explicit, default)
    for (_, weights), original in zip(components, before):
        assert np.array_equal(weights, original)


@pytest.mark.parametrize("mutation", ["receipt", "weights", "sum", "NIV1483", "HeO"])
def test_component_grid_rejects_inconsistent_physical_receipts(mutation):
    atomic, grid, digest = inputs()
    grid = copy.deepcopy(grid)
    if mutation == "receipt":
        grid["atomic_files"][0]["sha256"] = "0" * 64
    elif mutation == "weights":
        grid["records"][0]["components"][1]["normalized_weights"] = [0.5, 0.5]
    elif mutation == "sum":
        grid["records"][0]["components"][1]["component_emissivity_erg_cm3_s"][0] *= 1.01
    elif mutation == "NIV1483":
        grid["NIV_1483_included"] = True
    else:
        grid["records"][0]["components"][2]["normalized_weights"] = [0.5, 0.25, 0.25]
    with pytest.raises(ValueError):
        validate_component_grid(grid, atomic, digest)


def test_independent_quadrature_native_refit_gets_fresh_flux_and_covariance():
    # At high synthetic resolving power the wrong multiplet weights are visible.
    # Generate source amplitudes by quadrature rather than the ndtr line provider.
    wave = np.linspace(2.15, 3.2, 700)
    edges = bin_edges(wave)
    components = [(w, a) for w, a in LINE_COMPONENTS]
    components[3] = (LINE_COMPONENTS[3][0], (1, 3, 2, 1, 5))
    components[4] = (LINE_COMPONENTS[4][0], (3, 1))
    truth = np.array([40, 20, 15, -8, 25])
    templates = np.zeros((len(wave), 5))
    sub = edges[:-1, None] + np.diff(edges)[:, None] * np.linspace(0, 1, 2001)
    for group, (rests, weights) in enumerate(components):
        for rest, weight in zip(rests, np.array(weights) / np.sum(weights)):
            center = rest * 1e-4 * 15.44
            sigma = center / 3000 / (2 * np.sqrt(2 * np.log(2)))
            gaussian = np.exp(-0.5 * ((sub - center) / sigma) ** 2) / (sigma * np.sqrt(2 * np.pi))
            templates[:, group] += weight * np.trapezoid(gaussian, sub) / np.diff(edges)
    flux = templates @ truth / (2.99792458e5 / wave**2) + 0.02 + 0.003 * (wave - 2.675) / 0.525
    data = [
        {
            "wave": np.tile(wave, (3, 1)),
            "good": np.ones((3, len(wave)), bool),
            "trace_seed": np.ones(len(wave)),
        }
        for _ in range(2)
    ]
    source_flux = np.tile(flux, (2, 1))
    blocks = np.tile(np.eye(2) * 1e-8, (len(wave), 1, 1))
    selected = np.delete(np.arange(len(wave)), 130)
    physical = fit_native(
        data,
        source_flux,
        blocks,
        selected,
        np.array([1, 5]),
        np.array([3000, 3000]),
        components=components,
    )
    assert np.allclose(physical["fluxes"], truth, rtol=1e-5, atol=1e-6)
    fixed = fit_native(
        data, source_flux, blocks, selected, np.array([1, 5]), np.array([3000, 3000])
    )
    assert np.max(np.abs(np.array(fixed["fluxes"]) - truth)) > 0.5
    assert not np.allclose(physical["flux_covariance"], fixed["flux_covariance"], rtol=0.01)
    # The templates are also checked against an independently integrated oracle.
    provider = line_matrix(wave, np.array([1, 5]), np.array([3000, 3000]), components=components)
    assert np.allclose(provider, templates, rtol=2e-5, atol=1e-8)
    design = np.column_stack(
        [
            np.ones(len(wave)) / 100,
            (wave - 2.675) / 0.525 / 100,
            templates / (2.99792458e5 / wave**2)[:, None],
        ]
    )[selected]
    expected_covariance = np.linalg.inv(design.T @ design * (2 / 1e-8))[2:, 2:]
    assert np.allclose(physical["flux_covariance"], expected_covariance, rtol=1e-5, atol=1e-8)


def test_consistent_component_forgery_cannot_replace_the_frozen_provider(tmp_path):
    atomic, components, atomic_sha256 = inputs()
    group = components["records"][0]["components"][1]
    total = sum(group["component_emissivity_erg_cm3_s"])
    group["component_emissivity_erg_cm3_s"] = [total / 2, total / 2]
    group["normalized_weights"] = [0.5, 0.5]
    # Shape/totals are consistent, but they are not the frozen PyNeb solution.
    validate_component_grid(components, atomic, atomic_sha256)
    forged_path = tmp_path / "components.json"
    forged_path.write_text(json.dumps(components))
    with pytest.raises(ValueError, match="independently frozen PyNeb"):
        run(
            ROOT / "research_output/mom_native_reduction.json",
            ROOT / "research_output/mom_atomic_grid.json",
            forged_path,
        )


def test_compact_loader_retains_real_grids_but_does_not_manufacture_science_pixels():
    path = ROOT / "research_output/mom_native_reduction.json"
    replay = load_native_replay(path)
    assert all("science" not in datum for datum in replay["data"])
    assert replay["flux"].shape[0] == len(replay["data"]) == 9
    assert all(x["maximum_flux_difference"] <= 1e-10 for x in replay_report(path)["comparisons"])


def test_saved_refit_has_new_covariance_and_signed_ionic_intervals():
    atomic, components, sha256 = inputs()
    validate_component_grid(components, atomic, sha256)
    saved = json.loads((ROOT / "research_output/mom_native_multiplet_refit.json").read_text())
    assert saved["line_flux_covariance_refit_for_each_template"] is True
    assert saved["source_amplitude_noise_covariance_refit"] is False
    assert saved["elemental_abundance_identified"] is False
    assert saved["NIV_1483_included"] is False
    assert len(saved["scenarios"]) == 4
    for scenario in saved["scenarios"]:
        assert len(scenario["records"]) == 28
        for cell, record in zip(atomic["records"], scenario["records"]):
            flux, covariance = (
                np.array(record["fit"]["fluxes"]),
                np.array(record["fit"]["flux_covariance"]),
            )
            e = cell["emissivity_erg_cm3_s"]
            projection = np.array(
                [
                    [e["CIII"] / e["NIV"], 0, 0, e["CIII"] / e["NIII"], 0],
                    [0, e["CIII"] / e["CIV"], 0, 0, 1],
                ]
            )
            numerator, denominator = projection @ flux
            ionic = record["observed_two_stage_ionic_N_over_C"]
            assert ionic["value"] == pytest.approx(numerator / denominator, rel=1e-12)
            assert np.allclose(
                ionic["scaled_covariance"], projection @ covariance @ projection.T, rtol=1e-12
            )
            assert record["maximum_line_covariance_change_from_fixed_template"] > 0
    point = saved["scenarios"][-1]
    assert (
        sum(
            r["observed_two_stage_ionic_N_over_C"]["conditional_gaussian_95_fieller_set"][
                "interval"
            ][0]
            <= 0
            for r in point["records"]
        )
        == 3
    )
