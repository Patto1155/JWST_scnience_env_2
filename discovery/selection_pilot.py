"""Geometry-frozen three-band, unmasked-background selection response pilot.

All probabilities are conditional operator responses, never survey completeness.
Poisson counts are explicitly assumed output-grid nuisance models, not detector
calibration: native source covariance and local effective exposure remain absent.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.stats import sigma_clipped_stats
from astropy.wcs.utils import proj_plane_pixel_scales
from scipy.ndimage import shift
from scipy.signal import fftconvolve

from data_pipeline.research_sources import fetch_product
from discovery.deep_control_recovery import json_hash
from discovery.deep_reference_comparison import load_deep_cutout
from discovery.observed_template_injections import local_detection
from discovery.psf_noise import circular_weights, overlap_resample, verified_template
from discovery.survivor_deep_model import elliptical_gaussian

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data_sources/selection_pilot/manifest.json"
BANDS = ("F090W", "F200W", "F444W")
COLORS = {"blue": (1.0, 1.0, 1.0), "intermediate": (0.2, 0.5, 1.0), "red": (0.03, 0.1, 1.0)}
MORPHOLOGIES = ("point", "extended", "pair")
FLUXES = (20.0, 80.0)
GAINS = (1.0, 10.0)
HALF = 24
SEED = 271828


def acquire(directory: Path) -> dict:
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    for product in manifest["products"]:
        path = directory / product["filename"]
        if not path.exists():
            fetch_product(product, path, max_bytes=product["max_bytes"], timeout=90)
        raw = path.read_bytes()
        if (
            len(raw) != product["expected_bytes"]
            or hashlib.sha256(raw).hexdigest() != product["sha256"]
        ):
            raise ValueError("Selection input differs from pinned public manifest")
        rows.append({"filename": path.name, "bytes": len(raw), "sha256": product["sha256"]})
    total = sum(row["bytes"] for row in rows)
    if total > 60 * 1024**2:
        raise ValueError("Selected pilot exceeds frozen new-download ceiling")
    return {"selected_new_bytes": total, "inputs": rows}


def aperture_operator(size: int, scale: float) -> np.ndarray:
    aperture = circular_weights(size, 0.2 / scale)
    annulus = circular_weights(size, 0.6 / scale) - circular_weights(size, 0.4 / scale)
    return aperture - annulus * aperture.sum() / annulus.sum()


def poisson_profile(
    profile: np.ndarray, flux: float, electrons_per_njy: float, rng: np.random.Generator
) -> np.ndarray:
    if not np.isfinite(profile).all() or np.any(profile < 0) or not np.isclose(profile.sum(), 1):
        raise ValueError("Poisson profile must be finite nonnegative normalized")
    if not np.isfinite([flux, electrons_per_njy]).all() or flux < 0 or electrons_per_njy <= 0:
        raise ValueError("Invalid source count nuisance")
    return rng.poisson(profile * flux * electrons_per_njy) / electrons_per_njy


def count_transport_counterexample() -> dict:
    """One independent detector count split into adjacent mosaic pixels.

    For N~Poisson(20), y=(N/2,N/2); covariance has off-diagonal5.
    Assigning independent Poisson(10) to output pixels gives variance10
    rather than5 for one pixel, and20 rather than0 for their difference.
    Neither this toy split nor the pilot's gain is actual instrument calibration.
    """
    mean = 20.0
    transport = np.array([[0.5], [0.5]])
    covariance = transport @ np.diag([mean]) @ transport.T
    independent = np.diag((transport @ np.array([mean])).ravel())
    difference = np.array([1.0, -1.0])
    return {
        "detector_mean_electrons": mean,
        "toy_flux_conserving_transport": transport.tolist(),
        "transported_covariance": covariance.tolist(),
        "independent_output_poisson_covariance": independent.tolist(),
        "one_pixel_variance_transport_vs_output": [
            float(covariance[0, 0]),
            float(independent[0, 0]),
        ],
        "signed_difference_variance_transport_vs_output": [
            float(difference @ covariance @ difference),
            float(difference @ independent @ difference),
        ],
        "scope": "Analytic counterexample: output-grid Poisson cannot replace native transport",
    }


def classify(fluxes: dict[str, float], red_snr: float) -> str:
    red = fluxes["F444W"]
    if red <= 0 or red_snr < 5:
        return "below_red_gate"
    if fluxes["F090W"] < 0.1 * red and fluxes["F200W"] < 0.25 * red:
        return "red"
    if fluxes["F090W"] >= 0.5 * red and fluxes["F200W"] >= 0.5 * red:
        return "blue"
    return "intermediate"


def profiles(psf: np.ndarray, scale: float) -> dict[str, np.ndarray]:
    model = {
        "point": psf.copy(),
        "extended": fftconvolve(
            psf, elliptical_gaussian(psf.shape[0], 0.12 / scale, 0.65, 0.4), mode="same"
        ),
        "pair": 0.5 * shift(psf, (0, -0.20 / scale), order=1, mode="constant")
        + 0.5 * shift(psf, (0, 0.20 / scale), order=1, mode="constant"),
    }
    return {key: np.maximum(value, 0) / np.maximum(value, 0).sum() for key, value in model.items()}


def build_plan(directory: Path, psf_directory: Path) -> tuple[dict, dict, dict]:
    receipt = acquire(directory)
    bundles, models, reports = {}, {}, []
    psf_pins = {
        p["filter"]: p
        for p in json.loads((ROOT / "data_sources/survivor_deep/manifest.json").read_text())[
            "products"
        ]
        if p["kind"] == "modeled_finite_psf"
    }
    for band in BANDS:
        bundle, report = load_deep_cutout(directory / f"selection_{band}.fits")
        if (
            bundle["header"]["FILTER"] != band + "-CLEAR"
            or bundle["header"]["BUNIT"] != "10.0*nanoJansky"
        ):
            raise ValueError("Pinned selection identity/unit mismatch")
        center = bundle["wcs"].pixel_to_world(399.5, 399.5)
        if center.separation(SkyCoord(53.12, -27.81, unit="deg")).arcsec > 0.1:
            raise ValueError("Unexpected selection sky footprint")
        scale = float(np.sqrt(np.prod(proj_plane_pixel_scales(bundle["wcs"]) * 3600)))
        kernel, psf_report = verified_template(
            psf_directory
            / ("f444wa_v5.0_mpsf.fits" if band == "F444W" else band.lower() + "_v5.0_mpsf.fits"),
            band,
        )
        if psf_report["sha256"] != psf_pins[band]["sha256"]:
            raise ValueError("Modeled PSF differs from existing independently pinned manifest")
        # Re-download timestamps are not scientific identity or frozen design.
        psf_report.pop("retrieved_utc", None)
        report["receipt"] = {k: report["receipt"][k] for k in ("bytes", "sha256")}
        resampled = overlap_resample(kernel, psf_report["input_scale_arcsec"], scale, 2 * HALF + 1)
        models[band] = profiles(resampled, scale)
        _, median, sigma = sigma_clipped_stats(bundle["sci"][bundle["validity_mask"]], sigma=3)
        report.update(
            scale_arcsec=scale,
            median_stored=float(median),
            sigma_stored=float(sigma),
            psf=psf_report,
            psf_retained_fraction=float(resampled.sum()),
            profile_hashes={
                k: hashlib.sha256(v.astype("<f8").tobytes()).hexdigest()
                for k, v in models[band].items()
            },
        )
        bundles[band] = bundle
        reports.append(report)
    sites = []
    for row, column in itertools.product(range(4), repeat=2):
        x, y = (int(round(v * 800)) for v in ((column + 1) / 5, (row + 1) / 5))
        sky = bundles["F444W"]["wcs"].pixel_to_world(x, y)
        locations = {}
        for band in BANDS:
            bundle = bundles[band]
            bx, by = bundle["wcs"].world_to_pixel(sky)
            ix, iy = int(round(float(bx))), int(round(float(by)))
            valid = bundle["validity_mask"][iy - HALF : iy + HALF + 1, ix - HALF : ix + HALF + 1]
            if valid.shape != (49, 49) or not valid.all():
                break
            locations[band] = {"x": ix, "y": iy, "phase_pixels": [float(bx) - ix, float(by) - iy]}
        if len(locations) == len(BANDS):
            sites.append(
                {
                    "id": f"{row}-{column}",
                    "split": "heldout" if (row + column) % 2 else "pilot",
                    "ra_deg": float(sky.ra.deg),
                    "dec_deg": float(sky.dec.deg),
                    "locations": locations,
                }
            )
    if (
        len(sites) < 12
        or min(sum(s["split"] == t for s in sites) for t in ("pilot", "heldout")) < 6
    ):
        raise ValueError(
            "Insufficient geometrically valid fixed pilot sites; do not choose new sites from flux"
        )
    plan = {
        "schema_version": 1,
        "question": (
            "How do morphology, colors, background structure and conditional source "
            "counts change bounded detection and red-bin assignment?"
        ),
        "geometry_selection": (
            "fixed 40arcsec GOODS patch; 4x4 unmasked lattice, full-valid SCI/WHT only; "
            "no observed source outcomes enter site selection"
        ),
        "inputs": receipt,
        "images": reports,
        "sites": sites,
        "bands": list(BANDS),
        "finite_stamp_F444W_flux_njy": list(FLUXES),
        "colors": COLORS,
        "morphologies": list(MORPHOLOGIES),
        "output_grid_electrons_per_njy_assumed": list(GAINS),
        "source_realizations_per_cell": 2,
        "seed": SEED,
        "budget": {
            "new_download_cap_bytes": 60 * 1024**2,
            "max_injected_trials": 1152,
            "expansion": "none before independent review",
        },
        "measurement": (
            "fixed global uninjected five-sigma threshold, >=5 connected pixels and "
            ".2arcsec centroid gate; fixed signed .2arcsec aperture minus .4-.6arcsec "
            "mean sky"
        ),
        "model": (
            "modeled JADES PSF finite49px renormalization; point, Gaussian sigma.12arcsec "
            "q.65, equal pair separation.4arcsec; these are morphology classes, not "
            "verified object labels"
        ),
        "source_count_status": (
            "assumed output-grid Poisson sensitivity; EXPTIME sums and PHOTFNU do not "
            "calibrate local effective electrons; native drizzle source covariance "
            "omitted"
        ),
        "selection": (
            "declared red operator: red aperture diagonal SNR>=5, F090/F444<.1 and "
            "F200/F444<.25; evaluated jointly with centroid recovery"
        ),
        "dependence": (
            "one dependent multi-filter mosaic; spatial checkerboard holdout is not "
            "independent visit/field; repeated source realizations not independent "
            "backgrounds"
        ),
        "stopping": (
            "execute fixed pilot, report intervals/degeneracies and no population "
            "posterior; no outcome-dependent expansion"
        ),
    }
    plan["plan_content_sha256"] = json_hash(plan)
    return json.loads(json.dumps(plan)), bundles, models


def execute(plan: dict, directory: Path, psf_directory: Path) -> tuple[dict, list[dict]]:
    actual, bundles, models = build_plan(directory, psf_directory)
    if actual != plan:
        raise ValueError("Frozen selection plan differs from reconstructed inputs/design")
    rng = np.random.default_rng(SEED)
    by_band = {r["filename"].split("_")[-1].split(".")[0]: r for r in plan["images"]}
    trials, nulls = [], []
    for site in plan["sites"]:
        backgrounds, errors, operators, null_fluxes = {}, {}, {}, {}
        for band in BANDS:
            b = bundles[band]
            loc = site["locations"][band]
            x, y = loc["x"], loc["y"]
            backgrounds[band] = b["sci"][y - HALF : y + HALF + 1, x - HALF : x + HALF + 1] * 10
            errors[band] = b["err"][y - HALF : y + HALF + 1, x - HALF : x + HALF + 1] * 10
            operators[band] = aperture_operator(49, by_band[band]["scale_arcsec"])
            null_fluxes[band] = float(np.sum(backgrounds[band] * operators[band]))
        null_sigma = float(np.sqrt(np.sum((errors["F444W"] * operators["F444W"]) ** 2)))
        report = by_band["F444W"]
        null_detect = local_detection(
            backgrounds["F444W"] / 10,
            report["median_stored"],
            report["sigma_stored"],
            5,
            report["scale_arcsec"],
        )
        nulls.append(
            {
                "site_id": site["id"],
                "split": site["split"],
                "flux_njy": null_fluxes,
                "red_bin": classify(null_fluxes, null_fluxes["F444W"] / null_sigma),
                "centroid_status": null_detect["status"],
                "selected_red": classify(null_fluxes, null_fluxes["F444W"] / null_sigma) == "red"
                and null_detect["status"] == "matched",
            }
        )
        for morphology, flux, color, gain, realization in itertools.product(
            MORPHOLOGIES, FLUXES, COLORS, GAINS, range(2)
        ):
            fluxes, paired, expected, sigmas = {}, {}, {}, {}
            for band, ratio in zip(BANDS, COLORS[color]):
                profile = models[band][morphology]
                signal = poisson_profile(profile, flux * ratio, gain, rng)
                values = backgrounds[band] + signal
                fluxes[band] = float(np.sum(values * operators[band]))
                paired[band] = fluxes[band] - null_fluxes[band]
                expected[band] = float(np.sum(profile * flux * ratio * operators[band]))
                # Formal diagnostic only; observed background pixels retained, not redrawn.
                variance = errors[band] ** 2 + profile * flux * ratio / gain
                sigmas[band] = float(np.sqrt(np.sum(variance * operators[band] ** 2)))
                if band == "F444W":
                    detection = local_detection(
                        values / 10,
                        report["median_stored"],
                        report["sigma_stored"],
                        5,
                        report["scale_arcsec"],
                    )
            red_bin = classify(fluxes, fluxes["F444W"] / sigmas["F444W"])
            trials.append(
                {
                    "site_id": site["id"],
                    "split": site["split"],
                    "morphology": morphology,
                    "flux_njy": flux,
                    "truth_color": color,
                    "assumed_electrons_per_njy": gain,
                    "realization": realization,
                    "observed_bin": red_bin,
                    "centroid_status": detection["status"],
                    "selected_red": red_bin == "red" and detection["status"] == "matched",
                    "aperture_flux_njy": fluxes,
                    "paired_source_response_njy": paired,
                    "expected_aperture_response_njy": expected,
                    "formal_error_njy": sigmas,
                }
            )
    groups = defaultdict(list)
    for trial in trials:
        groups[
            (
                trial["split"],
                trial["morphology"],
                trial["flux_njy"],
                trial["truth_color"],
                trial["assumed_electrons_per_njy"],
            )
        ].append(trial)
    summary = []
    for key, rows in sorted(groups.items()):
        sites = sorted({r["site_id"] for r in rows})
        metrics = {
            "centroid_recovery": lambda r: float(r["centroid_status"] == "matched"),
            "red_selection": lambda r: float(r["selected_red"]),
        }
        estimates = {}
        for metric, function in metrics.items():
            site_values = np.array(
                [np.mean([function(r) for r in rows if r["site_id"] == s]) for s in sites]
            )
            boot_rng = np.random.default_rng(SEED)
            values = np.mean(
                site_values[boot_rng.integers(0, len(sites), (1000, len(sites)))], axis=1
            )
            estimates[metric] = {
                "fraction": float(site_values.mean()),
                "conditional_site_bootstrap_interval": np.quantile(values, [0.025, 0.975]).tolist(),
            }
        observed_bins = {
            label: sum(r["observed_bin"] == label for r in rows)
            for label in ("red", "blue", "intermediate", "below_red_gate")
        }
        relative_bias = [
            (r["aperture_flux_njy"]["F444W"] - r["expected_aperture_response_njy"]["F444W"])
            / key[2]
            for r in rows
        ]
        paired_bias = [
            (
                r["paired_source_response_njy"]["F444W"]
                - r["expected_aperture_response_njy"]["F444W"]
            )
            / key[2]
            for r in rows
        ]
        summary.append(
            {
                "split": key[0],
                "morphology": key[1],
                "flux_njy": key[2],
                "truth_color": key[3],
                "assumed_electrons_per_njy": key[4],
                "sites": len(sites),
                "realizations": len(rows),
                "metrics": estimates,
                "color_bin_counts": observed_bins,
                "red_aperture_total_assignment_bias_fraction_median": float(
                    np.median(relative_bias)
                ),
                "red_paired_response_bias_fraction_median": float(np.median(paired_bias)),
            }
        )
    result = {
        "schema_version": 1,
        "plan_content_sha256": plan["plan_content_sha256"],
        "trials": len(trials),
        "full_trial_content_sha256": json_hash(trials),
        "null_site_controls": nulls,
        "groups": summary,
        "source_count_convention": plan["source_count_status"],
        "uncalibrated_drizzle_counterexample": count_transport_counterexample(),
        "interval_scope": (
            "conditional 1000 site bootstrap; two count realizations averaged within "
            "site; uncalibrated coverage, no field/cosmic/PSF/gain uncertainty; extremes "
            "do not bound unseen failures"
        ),
        "interpretation": (
            "unmasked fixed-field conditional selection response and assumed-profile "
            "color scattering; no real-source truth labels, survey completeness, "
            "contamination fraction or population likelihood"
        ),
    }
    return result, trials


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("acquire", "freeze", "execute"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--psf-input", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--full-output", type=Path)
    args = parser.parse_args()
    if args.command == "acquire":
        print(json.dumps(acquire(args.input), indent=2))
        return
    if args.psf_input is None or args.plan is None:
        parser.error("freeze/execute require --psf-input and --plan")
    if args.command == "freeze":
        plan, _, _ = build_plan(args.input, args.psf_input)
        args.plan.write_text(json.dumps(plan, indent=2) + "\n")
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result, trials = execute(json.loads(args.plan.read_text()), args.input, args.psf_input)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        if args.full_output:
            args.full_output.write_text(json.dumps(trials, indent=2) + "\n")


if __name__ == "__main__":
    main()
