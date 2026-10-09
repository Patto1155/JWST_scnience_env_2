"""Pinned Cue v0.1 four-group photoionization predictions and covariant fitting.

Author weight archives are decoded through a narrow numeric whitelist. Inference
replays the author's supplied NumPy forward operation without TensorFlow/dill.
NIV is absent and NEVER added by assigning it zero emission or a made-up response.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import itertools
import json
import pickle
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from data_pipeline.atomic_inputs import CUE_BYTES, CUE_SHA256, CUE_URL, verify_bytes
from tools.jwst.atomic_grid import check_fluxes, spectral_scenarios
from tools.jwst.line_sensitivity import LINE_NAMES

ION_GROUPS = {
    "C2C3": ("C  2", "C  3"),
    "C4": ("C  4",),
    "N": ("N  1", "N  2", "N  3"),
    "He2": ("He 2",),
    "O3": ("O  3",),
}
FITTED_GROUPS = ("CIV", "HeII_OIII", "NIII", "CIII")
GROUP_WAVES = {
    "CIV": (1548.19, 1550.77),
    "HeII_OIII": (1640.41, 1660.81, 1666.15),
    "NIII": (1750.00,),
    "CIII": (1906.68, 1908.73),
}
SHAPES = {
    "author_emulator_default": [19.7, 5.3, 1.6, 0.6, 3.9, 0.01, 0.2],
    "author_readme_demo": [21.5, 14.85, 6.45, 3.15, 4.55, 0.7, 0.85],
    "hard_piecewise_control": [5.0, 2.0, 0.0, 0.0, 1.0, 0.0, 0.0],
}
LOGNO = (-1.0, -0.5, 0.0, 0.5, float(np.log10(5.4)))
LOGCO = LOGNO
LOGU = (-3.0, -2.0, -1.0)
LOGN = (2.0, 3.0, 4.0)
LOGZ = (-2.0, -1.3, -0.6)


class NumericData:
    """State-only stand-in for author PCA objects; no code from pickle is invoked."""


class NumericList(list):
    """State-only stand-in for TensorFlow's list wrapper."""


def create_array(function: Any, args: tuple, state: tuple, numpy_dictionary=None):
    if function is not np._core.multiarray._reconstruct:
        raise ValueError("only NumPy array reconstruction is permitted")
    array = function(*args)
    array.__setstate__(state)
    if array.dtype.hasobject:
        raise ValueError("object arrays are not permitted")
    return array


class NumericUnpickler(pickle.Unpickler):
    """Only numeric arrays and inert state containers can be reconstructed."""

    def find_class(self, module: str, name: str):
        if module in ("numpy.core.multiarray", "numpy._core.multiarray"):
            if name in ("_reconstruct", "scalar"):
                return getattr(np._core.multiarray, name)
        if module == "numpy" and name in ("ndarray", "dtype"):
            return getattr(np, name)
        if (module, name) == ("dill._dill", "_create_array"):
            return create_array
        if (module, name) == ("tensorflow.python.trackable.data_structures", "ListWrapper"):
            return NumericList
        if (module, name) in (
            ("cue.line_pca", "SpectrumPCA"),
            ("sklearn.decomposition._incremental_pca", "IncrementalPCA"),
        ):
            return NumericData
        raise ValueError(f"unapproved model-pickle global: {module}.{name}")


def forward(theta: np.ndarray, weights: list, pca: NumericData) -> np.ndarray:
    """Author nn.py log_spectrum_ plus PCA.inverse_transform and output scaling."""
    w, b, alpha, beta = weights[:4]
    parameters_shift, parameters_scale, pca_shift, pca_scale = weights[4:8]
    spectrum_shift, spectrum_scale = weights[8:10]
    layers = (theta - parameters_shift) / parameters_scale
    for i in range(len(w) - 1):
        act = layers @ w[i] + b[i]
        with np.errstate(over="ignore"):
            layers = (beta[i] + (1 - beta[i]) / (1 + np.exp(-alpha[i] * act))) * act
    coefficients = (layers @ w[-1] + b[-1]) * pca_scale + pca_shift
    result = (coefficients @ pca.PCA.components_ + pca.PCA.mean_) * spectrum_scale + spectrum_shift
    if not np.all(np.isfinite(result)):
        raise ValueError("nonfinite emulator prediction")
    return result


def read_models(path: Path) -> tuple[dict, dict]:
    verify_bytes(path, CUE_SHA256, CUE_BYTES)
    result, provenance = {}, []
    with zipfile.ZipFile(path) as archive:
        if sum(x.file_size for x in archive.infolist()) > 150 * 1024**2:
            raise ValueError("expanded Cue archive exceeds bound")

        def read(suffix: str) -> bytes:
            matches = [x for x in archive.namelist() if x.endswith("/" + suffix)]
            if len(matches) != 1:
                raise ValueError("missing or ambiguous Cue archive member")
            data = archive.read(matches[0])
            provenance.append(
                {"member": suffix, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            )
            return data

        names = np.load(
            io.BytesIO(read("src/cue/data/lineList_replaceblnd_name.npy")), allow_pickle=False
        )
        wavelengths = np.load(io.BytesIO(read("src/cue/data/lineList_wav.npy")), allow_pickle=False)
        ordering = np.argsort(wavelengths)
        names, wavelengths = names[ordering], wavelengths[ordering]
        ions = np.array([x[:4].rstrip() for x in names])
        for group, ions_in_group in ION_GROUPS.items():
            weights = NumericUnpickler(
                io.BytesIO(read(f"src/cue/data/speculator_line_new_{group}.pkl"))
            ).load()
            pca = NumericUnpickler(
                io.BytesIO(read(f"src/cue/data/pca_line_new_{group}.pkl"))
            ).load()
            selected = np.flatnonzero(np.isin(ions, ions_in_group))
            if len(weights) != 18 or not np.allclose(weights[10], pca.PCA.components_):
                raise ValueError("unsupported author network/PCA structure")
            if pca.PCA.whiten:
                raise ValueError("whitened PCA requires a different inverse transform")
            if len(selected) != len(weights[13]):
                raise ValueError("Cue ion selection disagrees with network output length")
            if not np.allclose(wavelengths[selected], weights[13]):
                raise ValueError("Cue ion wavelength order differs from saved network")
            result[group] = (weights, pca, wavelengths[selected])
        for source in ("src/cue/nn.py", "src/cue/emulator.py", "src/cue/utils.py"):
            read(source)
    return result, {
        "archive_url": CUE_URL,
        "archive_sha256": CUE_SHA256,
        "archive_bytes": CUE_BYTES,
        "member_provenance": provenance,
        "version": "Cue v0.1 / DOI 10.5281/zenodo.11118643",
        "runtime": "Author NumPy inference and PCA algebra; no TensorFlow runtime loaded",
        "missing_observed_groups": ["NIV"],
        "upstream_FSPS_128_line_projection_applied": False,
        "native_solar_log_NO": -0.88,
        "native_solar_log_CO": -0.37,
        "assumed_depletion_log_N": -0.22,
        "assumed_depletion_log_C": -0.30,
        "native_NC_parameter_to_MoM_undepleted_bracket_offset": 0.09,
        "native_NC_parameter_to_MoM_gas_phase_bracket_offset": 0.17,
    }


def parameters() -> tuple[np.ndarray, list[dict]]:
    rows, metadata = [], []
    for shape_name, spectral in SHAPES.items():
        for logu, logn, logz, logno, logco in itertools.product(LOGU, LOGN, LOGZ, LOGNO, LOGCO):
            logq = logu + np.log10(4 * np.pi) + 38 + logn + np.log10(2.9979e10)
            rows.append([*spectral, logq, 10**logn, logz, logno, logco])
            metadata.append(
                {
                    "ionizing_spectrum_control": shape_name,
                    "logU": logu,
                    "log_nH_cm3": logn,
                    "native_Cue_OH": logz,
                    "native_Cue_NO": logno,
                    "native_Cue_CO": logco,
                    "native_Cue_NO_minus_CO": logno - logco,
                    "touches_U_density_NO_CO_sampling_edge": logu == -1
                    or logn == 4
                    or logno in (LOGNO[0], LOGNO[-1])
                    or logco in (LOGCO[0], LOGCO[-1]),
                }
            )
    return np.asarray(rows), metadata


def group_predictions(theta: np.ndarray, models: dict) -> np.ndarray:
    predictions = {}
    for weights, pca, waves in models.values():
        values = forward(theta, weights, pca)
        for j, wavelength in enumerate(waves):
            predictions[float(wavelength)] = 10 ** (values[:, j] - 35)
    result = []
    for name in FITTED_GROUPS:
        included = []
        for wavelength in GROUP_WAVES[name]:
            matches = [x for x in predictions if abs(x - wavelength) < 0.015]
            if len(matches) != 1:
                raise ValueError("missing/ambiguous photoionization line; never assign zero")
            included.append(predictions[matches[0]])
        result.append(np.sum(included, axis=0))
    return np.asarray(result).T


def fit_grid(fit: dict, predicted: np.ndarray, metadata: list[dict]) -> dict:
    if (
        predicted.shape != (len(metadata), 4)
        or not len(metadata)
        or not np.all(np.isfinite(predicted) & (predicted > 0))
    ):
        raise ValueError("complete positive four-group physical predictions required")
    flux, covariance = check_fluxes(fit)
    selected = [LINE_NAMES.index(x) for x in FITTED_GROUPS]
    flux, covariance = flux[selected], covariance[np.ix_(selected, selected)]
    inverse = np.linalg.inv(covariance)
    # Profile a free nonnegative normalization for each physical line-shape model.
    model = predicted / predicted[:, -1, None]
    numerators = model @ inverse @ flux
    denominators = np.einsum("ij,jk,ik->i", model, inverse, model)
    amplitudes = np.maximum(0, numerators / denominators)
    residuals = flux - amplitudes[:, None] * model
    chi2 = np.einsum("ij,jk,ik->i", residuals, inverse, residuals)
    ordered = np.argsort(chi2)
    best = float(chi2[ordered[0]])
    close = chi2 <= best + 3.84145882069
    native_nc = np.array([x["native_Cue_NO_minus_CO"] for x in metadata])
    top = [
        {
            **metadata[i],
            "chi2_four_groups": float(chi2[i]),
            "CIII_normalization_flux": float(amplitudes[i]),
            "predicted_four_group_fluxes": (amplitudes[i] * model[i]).tolist(),
        }
        for i in ordered[:12]
    ]
    return {
        "extraction": fit.get("extraction"),
        "line_order": list(FITTED_GROUPS),
        "input_fluxes": flux.tolist(),
        "input_covariance": covariance.tolist(),
        "normalization_profiled": True,
        "models_compared": len(metadata),
        "best_chi2_four_groups": best,
        "ranked_grid_points": top,
        "grid_points_with_delta_chi2_le_3_841": int(np.sum(close)),
        "native_Cue_NO_minus_CO_range_within_delta": [
            float(np.min(native_nc[close])),
            float(np.max(native_nc[close])),
        ],
        "delta_set_is_calibrated_confidence_region": False,
        "sampling_edge_fraction_within_delta": float(
            np.mean(
                [
                    metadata[i]["touches_U_density_NO_CO_sampling_edge"]
                    for i in np.flatnonzero(close)
                ]
            )
        ),
        "physical_degrees_of_freedom": None,
        "interpretation": "Sparse deterministic sensitivity grid; neither posterior weights "
        "nor calibrated multi-parameter confidence region. NIV omitted, not fitted. "
        "Emulator/geometry errors and independent LSF calibration not propagated.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument(
        "--spectrum", type=Path, default=Path("research_output/mom_z14_point_resolution.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("research_output/mom_cue_grid_fit.json")
    )
    args = parser.parse_args()
    models, provenance = read_models(args.archive)
    theta, metadata = parameters()
    predictions = group_predictions(theta, models)
    spectrum = json.loads(args.spectrum.read_text())
    output = {
        "schema_version": 1,
        "provenance": provenance,
        "input_spectrum_sha256": hashlib.sha256(args.spectrum.read_bytes()).hexdigest(),
        "parameter_grid": {
            "ionizing_shapes": SHAPES,
            "logU": LOGU,
            "log_nH": LOGN,
            "native_Cue_OH": LOGZ,
            "native_Cue_NO": LOGNO,
            "native_Cue_CO": LOGCO,
        },
        "predicted_four_group_grid_sha256": hashlib.sha256(predictions.tobytes()).hexdigest(),
        "scenarios": [
            {"resolution_family": label, **fit_grid(fit, predictions, metadata)}
            for label, fit in spectral_scenarios(spectrum)
        ],
        "all_five_measured_groups_fit": False,
        "source_specific_model_validated": False,
        "ionizing_controls_identified_as_stellar_or_AGN": False,
    }
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "models": len(metadata)}, indent=2))


if __name__ == "__main__":
    main()
