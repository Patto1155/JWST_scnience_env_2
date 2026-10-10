"""Independent paired-table, XML zeropoint and scalar-GLS FLAME audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np

BANDS = ("F090W", "F115W", "F150W", "F200W", "F277W", "F356W", "F444W")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def raw_models(root, archive_path, deep):
    manifest = json.loads((root / "data_sources/survivor_flame/manifest.json").read_text())
    assert sha(archive_path) == manifest["product"]["sha256"]
    points = []
    for band in BANDS:
        params = {
            element.attrib.get("name"): element.attrib.get("value")
            for element in ET.parse(deep / f"svo_{band}.xml").iter()
            if element.tag.rsplit("}", 1)[-1] == "PARAM"
        }
        assert params["MagSys"] == "Vega" and params["ZeroPointUnit"] == "Jy"
        points.append(float(params["ZeroPoint"]))
    points = np.array(points)
    tables = {entry["member"]: entry for entry in manifest["tables"]}
    conventional = []
    inferred = []
    chemistry = []
    with zipfile.ZipFile(archive_path) as archive:
        for name in sorted(tables):
            if not name.endswith("_flux.txt"):
                continue
            partner = name.replace("_flux.txt", "_mag.txt")
            raw, raw_magnitude = archive.read(name), archive.read(partner)
            assert hashlib.sha256(raw).hexdigest() == tables[name]["sha256"]
            assert hashlib.sha256(raw_magnitude).hexdigest() == tables[partner]["sha256"]
            lines = raw.decode("ascii").splitlines()
            maglines = raw_magnitude.decode("ascii").splitlines()
            columns = lines[0].split()
            assert columns == maglines[0].split()
            assert len(columns) == len(set(columns))
            a = np.loadtxt(lines[1:])
            m = np.loadtxt(maglines[1:])
            indices = [columns.index(band) for band in BANDS]
            assert np.array_equal(a[:, : columns.index("F070W")], m[:, : columns.index("F070W")])
            teff, gravity = a[:, columns.index("Teff")], a[:, columns.index("log(g)")]
            keep = (teff >= 200) & (teff <= 1000) & (gravity >= 3.5) & (gravity <= 5.5)
            flux = a[keep][:, indices] * 1e6
            magnitude_flux = points[None, :] * 10 ** (-0.4 * m[keep][:, indices]) * 1e9
            conventional.extend(magnitude_flux)
            inferred.extend(flux)
            chemistry.extend(["deq" if "/deq/" in name else "eq"] * keep.sum())
    inferred, conventional = np.array(inferred), np.array(conventional)
    ratios = inferred / conventional
    assert len(inferred) == 37800
    assert np.max(abs(ratios - 1)) < 0.006
    return {"inferred_mjy": inferred, "vega_svo": conventional}, np.array(chemistry), ratios


def scalar_gls(y, c, models, keep=None):
    keep = np.arange(len(y)) if keep is None else np.asarray(keep)
    shape = models / models[:, -1, None]
    precision = np.linalg.inv(c[np.ix_(keep, keep)])
    selected = shape[:, keep]
    numerator = selected @ precision @ y[keep]
    denominator = np.einsum("ij,ij->i", selected @ precision, selected)
    amplitude = np.maximum(numerator / denominator, 0)
    residual = y[keep] - amplitude[:, None] * selected
    chi2 = np.einsum("ij,ij->i", residual @ precision, residual)
    return chi2, amplitude, shape


def audit(root, archive, deep, report_path):
    models, chemistry, ratio = raw_models(root, archive, deep)
    report = json.loads(report_path.read_text())
    y = np.array(report["observed_njy"])
    records = []
    for scenario in report["scenarios"]:
        prediction = models[scenario["photometry_convention"]]
        c = np.array(scenario["covariance_njy2"])
        losses, amplitudes, shape = scalar_gls(y, c, prediction)
        for saved in scenario["best_by_chemistry"]:
            use = (
                np.ones(len(losses), dtype=bool)
                if saved["chemistry_subset"] == "all"
                else chemistry == saved["chemistry_subset"]
            )
            optimum = np.flatnonzero(use)[np.argmin(losses[use])]
            assert optimum == saved["grid_index"]
            assert abs(losses[optimum] - saved["chi2_conditional"]) < 1e-8
            assert (
                np.max(abs(amplitudes[optimum] * shape[optimum] - saved["prediction_njy"])) < 1e-8
            )
        for i, saved in enumerate(scenario["held_out_predictions"]):
            assert saved["omitted_band"] == BANDS[i]
            keep = np.delete(np.arange(7), i)
            losses, a, shape = scalar_gls(y, c, prediction, keep)
            optimum = int(np.argmin(losses))
            assert optimum == saved["grid_index"]
            predicted = a[optimum] * shape[optimum]
            assert np.max(abs(predicted - saved["prediction_njy"])) < 1e-8
            sub = c[np.ix_(keep, keep)]
            cross = c[i, keep]
            adjusted = y[i] - predicted[i] - cross @ np.linalg.solve(sub, y[keep] - predicted[keep])
            z = adjusted / np.sqrt(c[i, i] - cross @ np.linalg.solve(sub, cross))
            assert abs(z - saved["conditional_residual_over_assumed_sigma"]) < 1e-8
        records.append(
            {
                "convention": scenario["photometry_convention"],
                "floor": scenario["fractional_floor_assumed"],
                "best_chi2": float(scenario["best_by_chemistry"][0]["chi2_conditional"]),
                "independent_grid_and_all_heldout_minima_match": True,
            }
        )
    return {
        "schema_version": 1,
        "archive_sha256": sha(archive),
        "report_sha256": sha(report_path),
        "rows": len(chemistry),
        "ratio_min_by_band": ratio.min(axis=0).tolist(),
        "ratio_max_by_band": ratio.max(axis=0).tolist(),
        "independent_scalar_GLS": records,
        "scope": (
            "Actual paired flux/magnitude table and independently decoded Vega/Jy audit; "
            "flux units inferred by consistency, not documented author unit confirmation; "
            "conditional finite single-row grid only"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("root", "archive", "deep", "report", "output"):
        parser.add_argument("--" + arg, type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root, args.archive, args.deep, args.report)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
