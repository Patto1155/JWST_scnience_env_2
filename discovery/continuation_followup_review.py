"""Independent full-native GLS and blue-counterpart background oracles.

The spectral templates remain the stated baseline assumptions. This validates
units and numerical likelihood algebra, not a source-specific LSF or gas model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
from scipy.linalg import block_diag
from scipy.special import ndtr

from discovery.continuation_review import digest
from tools.jwst.line_sensitivity import line_matrix, read_resolution
from tools.jwst.point_resolution import read_point_resolution

ROOT = Path(__file__).resolve().parents[1]
NATIVE_SCENARIOS = (
    "nominal_shared_formal",
    "point_shared_formal",
    "nominal_empirical_offtrace_transport",
    "point_empirical_offtrace_transport",
)
LINE_ORDER = ("NIV", "CIV", "HeII_OIII", "NIII", "CIII")


def compare_native_model(flux: np.ndarray, covariance: np.ndarray, stored: dict) -> dict:
    """Fail closed for zero entries, nonfinite values, units or likelihood order."""
    expected_flux = np.asarray(stored["fluxes"], dtype=float)
    expected_covariance = np.asarray(stored["flux_covariance"], dtype=float)
    if (
        stored.get("flux_units") != "1e-20 erg s^-1 cm^-2"
        or tuple(stored.get("line_order", ())) != LINE_ORDER
    ):
        raise ValueError("native stored likelihood units/order differ")
    for vector, matrix in ((flux, covariance), (expected_flux, expected_covariance)):
        if (
            vector.shape != (5,)
            or matrix.shape != (5, 5)
            or not np.isfinite(vector).all()
            or not np.isfinite(matrix).all()
        ):
            raise ValueError("native likelihood must have finite aligned five-group arrays")
        if (
            not np.allclose(matrix, matrix.T, rtol=1e-10, atol=1e-12)
            or np.linalg.eigvalsh(matrix).min() <= 0
        ):
            raise ValueError("native likelihood covariance must be symmetric positive definite")
    scale = float(np.max(np.abs(expected_covariance)))
    flux_difference = float(np.max(np.abs(flux - expected_flux)))
    covariance_difference = float(np.max(np.abs(covariance - expected_covariance)) / scale)
    if not np.allclose(flux, expected_flux, rtol=1e-10, atol=1e-10) or not np.allclose(
        covariance, expected_covariance, rtol=1e-9, atol=1e-11 * scale
    ):
        raise ValueError("independent native GLS disagrees with saved signed likelihood")
    return {
        "max_flux_absolute_error": flux_difference,
        "max_covariance_absolute_error_over_largest_saved_entry": covariance_difference,
    }


def check_native_arrays(npz, report: dict) -> None:
    """Reject empty/changed scenario and derived-array contracts before fitting."""
    if tuple(s.get("name") for s in report.get("scenarios", ())) != NATIVE_SCENARIOS:
        raise ValueError("exactly four ordered native scenarios required")
    if len(npz.files) != len(set(npz.files)):
        raise ValueError("duplicate native replay array names")
    wave, good, trace, sigma = (npz[k] for k in ("native_wave", "native_good", "trace", "sigma"))
    selected, blocks, flux, kernel, scale = (
        npz[k]
        for k in (
            "selected_columns",
            "covariance_blocks",
            "flux",
            "spectral_kernel",
            "noise_scale_squared",
        )
    )
    if (
        wave.ndim != 3
        or wave.shape[0] != 9
        or good.shape != wave.shape
        or good.dtype != bool
        or trace.shape != (9, wave.shape[2])
    ):
        raise ValueError("native wavelength/mask/trace shapes differ")
    if (
        sigma.shape != (1,)
        or scale.shape != (1,)
        or not np.isfinite(sigma).all()
        or not np.isfinite(scale).all()
        or min(sigma[0], scale[0]) <= 0
    ):
        raise ValueError("positive finite native width/noise scales required")
    if (
        selected.ndim != 1
        or not np.issubdtype(selected.dtype, np.integer)
        or len(selected) < 20
        or np.any(np.diff(selected) <= 0)
        or selected.min() < 0
        or selected.max() >= wave.shape[2]
    ):
        raise ValueError("ordered covered native columns required")
    if (
        flux.shape != (9, len(selected))
        or blocks.shape != (len(selected), 9, 9)
        or kernel.shape != (len(selected), len(selected))
    ):
        raise ValueError("native flux/covariance/kernel shapes differ")
    if (
        not np.isfinite(trace).all()
        or not np.isfinite(wave[good]).all()
        or any(not np.isfinite(x).all() for x in (flux, blocks, kernel))
    ):
        raise ValueError("native replay contains nonfinite source arrays")
    if (
        not np.allclose(blocks, blocks.transpose(0, 2, 1))
        or np.linalg.eigvalsh(blocks).min() <= 0
        or not np.allclose(kernel, kernel.T)
        or np.linalg.eigvalsh(kernel).min() <= 0
    ):
        raise ValueError("native covariance/kernel must be symmetric positive definite")


def native_gls_audit(npz_path: Path, report_path: Path) -> list:
    """Build L (K tensor I) L.T independently and solve GLS normal equations."""
    npz = np.load(npz_path, allow_pickle=False)
    report = json.loads(report_path.read_text())
    if digest(npz_path) != report["compact_native_replay"]["sha256"]:
        raise ValueError("derived native amplitudes disagree with report receipt")
    check_native_arrays(npz, report)
    wave, good, trace, sigma = (npz[k] for k in ("native_wave", "native_good", "trace", "sigma"))
    yy = np.arange(wave.shape[1])[None, :, None]
    profile = ndtr((yy + 0.5 - trace[:, None, :]) / sigma[0]) - ndtr(
        (yy - 0.5 - trace[:, None, :]) / sigma[0]
    )
    den = (profile * good).sum(axis=1)
    numerator = (np.where(good, wave, 0) * profile).sum(axis=1)
    waves = np.divide(numerator, den, out=np.full_like(den, np.nan), where=den > 0)
    for row in waves:
        valid = np.flatnonzero(np.isfinite(row))
        if len(valid) < 2:
            raise ValueError("native source wavelength lacks finite interpolation anchors")
        row[:] = np.interp(np.arange(len(row)), valid, row[valid])
        left, right = valid[0], valid[-1]
        row[:left] = row[left] + (np.arange(left) - left) * (row[left + 1] - row[left])
        row[right + 1 :] = row[right] + (np.arange(right + 1, len(row)) - right) * (
            row[right] - row[right - 1]
        )
    selected, blocks = npz["selected_columns"], npz["covariance_blocks"]
    factor = block_diag(*[np.linalg.cholesky(x) for x in blocks])
    values = npz["flux"].T.ravel()
    output = []
    for index, scenario in enumerate(report["scenarios"]):
        if index % 2:
            rw, rr, _ = read_point_resolution(
                ROOT / "data_sources/followup/unite_point_prism_resolution.csv"
            )
        else:
            rw, rr, _ = read_resolution(ROOT / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
        design = []
        for wavelength in waves:
            continuum = np.polynomial.legendre.legvander((wavelength - 2.675) / 0.525, 1) / 100
            lines = line_matrix(wavelength, rw, rr) / (2.99792458e5 / wavelength**2)[:, None]
            design.append(np.column_stack((continuum, lines))[selected])
        matrix = np.transpose(design, (1, 0, 2)).reshape(-1, 7)
        kernel = npz["spectral_kernel"] if index >= 2 else np.eye(len(selected))
        scale = npz["noise_scale_squared"][0] if index >= 2 else 1
        covariance = factor @ np.kron(kernel, np.eye(9)) @ factor.T * scale
        solved = np.linalg.solve(covariance, np.column_stack((matrix, values)))
        inverse = np.linalg.inv(matrix.T @ solved[:, :7])
        coefficient = inverse @ (matrix.T @ solved[:, -1])
        output.append(
            {
                "scenario": scenario["name"],
                **compare_native_model(coefficient[2:], inverse[2:, 2:], scenario["fit"]),
            }
        )
    return output


def blue_background_audit(directory: Path, inventory_path: Path) -> dict:
    """Actual254F090 pixels, four fixed annuli, independent mean and planar sky."""
    inventory = json.loads(inventory_path.read_text())
    pin = next(
        p for p in inventory["products"] if p.get("source_id") == 254 and p.get("filter") == "F090W"
    )
    path = directory / pin["filename"]
    if digest(path) != pin["sha256"]:
        raise ValueError("blue counterpart pixels differ from versioned inventory")
    with fits.open(path) as hdul:
        header = hdul[0].header
        if header["BUNIT"] != "10.0*nanoJansky":
            raise ValueError("independent blue oracle requires recorded ten-nJy units")
        science, weights, wcs = hdul[0].data * 10, hdul[1].data / 100, WCS(header).celestial
    center = SkyCoord(pin["ra_deg"], pin["dec_deg"], unit="deg")
    cx, cy = wcs.world_to_pixel(center)
    xx, yy = np.meshgrid(
        np.arange(int(cx) - 25, int(cx) + 26), np.arange(int(cy) - 25, int(cy) + 26)
    )
    sky = wcs.pixel_to_world(xx, yy)
    separation = sky.separation(center).arcsec
    east, north = center.spherical_offsets_to(sky)
    design = np.stack((np.ones(xx.shape), east.arcsec, north.arcsec), axis=-1)
    values, weight = science[yy, xx], weights[yy, xx]
    good = np.isfinite(values + weight) & (weight > 0)
    aperture = (separation <= 0.2) & good
    output = []
    for inner, outer in ((0.4, 0.6), (0.4, 0.8), (0.6, 0.8), (0.8, 1.0)):
        annulus = (separation >= inner) & (separation <= outer) & good
        mean = values[annulus].mean()
        mean_flux = values[aperture].sum() - aperture.sum() * mean
        mean_variance = (1 / weight[aperture]).sum() + aperture.sum() ** 2 * (
            1 / weight[annulus]
        ).sum() / annulus.sum() ** 2
        matrix = design[annulus]
        covariance = np.linalg.inv(matrix.T @ (weight[annulus, None] * matrix))
        coefficient = covariance @ (matrix.T @ (weight[annulus] * values[annulus]))
        operator = design[aperture].sum(axis=0)
        plane_flux = values[aperture].sum() - operator @ coefficient
        plane_variance = (1 / weight[aperture]).sum() + operator @ covariance @ operator
        output.append(
            {
                "annulus_arcsec": [inner, outer],
                "aperture_radius_arcsec": 0.2,
                "mean_sky_flux_njy": float(mean_flux),
                "mean_diagonal_error_njy": float(np.sqrt(mean_variance)),
                "plane_sky_flux_njy": float(plane_flux),
                "plane_diagonal_error_njy": float(np.sqrt(plane_variance)),
                "annulus_pixels": int(annulus.sum()),
            }
        )
    return {
        "sha256": pin["sha256"],
        "source_id": 254,
        "band": "F090W",
        "experiments": output,
        "limitations": "Same photons, fixed aperture, unmasked annuli, conditional diagonal errors; no deblend or redshift.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-report", type=Path, required=True)
    parser.add_argument("--native-npz", type=Path, required=True)
    parser.add_argument("--deep-inventory", type=Path, required=True)
    parser.add_argument("--deep-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {
        "schema_version": 2,
        "inputs_sha256": {
            k: digest(v)
            for k, v in vars(args).items()
            if k in ("native_report", "native_npz", "deep_inventory")
        },
        "native_gls_independent_oracle": native_gls_audit(args.native_npz, args.native_report),
        "source254_blue_background_oracle": blue_background_audit(
            args.deep_directory, args.deep_inventory
        ),
    }
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
