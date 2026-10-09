"""Follow-up to merged UV fits: pinned point-source R and bin-leverage controls.

The earlier nominal-resolution report remains provenance.  This module does not
convert line ratios to abundances or treat influential bins as bad pixels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits

from .line_sensitivity import (
    Extraction,
    LINE_COMPONENTS,
    LINE_NAMES,
    SOURCE_HASH,
    bin_edges,
    fit_lines,
    read_extractions,
    read_resolution,
    redshift_scan,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def read_point_resolution(path: Path) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Verify derivative bytes and replay the non-executable polynomial transform."""
    receipt = json.loads(Path(str(path) + ".provenance.json").read_text())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != receipt["sha256"]:
        raise ValueError("Point resolution derivative does not match receipt")
    table = np.genfromtxt(path, delimiter=",", names=True)
    wave, resolution = table["wavelength_um"], table["point_R"]
    if (
        len(wave) < 3
        or np.any(np.diff(wave) <= 0)
        or not np.all(np.isfinite(wave))
        or not np.all(np.isfinite(resolution) & (resolution > 0))
    ):
        raise ValueError("Invalid point resolution curve")
    replay = np.polyval(receipt["coefficients_descending"], wave)
    if not np.allclose(replay, resolution, rtol=1e-12, atol=1e-10):
        raise ValueError("Point resolution transform cannot be replayed")
    return (
        wave,
        resolution,
        {
            "sha256": digest,
            "source_url": receipt["source_receipt"]["requested_url"],
            "author_source_sha256": receipt["source_receipt"]["sha256"],
            "author_grid_sha256": receipt["grid_receipt"]["sha256"],
            "coefficients_descending": receipt["coefficients_descending"],
            "transform_replayed": True,
            "interpretation": "Pinned UNITE generic point-source R(lambda), Gaussian FWHM approximation",
            "source_specific_lsf_calibrated": False,
            "exact_published_runtime_reproduced": False,
            "citation": receipt["citation"],
        },
    )


def compact_fit(result: dict[str, Any]) -> dict[str, Any]:
    """Keep fluxes/covariance/assumptions, omit redundant 473-point model vectors."""
    return {k: v for k, v in result.items() if k != "model_fnu_uJy"}


def leave_one_bin_out(extraction: Extraction, rw: np.ndarray, rr: np.ndarray) -> dict[str, Any]:
    """Delete every usable UV bin in turn, retaining all original bin edges."""
    indices = np.flatnonzero(
        extraction.valid & (extraction.wave >= 2.15) & (extraction.wave <= 3.20)
    )
    baseline = fit_lines(extraction, rw, rr)
    records = []
    for index in indices:
        mask = extraction.valid.copy()
        mask[index] = False
        altered = Extraction(
            extraction.name,
            extraction.wave,
            extraction.flux,
            extraction.error,
            mask,
            extraction.notes,
        )
        fit = fit_lines(altered, rw, rr)
        records.append(
            {
                "omitted_full_grid_index": int(index),
                "omitted_wavelength_um": float(extraction.wave[index]),
                "remaining_fit_bins": fit["bins"],
                "line_fluxes": [fit["lines"][n]["flux"] for n in LINE_NAMES],
                "conditional_sigmas": [fit["lines"][n]["conditional_sigma"] for n in LINE_NAMES],
                "line_flux_ratio": fit["nitrogen_lines_over_carbon_lines"]["value"],
                "chi2": fit["chi2"],
            }
        )
    summary = {}
    for j, name in enumerate(LINE_NAMES):
        low = min(records, key=lambda record: record["line_fluxes"][j])
        high = max(records, key=lambda record: record["line_fluxes"][j])
        summary[name] = {
            "baseline_flux": baseline["lines"][name]["flux"],
            "minimum_flux": low["line_fluxes"][j],
            "minimum_conditional_sigma": low["conditional_sigmas"][j],
            "minimum_omitted_index": low["omitted_full_grid_index"],
            "minimum_omitted_wavelength_um": low["omitted_wavelength_um"],
            "maximum_flux": high["line_fluxes"][j],
            "maximum_omitted_index": high["omitted_full_grid_index"],
        }
    return {
        "redshift": 14.44,
        "intrinsic_fwhm_km_s": 0,
        "rho_assumed": 0,
        "continuum_fnu_polynomial_order": 1,
        "line_order": list(LINE_NAMES),
        "baseline_fit": compact_fit(baseline),
        "full_bin_grid_preserved": True,
        "deletions": len(records),
        "records": records,
        "per_line_extrema": summary,
        "interpretation": "Expected influence of sampled resolution elements; not a quality flag, detection test, or evidence that an influential bin is bad",
    }


def native_quality_support(
    path: Path, rw: np.ndarray, rr: np.ndarray, leverage: dict[str, Any], source_wave: np.ndarray
) -> dict[str, Any]:
    """Describe actual native DQ around line windows without calibrating new fluxes.

    Counts include all spatial rows and are not source-trace-specific line vetting.
    Official EXTENDED calibration differs from the DJA extraction conventions.
    """
    receipt = json.loads(Path(str(path) + ".provenance.json").read_text())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != receipt["sha256"]:
        raise ValueError("Native slit differs from receipt")
    with fits.open(path, memmap=False) as h:
        science, error, wave, dq = (
            np.asarray(h[n].data) for n in ("SCI", "ERR", "WAVELENGTH", "DQ")
        )
        if not (science.shape == error.shape == wave.shape == dq.shape):
            raise ValueError("Native SCI/ERR/WAVELENGTH/DQ shapes disagree")
        if h["SCI"].header["SRCNAME"] != "5224_277193":
            raise ValueError("Native slit is not verified MoM-z14 source")
        finite = (
            np.isfinite(science) & np.isfinite(error) & (error > 0) & np.isfinite(wave) & (wave > 0)
        )
        usable = finite & ((dq & 3) == 0)
        supports = {}
        for name, (rests, weights) in zip(LINE_NAMES, LINE_COMPONENTS):
            center = np.average(rests, weights=weights) * 1e-4 * 15.44
            fwhm = center / np.interp(center, rw, rr)
            in_window = np.isfinite(wave) & (np.abs(wave - center) <= fwhm)
            supports[name] = {
                "center_um": float(center),
                "window_half_width_um": float(fwhm),
                "native_pixels_in_window_all_rows": int(in_window.sum()),
                "finite_usable_dq_pixels_all_rows": int(np.sum(in_window & usable)),
                "do_not_use_pixels_all_rows": int(np.sum(in_window & ((dq & 1) != 0))),
                "saturated_pixels_all_rows": int(np.sum(in_window & ((dq & 2) != 0))),
            }
        edges = bin_edges(source_wave)
        overlap = {}
        for name in ("NIV", "CIV"):
            index = leverage["per_line_extrema"][name]["minimum_omitted_index"]
            low, high = edges[index : index + 2]
            selected = np.isfinite(wave) & (wave >= low) & (wave < high)
            yy, xx = np.where(selected)
            overlap[name] = {
                "dja_full_grid_bin_index": index,
                "dja_bin_center_um": float(source_wave[index]),
                "dja_bin_edges_um": [float(low), float(high)],
                "native_pixels_in_bin_all_rows": int(selected.sum()),
                "native_usable_pixels_in_bin_all_rows": int(np.sum(selected & usable)),
                "do_not_use_pixels_all_rows": int(np.sum(selected & ((dq & 1) != 0))),
                "saturated_pixels_all_rows": int(np.sum(selected & ((dq & 2) != 0))),
                "native_row_column_dq_usable": [
                    [int(y), int(x), int(dq[y, x]), bool(usable[y, x])] for y, x in zip(yy, xx)
                ],
                "interpretation": "Wavelength overlap only; no native trace or coadd contribution mapping assumed",
            }
        return {
            "input_sha256": digest,
            "source_url": receipt["input_receipt"]["requested_url"],
            "source_id": 277193,
            "shape": list(science.shape),
            "calibration_version": h[0].header["CAL_VER"],
            "crds_context": h[0].header["CRDS_CTX"],
            "source_type_upstream": h["SCI"].header["SRCTYPE"],
            "science_bunit": h["SCI"].header["BUNIT"],
            "exposure_time_s": receipt["exposure_time_s"],
            "nod_position_header": h[0].header.get("PATT_NUM"),
            "quality_rule": "Finite SCI/wavelength, finite positive ERR, no DO_NOT_USE(1) or SATURATED(2)",
            "usable_native_pixels": int(usable.sum()),
            "line_window_quality_support": supports,
            "highest_leverage_bin_native_overlap": overlap,
            "limitations": [
                "One shared exposure, not an independent observation of the galaxy",
                "All-row counts include geometrical slit edges; not source-trace quality fractions",
                "No EXTENDED-to-point-source conversion, nod subtraction, or new line extraction attempted",
                "Different official 2026 calibration version from 2025 DJA; not directly comparable flux calibration",
                "Native DQ supplies one-exposure inputs; coadd PIXTAB/quality mapping, all exposures, geometry and empirical covariance remain needed",
            ],
        }


def native_batch_quality(
    batch_path: Path,
    native_dir: Path,
    rw: np.ndarray,
    rr: np.ndarray,
    leverage: dict[str, Any],
    source_wave: np.ndarray,
    *,
    inventory_path: Path = REPO_ROOT / "data_sources/followup/mom_native_inventory.json",
    pinned_batch_path: Path = REPO_ROOT / "research_output/mom_native_batch.json",
    spectrum_path: Path = REPO_ROOT / "data_sources/pilot/mom_z14_dja_v4.spec.fits",
) -> dict[str, Any]:
    """Require the pinned nine originals/derivatives before certifying coverage.

    Empty, partial, duplicate or substituted batches are rejected. Empty UV
    wavelength support is not estimable, rather than vacuously usable.
    """
    batch = json.loads(batch_path.read_text())
    records = batch.get("exposures", [])
    names = [r.get("metadata", {}).get("filename") for r in records]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate exposure in native batch")
    if len(records) != 9:
        raise ValueError("Native batch requires exactly nine pinned exposures")
    if batch.get("source_spectrum_receipt", {}).get("sha256") != SOURCE_HASH:
        raise ValueError("Native batch was not selected from the verified source spectrum")
    inventory = json.loads(inventory_path.read_text())
    products = inventory["products"]
    expected = {p["filename"]: p for p in products}
    if (
        inventory["source_spectrum_sha256"] != SOURCE_HASH
        or len(products) != 9
        or len(expected) != 9
    ):
        raise ValueError("Pinned native inventory is inconsistent with the source spectrum")
    if set(names) != set(expected):
        raise ValueError("Native batch identities differ from exact pinned nine-exposure inventory")
    pinned = json.loads(pinned_batch_path.read_text())
    pinned_records = {r["metadata"]["filename"]: r for r in pinned["exposures"]}
    if (
        pinned.get("source_spectrum_receipt", {}).get("sha256") != SOURCE_HASH
        or len(pinned["exposures"]) != 9
        or set(pinned_records) != set(expected)
    ):
        raise ValueError("Pinned derivative manifest does not cover the exact inventory")
    if hashlib.sha256(spectrum_path.read_bytes()).hexdigest() != SOURCE_HASH:
        raise ValueError("Source spectrum differs from verified source SHA256")
    with fits.open(spectrum_path, memmap=False) as h:
        source_nods = {r["filename"]: int(r["position_number"]) for r in h["SLITS"].data}
    if {p["source_slits_filename"] for p in products} != set(source_nods):
        raise ValueError("Pinned inventory does not match the source SLITS exposure set")
    total_bytes = sum(p["expected_bytes"] for p in products)
    if batch.get("budget", {}).get("actual_original_bytes") != total_bytes:
        raise ValueError("Native batch byte total differs from pinned originals")
    exposures = []
    for record in records:
        metadata = record.get("metadata", {})
        product = expected[metadata["filename"]]
        reference = pinned_records[product["filename"]]
        filename = record.get("derived_slit_filename")
        expected_derived = product["filename"].replace("_cal.fits", "_277193_native.fits")
        if filename != expected_derived or filename != reference["derived_slit_filename"]:
            raise ValueError("Native derivative filename differs from pinned exposure")
        receipt = record.get("native_exposure_receipt", {})
        if (
            receipt.get("requested_url") != product["url"]
            or receipt.get("sha256") != product["sha256"]
            or receipt.get("bytes") != product["expected_bytes"]
            or metadata.get("source_slits_filename") != product["source_slits_filename"]
            or metadata.get("url") != product["url"]
            or metadata.get("position_number") != source_nods[product["source_slits_filename"]]
        ):
            raise ValueError(
                "Native parent identity/hash/size/nod differs from pinned source inventory"
            )
        original_path = native_dir / product["filename"]
        if (
            original_path.stat().st_size != product["expected_bytes"]
            or hashlib.sha256(original_path.read_bytes()).hexdigest() != product["sha256"]
        ):
            raise ValueError("Actual native original bytes differ from pinned inventory")
        path = native_dir / filename
        derivative_receipt = json.loads(Path(str(path) + ".provenance.json").read_text())
        parent_receipt = derivative_receipt.get("input_receipt", {})
        if (
            parent_receipt.get("requested_url") != product["url"]
            or parent_receipt.get("sha256") != product["sha256"]
            or parent_receipt.get("bytes") != product["expected_bytes"]
            or derivative_receipt.get("sha256") != reference["identity_quality"]["sha256"]
        ):
            raise ValueError("Native derivative parent/pinned checksum differs from inventory")
        actual = native_quality_support(path, rw, rr, leverage, source_wave)
        if (
            actual["input_sha256"] != record.get("identity_quality", {}).get("sha256")
            or actual["input_sha256"] != reference["identity_quality"]["sha256"]
        ):
            raise ValueError("Native batch derivative differs from selected manifest")
        if actual["nod_position_header"] != source_nods[product["source_slits_filename"]]:
            raise ValueError("Native slit nod header differs from verified source observation")
        if set(actual["line_window_quality_support"]) != set(LINE_NAMES) or set(
            actual["highest_leverage_bin_native_overlap"]
        ) != {"NIV", "CIV"}:
            raise ValueError("Native quality support is missing required UV groups")
        actual["filename"] = filename
        actual["nod_position"] = metadata["position_number"]
        exposures.append(actual)
    windows = [
        group
        for exposure in exposures
        for group in exposure["line_window_quality_support"].values()
    ]
    overlaps = [
        group
        for exposure in exposures
        for group in exposure["highest_leverage_bin_native_overlap"].values()
    ]
    window_estimable = all(g["native_pixels_in_window_all_rows"] > 0 for g in windows)
    overlap_estimable = all(g["native_pixels_in_bin_all_rows"] > 0 for g in overlaps)
    window_usable = (
        all(
            g["native_pixels_in_window_all_rows"] == g["finite_usable_dq_pixels_all_rows"]
            for g in windows
        )
        if window_estimable
        else None
    )
    overlap_usable = (
        all(
            g["native_pixels_in_bin_all_rows"] == g["native_usable_pixels_in_bin_all_rows"]
            for g in overlaps
        )
        if overlap_estimable
        else None
    )
    return {
        "batch_manifest_sha256": hashlib.sha256(batch_path.read_bytes()).hexdigest(),
        "pinned_inventory_sha256": hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
        "pinned_derivative_manifest_sha256": hashlib.sha256(
            pinned_batch_path.read_bytes()
        ).hexdigest(),
        "exposure_count": len(exposures),
        "original_bytes": total_bytes,
        "exposures": exposures,
        "all_uv_window_pixels_usable": window_usable,
        "all_high_leverage_overlap_pixels_usable": overlap_usable,
        "uv_support_status": "estimable" if window_estimable else "not_estimable",
        "high_leverage_support_status": "estimable" if overlap_estimable else "not_estimable",
        "interpretation": "Acquired full exposure set is available; native quality is not a re-extracted or independently calibrated line measurement",
    }


def render_summary(result: dict[str, Any], output: Path) -> None:
    nominal = result["nominal_reference_fit"]
    point = result["point_source_scenarios"][0]
    loo = result["leave_one_bin_out"]["generic_point_source"]
    scan = result["point_tied_redshift_width_scans"][0]
    text = [
        "# MoM-z14 follow-up: generic point-source resolution and bin leverage",
        "",
        "This experiment builds on merged PR #18 without replacing its provenance report. A pinned, generic UNITE point-source resolving-power calibration changes conditional flux constraints; source-specific slit geometry, wavelength uncertainty and empirical covariance are still missing. Nothing here measures elemental N/C or selects an enrichment mechanism.",
        "",
        "## Verified calibration",
        "",
        f"[Pinned author code]({result['point_resolution']['source_url']}) supplies PRISM POINT-source R(λ), citing [de Graaff et al.](https://doi.org/10.1051/0004-6361/202347755). The acquired CSV and receipt pin the source, official wavelength grid and derivative checksums. We replay the descending polynomial coefficients without executing downloaded author code. Generic point-source R is closer to the published UNITE model family than the preceding fully illuminated slit curve, but the current pinned commit is not proven to be the exact paper runtime, and its Gaussian approximation is not MoM's shutter-specific full LSF.",
        "",
        "| UV group | Nominal illuminated R | Generic point-source R |",
        "|---|---:|---:|",
    ]
    for n in LINE_NAMES:
        text.append(
            f"| {n} | {result['resolution_at_group_centers'][n]['nominal']:.2f} | {result['resolution_at_group_centers'][n]['point']:.2f} |"
        )
    text += [
        "",
        "## Actual-FITS fits",
        "",
        "Same 73 quality-masked bins, full original bin edges, z=14.44, intrinsic width zero, signed amplitudes and a linear fν continuum. Flux units are 10⁻²⁰ erg s⁻¹ cm⁻²; ± values are conditional GLS errors.",
        "",
        "| Group | Earlier nominal R | Generic point-source R | All-bin-delete flux range (point R) |",
        "|---|---:|---:|---:|",
    ]
    for n in LINE_NAMES:
        a, b, c = nominal["lines"][n], point["lines"][n], loo["per_line_extrema"][n]
        text.append(
            f"| {n} | {a['flux']:.2f} ± {a['conditional_sigma']:.2f} | {b['flux']:.2f} ± {b['conditional_sigma']:.2f} | {c['minimum_flux']:.2f}–{c['maximum_flux']:.2f} |"
        )
    ratios = [
        s["nitrogen_lines_over_carbon_lines"]["value"] for s in result["point_source_scenarios"]
    ]
    ratio = point["nitrogen_lines_over_carbon_lines"]
    interval = ratio["fieller_normal_68_and_95_sets"]["1.95996398454"]
    interval_text = json.dumps(interval, allow_nan=False)
    text += [
        "",
        f"The point-source summed nitrogen/carbon **line-flux** ratio is {ratio['value']:.3f}, conditional 95% Fieller set `{interval_text}`. Across the {len(ratios)} specified point-resolution scenarios its point estimate spans {min(ratios):.3f}–{max(ratios):.3f}; this is an assumption range, not a confidence interval or elemental abundance.",
        "",
        f"The tied scan gives z={scan['best_fit']['redshift']:.3f}, Δχ²≤1 profile envelope {scan['delta_chi2_1_profile_envelope_z']}. Line-flux profile intervals propagating the tied z/width grid are saved with the conditional covariance matrices. Width, redshift and correlations remain model conditional; no independently calibrated significance is claimed.",
        "",
        "Assumed AR(1) ρ=0/0.25/0.5, all six central 2D extraction alternatives, intrinsic width 300/650 km/s, continuum orders 0/2/3 and alternative multiplet/blend weights are retained in the compact JSON. Empirical covariance is not inferred from these scenarios. The no-correlation null scan repeats 1,000 seeded simulations under the same limited Gaussian model; it includes the stated z/width search but excludes prior source/line selection and unknown reduction systematics.",
        "",
        "## Leverage is expected at PRISM sampling",
        "",
        "Every usable bin is withheld once, with no neighbor bin-edge changes and no flux-dependent rejection. These are diagnostic perturbations, **not** newly justified masks or bad-pixel identifications. A genuine unresolved feature sampled by few bins can have high one-bin leverage.",
        "",
        "| Group | Smallest estimate after one omission | Omitted observed wavelength |",
        "|---|---:|---:|",
    ]
    for n in LINE_NAMES:
        c = loo["per_line_extrema"][n]
        text.append(
            f"| {n} | {c['minimum_flux']:.2f} ± {c['minimum_conditional_sigma']:.2f} | {c['minimum_omitted_wavelength_um']:.6f} µm |"
        )
    text += [
        "",
        "The useful next test is recurrence and native quality of influential detector samples across independent nods/integrations, with the complete extraction geometry. Removing a high bin solely because it supports a line would bias the fit.",
        "",
    ]
    if result["native_quality_support"] is not None:
        native = result["native_quality_support"]
        text += [
            "## Acquired actual native-DQ control",
            "",
            f"One public native-grid calibrated MoM-z14 slit was acquired and verified by source ID and coordinates. It supplies SCI/ERR/DQ/WAVELENGTH and pathloss/variance arrays for {native['exposure_time_s']:.3f} s, calibrated with `{native['calibration_version']}` / `{native['crds_context']}`. {native['usable_native_pixels']:,} pixels have finite values, positive errors and neither DO_NOT_USE nor SATURATED. Upstream `SRCTYPE={native['source_type_upstream']}` and `BUNIT={native['science_bunit']}` differ from the DJA point-source extraction; no unvalidated conversion/extraction is presented.",
            "",
            "Line-window DQ counts include **all spatial slit rows**, including geometric edges, and cannot be read as trace contamination fractions. One exposure's DQ is now accessible, while complete coadd PIXTAB, exposure-mask mapping and calibrated source-specific geometry remain genuine dependencies.",
            "",
        ]
    if result["native_batch_quality"] is not None:
        batch = result["native_batch_quality"]
        windows_clear = batch["all_uv_window_pixels_usable"] is True
        overlaps_clear = batch["all_high_leverage_overlap_pixels_usable"] is True
        if batch["all_uv_window_pixels_usable"] is None:
            window_text = "UV-window quality is **not estimable**: at least one required wavelength window has no native support. No all-window usability claim is possible."
        elif windows_clear:
            window_text = "All pixels in the five ±generic-point-FWHM UV windows are finite with positive errors and lack DO_NOT_USE/SATURATED in every acquired exposure."
        else:
            window_text = "At least one supported UV-window pixel fails the finite-value, positive-error or DO_NOT_USE/SATURATED criteria; the full window set is not wholly usable."
        if batch["all_high_leverage_overlap_pixels_usable"] is None:
            overlap_text = "Highest-leverage-bin native quality is **not estimable**: at least one required N IV]/C IV wavelength overlap has no native support."
        elif overlaps_clear:
            overlap_text = "All highest-leverage N IV]/C IV wavelength-overlap samples are likewise usable under these explicit criteria."
        else:
            overlap_text = "At least one highest-leverage N IV]/C IV wavelength-overlap sample fails the explicit usability criteria."
        text += [
            "## All-nine-exposure quality follow-up",
            "",
            f"The acquisition team subsequently fetched all {batch['exposure_count']} actual native calibrated exposures ({batch['original_bytes']:,} bytes), selected from the verified DJA SLITS list. This experiment requires the exact nine pinned identities, validates actual original hashes/sizes, independently pinned derivative hashes and source SLITS nod positions, and re-evaluates wavelength/DQ/error overlap. {window_text} {overlap_text}",
            "",
            "The nine original exposures are acquired and independently checked. Empty, partial, duplicate and substituted batches cannot certify full acquisition; an empty UV window or influential-bin overlap reports `not_estimable`, rather than vacuously usable. The wavelength/DQ checks do **not** close source-trace mapping, geometry/pathloss, exposure/nod background modelling, source-specific LSF or empirical covariance, and they do not establish independent line detections. All-row wavelength checks are kept distinct from a full reduction or source-trace completeness.",
            "",
        ]
        text += [
            "| High-leverage DJA bin | All-nine native wavelength-overlap pixels | Native usable pixels | DO_NOT_USE | SATURATED |",
            "|---|---:|---:|---:|---:|",
        ]
        for name in ("NIV", "CIV"):
            overlaps = [e["highest_leverage_bin_native_overlap"][name] for e in batch["exposures"]]
            center = overlaps[0]["dja_bin_center_um"]
            total, usable, do_not_use, saturated = [
                sum(o[key] for o in overlaps)
                for key in (
                    "native_pixels_in_bin_all_rows",
                    "native_usable_pixels_in_bin_all_rows",
                    "do_not_use_pixels_all_rows",
                    "saturated_pixels_all_rows",
                )
            ]
            text.append(
                f"| {name}: {center:.6f} µm | {total} | {usable} | {do_not_use} | {saturated} |"
            )
        text += [
            "",
            (
                "These native samples supply no flag-based justification for dropping the influential wavelengths. "
                if overlaps_clear
                else "The influence of quality failures or missing native overlap requires further assessment; the present checks do not justify automatic wavelength rejection. "
            )
            + "The 2026 official native calibration differs from the 2025 DJA processing; mapping exact original coadd contributors and its internal rejection remains an analysis task. Complete matched re-extraction is still needed, while the nine original calibrated exposures are acquired and verified.",
            "",
        ]
    text += [
        "## Rejected shortcuts and next experiments",
        "",
        "Reject equating UV flux ratios with N/C, arbitrary rejection of influential bins, treating repeated extractions as independent data, and substituting the generic R polynomial for a full source-specific calibrated LSF. WR/VMS/SMS/AGN/rotating Pop III are still not distinguished by these data alone.",
        "",
        "Highest value: reconstruct exposure/nod-separated spectra with native DQ and matched pathloss/geometry; compare a full point-source LSF and wavelength calibration nuisance against the Gaussian approximation; calibrate spectral/spatial covariance on independent controls; obtain higher-resolution N IV], N III], C III] and separated He II/O III] for density/ionization/emissivity inference.",
        "",
        "```bash",
        "OPENBLAS_NUM_THREADS=1 python -m tools.jwst.point_resolution",
        "# Include the acquired native slit control explicitly:",
        "OPENBLAS_NUM_THREADS=1 python -m tools.jwst.point_resolution --native-slit data_sources/followup/mom_00002_native_slit.fits",
        "# Reproduce all-nine acquisition and quality follow-up (bounded 600 MiB):",
        "python -m data_pipeline.mom_native_batch --spectrum data_sources/pilot/mom_z14_dja_v4.spec.fits --output /tmp/mom-native --report /tmp/mom-native-batch.json",
        "OPENBLAS_NUM_THREADS=1 python -m tools.jwst.point_resolution --native-batch /tmp/mom-native-batch.json --native-dir /tmp/mom-native",
        "python -m pytest -q tests/test_point_resolution.py tests/test_line_sensitivity.py",
        "```",
        "",
        "The first-round nominal-R JSON is retained unchanged. The new companion JSON omits model-vector duplication and records scenario flux/covariance, redshift profiles, null summaries, all 73 bin omissions under each R curve and native quality support for the acquired nine-exposure set.",
        "",
    ]
    output.with_suffix(".md").write_text("\n".join(text))


def run(
    point_path: Path,
    spectrum: Path,
    nominal_path: Path,
    output: Path,
    native_path: Path | None = None,
    native_batch_path: Path | None = None,
    native_dir: Path | None = None,
    null_draws: int = 1000,
) -> dict[str, Any]:
    exts, metadata = read_extractions(spectrum)
    rw, rr, nominal_metadata = read_resolution(nominal_path)
    pw, pr, point_metadata = read_point_resolution(point_path)
    scenarios = [fit_lines(e, pw, pr, rho=rho) for e in exts for rho in (0.0, 0.25, 0.5)]
    scenarios += [fit_lines(exts[0], pw, pr, intrinsic_fwhm=v) for v in (300.0, 650.0)]
    scenarios += [fit_lines(exts[0], pw, pr, continuum_order=d) for d in (0, 2, 3)]
    scenarios += [
        fit_lines(exts[0], pw, pr, blend=b)
        for b in ("HeII_only", "OIII_only", "alternate_multiplets")
    ]
    scans = [redshift_scan(exts[0], pw, pr, rho=rho, null_draws=null_draws) for rho in (0.0, 0.5)]
    for scan in scans:
        scan["best_fit"] = compact_fit(scan["best_fit"])
    centers = {
        n: np.average(rests, weights=weights) * 1e-4 * 15.44
        for n, (rests, weights) in zip(LINE_NAMES, LINE_COMPONENTS)
    }
    point_leverage = leave_one_bin_out(exts[0], pw, pr)
    result = {
        "schema_version": "mom_point_resolution_v1",
        "metadata": metadata,
        "point_resolution": point_metadata,
        "nominal_resolution": nominal_metadata,
        "resolution_at_group_centers": {
            n: {"nominal": float(np.interp(w, rw, rr)), "point": float(np.interp(w, pw, pr))}
            for n, w in centers.items()
        },
        "nominal_reference_fit": compact_fit(fit_lines(exts[0], rw, rr)),
        "point_source_scenarios": [compact_fit(s) for s in scenarios],
        "point_tied_redshift_width_scans": scans,
        "leave_one_bin_out": {
            "nominal_illuminated": leave_one_bin_out(exts[0], rw, rr),
            "generic_point_source": point_leverage,
        },
        "native_quality_support": native_quality_support(
            native_path, pw, pr, point_leverage, exts[0].wave
        )
        if native_path is not None
        else None,
        "native_batch_quality": native_batch_quality(
            native_batch_path,
            native_dir,
            pw,
            pr,
            point_leverage,
            exts[0].wave,
            spectrum_path=spectrum,
        )
        if native_batch_path is not None and native_dir is not None
        else None,
        "interpretation": "No abundance/yield mechanism inference; generic calibration and sampling leverage only",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if len(serialized.encode()) > 500_000:
        raise ValueError("Follow-up numerical report exceeds bounded 500 KB artifact size")
    output.write_text(serialized)
    render_summary(result, output)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--point-resolution",
        type=Path,
        default=Path("data_sources/followup/unite_point_prism_resolution.csv"),
    )
    parser.add_argument(
        "--spectrum", type=Path, default=Path("data_sources/pilot/mom_z14_dja_v4.spec.fits")
    )
    parser.add_argument(
        "--nominal-resolution",
        type=Path,
        default=Path("data_sources/pilot/jwst_nirspec_prism_disp.fits"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("research_output/mom_z14_point_resolution.json")
    )
    parser.add_argument("--native-slit", type=Path)
    parser.add_argument("--native-batch", type=Path)
    parser.add_argument("--native-dir", type=Path)
    parser.add_argument("--null-draws", type=int, default=1000)
    args = parser.parse_args()
    if args.null_draws < 100:
        parser.error("At least 100 null draws are required")
    if (args.native_batch is None) != (args.native_dir is None):
        parser.error("--native-batch and --native-dir must be supplied together")
    run(
        args.point_resolution,
        args.spectrum,
        args.nominal_resolution,
        args.output,
        native_path=args.native_slit,
        native_batch_path=args.native_batch,
        native_dir=args.native_dir,
        null_draws=args.null_draws,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
