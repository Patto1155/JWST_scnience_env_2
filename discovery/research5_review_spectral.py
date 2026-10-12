"""Independent clipped-bin CLASS line audit; 5720 is opt-in exploratory diagnostic."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_output"
Z = 0.08006536215543747
ALLOWED = {
    "27a4e980-5e21-11f0-9aca-525400f334e1",
    "2bf205a7-87cb-11ef-8f00-525400f334e1",
    "a6d1bcbc-885a-11ef-bbe3-525400f334e1",
    "6acc3cce-884f-11ef-9a35-525400f334e1",
}


def measure(
    record: dict, rest: float, width: float, sideband: tuple, policy: str, continuum: str
) -> dict:
    wave, flux, ivar = (
        np.array(record[key], dtype=float) for key in ["wavelength", "flux", "ivar"]
    )
    bits = np.array(record["mask"], dtype=np.int64)
    assert np.all(np.diff(wave) > 0)
    center = rest * (1 + Z)
    edges = np.r_[
        wave[0] - (wave[1] - wave[0]) / 2,
        (wave[:-1] + wave[1:]) / 2,
        wave[-1] + (wave[-1] - wave[-2]) / 2,
    ]
    lo, hi = center - width * (1 + Z), center + width * (1 + Z)
    weights = np.maximum(0, np.minimum(edges[1:], hi) - np.maximum(edges[:-1], lo))
    # Analytic removal of predefined geocoronal interval; no extrapolation.
    sky_lo, sky_hi = 6564.61 - 4, 6564.61 + 4
    excluded = np.maximum(
        0,
        np.minimum.reduce([edges[1:], np.full(len(wave), hi), np.full(len(wave), sky_hi)])
        - np.maximum.reduce([edges[:-1], np.full(len(wave), lo), np.full(len(wave), sky_lo)]),
    )
    weights -= excluded
    expected = hi - lo - max(0, min(hi, sky_hi) - max(lo, sky_lo))
    allowed = (
        0
        if policy == "strict" or record["data_release"] != "SDSS-DR17"
        else ((1 << 4) | (1 << 16) | (1 << 24))
    )
    good = np.isfinite(flux) & np.isfinite(ivar) & (ivar > 0) & ((bits & ~allowed) == 0)
    selected = good & (weights > 0)
    rest_offsets = (wave - center) / (1 + Z)
    lower, upper = sideband
    side = good & (abs(rest_offsets) >= lower) & (abs(rest_offsets) <= upper)
    side &= ~((wave >= sky_lo) & (wave <= sky_hi))
    fraction = float(weights[selected].sum() / expected)
    result = {
        "covered_unmasked_fraction": fraction,
        "predefined_sky_excluded_fraction": float(excluded.sum() / (hi - lo)),
        "line_pixels": int(selected.sum()),
        "sideband_pixels": int(side.sum()),
        "raw_line_mask_values": np.unique(bits[weights > 0]).tolist(),
        "status": "coverage_or_continuum_failure",
        "flux_1e17": None,
        "conditional_diagonal_error_1e17": None,
    }
    if fraction < 0.9 or selected.sum() < 3 or side.sum() < 8:
        return result
    x = rest_offsets[side]
    design = (
        np.ones((len(x), 1)) if continuum == "constant" else np.column_stack([np.ones(len(x)), x])
    )
    covariance = np.linalg.inv(design.T @ (ivar[side, None] * design))
    coefficients = covariance @ (design.T @ (ivar[side] * flux[side]))
    line_design = (
        np.ones((selected.sum(), 1))
        if continuum == "constant"
        else (np.column_stack([np.ones(selected.sum()), rest_offsets[selected]]))
    )
    line_weights = weights[selected]
    value = float(line_weights @ (flux[selected] - line_design @ coefficients))
    continuum_weights = line_weights @ line_design
    variance = float(
        np.sum(line_weights**2 / ivar[selected])
        + continuum_weights @ covariance @ continuum_weights
    )
    residuals = flux[side] - design @ coefficients
    scale = max(1.0, float(np.sum(residuals**2 * ivar[side]) / (len(x) - len(coefficients))))
    result.update(
        status="conditional_partial_line_measurement",
        flux_1e17=value,
        conditional_diagonal_error_1e17=float(np.sqrt(variance)),
        sideband_residual_chi2_scale=scale,
        residual_scaled_error_1e17=float(np.sqrt(variance * scale)),
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirmation",
        action="store_true",
        help="Explicit new exploratory 5720 diagnostic after original gate failed",
    )
    args = parser.parse_args()
    path = OUT / "research5_spectral/J111855_spectra.json.gz"
    body = gzip.decompress(path.read_bytes())
    data = json.loads(body)
    assert {r["sparcl_id"] for r in data[1:]} == ALLOWED
    for release in ["SDSS-DR17", "DESI-DR1"]:
        assert data[0]["UNITS"][release]["flux"] == "1e-17 erg cm-2 s-1 AA-1"
        assert data[0]["UNITS"][release]["wavelength"] == "AA"
    lines = {
        "FeVII6087": 6088.64,
        "OI": 6302.05,
        "SII6716": 6718.29,
        "SII6731": 6732.67,
        "OIII": 5008.24,
    }
    if args.confirmation:
        lines = {"FeVII5720": 5722.29}
    results = []
    for record in data[1:]:
        measurements = {}
        for line, rest in lines.items():
            for policy in ["strict", "advisory_diagnostic"]:
                for width in [8.0, 12.0, 16.0]:
                    for side in [(20.0, 40.0), (30.0, 60.0)]:
                        for continuum in ["linear", "constant"]:
                            key = f"{line}_{policy}_{width}_{side[0]}_{side[1]}_{continuum}"
                            measurements[key] = measure(
                                record, rest, width, side, policy, continuum
                            )
        results.append(
            {
                "sparcl_id": record["sparcl_id"],
                "survey": record["survey"],
                "dateobs": record["dateobs"],
                "data_release": record["data_release"],
                "measurements": measurements,
            }
        )
    result = {
        "scope": (
            "New explicitly exploratory 5720 diagnostic; original gate failure preserved"
            if args.confirmation
            else "Independent 6087/control audit; 5720 unmeasured"
        ),
        "raw_body_sha256": hashlib.sha256(body).hexdigest(),
        "fixed_z": Z,
        "limits": (
            "Pixel and continuum covariance are diagonal conditional estimates; "
            "persistent SDSS nearbadpixel/manybadcolumns flags remain a caveat; "
            "partial masked line flux is not certified total flux"
        ),
        "targets": results,
    }
    suffix = "5720" if args.confirmation else "6087"
    (OUT / f"research5_review_spectral_{suffix}.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    for record in results:
        line = "FeVII5720" if args.confirmation else "FeVII6087"
        value = record["measurements"][f"{line}_advisory_diagnostic_8.0_20.0_40.0_linear"]
        print(record["survey"], value)


if __name__ == "__main__":
    main()
