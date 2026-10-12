"""Fixed literature-frequency TESS/QLP pilot, with explicit window controls."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from astropy.io import fits

OUT = Path("research_output")
FREQ = 2.6184922
PERIOD = 87.4549
EPOCH = 2455668.82920 - 2457000
SIDES = [(2.61912, 15), (2.61832, 11), (2.61901, 6)]


def fit(t: np.ndarray, y: np.ndarray, frequencies: list[float], dt: float) -> dict:
    order = np.argsort(t)
    t = t[order]
    y = y[order]
    seg = np.cumsum(np.r_[0, np.diff(t) > 0.5])
    nuisance = []
    for s in np.unique(seg):
        mask = seg == s
        z = np.zeros(len(t))
        z[mask] = (t[mask] - np.mean(t[mask])) / max(np.ptp(t[mask]), 1)
        for power in range(3):
            nuisance.append(np.where(mask, z**power, 0))
    trig = []
    for f in frequencies:
        a = 2 * np.pi * f * (t - EPOCH)
        trig += [np.cos(a), np.sin(a)]
    x = np.column_stack(trig + nuisance)
    coef, _, rank, sval = np.linalg.lstsq(x, y, rcond=None)
    residual = y - x @ coef
    cov = np.linalg.pinv(x.T @ x) * np.sum(residual**2) / max(len(t) - rank, 1)
    a, b = coef[:2]
    amp = np.hypot(a, b)
    jac = np.array([a, b]) / amp if amp else np.ones(2)
    atten = np.sinc(FREQ * dt)
    return dict(
        n=len(t),
        baseline_days=float(np.ptp(t)),
        segments=int(seg.max() + 1),
        amplitude_ppm=float(amp * 1e6 / atten),
        white_error_ppm=float(np.sqrt(jac @ cov[:2, :2] @ jac) * 1e6 / atten),
        phase_rad=float(np.arctan2(-b, a)),
        rms_ppm=float(np.std(residual) * 1e6),
        design_condition=float(sval[0] / sval[-1]),
        rank=int(rank),
    )


def main() -> None:
    rows = []
    for entry in json.loads((OUT / "research5_stellar_inputs.json").read_text()):
        with fits.open(entry["compressed_path"]) as h:
            d = h[1].data
            hd = h[1].header
            ph = h[0].header
            t = np.asarray(d["TIME"], dtype=float)
            q = np.asarray(d["QUALITY"]) == 0
            phase = ((t - EPOCH) / PERIOD + 0.5) % 1 - 0.5
            keep = q & np.isfinite(t) & (np.abs(phase) >= 0.04)
            dt = float(hd["TIMEDEL"])
            row = {
                "sector": entry["sector"],
                "camera": ph.get("CAMERA"),
                "ccd": ph.get("CCD"),
                "apertures": {k: hd.get(k) for k in ["BESTAP", "SMALLAP", "LARGEAP"]},
                "timedel_days": dt,
                "all_rows": len(t),
                "kept_after_quality_periastron": int(keep.sum()),
                "quality_rejected": int((~q).sum()),
                "periastron_rejected": int((q & ~keep).sum()),
                "time_min": float(np.nanmin(t)),
                "time_max": float(np.nanmax(t)),
                "fits": {},
            }
            for col in [
                "SAP_FLUX",
                "KSPSAP_FLUX",
                "KSPSAP_FLUX_SML",
                "KSPSAP_FLUX_LAG",
                "DET_FLUX",
                "DET_FLUX_SML",
                "DET_FLUX_LAG",
                "SYS_RM_FLUX",
            ]:
                if col not in d.names:
                    continue
                y = np.asarray(d[col], dtype=float)
                k = keep & np.isfinite(y)
                tt = t[k]
                yy = y[k] / np.median(y[k]) - 1
                if len(tt) < 100:
                    continue
                full = fit(tt, yy, [FREQ], dt)
                full["adjacent_harmonics"] = fit(tt, yy, [FREQ, 228 / PERIOD, 230 / PERIOD], dt)
                halves = []
                for m in [tt <= np.median(tt), tt > np.median(tt)]:
                    halves.append(fit(tt[m], yy[m], [FREQ], dt))
                full["halves"] = halves
                # Exact coefficient perturbation for three fixed known neighbors,
                # sampled through these timestamps, over unknown phase envelopes.
                leakage = 0.0
                for sf, ppm in SIDES:
                    vals = []
                    for p in np.arange(8) * np.pi / 4:
                        injected = (
                            ppm
                            * 1e-6
                            * np.sinc(sf * dt)
                            * np.cos(2 * np.pi * sf * (tt - EPOCH) + p)
                        )
                        vals.append(fit(tt, injected, [FREQ], dt)["amplitude_ppm"])
                    leakage += max(vals)
                full["known_neighbor_worst_linear_leakage_ppm"] = float(leakage)
                injected = 1e-3 * np.sinc(FREQ * dt) * np.cos(2 * np.pi * FREQ * (tt - EPOCH))
                full["1000ppm_integration_aware_window_recovery_ppm"] = fit(
                    tt, injected, [FREQ], dt
                )["amplitude_ppm"]
                row["fits"][col] = full
            rows.append(row)
    report = {
        "target": "KIC8164262/TIC159649612",
        "frequency_per_day": FREQ,
        "status": "exploratory measurement; white errors are not total uncertainties",
        "rows": rows,
    }
    (OUT / "research5_stellar_measurements.json").write_text(json.dumps(report, indent=2) + "\n")
    for r in rows:
        print(r["sector"], r["camera"], r["ccd"], r["apertures"])
        for col, v in r["fits"].items():
            print(
                col,
                round(v["amplitude_ppm"], 1),
                round(v["white_error_ppm"], 1),
                "halves",
                [round(x["amplitude_ppm"], 1) for x in v["halves"]],
                "adj",
                round(v["adjacent_harmonics"]["amplitude_ppm"], 1),
            )


if __name__ == "__main__":
    main()
