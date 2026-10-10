"""Validate rectified source coverage without extracting or fitting flux."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from astropy.io import fits

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "data_sources/capers_s2d"


def support_counts(wave, science, error, weight, context, dq=None):
    uv = np.isfinite(wave) & (wave >= 2.15) & (wave <= 3.2)
    finite = np.isfinite(wave) & np.isfinite(science) & np.isfinite(error)
    supported = finite & (error > 0) & np.isfinite(weight) & (weight > 0)
    supported &= np.any(context != 0, axis=0)
    flagged = None if dq is None else supported & ((dq & 3) == 0)
    return {
        "pixels": wave.size,
        "finite_wavelength_pixels": int(np.isfinite(wave).sum()),
        "uv_wavelength_pixels_before_quality_cuts": int(uv.sum()),
        "finite_science_error_wavelength_pixels": int(finite.sum()),
        "positive_error_weight_context_supported_pixels": int(supported.sum()),
        "uv_supported_pixels_before_dq": int((uv & supported).sum()),
        "dq_array_present": dq is not None,
        "uv_supported_pixels_after_supplied_dq": (
            None if flagged is None else int((uv & flagged).sum())
        ),
    }


def replay():
    start = perf_counter()
    receipt = json.loads((DIRECTORY / "receipt.json").read_text())
    path = DIRECTORY / "source_s2d.fits"
    raw = path.read_bytes()
    if len(raw) != receipt["bytes"] or hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
        raise ValueError("Source S2D differs from whole-file pin")
    if (
        receipt["endpoint_count"] != 1
        or len(raw) > 2097152
        or receipt["acquisition_runtime_s"] > 60
    ):
        raise ValueError("S2D pilot acquisition budget exceeded")
    companion = json.loads((ROOT / "research_output/capers_companion_coverage_v1.json").read_text())
    with fits.open(path, memmap=False) as hdul:
        primary, header = hdul[0].header, hdul["SCI"].header
        if (
            header["SOURCEID"] != 102896
            or header["SRCRA"] != 150.0933178
            or header["SRCDEC"] != 2.2731591
            or header["SLITID"] != 139
        ):
            raise ValueError("Rectified source identity differs")
        for key in ("ASNTABLE", "CAL_VER", "CRDS_CTX", "R_WAVCOR"):
            if primary[key] != companion["provenance"][key]:
                raise ValueError("Rectified and extracted source provenance differs")
        files = sorted(str(value) for value in hdul["HDRTAB"].data["FILENAME"])
        if files != sorted(companion["association_science_members"]):
            raise ValueError("Rectified actual contributor inventory differs")
        detectors = hdul["HDRTAB"].data["DETECTOR"]
        wave, science, error, weight = [
            hdul[name].data.copy() for name in ("WAVELENGTH", "SCI", "ERR", "WHT")
        ]
        context = hdul["CON"].data.copy()
        if wave.shape != (31, 277) or any(a.shape != wave.shape for a in (science, error, weight)):
            raise ValueError("Rectified coverage array shape differs")
        if context.shape != (2, 31, 277):
            raise ValueError("Rectified contributor context dimensions differ")
        asdf_column = hdul["ASDF"].data.dtype.names[0]
        text = hdul["ASDF"].data[asdf_column][0].tobytes().split(b"\n...\n", 1)[0].decode("utf8")
        spectral_frame = text.split("spectral_frame", 1)[1].split("name: slit_frame", 1)[0]
        if "axes_names: [wavelength]" not in spectral_frame:
            raise ValueError("Embedded spectral coordinate is ambiguous")
        if "unit: [!unit/unit-1.0.0 um]" not in spectral_frame:
            raise ValueError("Embedded spectral coordinate units differ")
        if "source: fits:WAVELENGTH,1" not in text:
            raise ValueError("Embedded wavelength-array mapping differs")
        if header["BUNIT"] != "MJy" or hdul["ERR"].header["BUNIT"] != "MJy":
            raise ValueError("Source SCI/ERR units differ")
        dq = hdul["DQ"].data.copy() if "DQ" in hdul else None
        identities = {key: header[key] for key in ("SOURCEID", "SRCRA", "SRCDEC", "SRCTYPE")}
        provenance = {
            key: primary[key]
            for key in (
                "CAL_VER",
                "CRDS_CTX",
                "ASNTABLE",
                "DETECTOR",
                "S_WAVCOR",
                "R_WAVCOR",
            )
        }
    x1d = ROOT / "data_sources/capers_companion/source_x1d.fits"
    x1d_receipt = json.loads((x1d.parent / "receipt.json").read_text())
    x1d_pin = next(q for q in x1d_receipt["queries"] if q["id"] == "source_x1d")
    if hashlib.sha256(x1d.read_bytes()).hexdigest() != x1d_pin["sha256"]:
        raise ValueError("Unit-tagged source X1D differs")
    with fits.open(x1d) as hdul:
        expected_wave = hdul["EXTRACT1D"].data["WAVELENGTH"]
        assert hdul["EXTRACT1D"].columns["WAVELENGTH"].unit == "um"
        if not np.allclose(wave, expected_wave[None, :], atol=1e-6, rtol=0):
            raise ValueError("Rectified wavelength grid disagrees with unit-tagged source X1D")
    result = support_counts(wave, science, error, weight, context, dq)
    runtime = perf_counter() - start
    if runtime > 60:
        raise ValueError("Coverage analysis budget exceeded")
    return {
        "schema_version": 1,
        "plan_revision": "c6b864b",
        "input_receipt": receipt,
        "source": identities,
        "provenance": provenance,
        "shape": list(wave.shape),
        "SCI_ERR_units": "MJy",
        "wavelength_units_embedded_spectral_frame": "um",
        "explicit_wavelength_hdu_BUNIT": None,
        "source_X1D_grid_crosscheck_passed": True,
        "actual_HDRTAB_contributor_count": len(files),
        "actual_contributor_filenames": files,
        "actual_nrs1_contributors": int((detectors == "NRS1").sum()),
        "actual_nrs2_contributors": int((detectors == "NRS2").sum()),
        "coverage": result,
        "analysis_runtime_s": runtime,
        "stopping_decision": (
            "Zero UV coordinates in rectified source S2D; stop intermediate UV fits"
        ),
        "rejected_explanation": "The UV gap exists solely in the official X1D extraction mask",
        "limits": [
            "No DQ array supplied: flag validation is unavailable, never replaced with zero flags",
            "Zero UV coordinate pixels means any further flag cut also has zero UV support",
            (
                "Drizzled pixels and contributor context do not supply independent "
                "exposure likelihoods"
            ),
            "Context is a signed bitmask: nonzero, not positive values, indicate contributors",
            "Zero UV coverage is not zero source flux or an upper limit",
            "Pipeline calibrated/resampled source support is not lower-stage detector reproduction",
            "Raw trace geometry and wavelength assignment still permit a separate archive pilot",
            "No new abundance, redshift, source identity or empirical LSF established",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
