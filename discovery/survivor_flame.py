"""Source46 updated-chemistry atmosphere pilot with a fail-closed unit audit.

Author notebook unit prose conflicts with actual paired photometry. Interpret
flux as mJy only after every retained row matches independent SVO Vega/Jy
zeropoints within tabulated magnitude rounding (0.01mag). Both conventions are
fit separately. Results remain conditional model-family comparisons.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import zipfile
from pathlib import Path

import numpy as np
from astropy.io.votable import parse

from data_pipeline.research_sources import fetch_product
from data_pipeline.survivor_deep_data import verify_pinned
from discovery.survivor_atmosphere import BANDS

MANIFEST = Path(__file__).resolve().parents[1] / "data_sources/survivor_flame/manifest.json"


def parse_table(text):
    lines = text.splitlines()
    header = lines[0].split()
    if len(header) != len(set(header)) or not set(BANDS).issubset(header):
        raise ValueError("Missing or duplicate actual JWST band header")
    required = ["Teff", "log(g)", "Mass/Mjup", "Radius/Rjup", "Age/Gyr", "log(L/Lsun)"]
    if not set(required).issubset(header):
        raise ValueError("Missing physical header identity")
    rows = [line.split() for line in lines[1:] if line.strip()]
    if any(len(row) != len(header) for row in rows):
        raise ValueError("Table row lengths disagree")
    values = np.array(rows, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Nonfinite table values")
    return header, values


def zeropoints(directory):
    points = []
    receipts = []
    inventory = json.loads(
        (
            Path(__file__).resolve().parents[1] / "data_sources/survivor_deep/manifest.json"
        ).read_text()
    )
    for band in BANDS:
        product = next(p for p in inventory["products"] if p["id"] == "throughput-" + band)
        path = directory / product["filename"]
        receipt = verify_pinned(path, product)
        votable = parse(path)
        params = {p.name: p.value for r in votable.resources for t in r.tables for p in t.params}
        if (
            params.get("MagSys") != "Vega"
            or params.get("ZeroPointUnit") != "Jy"
            or params.get("ZeroPointType") != "Pogson"
        ):
            raise ValueError("Unexpected SVO magnitude/zeropoint identity")
        point = float(params["ZeroPoint"])
        if point <= 0:
            raise ValueError("Nonpositive zeropoint")
        points.append(point)
        receipts.append({"band": band, "zero_point_jy": point, "receipt": receipt})
    return np.array(points), receipts


def audit_units(raw_flux, magnitude, point_jy):
    """Actual cross-file identity: inferred mJy agrees with independent Vega/Jy."""
    inferred_njy = raw_flux * 1e6
    vega_njy = 10 ** (-0.4 * magnitude) * point_jy * 1e9
    if np.any(inferred_njy <= 0) or np.any(vega_njy <= 0):
        raise ValueError("Nonpositive band prediction")
    ratio = inferred_njy / vega_njy
    if np.any(np.abs(ratio - 1) > 0.006):
        raise ValueError("Flux/magnitude/independent-zeropoint consistency failed")
    return inferred_njy, vega_njy, ratio


def load(directory, deep_directory):
    inventory = json.loads(MANIFEST.read_text())
    product = inventory["product"]
    path = directory / product["filename"]
    if not path.exists():
        fetch_product(product, path, max_bytes=product["max_bytes"], timeout=45)
    receipt = verify_pinned(path, product)
    if hashlib.md5(path.read_bytes()).hexdigest() != product["publisher_md5"]:
        raise ValueError("Publisher MD5 mismatch")
    points, point_receipts = zeropoints(deep_directory)
    indexed = {t["member"]: t for t in inventory["tables"]}
    metadata = []
    inferred = []
    vega = []
    ratios = []
    with zipfile.ZipFile(path) as archive:
        for name in sorted(indexed):
            if not name.endswith("_flux.txt"):
                continue
            partner = name.replace("_flux", "_mag")
            texts = []
            for selected in (name, partner):
                data = archive.read(selected)
                if (
                    len(data) != indexed[selected]["bytes"]
                    or hashlib.sha256(data).hexdigest() != indexed[selected]["sha256"]
                ):
                    raise ValueError("Pinned archive member mismatch")
                texts.append(data.decode("ascii"))
            h, a = parse_table(texts[0])
            hm, m = parse_table(texts[1])
            if h != hm or not np.array_equal(a[:, : h.index("F070W")], m[:, : h.index("F070W")]):
                raise ValueError("Flux/magnitude physical rows disagree")
            keep = (
                (a[:, h.index("Teff")] >= 200)
                & (a[:, h.index("Teff")] <= 1000)
                & (a[:, h.index("log(g)")] >= 3.5)
                & (a[:, h.index("log(g)")] <= 5.5)
            )
            selected = np.flatnonzero(keep)
            columns = [h.index(b) for b in BANDS]
            f, v, r = audit_units(a[keep][:, columns], m[keep][:, columns], points)
            inferred.extend(f)
            vega.extend(v)
            ratios.extend(r)
            labels = re.search(r"mh([+-][\d.]+)_co([\d.]+)_flux", name)
            for index in selected:
                metadata.append(
                    {
                        "table_member": name,
                        "author_row": int(index + 2),
                        "chemistry": "deq" if "/deq/" in name else "eq",
                        "teff_k": float(a[index, h.index("Teff")]),
                        "logg_cgs": float(a[index, h.index("log(g)")]),
                        "metallicity_dex": float(labels[1]),
                        "co_relative_to_solar": float(labels[2]),
                        "logkzz": float(a[index, h.index("log(kzz)")]) if "log(kzz)" in h else None,
                        "tabulated_mass_mjup": float(a[index, h.index("Mass/Mjup")]),
                        "tabulated_radius_rjup": float(a[index, h.index("Radius/Rjup")]),
                        "tabulated_age_gyr": float(a[index, h.index("Age/Gyr")]),
                    }
                )
    ratios = np.array(ratios)
    return (
        metadata,
        {"inferred_mjy": np.array(inferred), "vega_svo": np.array(vega)},
        {
            "archive_receipt": receipt,
            "zeropoints": point_receipts,
            "rows": len(metadata),
            "unit_ratio_min_by_band": ratios.min(axis=0).tolist(),
            "unit_ratio_max_by_band": ratios.max(axis=0).tolist(),
            "unit_ratio_median_by_band": np.median(ratios, axis=0).tolist(),
            "unit_resolution": "Independent paired-table/zeropoint consistency implies mJy; notebook F_lambda prose rejected for these table numbers.",
        },
    )


def fit_vectorized(flux, covariance, absolute, metadata, retained=None):
    keep = np.arange(len(flux)) if retained is None else np.asarray(retained)
    shapes = absolute / absolute[:, -1, None]
    lower = np.linalg.cholesky(covariance[np.ix_(keep, keep)])
    design = np.linalg.solve(lower, shapes[:, keep].T).T
    data = np.linalg.solve(lower, flux[keep])
    amplitudes = np.maximum((design @ data) / np.einsum("ij,ij->i", design, design), 0)
    residual = data - amplitudes[:, None] * design
    objectives = np.einsum("ij,ij->i", residual, residual)
    results = []
    for chemistry in ("all", "eq", "deq"):
        indices = (
            np.arange(len(metadata))
            if chemistry == "all"
            else np.array([i for i, x in enumerate(metadata) if x["chemistry"] == chemistry])
        )
        if not len(indices):
            continue
        best = int(indices[np.argmin(objectives[indices])])
        pred = amplitudes[best] * shapes[best]
        results.append(
            {
                "chemistry_subset": chemistry,
                "grid_index": best,
                "chi2_conditional": float(objectives[best]),
                "f444_amplitude_njy": float(amplitudes[best]),
                "prediction_njy": pred.tolist(),
                "model": metadata[best],
            }
        )
    return results


def run(directory, deep, photometry, output):
    start = time.perf_counter()
    metadata, models, provenance = load(directory, deep)
    if (
        hashlib.sha256(photometry.read_bytes()).hexdigest()
        != json.loads(MANIFEST.read_text())["photometry_sha256"]
    ):
        raise ValueError("Photometry contract changed")
    photo = json.loads(photometry.read_text())
    source = next(x for x in photo["sources"] if x["source_id"] == 46)
    if tuple(photo["bands"]) != BANDS:
        raise ValueError("Wrong photometry bands")
    flux = np.array([x["fixed_extended_fit"]["flux_njy"] for x in source["bands"]])
    scenarios = []
    for convention, absolute in models.items():
        for sensitivity in source["phenomenological_continuum_sensitivity"]:
            covariance = np.array(sensitivity["flux_covariance_njy2"])
            fitted = fit_vectorized(flux, covariance, absolute, metadata)
            held = []
            for omitted in range(len(BANDS)):
                keep = np.delete(np.arange(len(BANDS)), omitted)
                best = fit_vectorized(flux, covariance, absolute, metadata, keep)[0]
                prediction = np.array(best["prediction_njy"])
                cross = covariance[omitted, keep]
                sub = covariance[np.ix_(keep, keep)]
                sigma = np.sqrt(covariance[omitted, omitted] - cross @ np.linalg.solve(sub, cross))
                adjusted = (
                    flux[omitted]
                    - prediction[omitted]
                    - cross @ np.linalg.solve(sub, flux[keep] - prediction[keep])
                )
                held.append(
                    {
                        "omitted_band": BANDS[omitted],
                        **best,
                        "conditional_residual_over_assumed_sigma": float(adjusted / sigma),
                    }
                )
            scenarios.append(
                {
                    "photometry_convention": convention,
                    "fractional_floor_assumed": sensitivity["independent_fractional_floor"],
                    "covariance_njy2": covariance.tolist(),
                    "best_by_chemistry": fitted,
                    "held_out_predictions": held,
                }
            )
    result = {
        "schema_version": 1,
        "source_id": 46,
        "bands": BANDS,
        "observed_njy": flux.tolist(),
        "provenance": provenance,
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "photometry_sha256": hashlib.sha256(photometry.read_bytes()).hexdigest(),
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scenarios": scenarios,
        "runtime_seconds": time.perf_counter() - start,
        "limits": [
            "Versioned finite cloudfree updated-opacity eq/deq family; not clouds or galaxies.",
            "Unit interpretation independently cross-validated numerically; inconsistent notebook prose is not silently applied.",
            "Zero points/passbands are nominal, not source-specific empirical calibration.",
            "Assumed covariance floors, source morphology and physical-model inadequacy remain.",
            "Tabulated evolution metadata are not fitted ages, distances or coevality evidence.",
            "No class probabilities, posterior grid-member counts or identity.",
        ],
    }
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--deep", type=Path, required=True)
    parser.add_argument("--photometry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    r = run(args.input, args.deep, args.photometry, args.output)
    print(
        json.dumps(
            [
                (
                    s["photometry_convention"],
                    s["fractional_floor_assumed"],
                    s["best_by_chemistry"][0]["chi2_conditional"],
                )
                for s in r["scenarios"]
            ]
        )
    )


if __name__ == "__main__":
    main()
