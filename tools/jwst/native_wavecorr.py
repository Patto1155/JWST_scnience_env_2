"""Pinned toy-reference wavelength sensitivity, without changing old reductions.

This narrowly decodes one checksummed ASDF reference, not arbitrary ASDF models.
Optional GWCS packages are needed only for the actual CAL half-pixel derivative;
the frozen derivative and likelihood arrays replay using the standard environment.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import struct
from pathlib import Path

import numpy as np
from astropy.io import fits
from scipy.interpolate import RegularGridInterpolator, interp1d

from .line_sensitivity import read_resolution
from .native_reduction import (
    ROOT,
    covariance_blocks,
    empirical_noise,
    extract_columns,
    fit_native,
    read_inputs,
    replay_report,
    sha256,
    signed_profiles,
)
from .native_spatial_covariance import (
    offtrace_controls,
    spatial_moments,
    stationary_spatial_kernel,
)
from .point_resolution import read_point_resolution

REFERENCE_HASH = "869d4279137b1c7dea5e8bb4b4980d72fd0aa8423c87814050bfa710cd2b58f3"
REFERENCE_BYTES = 16453
REFERENCE = ROOT / "data_sources/followup/jwst_nirspec_wavecorr_0004.asdf"


def plot_wavecorr(report: dict, output: Path) -> None:
    """Show actual predicted shifts and the resulting conditional flux sensitivity."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(2, 1, figsize=(10, 7.5))
    upper, lower = axes
    group = report["predictions"][0]["group"]
    for prediction in report["predictions"]:
        if prediction["group"] != group:
            continue
        table = prediction["prediction"]
        wave = np.array(table["mapping_mean_wavelength_um"])
        offset = np.array(table["mapping_offset_pixels"])
        uv = (wave > 2.15) & (wave < 3.20)
        upper.plot(wave[uv], offset[uv], label=f"Nod{prediction['nod']}")
    upper.set_ylabel("Predicted wavelength correction (detector pixels)")
    upper.set_xlabel("Original wavelength (micron)")
    upper.set_title("MoM-z14: pinned DUMMY / toy wavecorr reference", loc="left")
    upper.legend(frameon=False, ncol=3)
    for i, (key, label, color) in enumerate(
        [
            ("original_wavelength_scenarios", "Original native wavelengths", "#278EA5"),
            ("predicted_corrected_wavelength_scenarios", "Pinned toy prediction", "#C55A11"),
        ]
    ):
        fit = report[key][4]["fit"]
        flux = np.array(fit["fluxes"])
        sigma = np.sqrt(np.diag(fit["flux_covariance"]))
        lower.errorbar(
            np.arange(5) + (i - 0.5) * 0.16,
            flux,
            yerr=sigma,
            fmt="o",
            color=color,
            capsize=4,
            label=label,
        )
    lower.axhline(0, color="#aaaaaa", lw=1)
    lower.set_xticks(np.arange(5), ["N IV]", "C IV", "He II + O III]", "N III]", "C III]"])
    lower.set_ylabel("Line flux (10$^{-20}$ erg s$^{-1}$ cm$^{-2}$)")
    lower.legend(frameon=False, ncol=2)
    figure.text(
        0.02,
        0.01,
        "Point R and empirical row+column noise assumed; conditional1sigma errors. "
        "Planned source offsets; no empirical wavelength / LSF calibration.",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.045, 1, 1))
    figure.savefig(output, dpi=160)
    plt.close(figure)


def decode_blocks(content: bytes) -> list[bytes]:
    """Read this uncompressed ASDF block layout, checking each stored MD5."""
    position = content.find(b"\xd3BLK")
    if position < 0:
        raise ValueError("Missing ASDF blocks")
    blocks = []
    while content[position : position + 4] == b"\xd3BLK":
        header_size = struct.unpack(">H", content[position + 4 : position + 6])[0]
        if header_size != 48:
            raise ValueError("Unsupported ASDF block header")
        flags, compression, allocated, used, size, checksum = struct.unpack(
            ">I4sQQQ16s", content[position + 6 : position + 54]
        )
        if flags != 0 or compression != b"\0" * 4 or allocated != used or used != size:
            raise ValueError("Only exact uncompressed reference blocks are supported")
        data = content[position + 54 : position + 54 + size]
        if len(data) != size or hashlib.md5(data).digest() != checksum:
            raise ValueError("ASDF block checksum/length mismatch")
        blocks.append(data)
        position += 54 + allocated
    if [len(b) for b in blocks] != [3528, 3528, 7056]:
        raise ValueError("Pinned reference block layout changed")
    if content[position:] != b"#ASDF BLOCK INDEX\n%YAML 1.1\n---\n- 2122\n- 5704\n- 9286\n...\n":
        raise ValueError("Pinned reference block index changed")
    return blocks


def read_reference(path: Path = REFERENCE) -> dict:
    content = path.read_bytes()
    if len(content) != REFERENCE_BYTES or hashlib.sha256(content).hexdigest() != REFERENCE_HASH:
        raise ValueError("Wavecorr reference differs from the native CAL pin")
    blocks = decode_blocks(content)
    # Exact descriptors in the SHA-pinned YAML. In particular table is Fortran
    # strided, and coordinate arrays are views of a shared21x21x2 little-endian block.
    wavelength = np.ndarray((21,), "<f8", buffer=blocks[2], strides=(16,)).copy()
    source_xpos = np.ndarray((21,), "<f8", buffer=blocks[2], offset=8, strides=(336,)).copy()
    offset = np.ndarray((21, 21), ">f8", buffer=blocks[1], strides=(8, 168)).copy()
    variance = np.ndarray((21, 21), ">f8", buffer=blocks[0]).copy()
    if not np.allclose(wavelength[[0, -1]], [6e-7, 5.3e-6], rtol=0, atol=1e-20):
        raise ValueError("Reference wavelength axis is not the pinned meter axis")
    if not np.allclose(source_xpos, np.linspace(-0.5, 0.5, 21), rtol=0, atol=1e-15):
        raise ValueError("Reference source position axis changed")
    if not np.all(np.isfinite(offset)) or not np.all(variance == 0.1**2):
        raise ValueError("Reference table/variance contract changed")
    return {
        "wavelength_m": wavelength,
        "source_xpos_fraction_of_MOS_pitch": source_xpos,
        "offset_pixels": offset,
        "variance_values": variance,
    }


def offset_pixels(reference: dict, wavelength_m: np.ndarray, source_xpos: float) -> np.ndarray:
    """Pipeline2.0.1 convention: input meters, slit fraction, output pixels."""
    if not np.isfinite(source_xpos) or not -0.5 <= source_xpos <= 0.5:
        raise ValueError("Source offset must be a finite fraction within the MOS pitch")
    wavelength_m = np.asarray(wavelength_m, dtype=float)
    if not np.all(np.isfinite(wavelength_m)) or np.any(
        (wavelength_m < 0.3e-6) | (wavelength_m > 6e-6)
    ):
        raise ValueError("Wavecorr expects finite wavelength in meters")
    model = RegularGridInterpolator(
        (reference["wavelength_m"], reference["source_xpos_fraction_of_MOS_pitch"]),
        reference["offset_pixels"],
        method="linear",
        bounds_error=False,
        fill_value=None,
    )
    return model(
        np.column_stack([wavelength_m.ravel(), np.full(wavelength_m.size, source_xpos)])
    ).reshape(wavelength_m.shape)


def correct_wavelength(
    wave_um: np.ndarray,
    dispersion_m: np.ndarray,
    reference: dict,
    source_xpos: float,
    *,
    already_corrected: bool,
    offset_delta_pixels: float = 0,
) -> tuple[np.ndarray, dict]:
    """Pipeline mean-column transform with exact or declared approximate dispersion."""
    if already_corrected is not False:
        raise ValueError("Reject wavelength correction when target is already corrected/unknown")
    if wave_um.shape != dispersion_m.shape or wave_um.ndim != 2:
        raise ValueError("Native wavelength and dispersion shapes must agree")
    lam_mean = np.nanmean(wave_um * 1e-6, axis=0)
    dispersion_mean = np.nanmean(dispersion_m, axis=0)
    valid = np.isfinite(lam_mean) & np.isfinite(dispersion_mean)
    if np.any((dispersion_mean[valid] <= 0) | (dispersion_mean[valid] >= 1e-6)):
        raise ValueError("Dispersion must be positive and supplied in meters per pixel")
    original = lam_mean[valid]
    if len(original) < 3 or np.any(np.diff(original) <= 0):
        raise ValueError("Mean native wavelength grid must be ordered")
    delta = offset_pixels(reference, original, source_xpos) + offset_delta_pixels
    corrected = original + delta * dispersion_mean[valid]
    if not np.all(np.isfinite(corrected)) or np.any(np.diff(corrected) <= 0):
        raise ValueError("Noninvertible wavelength-correction mapping")
    transform = interp1d(original, corrected, bounds_error=False, fill_value="extrapolate")
    result = np.asarray(transform(wave_um * 1e-6)) * 1e6
    return result, {
        "source_xpos_fraction_of_MOS_pitch": source_xpos,
        "mapping_mean_wavelength_um": (original * 1e6).tolist(),
        "mapping_offset_pixels": delta.tolist(),
        "mapping_delta_wavelength_um": ((corrected - original) * 1e6).tolist(),
        "reference_extrapolated_column_count": int(
            np.sum(
                (original < reference["wavelength_m"][0])
                | (original > reference["wavelength_m"][-1])
            )
        ),
        "double_application_guard": "target WAVECOR must be False",
    }


def read_wcs_dispersion(path: Path, native_wave: np.ndarray) -> tuple[np.ndarray, dict]:
    """Evaluate pinned CAL's original GWCS at x±0.5, not a generic R model."""
    import asdf

    with fits.open(path, memmap=False) as hdul:
        target = next(
            h for h in hdul if h.name == "SCI" and h.header.get("SRCNAME") == "5224_277193"
        )
        header, primary = target.header, hdul[0].header
        if header.get("WAVECOR") is not False:
            raise ValueError("Target wavelength correction is already applied or unknown")
        if primary["R_WAVCOR"] != "crds://jwst_nirspec_wavecorr_0004.asdf":
            raise ValueError("CAL selected a different wavecorr reference")
        content = hdul["ASDF"].data["ASDF_METADATA"][0].tobytes()
    with asdf.open(io.BytesIO(content), lazy_load=True, lazy_tree=True) as tree:
        targets = [s for s in tree["slits"] if s.get("source_name") == "5224_277193"]
        if len(targets) != 1:
            raise ValueError("ASDF target slit identity ambiguous")
        wcs = targets[0]["meta"]["wcs"]
        if "wavecorr_frame" in wcs.available_frames:
            raise ValueError("Original WCS already contains a wavecorr transform")
        y, x = np.indices(native_wave.shape, dtype=float)
        check = np.asarray(wcs(x, y)[2])
        finite = np.isfinite(native_wave) & np.isfinite(check)
        if not np.array_equal(np.isfinite(native_wave), np.isfinite(check)):
            raise ValueError("Native WAVELENGTH and original WCS valid pixels differ")
        difference = float(np.max(np.abs(check[finite] - native_wave[finite])))
        if difference > 3e-7:
            raise ValueError("GWCS wavelength differs beyond float32 native storage tolerance")
        dispersion = (np.asarray(wcs(x + 0.5, y)[2]) - np.asarray(wcs(x - 0.5, y)[2])) * 1e-6
        metadata = {
            "target_WAVECOR": False,
            "primary_S_WAVCOR": primary["S_WAVCOR"],
            "reference": primary["R_WAVCOR"],
            "crds_context": primary["CRDS_CTX"],
            "CAL_VER": primary["CAL_VER"],
            "wcs_available_frames": list(wcs.available_frames),
            "maximum_native_vs_GWCS_wavelength_difference_um": difference,
            "dispersion_method": (
                "original CAL GWCS(lambda(x+0.5,y)-lambda(x-0.5,y))*1e-6 meters/pixel"
            ),
        }
    return dispersion, metadata


def run(native_dir: Path, baseline_path: Path, spatial_path: Path, output: Path) -> dict:
    baseline = json.loads(baseline_path.read_text())
    spatial = json.loads(spatial_path.read_text())
    baseline_replay = replay_report(baseline_path)
    data, metadata = read_inputs(native_dir, ROOT / "data_sources/pilot/mom_z14_dja_v4.spec.fits")
    geometry = baseline["geometry"]
    selected = np.array(baseline["selected_native_columns"])
    for d in data:
        d["trace_refined"] = d["trace_seed"] + geometry["offset_pixels"]
        d["sigma_refined"] = geometry["sigma_pixels"]
    profile = signed_profiles(data, geometry["sigma_pixels"], geometry["offset_pixels"])
    flux, operators, _ = extract_columns(data, profile)
    blocks, _ = covariance_blocks(data, operators)
    spectral_kernel, noise = empirical_noise(data, geometry, selected)
    controls = offtrace_controls(data, geometry, selected)
    spatial_kernel, _ = stationary_spatial_kernel(
        spatial_moments(controls)[0], data[0]["wave"].shape[0]
    )
    spatial_blocks, _ = covariance_blocks(data, operators, spatial_kernel)
    with np.load(
        baseline_path.parent / baseline["compact_native_replay"]["filename"], allow_pickle=False
    ) as replay:
        if not np.allclose(flux[:, selected], replay["flux"], rtol=0, atol=1e-12):
            raise ValueError("Actual extraction does not reproduce frozen source amplitudes")
        if not np.allclose(blocks[selected], replay["covariance_blocks"], rtol=0, atol=1e-12):
            raise ValueError("Actual covariance does not reproduce frozen source likelihood")
    rw, rr, _ = read_resolution(ROOT / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
    pw, pr, _ = read_point_resolution(
        ROOT / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    configurations = [
        ("nominal_formal_shared", rw, rr, blocks, None, 1),
        ("point_formal_shared", pw, pr, blocks, None, 1),
        (
            "nominal_empirical_spectral_transport",
            rw,
            rr,
            blocks,
            spectral_kernel,
            noise["pooled_scale_squared"],
        ),
        (
            "point_empirical_spectral_transport",
            pw,
            pr,
            blocks,
            spectral_kernel,
            noise["pooled_scale_squared"],
        ),
        (
            "point_spatial_spectral_transport",
            pw,
            pr,
            spatial_blocks,
            spectral_kernel,
            noise["pooled_scale_squared"],
        ),
        (
            "nominal_spatial_spectral_transport",
            rw,
            rr,
            spatial_blocks,
            spectral_kernel,
            noise["pooled_scale_squared"],
        ),
    ]
    unchanged = []
    for i, (name, w, r, b, k, scale) in enumerate(configurations):
        fit = fit_native(data, flux, b, selected, w, r, kernel=k, noise_scale=scale)
        original = baseline["scenarios"][i]["fit"] if i < 4 else spatial["scenarios"][i - 4]["fit"]
        error = float(np.max(np.abs(np.array(fit["fluxes"]) - original["fluxes"])))
        if error > 1e-10:
            raise ValueError("Frozen original wavelength scenarios failed numerical replay")
        unchanged.append({"name": name, "fit": fit, "maximum_saved_flux_difference": error})
    reference = read_reference()
    dispersions, predictions, corrected_data = [], [], []
    for d in data:
        dispersion, audit = read_wcs_dispersion(native_dir / d["filename"], d["wave"])
        corrected, prediction = correct_wavelength(
            d["wave"], dispersion, reference, d["source_xpos"], already_corrected=False
        )
        dispersions.append(dispersion)
        corrected_data.append({**d, "wave": corrected})
        uv = prediction["mapping_mean_wavelength_um"]
        uv_mask = (np.array(uv) > 2.15) & (np.array(uv) < 3.20)
        shifts = np.array(prediction["mapping_offset_pixels"])[uv_mask]
        prediction["uv_offset_pixels_min_median_max"] = [
            float(np.min(shifts)),
            float(np.median(shifts)),
            float(np.max(shifts)),
        ]
        predictions.append(
            {
                "filename": d["filename"],
                "group": d["group"],
                "nod": d["nod"],
                "audit": audit,
                "prediction": prediction,
            }
        )
    changed = [
        {
            "name": name,
            "fit": fit_native(corrected_data, flux, b, selected, w, r, kernel=k, noise_scale=scale),
        }
        for name, w, r, b, k, scale in configurations
    ]
    alternatives = []
    for name, position_shift, reference_shift, use_gradient in [
        ("source_offset_minus_0p05_MOS_pitch", -0.05, 0, False),
        ("source_offset_plus_0p05_MOS_pitch", 0.05, 0, False),
        ("coherent_reference_minus_0p1_pixel", 0, -0.1, False),
        ("coherent_reference_plus_0p1_pixel", 0, 0.1, False),
        ("native_integer_grid_dispersion", 0, 0, True),
    ]:
        changed_data = []
        for d, dispersion in zip(data, dispersions):
            if use_gradient:
                dispersion = np.gradient(d["wave"], axis=1) * 1e-6
            new_wave, _ = correct_wavelength(
                d["wave"],
                dispersion,
                reference,
                d["source_xpos"] + position_shift,
                already_corrected=False,
                offset_delta_pixels=reference_shift,
            )
            changed_data.append({**d, "wave": new_wave})
        alternatives.append(
            {
                "name": name,
                "fit": fit_native(
                    changed_data,
                    flux,
                    spatial_blocks,
                    selected,
                    pw,
                    pr,
                    kernel=spectral_kernel,
                    noise_scale=noise["pooled_scale_squared"],
                ),
                "scope": (
                    "Assumed coherent sensitivity, not a posterior error or independent calibration"
                ),
            }
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    compact_path = output.with_suffix(".npz")
    np.savez_compressed(
        compact_path,
        native_wave=np.array([d["wave"] for d in data]),
        corrected_wave=np.array([d["wave"] for d in corrected_data]),
        dispersion_m=np.array(dispersions),
        native_good=np.array([d["good"] for d in data]),
        trace=np.array([d["trace_refined"] for d in data]),
        sigma=np.array([geometry["sigma_pixels"]]),
        source_xpos=np.array([d["source_xpos"] for d in data]),
        selected_columns=selected,
        flux=flux[:, selected],
        covariance_blocks=blocks[selected],
        spatial_covariance_blocks=spatial_blocks[selected],
        spectral_kernel=spectral_kernel,
        noise_scale_squared=np.array([noise["pooled_scale_squared"]]),
    )
    result = {
        "schema_version": 1,
        "kind": "pinned_toy_wavecorr_sensitivity",
        "input_baseline_sha256": sha256(baseline_path),
        "input_spatial_report_sha256": sha256(spatial_path),
        "baseline_compact_replay": baseline_replay,
        "native_cal_metadata": metadata,
        "reference_receipt_sha256": sha256(
            ROOT / "data_sources/followup/mom_wavecorr_receipt.json"
        ),
        "reference": {
            "sha256": REFERENCE_HASH,
            "filename": REFERENCE.name,
            "internal_filename": "jwst_nirspec_wavecorr_0002.asdf",
            "pedigree": "DUMMY",
            "description": "MOS simple toy model",
            "coordinate_order": ["wavelength_m", "source_xpos_fraction_of_MOS_pitch"],
            "output_units": "detector_pixels",
            "reference_pitch_width_m": 0.00010442,
            "variance_all_values": 0.1**2,
            "variance_units_schema": (
                "Called variance of zero-point offset; schema prose says detector pixel, "
                "without explicitly squared units"
            ),
            "variance_interpretation": (
                "Metadata, not validated source-specific calibrated uncertainty; "
                "reference supplies no covariance. Coherent0.1pixel sensitivity assumes "
                "square-root interpretation of0.01"
            ),
        },
        "predictions": predictions,
        "original_wavelength_scenarios": unchanged,
        "predicted_corrected_wavelength_scenarios": changed,
        "assumed_sensitivities": alternatives,
        "compact_replay": {
            "filename": compact_path.name,
            "bytes": compact_path.stat().st_size,
            "sha256": sha256(compact_path),
        },
        "code_receipt": {
            "filename": "tools/jwst/native_wavecorr.py",
            "sha256": sha256(Path(__file__)),
        },
        "interpretation": [
            (
                "Versioned point-source wavelength prediction, not empirical wavelength "
                "or spectral LSF calibration"
            ),
            (
                "Source offsets from planned CAL metadata, not a measured actual shutter "
                "placement; red cross-dispersion trace does not measure this "
                "dispersion-direction position"
            ),
            (
                "Original GWCS already includes geometrical source position; wavecorr "
                "adds the separate diffraction zero-point correction once"
            ),
            (
                "Science amplitudes, native masks, extraction/profile/pathloss and "
                "shared-noise covariance frozen; only native wavelength templates "
                "and fnu conversion change"
            ),
            (
                "Not a full spec2 reprocessing; wavelength dependence of "
                "pathloss/calibration is not regenerated"
            ),
            (
                "Fixedz14.44, zero intrinsic width and legacy fixed multiplet weights; "
                "no elemental abundance or independent detection claim"
            ),
            (
                "Generic point/nominal R remains an assumption; a zero-point prediction "
                "does not calibrate source-specific LSF"
            ),
        ],
    }
    plot_path = output.with_suffix(".png")
    plot_wavecorr(result, plot_path)
    result["figure"] = {"filename": plot_path.name, "sha256": sha256(plot_path)}
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def load_wavecorr_replay(report_path: Path, *, corrected: bool = True) -> dict:
    """Expose wavelength hypotheses and unchanged derived likelihood for later fits."""
    report = json.loads(report_path.read_text())
    receipt = report["compact_replay"]
    path = report_path.parent / receipt["filename"]
    if path.stat().st_size != receipt["bytes"] or sha256(path) != receipt["sha256"]:
        raise ValueError("Wavecorr compact likelihood differs from receipt")
    with np.load(path, allow_pickle=False) as saved:
        arrays = {name: saved[name].copy() for name in saved.files}
    selected = arrays["selected_columns"]
    original = arrays["native_wave"]
    if original.shape != (9, 28, 423) or arrays["corrected_wave"].shape != original.shape:
        raise ValueError("Wavecorr replay geometry changed")
    reference = read_reference()
    for wave, dispersion, source_xpos, frozen in zip(
        original, arrays["dispersion_m"], arrays["source_xpos"], arrays["corrected_wave"]
    ):
        prediction, _ = correct_wavelength(
            wave, dispersion, reference, float(source_xpos), already_corrected=False
        )
        if not np.allclose(prediction, frozen, rtol=0, atol=1e-14, equal_nan=True):
            raise ValueError("Corrected wavelength snapshot fails pinned prediction replay")
    flux = np.full((9, original.shape[2]), np.nan)
    flux[:, selected] = arrays["flux"]
    formal = np.zeros((original.shape[2], 9, 9))
    spatial = np.zeros_like(formal)
    formal[selected] = arrays["covariance_blocks"]
    spatial[selected] = arrays["spatial_covariance_blocks"]
    wave_grid = arrays["corrected_wave"] if corrected else original
    data = [
        {
            "wave": wave,
            "good": good,
            "trace_refined": trace,
            "trace_seed": trace,
            "sigma_refined": float(arrays["sigma"][0]),
            "source_xpos": float(position),
        }
        for wave, good, trace, position in zip(
            wave_grid, arrays["native_good"], arrays["trace"], arrays["source_xpos"]
        )
    ]
    return {
        "data": data,
        "flux": flux,
        "covariance_blocks": formal,
        "spatial_covariance_blocks": spatial,
        "selected": selected,
        "spectral_kernel": arrays["spectral_kernel"],
        "noise_scale_squared": float(arrays["noise_scale_squared"][0]),
        "wavelength_hypothesis": "pinned_toy_prediction" if corrected else "original_native",
        "source_noise_frozen": True,
    }


def replay_wavecorr(report_path: Path) -> dict:
    """Replay saved wavelength prediction and twelve fits; no raw WCS rerun."""
    report = json.loads(report_path.read_text())
    rw, rr, _ = read_resolution(ROOT / "data_sources/pilot/jwst_nirspec_prism_disp.fits")
    pw, pr, _ = read_point_resolution(
        ROOT / "data_sources/followup/unite_point_prism_resolution.csv"
    )
    comparisons = []
    for corrected, key in [
        (False, "original_wavelength_scenarios"),
        (True, "predicted_corrected_wavelength_scenarios"),
    ]:
        saved = load_wavecorr_replay(report_path, corrected=corrected)
        formal, spatial = saved["covariance_blocks"], saved["spatial_covariance_blocks"]
        kernel, scale = saved["spectral_kernel"], saved["noise_scale_squared"]
        configurations = [
            (rw, rr, formal, None, 1),
            (pw, pr, formal, None, 1),
            (rw, rr, formal, kernel, scale),
            (pw, pr, formal, kernel, scale),
            (pw, pr, spatial, kernel, scale),
            (rw, rr, spatial, kernel, scale),
        ]
        for original, (w, r, blocks, k, s) in zip(report[key], configurations):
            fit = fit_native(
                saved["data"],
                saved["flux"],
                blocks,
                saved["selected"],
                w,
                r,
                kernel=k,
                noise_scale=s,
            )
            flux_difference = float(
                np.max(np.abs(np.array(fit["fluxes"]) - original["fit"]["fluxes"]))
            )
            covariance_difference = float(
                np.max(
                    np.abs(np.array(fit["flux_covariance"]) - original["fit"]["flux_covariance"])
                )
            )
            if flux_difference > 1e-10 or covariance_difference > 1e-9:
                raise ValueError("Saved wavelength scenario fails numerical likelihood replay")
            comparisons.append(
                {
                    "hypothesis": key,
                    "scenario": original["name"],
                    "maximum_flux_difference": flux_difference,
                    "maximum_covariance_difference": covariance_difference,
                }
            )
    return {
        "report_sha256": sha256(report_path),
        "comparisons": comparisons,
        "scope": (
            "Compact numerical replay of frozen original-WCS derivatives and derived "
            "likelihood; not original ASDF/GWCS or raw-pixel validation"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--native-dir", type=Path)
    inputs.add_argument("--replay-report", type=Path)
    parser.add_argument(
        "--baseline-report", type=Path, default=ROOT / "research_output/mom_native_reduction.json"
    )
    parser.add_argument(
        "--spatial-report",
        type=Path,
        default=ROOT / "research_output/mom_native_spatial_covariance.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.replay_report:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(replay_wavecorr(args.replay_report), indent=2) + "\n")
    else:
        run(args.native_dir, args.baseline_report, args.spatial_report, args.output)


if __name__ == "__main__":
    main()
