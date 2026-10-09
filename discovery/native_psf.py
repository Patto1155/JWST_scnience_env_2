"""Native-grid unresolved-source PSF response and blank-sky masking sensitivity.

Built on the merged PSF/noise estimator. Modeled responses quantify instrumental
aperture sensitivity; they do not assign any observed galaxy a point-source SED.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from astropy.coordinates import SkyCoord

from data_pipeline.research_sources import fetch_product
from discovery.psf_noise import (
    DEFAULT_PHASES,
    _summarize_blanks,
    blank_aperture_report,
    overlap_resample,
    read_image,
    source_mask,
    verified_template,
)
from tools.jwst.flux_calibration import celestial_wcs, flux_density_factors

RADIUS = 0.18873807945080867
ANNULUS = (0.37747615890161734, 0.6291269315026955)
PRODUCTS = Path("data_sources/native_psf_products.json")


def fetch_templates(directory: Path) -> list[dict[str, Any]]:
    """Fetch the two newly needed PSFs, bounded and pinned in a source inventory."""
    rows = json.loads(PRODUCTS.read_text())["products"]
    receipts = []
    for row in rows:
        destination = directory / row["filename"]
        if not destination.exists():
            fetch_product(row, destination, max_bytes=5 * 1024 * 1024)
        _, provenance = verified_template(destination, row["filter"])
        if provenance["sha256"] != row["sha256"]:
            raise ValueError("cached PSF differs from pinned inventory")
        receipts.append(provenance)
    return receipts


def native_response(
    template: np.ndarray,
    *,
    input_scale: float,
    output_scale: float,
    phase: tuple[float, float],
    radius: float = RADIUS,
    annulus: tuple[float, float] = ANNULUS,
    geometry: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None,
) -> dict[str, float]:
    """Net response of the production binary-aperture/mean-SCI-annulus operator.

    Template pixels represent discrete integrated flux fractions. The native
    output image is resampled by pixel-overlap integration without renormalizing
    its bounded crop. Optional (ap, ann, Jy/raw factors) supplies actual spherical
    WCS geometry and local surface-brightness conversion at one source position.
    """
    if (
        not np.all(np.isfinite([input_scale, output_scale, *phase, radius, *annulus]))
        or not 0 < radius < annulus[0] < annulus[1]
        or min(input_scale, output_scale) <= 0
        or max(abs(p) for p in phase) > 0.5
    ):
        raise ValueError("invalid native aperture geometry")
    template = np.asarray(template, float)
    if (
        template.ndim != 2
        or any(n % 2 == 0 for n in template.shape)
        or not np.isfinite(template).all()
        or np.any(template < 0)
    ):
        raise ValueError("native response requires finite nonnegative odd 2D template")
    size = 2 * int(np.ceil(annulus[1] / output_scale + 2)) + 1
    half_input = int(np.ceil((annulus[1] + 3 * output_scale) / input_scale)) + 1
    middle = np.array(template.shape) // 2
    if np.any(middle < half_input):
        raise ValueError("PSF finite template does not contain the required annulus")
    crop = template[
        middle[0] - half_input : middle[0] + half_input + 1,
        middle[1] - half_input : middle[1] + half_input + 1,
    ]
    image = overlap_resample(crop, input_scale, output_scale, size, phase)
    if geometry is None:
        yy, xx = np.mgrid[:size, :size] - size // 2
        distance = np.hypot(xx - phase[0], yy - phase[1]) * output_scale
        ap = distance <= radius
        ann = (distance >= annulus[0]) & (distance <= annulus[1])
        factors = np.ones(image.shape)
    else:
        ap, ann, factors = geometry
        if any(np.shape(value) != image.shape for value in geometry):
            raise ValueError("native geometry arrays have inconsistent shapes")
    if (
        not np.any(ap)
        or not np.any(ann)
        or not np.isfinite(factors[ap | ann]).all()
        or np.any(factors[ap | ann] <= 0)
    ):
        raise ValueError("invalid aperture/annulus/factor values")
    ee = float(image[ap].sum())
    ann_energy = float(image[ann].sum())
    background_response = float(np.mean(image[ann] / factors[ann]) * factors[ap].sum())
    response = ee - background_response
    if not np.isfinite(response) or response <= 0:
        raise ValueError("nonpositive modeled response")
    return {
        "encircled_energy": ee,
        "annulus_energy": ann_energy,
        "annulus_subtraction_response": background_response,
        "net_response": response,
        "total_flux_multiplier": 1 / response,
        "n_aperture_pixels": int(ap.sum()),
        "n_annulus_pixels": int(ann.sum()),
    }


def source_geometry(
    bundle: dict[str, Any],
    x: float,
    y: float,
    *,
    radius: float = RADIUS,
    annulus: tuple[float, float] = ANNULUS,
) -> tuple[float, tuple[float, float], tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Use actual celestial separation and local Jy conversion, never detector labels."""
    wcs = celestial_wcs(bundle)
    if wcs is None:
        raise ValueError("native science image requires celestial WCS")
    scales = np.linalg.svd(wcs.pixel_scale_matrix, compute_uv=False) * 3600
    scale = float(np.sqrt(np.prod(scales)))
    if max(scales) / min(scales) > 1.001:
        raise ValueError("anisotropic grid requires general 2D PSF area resampling")
    size = 2 * int(np.ceil(annulus[1] / scale + 2)) + 1
    yy, xx = np.mgrid[:size, :size] - size // 2
    integer_x, integer_y = int(np.round(x)), int(np.round(y))
    world = wcs.pixel_to_world(xx + integer_x, yy + integer_y)
    distance = world.separation(wcs.pixel_to_world(x, y)).arcsec
    ap = distance <= radius
    ann = (distance >= annulus[0]) & (distance <= annulus[1])
    # Match the production flux mask: finite SCI and positive finite WHT.
    # ERR validates uncertainty separately and must not redefine measured flux.
    if "sci" in bundle:
        science = np.asarray(bundle["sci"])
        gx, gy = xx + integer_x, yy + integer_y
        inside = (gx >= 0) & (gy >= 0) & (gx < science.shape[1]) & (gy < science.shape[0])
        valid = np.zeros(ap.shape, bool)
        valid[inside] = np.isfinite(science[gy[inside], gx[inside]])
        if bundle.get("wht") is not None:
            weights = np.asarray(bundle["wht"])[gy[inside], gx[inside]]
            valid[inside] &= np.isfinite(weights) & (weights > 0)
        if bundle.get("validity_mask") is not None:
            valid[inside] &= np.asarray(bundle["validity_mask"], bool)[gy[inside], gx[inside]]
        ap &= valid
        ann &= valid
    conversion = flux_density_factors(bundle, xx + integer_x, yy + integer_y)
    if conversion["status"] != "calibrated":
        raise ValueError("source geometry requires physically calibrated image")
    return scale, (float(x - integer_x), float(y - integer_y)), (ap, ann, conversion["factor_jy"])


def _quantiles(values: list[float]) -> list[float]:
    return [float(v) for v in np.quantile(values, [0, 0.16, 0.5, 0.84, 1])] if values else []


def native_report(
    directory: Path,
    manifest_path: Path,
    catalog_path: Path,
    *,
    radius: float = RADIUS,
    annulus: tuple[float, float] = ANNULUS,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads(manifest_path.read_text())
    with catalog_path.open() as stream:
        sources = list(csv.DictReader(stream))
    result: dict[str, Any] = {
        "experiment": "native-grid modeled point-source response",
        "model_not_observed": True,
        "radius_arcsec": radius,
        "annulus_radii_arcsec": annulus,
        "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "images_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "phase_grid_pixels": DEFAULT_PHASES,
        "filters": [],
        "differential_color_summary": [],
        "limits": [
            "JADES modeled PSFs are not observed stars in these original exposures.",
            "Input/output PSF axes are aligned; rotation/field/visit/template uncertainty remains.",
            "Nine sampled phases give sensitivity values, not a confidence interval or exhaustive bound.",
            "Output grid locally isotropic; spherical WCS masks and Jy conversion are evaluated per source.",
            "No galaxy morphology/extension model: these values must not silently correct extended-source colors.",
            "Current stored astrometry is used; any independently measured offset must be resolved separately.",
            "Finite supplied template defines total; unknown more distant wings are not measured.",
        ],
    }
    records = []
    filename = {"F090W": "f090w", "F200W": "f200w", "F444W": "f444wa"}
    for band in filename:
        selected = next(row for row in manifest["images"] if row["filter"] == band)
        path = Path(selected["path"])
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        if checksum != selected["sha256"]:
            raise ValueError("image bytes differ from manifest")
        bundle = read_image(path)
        bundle["wcs"] = celestial_wcs(bundle)
        template, provenance = verified_template(
            directory / f"{filename[band]}_v5.0_mpsf.fits", band
        )
        # Same current grid at the image centre for the fixed phase diagnostic.
        height, width = bundle["sci"].shape
        scale, _, _ = source_geometry(bundle, width / 2, height / 2, radius=radius, annulus=annulus)
        phases = [
            {
                "phase": phase,
                **native_response(
                    template,
                    input_scale=provenance["input_scale_arcsec"],
                    output_scale=scale,
                    phase=phase,
                    radius=radius,
                    annulus=annulus,
                ),
            }
            for phase in DEFAULT_PHASES
        ]
        band_records = []
        for source in sources:
            flux_field = source.get(f"{band}_flux", "")
            if (
                not flux_field
                or not np.isfinite(float(flux_field))
                or float(source.get(f"{band}_coverage", 0)) < 0.9
            ):
                continue
            coordinate = SkyCoord(float(source["ra"]), float(source["dec"]), unit="deg")
            x, y = bundle["wcs"].world_to_pixel(coordinate)
            scale, phase, geometry = source_geometry(
                bundle, float(x), float(y), radius=radius, annulus=annulus
            )
            response = native_response(
                template,
                input_scale=provenance["input_scale_arcsec"],
                output_scale=scale,
                phase=phase,
                radius=radius,
                annulus=annulus,
                geometry=geometry,
            )
            band_records.append(
                {
                    "source_id": source["source_id"],
                    "band": band,
                    "x": float(x),
                    "y": float(y),
                    "phase_x": phase[0],
                    "phase_y": phase[1],
                    "response": response["net_response"],
                    "total_pointsource_multiplier": response["total_flux_multiplier"],
                    "aperture_pixels": response["n_aperture_pixels"],
                    "annulus_pixels": response["n_annulus_pixels"],
                    "modeled_not_observed": True,
                }
            )
        records.extend(band_records)
        result["filters"].append(
            {
                "filter": band,
                "provenance": provenance,
                "image_sha256": checksum,
                "image_filename": path.name,
                "native_pixel_scale_arcsec": scale,
                "nine_sampled_phases": phases,
                "source_count": len(band_records),
                "actual_source_response_quantiles_0_16_50_84_100": _quantiles(
                    [r["response"] for r in band_records]
                ),
                "actual_source_multiplier_quantiles_0_16_50_84_100": _quantiles(
                    [r["total_pointsource_multiplier"] for r in band_records]
                ),
            }
        )
    source_groups: dict[str, dict[str, Any]] = {}
    for record in records:
        source_groups.setdefault(record["source_id"], {})[record["band"]] = record
    for blue in ("F090W", "F200W"):
        biases = [
            -2.5 * np.log10(row[blue]["response"] / row["F444W"]["response"])
            for row in source_groups.values()
            if blue in row and "F444W" in row
        ]
        result["differential_color_summary"].append(
            {
                "bands": [blue, "F444W"],
                "matched_sources": len(biases),
                "aperture_minus_total_color_quantiles_0_16_50_84_100": _quantiles(biases),
                "correction": "subtract modeled bias only under unresolved-source assumption",
            }
        )
    return result, records


def compact_noise(report: dict[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(report)
    for row in output["apertures"]:
        measurements = row.pop("measurements")
        canonical = json.dumps(measurements, sort_keys=True, separators=(",", ":"), allow_nan=False)
        row["regenerable_blank_measurements"] = {
            "count": len(measurements),
            "canonical_json_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        }
        row.pop("spatial_blocks", None)
    return output


def noise_mask_sensitivity(
    manifest_path: Path, *, radius: float = RADIUS, annulus: tuple[float, float] = ANNULUS
) -> dict[str, Any]:
    """Evaluate source-mask/dilation and bootstrap-block choices on the same sky."""
    manifest = json.loads(manifest_path.read_text())
    result = {
        "experiment": "conditional mask and block-size sensitivity",
        "images": [],
        "seed": 731,
        "radius_arcsec": radius,
        "annulus_radii_arcsec": annulus,
        "robust_vs_ordinary": "both retained; neither yields validated tail probability",
        "limits": [
            "Mask thresholds select different sky subsets; intervals are conditional on each subset.",
            "Robust MAD and standard deviation estimate different aspects of non-Gaussian residuals.",
            "Disjoint footprints do not remove longer-range or whole-field dependence.",
        ],
    }
    for band in ("F090W", "F200W", "F444W"):
        selected = next(r for r in manifest["images"] if r["filter"] == band)
        path = Path(selected["path"])
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        if checksum != selected["sha256"]:
            raise ValueError("image checksum mismatch")
        bundle = read_image(path)
        bundle["wcs"] = celestial_wcs(bundle)
        image = bundle["sci"]
        valid = np.isfinite(image) & np.isfinite(bundle["wht"]) & (bundle["wht"] > 0)
        valid &= np.isfinite(bundle["err"]) & (bundle["err"] > 0)
        scales = np.linalg.svd(bundle["wcs"].pixel_scale_matrix, compute_uv=False) * 3600
        scale = float(min(scales))
        # Match the merged first-round mask, which protected the largest .31456arcsec aperture.
        base_dilation = int(np.ceil(0.31456346575134775 / scale)) + 2
        aperture_dilation = int(np.ceil(radius / scale)) + 2
        variations = []
        for threshold, dilation in (
            (3.0, base_dilation),
            (4.0, base_dilation),
            (3.0, base_dilation + 3),
            (3.0, aperture_dilation),
        ):
            mask = source_mask(image, valid, dilation=dilation, threshold=threshold)
            raw = blank_aperture_report(
                bundle,
                radii=(radius,),
                annulus_radii_arcsec=annulus,
                mask=mask,
                seed=731,
                block_size=128,
                bootstrap=500,
            )
            raw["source_mask_threshold"] = threshold
            raw["source_mask_dilation_pixels"] = dilation
            if threshold == 3 and dilation == base_dilation:
                comparisons = []
                measurements = raw["apertures"][0]["measurements"]
                for block_size in (64, 128, 256):
                    blocked = [
                        {
                            **row,
                            "spatial_block": f"{row['x'] // block_size}:{row['y'] // block_size}",
                        }
                        for row in measurements
                    ]
                    summary = _summarize_blanks(blocked, seed=731, bootstrap=500)
                    summary.pop("spatial_blocks", None)
                    comparisons.append({"block_size_pixels": block_size, **summary})
                raw["block_size_sensitivity"] = comparisons
            variations.append(compact_noise(raw))
        result["images"].append(
            {
                "filter": band,
                "image_sha256": checksum,
                "image_filename": path.name,
                "mask_variations": variations,
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fetch", "run"))
    parser.add_argument("--psf-directory", type=Path, default=Path("data_sources/pilot"))
    parser.add_argument("--image-manifest", type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--output", type=Path, default=Path("research_output/native_psf.json"))
    parser.add_argument(
        "--source-output", type=Path, default=Path("research_output/native_psf_source_phases.csv")
    )
    parser.add_argument(
        "--noise-output", type=Path, default=Path("research_output/noise_mask_sensitivity.json")
    )
    args = parser.parse_args()
    if args.action == "fetch":
        print(json.dumps(fetch_templates(args.psf_directory), indent=2))
        return 0
    if args.image_manifest is None or args.catalog is None:
        parser.error("run requires --image-manifest and --catalog")
    result, records = native_report(args.psf_directory, args.image_manifest, args.catalog)
    if not records:
        raise ValueError("catalog contains no eligible measured source positions")
    for path in (args.source_output, args.output, args.noise_output):
        path.parent.mkdir(parents=True, exist_ok=True)
    with args.source_output.open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    result["source_phase_csv"] = {
        "path": str(args.source_output),
        "rows": len(records),
        "sha256": hashlib.sha256(args.source_output.read_bytes()).hexdigest(),
    }
    result["code_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    noise = noise_mask_sensitivity(args.image_manifest)
    noise["code_sha256"] = result["code_sha256"]
    args.noise_output.write_text(json.dumps(noise, indent=2, allow_nan=False) + "\n")
    print(
        f"Native modeled responses at {len(records)} source/band positions; noise-mask sensitivity saved"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
