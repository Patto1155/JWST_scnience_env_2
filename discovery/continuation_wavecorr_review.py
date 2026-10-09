"""Independent ASDF, wavelength mapping and normal-equation likelihood audit.

Optional ASDF/GWCS packages are used only when decoding the actual reference
or original CAL metadata. They are not needed for the algebra helpers below.
The pinned DUMMY reference remains a sensitivity assumption, not calibration.
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import numpy as np
from scipy.linalg import block_diag
from scipy.special import ndtr

from discovery.continuation_followup_review import LINE_ORDER
from discovery.continuation_review import digest
from tools.jwst.line_sensitivity import LINE_COMPONENTS, read_resolution
from tools.jwst.point_resolution import read_point_resolution

SCENARIOS = (
    "nominal_formal_shared",
    "point_formal_shared",
    "nominal_empirical_spectral_transport",
    "point_empirical_spectral_transport",
    "point_spatial_spectral_transport",
    "nominal_spatial_spectral_transport",
)


def linear_extrapolation(x, points, values):
    """Piecewise linear interpolation with explicit endpoint slope continuation."""
    x, points, values = map(np.asarray, (x, points, values))
    if (
        points.ndim != 1
        or len(points) < 3
        or values.shape != points.shape
        or not np.isfinite(points).all()
        or not np.isfinite(values).all()
        or np.any(np.diff(points) <= 0)
        or np.any(np.diff(values) <= 0)
    ):
        raise ValueError("finite ordered invertible piecewise mapping required")
    mapped = np.interp(x, points, values)
    for mask, endpoint, neighbor in [(x < points[0], 0, 1), (x > points[-1], -1, -2)]:
        slope = (values[endpoint] - values[neighbor]) / (points[endpoint] - points[neighbor])
        mapped = np.where(mask, values[endpoint] + slope * (x - points[endpoint]), mapped)
    return mapped


def source_waves(wave, good, trace, sigma):
    rows = np.arange(wave.shape[1])[None, :, None]
    p = ndtr((rows + 0.5 - trace[:, None, :]) / sigma) - ndtr(
        (rows - 0.5 - trace[:, None, :]) / sigma
    )
    denominator = (p * good).sum(axis=1)
    numerator = (np.where(good, wave, 0) * p).sum(axis=1)
    waves = np.divide(
        numerator, denominator, out=np.full_like(denominator, np.nan), where=denominator > 0
    )
    for w in waves:
        valid = np.flatnonzero(np.isfinite(w))
        if len(valid) < 3:
            raise ValueError("source wavelength coverage is insufficient")
        w[:] = linear_extrapolation(np.arange(len(w)), valid, w[valid])
    return waves


def bin_design(waves, selected, resolution_wave, resolution, components=LINE_COMPONENTS):
    designs = []
    for w in waves:
        edges = np.r_[w[0] - (w[1] - w[0]) / 2, (w[:-1] + w[1:]) / 2, w[-1] + (w[-1] - w[-2]) / 2]
        width = np.diff(edges)
        lines = []
        for wavelengths, weights in components:
            weights = np.asarray(weights) / np.sum(weights)
            model = np.zeros(len(w))
            for rest, weight in zip(wavelengths, weights, strict=True):
                center = rest * 0.0001 * 15.44
                r = np.interp(center, resolution_wave, resolution)
                sigma = center / r / (2 * np.sqrt(2 * np.log(2)))
                model += weight * np.diff(ndtr((edges - center) / sigma)) / width
            lines.append(model / (299792.458 / w**2))
        designs.append(
            np.column_stack((np.ones(len(w)) / 100, (w - 2.675) / 0.525 / 100, np.array(lines).T))[
                selected
            ]
        )
    return np.transpose(designs, (1, 0, 2)).reshape(-1, 7)


def normal_fit(design, precision, values, saved):
    expected = np.asarray(saved["fluxes"])
    expected_covariance = np.asarray(saved["flux_covariance"])
    if (
        saved["flux_units"] != "1e-20 erg s^-1 cm^-2"
        or tuple(saved["line_order"]) != LINE_ORDER
        or expected.shape != (5,)
        or expected_covariance.shape != (5, 5)
        or not np.isfinite(expected).all()
        or not np.isfinite(expected_covariance).all()
        or not np.allclose(expected_covariance, expected_covariance.T)
        or np.linalg.eigvalsh(expected_covariance).min() <= 0
    ):
        raise ValueError("finite aligned five-group signed likelihood required")
    covariance = np.linalg.inv(design.T @ precision @ design)
    coefficient = covariance @ (design.T @ precision @ values)
    flux_error = float(np.max(abs(coefficient[2:] - expected)))
    covariance_error = float(
        np.max(abs(covariance[2:, 2:] - expected_covariance)) / np.max(abs(expected_covariance))
    )
    residual = values - design @ coefficient
    chi2_error = float(abs(residual @ precision @ residual - saved["conditional_chi2"]))
    if not (flux_error < 1e-9 and covariance_error < 1e-9 and chi2_error < 1e-8):
        raise ValueError("independent normal-equation likelihood differs")
    return flux_error, covariance_error, chi2_error


def audit(root: Path, native_dir: Path | None = None):
    import asdf

    path = root / "research_output/mom_native_wavecorr.json"
    report = json.loads(path.read_text())
    compact = path.parent / report["compact_replay"]["filename"]
    if digest(compact) != report["compact_replay"]["sha256"]:
        raise ValueError("frozen likelihood receipt changed")
    with np.load(compact, allow_pickle=False) as z:
        arrays = {key: z[key].copy() for key in z.files}
    if arrays["native_wave"].shape != (9, 28, 423):
        raise ValueError("nine native target geometries required")
    reference_path = root / "data_sources/followup/jwst_nirspec_wavecorr_0004.asdf"
    if digest(reference_path) != report["reference"]["sha256"]:
        raise ValueError("actual reference receipt changed")
    with asdf.open(reference_path, lazy_load=False) as reference:
        aperture = reference["apertures"][0]
        model = aperture["zero_point_offset"]
        if (
            reference["meta"]["pedigree"] != "DUMMY"
            or reference["meta"]["filename"] != "jwst_nirspec_wavecorr_0002.asdf"
            or not np.allclose(model.points[0], np.linspace(6e-7, 5.3e-6, 21), rtol=0, atol=1e-20)
            or not np.allclose(model.points[1], np.linspace(-0.5, 0.5, 21), rtol=0, atol=1e-15)
            or model.lookup_table.shape != (21, 21)
            or not np.isfinite(model.lookup_table).all()
            or not np.all(aperture["variance"] == 0.1**2)
        ):
            raise ValueError("actual ASDF reference table, axes or pedigree differ")
        model.bounds_error = False
        model.fill_value = None
        mapping_errors = []
        for wave, dispersion, position, corrected in zip(
            arrays["native_wave"],
            arrays["dispersion_m"],
            arrays["source_xpos"],
            arrays["corrected_wave"],
            strict=True,
        ):
            original = np.nanmean(wave, axis=0) * 1e-6
            derivative = np.nanmean(dispersion, axis=0)
            valid = np.isfinite(original) & np.isfinite(derivative)
            shifted = original[valid] + model(original[valid], position) * derivative[valid]
            independent = linear_extrapolation(wave * 1e-6, original[valid], shifted) * 1e6
            error = float(np.nanmax(abs(independent - corrected)))
            if error > 1e-13 or not np.array_equal(
                np.isfinite(independent), np.isfinite(corrected)
            ):
                raise ValueError("independent column mapping differs")
            mapping_errors.append(error)
    raw_checks = []
    if native_dir is not None:
        from astropy.io import fits

        for index, prediction in enumerate(report["predictions"]):
            with fits.open(native_dir / prediction["filename"], memmap=False) as hdul:
                target = next(
                    h for h in hdul if h.name == "SCI" and h.header.get("SRCNAME") == "5224_277193"
                )
                if target.header["WAVECOR"] is not False or target.header["SRCTYPE"] != "EXTENDED":
                    raise ValueError("original target classification/correction contract changed")
                metadata = hdul["ASDF"].data["ASDF_METADATA"][0].tobytes()
            with asdf.open(io.BytesIO(metadata), lazy_load=True, lazy_tree=True) as tree:
                targets = [s for s in tree["slits"] if s.get("source_name") == "5224_277193"]
                if len(targets) != 1:
                    raise ValueError("raw ASDF target identity is ambiguous")
                wcs = targets[0]["meta"]["wcs"]
                if "wavecorr_frame" in wcs.available_frames:
                    raise ValueError("wavecorr already exists in original WCS")
                y: np.ndarray
                x: np.ndarray
                y, x = np.indices((28, 423), dtype=float)
                wave = np.asarray(wcs(x, y)[2])
                derivative = (np.asarray(wcs(x + 0.5, y)[2]) - wcs(x - 0.5, y)[2]) * 1e-6
                frozen = arrays["native_wave"][index]
                derivative_error = float(np.nanmax(abs(derivative - arrays["dispersion_m"][index])))
                wave_error = float(np.nanmax(abs(wave - frozen)))
                if (
                    derivative_error > 1e-20
                    or wave_error > 3e-7
                    or not np.array_equal(np.isfinite(wave), np.isfinite(frozen))
                ):
                    raise ValueError("independent original GWCS audit differs")
                raw_checks.append(
                    {
                        "filename": prediction["filename"],
                        "wave_error_um": wave_error,
                        "dispersion_error_m_per_pixel": derivative_error,
                    }
                )
    inverses = []
    for index in range(6):
        blocks = arrays["spatial_covariance_blocks" if index >= 4 else "covariance_blocks"]
        factor = block_diag(*[np.linalg.cholesky(block) for block in blocks])
        kernel = np.eye(70) if index < 2 else arrays["spectral_kernel"]
        scale = 1 if index < 2 else arrays["noise_scale_squared"][0]
        inverses.append(np.linalg.inv(factor @ np.kron(kernel, np.eye(9)) @ factor.T * scale))
    values = arrays["flux"].T.ravel()
    checks = []
    for grid, key in [
        ("native_wave", "original_wavelength_scenarios"),
        ("corrected_wave", "predicted_corrected_wavelength_scenarios"),
    ]:
        if tuple(s["name"] for s in report[key]) != SCENARIOS:
            raise ValueError("exactly six wavelength/covariance scenarios required")
        waves = source_waves(
            arrays[grid], arrays["native_good"], arrays["trace"], arrays["sigma"][0]
        )
        for index, scenario in enumerate(report[key]):
            point = index in (1, 3, 4)
            rw, rr, _ = (
                read_point_resolution(
                    root / "data_sources/followup/unite_point_prism_resolution.csv"
                )
                if point
                else read_resolution(root / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
            )
            design = bin_design(waves, arrays["selected_columns"], rw, rr)
            errors = normal_fit(design, inverses[index], values, scenario["fit"])
            checks.append(
                {
                    "hypothesis": grid,
                    "scenario": scenario["name"],
                    "flux_error": errors[0],
                    "covariance_error_over_scale": errors[1],
                    "chi2_error": errors[2],
                }
            )
    return {
        "schema_version": 1,
        "wavecorr_report_sha256": digest(path),
        "compact_sha256": digest(compact),
        "actual_asdf_reference_sha256": digest(reference_path),
        "actual_asdf_table_and_axes_audited": True,
        "independent_mapping_max_difference_um": max(mapping_errors),
        "independent_original_GWCS": raw_checks,
        "independent_twelve_full_grid_GLS": checks,
        "scope": (
            "DUMMY reference/planned placement sensitivity; EXTENDED classification is a "
            "hypothesis change; no measured source LSF or wavelength calibration"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--native-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(audit(args.root, args.native_dir), indent=2, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    main()
