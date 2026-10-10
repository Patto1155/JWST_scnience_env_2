"""Bounded neighbor/halo decomposition with spatial prediction and SVD guards.

Signed linear amplitudes are conditional template parameters. Folds partition
pixels of one image; they are not independent observing epochs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from astropy.coordinates import SkyCoord
from scipy.ndimage import gaussian_filter, maximum_filter

from data_pipeline.survivor_deep_data import verify_pinned
from discovery.deep_reference_comparison import load_deep_cutout
from discovery.psf_noise import overlap_resample, read_image, verified_template
from discovery.survivor_deep_model import image_template, stamp
from tools.jwst.flux_calibration import celestial_wcs

ROOT = Path(__file__).resolve().parents[1]
BANDS = ("F090W", "F200W", "F444W")
FAMILIES = (
    ("extended_multineighbor_plane", (0.15,), (0.0,), 1, 0),
    ("extended_multineighbor_halo_quadratic", (0.15,), (0.0, 0.15), 2, 0),
    ("target_core_envelope_multineighbor", (0.0, 0.15), (0.0, 0.15), 2, 0),
    ("target_three_scales_multineighbor", (0.0, 0.10, 0.30), (0.0, 0.15), 2, 0),
    ("target_three_scales_broad_neighbors", (0.0, 0.10, 0.30), (0.0, 0.30), 2, 0),
    ("target_three_scales_rotated_psf", (0.0, 0.10, 0.30), (0.0, 0.15), 2, 90),
)


def svd_fit(design, observations, errors):
    design, observations, errors = map(np.asarray, (design, observations, errors))
    if (
        design.ndim != 2
        or observations.shape != (len(design),)
        or errors.shape != observations.shape
    ):
        raise ValueError("Linear arrays disagree")
    if (
        not np.isfinite(design).all()
        or not np.isfinite(observations).all()
        or not np.isfinite(errors).all()
        or np.any(errors <= 0)
    ):
        raise ValueError("Finite linear arrays and positive errors required")
    weighted = design / errors[:, None]
    norms = np.linalg.norm(weighted, axis=0)
    if np.any(norms == 0):
        raise ValueError("Zero-support model column")
    matrix = weighted / norms
    u, singular, vt = np.linalg.svd(matrix, full_matrices=False)
    if singular[-1] <= singular[0] * 1e-10:
        raise ValueError("Rank-deficient neighborhood model")
    coefficient = (vt.T @ ((u.T @ (observations / errors)) / singular)) / norms
    covariance = ((vt.T / singular**2) @ vt) / np.outer(norms, norms)
    return coefficient, covariance, singular


def fixed_neighbors(data, error, scale, target_offset, halfwidth=2.5, maximum=6):
    """Geometry-only red-guide local maxima, frozen before band coefficients.

    Data-dependent guide positions are not independent source classifications.
    Bright peaks must be 0.25 arcsec from target/other peaks.
    """
    yy, xx = np.mgrid[: len(data), : len(data)] - len(data) // 2
    dx, dy = xx * scale - target_offset[0], yy * scale - target_offset[1]
    smoothed = gaussian_filter(np.where(np.isfinite(data), data, 0), 1.0)
    candidates = smoothed == maximum_filter(smoothed, size=5)
    candidates &= (np.hypot(dx, dy) > 0.25) & (np.hypot(dx, dy) < halfwidth)
    candidates &= np.isfinite(error) & (error > 0) & (smoothed / error > 10)
    rows = np.argwhere(candidates)
    order = np.argsort(smoothed[candidates])[::-1]
    selected = []
    for iy, ix in rows[order]:
        point = (float(dx[iy, ix]), float(dy[iy, ix]))
        if all(np.hypot(point[0] - p[0], point[1] - p[1]) > 0.25 for p in selected):
            selected.append(point)
        if len(selected) >= maximum:
            break
    return selected


def neighborhood_fit(
    data,
    error,
    scale,
    templates,
    labels,
    target_columns,
    halfwidth=2.5,
    degree=2,
    aperture_center=(0.0, 0.0),
):
    yy, xx = np.mgrid[: len(data), : len(data)] - len(data) // 2
    x, y = xx * scale, yy * scale
    valid = (abs(x) <= halfwidth) & (abs(y) <= halfwidth)
    valid &= np.isfinite(data) & np.isfinite(error) & (error > 0)
    columns = [t[valid] for t in templates]
    background = [np.ones(valid.sum()), x[valid], y[valid]]
    if degree == 2:
        background += [x[valid] ** 2, x[valid] * y[valid], y[valid] ** 2]
    design = np.column_stack(columns + background)
    observations, errors = data[valid], error[valid]
    if len(observations) <= 10 * design.shape[1]:
        raise ValueError("Too few neighborhood pixels")
    coefficient, covariance, singular = svd_fit(design, observations, errors)
    residual = (observations - design @ coefficient) / errors
    # Six deterministic held-out spatial-block classes; no independent pixels claim.
    fold = (
        np.floor((x[valid] + halfwidth) / 0.2).astype(int)
        + 2 * np.floor((y[valid] + halfwidth) / 0.2).astype(int)
    ) % 6
    tests = []
    for f in range(6):
        train, test = fold != f, fold == f
        cb, _, _ = svd_fit(design[train], observations[train], errors[train])
        rr = (observations[test] - design[test] @ cb) / errors[test]
        tests.append(
            {
                "fold": f,
                "pixels": int(test.sum()),
                "standardized_rms": float(np.sqrt(np.mean(rr**2))),
            }
        )
    functional = np.zeros(design.shape[1])
    functional[target_columns] = 1
    core = np.hypot(x - aperture_center[0], y - aperture_center[1]) <= 0.2
    aperture_functional = np.zeros(design.shape[1])
    for i in target_columns:
        aperture_functional[i] = templates[i][core].sum()
    sigmas = np.sqrt(np.diag(covariance))
    correlation = covariance / np.outer(sigmas, sigmas)
    target_others = [j for j in range(design.shape[1]) if j not in target_columns]
    maximum_correlation = max(abs(correlation[i, j]) for i in target_columns for j in target_others)
    cv_rms = np.sqrt(
        sum(t["standardized_rms"] ** 2 * t["pixels"] for t in tests)
        / sum(t["pixels"] for t in tests)
    )
    return {
        "pixels": int(valid.sum()),
        "parameters": int(design.shape[1]),
        "signed_component_coefficients_njy": dict(
            zip(labels, coefficient[: len(labels)].tolist(), strict=True)
        ),
        "signed_component_covariance_njy2": covariance[: len(labels), : len(labels)].tolist(),
        "signed_target_template_total_njy": float(functional @ coefficient),
        "target_total_diagonal_error_njy": float(np.sqrt(functional @ covariance @ functional)),
        "selection_centered_target_template_aperture_0p2_njy": float(
            aperture_functional @ coefficient
        ),
        "selection_centered_target_aperture_diagonal_error_njy": float(
            np.sqrt(aperture_functional @ covariance @ aperture_functional)
        ),
        "normalized_design_condition": float(singular[0] / singular[-1]),
        "maximum_target_nuisance_parameter_correlation": float(maximum_correlation),
        "train_standardized_rms": float(np.sqrt(np.mean(residual**2))),
        "heldout_standardized_rms": float(cv_rms),
        "spatial_block_folds": tests,
        "conditional_predictive_gate_pass": bool(cv_rms <= 2),
        "scope": (
            "Same-image spatial prediction; diagonal errors are not a calibrated "
            "covariance/coverage model"
        ),
    }


def run_source(source_id, coordinate, products, directory, psf_directory, *, target_shape):
    inputs, bundles = [], {}
    for pin in products:
        path = directory / pin["filename"]
        if pin.get("kind") == "native_image":
            receipt = {
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            if receipt["bytes"] != pin["expected_bytes"] or receipt["sha256"] != pin["sha256"]:
                raise ValueError("Native image differs from frozen input inventory")
            bundle = read_image(path)
            bundle["wcs"] = celestial_wcs(bundle)
            provenance = {"contributors": [path.name.replace("_i2d", "_uncal")]}
            provenance["contributor_status"] = (
                "Filename-inferred singleton with primary NDRIZ checked; association "
                "members not separately acquired"
            )
            if bundle["primary_header"].get("NDRIZ") != 1:
                raise ValueError("Expected a singleton native image product")
        else:
            receipt = verify_pinned(path, pin)
            bundle, provenance = load_deep_cutout(path)
        bundles[pin["filter"]] = bundle
        inputs.append(
            {
                "filter": pin["filter"],
                "sha256": receipt["sha256"],
                "bytes": receipt["bytes"],
                "contributors": provenance["contributors"],
                "contributor_status": provenance.get(
                    "contributor_status", "Actual FLT contributor names read from mosaic header"
                ),
            }
        )
    guide_band = "F200W"
    guide = bundles[guide_band]
    guide_scale = float(np.sqrt(abs(np.linalg.det(guide["wcs"].pixel_scale_matrix))) * 3600)
    guide_half = int(np.ceil(3.0 / guide_scale))
    guide_data, guide_error, _, guide_phase = stamp(guide, *coordinate, guide_half)
    target_offset = (guide_phase[0] + target_shape[0], guide_phase[1] + target_shape[1])
    neighbors = fixed_neighbors(guide_data, guide_error, guide_scale, target_offset)
    guide_x, guide_y = map(float, guide["wcs"].world_to_pixel(SkyCoord(*coordinate, unit="deg")))
    target_sky = guide["wcs"].pixel_to_world(
        guide_x + target_shape[0] / guide_scale, guide_y + target_shape[1] / guide_scale
    )
    neighbor_sky = [
        guide["wcs"].pixel_to_world(
            guide_x + (target_shape[0] + dx) / guide_scale,
            guide_y + (target_shape[1] + dy) / guide_scale,
        )
        for dx, dy in neighbors
    ]
    results = []
    for band in BANDS:
        bundle = bundles[band]
        scale = float(np.sqrt(abs(np.linalg.det(bundle["wcs"].pixel_scale_matrix))) * 3600)
        half = int(np.ceil(3.0 / scale))
        data, error, _, phase = stamp(bundle, *coordinate, half)
        selection_x, selection_y = map(
            float, bundle["wcs"].world_to_pixel(SkyCoord(*coordinate, unit="deg"))
        )
        target_x, target_y = map(float, bundle["wcs"].world_to_pixel(target_sky))
        target_center = (
            (target_x - round(selection_x)) * scale,
            (target_y - round(selection_y)) * scale,
        )
        neighbor_centers = []
        for sky in neighbor_sky:
            nx, ny = map(float, bundle["wcs"].world_to_pixel(sky))
            neighbor_centers.append(
                ((nx - round(selection_x)) * scale, (ny - round(selection_y)) * scale)
            )
        psf_pin = next(
            p
            for p in json.loads((ROOT / "data_sources/survivor_deep/manifest.json").read_text())[
                "products"
            ]
            if p.get("kind") == "modeled_finite_psf" and p["filter"] == band
        )
        psf_path = psf_directory / psf_pin["filename"]
        verify_pinned(psf_path, psf_pin)
        kernel, provenance = verified_template(psf_path, band)
        finite_psf = overlap_resample(kernel, provenance["input_scale_arcsec"], scale, 2 * half + 1)
        for name, target_scales, neighbor_scales, degree, rotation in FAMILIES:
            psf = np.rot90(finite_psf) if rotation else finite_psf
            templates, labels = [], []
            for sigma in target_scales:
                templates.append(
                    image_template(
                        psf,
                        scale,
                        np.array([*target_center, sigma, target_shape[2], target_shape[3]]),
                    )
                )
                labels.append(f"target_sigma{sigma}")
            target_columns = list(range(len(templates)))
            for n, (dx, dy) in enumerate(neighbor_centers):
                for sigma in neighbor_scales:
                    templates.append(image_template(psf, scale, np.array([dx, dy, sigma, 1, 0])))
                    labels.append(f"neighbor{n}_sigma{sigma}")
            result = neighborhood_fit(
                data,
                error,
                scale,
                templates,
                labels,
                target_columns,
                degree=degree,
                aperture_center=phase,
            )
            results.append({"filter": band, "family": name, **result})
    decisions = []
    for band in BANDS:
        rows = [r for r in results if r["filter"] == band]
        accepted = [r for r in rows if r["conditional_predictive_gate_pass"]]
        decision = {
            "filter": band,
            "families_passing": len(accepted),
            "minimum_heldout_standardized_rms": min(r["heldout_standardized_rms"] for r in rows),
        }
        if accepted:
            flux = np.array([r["signed_target_template_total_njy"] for r in accepted])
            tolerance = max(
                0.2 * abs(float(np.median(flux))),
                2 * max(r["target_total_diagonal_error_njy"] for r in accepted),
            )
            decision.update(
                accepted_family_flux_excursion_njy=float(np.ptp(flux)),
                stability_tolerance_njy=tolerance,
                stable_target_under_accepted_templates=bool(
                    len(accepted) >= 2 and np.ptp(flux) <= tolerance
                ),
            )
        else:
            decision["stable_target_under_accepted_templates"] = False
        decision["classification_decision"] = (
            "stop: residual/model or component instability unresolved"
        )
        decisions.append(decision)
    return {
        "source_id": source_id,
        "sky_deg": list(coordinate),
        "inputs": inputs,
        "guide_band": guide_band,
        "data_selected_neighbor_offsets_from_target_arcsec": neighbors,
        "target_sky_deg": [float(target_sky.ra.deg), float(target_sky.dec.deg)],
        "neighbor_sky_deg": [[float(s.ra.deg), float(s.dec.deg)] for s in neighbor_sky],
        "fixed_target_offset_arcsec_and_axis_ratio_angle": list(target_shape),
        "fits": results,
        "decisions": decisions,
    }


def run(deep_directory, originals_directory, output):
    start = perf_counter()
    deep = json.loads((ROOT / "data_sources/survivor_deep/manifest.json").read_text())
    products = [p for p in deep["products"] if p.get("source_id") == 98 and p["filter"] in BANDS]
    sources = [
        run_source(
            98,
            (products[0]["ra_deg"], products[0]["dec_deg"]),
            products,
            deep_directory,
            deep_directory,
            target_shape=(
                0.09083655354402044,
                0.06991672127757008,
                0.39506235376392224,
                0.8056694252761015,
            ),
        )
    ]
    smacs = json.loads(
        (ROOT / "data_sources/original_images_round3_matched_smacs.json").read_text()
    )["images"]
    native = []
    for band in BANDS:
        pin = next(
            p
            for p in smacs
            if p["filter"] == band
            and "jw02736" in p["id"]
            and (band != "F200W" or p["id"] == "jw02736001001_02105_00004_nrca1_i2d.fits")
        )
        native.append({**pin, "filename": pin["product_filename"], "kind": "native_image"})
    missing = [p["filename"] for p in native if not (originals_directory / p["filename"]).exists()]
    if missing:
        sources.append(
            {
                "source_id": 1043,
                "status": "bounded_experiment_waiting_pinned_original_pixels",
                "required_missing_filenames": missing,
                "classification_decision": (
                    "stop classification; prior patch/background ambiguity retained"
                ),
            }
        )
    else:
        sources.append(
            run_source(
                1043,
                (110.63858928243717, -73.48487214542632),
                native,
                originals_directory,
                deep_directory,
                target_shape=(0.0, 0.0, 1.0, 0.0),
            )
        )
    report = {
        "schema_version": 1,
        "starting_revision": "bc7abf0",
        "question": (
            "Do broader neighbor/halo models produce identifiable fluxes and "
            "held-out spatial predictions?"
        ),
        "design": {
            "families": 6,
            "bands": list(BANDS),
            "guide_neighbor_limit": 6,
            "guide_neighbor_minimum_separation_arcsec": 0.25,
            "guide_peak_minimum_smoothed_pixel_snr": 10,
            "fit_halfwidth_arcsec": 2.5,
            "heldout_spatial_block_width_arcsec": 0.2,
            "folds": 6,
            "predictive_rms_gate": 2,
            "stable_flux_relative_tolerance": 0.2,
            "stable_flux_diagonal_error_multiple": 2,
            "stopping": (
                "Stop classification when no family predicts held-out pixels or accepted "
                "component assignment is unstable"
            ),
        },
        "new_selected_input_bytes": 0,
        "input_manifest_hashes": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "data_sources/survivor_deep/manifest.json",
                "data_sources/original_images_round3_matched_smacs.json",
                "research_output/survivor_deep_model.json",
            )
        },
        "analysis_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "runtime_s": perf_counter() - start,
        "sources": sources,
        "limits": [
            (
                "No empirical PSF calibration; JADES modeled PSF transport/orientation "
                "remains conditional"
            ),
            (
                "Guide geometry selected from F200 same scene, not a "
                "completeness-controlled neighbor catalog"
            ),
            (
                "Spatial folds share one image and are not independent exposures; "
                "correlated noise can change RMS interpretation"
            ),
            (
                "F200 guide geometry and inherited F444 source98 shape used pixels "
                "before amplitude-fold assignment: conditional amplitude prediction, not "
                "unbiased end-to-end cross-validation"
            ),
            (
                "Signed component sums and excursions are template sensitivities, not "
                "physical totals or confidence intervals"
            ),
            (
                "No likelihood pooling with previous extractions; source "
                "identity/redshift unestablished"
            ),
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deep-directory", type=Path, required=True)
    parser.add_argument("--originals-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.deep_directory, args.originals_directory, args.output)


if __name__ == "__main__":
    main()
