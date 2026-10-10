"""Pin and audit the public MoM pixel-table extraction, without recalibrating it.

The native pixel table is an author-release intermediate, not original RATE
pixels. Its diagonal variance replay is not a shared-noise likelihood.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np
from astropy.io import fits

from data_pipeline.research_sources import fetch_product

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data_sources/author_provenance/manifest.json"
FIELDS = (
    "sci",
    "sky",
    "var_total",
    "var_rnoise",
    "wave",
    "dwave_dx",
    "yslit",
    "bar",
    "profile",
    "pathloss",
    "exposure_index",
    "exptime",
)


def verify_pin(path: Path, pin: dict) -> dict:
    payload = path.read_bytes()
    result = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    if result["bytes"] != pin["expected_bytes"] or result["sha256"] != pin["sha256"]:
        raise ValueError(f"Pinned public input differs: {path.name}")
    return result


def pixel_table_replay(table, wave: np.ndarray, y_range=(-3.0, 3.0)) -> dict:
    """Independent numpy histograms of the pinned author ivm extraction.

    Pathloss is divided exactly once. Negative profiles remain signed. This
    reproduces author diagonal errors only, without independence claims.
    """
    wave = np.asarray(wave, dtype=float)
    if (
        wave.ndim != 1
        or len(wave) < 2
        or not np.all(np.isfinite(wave))
        or np.any(np.diff(wave) <= 0)
    ):
        raise ValueError("Output wavelengths must be finite and strictly increasing")
    names = table.dtype.names
    if names is None or not set(FIELDS).issubset(names):
        raise ValueError("Missing public pixel-table fields")
    for key in FIELDS:
        if not np.all(np.isfinite(table[key])):
            raise ValueError(f"Nonfinite pixel-table field: {key}")
    for key in ("var_total", "var_rnoise", "pathloss", "dwave_dx", "exptime"):
        if np.any(table[key] <= 0):
            raise ValueError(f"Nonpositive pixel-table field: {key}")
    if not len(y_range) == 2 or not np.isfinite(y_range).all() or y_range[0] >= y_range[1]:
        raise ValueError("Invalid cross-dispersion extraction range")
    edges = np.r_[
        wave[0] - (wave[1] - wave[0]) / 2,
        (wave[:-1] + wave[1:]) / 2,
        wave[-1] + (wave[-1] - wave[-2]) / 2,
    ]
    mask = (table["yslit"] >= y_range[0]) & (table["yslit"] <= y_range[1])
    data = table[mask]
    weights = 1 / data["var_rnoise"]
    profile, pathloss = data["profile"], data["pathloss"]

    def total(value):
        return np.histogram(data["wave"], edges, weights=value)[0]

    denominator = total(weights * profile**2)
    numerator = total(data["sci"] / pathloss * weights * profile)
    variance = total(data["var_total"] / pathloss**2 * weights**2 * profile**2)
    with np.errstate(divide="ignore", invalid="ignore"):
        flux = numerator / denominator
        error = np.sqrt(variance) / denominator
    return {
        "flux": flux,
        "err": error,
        "npix": total(np.ones(len(data))),
        "profile_sum": total(profile),
        "flux_sum": total(data["sci"] / pathloss),
        "var_sum": total(data["var_total"] / pathloss**2),
    }


def shared_sky_counts(table) -> list[list[int]]:
    """Exact common stored sky values, an observed dependence witness.

    These are set intersections, not pixel correspondences or covariance.
    """
    indices = np.unique(table["exposure_index"])
    if not np.array_equal(indices, np.arange(9)):
        raise ValueError("Expected nine ordered public exposure indices")
    sky = [np.unique(table["sky"][table["exposure_index"] == i]) for i in indices]
    return [[int(len(np.intersect1d(a, b, assume_unique=True))) for b in sky] for a in sky]


def audit(pixtab: Path, spectrum: Path, source: Path) -> dict:
    manifest = json.loads(MANIFEST.read_text())
    pins = {p["id"]: p for p in manifest["products"]}
    inputs = {
        key: verify_pin(path, pins[key])
        for key, path in (
            ("mom-pixtab", pixtab),
            ("mom-spectrum", spectrum),
            ("msaexp-source", source),
        )
    }
    with fits.open(pixtab, memmap=False) as hdul:
        if [h.name for h in hdul] != ["PRIMARY", "PIXTAB"]:
            raise ValueError("Unexpected public pixel-table extensions")
        table = hdul["PIXTAB"].data.copy()
        header = hdul["PIXTAB"].header.copy()
    with fits.open(spectrum, memmap=False) as hdul:
        spec = hdul["SPEC1D"].data.copy()
        sh = hdul["SCI"].header.copy()
        slits = hdul["SLITS"].data.copy()
    if tuple(table.dtype.names) != FIELDS or len(table) != 56734:
        raise ValueError("Unexpected pinned pixel-table schema or row count")
    if len(slits) != 9 or np.any(slits["source_id"] != 277193):
        raise ValueError("Source/exposure identity differs")
    if not np.allclose(slits["source_ra"], 150.0933255, atol=1e-7, rtol=0) or not np.allclose(
        slits["source_dec"], 2.2731627, atol=1e-7, rtol=0
    ):
        raise ValueError("Source coordinates differ")
    settings = (
        "VERSION",
        "PROFCEN",
        "PROFSIG",
        "PROFSTRT",
        "PROFSTOP",
        "YTRACE",
        "YMIN1D",
        "YMAX1D",
        "WITHPATH",
    )
    if any(header[k] != sh[k] for k in settings) or sh["WEIGHT_TYPE"] != "ivm":
        raise ValueError("Public spectrum/pixel-table extraction settings differ")
    contributors = []
    for i, row in enumerate(slits):
        filename = str(row["filename"])
        if filename != sh[f"SFILE{i:03d}"]:
            raise ValueError("Ordered contributor identity differs")
        match = re.fullmatch(
            r"jw05224004001_(\d{5})_(\d{5})_nrs2_clear_prism_raw\.21\.5224_277193\.fits", filename
        )
        if match is None:
            raise ValueError("Unexpected contributor filename")
        subset = table[table["exposure_index"] == i]
        if not np.all(subset["exptime"] == row["exposure_time"]):
            raise ValueError("Contributor exposure duration differs")
        if not np.isclose(header[f"XPOS{i}"], row["source_xpos"], atol=1e-7, rtol=0):
            raise ValueError("Contributor source placement differs")
        contributors.append(
            {
                "exposure_index": i,
                "filename": filename,
                "official_visit_group": match.group(1)[:2],
                "nod_position": int(row["position_number"]),
                "rows": len(subset),
                "uv_rows_2p15_to_3p20_um": int(
                    np.sum((subset["wave"] >= 2.15) & (subset["wave"] <= 3.2))
                ),
                "exposure_time_s": float(row["exposure_time"]),
                "planned_source_xpos": float(row["source_xpos"]),
            }
        )
    replay = pixel_table_replay(table, spec["wave"], (header["YMIN1D"], header["YMAX1D"]))
    comparisons = {}
    for name, actual in replay.items():
        expected = spec[name]
        if not np.array_equal(np.isfinite(actual), np.isfinite(expected)):
            raise ValueError(f"Author replay finite mask differs: {name}")
        valid = np.isfinite(actual)
        if not np.allclose(actual[valid], expected[valid], atol=2e-8, rtol=2e-8):
            raise ValueError(f"Author replay numerical mismatch: {name}")
        comparisons[name] = {
            "finite_bins": int(valid.sum()),
            "max_absolute_difference": float(np.max(abs(actual[valid] - expected[valid]))),
        }
    return {
        "schema_version": 1,
        "question": (
            "Can public author intermediate/settings be recovered and numerically replayed?"
        ),
        "input_pins": inputs,
        "pixtab_rows": len(table),
        "pixtab_fields": list(FIELDS),
        "settings": {k: header[k] for k in settings},
        "weight_type": sh["WEIGHT_TYPE"],
        "public_release_calibration": {
            k: sh[k] for k in ("CAL_VER", "CAL_VCS", "CRDS_CTX", "CRDS_VER")
        },
        "contributors": contributors,
        "replay": comparisons,
        "exact_shared_sky_value_counts": shared_sky_counts(table),
        "profile_signed_negative_rows": int(np.sum(table["profile"] < 0)),
        "pathloss_range": [float(np.min(table["pathloss"])), float(np.max(table["pathloss"]))],
        "limits": [
            (
                "Public author-release pixel-table reproduction, not original RATE "
                "recalibration or publication-likelihood reproduction"
            ),
            (
                "Exact shared stored sky values witness dependence across official visit "
                "groups; set intersections are not covariance estimates"
            ),
            (
                "Pixel table has no raw detector coordinates, negative contributor "
                "masks, full covariance, empirical LSF or measured dispersion-direction "
                "placement"
            ),
            (
                "Diagonal error replay neither calibrates interval coverage nor "
                "establishes independent line detections"
            ),
            (
                "The older public release calibration differs from the already "
                "reconstructed current official CAL alternative"
            ),
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--acquire", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    locations = {}
    for pin in manifest["products"]:
        if pin["id"] not in ("mom-pixtab", "mom-spectrum", "msaexp-source"):
            continue
        destination = (
            ROOT / pin["repo_path"] if pin.get("repo_path") else args.cache / pin["filename"]
        )
        if not destination.exists() and args.acquire:
            fetch_product(pin, destination, max_bytes=pin["max_bytes"], timeout=60)
        verify_pin(destination, pin)
        locations[pin["id"]] = destination
    report = audit(locations["mom-pixtab"], locations["mom-spectrum"], locations["msaexp-source"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
