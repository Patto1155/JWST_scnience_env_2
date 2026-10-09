"""Observed two-dither stellar aperture curves under finite-reference controls.

The reference is a larger measured aperture, never an asserted total stellar
flux. M92 cal images differ from GOODS-S/JADES modeled mosaic PSFs, so this
conditional observed-star comparison does not supply a universal correction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from scipy.spatial import cKDTree

from discovery.native_psf import ANNULUS, RADIUS, native_response
from discovery.psf_noise import DEFAULT_PHASES, read_image, robust_sigma, verified_template
from tools.jwst.flux_calibration import celestial_wcs, flux_density_factors
from tools.jwst.photometry import extract_photometry

REFERENCE_RADII = (0.45, 0.6, 0.8)
CURVE_RADII = (0.1258253863005391, RADIUS, 0.25, 0.315, 0.45, 0.6, 0.8)
REFERENCE_BACKGROUNDS = ((0.95, 1.35, False), (0.95, 1.35, True), (1.1, 1.5, True))
POLICY = {
    "object_type": 1,
    "minimum_reference_snr": 100,
    "vega_magnitude_range": [15, 19],
    "maximum_abs_sharpness": 0.1,
    "maximum_crowding_mag": 0.05,
    "quality_flag": 0,
    "neighbor_minimum_reference_snr": 3,
    "neighbor_maximum_vega_magnitude": 30,
    "isolation_radius_arcsec": 0.8,
    "maximum_summed_neighbor_catalog_flux_ratio": 0.03,
    "minimum_large_aperture_coverage": 0.99,
    "core_radius_arcsec": 0.3,
    "minimum_annulus_coverage": 0.5,
    "minimum_reference_aperture_snr": 30,
    "maximum_centroid_catalog_separation_arcsec": 0.2,
    "maximum_centroid_radius_method_difference_pixels": 0.15,
    "neighbor_background_mask_radius_arcsec": 0.22,
    "DQ_excluded_bits": 3,
    "maximum_selected_stars": 24,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify(path: Path) -> dict[str, Any]:
    receipt = json.loads(path.with_name(path.name + ".provenance.json").read_text())
    if path.stat().st_size != receipt["bytes"] or sha256(path) != receipt["sha256"]:
        raise ValueError(f"input receipt mismatch: {path.name}")
    return receipt


def unit_vectors(ra: np.ndarray, dec: np.ndarray) -> np.ndarray:
    ra, dec = np.deg2rad(ra), np.deg2rad(dec)
    return np.column_stack((np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)))


def select_catalog(catalog: Path, bundles: list[dict[str, Any]]) -> tuple[list[dict], dict, dict]:
    receipt = verify(catalog)
    with fits.open(catalog, memmap=True) as hdus:
        table = hdus[1].data
        names = [
            "NUMBER",
            "RA",
            "DEC",
            "OBJECT_TYPE",
            "F444W_VEGA",
            "F444W_SNR",
            "F444W_SHARP",
            "F444W_CROWD",
            "F444W_FLAG",
            "F444W_ERR",
        ]
        cols = {name: np.asarray(table[name], float).copy() for name in names}
        raw_rows = len(table)
    coordinates = np.isfinite(cols["RA"] + cols["DEC"])
    coordinates &= (cols["RA"] >= 0) & (cols["RA"] < 360) & (np.abs(cols["DEC"]) <= 90)
    valid = coordinates & np.isfinite(cols["F444W_VEGA"] + cols["F444W_SNR"])
    valid &= (cols["F444W_VEGA"] > 0) & (cols["F444W_VEGA"] < 30) & (cols["F444W_SNR"] >= 3)
    quality = valid & (cols["OBJECT_TYPE"] == 1) & (cols["F444W_SNR"] >= 100)
    quality &= (cols["F444W_VEGA"] >= 15) & (cols["F444W_VEGA"] < 19)
    quality &= np.abs(cols["F444W_SHARP"]) <= 0.1
    quality &= (cols["F444W_CROWD"] >= 0) & (cols["F444W_CROWD"] <= 0.05)
    quality &= (cols["F444W_FLAG"] == 0) & (cols["F444W_ERR"] > 0) & (cols["F444W_ERR"] < 9)
    candidates = np.flatnonzero(quality)
    covered = np.ones(len(candidates), bool)
    for bundle in bundles:
        wcs = celestial_wcs(bundle)
        if wcs is None:
            raise ValueError("M92 image requires celestial WCS")
        x, y = wcs.world_to_pixel_values(cols["RA"][candidates], cols["DEC"][candidates])
        scale = np.min(np.linalg.svd(wcs.pixel_scale_matrix, compute_uv=False)) * 3600
        margin = int(np.ceil(1.6 / scale)) + 4
        covered &= np.isfinite(x + y) & (x >= margin) & (y >= margin)
        covered &= (x < bundle["sci"].shape[1] - margin) & (y < bundle["sci"].shape[0] - margin)
    candidates = candidates[covered]
    neighbor_indices = np.flatnonzero(valid)
    xyz = unit_vectors(cols["RA"][valid], cols["DEC"][valid])
    tree = cKDTree(xyz)
    candidate_xyz = unit_vectors(cols["RA"][candidates], cols["DEC"][candidates])
    distance = 2 * np.sin(np.deg2rad(0.8 / 3600) / 2)
    neighborhoods = tree.query_ball_point(candidate_xyz, distance)
    selected = []
    for index, neighborhood in zip(candidates, neighborhoods):
        neighbors = neighbor_indices[neighborhood]
        neighbors = neighbors[neighbors != index]
        ratio = float(
            np.sum(10 ** (-0.4 * (cols["F444W_VEGA"][neighbors] - cols["F444W_VEGA"][index])))
        )
        if ratio < 0.03:
            selected.append(
                {
                    "source_id": str(int(cols["NUMBER"][index])),
                    "catalog_index": int(index),
                    "ra": float(cols["RA"][index]),
                    "dec": float(cols["DEC"][index]),
                    "vega_magnitude": float(cols["F444W_VEGA"][index]),
                    "reference_snr": float(cols["F444W_SNR"][index]),
                    "catalog_neighbor_flux_ratio_inside_08": ratio,
                }
            )
    selected.sort(key=lambda r: (r["vega_magnitude"], r["source_id"]))
    summary = {
        "catalog_receipt": receipt,
        "raw_rows": raw_rows,
        "reference_quality_rows": int(np.count_nonzero(quality)),
        "covered_in_both_images": int(len(candidates)),
        "isolated_candidates_before_image_gates": len(selected),
        "neighbor_reference_rows": len(neighbor_indices),
        "policy": POLICY,
    }
    neighbor_data = {"columns": cols, "tree": tree, "indices": neighbor_indices}
    return selected, summary, neighbor_data


def valid_pixels(bundle: dict) -> np.ndarray:
    valid = np.isfinite(bundle["sci"]) & np.isfinite(bundle["err"]) & (bundle["err"] > 0)
    if bundle.get("dq") is not None:
        valid &= (bundle["dq"].astype(np.uint32) & 3) == 0
    return valid


def centroid(bundle: dict, x: float, y: float, *, radius: float = 3) -> tuple[float, float]:
    """Bounded positive core centroid; catalog remains the independent identity."""
    image, valid = bundle["sci"], bundle["validity_mask"]
    ix, iy = int(np.round(x)), int(np.round(y))
    xx, yy = np.meshgrid(np.arange(ix - 18, ix + 19), np.arange(iy - 18, iy + 19))
    if (
        np.min(xx) < 0
        or np.min(yy) < 0
        or np.max(xx) >= image.shape[1]
        or np.max(yy) >= image.shape[0]
    ):
        raise ValueError("centroid footprint off image")
    values = image[yy, xx]
    good = valid[yy, xx]
    radial = np.hypot(xx - x, yy - y)
    ann = good & (radial >= 10) & (radial <= 16)
    if ann.sum() < 20:
        raise ValueError("insufficient centroid background")
    background = float(np.median(values[ann]))
    near = good & (radial <= 4)
    if not np.any(near):
        raise ValueError("no valid centroid core")
    peak_index = np.argmax(np.where(near, values, -np.inf))
    cx, cy = float(xx.ravel()[peak_index]), float(yy.ravel()[peak_index])
    for _ in range(5):
        core = good & (np.hypot(xx - cx, yy - cy) <= radius)
        weights = np.where(core, np.maximum(values - background, 0), 0)
        weights[~np.isfinite(weights)] = 0
        total = float(weights.sum())
        if total <= 0:
            raise ValueError("no positive centroid flux")
        cx, cy = float(np.sum(xx * weights) / total), float(np.sum(yy * weights) / total)
    return cx, cy


def neighbor_mask(bundle: dict, source: dict, neighbors: dict) -> np.ndarray:
    """Independent-catalog source masks only affect reference background annuli."""
    columns, tree, indices = neighbors["columns"], neighbors["tree"], neighbors["indices"]
    xyz = unit_vectors(np.array([source["ra"]]), np.array([source["dec"]]))[0]
    nearby = indices[tree.query_ball_point(xyz, 2 * np.sin(np.deg2rad(1.8 / 3600) / 2))]
    nearby = nearby[nearby != source["catalog_index"]]
    wcs = bundle["wcs"]
    mask = np.zeros(bundle["sci"].shape, bool)
    for index in nearby:
        x, y = wcs.world_to_pixel_values(columns["RA"][index], columns["DEC"][index])
        margin = 5
        xx, yy = np.meshgrid(
            np.arange(int(np.floor(x)) - margin, int(np.ceil(x)) + margin + 1),
            np.arange(int(np.floor(y)) - margin, int(np.ceil(y)) + margin + 1),
        )
        inside = (xx >= 0) & (yy >= 0) & (xx < mask.shape[1]) & (yy < mask.shape[0])
        world = wcs.pixel_to_world(xx, yy)
        separation = world.separation(
            SkyCoord(columns["RA"][index], columns["DEC"][index], unit="deg")
        ).arcsec
        chosen = inside & (separation <= 0.22)
        mask[yy[chosen], xx[chosen]] = True
    return mask


def measure(
    bundle: dict,
    x: float,
    y: float,
    radius: float,
    annulus: tuple[float, float],
    background_mask: np.ndarray | None = None,
) -> dict[str, Any]:
    """Physical calibrated native operator with explicit sparse diagonal weights."""
    if (
        not np.all(np.isfinite([x, y, radius, *annulus]))
        or not 0 < radius < annulus[0] < annulus[1]
    ):
        raise ValueError("invalid aperture geometry")
    wcs = bundle["wcs"]
    center = wcs.pixel_to_world(x, y)
    boundary = center.directional_offset_by(
        np.linspace(0, 360, 129) * center.ra.unit, annulus[1] / 3600 * center.ra.unit
    )
    bx, by = wcs.world_to_pixel(boundary)
    margin = int(np.ceil(max(np.max(np.abs(bx - x)), np.max(np.abs(by - y))))) + 2
    xx, yy = np.meshgrid(
        np.arange(int(np.floor(x)) - margin, int(np.ceil(x)) + margin + 1),
        np.arange(int(np.floor(y)) - margin, int(np.ceil(y)) + margin + 1),
    )
    inside = (xx >= 0) & (yy >= 0) & (xx < bundle["sci"].shape[1]) & (yy < bundle["sci"].shape[0])
    distance = wcs.pixel_to_world(xx, yy).separation(center).arcsec
    full_ap = distance <= radius
    full_ann = (distance >= annulus[0]) & (distance <= annulus[1])
    valid = np.zeros(xx.shape, bool)
    valid[inside] = bundle["validity_mask"][yy[inside], xx[inside]]
    ap, ann = full_ap & valid, full_ann & valid
    if background_mask is not None:
        ann[inside] &= ~background_mask[yy[inside], xx[inside]]
    if not np.any(ap) or ann.sum() < 2:
        raise ValueError("unmeasurable aperture/background")
    calibration = flux_density_factors(bundle, xx, yy)
    if calibration["status"] != "calibrated":
        raise ValueError("physical calibration unavailable")
    factors = calibration["factor_jy"]
    coefficients = np.where(ap, factors, 0)
    coefficients[ann] = -float(factors[ap].sum()) / int(ann.sum())
    support = ap | ann
    values = bundle["sci"][yy[support], xx[support]]
    errors = bundle["err"][yy[support], xx[support]]
    flux = float(np.sum(coefficients[support] * values))
    sigma = float(np.sqrt(np.sum((coefficients[support] * errors) ** 2)))
    pixels = yy[support] * bundle["sci"].shape[1] + xx[support]
    return {
        "radius_arcsec": radius,
        "annulus_arcsec": annulus,
        "flux_jy": flux,
        "diagonal_sigma_jy": sigma,
        "snr_diagonal": flux / sigma if sigma > 0 else None,
        "aperture_coverage": float(ap.sum() / full_ap.sum()),
        "annulus_coverage": float(ann.sum() / full_ann.sum()),
        "aperture_pixels": int(ap.sum()),
        "annulus_pixels": int(ann.sum()),
        "background_neighbor_masked": background_mask is not None,
        "weights": {int(i): float(v) for i, v in zip(pixels, coefficients[support])},
    }


def ratio(a: dict, b: dict, errors: np.ndarray) -> dict[str, Any]:
    """Ratio error includes shared-pixel aperture/background covariance."""
    if not np.isfinite(a["flux_jy"] + b["flux_jy"]) or b["flux_jy"] <= 0:
        raise ValueError("positive finite reference flux required")
    covariance = sum(
        value * b["weights"].get(index, 0) * errors.ravel()[index] ** 2
        for index, value in a["weights"].items()
    )
    value = a["flux_jy"] / b["flux_jy"]
    derivative: dict[int, float] = {
        index: coefficient / b["flux_jy"] for index, coefficient in a["weights"].items()
    }
    for index, coefficient in b["weights"].items():
        derivative[index] = (
            derivative.get(index, 0) - a["flux_jy"] * coefficient / b["flux_jy"] ** 2
        )
    variance = sum(
        coefficient**2 * errors.ravel()[index] ** 2 for index, coefficient in derivative.items()
    )
    return {
        "finite_aperture_ratio": value,
        "diagonal_ratio_sigma": float(np.sqrt(variance)),
        "shared_pixel_flux_covariance_jy2": float(covariance),
        "error_scope": "diagonal ERR with shared-pixel covariance; detector correlations and calibration excluded",
    }


def grouped_summary(rows: list[dict], *, seed: int = 932) -> dict:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["source_id"], []).append(row)
    pairs = [values for values in groups.values() if len(values) == 2]
    means = np.array([np.mean([r["finite_aperture_ratio"] for r in values]) for values in pairs])
    differences = np.array(
        [
            values[1]["finite_aperture_ratio"] - values[0]["finite_aperture_ratio"]
            for values in pairs
        ]
    )
    if not len(pairs):
        return {"status": "not_estimable", "stars": 0}
    interval = None
    if len(pairs) >= 5:
        rng = np.random.default_rng(seed)
        estimates = [np.median(means[rng.integers(0, len(means), len(means))]) for _ in range(1000)]
        interval = [float(v) for v in np.quantile(estimates, [0.025, 0.975])]
    return {
        "status": "measured",
        "stars": len(pairs),
        "dependent_exposure_measurements": 2 * len(pairs),
        "median_star_mean_ratio": float(np.median(means)),
        "star_mean_ratio_16_84": [float(v) for v in np.quantile(means, [0.16, 0.84])],
        "median_source_bootstrap_95": interval,
        "median_epoch2_minus_epoch1_ratio": float(np.median(differences)),
        "repeat_difference_robust_sigma": robust_sigma(differences),
        "repeat_difference_ordinary_sigma": float(np.std(differences, ddof=1))
        if len(pairs) > 1
        else None,
        "median_diagonal_ratio_sigma": float(
            np.median([r["diagonal_ratio_sigma"] for values in pairs for r in values])
        ),
        "interval_scope": "source-group resampling, conditional one field/visit and selection; no whole-field systematic error",
    }


def model_reference(directory: Path, sampled_scales: tuple[float, ...] = (0.063,)) -> dict:
    template, provenance = verified_template(directory / "f444wa_v5.0_mpsf.fits", "F444W")
    scale = 0.063
    small = native_response(
        template,
        input_scale=provenance["input_scale_arcsec"],
        output_scale=scale,
        phase=(0, 0),
        radius=RADIUS,
        annulus=ANNULUS,
    )
    ratios = []
    for radius in REFERENCE_RADII:
        for inner, outer, masked in REFERENCE_BACKGROUNDS:
            # The modeled comparator contains no neighbors to mask.
            big = native_response(
                template,
                input_scale=provenance["input_scale_arcsec"],
                output_scale=scale,
                phase=(0, 0),
                radius=radius,
                annulus=(inner, outer),
            )
            ratios.append(
                {
                    "reference_radius_arcsec": radius,
                    "background_annulus_arcsec": [inner, outer],
                    "background_neighbor_masked": masked,
                    "modeled_small_net_response_finite_template": small["net_response"],
                    "modeled_reference_net_response_finite_template": big["net_response"],
                    "modeled_finite_aperture_ratio": small["net_response"] / big["net_response"],
                }
            )
    curve = []
    for radius in CURVE_RADII:
        trials = []
        for grid_scale in sampled_scales:
            for phase in DEFAULT_PHASES:
                numerator = native_response(
                    template,
                    input_scale=provenance["input_scale_arcsec"],
                    output_scale=grid_scale,
                    phase=phase,
                    radius=radius,
                    annulus=(0.95, 1.35),
                )
                denominator = native_response(
                    template,
                    input_scale=provenance["input_scale_arcsec"],
                    output_scale=grid_scale,
                    phase=phase,
                    radius=0.8,
                    annulus=(0.95, 1.35),
                )
                trials.append(numerator["net_response"] / denominator["net_response"])
        curve.append(
            {
                "radius_arcsec": radius,
                "nine_phase_and_scale_sensitivity_range": [float(min(trials)), float(max(trials))],
            }
        )
    return {
        "provenance": provenance,
        "comparator_sampling_arcsec": scale,
        "curve_finite_08": curve,
        "curve_sampling_scales_arcsec": sampled_scales,
        "phase_grid": DEFAULT_PHASES,
        "ratios": ratios,
        "limits": "Modeled mosaic shape on an isotropic grid, not a model of this cal exposure's field/visit/SIP/phase.",
    }


def run(directory: Path, psf_directory: Path, *, maximum_stars: int = 24) -> dict:
    if not 1 <= maximum_stars <= 100:
        raise ValueError("bounded maximum_stars must be between 1 and 100")
    catalog = directory / "hlsp_jwststars_jwst_nircam_m92_f090w-f150w-f277w-f444w_v1_phot.fits"
    paths = [directory / f"jw01334001001_04101_0000{n}_nrcalong_cal.fits" for n in (1, 4)]
    bundles = []
    provenance = []
    for path in paths:
        receipt = verify(path)
        bundle = read_image(path)
        bundle["wcs"] = celestial_wcs(bundle)
        bundle["validity_mask"] = valid_pixels(bundle)
        bundles.append(bundle)
        header = bundle["primary_header"]
        provenance.append(
            {
                "filename": path.name,
                "receipt": receipt,
                "CAL_VER": header.get("CAL_VER"),
                "CRDS_CTX": header.get("CRDS_CTX"),
                "EXPMID": header.get("EXPMID"),
            }
        )
    candidates, selection, neighbors = select_catalog(catalog, bundles)
    selected = []
    excluded: Counter[str] = Counter()
    attempted = []
    records = []
    transfer = []
    sampled_scales = []
    for source in candidates:
        if len(selected) >= maximum_stars:
            break
        source_records = []
        source_checks = []
        fail = None
        for epoch, bundle in enumerate(bundles):
            wcs = bundle["wcs"]
            x, y = wcs.world_to_pixel(SkyCoord(source["ra"], source["dec"], unit="deg"))
            try:
                cx, cy = centroid(bundle, float(x), float(y), radius=3)
                dx, dy = centroid(bundle, float(x), float(y), radius=2.5)
                displacement = (
                    wcs.pixel_to_world(cx, cy).separation(wcs.pixel_to_world(x, y)).arcsec
                )
                if displacement > 0.2 or np.hypot(cx - dx, cy - dy) > 0.15:
                    raise ValueError("ambiguous_centroid")
                core = measure(bundle, cx, cy, 0.3, (0.95, 1.35))
                if core["aperture_coverage"] < 1:
                    raise ValueError("masked_or_saturated_core")
                small = measure(bundle, cx, cy, RADIUS, ANNULUS)
                production = extract_photometry(
                    bundle,
                    x=cx,
                    y=cy,
                    aperture_radius_arcsec=RADIUS,
                    background_annulus_inner_radius_arcsec=ANNULUS[0],
                    background_annulus_outer_radius_arcsec=ANNULUS[1],
                )
                source_checks.append(
                    {
                        "source_id": source["source_id"],
                        "epoch": epoch,
                        "flux_residual_jy": small["flux_jy"]
                        - production["background_subtracted_flux_jy"],
                        "diagonal_sigma_ratio": small["diagonal_sigma_jy"]
                        / production["flux_error_jy"],
                    }
                )
                forced = measure(bundle, float(x), float(y), RADIUS, ANNULUS)
                bgmask = neighbor_mask(bundle, source, neighbors)
                for reference_radius in REFERENCE_RADII:
                    for inner, outer, masked in REFERENCE_BACKGROUNDS:
                        reference = measure(
                            bundle,
                            cx,
                            cy,
                            reference_radius,
                            (inner, outer),
                            bgmask if masked else None,
                        )
                        if reference["aperture_coverage"] < 0.99:
                            raise ValueError("reference_coverage")
                        if reference["annulus_coverage"] < 0.5 or small["annulus_coverage"] < 0.8:
                            raise ValueError("background_coverage")
                        if reference["snr_diagonal"] is None or reference["snr_diagonal"] < 30:
                            raise ValueError("reference_signal_to_noise")
                        row = {
                            "source_id": source["source_id"],
                            "epoch": epoch,
                            "image": paths[epoch].name,
                            "reference_radius_arcsec": reference_radius,
                            "reference_background_annulus_arcsec": [inner, outer],
                            "reference_background_neighbor_masked": masked,
                            "centroid_x": cx,
                            "centroid_y": cy,
                            "catalog_centroid_separation_arcsec": float(displacement),
                            "small_flux_jy": small["flux_jy"],
                            "reference_flux_jy": reference["flux_jy"],
                            "reference_coverage": reference["aperture_coverage"],
                            "reference_annulus_coverage": reference["annulus_coverage"],
                            **ratio(small, reference, bundle["err"]),
                        }
                        row["forced_catalog_to_centroid_small_flux_ratio"] = (
                            forced["flux_jy"] / small["flux_jy"]
                        )
                        source_records.append(row)
                # The same far masked background for all curve radii, finite .8arcsec normalization.
                largest = measure(bundle, cx, cy, 0.8, (0.95, 1.35), bgmask)
                curves = []
                for radius in CURVE_RADII:
                    point = measure(bundle, cx, cy, radius, (0.95, 1.35), bgmask)
                    curves.append({"radius_arcsec": radius, **ratio(point, largest, bundle["err"])})
                local = flux_density_factors(bundle, np.array([[cx]]), np.array([[cy]]))
                local_scale = float(np.sqrt(local["pixel_area_sr"][0, 0]) * 180 / np.pi * 3600)
                source_records.append(
                    {
                        "source_id": source["source_id"],
                        "epoch": epoch,
                        "image": paths[epoch].name,
                        "local_pixel_area_scale_arcsec": local_scale,
                        "curve_of_growth_finite_08": curves,
                    }
                )
            except ValueError as error:
                fail = str(error)
                break
        attempted.append(
            {
                "source_id": source["source_id"],
                "accepted_both_images": fail is None,
                "failure": fail,
            }
        )
        if fail:
            excluded[fail] += 1
            continue
        selected.append(source)
        sampled_scales.extend(
            r["local_pixel_area_scale_arcsec"]
            for r in source_records
            if "local_pixel_area_scale_arcsec" in r
        )
        records.extend(source_records)
        transfer.extend(source_checks)
    summaries = []
    for reference_radius in REFERENCE_RADII:
        for inner, outer, masked in REFERENCE_BACKGROUNDS:
            rows = [
                r
                for r in records
                if r.get("reference_radius_arcsec") == reference_radius
                and r["reference_background_annulus_arcsec"] == [inner, outer]
                and r["reference_background_neighbor_masked"] == masked
            ]
            summaries.append(
                {
                    "reference_radius_arcsec": reference_radius,
                    "reference_background_annulus_arcsec": [inner, outer],
                    "reference_background_neighbor_masked": masked,
                    **grouped_summary(rows),
                }
            )
    all_ratios = [
        r["forced_catalog_to_centroid_small_flux_ratio"]
        for r in records
        if r.get("reference_radius_arcsec") == 0.8
        and r["reference_background_annulus_arcsec"] == [0.95, 1.35]
        and r["reference_background_neighbor_masked"]
    ]
    curves = []
    for radius in CURVE_RADII:
        rows = [
            {"source_id": r["source_id"], "epoch": r["epoch"], **point}
            for r in records
            for point in r.get("curve_of_growth_finite_08", [])
            if point["radius_arcsec"] == radius
        ]
        curves.append({"radius_arcsec": radius, **grouped_summary(rows)})
    return {
        "experiment": "observed M92 two-dither finite-aperture response",
        "schema_version": 1,
        "actual_observed_stars": True,
        "not_true_total_encircled_energy": True,
        "policy": {**POLICY, "maximum_selected_stars": maximum_stars},
        "selection": selection,
        "attempted_candidates": attempted,
        "gate_failure_counts": dict(excluded),
        "selected_stars": selected,
        "selected_star_count": len(selected),
        "image_provenance": provenance,
        "science_radius_arcsec": RADIUS,
        "science_annulus_arcsec": ANNULUS,
        "summaries": summaries,
        "curve_of_growth_finite_08": curves,
        "forced_catalog_to_centroid_ratio_quantiles_16_50_84": [
            float(v) for v in np.quantile(all_ratios, [0.16, 0.5, 0.84])
        ]
        if all_ratios
        else [],
        "production_operator_transfer": transfer,
        "modeled_comparator": model_reference(
            psf_directory,
            sampled_scales=tuple(float(v) for v in np.quantile(sampled_scales, [0, 0.5, 1]))
            if sampled_scales
            else (0.063,),
        ),
        "records": records,
        "code_sha256": sha256(Path(__file__)),
        "limits": [
            "Larger apertures are finite references, not true total flux or measured infinite-aperture EE.",
            "Catalog neighbor sum is a conditional contamination screen; uncataloged/faint neighbors remain.",
            "DOLPHOT catalog and current image calibration versions differ; image cores are recentered independently.",
            "Two dithers share one visit and stars; group bootstrap excludes field-wide systematic uncertainty.",
            "M92 cal detector pixels are not GOODS-S/JADES i2d mosaic pixels; a universal correction is unsupported.",
            "Diagonal ratio error includes shared pixels; interpixel detector/noise correlations remain unknown.",
            "Observed stellar SED, field PSF variation, sample selection and background masking affect transfer.",
        ],
    }


def compact(report: dict) -> dict:
    result = {key: value for key, value in report.items() if key != "records"}
    raw = json.dumps(
        report["records"], sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    result["regenerable_records"] = {
        "count": len(report["records"]),
        "canonical_json_sha256": hashlib.sha256(raw).hexdigest(),
    }
    return result


def plot_report(report: dict, path: Path) -> None:
    """Scientific finite-aperture diagnostic; no generated imagery or fitting."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.9))
    curve = report["curve_of_growth_finite_08"]
    radius = np.array([r["radius_arcsec"] for r in curve])
    observed = np.array([r["median_star_mean_ratio"] for r in curve])
    lower = np.array([r["median_source_bootstrap_95"][0] for r in curve])
    upper = np.array([r["median_source_bootstrap_95"][1] for r in curve])
    model = report["modeled_comparator"]["curve_finite_08"]
    model_lower = np.array([r["nine_phase_and_scale_sensitivity_range"][0] for r in model])
    model_upper = np.array([r["nine_phase_and_scale_sensitivity_range"][1] for r in model])
    axes[0].fill_between(
        radius,
        model_lower,
        model_upper,
        color="#9a9da5",
        alpha=0.4,
        label="JADES model: phase/scale sensitivity",
    )
    axes[0].errorbar(
        radius,
        observed,
        yerr=np.array([observed - lower, upper - observed]),
        fmt="o-",
        color="#166a73",
        capsize=3,
        lw=1.2,
        label="Observed stars: source bootstrap 95%",
    )
    axes[0].set(
        xlabel="Aperture radius (arcsec)",
        ylabel="Flux / finite 0.8 arcsec reference",
        title="Curve with catalog-masked background",
        ylim=(0.5, 1.04),
    )
    axes[0].legend(fontsize=7, loc="lower right")
    for index, (masked, color, label_text) in enumerate(
        (
            (False, "#bd7043", "Unmasked background"),
            (True, "#166a73", "Catalog-neighbor-masked background"),
        )
    ):
        selected = [
            r
            for r in report["summaries"]
            if r["reference_background_annulus_arcsec"] == [0.95, 1.35]
            and r["reference_background_neighbor_masked"] == masked
        ]
        x = np.array([r["reference_radius_arcsec"] for r in selected]) + (
            -0.006 if index == 0 else 0.006
        )
        y = np.array([r["median_star_mean_ratio"] for r in selected])
        low = np.array([r["median_source_bootstrap_95"][0] for r in selected])
        high = np.array([r["median_source_bootstrap_95"][1] for r in selected])
        axes[1].errorbar(
            x,
            y,
            yerr=np.array([y - low, high - y]),
            fmt="o-",
            color=color,
            capsize=3,
            lw=1.2,
            label=label_text,
        )
    axes[1].set(
        xlabel="Reference aperture radius (arcsec)",
        ylabel="Science aperture / finite reference",
        title="Same 0.189 arcsec science operator",
        ylim=(0.70, 1.08),
    )
    axes[1].legend(fontsize=7, loc="upper left")
    for axis in axes:
        axis.grid(alpha=0.2)
        axis.tick_params(labelsize=8)
        axis.xaxis.label.set_size(9)
        axis.yaxis.label.set_size(9)
        axis.title.set_size(10)
    fig.suptitle(
        f"M92: {report['selected_star_count']} quality-selected stellar identities, two dependent dithers",
        fontsize=11,
    )
    fig.text(
        0.5,
        0.01,
        "Finite reference is not total flux. Intervals exclude field/model systematics; background choices change the result.",
        ha="center",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.045, 1, 0.94))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--psf-directory", type=Path, default=Path("data_sources/pilot"))
    parser.add_argument("--max-stars", type=int, default=24)
    parser.add_argument(
        "--output", type=Path, default=Path("research_output/m92_aperture_response.json")
    )
    parser.add_argument("--full-output", type=Path)
    parser.add_argument("--plot", type=Path)
    args = parser.parse_args()
    result = run(args.directory, args.psf_directory, maximum_stars=args.max_stars)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(compact(result), indent=2, allow_nan=False) + "\n")
    if args.full_output is not None:
        args.full_output.parent.mkdir(parents=True, exist_ok=True)
        args.full_output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    if args.plot is not None:
        plot_report(result, args.plot)
    print(
        f"Measured {result['selected_star_count']} independent stellar identities in two dependent dithers"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
