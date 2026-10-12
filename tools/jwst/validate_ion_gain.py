"""Independent direct-quadrature/NNLS review of the retained ion-gain pilot.

The author optimizer is called only for comparison. The oracle uses independent
Gaussian integration and a nonnegative boundary-ray spectral fit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from astropy.io import fits
from scipy.integrate import quad
from scipy.optimize import nnls

from tools.jwst.cloudy_ion_gain import gain_discrimination

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
AUTHOR_FILES = (
    "tools/jwst/cloudy_ion_gain.py",
    "tests/test_cloudy_ion_gain.py",
    "docs/MOM_CLOUDY_ION_GAIN.md",
    "data_sources/pilot/observation_design/ion_gain_plan.json",
    "research_output/mom_cloudy_ion_gain.json",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nominal_curve(root: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read and verify the retained G235H curve without author helpers."""
    source = root / "data_sources/pilot/observation_design"
    receipt = json.loads((source / "receipt.json").read_text())
    rows = [
        row
        for row in receipt["records"]
        if row["name"].endswith(".fits") and row["name"].split("_")[2] == "g235h"
    ]
    if len(rows) != 1:
        raise ValueError("one retained G235H curve required")
    row = rows[0]
    path = source / row["name"]
    if path.stat().st_size != row["bytes"] or digest(path) != row["sha256"]:
        raise ValueError("nominal curve identity changed")
    with fits.open(path) as hdul:
        return np.array(hdul[1].data["WAVELENGTH"], float), np.array(hdul[1].data["R"], float)


def run(root: Path) -> dict:
    """Recompute all finite comparisons and verify saved closest/paired records."""
    model_path = root / "research_output/mom_cloudy_pilot20_rate_v3.json"
    plan_path = root / "data_sources/pilot/observation_design/ion_gain_plan.json"
    output_path = root / "research_output/mom_cloudy_ion_gain.json"
    pilot = json.loads(model_path.read_text())
    plan = json.loads(plan_path.read_text())
    saved = json.loads(output_path.read_text())
    assert digest(model_path) == plan["input_sha256"] == saved["input_sha256"]
    assert digest(plan_path) == saved["plan_sha256"]
    assert plan["mode"] == "g235h" and plan["intrinsic_fwhm_km_s"] == 0
    models = pilot["models"]
    indices = [7, 8, 9, 10, 11, 12, 13]
    rest = np.asarray([pilot["lines"][i][1] for i in indices])
    wave = rest * 15.44 / 1e4
    cw, cr = nominal_curve(root)
    sigma = wave / np.interp(wave, cw, cr) / np.sqrt(8 * np.log(2))

    def gaussian(x: float) -> np.ndarray:
        return np.exp(-0.5 * ((x - wave) / sigma) ** 2) / (sigma * np.sqrt(2 * np.pi))

    # Integrate each pair in the standardized coordinate of its Gaussian product.
    gram = np.zeros((7, 7))
    for i in range(7):
        for j in range(7):
            center = (wave[i] / sigma[i] ** 2 + wave[j] / sigma[j] ** 2) / (
                1 / sigma[i] ** 2 + 1 / sigma[j] ** 2
            )
            scale = 1 / np.sqrt(1 / sigma[i] ** 2 + 1 / sigma[j] ** 2)
            gram[i, j] = quad(
                lambda x: gaussian(center + scale * x)[i] * gaussian(center + scale * x)[j] * scale,
                -12,
                12,
                epsabs=1e-12,
                epsrel=1e-12,
            )[0]
    chol = np.linalg.cholesky(gram).T
    analytic = np.exp(
        -((wave[:, None] - wave[None, :]) ** 2) / (2 * (sigma[:, None] ** 2 + sigma[None, :] ** 2))
    ) / np.sqrt(2 * np.pi * (sigma[:, None] ** 2 + sigma[None, :] ** 2))
    assert np.allclose(gram, analytic, atol=1e-9, rtol=1e-11)

    def oracle(truth: np.ndarray, alt: np.ndarray, h: float | None) -> tuple[float, np.ndarray]:
        ion = np.zeros((7, 2))
        ion[:5, 0] = alt[:5]
        ion[5:, 1] = alt[5:]
        rays = np.eye(2) if h is None else np.array([[1 - h, 1 + h], [1, 1.0]])
        coef, _ = nnls(chol @ ion @ rays, chol @ truth, maxiter=500)
        amplitudes = rays @ coef
        res = truth - ion @ amplitudes
        return float(res @ gram @ res / (truth @ gram @ truth)), amplitudes

    ordinary = [m for m in models if m["parameters"]["log_NC_relative_minus060"] == 0]
    enhanced = [m for m in models if m["parameters"]["log_NC_relative_minus060"] == 1]
    maxerr = 0.0
    maxcoef = 0.0
    allcount = 0
    case_rows = []
    for case in saved["cases"]:
        response = case["response"]
        h = case["fractional_gain_half_width"]
        shapes = {}
        for m in models:
            for A in plan["attenuation_A1500_mag"]:
                values = np.asarray(m[response])[indices] * np.exp(
                    -0.4 * np.log(10) * A * (rest / 1500) ** -1.2
                )
                shapes[m["id"], A] = values / values.sum()
        best_pair = {}
        for truth in enhanced:
            for alt in ordinary:
                candidates = []
                for A in plan["attenuation_A1500_mag"]:
                    for B in plan["attenuation_A1500_mag"]:
                        t, a = shapes[truth["id"], A], shapes[alt["id"], B]
                        info, co = oracle(t, a, h)
                        author = gain_discrimination(analytic, t, a, 5, h)
                        maxerr = max(maxerr, abs(author["shape_information_fraction"] - info))
                        maxcoef = max(
                            maxcoef,
                            float(
                                np.max(
                                    np.abs(
                                        co
                                        - [
                                            author["profiled_NIII_amplitude"],
                                            author["profiled_CIII_amplitude"],
                                        ]
                                    )
                                )
                            ),
                        )
                        allcount += 1
                        candidates.append((info, truth["id"], alt["id"], A, B, co))
                best_pair[truth["id"], alt["id"]] = min(candidates, key=lambda x: x[0])
        for record in [case["closest_cross_environment"]] + case["matched_environment_pairs"]:
            raw = best_pair[
                record["enhanced_truth_model_id"], record["ordinary_alternative_model_id"]
            ]
            assert abs(raw[0] - record["shape_information_fraction"]) < 1e-11
            assert (raw[3], raw[4]) == (record["enhanced_A1500_mag"], record["ordinary_A1500_mag"])
        closest = min(best_pair.values(), key=lambda x: x[0])
        record = case["closest_cross_environment"]
        assert closest[1:5] == (
            record["enhanced_truth_model_id"],
            record["ordinary_alternative_model_id"],
            record["enhanced_A1500_mag"],
            record["ordinary_A1500_mag"],
        )
        case_rows.append(
            {
                "response": response,
                "h": h,
                "info": closest[0],
                "snr": float(np.sqrt(9 / closest[0])),
                "gain": float(closest[5][0] / closest[5][1]),
                "pair": closest[1:5],
            }
        )
    result = {
        "scope": (
            "independent full finite-comparison NNLS on boundary-ray spectra; Gram from "
            "direct numerical Gaussian quadrature; no observed likelihood/thermal replay"
        ),
        "comparisons": allcount,
        "maximum_information_error": maxerr,
        "maximum_ion_amplitude_error": maxcoef,
        "maximum_gram_quadrature_error": float(np.max(np.abs(gram - analytic))),
        "saved_closest_and_paired_records_checked": len(saved["cases"]) * 11,
        "cases": case_rows,
        "input_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        "author_output_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }

    assert len(saved["cases"]) == 12 and allcount == 10800
    assert maxerr < 1e-11 and maxcoef < 1e-10
    assert all(len(case["matched_environment_pairs"]) == 10 for case in saved["cases"])
    result.update(
        status="passed",
        reviewed_files_sha256={name: digest(root / name) for name in AUTHOR_FILES},
        reviewer_source="tools/jwst/validate_ion_gain.py",
        reviewer_script_sha256=digest(Path(__file__).resolve()),
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.root.resolve())
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
