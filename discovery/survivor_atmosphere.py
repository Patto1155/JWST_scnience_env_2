"""Compare the curved persistent source with versioned cool-atmosphere predictions.

Use published JWST log(mJy) at 10 pc, never Vega magnitudes or guessed column
labels.  Discrete-grid predictive failures do not identify an object or exclude
all atmospheres; grid/cloud/chemistry, PSF and calibration assumptions remain.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tarfile
from pathlib import Path

import numpy as np

from data_pipeline.research_sources import fetch_product
from data_pipeline.survivor_deep_data import verify_pinned

MANIFEST = Path(__file__).resolve().parents[1] / "data_sources/survivor_atmosphere/manifest.json"
BANDS = ("F090W", "F115W", "F150W", "F200W", "F277W", "F356W", "F444W")


def parse_table(text: str, metadata: dict) -> list[dict]:
    """Decode the actual author header and unit declaration; retain starred radius flags."""
    if "log(fluxes) (in mJy) computed for d=" not in text or "10.00pc" not in text:
        raise ValueError("Missing documented log10-mJy-at-10pc model units")
    lines = text.splitlines()
    headers = [i for i, line in enumerate(lines) if line.strip().startswith("Teff")]
    if len(headers) != 1:
        raise ValueError("Model table lacks one unique physical/filter header")
    start = headers[0]
    prefix = lines[start].split()[:8]
    if prefix != ["Teff", "log", "g", "mass", "R/Rsun", "Y", "log", "Kzz"]:
        raise ValueError("Unexpected physical parameter columns")
    filters = lines[start].split()[8:]
    if not set(BANDS).issubset(filters) or len(filters) != len(set(filters)):
        raise ValueError("Actual table header does not supply unique required JWST bands")
    selected = [6 + filters.index(band) for band in BANDS]
    output = []
    for line_number, line in enumerate(lines[start + 1 :], start=start + 2):
        if not line.strip():
            continue
        tokens = line.split()
        if len(tokens) != 6 + len(filters):
            raise ValueError("Model row and actual filter-header lengths differ")
        flagged = tokens[3].endswith("*")
        # Only the documented radius field has a trailing author flag.
        tokens[3] = tokens[3].rstrip("*")
        values = np.array([float(token) for token in tokens])
        if not np.isfinite(values).all() or values[0] <= 0 or values[3] <= 0:
            raise ValueError("Nonphysical/nonfinite model table row")
        if not 200 <= values[0] <= 2400 or not 3.25 <= values[1] <= 5.5:
            continue
        flux = 10 ** values[selected] * 1e6  # mJy -> nJy, already band-integrated
        if not np.isfinite(flux).all() or np.any(flux <= 0):
            raise ValueError("Nonpositive model band flux")
        output.append(
            {
                **metadata,
                "author_row": line_number,
                "teff_k": float(values[0]),
                "logg_cgs": float(values[1]),
                "model_mass_mjupiter": float(values[2]),
                "model_radius_rsun": float(values[3]),
                "radius_author_flag": flagged,
                "helium_mass_fraction": float(values[4]),
                "logkzz": float(values[5]),
                "flux_njy_at_10pc": flux.tolist(),
                "additional_flux_njy_at_10pc": {
                    band: float(10 ** values[6 + filters.index(band)] * 1e6)
                    for band in ("F335M", "F410M", "F430M", "F460M", "F480M", "F770W")
                    if band in filters
                },
            }
        )
    if not output:
        raise ValueError("No eligible atmosphere grid rows")
    return output


def load_grid(directory: Path) -> tuple[list[dict], dict]:
    inventory = json.loads(MANIFEST.read_text())
    product = inventory["product"]
    archive = directory / product["filename"]
    if not archive.exists():
        fetch_product(product, archive, max_bytes=2 * 1024 * 1024, timeout=45)
    receipt = verify_pinned(archive, product)
    if hashlib.md5(archive.read_bytes()).hexdigest() != product["publisher_md5"]:
        raise ValueError("Archive differs from publisher MD5")
    rows, rejected = [], []
    with tarfile.open(archive, "r:gz") as tar:
        for selected in inventory["tables"]:
            member = tar.getmember(selected["member"])
            if not member.isfile() or member.size > 2 * 1024 * 1024:
                raise ValueError("Selected archive member is not a bounded regular table")
            text = tar.extractfile(member).read().decode("ascii")
            if hashlib.sha256(text.encode()).hexdigest() != selected["sha256"]:
                raise ValueError("Table bytes differ from pinned member inventory")
            try:
                parsed = parse_table(
                    text,
                    {
                        "table_member": member.name,
                        "metallicity_dex": selected["metallicity_dex"],
                        "co_relative_to_solar": selected["co_relative_to_solar"],
                    },
                )
            except ValueError as error:
                if selected.get("expected_status") != "rejected_missing_jwst_header":
                    raise
                rejected.append({"member": member.name, "reason": str(error)})
                continue
            if selected.get("expected_status") == "rejected_missing_jwst_header":
                raise ValueError("Previously rejected input changed validation status")
            rows.extend(parsed)
    return rows, {
        "archive_receipt": receipt,
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "valid_grid_rows": len(rows),
        "rejected_tables": rejected,
    }


def fit_grid(
    flux: np.ndarray, covariance: np.ndarray, grid: list[dict], retained: np.ndarray | None = None
) -> list[dict]:
    """Positive amplitude-only GLS per actual row; full covariance for retained bands."""
    keep = np.arange(len(flux)) if retained is None else retained
    inverse = np.linalg.inv(covariance[np.ix_(keep, keep)])
    fitted = []
    for row in grid:
        absolute_flux = np.array(row["flux_njy_at_10pc"])
        shape = absolute_flux / absolute_flux[-1]
        selected = shape[keep]
        denominator = float(selected @ inverse @ selected)
        if denominator <= 0:
            raise ValueError("Unidentifiable atmosphere amplitude")
        amplitude = max(0.0, float(selected @ inverse @ flux[keep] / denominator))
        predicted = amplitude * shape
        residual = flux[keep] - predicted[keep]
        fitted.append(
            {
                **row,
                "f444_amplitude_njy": amplitude,
                "model_flux_njy": predicted.tolist(),
                "chi2_conditional": float(residual @ inverse @ residual),
                "additional_band_predictions_njy": {
                    band: float(amplitude * value / absolute_flux[-1])
                    for band, value in row.get("additional_flux_njy_at_10pc", {}).items()
                },
                "distance_pc_if_model_radius_single_object": (
                    float(10 * np.sqrt(absolute_flux[-1] / amplitude)) if amplitude > 0 else None
                ),
            }
        )
    return sorted(fitted, key=lambda row: row["chi2_conditional"])


def compare(directory: Path, photometry_path: Path, output: Path) -> dict:
    grid, provenance = load_grid(directory)
    inventory = json.loads(MANIFEST.read_text())
    if (
        hashlib.sha256(photometry_path.read_bytes()).hexdigest()
        != inventory["photometry_report_sha256"]
    ):
        raise ValueError("Photometry report differs from pinned model-fit version")
    photo = json.loads(photometry_path.read_text())
    source = next(s for s in photo["sources"] if s["source_id"] == 46)
    if tuple(photo["bands"]) != BANDS:
        raise ValueError("Photometry/model filter identities disagree")
    flux = np.array([b["fixed_extended_fit"]["flux_njy"] for b in source["bands"]])
    scenarios = []
    for continuum in source["phenomenological_continuum_sensitivity"]:
        covariance = np.array(continuum["flux_covariance_njy2"])
        fit = fit_grid(flux, covariance, grid)
        held_out = []
        for omitted in range(len(BANDS)):
            keep = np.array([i for i in range(len(BANDS)) if i != omitted])
            best = fit_grid(flux, covariance, grid, keep)[0]
            predicted = best["model_flux_njy"][omitted]
            # Gaussian conditional residual removes assumed cross-band common term;
            # selection/model uncertainty remains excluded, so this is descriptive.
            ckeep = covariance[np.ix_(keep, keep)]
            cross = covariance[omitted, keep]
            conditional_variance = covariance[omitted, omitted] - cross @ np.linalg.solve(
                ckeep, cross
            )
            adjusted = (
                flux[omitted]
                - predicted
                - cross
                @ np.linalg.solve(ckeep, flux[keep] - np.array(best["model_flux_njy"])[keep])
            )
            held_out.append(
                {
                    "omitted_band": BANDS[omitted],
                    "observed_njy": float(flux[omitted]),
                    "predicted_njy_without_band": predicted,
                    "conditional_residual_over_assumed_sigma": float(
                        adjusted / np.sqrt(conditional_variance)
                    ),
                    "best_retained_model": best,
                }
            )
        scenarios.append(
            {
                "independent_fractional_floor": continuum["independent_fractional_floor"],
                "assumed_flux_covariance_njy2": covariance.tolist(),
                "top_10_grid_rows": fit[:10],
                "band_held_out_predictions": held_out,
                "comparison_existing_families": {
                    family: model["chi2_conditional"]
                    for family, model in continuum["families"].items()
                },
            }
        )
    result = {
        "schema_version": 1,
        "evidence_kind": "actual_source_fluxes_against_versioned_physical_model_grid",
        "source_id": 46,
        "source_ra_deg": source["ra_deg"],
        "source_dec_deg": source["dec_deg"],
        "photometry_report_sha256": hashlib.sha256(photometry_path.read_bytes()).hexdigest(),
        "photometry_manifest_sha256": photo["manifest_sha256"],
        "provenance": provenance,
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "bands": BANDS,
        "observed_flux_njy": flux.tolist(),
        "scenarios": scenarios,
        "model": "Sonora Bobcat2021 cloudless, rainout chemical equilibrium; finite tabulated grid",
        "limits": [
            "Grid chi2 and held-out residuals condition on adopted PSF and calibration covariance.",
            "No interpolation, clouds, nonequilibrium chemistry, binaries or galaxy SED grid.",
            "Searching grid parameters invalidates naive fixed-row significance or posterior.",
            "Distance is a conditional amplitude/model-radius conversion, not a measurement.",
            "Model passband and image calibration conventions are not empirically harmonized.",
            "Grid failure does not identify the source or exclude all cool atmospheres.",
            "Held-band predictions reuse the F444-derived morphology and selected object; "
            "they are not independent imaging or population validation.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    csv_path = output.with_name(output.stem + "_grid.csv")
    fields = [
        "table_member",
        "author_row",
        "metallicity_dex",
        "co_relative_to_solar",
        "teff_k",
        "logg_cgs",
        "model_mass_mjupiter",
        "model_radius_rsun",
        "radius_author_flag",
    ] + list(BANDS)
    with csv_path.open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in grid:
            writer.writerow(
                {
                    **{k: row[k] for k in fields if k not in BANDS},
                    **dict(zip(BANDS, row["flux_njy_at_10pc"])),
                }
            )
    result["derived_grid_csv"] = {
        "filename": csv_path.name,
        "rows": len(grid),
        "sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
    }
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--photometry-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.input, args.photometry_report, args.output)
    print(
        json.dumps(
            {
                s["independent_fractional_floor"]: s["top_10_grid_rows"][0]["chi2_conditional"]
                for s in result["scenarios"]
            }
        )
    )


if __name__ == "__main__":
    main()
