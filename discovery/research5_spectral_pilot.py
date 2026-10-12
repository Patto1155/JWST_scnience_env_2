"""Frozen direct integration for CLASS J111855; no heldout-line measurement."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

Z = 0.08006536215543747
CENTERS = {
    "FeVII6087": 6088.64,
    "OI6300": 6302.05,
    "SII6716": 6718.29,
    "SII6731": 6732.67,
    "OIII5007": 5008.24,
}


def load_verified(path: Path, receipt: dict) -> list[dict]:
    """Verify retained response-body identity and exact requested spectrum IDs."""
    body = gzip.decompress(path.read_bytes())
    if hashlib.sha256(body).hexdigest() != receipt["sha256"]:
        raise ValueError("Spectrum response body hash mismatch")
    rows = json.loads(body)
    found = [r["sparcl_id"] for r in rows[1:]]
    expected = receipt["request_ids"]
    if len(found) != len(set(found)) or set(found) != set(expected):
        raise ValueError("Spectrum response identities do not match requested IDs")
    return rows


def measure(
    record: dict,
    center: float,
    halfwidth: float,
    sideband: tuple[float, float],
    advisory_sdss: bool = False,
    redshift: float = Z,
) -> dict:
    """Integrate observed wavelength, with pixel and continuum covariance."""
    wave = np.asarray(record["wavelength"], dtype=float)
    flux = np.asarray(record["flux"], dtype=float)
    ivar = np.asarray(record["ivar"], dtype=float)
    mask = np.asarray(record["mask"])
    if wave.ndim != 1 or len(wave) < 2 or any(a.shape != wave.shape for a in (flux, ivar, mask)):
        raise ValueError("Spectrum arrays must be one dimensional with equal lengths >=2")
    if not np.all(np.isfinite(wave)) or not np.all(np.diff(wave) > 0):
        raise ValueError("Wavelengths must be finite and strictly increasing")
    rest = wave / (1 + redshift)
    offset = rest - center
    edges = np.r_[
        wave[0] - (wave[1] - wave[0]) / 2,
        (wave[1:] + wave[:-1]) / 2,
        wave[-1] + (wave[-1] - wave[-2]) / 2,
    ]
    widths = np.diff(edges)
    allowed = (1 << 4) | (1 << 16) | (1 << 24) if advisory_sdss else 0
    usable = np.isfinite(flux) & np.isfinite(ivar) & (ivar > 0) & ((mask & ~allowed) == 0)
    sky = np.abs(wave - 6564.61) <= 4.0
    geometric = np.abs(offset) <= halfwidth
    permitted = geometric & ~sky
    selected = permitted & usable
    expected = widths[permitted].sum()
    covered = widths[selected].sum()
    coverage = covered / expected if expected else 0.0
    left = (offset >= -sideband[1]) & (offset <= -sideband[0]) & usable & ~sky
    right = (offset >= sideband[0]) & (offset <= sideband[1]) & usable & ~sky
    output = {
        "center_vacuum_A": center,
        "halfwidth_rest_A": halfwidth,
        "sidebands_rest_A": sideband,
        "coverage_after_fixed_sky_exclusion": coverage,
        "sky_excluded_fraction": (
            widths[geometric & sky].sum() / widths[geometric].sum() if geometric.any() else 0.0
        ),
        "n_line_pixels": int(selected.sum()),
        "n_sideband_pixels": [int(left.sum()), int(right.sum())],
    }
    if edges[0] > (center - halfwidth) * (1 + redshift) or edges[-1] < (center + halfwidth) * (
        1 + redshift
    ):
        return output | {
            "status": "unavailable_coverage",
            "reason": "requested line window truncated",
        }
    if coverage < 0.9 or left.sum() < 5 or right.sum() < 5:
        return output | {"status": "unavailable_coverage"}
    side = left | right
    design = np.c_[np.ones(side.sum()), offset[side]]
    normal = design.T @ (ivar[side, None] * design)
    covariance = np.linalg.inv(normal)
    beta = covariance @ (design.T @ (ivar[side] * flux[side]))
    residual = flux[side] - design @ beta
    reduced_chi2 = float(np.sum(ivar[side] * residual**2) / (side.sum() - 2))
    inflation = max(1.0, reduced_chi2)
    projection = np.c_[np.ones(selected.sum()), offset[selected]]
    weights = widths[selected]
    value = float(weights @ (flux[selected] - projection @ beta))
    vector = weights @ projection
    variance = float(
        (np.sum(weights**2 / ivar[selected]) + vector @ covariance @ vector) * inflation
    )
    error = float(np.sqrt(variance))
    return output | {
        "status": "measured",
        "flux_1e17_erg_cm2_s": value,
        "error_1e17_erg_cm2_s": error,
        "snr": value / error,
        "upper_bound_3sigma": max(0.0, value) + 3 * error,
        "sideband_reduced_chi2": reduced_chi2,
        "variance_inflation": inflation,
        "continuum_coefficients": beta.tolist(),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    folder = root / "research_output" / "research5_spectral"
    receipt = json.loads((folder / "J111855_spectra_receipt.json").read_text())
    raw = load_verified(folder / "J111855_spectra.json.gz", receipt)
    results = []
    for record in raw[1:]:
        variants = []
        for width in (8.0, 12.0, 16.0):
            for sideband in ((20.0, 40.0), (30.0, 60.0)):
                variants.append(
                    {
                        "halfwidth": width,
                        "sideband": sideband,
                        "measurements": {
                            name: measure(record, center, width, sideband)
                            for name, center in CENTERS.items()
                        },
                    }
                )
        results.append(
            {
                "sparcl_id": record["sparcl_id"],
                "survey": record["survey"],
                "dateobs": record["dateobs"],
                "variants": variants,
            }
        )
    output = {
        "classification": "exploratory frozen single-object discovery-line pilot",
        "heldout_FeVII5720": "not measured",
        "redshift": Z,
        "uncertainty": (
            "pixel IVAR plus sideband fit, inflated by sideband chi2; "
            "residual covariance not fully calibrated"
        ),
        "records": results,
    }
    (folder / "J111855_discovery_measurements.json").write_text(
        json.dumps(output, indent=2, allow_nan=False)
    )
    for row in results:
        print(row["survey"], row["sparcl_id"])
        for name, result in row["variants"][0]["measurements"].items():
            print(
                name,
                result.get("flux_1e17_erg_cm2_s"),
                result.get("error_1e17_erg_cm2_s"),
                result.get("snr"),
                result["coverage_after_fixed_sky_exclusion"],
                result["sky_excluded_fraction"],
            )


if __name__ == "__main__":
    main()
