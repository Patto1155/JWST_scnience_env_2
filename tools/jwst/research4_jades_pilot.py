"""Frozen GOODS-S metadata pilot; no GOODS-N outcome access or physical p-values."""

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path

import numpy as np
from astropy.io import fits

from tools.jwst.jades_balmer_pilot import fit_line


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def freeze(catalog: Path, manifest: Path) -> None:
    """Read field first, then only GOODS-S rows, exclusively metadata columns."""
    digest = hashlib.sha256(catalog.read_bytes()).hexdigest()
    if digest != "4b4e7fd4306208ee801406c7ed73fdab895a2e67184af7f639a91e5f9c8ab7d4":
        raise ValueError("Catalog hash disagrees with verified DR4 acquisition")
    targets = []
    counts = {}
    with fits.open(catalog, memmap=True) as h:
        south = np.flatnonzero(h[1].data["Field"] == "GS")
        o = h[1].data[south]
        z = o["z_Spec"]
        base = np.isin(o["z_Spec_flag"], ["A", "B"])
        base &= (o["tExp_G140M"] > 0) & (o["tExp_G235M"] > 0)
        for group, lower, upper in (("lower_z", 2.45, 2.60), ("interior_z", 2.70, 2.90)):
            eligible = np.flatnonzero(base & (z >= lower) & (z < upper))
            counts[group] = int(len(eligible))
            ordered = sorted(
                eligible,
                key=lambda i: (
                    -min(o["tExp_G140M"][i], o["tExp_G235M"][i]),
                    str(o["Unique_ID"][i]),
                ),
            )
            members = []
            for i in ordered:
                uid = str(o["Unique_ID"][i])
                if uid in ("goods-s-deepjwst_7496", "goods-s-mediumjwst_8656"):
                    continue
                ra, dec = float(o["RA_TARG"][i]), float(o["Dec_TARG"][i])
                dr5 = int(o["NIRCam_DR5_ID"][i])
                duplicate = any(
                    (dr5 > 0 and dr5 == x["dr5_id"])
                    or np.hypot((ra - x["ra_deg"]) * np.cos(np.deg2rad(dec)), dec - x["dec_deg"])
                    * 3600
                    <= 0.2
                    for x in targets + members
                )
                if duplicate:
                    continue
                members.append(
                    dict(
                        unique_id=uid,
                        target=int(o["NIRSpec_ID"][i]),
                        tier=str(o["TIER"][i]),
                        z=float(z[i]),
                        group=group,
                        ra_deg=ra,
                        dec_deg=dec,
                        dr5_id=dr5,
                        catalog_index=int(south[i]),
                        exposure_g140m_s=float(o["tExp_G140M"][i]),
                        exposure_g235m_s=float(o["tExp_G235M"][i]),
                    )
                )
                if len(members) == 6:
                    break
            targets.extend(members)
    write_json(
        manifest,
        dict(
            version="research4-jades-gs-metadata-v1",
            scope="GOODS-S metadata only; GOODS-N outcomes unopened; no ratio or SNR selection",
            catalog_sha256=digest,
            metadata_eligible_observation_rows=counts,
            targets=targets,
            exclusions=["goods-s-deepjwst_7496", "goods-s-mediumjwst_8656"],
            selection=(
                "A/B; paired positive exposures; fixed z bins; decreasing minimum exposure "
                "then Unique_ID; positive DR5 or <=0.2 arcsec dedup; six per bin; no replacement"
            ),
            fit_contract=(
                "5pix FLUX primary; Hb4862.68 and OIII5008.24; fixed +/-0.015um integrated "
                "Gaussian+linear continuum; full rank/convergence/no active bounds; primary "
                "box +/-0.0035um >=90% finite, >=2 line bins, >=4 red sideband bins "
                "at +0.008..0.015um"
            ),
            endpoint=(
                "D=log(Hb235/Hb140)-log(OIII235/OIII140); positive valid fits only; counts "
                "include negative or unavailable measurements; >=4 valid per group or stop; "
                "descriptive only, no calibrated p-value"
            ),
            sensitivities=(
                "3pix and FLUX_NOD2 dependent checks; independent box integration reviewer"
            ),
            max_download_bytes=100_000_000,
            max_compute_seconds=300,
        ),
    )


def coverage(data, center: float, field: str, errfield: str) -> dict:
    w = np.asarray(data["WAVELENGTH"])
    if w.ndim != 1 or len(w) < 2 or not np.all(np.isfinite(w)):
        raise ValueError("Expected a finite one-dimensional wavelength grid")
    dw = float(np.median(np.diff(w)))
    if dw <= 0 or not np.allclose(np.diff(w), dw, rtol=1e-7, atol=1e-12):
        raise ValueError("Expected a strictly increasing uniform wavelength grid")
    valid = np.isfinite(data[field]) & np.isfinite(data[errfield]) & (data[errfield] > 0)
    overlap = np.maximum(
        0, np.minimum(w + dw / 2, center + 0.0035) - np.maximum(w - dw / 2, center - 0.0035)
    )
    frac = float(np.sum(overlap[valid]) / 0.007)
    side = valid & (w >= center + 0.008) & (w <= center + 0.015)
    edge = float(center - np.min(w[valid])) if np.any(valid) else None
    return dict(
        primary_box_fraction=min(frac, 1.0),
        primary_box_bins=int(np.sum(valid & (overlap > 0))),
        red_sideband_bins=int(np.sum(side)),
        finite_blue_edge_distance_um=edge,
        eligible=bool(frac >= 0.9 and np.sum(valid & (overlap > 0)) >= 2 and np.sum(side) >= 4),
    )


def validate_product(hdus, target: dict, config: str) -> None:
    header = hdus[0].header
    filt, grating = config.upper().split("-")
    required = dict(
        GRATING=grating, FILTER=filt, HLSPTIER=target["tier"], HLSPVER="1.0", HLSPID="JADES"
    )
    if int(header["TARGET"]) != target["target"]:
        raise ValueError("Product TARGET disagrees with frozen manifest")
    for key, value in required.items():
        if str(header.get(key)) != value:
            raise ValueError(f"Product {key} disagrees with frozen contract")
    if not np.isclose(header["RA"], target["ra_deg"], rtol=0, atol=1e-5):
        raise ValueError("Product RA disagrees with frozen manifest")
    if not np.isclose(header["DEC"], target["dec_deg"], rtol=0, atol=1e-5):
        raise ValueError("Product DEC disagrees with frozen manifest")
    for aperture in (5, 3):
        columns = hdus[f"EXTRACT{aperture}PIX1D"].columns
        if columns["WAVELENGTH"].unit != "um":
            raise ValueError("Unexpected wavelength units")
        for field in ("FLUX", "FLUX_ERR", "FLUX_NOD2", "FLUX_ERR_NOD2"):
            if columns[field].unit != "erg s-1 cm-2 AA-1":
                raise ValueError("Unexpected flux-density units")


def run(manifest: Path, data_root: Path, output: Path, receipt: Path | None = None) -> None:
    plan = json.loads(manifest.read_text())
    data_root.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    previous = receipt if receipt is not None else output if output.exists() else None
    pinned = {}
    if previous is not None:
        pinned = {
            x["name"]: x["sha256"]
            for x in json.loads(previous.read_text())["downloads"]
            if "sha256" in x
        }
    downloads = []
    results = []
    transferred = 0
    compute_seconds = 0.0
    for target in plan["targets"]:
        row = dict(target)
        row["measurements"] = {}
        for config in ("f070lp-g140m", "f170lp-g235m"):
            name = (
                f"hlsp_jades_jwst_nirspec_{target['tier']}-"
                f"{target['target']:08d}_{config}_v1.0_x1d.fits"
            )
            url = f"https://jades.herts.ac.uk/DR4/goods-s/spectra/{config}/{target['tier']}/{name}"
            path = data_root / name
            was_cached = path.exists()
            if was_cached and name not in pinned:
                raise ValueError("Cached products require a pinned acquisition receipt")
            if not path.exists():
                remaining = plan["max_download_bytes"] - transferred
                try:
                    with urllib.request.urlopen(url, timeout=60) as response:
                        body = response.read(remaining + 1)
                except (OSError, urllib.error.URLError) as error:
                    downloads.append(
                        dict(
                            unique_id=target["unique_id"],
                            url=url,
                            name=name,
                            outcome="acquisition_failure",
                            detail=str(error),
                        )
                    )
                    for aperture in (5, 3):
                        for field in ("FLUX", "FLUX_NOD2"):
                            for line in ("Hb", "OIII"):
                                row["measurements"][f"{config}_{aperture}pix_{field}_{line}"] = (
                                    dict(
                                        coverage=dict(eligible=False),
                                        fit=dict(outcome="acquisition_failure", flux_1e20=None),
                                    )
                                )
                    continue
                if len(body) > remaining:
                    raise RuntimeError("Download budget exceeded")
                transferred += len(body)
                path.write_bytes(body)
            body = path.read_bytes()
            digest = hashlib.sha256(body).hexdigest()
            if name in pinned and digest != pinned[name]:
                raise ValueError("Cached product hash disagrees with acquisition receipt")
            downloads.append(
                dict(
                    unique_id=target["unique_id"],
                    url=url,
                    name=name,
                    bytes=len(body),
                    sha256=digest,
                )
            )
            with fits.open(path) as h:
                validate_product(h, target, config)
                compact = {}
                for aperture in (5, 3):
                    d = h[f"EXTRACT{aperture}PIX1D"].data
                    for column in d.names:
                        compact[f"{aperture}pix_{column}"] = np.array(d[column])
                    for field, error in (("FLUX", "FLUX_ERR"), ("FLUX_NOD2", "FLUX_ERR_NOD2")):
                        for line, rest in (("Hb", 4862.68), ("OIII", 5008.24)):
                            key = f"{config}_{aperture}pix_{field}_{line}"
                            cov = coverage(d, rest * (1 + target["z"]) / 10000, field, error)
                            value = dict(outcome="coverage_failure", flux_1e20=None)
                            if cov["eligible"]:
                                started = time.perf_counter()
                                try:
                                    value = fit_line(d, rest, target["z"], 0.015, field, error)[0]
                                except ValueError as e:
                                    value = dict(
                                        outcome="fit_failure", detail=str(e), flux_1e20=None
                                    )
                                compute_seconds += time.perf_counter() - started
                                if compute_seconds > plan["max_compute_seconds"]:
                                    raise RuntimeError("Numerical computation budget exceeded")
                            row["measurements"][key] = dict(coverage=cov, fit=value)
                np.savez_compressed(
                    output.parent / f"research4_jades_{target['unique_id']}_{config}_inputs.npz",
                    **compact,
                )
        row["differential_log_ratio"] = endpoint(row["measurements"])
        results.append(row)
        write_json(
            output,
            dict(
                status="running",
                manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                targets=results,
                downloads=downloads,
                transferred_bytes=transferred,
            ),
        )
    groups = {}
    for group in ("lower_z", "interior_z"):
        vals = [
            x["differential_log_ratio"]
            for x in results
            if x["group"] == group and x["differential_log_ratio"] is not None
        ]
        groups[group] = dict(
            selected=6,
            valid=len(vals),
            median_D=float(np.median(vals)) if vals else None,
            positive_D=int(sum(v > 0 for v in vals)),
        )
    enough = all(x["valid"] >= 4 for x in groups.values())
    write_json(
        output,
        dict(
            status="complete" if enough else "stop_insufficient_valid_groups",
            scope=(
                "Actual released coadd data; selected metadata pilot; descriptive only; "
                "diagonal fit errors uncalibrated; no GOODS-N outcomes"
            ),
            manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
            groups=groups,
            targets=results,
            downloads=downloads,
            transferred_bytes=transferred,
            total_product_bytes=sum(x.get("bytes", 0) for x in downloads),
            fit_compute_seconds=compute_seconds,
        ),
    )


def endpoint(measurements: dict) -> float | None:
    flux = {}
    for config in ("f070lp-g140m", "f170lp-g235m"):
        for line in ("Hb", "OIII"):
            m = measurements[f"{config}_5pix_FLUX_{line}"]
            f = m["fit"].get("flux_1e20")
            if (
                not m["coverage"]["eligible"]
                or not m["fit"].get("covariance_valid")
                or f is None
                or f <= 0
            ):
                return None
            flux[config, line] = f
    return float(
        np.log(flux["f170lp-g235m", "Hb"] / flux["f070lp-g140m", "Hb"])
        - np.log(flux["f170lp-g235m", "OIII"] / flux["f070lp-g140m", "OIII"])
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--download-receipt", type=Path)
    a = parser.parse_args()
    if a.action == "freeze":
        freeze(a.catalog, a.manifest)
    else:
        run(a.manifest, a.data_root, a.output, a.download_receipt)


if __name__ == "__main__":
    main()
