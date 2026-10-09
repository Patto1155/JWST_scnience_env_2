"""Independent reference-set membership,336 cell projections and frozen-input controls."""

import json
from pathlib import Path

import numpy as np
import pytest

from tools.jwst.composed_spectral_refit import AMBIENT_IONIC_REFERENCE, ratio_accepted, run

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "n,d,variance,accepted,rejected",
    [
        (5, 4, [[1, 0], [0, 1]], [1.25], [0, 20]),
        (10, 0.1, [[1, 0], [0, 10]], [-100, 100], [0]),
        (0, 0, [[1, 0], [0, 1]], [-100, 0, 100], []),
        (1, 0, [[0, 0], [0, 0]], [], [-100, 0, 100]),
        (1, 1, [[1, 0], [0, 1 / 3.84145882069]], [0, 5], [-2]),
    ],
)
def test_quadratic_membership_supports_bounded_unbounded_and_degenerate_sets(
    n, d, variance, accepted, rejected
):
    answer = {"scaled_numerator": n, "scaled_denominator": d, "scaled_covariance": variance}
    assert all(ratio_accepted(answer, value) for value in accepted)
    assert not any(ratio_accepted(answer, value) for value in rejected)
    with pytest.raises(ValueError):
        ratio_accepted(answer, float("nan"))


def test_consistently_relabelled_wavecorr_metadata_cannot_replace_frozen_input(tmp_path):
    source = json.loads((ROOT / "research_output/mom_native_wavecorr.json").read_text())
    source["reference"]["pedigree"] = "GROUND"
    path = tmp_path / "altered.json"
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="independent frozen pin"):
        run(
            path,
            ROOT / "research_output/mom_atomic_grid_niv_doublet_v2.json",
            ROOT / "research_output/mom_multiplet_components_niv_doublet_v2.json",
            ROOT / "research_output/mom_native_niv_doublet_refit_v2.json",
        )


def test_actual336_fresh_fits_have_independent_covariance_projections_and_summaries():
    result = json.loads((ROOT / "research_output/mom_composed_spectral_refit.json").read_text())
    atomic = json.loads((ROOT / "research_output/mom_atomic_grid_niv_doublet_v2.json").read_text())
    assert result["spectral_fits"] == 336
    assert len(result["alternatives"]) == 12
    assert result["alternative_likelihoods_pooled"] is False
    assert result["posterior_weights_assigned"] is False
    assert result["elemental_abundance_identified"] is False
    assert result["ambient_reference_is_elemental_test"] is False
    assert result["empirical_wavelength_calibration"] is False
    assert result["reference_metadata"]["pedigree"] == "DUMMY"
    assert len(result["original_quartet_v2_controls"]) == 112
    assert max(c["maximum_flux_difference"] for c in result["original_quartet_v2_controls"]) <= 1e-9
    assert (
        max(c["maximum_covariance_difference"] for c in result["original_quartet_v2_controls"])
        <= 1e-8
    )
    families = set()
    for alternative in result["alternatives"]:
        families.add(
            (
                alternative["wavelength_hypothesis"],
                alternative["resolution_family"],
                alternative["noise_family"],
            )
        )
        assert alternative["source_noise_frozen"] is True
        assert len(alternative["records"]) == 28
        zero, ambient = 0, 0
        for cell, record in zip(atomic["records"], alternative["records"]):
            assert (cell["temperature_K"], cell["electron_density_cm3"]) == (
                record["temperature_K"],
                record["electron_density_cm3"],
            )
            fit = record["fit"]
            assert fit["line_contract_version"] == 2
            assert fit["NIV_flux_definition"].startswith("Total1483.321+1486.496")
            f, v = np.asarray(fit["fluxes"]), np.asarray(fit["flux_covariance"])
            assert np.min(np.linalg.eigvalsh(v)) > 0
            assert np.allclose(
                [fit["lines"][name]["conditional_sigma"] ** 2 for name in fit["line_order"]],
                np.diag(v),
                rtol=1e-12,
            )
            e = cell["emissivity_erg_cm3_s"]
            matrix = np.array(
                [
                    [e["CIII"] / e["NIV"], 0, 0, e["CIII"] / e["NIII"], 0],
                    [0, e["CIII"] / e["CIV"], 0, 0, 1],
                ]
            )
            n, d = matrix @ f
            projected = matrix @ v @ matrix.T
            answer = record["observed_two_stage_ionic_N_over_C"]
            assert answer["value"] == pytest.approx(n / d, rel=1e-12)
            assert np.allclose(answer["scaled_covariance"], projected, rtol=1e-12)
            z2 = 1.959963984540054**2
            roots = np.sort(
                np.roots(
                    [
                        d * d - z2 * projected[1, 1],
                        -2 * n * d + 2 * z2 * projected[0, 1],
                        n * n - z2 * projected[0, 0],
                    ]
                )
            )
            interval = answer["conditional_gaussian_95_fieller_set"]
            assert interval["type"] == "bounded"
            assert np.allclose(interval["interval"], roots, rtol=1e-11, atol=1e-12)
            zero += int(roots[0] <= 0 <= roots[1])
            ambient += int(roots[0] <= AMBIENT_IONIC_REFERENCE <= roots[1])
        assert alternative["grid_summary"]["ionic_zero_accepted_95_count"] == zero
        assert alternative["grid_summary"]["ionic_ambient_reference_accepted_95_count"] == ambient
        assert alternative["grid_summary"]["grid_range_is_confidence_interval"] is False
        reference = next(
            r
            for r in alternative["records"]
            if r["temperature_K"] == 20000 and r["electron_density_cm3"] == 1000
        )
        assert (
            alternative["reference_cell"]["ionic_ratio"]
            == reference["observed_two_stage_ionic_N_over_C"]["value"]
        )
    assert len(families) == 12
    # The measured sign-support contrast must remain visible rather than pooled.
    original_point = next(
        a
        for a in result["alternatives"]
        if a["wavelength_hypothesis"] == "original_native"
        and a["resolution_family"] == "generic_point"
        and a["noise_family"] == "empirical_rows_and_columns"
    )
    toy_point = next(
        a
        for a in result["alternatives"]
        if a["wavelength_hypothesis"] == "pinned_toy_prediction"
        and a["resolution_family"] == "generic_point"
        and a["noise_family"] == "empirical_rows_and_columns"
    )
    assert original_point["grid_summary"]["ionic_zero_accepted_95_count"] == 28
    assert toy_point["grid_summary"]["ionic_zero_accepted_95_count"] == 0
    assert original_point["reference_cell"]["ionic_ambient_reference_accepted_95"] is True
    assert toy_point["reference_cell"]["ionic_ambient_reference_accepted_95"] is True
