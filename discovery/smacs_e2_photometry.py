"""Unchanged E1/E2 angular operators on independently reduced SMACS pixels."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits

from discovery.independent_repeat_vetting import centroid_diagnostic, heldout_frame
from discovery.smacs_e2_run import E2_FREEZE
from tools.jwst.astrometry import detect_centroids, match_sources
from tools.jwst.fits_loader import load_fits_bundle
from tools.jwst.flux_calibration import flux_density_factors
from tools.jwst.photometry import extract_photometry


def polynomial_aperture(bundle: dict, c: SkyCoord, degree: int) -> dict:
    x, y = bundle["wcs"].world_to_pixel(c)
    scale = np.sqrt(abs(np.linalg.det(bundle["wcs"].pixel_scale_matrix))) * 3600
    half = int(np.ceil(0.65 / scale)) + 1
    ix, iy = int(round(float(x))), int(round(float(y)))
    height, width = bundle["sci"].shape
    if ix - half < 0 or iy - half < 0 or ix + half >= width or iy + half >= height:
        return {"status": "uncovered"}
    yy, xx = np.mgrid[iy - half : iy + half + 1, ix - half : ix + half + 1]
    sky = bundle["wcs"].pixel_to_world(xx, yy)
    east, north = c.spherical_offsets_to(sky)
    east, north = east.arcsec, north.arcsec
    r = c.separation(sky).arcsec
    valid = bundle["validity_mask"][yy, xx].copy()
    error = bundle["err"][yy, xx]
    valid &= np.isfinite(error) & (error > 0)
    conversion = flux_density_factors(bundle, xx, yy)
    if conversion["status"] != "calibrated":
        return {"status": "uncalibrated"}
    factor = conversion["factor_jy"] * 1e9
    values = bundle["sci"][yy, xx] * factor
    sigma = error * factor
    aperture = r <= 0.18873115
    coverage = float(np.mean(valid[aperture]))
    background = valid & (r >= 0.3) & (np.abs(east) <= 0.65) & (np.abs(north) <= 0.65)
    columns = [np.ones_like(east)]
    if degree >= 1:
        columns += [east, north]
    if degree >= 2:
        columns += [east**2, east * north, north**2]
    design = np.stack(columns, axis=-1)
    if coverage < 0.9 or background.sum() < len(columns) + 2:
        return {"status": "uncovered", "coverage": coverage}
    matrix = design[background] / sigma[background, None]
    beta, _, rank, _ = np.linalg.lstsq(matrix, values[background] / sigma[background], rcond=None)
    if rank != len(columns):
        return {"status": "background not estimable"}
    residual = values - design @ beta
    return {
        "status": "measured",
        "flux_njy": float(np.sum(residual[aperture & valid])),
        "coverage": coverage,
        "background_coefficients": beta.tolist(),
        "background_pixels": int(background.sum()),
    }


def operators(bundle: dict, c: SkyCoord) -> dict:
    p = extract_photometry(
        bundle,
        ra_deg=c.ra.deg,
        dec_deg=c.dec.deg,
        aperture_radius_arcsec=0.18873115,
        background_annulus_inner_radius_arcsec=0.37746230,
        background_annulus_outer_radius_arcsec=0.62910384,
    )
    flux = p.get("background_subtracted_flux_jy")
    a = {
        "status": "measured"
        if flux is not None and p.get("coverage_fraction", 0) >= 0.9
        else "uncovered",
        "flux_njy": None if flux is None else flux * 1e9,
        "coverage": p.get("coverage_fraction"),
        "diagonal_error_njy": None if p.get("flux_error_jy") is None else p["flux_error_jy"] * 1e9,
    }
    return {"annulus": a, **{f"poly{d}": polynomial_aperture(bundle, c, d) for d in range(3)}}


def null_gate(targets: list[dict], controls: list[list[dict]]) -> dict:
    results = {}
    for name in ("annulus", "poly0", "poly1", "poly2"):
        eligible = [
            i
            for i in range(len(controls[0]))
            if all(controls[e][i][name]["status"] == "measured" for e in range(2))
        ]
        if len(eligible) < 40 or any(t[name]["status"] != "measured" for t in targets):
            results[name] = {"status": "blocked: coverage", "covered_controls": len(eligible)}
            continue
        c = np.array([[controls[e][i][name]["flux_njy"] for i in eligible] for e in range(2)])
        scale = 1.4826 * np.median(np.abs(c - np.median(c, axis=1)[:, None]), axis=1)
        if np.any(scale <= 0) or np.any(~np.isfinite(scale)):
            results[name] = {"status": "blocked: empirical scale"}
            continue
        flux = np.array([t[name]["flux_njy"] for t in targets])
        statistic = float(np.min(flux / scale))
        null_statistic = np.min(c / scale[:, None], axis=0)
        count = int(np.sum(null_statistic >= statistic))
        p = (1 + count) / (1 + len(eligible))
        ratio = float(flux[1] / flux[0]) if flux[0] > 0 else None
        passed = bool(
            np.all(flux / scale >= 5) and p <= 0.0125 and ratio is not None and 0.7 <= ratio <= 1.3
        )
        results[name] = {
            "status": "pass diagnostic thresholds" if passed else "failed thresholds",
            "covered_controls": len(eligible),
            "target_flux_njy": flux.tolist(),
            "control_mad_scale_njy": scale.tolist(),
            "empirical_snr": (flux / scale).tolist(),
            "joint_min_statistic": statistic,
            "null_greater_equal": count,
            "rank_p": p,
            "rank_p_threshold": 0.0125,
            "repeat_reference_ratio": ratio,
            "limitation": (
                "spatially dependent structured-light rank diagnostic; "
                "not independent-tail calibration"
            ),
        }
    return results


def compact_image(bundle: dict, center: SkyCoord, path: Path) -> dict:
    x, y = bundle["wcs"].world_to_pixel(center)
    scale = np.sqrt(abs(np.linalg.det(bundle["wcs"].pixel_scale_matrix))) * 3600
    half = int(np.ceil(8 / scale))
    ix, iy = int(round(float(x))), int(round(float(y)))
    sx, sy = slice(ix - half, ix + half + 1), slice(iy - half, iy + half + 1)
    header = bundle["wcs"].slice((sy, sx)).to_header()
    header["BUNIT"] = bundle["header"]["BUNIT"]
    hdus = [
        fits.PrimaryHDU(header=bundle["primary_header"]),
        fits.ImageHDU(bundle["sci"][sy, sx].astype("f4"), header=header, name="SCI"),
        fits.ImageHDU(bundle["err"][sy, sx].astype("f4"), name="ERR"),
    ]
    if bundle.get("wht") is not None:
        hdus.append(fits.ImageHDU(bundle["wht"][sy, sx].astype("f4"), name="WHT"))
    fits.HDUList(hdus).writeto(path, overwrite=True)
    return {
        "filename": str(path),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "kind": "compact derived calibrated cutout",
    }


def measure(paths: list[Path], out: Path, *, compact: bool = True) -> dict:
    geometry = json.loads(Path("research_output/session_20261014/e2_geometry.json").read_text())
    c = SkyCoord(**geometry["target"], unit="deg")
    rows, controls, bundles = [], [], []
    result = {
        "freeze_commit": E2_FREEZE,
        "first_target_array_access_utc": datetime.now(timezone.utc).isoformat(),
        "target": geometry["target"],
        "control_positions": geometry["controls"],
        "images": [],
    }
    for path in paths:
        bundle = load_fits_bundle(str(path))
        bundles.append(bundle)
        target = operators(bundle, c)
        positions = [SkyCoord(x["ra_deg"], x["dec_deg"], unit="deg") for x in geometry["controls"]]
        measured = [operators(bundle, x) for x in positions]
        rows.append(target)
        controls.append(measured)
        r = {
            "filename": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "target_operators": target,
            "control_operators": measured,
            "cal_ver": bundle["primary_header"].get("CAL_VER"),
            "crds_context": bundle["primary_header"].get("CRDS_CTX"),
        }
        if compact:
            r["compact_image"] = compact_image(
                bundle, c, out.parent / (path.stem + "_compact.fits")
            )
        result["images"].append(r)
    result["null_control_gates"] = null_gate(rows, controls)
    if compact:
        points = [detect_centroids(b) for b in bundles]
        skies = [b["wcs"].pixel_to_world(p[:, 0], p[:, 1]) for b, p in zip(bundles, points)]
        reference = [
            {"id": f"reference_{i}", "ra": s.ra.deg, "dec": s.dec.deg}
            for i, s in enumerate(skies[0])
            if s.separation(c).arcsec >= 1
        ]
        matches = match_sources(bundles[1], points[1], reference, radius_arcsec=0.2)
        frame = heldout_frame(matches["matches"])
        result["astrometry"] = frame
        result["centroid_association"] = [centroid_diagnostic(c, s) for s in skies]
        result["astrometry_gate_passed"] = (
            frame.get("status") == "measured"
            and frame["holdout_corrected_radial_median_p90_arcsec"][1] <= 0.05
        )
        associated = all(x["is_association"] for x in result["centroid_association"])
        pair_separation = None
        if associated and frame.get("status") == "measured":
            offsets = np.array(
                [x["offset_east_north_arcsec"] for x in result["centroid_association"]]
            )
            shift = np.array(frame["training_median_offset_east_north_arcsec"])
            pair_separation = float(np.linalg.norm(offsets[1] - offsets[0] - shift))
        result["registered_centroid_pair_separation_arcsec"] = pair_separation
        result["centroid_gate_passed"] = bool(
            associated and pair_separation is not None and pair_separation <= 0.05
        )
    failed = [
        name
        for name, gate in result["null_control_gates"].items()
        if gate["status"] != "pass diagnostic thresholds"
    ]
    result["frozen_all_operator_null_gate_passed"] = not failed
    result["injection_recovery"] = {
        "status": "not run",
        "reason": "required null/association gates already failed; no calibrated point-source PSF",
    }
    result["scientific_verdict"] = (
        "failed required frozen promotion gates; persistent aperture patch remains unconfirmed"
        if failed or result.get("centroid_gate_passed") is False
        else "no promotion; required injection-recovery gate has not been run"
    )
    out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", type=Path, nargs=2)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay-compact", action="store_true")
    args = parser.parse_args()
    r = measure(args.images, args.output, compact=not args.replay_compact)
    print(json.dumps(r["null_control_gates"], indent=2))


if __name__ == "__main__":
    main()
