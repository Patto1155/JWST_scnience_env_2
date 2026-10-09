"""Compare single-exposure nonrecovery with bounded DAWN deep-cutout recovery.

This is a targeted depth/systematics diagnostic, not survey completeness or an
independent image sample. The mosaics include the original exposure. No frozen
native-pixel classifier is applied to differently sampled mosaics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import warnings
from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales
from photutils.segmentation import detect_sources
from scipy.ndimage import binary_dilation

from data_pipeline.followup_data import MANIFEST, verify
from data_pipeline.research_sources import load_manifest
from discovery.artifact_characterization import detect_with_morphology
from tools.jwst.fits_loader import load_fits_bundle
from tools.jwst.photometry import extract_photometry

APERTURE = {"aperture_radius_arcsec": 0.2,
            "background_annulus_inner_radius_arcsec": 0.4,
            "background_annulus_outer_radius_arcsec": 0.6}


def load_deep_cutout(path: Path) -> tuple[dict, dict]:
    receipt = verify(path)
    with fits.open(path, memmap=False) as hdul:
        if len(hdul) != 2 or hdul[0].header["EXTVER"] != "SCI" or hdul[1].header["EXTVER"] != "WHT":
            raise ValueError("Expected exactly one SCI+inverse variance WHT pair")
        header = hdul[0].header.copy()
        sci = np.array(hdul[0].data, dtype=float)
        wht = np.array(hdul[1].data, dtype=float)
    valid = np.isfinite(sci) & np.isfinite(wht) & (wht > 0)
    err = np.full(sci.shape, np.nan)
    err[valid] = 1 / np.sqrt(wht[valid])
    bundle = {"sci": sci, "wht": wht, "err": err, "header": header,
              "wcs": WCS(header).celestial, "validity_mask": valid}
    contributors = [str(header[k]) for k in header if k.startswith("FLT")]
    return bundle, {
        "filename": path.name, "receipt": receipt, "input_bunit": header.get("BUNIT"),
        "grid_pixel_scales_arcsec": (proj_plane_pixel_scales(bundle["wcs"]) * 3600).tolist(),
        "ndrizim": header.get("NDRIZIM"), "header_exptime_s": header.get("EXPTIME"),
        "header_exptime_caveat": "Mosaic total header time is not necessarily local per-pixel depth",
        "grizli_version": header.get("GRIZLIV"), "crds_context": header.get("CRDS_CTX"),
        "updated_context": header.get("UPDA_CTX"), "contributors": contributors,
        "weight_interpretation": "inverse variance of SCI stored units from documented fits_weight API",
    }


def measurement(bundle: dict, **position) -> dict:
    result = extract_photometry(bundle, **position, **APERTURE)
    return {k: result[k] for k in ["background_subtracted_flux_jy", "flux_error_jy", "snr",
        "measurement_status", "calibration_status", "coverage_fraction", "uncertainty_method"]}


def blank_noise(bundle: dict) -> dict:
    """Disjoint angular footprints; robust scatter includes covariance/confusion.

    Source mask at 2 sigma with >=5 connected pixels, dilated four pixels, is an
    explicit operational sky definition. All aperture and annulus pixels must
    avoid this mask. Grid spacing >=1.5 arcsec exceeds twice the outer radius.
    """
    sci, valid = bundle["sci"], bundle["validity_mask"]
    _, median, sigma = sigma_clipped_stats(sci[valid], sigma=3)
    segmentation = detect_sources(np.where(valid, sci - median, 0),
                                  2 * sigma, npixels=5, mask=~valid)
    bright = np.zeros(sci.shape, bool) if segmentation is None else segmentation.data > 0
    excluded = binary_dilation(bright, iterations=4) | ~valid
    scale = float(np.sqrt(np.prod(proj_plane_pixel_scales(bundle["wcs"]) * 3600)))
    radius = int(np.ceil(0.6 / scale)) + 1
    spacing = int(np.ceil(1.5 / scale))
    samples, errors, positions = [], [], []
    yy, xx = np.mgrid[-radius:radius+1, -radius:radius+1]
    footprint = np.hypot(xx, yy) <= 0.6 / scale + 1
    for y in range(radius + 1, sci.shape[0] - radius - 1, spacing):
        for x in range(radius + 1, sci.shape[1] - radius - 1, spacing):
            if np.any(excluded[y-radius:y+radius+1, x-radius:x+radius+1][footprint]):
                continue
            row = measurement(bundle, x=x, y=y)
            if row["measurement_status"] != "measured" or row["flux_error_jy"] is None:
                continue
            samples.append(row["background_subtracted_flux_jy"])
            errors.append(row["flux_error_jy"])
            positions.append([x, y])
    if len(samples) < 20:
        return {"status": "insufficient_blank_apertures", "count": len(samples), "sigma_jy": None}
    a = np.array(samples)
    scatter = float(1.4826 * np.median(np.abs(a - np.median(a))))
    return {"status": "measured", "count": len(samples), "sigma_jy": scatter,
            "median_jy": float(np.median(a)), "formal_error_median_jy": float(np.median(errors)),
            "scatter_to_formal_ratio": float(scatter / np.median(errors)),
            "samples_jy": samples, "positions_pixels": positions,
            "limitation": "Source-masked blank-sky covariance/confusion diagnostic; masks and spatial depth affect scatter"}


def detect_match(bundle: dict, reference: dict) -> dict:
    sources = detect_with_morphology(bundle)
    if not sources:
        return {"status": "not_detected", "total_detections": 0, "separation_arcsec": None}
    coords = bundle["wcs"].pixel_to_world([s["x"] for s in sources], [s["y"] for s in sources])
    reference_sky = SkyCoord(reference["ra_deg"], reference["dec_deg"], unit="deg")
    separations = reference_sky.separation(coords).arcsec
    close = np.flatnonzero(separations <= 0.2)
    return {"status": "matched" if len(close) == 1 else "ambiguous" if len(close) else "not_detected",
            "total_detections": len(sources), "matches_within_0p2_arcsec": len(close),
            "separation_arcsec": float(separations.min()),
            "detector_rule": "unchanged 5-sigma >=5-pixel segmentation; angular area differs between image grids"}


def compare(input_dir: Path, original: Path) -> dict:
    source = load_manifest(MANIFEST)["sources"][1]
    original_bundle = load_fits_bundle(str(original.resolve()))
    original_receipt = verify(original)
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for product in source["products"]:
            reference = product["reference"]
            bundle, provenance = load_deep_cutout(input_dir / ("dja_f444w_" + product["id"] + ".fits"))
            noise = blank_noise(bundle)
            photometry = measurement(bundle, ra_deg=reference["ra_deg"], dec_deg=reference["dec_deg"])
            if noise["sigma_jy"] is not None and noise["sigma_jy"] > 0:
                photometry["blank_scatter_snr"] = photometry["background_subtracted_flux_jy"] / noise["sigma_jy"]
            else:
                photometry["blank_scatter_snr"] = None
            rows.append({"reference": reference, "deep_image": provenance,
                         "original_in_deep_contributors": original.name.replace("_i2d.fits", "_rate.fits") in provenance["contributors"],
                         "single_exposure_measurement": measurement(original_bundle, ra_deg=reference["ra_deg"], dec_deg=reference["dec_deg"]),
                         "single_exposure_detection": detect_match(original_bundle, reference),
                         "deep_measurement": photometry, "deep_detection": detect_match(bundle, reference),
                         "deep_blank_noise": noise})
    return {
        "schema_version": 1, "evidence_kind": "actual_public_images_targeted_depth_comparison",
        "original_receipt": original_receipt,
        "reference_csv_sha256": hashlib.sha256(Path("data_sources/pilot/jades_dr4_reference.csv").read_bytes()).hexdigest(),
        "selection": "Three exact covered-undetected high-z references from preceding frozen real validation; A and C labels separate",
        "aperture": APERTURE, "rows": rows,
        "limits": ["No independent-image claim: mosaic includes original exposure and cutouts may overlap",
                   "No completeness estimate from three selected nonrecoveries",
                   "No frozen classifier transferred to differently sampled mosaic",
                   "Aperture fluxes omit PSF correction; WHT formal errors are diagonal; empirical sky scatter retains masking assumptions",
                   "5-pixel detector rule covers different angular area at different sampling",
                   "Two tentative C redshifts are not treated as robust A/B truth"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.input, args.original)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
