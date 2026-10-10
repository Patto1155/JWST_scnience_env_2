"""Independent QR audit of frozen actual-pixel candidate neighborhood families."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from scipy.ndimage import gaussian_filter, map_coordinates, maximum_filter
from scipy.signal import fftconvolve

from discovery.deep_reference_comparison import load_deep_cutout
from discovery.psf_noise import read_image
from discovery.research2_medium_review import sha
from discovery.survivor_deep_model import stamp
from tools.jwst.flux_calibration import celestial_wcs

FAMILIES = (
    ((0.15,), (0.0,), 1, 0),
    ((0.15,), (0.0, 0.15), 2, 0),
    ((0.0, 0.15), (0.0, 0.15), 2, 0),
    ((0.0, 0.10, 0.30), (0.0, 0.15), 2, 0),
    ((0.0, 0.10, 0.30), (0.0, 0.30), 2, 0),
    ((0.0, 0.10, 0.30), (0.0, 0.15), 2, 90),
)


def qr_fit(design, data, error):
    weighted = design / error[:, None]
    q, r = np.linalg.qr(weighted, mode="reduced")
    coefficient = np.linalg.solve(r, q.T @ (data / error))
    inverse = np.linalg.solve(r, np.eye(len(r)))
    return coefficient, inverse @ inverse.T


def image(psf, scale, center, sigma, axis, angle):
    size = len(psf)
    y, x = np.mgrid[:size, :size] - size // 2
    if sigma:
        major, minor = x * np.cos(angle) + y * np.sin(angle), -x * np.sin(angle) + y * np.cos(angle)
        gaussian = np.exp(
            -0.5 * ((major * scale / sigma) ** 2 + (minor * scale / sigma / axis) ** 2)
        )
        gaussian /= gaussian.sum()
        profile = fftconvolve(psf, gaussian, mode="same")
    else:
        profile = psf
    return map_coordinates(
        profile,
        [y + size // 2 - center[1] / scale, x + size // 2 - center[0] / scale],
        order=1,
        mode="constant",
        cval=0,
    )


def angular_psf(path, scale, size):
    with fits.open(path) as hdul:
        hdu = next(h for h in hdul if h.data is not None and h.data.ndim == 2)
        raw = np.asarray(hdu.data, float)
        old_scale = float(hdu.header["PIXELSCL"])
    raw /= raw.sum()
    old = (np.arange(len(raw)) - (len(raw) - 1) / 2) * old_scale
    new = (np.arange(size) - size // 2) * scale
    widths = (
        np.maximum(
            0,
            np.minimum(new[:, None] + scale / 2, old[None, :] + old_scale / 2)
            - np.maximum(new[:, None] - scale / 2, old[None, :] - old_scale / 2),
        )
        / old_scale
    )
    return widths @ raw @ widths.T


def audit(root, deep, originals):
    artifact = root / "research_output/candidate_neighborhood_v1.json"
    frozen_hash = "10e74e8bd2c0b33b0a0e67927189580d5ac1e98561a6822924d8ed8b93a0b973"
    if sha(artifact) != frozen_hash:
        raise ValueError("Frozen 2b050c0 artifact changed")
    saved = json.loads(artifact.read_text())
    manifest = json.loads((root / "data_sources/survivor_deep/manifest.json").read_text())[
        "products"
    ]
    native = json.loads(
        (root / "data_sources/original_images_round3_matched_smacs.json").read_text()
    )["images"]
    checked = {}
    reviews = []
    for source in saved["sources"]:
        sky = SkyCoord(*source["sky_deg"], unit="deg")
        bundles = {}
        for item in source["inputs"]:
            band = item["filter"]
            if source["source_id"] == 98:
                pin = next(p for p in manifest if p.get("source_id") == 98 and p["filter"] == band)
                path = deep / pin["filename"]
                bundles[band] = load_deep_cutout(path)[0]
            else:
                pin = next(p for p in native if p["sha256"] == item["sha256"])
                path = originals / pin["product_filename"]
                bundles[band] = read_image(path)
                bundles[band]["wcs"] = celestial_wcs(bundles[band])
                if bundles[band]["primary_header"]["NDRIZ"] != 1:
                    raise ValueError("Native contributor assumption differs")
            if sha(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
                raise ValueError("Actual pixels differ from frozen identity")
            checked[path.name] = item["sha256"]
        guide = bundles["F200W"]
        scale = float(np.sqrt(abs(np.linalg.det(guide["wcs"].pixel_scale_matrix))) * 3600)
        data, error, _, phase = stamp(guide, *source["sky_deg"], int(np.ceil(3 / scale)))
        dx, dy, axis, angle = source["fixed_target_offset_arcsec_and_axis_ratio_angle"]
        y, x = np.mgrid[: len(data), : len(data)] - len(data) // 2
        offsets = (x * scale - phase[0] - dx, y * scale - phase[1] - dy)
        smoothed = gaussian_filter(np.where(np.isfinite(data), data, 0), 1)
        radius = np.hypot(*offsets)
        candidates = (
            (smoothed == maximum_filter(smoothed, size=5))
            & (radius > 0.25)
            & (radius < 2.5)
            & np.isfinite(error)
            & (error > 0)
            & (smoothed / error > 10)
        )
        rows = sorted(np.argwhere(candidates), key=lambda rc: smoothed[tuple(rc)], reverse=True)
        neighbors = []
        for row in rows:
            point = np.array([offsets[0][tuple(row)], offsets[1][tuple(row)]])
            if all(np.linalg.norm(point - other) > 0.25 for other in neighbors):
                neighbors.append(point)
            if len(neighbors) == 6:
                break
        if not np.allclose(
            neighbors, source["data_selected_neighbor_offsets_from_target_arcsec"], atol=1e-12
        ):
            raise ValueError("Independent guide peak geometry differs")
        gx, gy = map(float, guide["wcs"].world_to_pixel(sky))
        target_sky = guide["wcs"].pixel_to_world(gx + dx / scale, gy + dy / scale)
        neighbor_sky = [
            guide["wcs"].pixel_to_world(gx + (dx + n[0]) / scale, gy + (dy + n[1]) / scale)
            for n in neighbors
        ]
        differences = []
        for band in ("F090W", "F200W", "F444W"):
            bundle = bundles[band]
            scale = float(np.sqrt(abs(np.linalg.det(bundle["wcs"].pixel_scale_matrix))) * 3600)
            half = int(np.ceil(3 / scale))
            data, error, _, phase = stamp(bundle, *source["sky_deg"], half)
            sx, sy = map(float, bundle["wcs"].world_to_pixel(sky))
            centers = [
                tuple(
                    (float(v) - base) * scale
                    for v, base in zip(
                        bundle["wcs"].world_to_pixel(s), (round(sx), round(sy)), strict=True
                    )
                )
                for s in [target_sky] + neighbor_sky
            ]
            psf_pin = next(
                p for p in manifest if p.get("kind") == "modeled_finite_psf" and p["filter"] == band
            )
            path = deep / psf_pin["filename"]
            if sha(path) != psf_pin["sha256"]:
                raise ValueError("PSF identity differs")
            checked[path.name] = psf_pin["sha256"]
            psf = angular_psf(path, scale, len(data))
            y, x = np.mgrid[: len(data), : len(data)] - len(data) // 2
            x, y = x * scale, y * scale
            mask = (
                (abs(x) <= 2.5)
                & (abs(y) <= 2.5)
                & np.isfinite(data)
                & np.isfinite(error)
                & (error > 0)
            )
            observations, errors = data[mask], error[mask]
            for saved_fit, (target_scales, neighbor_scales, degree, rotation) in zip(
                [r for r in source["fits"] if r["filter"] == band], FAMILIES, strict=True
            ):
                local_psf = psf if rotation == 0 else psf.T[::-1]
                templates = [
                    image(local_psf, scale, centers[0], sigma, axis, angle)
                    for sigma in target_scales
                ]
                for center in centers[1:]:
                    templates.extend(
                        image(local_psf, scale, center, sigma, 1, 0) for sigma in neighbor_scales
                    )
                background = [np.ones(mask.sum()), x[mask], y[mask]]
                if degree == 2:
                    background.extend([x[mask] ** 2, x[mask] * y[mask], y[mask] ** 2])
                design = np.column_stack([t[mask] for t in templates] + background)
                coefficient, covariance = qr_fit(design, observations, errors)
                n, nt = len(templates), len(target_scales)
                function = np.zeros(len(coefficient))
                function[:nt] = 1
                core = np.hypot(x - phase[0], y - phase[1]) <= 0.2
                aperture = np.zeros(len(coefficient))
                aperture[:nt] = [t[core].sum() for t in templates[:nt]]
                fold = (
                    np.floor((x[mask] + 2.5) / 0.2).astype(int)
                    + 2 * np.floor((y[mask] + 2.5) / 0.2).astype(int)
                ) % 6
                rms = []
                for f in range(6):
                    train, test = fold != f, fold == f
                    beta, _ = qr_fit(design[train], observations[train], errors[train])
                    residual = (observations[test] - design[test] @ beta) / errors[test]
                    rms.append(float(np.sqrt(np.mean(residual**2))))
                weighted = design / errors[:, None]
                condition = float(np.linalg.cond(weighted / np.linalg.norm(weighted, axis=0)))
                correlation = covariance / np.sqrt(
                    np.outer(np.diag(covariance), np.diag(covariance))
                )
                maxcor = float(np.max(abs(correlation[:nt, nt:])))
                checks = {
                    "coefficients_max_abs_njy": np.max(
                        abs(
                            coefficient[:n]
                            - list(saved_fit["signed_component_coefficients_njy"].values())
                        )
                    ),
                    "covariance_max_abs_njy2": np.max(
                        abs(covariance[:n, :n] - saved_fit["signed_component_covariance_njy2"])
                    ),
                    "fold_rms_max_abs": np.max(
                        abs(
                            np.array(rms)
                            - [r["standardized_rms"] for r in saved_fit["spatial_block_folds"]]
                        )
                    ),
                    "total_abs_njy": abs(
                        function @ coefficient - saved_fit["signed_target_template_total_njy"]
                    ),
                    "total_sigma_abs_njy": abs(
                        np.sqrt(function @ covariance @ function)
                        - saved_fit["target_total_diagonal_error_njy"]
                    ),
                    "aperture_abs_njy": abs(
                        aperture @ coefficient
                        - saved_fit["selection_centered_target_template_aperture_0p2_njy"]
                    ),
                    "aperture_sigma_abs_njy": abs(
                        np.sqrt(aperture @ covariance @ aperture)
                        - saved_fit["selection_centered_target_aperture_diagonal_error_njy"]
                    ),
                    "condition_abs": abs(condition - saved_fit["normalized_design_condition"]),
                    "correlation_abs": abs(
                        maxcor - saved_fit["maximum_target_nuisance_parameter_correlation"]
                    ),
                }
                if max(checks.values()) > 1e-6:
                    raise ValueError(f"Independent QR/template audit differs: {band} {checks}")
                differences.append(
                    {
                        "band": band,
                        "family": saved_fit["family"],
                        "checks": {k: float(v) for k, v in checks.items()},
                    }
                )
        decisions = []
        for band in ("F090W", "F200W", "F444W"):
            rows = [r for r in source["fits"] if r["filter"] == band]
            passing = [r for r in rows if r["heldout_standardized_rms"] <= 2]
            decision = next(d for d in source["decisions"] if d["filter"] == band)
            if len(passing) != decision["families_passing"]:
                raise ValueError("Conditional gate tally differs")
            decisions.append(
                {
                    "band": band,
                    "passing_families": len(passing),
                    "minimum_rms": min(r["heldout_standardized_rms"] for r in rows),
                }
            )
        reviews.append(
            {
                "source_id": source["source_id"],
                "fits": differences,
                "decisions": decisions,
                "maximum_normalized_condition": max(
                    r["normalized_design_condition"] for r in source["fits"]
                ),
                "maximum_target_nuisance_correlation": max(
                    r["maximum_target_nuisance_parameter_correlation"] for r in source["fits"]
                ),
            }
        )
    return {
        "schema_version": 1,
        "frozen_author_commit": "2b050c0ae6f574944f7681b1f24a1eb7f18e588f",
        "frozen_artifact_sha256": frozen_hash,
        "checked_input_sha256": checked,
        "sources": reviews,
        "review_code_sha256": sha(Path(__file__)),
        "approval": (
            "Approved conditional numerical decomposition and stopping decisions; "
            "no identity or calibrated coverage claim"
        ),
        "independence": (
            "No candidate_neighborhood imports. Independent finite-PSF overlap "
            "integration, coordinate-map templates and unnormalized QR rather than author "
            "normalized SVD. Shared previously reviewed input loader/stamp calibration only."
        ),
        "limitations": [
            (
                "Diagonal conditional covariance; residual inadequacy can reflect "
                "model and noise errors"
            ),
            (
                "Guide and inherited source98 shape predate folds; same-image amplitude "
                "prediction is not unbiased pipeline cross-validation"
            ),
            (
                "Failed-model coefficient ranges are not astrophysical flux intervals; "
                "weak blue98 coefficient admits zero"
            ),
            (
                "Well-conditioned design does not guarantee scientific component "
                "identifiability; classification stops for both candidates"
            ),
        ],
        "new_download_bytes": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "deep", "originals", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(audit(args.root, args.deep, args.originals), indent=2, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    main()
