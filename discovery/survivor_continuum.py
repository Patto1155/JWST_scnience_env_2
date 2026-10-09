"""Forced F277W/F356W continuum checks and honest targeted-catalog crossmatches."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from astropy.coordinates import SkyCoord

from discovery.audit_candidates import audit_candidate
from discovery.image_photometry_rerun import (
    load_selection_measurements,
    sha256_file,
    verify_image_manifest,
)
from tools.jwst.fits_loader import load_fits_bundle
from tools.jwst.photometry import extract_photometry


def continuum_slope(first: dict, second: dict, red: dict) -> dict[str, Any]:
    """Conditional slope diagnostic, using nominal filter-label wavelengths."""
    result = {
        "status": "insufficient_positive_3sigma_continuum",
        "alpha_fnu_frequency": None,
        "alpha_diagonal_error": None,
        "predicted_f444_flux_jy": None,
        "observed_minus_predicted_fraction": None,
    }
    for item in (first, second):
        flux, error = item.get("background_subtracted_flux_jy"), item.get("flux_error_jy")
        if (
            item.get("calibration_status") != "calibrated"
            or item.get("measurement_status") != "measured"
            or item.get("background_status") != "measured"
            or item.get("coverage_fraction", 0) < 0.9
            or flux is None
            or error is None
            or not math.isfinite(flux)
            or not math.isfinite(error)
            or error <= 0
            or flux / error < 3
        ):
            return result
    flux1, flux2 = first["background_subtracted_flux_jy"], second["background_subtracted_flux_jy"]
    logratio = math.log(3.56 / 2.77)
    beta = math.log(flux2 / flux1) / logratio
    beta_error = (
        math.hypot(first["flux_error_jy"] / flux1, second["flux_error_jy"] / flux2) / logratio
    )
    prediction = flux1 * (4.44 / 2.77) ** beta
    fraction = None
    if red.get("background_subtracted_flux_jy") is not None:
        fraction = (red["background_subtracted_flux_jy"] - prediction) / prediction
    result.update(
        status="diagonal_PSF_uncorrected_diagnostic",
        alpha_fnu_frequency=-beta,
        alpha_diagonal_error=beta_error,
        predicted_f444_flux_jy=prediction,
        observed_minus_predicted_fraction=fraction,
    )
    return result


def reference_matches(ra: float, dec: float, references: list[dict[str, Any]]) -> dict[str, Any]:
    """Spherical 0.3/0.5 arcsec matches; never associate a distant nearest neighbour."""
    coords = SkyCoord(
        [float(row["RA_TARG"]) for row in references],
        [float(row["Dec_TARG"]) for row in references],
        unit="deg",
    )
    separations = SkyCoord(ra, dec, unit="deg").separation(coords).arcsec
    order = np.argsort(separations)

    def record(index: int) -> dict:
        row = references[index]
        redshift = float(row["z_Spec"])
        return {
            "observation_id": row["Unique_ID"],
            "separation_arcsec": float(separations[index]),
            "quality": row["z_Spec_flag"],
            "z_spec": redshift if math.isfinite(redshift) and redshift >= 0 else None,
            "nircam_dr5_id": row["NIRCam_DR5_ID"],
        }

    return {
        "nearest_observation": record(int(order[0])),
        "within_0p3arcsec": [record(int(i)) for i in order if separations[i] <= 0.3],
        "within_0p5arcsec": [record(int(i)) for i in order if separations[i] <= 0.5],
        "nearest_AB_observation": next(
            (record(int(i)) for i in order if references[i]["z_Spec_flag"] in ("A", "B")), None
        ),
        "association_status_0p5arcsec": (
            "unmatched"
            if not np.any(separations <= 0.5)
            else "single_targeted_observation"
            if int(np.sum(separations <= 0.5)) == 1
            else "multiple_observations_check_identity_and_redshift_consistency"
        ),
        "coordinate_field": "JADES spectroscopic targeting RA_TARG/Dec_TARG",
        "association_rule": (
            "Associate only within the radius; repeated observations are not unique galaxies"
        ),
    }


def run_continuum(
    catalog_dir: Path,
    manifest: Path,
    reference_csv: Path,
    output: Path,
    *,
    extra_source_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Measure the original survivors and explicitly nominated model-sensitivity entrants."""
    csv_path, metadata_path = (
        catalog_dir / "selection_measurements.csv",
        catalog_dir / "selection_metadata.json",
    )
    replay = json.loads((catalog_dir / "compact_replay_verification.json").read_text())
    if (
        sha256_file(csv_path) != replay["selection_csv_sha256"]
        or sha256_file(metadata_path) != replay["selection_metadata_sha256"]
    ):
        raise ValueError("Compact measurement provenance mismatch")
    metadata = json.loads(metadata_path.read_text())
    source_rows = load_selection_measurements(csv_path, metadata_path)
    survivors = {
        row["source_id"]
        for row in source_rows
        if audit_candidate(row)["audit_verdict"] == "survives"
    }
    requested = survivors | set(extra_source_ids or [])
    selected = [row for row in source_rows if row["source_id"] in requested]
    if len(selected) != len(requested):
        raise ValueError("Requested source ID is absent from the frozen proposal catalog")
    images, blockers = verify_image_manifest(manifest)
    if blockers:
        raise ValueError(f"Science images unavailable or unverified: {blockers}")
    images = [image for image in images if image["filter"] in ("F277W", "F356W")]
    if not images:
        raise ValueError("No F277W/F356W science images supplied")
    bundles = {image["resolved_path"]: load_fits_bundle(image["resolved_path"]) for image in images}
    reference_receipt_path = reference_csv.with_name(reference_csv.name + ".provenance.json")
    reference_receipt = json.loads(reference_receipt_path.read_text())
    if sha256_file(reference_csv) != reference_receipt["sha256"]:
        raise ValueError("Reference catalog hash does not match its acquisition receipt")
    references = list(csv.DictReader(reference_csv.open(newline="")))
    if len(references) != reference_receipt["summary"]["rows"]:
        raise ValueError(
            "Reference catalog row count differs from the pinned full-observation transform"
        )
    output_sources = []
    for source in selected:
        ra, dec = source["sky_center"]["ra"], source["sky_center"]["dec"]
        measurements = []
        for image in images:
            if image["target"] != source["target"]:
                continue
            bundle = bundles[image["resolved_path"]]
            measured = extract_photometry(
                bundle,
                ra_deg=ra,
                dec_deg=dec,
                aperture_radius_arcsec=metadata["aperture_radius_arcsec_by_filter"]["F444W"],
                background_annulus_inner_radius_arcsec=metadata["annulus_radii_arcsec"]["inner"],
                background_annulus_outer_radius_arcsec=metadata["annulus_radii_arcsec"]["outer"],
                strict_data=True,
            )
            mid_mjd = bundle["primary_header"].get("EXPMID", bundle["header"].get("MJD-AVG"))
            measurements.append(
                {
                    "filter": image["filter"],
                    "image_sha256": image["sha256"],
                    "image_filename": Path(image["resolved_path"]).name,
                    "expmid_mjd": mid_mjd,
                    "measurement": measured,
                }
            )
        recent = {}
        for measurement in measurements:
            band = measurement["filter"]
            if band not in recent or measurement["expmid_mjd"] > recent[band]["expmid_mjd"]:
                recent[band] = measurement
        slope = continuum_slope(
            recent["F277W"]["measurement"],
            recent["F356W"]["measurement"],
            source["photometry_by_filter"]["F444W"]["3"],
        )
        output_sources.append(
            {
                "source_id": source["source_id"],
                "sky_center": source["sky_center"],
                "in_original_seven": source["source_id"] in survivors,
                "measurements": measurements,
                "latest_visit_slope": slope,
                "reference_catalog": reference_matches(ra, dec, references),
            }
        )
    result = {
        "experiment": "forced cross-band continuum and targeted spectroscopy reference checks",
        "catalog_sha256": sha256_file(csv_path),
        "operator_metadata_sha256": sha256_file(metadata_path),
        "images_manifest_sha256": sha256_file(manifest),
        "reference_catalog_sha256": sha256_file(reference_csv),
        "reference_receipt_sha256": sha256_file(reference_receipt_path),
        "reference_original_fits_sha256": reference_receipt["source_sha256"],
        "reference_observation_count": len(references),
        "sources": output_sources,
        "assumptions": [
            "Slope uses nominal filter-label wavelengths 2.77,3.56,4.44 microns.",
            "Slope error assumes diagonal noise; PSF/background/calibration terms are excluded.",
            "Latest observation per filter defines the slope; exposures are not simultaneous.",
        ],
        "limits": [
            "Fluxes remain signed; insufficient continuum yields no logarithmic slope.",
            "Broadband slope does not establish redshift, age, dust or black-hole content.",
            "Targeted JADES spectra are incomplete; no match does not establish an unknown object.",
            "Repeat F444 evidence is measured independently of cross-band absence.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog_dir", type=Path)
    parser.add_argument("images_manifest", type=Path)
    parser.add_argument("reference_csv", type=Path)
    parser.add_argument("--extra-source-ids", nargs="*", type=int, default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_continuum(
        args.catalog_dir,
        args.images_manifest,
        args.reference_csv,
        args.output,
        extra_source_ids=args.extra_source_ids,
    )
    print(
        json.dumps(
            {row["source_id"]: row["latest_visit_slope"]["status"] for row in result["sources"]}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
