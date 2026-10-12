"""Independent GOODS-S paired-line integration; imports no author fitting code.

Operator/coding-agent audit of released coadds. Diagonal uncertainties are
conditional, and aperture/nod variants are dependent sensitivity checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from astropy.io import fits


def integrate(data, center: float, half_width: float, field: str, error_field: str) -> dict:
    wave = np.asarray(data["WAVELENGTH"], float)
    flux = np.asarray(data[field], float) / 1e-20
    error = np.asarray(data[error_field], float) / 1e-20
    assert len(wave) >= 2 and np.all(np.diff(wave) > 0)
    edges = np.r_[
        wave[0] - (wave[1] - wave[0]) / 2,
        (wave[:-1] + wave[1:]) / 2,
        wave[-1] + (wave[-1] - wave[-2]) / 2,
    ]
    valid = np.isfinite(flux) & np.isfinite(error) & (error > 0)
    side = valid & (wave >= center + 0.008) & (wave <= center + 0.015)
    widths = (
        np.maximum(
            0,
            np.minimum(edges[1:], center + half_width)
            - np.maximum(edges[:-1], center - half_width),
        )
        * 1e4
    )
    inside = valid & (widths > 0)
    fraction = float(widths[inside].sum() / (2 * half_width * 1e4))
    result = {
        "center_um": center,
        "half_width_um": half_width,
        "finite_window_fraction": fraction,
        "line_bins": int(inside.sum()),
        "continuum_bins": int(side.sum()),
        "continuum_sideband_relative_um": [0.008, 0.015],
        "first_finite_wave_um": float(wave[valid].min()) if valid.any() else None,
        "last_finite_wave_um": float(wave[valid].max()) if valid.any() else None,
        "flux_1e20": None,
        "conditional_diagonal_error_1e20": None,
        "status": "insufficient_coverage",
    }
    if fraction < 0.9 - 1e-10 or side.sum() < 4 or inside.sum() < 2:
        return result
    weights = 1 / error[side] ** 2
    baseline = float(np.sum(weights * flux[side]) / weights.sum())
    total_width = widths[inside].sum()
    value = float(np.sum((flux[inside] - baseline) * widths[inside]))
    variance = float(np.sum((error[inside] * widths[inside]) ** 2) + total_width**2 / weights.sum())
    result.update(
        flux_1e20=value,
        conditional_diagonal_error_1e20=float(np.sqrt(variance)),
        continuum_1e20_per_A=baseline,
        status="conditional_measurement",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    targets = manifest.get("targets", manifest.get("rows", manifest.get("cohort", [])))
    if not targets:
        raise ValueError("Manifest must contain targets, rows, or cohort list")
    results = []
    for target in targets:
        unique_id = target["unique_id"]
        assert unique_id.startswith("goods-s-"), "GOODS-N holdout prohibited"
        tier, ident = unique_id.rsplit("_", 1)
        z = float(target.get("z", target.get("redshift")))
        group = target.get("group", target.get("stratum"))
        measured, sources = {}, []
        for config in ["f070lp-g140m", "f170lp-g235m"]:
            path = (
                args.data_root
                / f"hlsp_jades_jwst_nirspec_{tier}-{int(ident):08d}_{config}_v1.0_x1d.fits"
            )
            if not path.exists():
                sources.append(
                    {"config": config, "status": "missing_product", "filename": path.name}
                )
                continue
            sources.append(
                {
                    "config": config,
                    "status": "verified_product",
                    "filename": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
            with fits.open(path) as h:
                assert h[0].header["TARGET"] == f"{int(ident):08d}"
                assert h[0].header["HLSPTIER"] == tier
                assert abs(float(h[0].header["RA"]) - float(target["ra_deg"])) < 1e-6
                assert abs(float(h[0].header["DEC"]) - float(target["dec_deg"])) < 1e-6
                assert h[1].columns["WAVELENGTH"].unit == "um"
                assert h[1].columns["FLUX"].unit == "erg s-1 cm-2 AA-1"
                for aperture in [5, 3]:
                    data = h[f"EXTRACT{aperture}PIX1D"].data
                    for field, error_field in [
                        ("FLUX", "FLUX_ERR"),
                        ("FLUX_NOD2", "FLUX_ERR_NOD2"),
                    ]:
                        for line, rest in [("Hb", 4862.68), ("OIII", 5008.24)]:
                            for width in [0.0025, 0.0035, 0.0045]:
                                key = f"{config}_{aperture}pix_{field}_{line}_{width:.4f}"
                                measured[key] = integrate(
                                    data, rest * (1 + z) / 1e4, width, field, error_field
                                )
        contrasts = {}
        for aperture in [5, 3]:
            for field in ["FLUX", "FLUX_NOD2"]:
                for width in [0.0025, 0.0035, 0.0045]:
                    values = {}
                    for line in ["Hb", "OIII"]:
                        entries = [
                            measured.get(f"{config}_{aperture}pix_{field}_{line}_{width:.4f}", {})
                            for config in ["f070lp-g140m", "f170lp-g235m"]
                        ]
                        fs = [entry.get("flux_1e20") for entry in entries]
                        if all(f is not None and f > 0 for f in fs):
                            values[line] = float(np.log(fs[1] / fs[0]))
                        else:
                            values[line] = None
                    d = (
                        values["Hb"] - values["OIII"]
                        if all(v is not None for v in values.values())
                        else None
                    )
                    contrasts[f"{aperture}pix_{field}_{width:.4f}"] = {
                        "log_Hb_235_over_140": values["Hb"],
                        "log_OIII_235_over_140": values["OIII"],
                        "D": d,
                    }
        results.append(
            {
                "unique_id": unique_id,
                "z": z,
                "group": group,
                "sources": sources,
                "measurements": measured,
                "contrasts": contrasts,
            }
        )
    summaries = {}
    for group in sorted({r["group"] for r in results}):
        cohort = [r for r in results if r["group"] == group]
        for key in results[0]["contrasts"]:
            ds = [r["contrasts"][key]["D"] for r in cohort if r["contrasts"][key]["D"] is not None]
            summaries[f"{group}_{key}"] = {
                "selected_n": len(cohort),
                "positive_covered_n": len(ds),
                "median_D": float(np.median(ds)) if ds else None,
                "positive_D_n": int(np.sum(np.asarray(ds) > 0)),
                "negative_D_n": int(np.sum(np.asarray(ds) < 0)),
            }
    output = {
        "scope": "Exploratory GOODS-S-only frozen metadata cohort; GOODS-N unopened",
        "method": (
            "Direct bin-clipped summation, inverse-variance constant "
            "red-sideband continuum; no Gaussian fit"
        ),
        "limits": (
            "Diagonal conditional errors; unknown pixel/calibration covariance; "
            "variants share photons; positive-flux contrast eligibility can condition summary"
        ),
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "targets": results,
        "group_summaries": summaries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
