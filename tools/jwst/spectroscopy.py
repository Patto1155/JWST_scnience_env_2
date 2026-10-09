"""Read-only diagnostics for a unit-bearing extracted one-dimensional spectrum.

This inspects an extraction, not its astrophysical interpretation. It does not
fit a redshift, emission lines, nitrogen abundance, or a chemical evolution model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from astropy import units as u
from astropy.io import fits


def _column(hdu: fits.BinTableHDU, name: str, target_unit: u.UnitBase) -> np.ndarray:
    if name not in hdu.columns.names:
        raise ValueError(f"Spectrum is missing required {name!r} column")
    unit = hdu.columns[name].unit
    if not unit:
        raise ValueError(f"Spectrum column {name!r} requires an explicit FITS unit")
    try:
        conversion = u.Unit(unit).to(target_unit)
    except (ValueError, TypeError, u.UnitConversionError) as exc:
        raise ValueError(f"Spectrum column {name!r} has incompatible unit {unit!r}") from exc
    values = np.asarray(hdu.data[name], dtype=float)
    if values.ndim != 1:
        raise ValueError(f"Spectrum column {name!r} must be one-dimensional")
    return values * conversion


def summarize_extracted_spectrum(
    path: str | Path,
    *,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Summarize stored SPEC1D flux/error values with provenance and validity.

    The chi-square-like sum is a descriptive diagonal zero-flux statistic;
    correlations, extraction systematics and nuisance continuum are not modelled.
    Per-bin SNR threshold counts are not independent emission-line detections.
    """
    path = Path(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256.lower():
        raise ValueError("Spectrum SHA256 does not match its acquisition receipt")
    with fits.open(path, memmap=False) as hdul:
        if "SPEC1D" not in hdul or not isinstance(hdul["SPEC1D"], fits.BinTableHDU):
            raise ValueError("An extracted SPEC1D FITS binary table is required")
        hdu = hdul["SPEC1D"]
        wave = _column(hdu, "wave", u.um)
        flux = _column(hdu, "flux", u.uJy)
        error = _column(hdu, "err", u.uJy)
        header = hdu.header
        source_position = {}
        for output, name in (("ra_deg", "SRCRA"), ("dec_deg", "SRCDEC")):
            try:
                value = float(header[name])
                source_position[output] = value if np.isfinite(value) else None
            except (KeyError, TypeError, ValueError):
                source_position[output] = None
        metadata = {key: header.get(key) for key in ("GRATING", "FILTER", "PROGRAM")}
        original_units = {name: hdu.columns[name].unit for name in ("wave", "flux", "err")}
        extension_names = [hdu.name for hdu in hdul]
    valid_wave = np.isfinite(wave) & (wave > 0)
    valid_flux = np.isfinite(flux)
    valid_error = np.isfinite(error) & (error > 0)
    valid = valid_wave & valid_flux & valid_error
    if not np.any(valid):
        raise ValueError(
            "Spectrum contains no samples with finite wavelength/flux and positive error"
        )
    with np.errstate(over="ignore", invalid="ignore"):
        snr = flux[valid] / error[valid]
        zero_flux_statistic = float(np.sum(snr**2))
    if not np.all(np.isfinite(snr)) or not np.isfinite(zero_flux_statistic):
        raise ValueError("Spectrum flux/error ratio overflows; input uncertainty is not usable")
    return {
        "schema_version": "spectrum_reference_v1",
        "input_filename": path.name,
        "sha256": digest,
        "hash_verified_against_receipt": expected_sha256 is not None,
        "metadata": metadata,
        "source_position": source_position,
        "source_position_header_keys": ["SRCRA", "SRCDEC"],
        "extension_names": extension_names,
        "original_column_units": original_units,
        "diagnostic_units": {"wavelength": "um", "flux": "uJy", "error": "uJy"},
        "samples": {
            "total": len(wave),
            "valid": int(valid.sum()),
            "excluded": int((~valid).sum()),
            "invalid_wavelength": int((~valid_wave).sum()),
            "nonfinite_flux": int((~valid_flux).sum()),
            "nonfinite_or_nonpositive_error": int((~valid_error).sum()),
            "note": "Invalid-reason counts can overlap; excluded is the union.",
        },
        "wavelength_range_um": [float(wave[valid].min()), float(wave[valid].max())],
        "valid_wavelengths_strictly_increasing": bool(np.all(np.diff(wave[valid]) > 0)),
        "signed_bin_snr": {
            "median": float(np.median(snr)),
            "minimum": float(snr.min()),
            "maximum": float(snr.max()),
            "bins_ge_3": int(np.sum(snr >= 3)),
            "bins_le_minus_3": int(np.sum(snr <= -3)),
        },
        "diagonal_zero_flux_statistic": {
            "sum_squared_signed_bin_snr": zero_flux_statistic,
            "interpretation": "Descriptive only; no p-value or independent detection significance.",
        },
        "limitations": [
            "Uses stored flux/error; no additional path-loss or slit-loss correction is applied.",
            "Bin covariance, extraction systematics and continuum uncertainty are not modelled.",
            "Threshold counts do not identify lines or establish independent detections.",
            "No redshift or chemical-abundance inference is performed.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spectrum", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = summarize_extracted_spectrum(args.spectrum, expected_sha256=args.expected_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
