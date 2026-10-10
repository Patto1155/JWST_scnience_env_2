"""Independent actual Cloudy composition guard; reject double metals scaling."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np


def expected_logs(parameters):
    selected = [
        parameters[key] for key in ("metallicity_scale", "log_CO", "log_NC_relative_minus060")
    ]
    if not np.isfinite(selected).all() or selected[0] <= 0:
        raise ValueError("Finite composition and positive metallicity required")
    oxygen = np.log10(4.90e-4 * parameters["metallicity_scale"])
    carbon = oxygen + parameters["log_CO"]
    nitrogen = carbon - 0.60 + parameters["log_NC_relative_minus060"]
    return np.array([carbon, nitrogen, oxygen])


def actual_out_composition(text, parameters):
    blocks = text.split("Gas Phase Chemical Composition")[1:]
    if not blocks:
        raise ValueError("No actual gas-phase composition printed")
    expected = expected_logs(parameters)
    records = []
    for block in blocks:
        line = block.splitlines()[1]
        values = []
        for symbol in ("C", "N", "O"):
            matched = re.search(r"(?<![A-Za-z])" + symbol + r"\s*:\s*(-?\d+\.\d+)", line)
            if matched is None:
                raise ValueError("Required actual abundance label missing: " + symbol)
            values.append(float(matched.group(1)))
        if np.max(abs(np.array(values) - expected)) > 6e-5:
            raise ValueError("Actual C/N/O composition disagrees with declared gas abundances")
        records.append(values)
    return {
        "expected_log_CNO_over_H": expected.tolist(),
        "actual_printed_log_CNO_over_H": records,
        "abundance_print_tolerance_dex": 6e-5,
    }


def actual_zone_composition(text, parameters):
    lines = text.splitlines()
    if not lines or not lines[0].startswith("#abund H"):
        raise ValueError("Missing actual zone abundance header")
    symbols = lines[0].split()[1:]
    positions = [symbols.index(name) for name in ("H", "CARB", "NITR", "OXYG")]
    numbers = np.loadtxt(lines[1:])
    numbers = np.atleast_2d(numbers)
    if not len(numbers) or not np.isfinite(numbers).all():
        raise ValueError("No finite actual zone abundance values")
    values = numbers[:, positions[1:]] - numbers[:, positions[0], None]
    expected = expected_logs(parameters)
    error = float(np.max(abs(values - expected)))
    if error > 0.0101:
        raise ValueError("Actual zone C/N/O relative to H disagrees with declared composition")
    return {
        "actual_zone_rows": len(numbers),
        "maximum_log_CNO_over_H_error_dex": error,
        "two_column_rounding_tolerance_dex": 0.0101,
    }


def audit(outpath, parameters, zonepath=None):
    result = actual_out_composition(outpath.read_text(), parameters)
    result["output_sha256"] = hashlib.sha256(outpath.read_bytes()).hexdigest()
    if zonepath is not None:
        result["zones"] = actual_zone_composition(zonepath.read_text(), parameters)
        result["zone_output_sha256"] = hashlib.sha256(zonepath.read_bytes()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cloudy-output", type=Path, required=True)
    parser.add_argument("--zone-abundances", type=Path)
    parser.add_argument("--parameters", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(
            audit(
                args.cloudy_output, json.loads(args.parameters.read_text()), args.zone_abundances
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
