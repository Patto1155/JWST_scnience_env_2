"""Four finite complete-model UV observing contrasts; no abundance posterior.

This module must not execute real model comparisons before the complete input
is independently validated and present in fetched origin/master ancestry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

import numpy as np

from tools.jwst.observation_design import (
    ROOT,
    SOURCE,
    gaussian_gram,
    read_nominal_curves,
    shape_discrimination,
)

EXPECTED_LINES = (
    ("N  4", 1483.32),
    ("N  4", 1486.50),
    ("C  4", 1548.19),
    ("C  4", 1550.77),
    ("He 2", 1640.41),
    ("O  3", 1660.81),
    ("O  3", 1666.15),
    ("N  3", 1746.82),
    ("N  3", 1748.65),
    ("N  3", 1749.67),
    ("N  3", 1752.16),
    ("N  3", 1753.99),
    ("C  3", 1906.68),
    ("C  3", 1908.73),
    ("Blnd", 1486.00),
    ("Blnd", 1549.00),
    ("Blnd", 1650.00),
    ("Blnd", 1750.00),
    ("Blnd", 1909.00),
    ("H  1", 4861.32),
    ("O  3", 5006.84),
    ("N  2", 6583.45),
    ("N  5", 1238.82),
    ("N  5", 1242.80),
    ("C  2", 2323.50),
    ("C  2", 2324.69),
    ("C  2", 2325.40),
    ("C  2", 2326.93),
    ("C  2", 2328.12),
)
GROUPS = {
    "NIV": (0, 1),
    "CIV": (2, 3),
    "HeII_OIII": (4, 5, 6),
    "NIII": (7, 8, 9, 10, 11),
    "CIII": (12, 13),
}
NITROGEN_KEY = "log_NC_relative_minus060"


def validate_models(pilot: dict) -> None:
    """Reject missing lines and incomplete/unpaired compositions, never fill zero."""
    if (
        pilot.get("cloudy_release") != "C23.01"
        or pilot.get("line_contract_version") != 2
        or pilot.get("complete_thermal_solution_per_composition") is not True
        or tuple(tuple(row) for row in pilot.get("lines", [])) != EXPECTED_LINES
        or pilot.get("intrinsic_line_unit") != "erg s^-1 cm^-2; Cloudy intensity geometry"
        or pilot.get("line_wavelength_medium")
        != ["air" if wave > 2000 else "vacuum" for _, wave in EXPECTED_LINES]
        or pilot.get("ordinary_reference_log_NC") != -0.60
        or pilot.get("reference_log_CO") != -0.37
        or len(pilot.get("models", [])) != 20
    ):
        raise ValueError("complete version2 converged20model line contract required")
    pairs = {}
    identifiers = set()
    for row in pilot["models"]:
        if row["id"] in identifiers:
            raise ValueError("duplicate model identity")
        identifiers.add(row["id"])
        params = row["parameters"]
        nitrogen = params[NITROGEN_KEY]
        if nitrogen not in (0, 1):
            raise ValueError("declared ordinary/enhanced composition required")
        key = tuple(sorted((k, v) for k, v in params.items() if k != NITROGEN_KEY))
        if nitrogen in pairs.setdefault(key, {}):
            raise ValueError("duplicate composition/environment")
        pairs[key][nitrogen] = row["id"]
        for response in ("intrinsic_line_values", "emergent_line_values"):
            values = np.asarray(row[response], dtype=float)
            if (
                values.shape != (29,)
                or not np.all(np.isfinite(values))
                or np.any(values < 0)
                or values[12:14].sum() <= 0
            ):
                raise ValueError(
                    "missing/nonfinite/negative line response; positive CIII anchor required"
                )
        if row.get("zones", 0) <= 0 or "Cloudy ends:" not in row.get("convergence_summary", ""):
            raise ValueError("converged thermal output required")
        abundances = row["actual_gas_abundances"]
        lognc = (
            abundances["NITR"]["actual_printed_log_XH"]
            - abundances["CARB"]["actual_printed_log_XH"]
        )
        if not np.isclose(lognc, -0.60 + nitrogen, atol=0.0101, rtol=0):
            raise ValueError("actual N/C does not match declared composition")
        logco = (
            abundances["CARB"]["actual_printed_log_XH"]
            - abundances["OXYG"]["actual_printed_log_XH"]
        )
        if not np.isclose(logco, -0.37, atol=0.0101, rtol=0):
            raise ValueError("actual C/O does not match declared custom composition")
    if len(pairs) != 10 or any(set(pair) != {0, 1} for pair in pairs.values()):
        raise ValueError("ten paired environment rows required")


def screen(values: np.ndarray, wavelength_A: np.ndarray, A1500: float) -> np.ndarray:
    """Exact existing upstream power-law foreground screen, applied to line energy."""
    if not np.isfinite(A1500) or A1500 < 0:
        raise ValueError("nonnegative finite attenuation required")
    return values * 10 ** (-0.4 * A1500 * (wavelength_A / 1500.0) ** -1.2)


def environment(model: dict) -> tuple:
    return tuple(
        sorted((key, value) for key, value in model["parameters"].items() if key != NITROGEN_KEY)
    )


def compare_family(
    models: list[dict],
    indices: tuple[int, ...],
    gram: np.ndarray,
    attenuations: list[float],
    response: str,
) -> dict:
    """Finite paired contrasts plus closest cross-environment model, no odds.

    Enhanced is truth; ordinary is the alternative. SNR depends on this
    convention and always refers to the truth's matched template.
    """
    ordinary = [m for m in models if m["parameters"][NITROGEN_KEY] == 0]
    enhanced = [m for m in models if m["parameters"][NITROGEN_KEY] == 1]
    waves = np.array([EXPECTED_LINES[index][1] for index in indices])
    shapes = {}
    for model in models:
        values = np.asarray(model[response])[list(indices)]
        for attenuation in attenuations:
            attenuated = screen(values, waves, attenuation)
            if attenuated.sum() <= 0:
                raise ValueError("zero target bundle response cannot supply a shape")
            shapes[model["id"], attenuation] = attenuated / attenuated.sum()
    comparisons = []
    for truth in enhanced:
        for alternative in ordinary:
            best = None
            for truth_A in attenuations:
                for alt_A in attenuations:
                    result = shape_discrimination(
                        gram, shapes[truth["id"], truth_A], shapes[alternative["id"], alt_A]
                    )
                    row = {
                        "enhanced_truth_model_id": truth["id"],
                        "ordinary_alternative_model_id": alternative["id"],
                        "enhanced_A1500_mag": truth_A,
                        "ordinary_A1500_mag": alt_A,
                        "same_environment": environment(truth) == environment(alternative),
                        **result,
                    }
                    if (
                        best is None
                        or row["shape_information_fraction"] < best["shape_information_fraction"]
                    ):
                        best = row
            comparisons.append(best)
    closest = min(comparisons, key=lambda row: row["shape_information_fraction"])
    paired = [row for row in comparisons if row["same_environment"]]
    return {
        "truth_convention": "enhanced+1dex model; signed native observations not used",
        "cross_environment_comparisons": len(ordinary) * len(enhanced),
        "existing_attenuation_pairs_per_comparison": len(attenuations) ** 2,
        "closest_cross_environment": closest,
        "matched_environment_pairs": paired,
        "hardest_matched_environment": min(
            paired, key=lambda row: row["shape_information_fraction"]
        ),
        "finite_counts_are_probabilities": False,
    }


def stage_ranges(models: list[dict], attenuations: list[float], response: str) -> list[dict]:
    """Extra-stage design outputs retain exact air-label convention for CII."""
    result = []
    for name, indices, convention in [
        ("NV", (22, 23), "vacuum"),
        ("CII", (24, 25, 26, 27, 28), "Cloudy air labels; approximate wavelength targets only"),
    ]:
        families = {}
        for composition in (0, 1):
            values = []
            for model in models:
                if model["parameters"][NITROGEN_KEY] != composition:
                    continue
                original = np.asarray(model[response])
                for attenuation in attenuations:
                    selected = np.array(indices + (12, 13))
                    attenuated = screen(
                        original[selected],
                        np.array([EXPECTED_LINES[i][1] for i in selected]),
                        attenuation,
                    )
                    values.append(float(attenuated[:-2].sum() / attenuated[-2:].sum()))
            families[str(composition)] = {"minimum": min(values), "maximum": max(values)}
        left = max(families["0"]["minimum"], families["1"]["minimum"])
        right = min(families["0"]["maximum"], families["1"]["maximum"])
        result.append(
            {
                "ion_group": name,
                "component_line_labels_A": [EXPECTED_LINES[i][1] for i in indices],
                "wavelength_medium": convention,
                "ratio_to_CIII": families,
                "finite_range_overlap": None if right < left else [left, right],
                "interpretation": (
                    "Finite thermal-model/attenuation prediction ranges, not "
                    "confidence intervals, stage corrections or sensitivity forecasts"
                ),
            }
        )
    return result


def run(pilot: dict) -> dict:
    validate_models(pilot)
    plan = json.loads((SOURCE / "cloudy_contrast_plan.json").read_text())
    curves = read_nominal_curves()
    started = time.monotonic()
    cases = []
    for response in ("intrinsic_line_values", "emergent_line_values"):
        for bundle in plan["bundles"]:
            indices = tuple(index for group in bundle["groups"] for index in GROUPS[group])
            waves = np.array([EXPECTED_LINES[index][1] for index in indices]) * 15.44 / 1e4
            for mode in ("g235m", "g235h"):
                w, r = curves[mode]
                if np.any(waves < max(w.min(), 1.66)) or np.any(waves > min(w.max(), 3.17)):
                    raise ValueError("target outside nominal mode/tabulated response")
                resolving = np.interp(waves, w, r)
                for width in plan["intrinsic_fwhm_km_s"]:
                    gram = gaussian_gram(waves, resolving, width)
                    comparison = compare_family(
                        pilot["models"], indices, gram, plan["attenuation_A1500_mag"], response
                    )
                    cases.append(
                        {
                            "bundle": bundle["name"],
                            "response": response,
                            "mode": mode,
                            "intrinsic_fwhm_km_s": width,
                            "component_indices": list(indices),
                            "component_wavelengths_observed_um": waves.tolist(),
                            **comparison,
                        }
                    )
                    if time.monotonic() - started > plan["computation_cap_seconds"]:
                        raise RuntimeError("bounded computation cap exceeded; no expansion allowed")
    return {
        "schema_version": 1,
        "experiment_id": plan["experiment_id"],
        "plan": plan,
        "cases": cases,
        "extra_stage_ranges": {
            response: stage_ranges(pilot["models"], plan["attenuation_A1500_mag"], response)
            for response in ("intrinsic_line_values", "emergent_line_values")
        },
        "input_plan_sha256": hashlib.sha256(
            (SOURCE / "cloudy_contrast_plan.json").read_bytes()
        ).hexdigest(),
        "composition_reference": {
            "ordinary_log_NC": pilot["ordinary_reference_log_NC"],
            "enhanced_log_NC": pilot["ordinary_reference_log_NC"] + 1.0,
            "declared_log_CO": pilot["reference_log_CO"],
            "unmodified_solar_pattern": False,
            "scope": (
                "GASS10 base with custom gas-phase C/N/O; ordinary is a declared model reference"
            ),
        },
        "calibration_scope": {
            "source_LSF_measured": False,
            "source_centroid_calibration_measured": False,
            "aperture_specific_gap_coverage_verified": False,
            "model_emergent_intrinsic_difference_bounds_source_CIV_transfer": False,
            "new_observing_time_demonstrated_essential": False,
        },
        "matched_native_observations_used": False,
        "new_observations_obtained": False,
        "alternative_response_contracts_pooled": False,
        "absolute_exposure_seconds": None,
        "interpretation": (
            "Conditional discrimination among finite Cloudy thermal models "
            "with known nuisance assumptions; not an abundance likelihood, "
            "posterior, source calibration or guaranteed observing feasibility"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=ROOT / "research_output/mom_cloudy_pilot.json"
    )
    parser.add_argument("--validated-merged-revision", required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "research_output/mom_cloudy_observation_contrasts.json",
    )
    args = parser.parse_args()
    payload = args.input.read_bytes()
    if hashlib.sha256(payload).hexdigest() != args.input_sha256:
        raise ValueError("complete input differs from frozen reviewed pin")
    revision = args.validated_merged_revision
    if len(revision) != 40 or any(char not in "0123456789abcdef" for char in revision):
        raise ValueError("exact validated merged revision required")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", revision, "origin/master"], cwd=ROOT, check=True
    )
    saved = subprocess.check_output(
        ["git", "show", f"{revision}:{args.input.resolve().relative_to(ROOT)}"], cwd=ROOT
    )
    if saved != payload:
        raise ValueError("actual model input is not exact merged artifact")
    result = run(json.loads(payload))
    result.update(input_sha256=args.input_sha256, validated_merged_input_revision=revision)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
