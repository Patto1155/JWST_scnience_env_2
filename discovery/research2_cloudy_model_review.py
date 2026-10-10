"""Independent actual-output review of complete thermal Cloudy pilot models."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path

import numpy as np

from discovery.research2_cloudy_composition_review import audit as composition_audit

UV_GROUPS = (
    ("N 4 1483.32A", "N 4 1486.50A"),
    ("C 4 1548.19A", "C 4 1550.77A"),
    ("He 2 1640.41A", "O 3 1660.81A", "O 3 1666.15A"),
    ("N 3 1746.82A", "N 3 1748.65A", "N 3 1749.67A", "N 3 1752.16A", "N 3 1753.99A"),
    ("C 3 1906.68A", "C 3 1908.73A"),
)
BLENDS = ("Blnd 1486.00A", "Blnd 1549.00A", "Blnd 1650.00A", "Blnd 1750.00A", "Blnd 1909.00A")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def archive_audit(receipt_path, archive_path, cache_root):
    receipt = json.loads(receipt_path.read_text())
    assert archive_path.stat().st_size == receipt["bytes"]
    assert sha(archive_path) == receipt["sha256"]
    members = {row["member"]: row for row in receipt["selected_members_verified_against_archive"]}
    count = len(members)
    with tarfile.open(archive_path) as archive:
        for item in archive:
            if item.name not in members:
                continue
            expected = members.pop(item.name)
            actual = archive.extractfile(item).read()
            assert len(actual) == expected["bytes"]
            assert hashlib.sha256(actual).hexdigest() == expected["sha256"]
            assert (cache_root / item.name).read_bytes() == actual
    assert not members
    return {
        "archive_sha256": receipt["sha256"],
        "actual_archive_members_verified": count,
        "receipt_sha256": sha(receipt_path),
        "extracted_cache_matches_archive": True,
    }


def read_actual_line_dictionary(path, expected):
    lines = path.read_text().splitlines()
    if len(lines) != 2 or not lines[0].startswith("#lineslist\t"):
        raise ValueError("Exactly one final line header and iteration row required")
    identities = [" ".join(value.split()) for value in lines[0].split("\t")[1:]]
    expected = [" ".join(f"{label} {wave:.2f}A".split()) for label, wave in expected]
    required = (
        [item for group in UV_GROUPS for item in group]
        + list(BLENDS)
        + [
            "H 1 4861.32A",
            "O 3 5006.84A",
            "N 2 6583.45A",
            "N 5 1238.82A",
            "N 5 1242.80A",
            "C 2 2323.50A",
            "C 2 2324.69A",
            "C 2 2325.40A",
            "C 2 2326.93A",
            "C 2 2328.12A",
        ]
    )
    if expected != required:
        raise ValueError("Declared line contract differs from independently required29 identities")
    if identities != expected or len(set(identities)) != 29:
        raise ValueError("Complete ordered29-line identity mismatch")
    fields = lines[1].split("\t")
    if not re.fullmatch(r"iteration \d+", fields[0]):
        raise ValueError("Missing actual final iteration identity")
    values = np.array([float(v) for v in fields[1:]])
    if len(values) != 29 or not np.isfinite(values).all() or np.any(values < 0):
        raise ValueError("Incomplete or nonphysical actual line intensity vector")
    data = dict(zip(identities, values, strict=True))
    sums = np.array([sum(data[name] for name in group) for group in UV_GROUPS])
    blend = np.array([data[name] for name in BLENDS])
    if not np.allclose(sums, blend, rtol=1e-4, atol=1e-30):
        raise ValueError("Complete independently summed UV groups differ from Cloudy blends")
    if np.any(sums <= 0):
        raise ValueError("Missing modeled UV group cannot be replaced by zero")
    return values, sums


def validate_final_physical_stop(summary, deck, overview, header):
    """Check a converged physical stop against declared limits and actual last zone."""
    if not re.search(r"Iteration (\d+) of \1$", summary):
        raise ValueError("Final model iteration has not converged")
    final = dict(zip(header, overview[-1], strict=True))
    if "low electron fraction." in summary:
        if "stop efrac -2" not in deck.splitlines() or final["eden"] / final["hden"] > 0.010001:
            raise ValueError("Electron-fraction stop disagrees with declared limit or actual zone")
        return "electron_fraction_0.01"
    if "lowest Te reached." in summary:
        if "stop temperature 1000 K" not in deck.splitlines() or final["Te"] > 1000.1:
            raise ValueError("Temperature stop disagrees with declared limit or actual zone")
        return "temperature_floor_1000K"
    raise ValueError("Undeclared or computation-limited final stop")


def audit(report_path, run_directory, source_directory, run_overrides=None):
    report = json.loads(report_path.read_text())
    assert report["line_contract_version"] == 2
    assert report["cloudy_release"] == "C23.01"
    actual = []
    primary_runs = run_directory
    for model in report["models"]:
        run_directory = (run_overrides or {}).get(model["id"], primary_runs)
        for item in model["files"]:
            path = run_directory / item["name"]
            assert path.stat().st_size == item["bytes"] and sha(path) == item["sha256"]
        name = model["id"]
        output = run_directory / (name + ".out")
        text = output.read_text()
        assert text.splitlines()[0].strip() == "Cloudy 23.01"
        summaries = re.findall(r"Cloudy ends:[^\n]+", text)
        assert len(summaries) == 1 and summaries[0] == model["convergence_summary"]
        assert not re.search(r"warning|failure|disaster|problem", summaries[0], re.I)
        stops = re.findall(r"Calculation stopped because[^\n]+", text)
        assert stops and re.search(r"Iteration (\d+) of \1$", stops[-1])
        assert "Intensity (erg/s/cm^2)." in text
        assert "iterate to convergence" in (run_directory / (name + ".in")).read_text()
        composition = composition_audit(
            output, model["parameters"], run_directory / (name + ".abn")
        )
        intrinsic, sums = read_actual_line_dictionary(
            run_directory / (name + ".lin"), report["lines"]
        )
        emergent, emergent_sums = read_actual_line_dictionary(
            run_directory / (name + ".emergent.lin"), report["lines"]
        )
        assert np.array_equal(intrinsic, model["intrinsic_line_values"])
        assert np.array_equal(emergent, model["emergent_line_values"])
        overview = np.loadtxt(run_directory / (name + ".ovr"))
        assert len(overview) == model["zones"]
        header = (run_directory / (name + ".ovr")).read_text().splitlines()[0].split()
        stop_contract = validate_final_physical_stop(
            stops[-1], (run_directory / (name + ".in")).read_text(), overview, header
        )
        assert np.array_equal(
            [overview[:, 1].min(), overview[:, 1].max()], model["zone_temperature_K_range"]
        )
        averages = np.loadtxt(run_directory / (name + ".avr"))
        assert len(averages) == 5 and np.all(averages > 0)
        assert overview[:, 1].min() <= averages[0] <= overview[:, 1].max()
        assert (run_directory / (name + ".avr")).read_text() == model[
            "hydrogen_weighted_temperature_output"
        ]
        actual.append(
            {
                "model_id": name,
                "file_pin_count": len(model["files"]),
                "composition": composition,
                "complete_intrinsic_group_intensities": sums.tolist(),
                "complete_emergent_group_intensities": emergent_sums.tolist(),
                "Hplus_weighted_temperature_K": float(averages[0]),
                "final_stop": stops[-1],
                "physical_stop_contract": stop_contract,
                "final_zones": len(overview),
            }
        )
    # Validate namespace and intensity interpretation against actual pinned source.
    prt = (source_directory / "source/prt.h").read_text()
    defaults = (source_directory / "source/init_defaults_preparse.cpp").read_text()
    driver = (source_directory / "source/cddrive.cpp").read_text()
    assert "use air wavelengths for wl > 2000A" in prt
    assert "prt.lgPrintLineAirWavelengths = true" in defaults
    assert "*absint = LineSave.lines[ipLine].SumLine(LineType) *" in driver
    assert "radius.Conv2PrtInten" in driver
    return {
        "schema_version": 1,
        "report_sha256": sha(report_path),
        "actual_models": actual,
        "actual_line_list_count": 29,
        "intensities_linear": True,
        "units": (
            "erg s^-1 cm^-2 in the printed Cloudy intensity geometry; no source distance conversion"
        ),
        "wavelength_namespace": (
            "Cloudy default vacuum below2000A, air above2000A; fitted14UV components allbelow2000"
        ),
        "primary_source_files_sha256": {
            name: sha(source_directory / "source" / name)
            for name in ("prt.h", "init_defaults_preparse.cpp", "cddrive.cpp", "iter_end_chk.cpp")
        },
        "scope": (
            "Actual converged code outputs and complete component/blend/abundance guards; "
            "not a code-independent thermal solver or measured source ionizing spectrum"
        ),
    }


def pilot20_parameters():
    """Independent enumeration of the declared ten environments and two N values."""
    base = (3.0, -2.0, 60000.0, 0.2)
    environments = [base]
    for axis, values in (
        (0, (2.0, 4.0, 5.0)),
        (1, (-3.0, -1.0)),
        (2, (40000.0, 100000.0)),
        (3, (0.05, 0.5)),
    ):
        for value in values:
            row = list(base)
            row[axis] = value
            environments.append(tuple(row))
    return [
        dict(
            zip(("log_nH_cm3", "log_U", "blackbody_K", "metallicity_scale"), row),
            log_CO=-0.37,
            log_NC_relative_minus060=nitrogen,
        )
        for row in environments
        for nitrogen in (0.0, 1.0)
    ]


def actual_deck_environment(path, parameters):
    text = path.read_text()
    numeric = {
        "blackbody_K": r"^blackbody ([\d.eE+-]+) K$",
        "log_U": r"^ionization parameter ([\d.eE+-]+)$",
        "log_nH_cm3": r"^hden ([\d.eE+-]+)$",
        "metallicity_scale": r"^metals ([\d.eE+-]+) linear$",
    }
    for key, expression in numeric.items():
        matches = re.findall(expression, text, re.M)
        if len(matches) != 1 or float(matches[0]) != parameters[key]:
            raise ValueError("Actual input deck physical setting mismatch: " + key)
    required = [
        "abundances GASS10",
        "radius 19",
        "sphere",
        "CMB redshift 14.44",
        "stop efrac -2",
        "stop temperature 1000 K",
        "stop zone 3000",
        "iterate to convergence",
    ]
    if any(text.splitlines().count(command) != 1 for command in required):
        raise ValueError("Actual input deck fixed physical contract mismatch")
    for element, expected in zip(
        ("oxygen", "carbon", "nitrogen"),
        (
            np.log10(4.90e-4),
            np.log10(4.90e-4) - 0.37,
            np.log10(4.90e-4) - 0.97 + parameters["log_NC_relative_minus060"],
        ),
    ):
        matches = re.findall(r"^element " + element + r" abundance ([\d.eE+-]+)$", text, re.M)
        if len(matches) != 1 or abs(float(matches[0]) - expected) > 1e-10:
            raise ValueError("Actual unscaled input composition mismatch: " + element)
    return text


def complete_pilot20_audit(report_path, run_directory):
    report = json.loads(report_path.read_text())
    models = report["models"]
    expected = pilot20_parameters()
    if len(models) != 20 or [m["id"] for m in models] != [f"model{i:03d}" for i in range(20)]:
        raise ValueError("Complete ordered twenty-model pilot required")
    if [m["parameters"] for m in models] != expected:
        raise ValueError("Complete pilot differs from declared physical parameter controls")
    actual = []
    decks = []
    for model in models:
        name = model["id"]
        parameters = model["parameters"]
        decks.append(actual_deck_environment(run_directory / (name + ".in"), parameters))
        overview = np.loadtxt(run_directory / (name + ".ovr"))
        header = (run_directory / (name + ".ovr")).read_text().splitlines()[0].split()
        hden = overview[:, header.index("hden")]
        if not np.allclose(hden, 10 ** parameters["log_nH_cm3"], rtol=1e-5, atol=0):
            raise ValueError("Actual zone hydrogen density disagrees with the declared environment")
        actual.append(
            {
                "model_id": name,
                "actual_zone_hydrogen_density_cm3": [float(hden.min()), float(hden.max())],
            }
        )
    for index in range(0, 20, 2):
        normalized = []
        for position in (index, index + 1):
            text = re.sub(r"model\d{3}", "MODEL", decks[position])
            text = re.sub(
                r"^element nitrogen abundance [^\n]+$", "NITROGEN_OVERRIDE", text, flags=re.M
            )
            normalized.append(text)
        if normalized[0] != normalized[1]:
            raise ValueError("Nitrogen-paired input decks change another instruction")
    return {
        "actual_environment_controls": actual,
        "complete_environment_count": 10,
        "nitrogen_only_deck_pair_count": 10,
        "scope": (
            "Actual declared input controls and zone densities; does not expand model coverage."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("report", "runs", "source", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--archive-receipt", type=Path)
    parser.add_argument("--require-complete-pilot20", action="store_true")
    parser.add_argument("--run-override", action="append", default=[], metavar="MODEL=DIRECTORY")
    args = parser.parse_args()
    overrides = {
        model: Path(directory)
        for model, directory in (value.split("=", 1) for value in args.run_override)
    }
    reviewed = audit(args.report, args.runs, args.source, overrides)
    if args.require_complete_pilot20:
        reviewed["complete_pilot20"] = complete_pilot20_audit(args.report, args.runs)
    if args.archive_receipt is not None:
        reviewed["actual_atomic_source_archive_audit"] = archive_audit(
            args.archive_receipt,
            args.source.parent / (args.source.name + ".tar.gz"),
            args.source.parent,
        )
    args.output.write_text(json.dumps(reviewed, indent=2) + "\n")


if __name__ == "__main__":
    main()
