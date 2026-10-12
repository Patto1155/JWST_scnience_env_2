"""Bounded JADES Balmer remeasurement of released coadds, not raw reduction.

Reported fit errors assume independent supplied coadd errors, with no calibration
covariance. Aperture/nod variants are dependent. No population or physics claim.
"""

import argparse
import hashlib
import json
import time
from pathlib import Path

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from scipy.optimize import least_squares
from scipy.special import ndtr


def fit_line(
    d, rest: float, z: float, window: float = 0.015, field: str = "FLUX", errfield: str = "FLUX_ERR"
) -> tuple[dict, tuple]:
    w = d["WAVELENGTH"]
    cen = rest * (1 + z) / 10000.0
    sel = abs(w - cen) < window
    sel &= np.isfinite(d[field]) & np.isfinite(d[errfield]) & (d[errfield] > 0)
    x = w[sel]
    y = d[field][sel] / 1e-20
    e = d[errfield][sel] / 1e-20
    dw = np.median(np.diff(w))
    xx = (x - cen) / window
    lines = np.array([6549.86, 6564.61, 6585.27]) if rest > 6000 else np.array([rest])
    centers = lines * (1 + z) / 10000.0

    def pred(t):
        center = centers + t[2]
        sig = t[3]
        g = (
            ndtr((x[:, None] + dw / 2 - center) / sig) - ndtr((x[:, None] - dw / 2 - center) / sig)
        ) / (dw * 10000.0)
        if len(lines) > 1:
            return t[0] + t[1] * xx + g @ np.array([t[5] / 2.96, t[4], t[5]])
        return t[0] + t[1] * xx + g[:, 0] * t[4]

    if len(y) <= (6 if len(lines) > 1 else 5):
        raise ValueError("Insufficient finite line-window pixels")
    initial = [np.median(y), 0, 0.0001, dw, 0.0] + ([10] if len(lines) > 1 else [])
    initial[4] = max(10, np.sum(y - np.median(y)) * dw * 10000.0)
    lower = [-np.inf, -np.inf, -0.003, 0.2 * dw, -np.inf] + ([-np.inf] if len(lines) > 1 else [])
    upper = [np.inf, np.inf, 0.003, 3 * dw, np.inf] + ([np.inf] if len(lines) > 1 else [])
    res = least_squares(lambda t: (pred(t) - y) / e, initial, bounds=(lower, upper), max_nfev=1000)
    scale = np.linalg.norm(res.jac, axis=0)
    safe = np.all(scale > 0)
    rank = int(np.linalg.matrix_rank(res.jac / np.where(scale > 0, scale, 1)))
    covariance_valid = bool(
        safe and rank == len(res.x) and res.success and (not np.any(res.active_mask))
    )
    cov = (
        np.linalg.pinv((res.jac / scale).T @ (res.jac / scale)) / scale[:, None] / scale[None, :]
        if safe
        else np.full((len(res.x), len(res.x)), np.nan)
    )
    out = dict(
        covariance_valid=covariance_valid,
        jacobian_rank=rank,
        n_parameters=len(res.x),
        NII6585_flux_1e20=float(res.x[5]) if len(lines) > 1 else None,
        flux_1e20=float(res.x[4]),
        diagonal_err_1e20=float(np.sqrt(cov[4, 4])) if covariance_valid else None,
        center_um=float(cen + res.x[2]),
        sigma_um=float(res.x[3]),
        chi2_diag=float(np.sum(res.fun**2)),
        dof=len(y) - len(res.x),
        n=len(y),
        success=bool(res.success),
        continuum_at_line_1e20=float(res.x[0]),
    )
    if not covariance_valid:
        out["optimizer_diagnostics"] = {
            key: out[key] for key in ("flux_1e20", "center_um", "sigma_um", "NII6585_flux_1e20")
        }
        for key in ("flux_1e20", "center_um", "sigma_um", "NII6585_flux_1e20"):
            out[key] = None
        out["outcome"] = "unidentifiable_or_nonconverged"
    else:
        out["outcome"] = "conditional_fit"
    return (out, (x, y, e, pred(res.x)))


def spectrum_key(target: str, config: str, aperture: int, field: str, line: str) -> str:
    """Include target identity to prevent cross-target replay/figure overwrite."""
    return f"{target}_{config}_{aperture}pix_{field}_{line}"


def run_candidate(directory: Path, target: str, tier: str, z: float, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    windows = {}
    sources = []
    inputs = {}
    for config in ("f070lp-g140m", "f170lp-g235m"):
        path = (
            directory / f"hlsp_jades_jwst_nirspec_{tier}-{int(target):08d}_{config}_v1.0_x1d.fits"
        )
        sources.append(
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
        with fits.open(path) as h:
            for aperture in (5, 3):
                d = h[f"EXTRACT{aperture}PIX1D"].data
                for column in d.names:
                    inputs[f"{target}_{config}_{aperture}pix_{column}"] = np.array(d[column])
                for field, err in (("FLUX", "FLUX_ERR"), ("FLUX_NOD2", "FLUX_ERR_NOD2")):
                    lines = (
                        (("Hb", 4862.68), ("Ha", 6564.61))
                        if config == "f170lp-g235m"
                        else (("Hb", 4862.68), ("Hg", 4341.68), ("Hd", 4102.89))
                    )
                    for label, rest in lines:
                        key = spectrum_key(target, config, aperture, field, label)
                        value, arrays = fit_line(
                            d, rest, z, 0.02 if label == "Ha" else 0.015, field, err
                        )
                        results[key] = value
                        for suffix, a in zip(("wave", "flux", "error", "model"), arrays):
                            windows[f"{key}_{suffix}"] = a
    np.savez_compressed(output / f"jades_balmer_{target}_windows.npz", **windows)
    np.savez_compressed(output / f"jades_balmer_{target}_inputs.npz", **inputs)
    result = {
        "target": target,
        "tier": tier,
        "z": z,
        "method": (
            "Pixel-integrated Gaussian plus linear continuum, fixed windows; "
            "Halpha plus NII doublet with fixed ratio2.96; supplied diagonal errors only"
        ),
        "scope": "Released coadd remeasurement, not raw exposure reduction; variants dependent",
        "sources": sources,
        "results": results,
    }
    (output / f"jades_balmer_{target}_fits.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    return result


def select_catalog(catalog: Path) -> dict:
    """Frozen GOODS-S discovery screen; GOODS-N outcomes never scanned."""
    t0 = time.time()
    with fits.open(catalog) as h:
        o = h[1].data
        a = h["R1000_5pix"].data
        b = h["R1000_3pix"].data
        assert np.array_equal(o["Unique_ID"], a["Unique_ID"]) and np.array_equal(
            o["Unique_ID"], b["Unique_ID"]
        )
        catalog_rows = len(o)
        original_indices = np.flatnonzero(o["Field"] == "GS")
        o = o[original_indices]
        a = a[original_indices]
        b = b[original_indices]
        south = np.ones(len(o), dtype=bool)
        z = o["z_Spec"]
        robust = np.isin(o["z_Spec_flag"], ["A", "B"])
        af = a["HBaA_6563_flux"]
        bf = a["HBaB_4861_flux"]
        ae = a["HBaA_6563_flux_err"]
        be = a["HBaB_4861_flux_err"]
        valid = (
            np.isfinite(af)
            & np.isfinite(bf)
            & np.isfinite(ae)
            & np.isfinite(be)
            & (af > 0)
            & (bf > 0)
            & (ae > 0)
            & (be > 0)
        )
        snr = (af / ae >= 10) & (bf / be >= 10)
        same = a["HBaA_6563_filter"] == a["HBaB_4861_filter"]
        selected = np.flatnonzero(south & robust & (z > 2) & (z < 7) & valid & snr & same)
        coords = SkyCoord(o["RA_TARG"][selected] * u.deg, o["Dec_TARG"][selected] * u.deg)
        score = np.minimum(af[selected] / ae[selected], bf[selected] / be[selected])
        keep = []
        seen = set()
        for k in np.argsort(-score):
            if int(k) in seen:
                continue
            sep = coords[k].separation(coords).arcsec
            seen.update(np.flatnonzero(sep <= 0.2).tolist())
            keep.append(int(selected[k]))
        rows = []
        for i in keep:
            r5 = float(af[i] / bf[i])
            d5 = float((af[i] - 2.65 * bf[i]) / np.hypot(ae[i], 2.65 * be[i]))
            ba = b["HBaA_6563_flux"][i]
            bb = b["HBaB_4861_flux"][i]
            ea = b["HBaA_6563_flux_err"][i]
            eb = b["HBaB_4861_flux_err"][i]
            r3 = float(ba / bb) if ba > 0 and bb > 0 and np.isfinite(ba + bb) else None
            d3 = (
                float((ba - 2.65 * bb) / np.hypot(ea, 2.65 * eb))
                if r3 and ea > 0 and (eb > 0)
                else None
            )
            rows.append(
                dict(
                    index=int(original_indices[i]),
                    Unique_ID=str(o["Unique_ID"][i]),
                    NIRSpec_ID=int(o["NIRSpec_ID"][i]),
                    TIER=str(o["TIER"][i]),
                    z=float(z[i]),
                    RA=float(o["RA_TARG"][i]),
                    Dec=float(o["Dec_TARG"][i]),
                    ratio_5=r5,
                    ratio_3=r3,
                    threshold_residual_diag_5=d5,
                    threshold_residual_diag_3=d3,
                    min_snr_5=float(min(af[i] / ae[i], bf[i] / be[i])),
                    filter=str(a["HBaA_6563_filter"][i]),
                    ha5=float(af[i]),
                    hb5=float(bf[i]),
                    haerr5=float(ae[i]),
                    hberr5=float(be[i]),
                )
            )
        rows.sort(key=lambda x: x["ratio_5"])
        out = dict(
            scope=(
                "catalog triage only; diagonal-error scores are uncalibrated; "
                "same photons aperture checks; GN outcome holdout unexamined"
            ),
            selected_observation_rows=len(selected),
            sky_deduplicated_rows=len(rows),
            selected_sub_2p65=sum((x["ratio_5"] < 2.65 for x in rows)),
            sub_2p65_in_both=sum(
                (
                    x["ratio_5"] < 2.65 and x["ratio_3"] is not None and (x["ratio_3"] < 2.65)
                    for x in rows
                )
            ),
            diagonal_score_below_minus3=sum((x["threshold_residual_diag_5"] < -3 for x in rows)),
            rows=rows,
            compute_elapsed_s=time.time() - t0,
            catalog_rows=catalog_rows,
            discovery_GS_observation_rows=int(np.sum(south)),
            holdout_GN_outcomes_opened=False,
        )
        return out


def run_compact(directory: Path, target: str, z: float, output: Path) -> dict:
    """Replay retained released-coadd arrays; does not reacquire or reduce raw data."""
    arrays = np.load(directory / f"jades_balmer_{target}_inputs.npz")
    reference = json.loads((directory / f"jades_balmer_{target}_fits.json").read_text())
    results = {}
    for config in ("f070lp-g140m", "f170lp-g235m"):
        for aperture in (5, 3):
            prefix = f"{target}_{config}_{aperture}pix_"
            data = {
                key[len(prefix) :]: arrays[key] for key in arrays.files if key.startswith(prefix)
            }
            for field, err in (("FLUX", "FLUX_ERR"), ("FLUX_NOD2", "FLUX_ERR_NOD2")):
                lines = (
                    (("Hb", 4862.68), ("Ha", 6564.61))
                    if config == "f170lp-g235m"
                    else (("Hb", 4862.68), ("Hg", 4341.68), ("Hd", 4102.89))
                )
                for label, rest in lines:
                    key = spectrum_key(target, config, aperture, field, label)
                    results[key] = fit_line(
                        data, rest, z, 0.02 if label == "Ha" else 0.015, field, err
                    )[0]
    reference["results"] = results
    reference["scope"] = (
        "Compact replay of retained released-coadd arrays, not a raw-data reduction"
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / f"jades_balmer_{target}_compact_replay.json").write_text(
        json.dumps(reference, indent=2, allow_nan=False) + "\n"
    )
    return reference


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    catalog = args.directory / "Combined_DR4_external_v1.2.1.fits"
    if catalog.exists() and not args.replay:
        selected = select_catalog(catalog)
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "jades_balmer_catalog_pilot.json").write_text(
            json.dumps(selected, indent=2, allow_nan=False) + "\n"
        )
    for target, tier, z in [
        ("7496", "goods-s-deepjwst", 2.493465347981974),
        ("8656", "goods-s-mediumjwst", 2.9727409777018314),
    ]:
        result = (
            run_compact(args.directory, target, z, args.output)
            if args.replay
            else run_candidate(args.directory, target, tier, z, args.output)
        )
        print(target, len(result["results"]))


if __name__ == "__main__":
    main()
