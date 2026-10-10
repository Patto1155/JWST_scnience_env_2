"""An adjacent medium band tests source46 F444-only excess, not its identity."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from scipy.ndimage import rotate
from scipy.optimize import minimize

from data_pipeline.research_sources import fetch_product
from data_pipeline.survivor_deep_data import verify_pinned
from discovery.deep_reference_comparison import load_deep_cutout
from discovery.psf_noise import overlap_resample, verified_template
from discovery.survivor_deep_model import (
    blank_operator_noise,
    image_template,
    linear_fit,
    read_passband,
    stamp,
)
from tools.jwst.photometry import extract_photometry

MANIFEST = Path(__file__).resolve().parents[1] / "data_sources/survivor46_medium/manifest.json"


def line_response_ratio(wavelength, medium_passband, wide_passband):
    """Photon-integrated fnu ratio of a single narrow line, common flux cancels."""
    wm, tm = medium_passband
    ww, tw = wide_passband
    dm = np.trapezoid(tm / wm, wm)
    dw = np.trapezoid(tw / ww, ww)
    medium = np.interp(wavelength, wm, tm, left=0, right=0) / dm
    wide = np.interp(wavelength, ww, tw, left=0, right=0) / dw
    return np.divide(medium, wide, out=np.full_like(np.asarray(medium), np.nan), where=wide > 0)


def contributors(bundle):
    return sorted(str(bundle["header"][k]) for k in bundle["header"] if k.startswith("FLT"))


def run(directory, deep, photometry, output):
    inventory = json.loads(MANIFEST.read_text())
    receipts = []
    for product in inventory["products"]:
        path = directory / product["filename"]
        if not path.exists():
            fetch_product(product, path, max_bytes=product["max_bytes"], timeout=40)
        receipts.append({"id": product["id"], **verify_pinned(path, product)})
    if hashlib.sha256(photometry.read_bytes()).hexdigest() != inventory["photometry_sha256"]:
        raise ValueError("Frozen photometry contract changed")
    for product in inventory["reused_deep_products"]:
        verify_pinned(deep / product["filename"], product)
    ra, dec = inventory["ra_deg"], inventory["dec_deg"]
    path = directory / "dja_46_F410M.fits"
    with fits.open(path) as hdus:
        if hdus[0].header.get("FILTER") != "F410M-CLEAR" or hdus[1].header.get("EXTVER") != "WHT":
            raise ValueError("Wrong actual medium-band SCI/WHT/filter identity")
    bundle, provenance = load_deep_cutout(path)
    position = SkyCoord(ra, dec, unit="deg")
    x, y = bundle["wcs"].world_to_pixel(position)
    if not (0 <= float(x) < bundle["sci"].shape[1] and 0 <= float(y) < bundle["sci"].shape[0]):
        raise ValueError("Requested position is outside array")
    if not bundle["validity_mask"][int(round(float(y))), int(round(float(x)))]:
        raise ValueError("Requested position lacks positive weight coverage")
    source = next(s for s in json.loads(photometry.read_text())["sources"] if s["source_id"] == 46)
    data, error, scale, phase = stamp(bundle, ra, dec, 40)
    raw, psf_provenance = verified_template(directory / "f410ma_v5.0_mpsf.fits", "F410M")
    psf = overlap_resample(raw, psf_provenance["input_scale_arcsec"], scale, 81)
    original, unused = load_deep_cutout(deep / "dja_46_F444W.fits")
    _, _, _, old_phase = stamp(original, ra, dec, 40)
    fixed = np.array(source["f444_morphology"]["extended"]["params"])
    fixed[:2] = phase + (fixed[:2] - old_phase)
    yy, xx = np.mgrid[:81, :81] - 40
    radius = np.hypot(xx, yy) * scale
    fits_out = []
    for fit_radius in (0.35, 0.5, 0.65):
        for angle in (0, 30):
            template_psf = (
                psf
                if angle == 0
                else rotate(psf, angle, reshape=False, order=1, mode="constant", cval=0)
            )
            fit = linear_fit(
                data, error, image_template(template_psf, scale, fixed), radius <= fit_radius, scale
            )
            fits_out.append({"radius_arcsec": fit_radius, "modeled_psf_rotation_deg": angle, **fit})
    noise = blank_operator_noise(bundle, psf, fixed, scale, 40)

    def centroid_score(offset):
        shifted = fixed.copy()
        shifted[:2] = offset
        return linear_fit(data, error, image_template(psf, scale, shifted), radius <= 0.65, scale)[
            "chi2_diagonal"
        ]

    centroid = minimize(
        centroid_score, fixed[:2], method="Powell", bounds=[(v - 0.1, v + 0.1) for v in fixed[:2]]
    )
    centroid_diagnostic = {
        "fixed_position_arcsec": fixed[:2].tolist(),
        "free_position_arcsec": centroid.x.tolist(),
        "displacement_arcsec": float(np.linalg.norm(centroid.x - fixed[:2])),
        "optimizer_success": bool(centroid.success),
        "interpretation": "Conditional same-mosaic registration, not a proper-motion measurement.",
    }
    apertures = []
    for radius_ap in (0.15, 0.2, 0.3):
        for inner, outer in ((0.4, 0.6), (0.6, 0.9)):
            fitted = extract_photometry(
                bundle,
                ra_deg=ra,
                dec_deg=dec,
                aperture_radius_arcsec=radius_ap,
                background_annulus_inner_radius_arcsec=inner,
                background_annulus_outer_radius_arcsec=outer,
            )
            apertures.append(
                {
                    "radius_arcsec": radius_ap,
                    "annulus_arcsec": [inner, outer],
                    "flux_njy": fitted["background_subtracted_flux_jy"] * 1e9,
                    "diagonal_error_njy": fitted["flux_error_jy"] * 1e9,
                }
            )
    model = next(
        f for f in fits_out if f["radius_arcsec"] == 0.65 and f["modeled_psf_rotation_deg"] == 0
    )
    f444 = source["bands"][-1]["fixed_extended_fit"]["flux_njy"]
    ratio = model["flux_njy"] / f444
    medium = read_passband(directory / "svo_F410M.xml", "F410M")
    wide = read_passband(deep / "svo_F444W.xml", "F444W")
    wavelengths = np.linspace(3.7, 5.0, 1301)
    responses = line_response_ratio(wavelengths, medium, wide)
    supported = np.isfinite(responses) & (
        np.interp(wavelengths, wide[0], wide[1], left=0, right=0) > 0.05 * wide[1].max()
    )
    matches = supported & (abs(responses - ratio) < 0.15 * abs(ratio))
    cmedium = contributors(bundle)
    cwide = contributors(original)
    overlap = sorted(set(cmedium) & set(cwide))
    result = {
        "schema_version": 1,
        "source_id": 46,
        "filter": "F410M",
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "photometry_sha256": hashlib.sha256(photometry.read_bytes()).hexdigest(),
        "input_receipts": receipts,
        "psf_provenance": psf_provenance,
        "medium_image": provenance,
        "exact_center_pixel": [float(x), float(y)],
        "frozen_f444_morphology_in_medium_pixel_phase": fixed.tolist(),
        "signed_fixed_models": fits_out,
        "background_operator_controls": noise,
        "aperture_background_sensitivity": apertures,
        "f444_frozen_njy": f444,
        "fiducial_f410_njy": model["flux_njy"],
        "fiducial_background_scaled_diagonal_error_njy": model["diagonal_error_njy"]
        * max(1, noise["diagonal_scale_factor"])
        if noise["diagonal_scale_factor"] is not None
        else None,
        "conditional_centroid_diagnostic": centroid_diagnostic,
        "f410_over_f444_conditional": ratio,
        "contributor_audit": {
            "medium_count": len(cmedium),
            "wide_count": len(cwide),
            "shared_exact_filenames": overlap,
            "medium_contributors": cmedium,
            "wide_contributors": cwide,
            "interpretation": "Different filters may share visits/calibration; disjoint exact file names do not make measurement systematics independent.",
        },
        "single_narrow_line_response_sensitivity": {
            "assumed_ratio_fractional_tolerance": 0.15,
            "ratio_not_a_calibrated_interval": True,
            "matched_wavelengths_micron": wavelengths[matches].tolist(),
            "maximum_f410_over_f444_single_line": float(np.nanmax(responses[supported])),
            "interpretation": "A single line inside both filters may mimic adjacent-band signal; positive F410 rejects only F444-only excess with negligible medium-band emission.",
        },
        "limits": [
            "Modeled official PSF transported to DAWN; source-specific empirical PSF, wings and rotation not calibrated.",
            "Diagonal objective and background scatter are descriptive, not Gaussian-tail probability; source shot noise omitted.",
            "Source shape frozen from F444 and nominal passbands; systematic floors remain assumed.",
            "No broad-continuum versus overlapping-line identity or stellar/galaxy classification established.",
        ],
    }
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("input", "deep", "photometry", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    r = run(args.input, args.deep, args.photometry, args.output)
    print(r["fiducial_f410_njy"], r["f410_over_f444_conditional"])


if __name__ == "__main__":
    main()
