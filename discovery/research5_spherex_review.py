"""Independent QR3 native-pixel ePSF photometry; no acquisition or W1 extrapolation."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
from scipy.interpolate import RectBivariateSpline
from scipy.optimize import minimize


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_zone(table: np.ndarray, x: float, y: float) -> int:
    """Select on parent detector coordinates, never on cutout coordinates."""
    return int(np.argmin((table["XCENTER"] - x) ** 2 + (table["YCENTER"] - y) ** 2))


def benign_flag_mask(header: fits.Header) -> int:
    """Support actual QR3 MSKN/MSKM metadata as well as old MP bit indices."""
    benign = 0
    names = {"SOURCE", "FULLSAMPLE"}
    for key in header:
        if key.startswith("MSKN") and str(header[key]).strip() in names:
            benign |= int(header["MSKM" + key[4:]])
    for name in names:
        if "MP_" + name in header:
            benign |= 1 << int(header["MP_" + name])
    return benign


def native_psf(
    epsf: np.ndarray,
    shape: tuple[int, int],
    x0: float,
    y0: float,
    oversampling: tuple[int, int] = (5, 5),
) -> tuple[np.ndarray, float]:
    """Sample pixel-convolved ePSF at native centers; do not convolve it again.

    Normalize on a complete support stamp, not only retained/masked pixels.
    The returned raw sum exposes phase-dependent normalization sensitivity.
    """
    epsf = np.asarray(epsf, dtype=float)
    ny, nx = epsf.shape
    sy, sx = oversampling
    spline = RectBivariateSpline(np.arange(nx), np.arange(ny), epsf.T)

    def sample(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        xx = sx * (x - x0) + (nx - 1) / 2
        yy = sy * (y - y0) + (ny - 1) / 2
        values = spline(xx, yy, grid=False)
        return np.where((xx >= 0) & (xx <= nx - 1) & (yy >= 0) & (yy <= ny - 1), values, 0.0)

    half = int(np.ceil(max(nx / sx, ny / sy))) + 1
    yy, xx = np.mgrid[-half : half + 1, -half : half + 1]
    total = float(sample(xx + np.floor(x0), yy + np.floor(y0)).sum())
    if total <= 0 or not np.isfinite(total):
        raise ValueError("nonpositive/nonfinite native PSF normalization")
    yy, xx = np.indices(shape)
    return sample(xx, yy) / total, total


def linear_photometry(
    image: np.ndarray,
    variance: np.ndarray,
    psf: np.ndarray,
    good: np.ndarray,
    x0: float,
    y0: float,
    radius: float = 6,
    plane: bool = False,
) -> dict:
    """Weighted fit with background nuisance terms and full covariance."""
    yy, xx = np.indices(image.shape)
    columns = [psf, np.ones(image.shape)]
    if plane:
        columns.extend([xx - x0, yy - y0])
    mask = (
        good
        & np.isfinite(image)
        & np.isfinite(variance)
        & (variance > 0)
        & (np.hypot(xx - x0, yy - y0) <= radius)
    )
    design = np.column_stack([c[mask] for c in columns])
    weights = np.sqrt(variance[mask])
    if len(weights) <= len(columns):
        raise ValueError("insufficient usable pixels")
    weighted = design / weights[:, None]
    coefficients, _, rank, _ = np.linalg.lstsq(weighted, image[mask] / weights, rcond=None)
    if rank != len(columns):
        raise ValueError("singular photometry design")
    covariance = np.linalg.inv(weighted.T @ weighted)
    residual = (image[mask] - design @ coefficients) / weights
    dof = len(weights) - len(columns)
    reduced_chi2 = float(residual @ residual / dof)
    return {
        "amplitude": float(coefficients[0]),
        "formal_error": float(np.sqrt(covariance[0, 0])),
        "residual_scaled_error": float(np.sqrt(covariance[0, 0] * max(1.0, reduced_chi2))),
        "background_coefficients": coefficients[1:].tolist(),
        "reduced_chi2": reduced_chi2,
        "dof": dof,
        "usable_psf_fraction": float(psf[mask].sum()),
    }


def local_solid_angle(wcs: WCS, x: float, y: float) -> float:
    """Steradian estimate from local SIP-aware celestial Jacobian."""
    step = 0.01
    center = wcs.pixel_to_world(x, y)
    frame = center.skyoffset_frame()
    offsets = [
        wcs.pixel_to_world(x + step, y).transform_to(frame),
        wcs.pixel_to_world(x, y + step).transform_to(frame),
    ]
    jacobian = np.array([[p.lon.to_value(u.rad), p.lat.to_value(u.rad)] for p in offsets]).T / step
    return float(abs(np.linalg.det(jacobian)))


def centroid_diagnostic(
    image: np.ndarray,
    variance: np.ndarray,
    epsf: np.ndarray,
    good: np.ndarray,
    x: float,
    y: float,
    oversampling: tuple[int, int],
) -> dict:
    """Profile flux/background while allowing at most 0.6 native-pixel displacement."""
    yy, xx = np.indices(image.shape)
    usable = good & (np.hypot(xx - x, yy - y) <= 6)

    def fit_at(offset: np.ndarray) -> dict:
        psf, _ = native_psf(epsf, image.shape, x + offset[0], y + offset[1], oversampling)
        return linear_photometry(image, variance, psf, usable, x, y, 100, True)

    def objective(offset: np.ndarray) -> float:
        fit = fit_at(offset)
        return fit["reduced_chi2"] * fit["dof"]

    opt = minimize(objective, np.zeros(2), method="Powell", bounds=[(-0.6, 0.6)] * 2)
    fit = fit_at(opt.x)
    return {
        "offset_pixels": opt.x.tolist(),
        "optimizer_success": bool(opt.success),
        "at_search_boundary": bool(np.max(abs(opt.x)) > 0.59),
        "amplitude": fit["amplitude"],
        "reduced_chi2": fit["reduced_chi2"],
        "status": "centroid sensitivity diagnostic, not alternative selection",
    }


def aperture_check(
    image: np.ndarray,
    variance: np.ndarray,
    psf: np.ndarray,
    good: np.ndarray,
    x: float,
    y: float,
    radius: float,
) -> dict:
    yy, xx = np.indices(image.shape)
    distance = np.hypot(xx - x, yy - y)
    usable = good & np.isfinite(image) & np.isfinite(variance) & (variance > 0)
    annulus = usable & (distance >= 4) & (distance <= 8)
    aperture = usable & (distance <= radius)
    fraction = float(psf[aperture].sum())
    if annulus.sum() < 10 or fraction < 0.5:
        return {"status": "insufficient aperture/background coverage"}
    background = float(np.median(image[annulus]))
    scatter = float(1.4826 * np.median(abs(image[annulus] - background)))
    # Median-background standard error: normal approximation, diagnostic only.
    bg_error = 1.2533 * scatter / np.sqrt(annulus.sum())
    amplitude = float(np.sum(image[aperture] - background) / fraction)
    error = float(np.sqrt(variance[aperture].sum() + (aperture.sum() * bg_error) ** 2) / fraction)
    return {
        "amplitude": amplitude,
        "formal_error": error,
        "background_median": background,
        "background_mad_sigma": scatter,
        "psf_fraction": fraction,
        "annulus_pixels": int(annulus.sum()),
    }


def response_coverage(wavelengths: np.ndarray, widths: np.ndarray, response: np.ndarray) -> dict:
    """Report union of nominal channel supports and interpolation hull separately.

    QE response is per photon; Fnu photon-count weighting is R(lambda)/lambda.
    WCS widths are approximations to actual bandpasses, so this is a diagnostic.
    """
    wave = np.linspace(response[0, 0], response[-1, 0], 20001)
    throughput = np.interp(wave, response[:, 0], response[:, 1])
    flat_fnu_weight = throughput / wave
    union = np.zeros(len(wave), dtype=bool)
    for center, width in zip(wavelengths, widths, strict=True):
        union |= abs(wave - center) <= width / 2
    if len(wavelengths):
        hull = (wave >= np.min(wavelengths)) & (wave <= np.max(wavelengths))
    else:
        hull = np.zeros(len(wave), dtype=bool)

    def fraction(mask: np.ndarray, weight: np.ndarray) -> float:
        return float(np.trapezoid(weight * mask, wave) / np.trapezoid(weight, wave))

    # Conservative diagnostic count of nonoverlapping nominal resolution elements.
    count, previous_upper = 0, -np.inf
    for index in np.argsort(wavelengths):
        lower = wavelengths[index] - widths[index] / 2
        if lower >= previous_upper:
            count += 1
            previous_upper = wavelengths[index] + widths[index] / 2
    return {
        "nominal_support_response_fraction": fraction(union, throughput),
        "nominal_support_flat_fnu_photon_fraction": fraction(union, flat_fnu_weight),
        "interpolation_hull_response_fraction": fraction(hull, throughput),
        "interpolation_hull_flat_fnu_photon_fraction": fraction(hull, flat_fnu_weight),
        "nonoverlapping_nominal_channel_count": count,
        "status": "bandpass diagnostic; widths approximate; no flux extrapolation",
    }


def review_frame(path: Path, coordinate: SkyCoord) -> dict:
    """Measure an already acquired actual QR3 FITS file and preserve caveats."""
    receipt_path = Path(str(path).removesuffix(".gz") + ".receipt.json")
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    with fits.open(path, memmap=False) as hdul:
        header = hdul["IMAGE"].header
        image = np.asarray(hdul["IMAGE"].data, dtype=float)
        variance = np.asarray(hdul["VARIANCE"].data, dtype=float)
        flags = np.asarray(hdul["FLAGS"].data, dtype=np.int64)
        if str(header.get("BUNIT", "")).replace(" ", "") != "MJy/sr":
            raise ValueError("unexpected IMAGE units; refuse silent unit assumption")
        spatial = WCS(header)
        x, y = [float(v) for v in spatial.world_to_pixel(coordinate)]
        edge_distance = float(min(x, y, image.shape[1] - 1 - x, image.shape[0] - 1 - y))
        if not (-0.5 <= x <= image.shape[1] - 0.5 and -0.5 <= y <= image.shape[0] - 0.5):
            raise ValueError("coordinate outside acquired image")
        if "ORIGX0" in header:
            parent_x, parent_y = x + header["ORIGX0"], y + header["ORIGY0"]
        else:
            parent_x = 1 + x - header["CRPIX1A"]
            parent_y = 1 + y - header["CRPIX2A"]
        epsf_hdu = hdul["EPSF"]
        table = epsf_hdu.data
        zone = select_zone(table, parent_x, parent_y)
        oversampling = (int(epsf_hdu.header["OVSMPY"]), int(epsf_hdu.header["OVSMPX"]))
        psf, raw_sum = native_psf(table["EPSF"][zone], image.shape, x, y, oversampling)
        # SOURCE and FULLSAMPLE describe information, not rejected detector quality.
        benign = benign_flag_mask(hdul["FLAGS"].header)
        good = ((flags & ~benign) == 0) & np.isfinite(image) & np.isfinite(variance)
        good &= variance > 0
        omega = local_solid_angle(spatial, x, y)
        mjy_factor = omega * 1e9
        fits_out = {}
        for name, plane, radius in [
            ("constant_r6", False, 6),
            ("plane_r6", True, 6),
            ("constant_r4", False, 4),
        ]:
            fit = linear_photometry(image, variance, psf, good, x, y, radius, plane)
            fit["flux_mjy"] = fit["amplitude"] * mjy_factor
            fit["error_mjy"] = fit["residual_scaled_error"] * mjy_factor
            fits_out[name] = fit
        apertures = {}
        for radius in (2, 3):
            ap = aperture_check(image, variance, psf, good, x, y, radius)
            if "amplitude" in ap:
                ap["flux_mjy"] = ap["amplitude"] * mjy_factor
                ap["error_mjy"] = ap["formal_error"] * mjy_factor
            apertures[str(radius)] = ap
        centroid = centroid_diagnostic(
            image, variance, table["EPSF"][zone], good, x, y, oversampling
        )
        centroid["flux_mjy"] = centroid["amplitude"] * mjy_factor
        zone_checks = []
        distances = (table["XCENTER"] - parent_x) ** 2 + (table["YCENTER"] - parent_y) ** 2
        for trial_zone in np.argsort(distances)[:5]:
            trial_psf, _ = native_psf(table["EPSF"][trial_zone], image.shape, x, y, oversampling)
            trial = linear_photometry(image, variance, trial_psf, good, x, y, 6, True)
            mapping = receipt.get("epsf_original_indices", list(range(len(table))))
            zone_checks.append(
                {
                    "zone": int(trial_zone),
                    "original_zone": int(mapping[trial_zone]),
                    "distance_pixels": float(np.sqrt(distances[trial_zone])),
                    "flux_mjy": trial["amplitude"] * mjy_factor,
                    "reduced_chi2": trial["reduced_chi2"],
                }
            )
        # Obtain source wavelength and width from tabular spectral WCS, not footprint.
        spectral_header = header.copy()
        # SIP pertains to celestial axes only; spectral lookup uses raw detector pixels.
        for key in list(spectral_header):
            if key.startswith(("A_", "B_", "AP_", "BP_")):
                del spectral_header[key]
        spectral = WCS(spectral_header, fobj=hdul, key="W")
        spectral.sip = None
        wavelength, bandwidth = spectral.pixel_to_world(x, y)
        original_zone = (
            int(table["EPSFZID"][zone])
            if "EPSFZID" in table.names
            else int(receipt.get("epsf_original_indices", list(range(len(table))))[zone])
        )
        return {
            "path": str(path),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "acquisition_receipt_sha256": sha256(receipt_path) if receipt else None,
            "original_url": receipt.get("url"),
            "original_epsf_sha256": receipt.get("original_epsf_sha256"),
            "kind": "actual data independent measurement",
            "image_shape": list(image.shape),
            "source_pixel": [x, y],
            "parent_pixel": [parent_x, parent_y],
            "edge_distance_pixels": edge_distance,
            "detector": str(header.get("DETECTOR")),
            "mjd": float(header.get("MJD-OBS", header.get("MJD_OBS", np.nan))),
            "wavelength_um": float(wavelength.to_value(u.um)),
            "bandwidth_um": float(bandwidth.to_value(u.um)),
            "epsf_zone": zone,
            "epsf_original_zone": original_zone,
            "epsf_zone_wavelength_um": float(table["CWAVE"][zone]),
            "epsf_raw_native_sum": raw_sum,
            "epsf_native_sum": float(psf.sum()),
            "psf_good_fraction": float(psf[good].sum()),
            "central_flags": int(flags[int(round(y)), int(round(x))]),
            "flag_counts": {
                str(v): int(n) for v, n in zip(*np.unique(flags, return_counts=True), strict=True)
            },
            "benign_flag_mask": benign,
            "solid_angle_sr": omega,
            "mjy_per_mjy_sr_pixel": mjy_factor,
            "solid_angle_method": "approximate local SIP-aware WCS; not calibration SAPM",
            "psf_fits": fits_out,
            "aperture_checks": apertures,
            "centroid_diagnostic": centroid,
            "neighbor_zone_diagnostics": zone_checks,
            "limitations": [
                "ePSF truncated calibration support; wings uncertain",
                "diagonal variance; residual rescaling omits noise covariance",
                "no instrument calibration floor imposed",
                "narrowband flux is not WISE W1",
            ],
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ra", type=float, default=57.641985)
    parser.add_argument("--dec", type=float, default=35.585679)
    parser.add_argument("--response", type=Path)
    args = parser.parse_args()
    coordinate = SkyCoord(args.ra * u.deg, args.dec * u.deg)
    results, errors = [], []
    for path in args.paths:
        try:
            results.append(review_frame(path, coordinate))
        except (OSError, ValueError, KeyError, np.linalg.LinAlgError) as error:
            errors.append({"path": str(path), "sha256": sha256(path), "error": str(error)})
    output = {
        "status": "independent QR3 narrowband measurement; W1 contract not evaluated",
        "coordinate_deg": [args.ra, args.dec],
        "frames": results,
        "failures": errors,
    }
    if args.response and results:
        opener = gzip.open if args.response.suffix == ".gz" else open
        with opener(args.response, "rt") as handle:
            response = np.loadtxt(handle)
        output["w1_response_input"] = {"path": str(args.response), "sha256": sha256(args.response)}
        output["w1_coverage"] = response_coverage(
            np.array([r["wavelength_um"] for r in results]),
            np.array([r["bandwidth_um"] for r in results]),
            response,
        )
        reliable = [
            r for r in results if r["psf_good_fraction"] >= 0.85 and r["edge_distance_pixels"] >= 4
        ]
        output["w1_quality_diagnostic"] = {
            "criterion": "after-outcome diagnostic: >=85%usable PSF; >=4pixel edge distance",
            "accepted_frames": len(reliable),
            "excluded_paths": [r["path"] for r in results if r not in reliable],
            "coverage": response_coverage(
                np.array([r["wavelength_um"] for r in reliable]),
                np.array([r["bandwidth_um"] for r in reliable]),
                response,
            ),
        }
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
