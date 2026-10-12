"""Independent SVD/QR remeasurement of the frozen QLP stellar mode pilot.

Operator-only workflow. These are conditional aperture flux amplitudes, not
intrinsic stellar amplitudes or calibrated tidal-evolution detections.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits
from scipy import linalg

FREQUENCY = 2.6184922
ORBIT_DAYS = 87.4549
EPOCH_BTJD = 2455668.82920 - 2457000
SIDEBANDS = ((2.61912, 15.0), (2.61832, 11.0), (2.61901, 6.0))
FLUX_COLUMNS = (
    "SAP_FLUX",
    "KSPSAP_FLUX",
    "KSPSAP_FLUX_SML",
    "KSPSAP_FLUX_LAG",
    "DET_FLUX",
    "DET_FLUX_SML",
    "DET_FLUX_LAG",
    "SYS_RM_FLUX",
)


def design(
    time: np.ndarray,
    frequencies: list[float],
    degree: int = 2,
    auxiliary: np.ndarray | None = None,
) -> np.ndarray:
    columns: list[np.ndarray] = []
    for frequency in frequencies:
        angle = 2 * np.pi * frequency * (time - EPOCH_BTJD)
        columns.extend((np.cos(angle), np.sin(angle)))
    segment = np.cumsum(np.r_[0, np.diff(time) > 0.5])
    for label in np.unique(segment):
        member = segment == label
        coordinate = (time - np.mean(time[member])) / max(np.ptp(time[member]), 1)
        for power in range(degree + 1):
            columns.append(np.where(member, coordinate**power, 0))
        if auxiliary is not None:
            for vector in auxiliary.T:
                centered = vector - np.mean(vector[member])
                if np.std(centered[member]) > 0:
                    columns.append(np.where(member, centered / np.std(centered[member]), 0))
    return np.column_stack(columns)


def fit_mode(
    time: np.ndarray,
    flux: np.ndarray,
    cadence_days: float,
    degree: int = 2,
    frequencies: list[float] | None = None,
    auxiliary: np.ndarray | None = None,
) -> dict[str, Any]:
    """Rank-revealing QR fit with separately computed SVD diagnostics/operator."""
    matrix = design(time, frequencies or [FREQUENCY], degree, auxiliary)
    scales = np.linalg.norm(matrix, axis=0)
    zero_columns = int(np.sum(scales == 0))
    matrix = matrix[:, scales > 0]
    scales = scales[scales > 0]
    scaled = matrix / scales
    coefficient_scaled, _, rank, _ = linalg.lstsq(scaled, flux, lapack_driver="gelsy")
    coefficient = coefficient_scaled / scales
    singular = linalg.svdvals(scaled)
    operator = linalg.pinv(scaled) / scales[:, None]
    residual = flux - matrix @ coefficient
    attenuation = np.sinc(FREQUENCY * cadence_days)
    amplitude = np.linalg.norm(coefficient[:2])
    white_covariance = (
        operator[:2] @ operator[:2].T * np.sum(residual**2) / max(len(time) - rank, 1)
    )
    direction = coefficient[:2] / amplitude if amplitude else np.zeros(2)
    white_error = np.sqrt(max(float(direction @ white_covariance @ direction), 0))
    # Exact phase-envelope bound: largest singular value of the two-dimensional
    # map from unit sideband quadratures to target quadratures, with integration.
    leakage = 0.0
    for frequency, ppm in SIDEBANDS:
        angle = 2 * np.pi * frequency * (time - EPOCH_BTJD)
        side_matrix = np.column_stack((np.cos(angle), np.sin(angle)))
        mapped = operator[:2] @ side_matrix
        leakage += ppm * linalg.svdvals(mapped)[0] * np.sinc(frequency * cadence_days)
    injected = 1e-3 * attenuation * matrix[:, 0]
    recovered = np.linalg.norm((operator @ injected)[:2]) * 1e6 / attenuation
    return {
        "n": len(time),
        "baseline_days": float(np.ptp(time)),
        "amplitude_ppm": float(amplitude * 1e6 / attenuation),
        "cosine_coefficient_ppm": float(coefficient[0] * 1e6 / attenuation),
        "sine_coefficient_ppm": float(coefficient[1] * 1e6 / attenuation),
        "phase_rad": float(np.arctan2(-coefficient[1], coefficient[0])),
        "conditional_white_error_ppm": float(white_error * 1e6 / attenuation),
        "residual_rms_ppm": float(np.sqrt(np.mean(residual**2)) * 1e6),
        "normalized_design_condition": float(singular[0] / singular[-1]),
        "rank": int(rank),
        "columns": matrix.shape[1],
        "zero_nuisance_columns_removed": zero_columns,
        "all_parameters_identifiable": bool(rank == matrix.shape[1]),
        "known_sideband_phase_envelope_ppm": float(leakage / attenuation),
        "integration_aware_1000ppm_control_recovery": float(recovered),
    }


def review(manifest: Path) -> dict[str, Any]:
    rows = []
    epoch_data: dict[str, dict[int, tuple[np.ndarray, np.ndarray, float]]] = {}
    epoch_auxiliary: dict[str, dict[int, np.ndarray]] = {}
    for entry in sorted(json.loads(manifest.read_text()), key=lambda r: r["sector"]):
        path = Path(entry["compressed_path"])
        artifact = path.read_bytes()
        body = gzip.decompress(artifact)
        if len(body) != entry["body_bytes"] or hashlib.sha256(body).hexdigest() != entry["sha256"]:
            raise ValueError(f"Input identity mismatch: {path}")
        with fits.open(io.BytesIO(body)) as hdus:
            header, table_header, data = hdus[0].header, hdus[1].header, hdus[1].data
            if int(header["TICID"]) != 159649612 or int(header["SECTOR"]) != entry["sector"]:
                raise ValueError("Wrong target or sector")
            if table_header["BJDREFI"] != 2457000 or table_header["TIMESYS"] != "TDB":
                raise ValueError("Unexpected barycentric time convention")
            time = np.asarray(data["TIME"], dtype=float)
            phase = ((time - EPOCH_BTJD) / ORBIT_DAYS + 0.5) % 1 - 0.5
            baseline = np.isfinite(time) & (data["QUALITY"] == 0) & (np.abs(phase) >= 0.04)
            cadence = float(table_header["TIMEDEL"])
            row: dict[str, Any] = {
                "sector": entry["sector"],
                "source_sha256": entry["sha256"],
                "artifact_sha256": hashlib.sha256(artifact).hexdigest(),
                "camera": header.get("CAMERA"),
                "ccd": header.get("CCD"),
                "cadence_days": cadence,
                "crowdsap": table_header.get("CROWDSAP", header.get("CROWDSAP")),
                "flfrcsap": table_header.get("FLFRCSAP", header.get("FLFRCSAP")),
                "detrending_method": table_header.get("DETMET", header.get("DETMET")),
                "aperture_keywords": {
                    k: table_header.get(k) for k in ("BESTAP", "SMALLAP", "LARGEAP")
                },
                "available_flux_columns": [c for c in FLUX_COLUMNS if c in data.names],
                "all_rows": len(time),
                "quality_periastron_kept": int(np.sum(baseline)),
                "measurements": {},
            }
            for column in FLUX_COLUMNS:
                if column not in data.names:
                    continue
                flux = np.asarray(data[column], dtype=float)
                keep = baseline & np.isfinite(flux)
                if np.sum(keep) < 100:
                    row["measurements"][column] = {
                        "outcome": "insufficient_finite_flux",
                        "finite_kept_rows": int(np.sum(keep)),
                    }
                    continue
                t, y = time[keep], flux[keep]
                order = np.argsort(t)
                t, y = t[order], y[order]
                median = float(np.median(y))
                if median == 0:
                    raise ValueError("Cannot normalize zero median flux")
                y = y / median - 1
                epoch_data.setdefault(column, {})[entry["sector"]] = (t, y, cadence)
                primary = fit_mode(t, y, cadence)
                primary["first_btjd"] = float(t[0])
                primary["last_btjd"] = float(t[-1])
                primary["observed_cadence_days"] = float(np.median(np.diff(t)))
                primary["sample_coverage_days"] = float(len(t) * cadence)
                primary["integration_sinc"] = float(np.sinc(FREQUENCY * cadence))
                primary["sampling_window_modulus_at_offsets"] = {
                    str(frequency - FREQUENCY): float(
                        abs(np.mean(np.exp(2j * np.pi * (frequency - FREQUENCY) * (t - t[0]))))
                    )
                    for frequency in [228 / ORBIT_DAYS, 230 / ORBIT_DAYS]
                    + [frequency for frequency, _ in SIDEBANDS]
                }
                primary["linear_trend_sensitivity"] = fit_mode(t, y, cadence, degree=1)
                primary["adjacent_orbital_harmonics"] = fit_mode(
                    t, y, cadence, frequencies=[FREQUENCY, 228 / ORBIT_DAYS, 230 / ORBIT_DAYS]
                )
                halves = []
                for subset in (t <= np.median(t), t > np.median(t)):
                    halves.append(fit_mode(t[subset], y[subset], cadence))
                primary["halves"] = halves
                auxiliary = np.column_stack(
                    [
                        np.asarray(data[c], dtype=float)[keep][order]
                        for c in ("SAP_X", "SAP_Y", "SAP_BKG")
                    ]
                )
                if np.all(np.isfinite(auxiliary)):
                    epoch_auxiliary.setdefault(column, {})[entry["sector"]] = auxiliary
                    primary["background_centroid_sensitivity"] = fit_mode(
                        t, y, cadence, degree=1, auxiliary=auxiliary
                    )
                row["measurements"][column] = primary
            rows.append(row)
    combined_epochs: dict[str, dict[str, Any]] = {}
    for column, data in epoch_data.items():
        for label, sectors in (("sectors74_75", (74, 75)), ("sectors81_82", (81, 82))):
            if not all(sector in data for sector in sectors):
                continue
            cadences = [data[s][2] for s in sectors]
            if not np.allclose(cadences, cadences[0]):
                raise ValueError("Joint epoch requires matching integration cadence")
            times = np.concatenate([data[s][0] for s in sectors])
            fluxes = np.concatenate([data[s][1] for s in sectors])
            order = np.argsort(times)
            joint = fit_mode(times[order], fluxes[order], cadences[0])
            joint["linear_trend_sensitivity"] = fit_mode(
                times[order], fluxes[order], cadences[0], degree=1
            )
            auxiliary_data = epoch_auxiliary.get(column, {})
            if all(sector in auxiliary_data for sector in sectors):
                auxiliary = np.concatenate([auxiliary_data[s] for s in sectors])[order]
                joint["background_centroid_sensitivity"] = fit_mode(
                    times[order], fluxes[order], cadences[0], degree=1, auxiliary=auxiliary
                )
            combined_epochs.setdefault(column, {})[label] = joint
    return {
        "schema_version": 1,
        "target": "KIC8164262/TIC159649612",
        "scope": "Independent actual QLP photon remeasurement; conditional aperture amplitudes",
        "input_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "frequency_per_day": FREQUENCY,
        "period_days": ORBIT_DAYS,
        "phase_reference_btjd": EPOCH_BTJD,
        "rows": rows,
        "combined_epoch_measurements": combined_epochs,
        "GOODS_N_outcomes_opened": False,
        "physical_mode_evolution_confirmed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = review(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    for row in result["rows"]:
        raw = row["measurements"]["SAP_FLUX"]
        print(row["sector"], raw.get("amplitude_ppm"), raw.get("conditional_white_error_ppm"))


if __name__ == "__main__":
    main()
