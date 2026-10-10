"""Independent raw ordinary-model backend-equivalence audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from discovery.research2_cloudy_composition_review import audit as composition_audit
from discovery.research2_cloudy_model_review import read_actual_line_dictionary
from discovery.research2_independent_review import digest


def audit(reference_path, control_path, cache, libraries):
    reference = json.loads(reference_path.read_text())
    control = json.loads(control_path.read_text())
    assert digest(reference_path) == control["reference_sha256"]
    first, second = reference["models"][0], control["control_model"]
    assert first["parameters"] == second["parameters"]
    runs = cache / "openblas-control"
    original = cache / "corrected-runs"
    for item in second["files"]:
        path = runs / item["name"]
        assert path.stat().st_size == item["bytes"] and digest(path) == item["sha256"]
    exact = {}
    for suffix in ("in", "lin", "emergent.lin", "avr", "abn"):
        filename = "model000." + suffix
        exact[filename] = (original / filename).read_bytes() == (runs / filename).read_bytes()
    assert all(exact.values())
    for suffix in ("lin", "emergent.lin"):
        values, _ = read_actual_line_dictionary(runs / ("model000." + suffix), reference["lines"])
        assert np.array_equal(
            values, second["intrinsic_line_values" if suffix == "lin" else "emergent_line_values"]
        )
    composition = composition_audit(
        runs / "model000.out", second["parameters"], runs / "model000.abn"
    )
    text = (runs / "model000.out").read_text()
    summary = next(line.strip() for line in text.splitlines() if "Cloudy ends:" in line)
    assert summary == second["convergence_summary"]
    assert not any(word in summary.lower() for word in ("warning", "failure", "disaster"))
    a, b = np.loadtxt(original / "model000.ovr"), np.loadtxt(runs / "model000.ovr")
    assert a.shape == b.shape == (234, 26)
    relative = np.max(abs(a - b) / np.maximum(abs(a), 1e-300), axis=0)
    assert relative[1] < 0.001 and relative.max() < 0.003
    build = control["openblas_build"]
    executable = cache / "c23.01/source/sys_pilot/cloudy-openblas.exe"
    assert digest(executable) == build["executable_sha256"]
    for item in build["lapack_backend"]["existing_libraries"]:
        path = libraries / item["name"]
        assert path.stat().st_size == item["bytes"] and digest(path) == item["sha256"]
    wrapper = (cache / "c23.01/source/thirdparty_lapack.cpp").read_text()
    assert 'extern "C" void dgetrf_(int32 *M' in wrapper
    assert 'extern "C" void dgtsv_(int32 *n' in wrapper
    return {
        "schema_version": 1,
        "control_receipt_sha256": digest(control_path),
        "reference_sha256": digest(reference_path),
        "exact_saved_files": exact,
        "actual_composition": composition,
        "zone_overview_byte_exact": False,
        "maximum_zone_temperature_difference_K": float(np.max(abs(a[:, 1] - b[:, 1]))),
        "maximum_zone_temperature_relative_difference": float(relative[1]),
        "maximum_overview_relative_difference": float(relative.max()),
        "zone_overview_relative_difference_by_column": relative.tolist(),
        "openblas_executable_sha256": digest(executable),
        "scope": (
            "Ordinary control printed-line and weighted-temperature equivalence only; "
            "slight zone-profile changes recorded. Not universal backend equivalence "
            "or a code-independent thermal solution."
        ),
    }


def enhanced_audit(reference_path, control_path, cache):
    reference = json.loads(reference_path.read_text())
    control = json.loads(control_path.read_text())
    original, revised = control["original_model"], control["consistent_backend_model"]
    assert next(m for m in reference["models"] if m["id"] == "model001") == original
    assert original["parameters"] == revised["parameters"]
    models = ((original, cache / "focused-pair"), (revised, cache / "revised-runs"))
    for model, runs in models:
        for item in model["files"]:
            path = runs / item["name"]
            assert path.stat().st_size == item["bytes"] and digest(path) == item["sha256"]
        text = (runs / "model001.out").read_text()
        summary = next(line.strip() for line in text.splitlines() if "Cloudy ends:" in line)
        assert summary == model["convergence_summary"]
        assert not any(word in summary.lower() for word in ("warning", "failure", "disaster"))
        composition_audit(runs / "model001.out", model["parameters"], runs / "model001.abn")
        for suffix in ("lin", "emergent.lin"):
            read_actual_line_dictionary(runs / ("model001." + suffix), reference["lines"])
    equal = {}
    for suffix in ("in", "lin", "emergent.lin", "avr", "abn"):
        filename = "model001." + suffix
        equal[filename] = (models[0][1] / filename).read_bytes() == (
            models[1][1] / filename
        ).read_bytes()
    assert all(equal.values())
    first = np.loadtxt(models[0][1] / "model001.ovr")
    second = np.loadtxt(models[1][1] / "model001.ovr")
    assert first.shape == second.shape == (236, 26)
    relative = np.max(abs(first - second) / np.maximum(abs(first), 1e-300), axis=0)
    assert relative[1] < 1e-4
    assert np.array_equal(first[:, 0], second[:, 0])
    assert (
        digest(cache / "c23.01/source/sys_pilot/cloudy-lapack.exe")
        == control["original_executable_sha256"]
    )
    assert (
        digest(cache / "c23.01/source/sys_pilot/cloudy-openblas.exe")
        == control["new_executable_sha256"]
    )
    return {
        "schema_version": 1,
        "control_receipt_sha256": digest(control_path),
        "original_pair_sha256": digest(reference_path),
        "actual_control_file_count": 14,
        "exact_saved_files": equal,
        "zone_overview_byte_exact": np.array_equal(first, second),
        "maximum_zone_temperature_difference_K": float(np.max(abs(first[:, 1] - second[:, 1]))),
        "maximum_zone_temperature_relative_difference": float(relative[1]),
        "depth_byte_exact": True,
        "scope": (
            "Enhanced model printed-line/average-temperature equivalence under pinned binaries; "
            "small zone-temperature differences. No general speedup or full-profile identity."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("reference", "control", "cache", "libraries", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--enhanced", action="store_true")
    args = parser.parse_args()
    reviewed = (
        enhanced_audit(args.reference, args.control, args.cache)
        if args.enhanced
        else audit(args.reference, args.control, args.cache, args.libraries)
    )
    args.output.write_text(json.dumps(reviewed, indent=2) + "\n")


if __name__ == "__main__":
    main()
