"""Model coverage, numeric-loader and covariance controls plus optional real replay."""

import ast
import io
import os
import pickle
import zipfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from tools.jwst.atomic_grid import spectral_scenarios
from tools.jwst.cue_grid import (
    FITTED_GROUPS,
    GROUP_WAVES,
    NumericUnpickler,
    fit_grid,
    forward,
    parameters,
    read_models,
)
from tools.jwst.line_sensitivity import LINE_NAMES


def example_fit():
    flux = [100, 2, 3, 4, 5]
    return {
        "lines": {name: {"flux": value} for name, value in zip(LINE_NAMES, flux)},
        "line_covariance": np.eye(5).tolist(),
        "line_flux_unit": "1e-20 erg s^-1 cm^-2",
    }


def metadata():
    return {"native_Cue_NO_minus_CO": 0.0, "touches_U_density_NO_CO_sampling_edge": False}


def test_niv_is_an_explicit_coverage_gap():
    assert "NIV" not in FITTED_GROUPS
    assert "NIV" not in GROUP_WAVES
    assert len(FITTED_GROUPS) == 4


def test_numeric_unpickler_rejects_other_classes_without_running_them():
    content = pickle.dumps(Path("non-numeric-object"))
    with pytest.raises(ValueError, match="unapproved"):
        NumericUnpickler(io.BytesIO(content)).load()


def test_scalar_forward_has_independent_closed_form():
    # One affine network; coefficient -> PCA reconstruct -> log-spectrum scale.
    weights = [
        [np.array([[2.0]])],
        [np.array([1.0])],
        [],
        [],
        np.array([1.0]),
        np.array([2.0]),
        np.array([3.0]),
        np.array([4.0]),
        np.array([10.0]),
        np.array([2.0]),
    ]
    pca = SimpleNamespace(PCA=SimpleNamespace(components_=np.array([[5.0]]), mean_=np.array([7.0])))
    theta = np.array([[3.0]])
    # x=1, affine=3, PCA coefficient=15, PCA inverse=82, final=174.
    assert forward(theta, weights, pca)[0, 0] == 174


def test_exact_physical_shape_profiles_normalization_and_excludes_niv():
    prediction = np.array([[2.0, 3.0, 4.0, 5.0]])
    result = fit_grid(example_fit(), prediction, [metadata()])
    assert result["best_chi2_four_groups"] == pytest.approx(0, abs=1e-25)
    assert result["ranked_grid_points"][0]["CIII_normalization_flux"] == pytest.approx(5)
    altered = example_fit()
    altered["lines"]["NIV"]["flux"] = -1000
    assert fit_grid(altered, prediction, [metadata()]) == result


@pytest.mark.parametrize("prediction", [np.zeros((1, 4)), np.ones((1, 3)), np.full((1, 4), np.nan)])
def test_incomplete_or_invalid_physical_predictions_are_rejected(prediction):
    with pytest.raises(ValueError):
        fit_grid(example_fit(), prediction, [metadata()])


def test_actual_parameter_grid_is_within_documented_ranges():
    theta, meta = parameters()
    assert theta.shape == (2025, 12)
    assert len(meta) == 2025
    assert np.min(theta[:, 8]) == 100 and np.max(theta[:, 8]) == 10000
    assert np.min(theta[:, 10]) == -1
    assert np.max(theta[:, 10]) == pytest.approx(np.log10(5.4))


def test_native_scenario_adaptation_preserves_covariance_units_and_sigmas():
    source = example_fit()
    native = {
        "scenarios": [
            {
                "name": "point_empirical_transport",
                "fit": {
                    "line_order": list(LINE_NAMES),
                    "fluxes": [100, 2, 3, 4, 5],
                    "flux_covariance": source["line_covariance"],
                    "flux_units": source["line_flux_unit"],
                    "lines": {name: {"conditional_sigma": 1} for name in LINE_NAMES},
                },
            }
        ]
    }
    label, fit = spectral_scenarios(native)[0]
    assert label == "point_empirical_transport"
    assert fit["line_covariance"] == source["line_covariance"]
    native["scenarios"][0]["fit"]["lines"]["NIV"]["conditional_sigma"] = 10
    with pytest.raises(ValueError, match="sigma"):
        spectral_scenarios(native)


@pytest.mark.integration
def test_author_numpy_forward_replay_on_actual_pinned_weights():
    value = os.environ.get("JWST_CUE_ARCHIVE")
    if value is None:
        pytest.skip("set JWST_CUE_ARCHIVE to independently pinned Cue v0.1 archive")
    archive = Path(value)
    models, _ = read_models(archive)
    # Extract only the author's already inspected NumPy inference routine;
    # TensorFlow/dill imports and author package initialization are not executed.
    with zipfile.ZipFile(archive) as z:
        source = z.read(next(n for n in z.namelist() if n.endswith("/src/cue/nn.py")))
    parsed = ast.parse(source)
    klass = next(x for x in parsed.body if isinstance(x, ast.ClassDef) and x.name == "Speculator")
    method = next(
        x for x in klass.body if isinstance(x, ast.FunctionDef) and x.name == "log_spectrum_"
    )
    context = {"np": np}
    exec(
        compile(ast.Module(body=[method], type_ignores=[]), "pinned_author_numpy", "exec"), context
    )
    theta, _ = parameters()
    for weights, pca, _ in models.values():
        fields = (
            "W_",
            "b_",
            "alphas_",
            "betas_",
            "parameters_shift_",
            "parameters_scale_",
            "pca_shift_",
            "pca_scale_",
            "log_spectrum_shift_",
            "log_spectrum_scale_",
        )
        author_object = SimpleNamespace(**dict(zip(fields, weights[:10])), n_layers=weights[16])
        coefficients = context["log_spectrum_"](author_object, theta)
        independent = (coefficients @ pca.PCA.components_ + pca.PCA.mean_) * weights[9] + weights[8]
        assert np.allclose(independent, forward(theta, weights, pca), rtol=1e-13, atol=1e-13)
