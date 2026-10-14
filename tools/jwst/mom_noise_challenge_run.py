"""Actual ranged-pixel MoM frozen noise challenge; no fullfile hash certification."""

from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import signal
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from astropy.io import fits

from tools.jwst.empirical_noise_challenge import (
    parity_calibration,
    reference_contrast,
    row_controls,
)
from tools.jwst.native_measurement_validation import (
    serial_fit,
    solve_measurement,
    transported_covariance,
)
from tools.jwst.native_rate_noise import donor_covariance, rate_signed_response
from tools.jwst.native_reduction import ROOT, extract_columns, mixing_matrix, signed_profiles
from tools.jwst.native_row_response import row_source_design
from tools.jwst.native_spatial_covariance import stationary_spatial_kernel
from tools.jwst.point_resolution import read_point_resolution
from tools.jwst.ranged_fits import HeaderRangedFITS, RangeBudget, RangedFITS


def ranged_inputs(
    budget: RangeBudget, *, coalesced_cal: bool = False
) -> tuple[list[dict], list[dict], list[dict]]:
    inventory = json.loads((ROOT / "data_sources/followup/mom_native_inventory.json").read_text())
    manifest = json.loads((ROOT / "data_sources/followup/mom_rate_noise_manifest.json").read_text())
    rate_pins = {x["filename"]: x for x in manifest["products"]}
    from tools.jwst.line_sensitivity import SOURCE_HASH
    from tools.jwst.native_reduction import sha256

    spectrum = ROOT / "data_sources/pilot/mom_z14_dja_v4.spec.fits"
    if sha256(spectrum) != SOURCE_HASH:
        raise ValueError("source SLITS spectrum differs from pinned identity")
    with fits.open(spectrum) as hdul:
        slits = hdul["SLITS"].data.copy()
        rows = {str(x["filename"]): x for x in slits}

    def read_pair(pin):
        row = rows[pin["source_slits_filename"]]
        stream = HeaderRangedFITS(pin["url"], pin["expected_bytes"], budget)
        if coalesced_cal:
            remote = stream
            stream = io.BytesIO(remote._fetch(0, remote.size))
            remote.close()
        with fits.open(stream, memmap=False) as hdul:
            primary = dict(hdul[0].header)
            sci = next(
                (h for h in hdul if h.name == "SCI" and h.header.get("SRCNAME") == "5224_277193")
            )
            header = dict(sci.header)
            version = header["EXTVER"]
            names = (
                "SCI",
                "ERR",
                "WAVELENGTH",
                "PATHLOSS_PS",
                "PATHLOSS_UN",
                "BARSHADOW",
                "VAR_POISSON",
                "VAR_RNOISE",
                "VAR_FLAT",
                "DQ",
            )
            arrays = {name: np.array(hdul[name, version].data, dtype=float) for name in names}
            offsets = {
                name: {
                    key: hdul[name, version].fileinfo()[key]
                    for key in ("hdrLoc", "datLoc", "datSpan")
                }
                for name in names
            }
            text = hdul["ASDF"].data["ASDF_METADATA"][0].tobytes().decode("utf-8", errors="replace")
        stream.close()
        if any((x.shape != (28, 423) for x in arrays.values())):
            raise ValueError("CAL target shape differs")
        if (
            primary["CAL_VER"],
            primary["CRDS_CTX"],
            primary["S_BKDSUB"],
            header["SRCTYPE"],
            header["PTHLOSS"],
            header["BARSHDW"],
            header["BUNIT"],
        ) != ("2.0.1", "jwst_1535.pmap", "COMPLETE", "EXTENDED", "UNIFORM", True, "MJy/sr"):
            raise ValueError("CAL identity/calibration differs from frozen design")
        if abs(header["SRCRA"] - 150.0933255) > 1e-07 or abs(header["SRCDEC"] - 2.2731627) > 1e-07:
            raise ValueError("CAL source coordinate differs")
        if (header["SLTSTRT1"], header["SLTSTRT2"]) != (440, 1293):
            raise ValueError("CAL detector origin differs")
        match = re.search("Step bkg_subtract running with args.*?\\[(.*?)\\]\\)", text, re.S)
        contributors = (
            re.findall("jw\\d{11}_\\d{5}_\\d{5}_nrs2_rate\\.fits", match.group(1)) if match else []
        )
        if len(set(contributors)) != 2:
            raise ValueError("actual background contributor incidence unavailable")
        xi = (np.arange(423) + header["SLTSTRT1"] - row["xstart"] - row["xsize"] / 2) / row["xsize"]
        trace = np.polyval([row["trace_c0"], row["trace_c1"], row["trace_c2"]], xi)
        trace += row["ystart"] - header["SLTSTRT2"]
        conversion = (
            header["PIXAR_SR"] * 1000000000000.0 * arrays["PATHLOSS_UN"] * arrays["BARSHADOW"]
        )
        good = arrays["DQ"].astype(np.uint32) & 3 == 0
        for name in names:
            good &= np.isfinite(arrays[name])
        for name in ("ERR", "WAVELENGTH", "PATHLOSS_PS", "PATHLOSS_UN", "BARSHADOW"):
            good &= arrays[name] > 0
        target = {
            "filename": pin["filename"],
            "group": primary["VISITGRP"],
            "nod": int(row["position_number"]),
            "background_contributors": contributors,
            "science": arrays["SCI"] * conversion,
            "variance": (arrays["ERR"] * conversion) ** 2,
            "point_pathloss": arrays["PATHLOSS_PS"],
            "wave": arrays["WAVELENGTH"],
            "trace_seed": trace,
            "good": good,
        }
        rate_pin = rate_pins[pin["filename"].replace("_cal", "_rate")]
        stream = RangedFITS(rate_pin["url"], rate_pin["bytes"], budget)
        with fits.open(stream, memmap=False) as hdul:
            rate_primary = dict(hdul[0].header)
            if (
                rate_primary["CAL_VER"],
                rate_primary["CRDS_CTX"],
                rate_primary["DETECTOR"],
                rate_primary["SUBSTRT1"],
                rate_primary["SUBSTRT2"],
                hdul["SCI"].header["BUNIT"],
            ) != ("2.0.1", "jwst_1535.pmap", "NRS2", 1, 1, "DN/s"):
                raise ValueError("RATE identity/units/context differ")
            rate = {
                name: np.array(hdul[name].section[1292:1320, 439:862], dtype=float)
                for name in ("SCI", "ERR", "VAR_POISSON", "VAR_RNOISE", "DQ")
            }
        stream.close()
        if rate_primary["EXPSTART"] != primary["EXPSTART"]:
            raise ValueError("RATE/CAL exposure mismatch")
        gain = np.sqrt(arrays["VAR_RNOISE"] * conversion**2 / rate["VAR_RNOISE"])
        valid = good & np.isfinite(gain) & (gain > 0) & np.isfinite(rate["ERR"]) & (rate["ERR"] > 0)
        pixel = {
            "rate": rate,
            "gain": gain,
            "flat": arrays["VAR_FLAT"] * conversion**2,
            "valid": valid,
        }
        identity = {
            "cal": pin["filename"],
            "rate": rate_pin["filename"],
            "mjd": primary["EXPSTART"],
            "fullfile_hash_verified": False,
            "source_deg": [header["SRCRA"], header["SRCDEC"]],
            "target_HDU_offsets": offsets,
        }
        return (target, pixel, identity)

    with ThreadPoolExecutor(max_workers=4) as pool:
        triples = list(pool.map(read_pair, inventory["products"]))
    data, pixels, identities = map(list, zip(*triples))
    for group in sorted({d["group"] for d in data}):
        members = [i for i, d in enumerate(data) if d["group"] == group]
        if sorted((data[i]["nod"] for i in members)) != [1, 2, 3]:
            raise ValueError("incomplete three-nod group")
        rates = {data[i]["filename"].replace("_cal", "_rate") for i in members}
        common = np.all([pixels[i]["valid"] for i in members], axis=0)
        for i in members:
            if set(data[i]["background_contributors"]) != rates - {
                data[i]["filename"].replace("_cal", "_rate")
            }:
                raise ValueError("background incidence differs")
            data[i]["good"] &= common
    return (data, pixels, identities)


def red_window_indices(waves: np.ndarray) -> np.ndarray:
    """Frozen windows on finite positive wavelength coverage, never missing=zero."""
    good = np.isfinite(waves) & (waves > 0)
    count = good.sum(axis=(0, 1))
    wave = np.divide(
        np.where(good, waves, 0).sum(axis=(0, 1)),
        count,
        out=np.full(count.shape, np.nan, dtype=float),
        where=count > 0,
    )
    return np.flatnonzero(
        (wave >= 3.35) & (wave <= 3.6)
        | (wave >= 3.9) & (wave <= 4.1)
        | (wave >= 4.25) & (wave <= 4.45)
    )


def run(
    output: Path,
    compact: Path,
    *,
    calibration_verdict: str,
    cancel_event: threading.Event | None = None,
    cap_bytes: int = 300_000_000,
    geometric_wavelength_prior: bool = False,
    freeze_commit: str = "d50fa97",
    coalesced_cal: bool = False,
) -> dict:
    if cap_bytes <= 0 or cap_bytes > 1_610_612_736:
        raise ValueError("cap must be positive and within authorized 1.5 GiB")
    if shutil.disk_usage(ROOT).free < 5_000_000_000:
        raise ValueError("less than required 5 GB free")
    budget = RangeBudget(
        cap=cap_bytes,
        journal=output.with_name(output.stem + "_ranges.jsonl"),
        cancel_event=cancel_event,
    )
    try:
        data, pixels, identities = ranged_inputs(budget, coalesced_cal=coalesced_cal)
        baseline = json.loads((ROOT / "research_output/mom_native_reduction.json").read_text())
        geom = baseline["geometry"]
        selected = np.array(baseline["selected_native_columns"], dtype=int)
        for d in data:
            d["trace_refined"] = d["trace_seed"] + geom["offset_pixels"]
            d["sigma_refined"] = geom["sigma_pixels"]
        profiles = signed_profiles(data, geom["sigma_pixels"], geom["offset_pixels"])
        flux, operators, _ = extract_columns(data, profiles)
        old = json.loads((ROOT / "research_output/mom_native_rate_noise.json").read_text())
        fixed_spatial, _ = stationary_spatial_kernel(
            old["empirical_noise_after_donor_normalization"][
                "measured_spatial_lag_correlations_0_to_3"
            ],
            28,
        )
        blocks, post, closure = (np.zeros((423, 9, 9)), np.zeros((9, 28, 423)), [])
        for group in sorted({d["group"] for d in data}):
            members = [i for i, d in enumerate(data) if d["group"] == group]
            valid = np.all([pixels[i]["valid"] for i in members], axis=0)
            raw = np.where(
                valid[None], np.array([pixels[i]["rate"]["ERR"] ** 2 for i in members]), 0
            )
            gains = np.where(valid[None], np.array([pixels[i]["gain"] for i in members]), 0)
            flat = np.where(valid[None], np.array([pixels[i]["flat"] for i in members]), 0)
            if np.any((operators[members] != 0) & ~valid[None]):
                raise ValueError("unsupported extraction weights")
            blocks[:, np.array(members)[:, None], members] = donor_covariance(
                raw, gains, operators[members], flat, fixed_spatial
            )
            post[members] = gains**2 * np.einsum("ik,krc->irc", mixing_matrix() ** 2, raw) + flat
            source = np.where(valid[None], np.array([pixels[i]["rate"]["SCI"] for i in members]), 0)
            predicted = gains * np.einsum("ik,krc->irc", mixing_matrix(), source)
            observed = np.array([data[i]["science"] for i in members])
            normalized = (predicted - observed) / np.sqrt(
                np.array([data[i]["variance"] for i in members])
            )
            maximum = float(np.max(np.abs(normalized[np.broadcast_to(valid, observed.shape)])))
            closure.append({"group": group, "max_CAL_sigma": maximum})
            if maximum > 0.0001:
                raise ValueError("fresh RATE/CAL SCI closure fails")
        traces = np.array([d["trace_refined"] for d in data])
        blank = np.all(np.abs(np.arange(28)[None, :, None] - traces[:, None]) > 2.5, axis=0)
        mask = np.array([d["good"] for d in data])[:, :, selected] & blank[None, :, selected]
        controls = row_controls(
            np.array([d["science"] for d in data])[:, :, selected], post[:, :, selected], mask
        )
        cal = parity_calibration(controls, [d["group"] for d in data], selected)
        atomic = json.loads(
            (ROOT / "research_output/mom_atomic_grid_niv_doublet_v2.json").read_text()
        )
        templates = json.loads(
            (ROOT / "research_output/mom_multiplet_components_niv_doublet_v2.json").read_text()
        )
        index = next(
            (
                i
                for i, c in enumerate(atomic["records"])
                if c["temperature_K"] == 20000 and c["electron_density_cm3"] == 1000
            )
        )
        emissivity = atomic["records"][index]["emissivity_erg_cm3_s"]
        components = [
            (x["vacuum_wavelengths_A"], x["normalized_weights"])
            for x in templates["records"][index]["components"]
        ]
        rw, rr, _ = read_point_resolution(
            ROOT / "data_sources/followup/unite_point_prism_resolution.csv"
        )
        positive = row_source_design(
            data, rw, rr, components, geom["sigma_pixels"], geom["offset_pixels"]
        )
        gains = np.array([p["gain"] for p in pixels])
        design = rate_signed_response(data, positive, gains, operators, selected)
        covariance = transported_covariance(
            blocks, selected, cal["kernel"], cal["training_scale_squared"], list(range(9))
        )
        # Preserve compact normalized measurement inputs before inference/control code.
        compact.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            compact.with_name(compact.stem + "_normalized.npz"),
            controls=controls,
            selected_columns=selected,
            source_flux=flux[:, selected],
            transported_covariance=covariance,
            source_wave=np.array([d["wave"] for d in data]),
            source_good=np.array([d["good"] for d in data]),
            source_point_pathloss=np.array([d["point_pathloss"] for d in data]),
            source_trace_seed=np.array([d["trace_seed"] for d in data]),
            groups=np.array([d["group"] for d in data]),
            gains=gains,
            operators=operators,
            resolution_wave=rw,
            resolution=rr,
            components_json=np.array(json.dumps(components)),
            geometry_json=np.array(json.dumps(geom)),
            emissivity_json=np.array(json.dumps(emissivity)),
        )
        marginal = None
        nuisance_designs = None
        if geometric_wavelength_prior:
            from tools.jwst.wavelength_mixture import (
                marginal_coefficient_moments,
                shift_row_wavelength,
            )

            nodes, prior_weights = np.polynomial.legendre.leggauss(41)
            prior_weights /= 2
            nuisance_designs = []
            for node in nodes:
                shifted = [dict(d, wave=shift_row_wavelength(d["wave"], node - 0.25)) for d in data]
                node_positive = row_source_design(
                    shifted, rw, rr, components, geom["sigma_pixels"], geom["offset_pixels"]
                )
                nuisance_designs.append(
                    rate_signed_response(shifted, node_positive, gains, operators, selected)
                )
            nuisance_designs = np.array(nuisance_designs)
            marginal = marginal_coefficient_moments(
                nuisance_designs, covariance, flux[:, selected].T.reshape(-1), prior_weights
            )
        fitted = serial_fit(
            solve_measurement(design, covariance, flux[:, selected].T.reshape(-1)), emissivity, 1
        )
        if marginal is not None:
            fitted = serial_fit(marginal, emissivity, 1)
            fitted["method"] = (
                "Fieller on marginalized coefficient moments; approximate mixture coverage"
            )
            fitted["node_fits"] = [
                serial_fit(
                    {"coefficients": m, "covariance": v, "chi2": c, "dof": marginal["dof"]},
                    emissivity,
                    1,
                )
                for m, v, c in zip(
                    marginal["node_coefficients"],
                    marginal["node_covariance"],
                    marginal["node_chi2"],
                    strict=True,
                )
            ]
            fitted["wavelength_prior"] = {
                "kind": "assumed uniform slit-position geometric bound",
                "centering_detector_pixels": [-1, 1],
                "global_detector_pixel_correction": -0.25,
                "common_across_exposures": True,
                "nodes": nodes.tolist(),
                "prior_weights": prior_weights.tolist(),
                "posterior_weights": marginal["weights"].tolist(),
                "empirical_prior_validated": False,
            }
        ratio = fitted["ionic_N_over_C"]
        direct = reference_contrast(
            ratio["scaled_numerator"],
            ratio["scaled_denominator"],
            np.array(ratio["scaled_covariance"]),
        )
        red = red_window_indices(np.array([d["wave"] for d in data]))
        separation = np.abs(red[:, None] - red[None, :])
        kernel = np.zeros_like(separation, dtype=float)
        for lag, corr in enumerate(cal["spectral_lag_correlations"]):
            kernel[separation == lag] = corr * (1 - lag / 4)
        kernel = (1 - cal["shrinkage"]) * kernel + cal["shrinkage"] * np.eye(len(red))
        if len(red) < 30:
            red_check = {
                "native_columns": len(red),
                "passes": False,
                "reason": "frozen minimum30 red-continuum columns unmet",
            }
        else:
            red_cov = transported_covariance(
                blocks, red, kernel, cal["training_scale_squared"], list(range(9))
            )
            red_design = rate_signed_response(data, positive, gains, operators, red)[:, :2]
            red_fit = solve_measurement(red_design, red_cov, flux[:, red].T.reshape(-1))
            red_reduced = red_fit["chi2"] / red_fit["dof"]
            red_check = {
                "native_columns": len(red),
                "chi2": red_fit["chi2"],
                "dof": red_fit["dof"],
                "reduced_chi2": red_reduced,
                "passes": 0.7 <= red_reduced <= 1.3,
            }
        kernel_array = cal.pop("kernel")
        np.savez_compressed(
            compact,
            controls=controls,
            selected_columns=selected,
            spectral_kernel=kernel_array,
            covariance_blocks=blocks[selected],
            source_flux=flux[:, selected],
            design=design,
            nuisance_designs=nuisance_designs if nuisance_designs is not None else np.empty((0,)),
            emissivity_json=np.array(json.dumps(emissivity)),
            transported_covariance=covariance,
        )
        result = {
            "status": "measured_conditional",
            "freeze_commit": freeze_commit,
            "first_data_access_utc": budget.first_access,
            "calibration_verdict": calibration_verdict,
            "identities": identities,
            "calibration": cal,
            "source_red_check": red_check,
            "fit": fitted,
            "independent_reference_contrast": direct,
            "RATE_CAL_closure": closure,
            "source_noise_validated": False,
            "all_practical_controls_pass": bool(
                cal["control_diagnostics_pass"] and red_check["passes"]
            ),
            "elemental_inference": False,
            "fullfile_hash_verified": False,
        }
    except BaseException as error:
        result = {
            "status": "interrupted"
            if isinstance(error, (KeyboardInterrupt, SystemExit, InterruptedError))
            else "blocked",
            "freeze_commit": freeze_commit,
            "first_data_access_utc": budget.first_access,
            "error": f"{type(error).__name__}: {error}",
            "traceback": traceback.format_exc(),
            "calibration_verdict": calibration_verdict,
            "source_noise_validated": False,
            "elemental_inference": False,
        }
    if budget.stop_reason is not None:
        result["stopping_reason"] = budget.stop_reason
        result["archive_absence_inferred"] = False
    result["acquisition"] = {
        "cap_bytes": budget.cap,
        "body_bytes": sum(r["body_bytes"] for r in budget.receipts),
        "charged_body_bytes": budget.bytes,
        "body_accounting_complete": all(
            r.get("complete_body_accounting", False) for r in budget.receipts
        ),
        "fragments": budget.receipts,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compact", type=Path, required=True)
    parser.add_argument("--calibration-verdict", choices=("pass", "fail", "blocked"), required=True)
    parser.add_argument("--coalesced-cal", action="store_true")
    parser.add_argument("--geometric-wavelength-prior", action="store_true")
    parser.add_argument("--cap-bytes", type=int, default=300_000_000)
    parser.add_argument("--freeze-commit", default="d50fa97")
    args = parser.parse_args()

    cancel_event = threading.Event()

    def terminate(signum, frame):
        cancel_event.set()
        raise KeyboardInterrupt(f"signal {signum}: preserve receipt, no scientific null")

    previous = signal.signal(signal.SIGTERM, terminate)
    try:
        result = run(
            args.output,
            args.compact,
            calibration_verdict=args.calibration_verdict,
            cancel_event=cancel_event,
            cap_bytes=args.cap_bytes,
            geometric_wavelength_prior=args.geometric_wavelength_prior,
            freeze_commit=args.freeze_commit,
            coalesced_cal=args.coalesced_cal,
        )
    finally:
        signal.signal(signal.SIGTERM, previous)
    print(json.dumps({k: result[k] for k in ("status", "first_data_access_utc")}))
    if result["status"] in ("blocked", "interrupted"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
