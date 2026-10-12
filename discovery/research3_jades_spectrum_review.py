"""Direct summation oracle, independent of the Gaussian model in fit7496.py.

Boxes are deliberately sensitivity checks selected after catalogue triage. They
are not preregistered significance tests. Missing bins are not interpolated.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from astropy.io import fits


def integrate(data, center, half_width, continuum_range, flux_column, error_column):
    wave = data["WAVELENGTH"]
    flux = data[flux_column] / 1e-20
    err = data[error_column] / 1e-20
    edges = np.r_[
        wave[0] - (wave[1] - wave[0]) / 2,
        (wave[:-1] + wave[1:]) / 2,
        wave[-1] + (wave[-1] - wave[-2]) / 2,
    ]
    valid = np.isfinite(flux) & np.isfinite(err) & (err > 0)
    continuum = (
        valid & (wave - center >= continuum_range[0]) & (wave - center <= continuum_range[1])
    )
    weight = 1 / err[continuum] ** 2
    baseline = float(np.sum(weight * flux[continuum]) / np.sum(weight))
    baseline_var = 1 / np.sum(weight)
    bin_width = (
        np.maximum(
            0,
            np.minimum(edges[1:], center + half_width)
            - np.maximum(edges[:-1], center - half_width),
        )
        * 1e4
    )
    bins = (bin_width > 0) & valid
    widths = bin_width[bins]
    total_width = np.sum(widths)
    value = np.sum((flux[bins] - baseline) * widths)
    variance = np.sum((err[bins] * widths) ** 2) + total_width**2 * baseline_var
    return dict(
        flux_1e20=float(value),
        conditional_diagonal_error_1e20=float(np.sqrt(variance)),
        contributing_bins=int(sum(bins)),
        continuum_bins=int(sum(continuum)),
        finite_window_fraction=float(total_width / (2 * half_width * 1e4)),
        continuum_1e20_per_A=baseline,
    )


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source-id", choices=["7496", "8656"], default="7496")
    args = parser.parse_args(argv)
    root = args.data_root.resolve()
    settings = {
        "7496": ("goods-s-deepjwst", 2.493465347981974, 53.0670414, -27.8989151),
        "8656": ("goods-s-mediumjwst", 2.9727409777018314, 53.0616384, -27.8970538),
    }
    tier, z, ra, dec = settings[args.source_id]
    target = f"{int(args.source_id):08d}"
    hb_center, ha_center = 4862.68 * (1 + z) / 1e4, 6564.61 * (1 + z) / 1e4
    results, metadata = {}, {}
    for config in ["f070lp-g140m", "f170lp-g235m"]:
        path = root / f"hlsp_jades_jwst_nirspec_{tier}-{target}_{config}_v1.0_x1d.fits"
        with fits.open(path) as h:
            assert h[0].header["TARGET"] == target
            assert h[0].header["HLSPTIER"] == tier
            assert abs(h[0].header["RA"] - ra) < 1e-9
            assert abs(h[0].header["DEC"] - dec) < 1e-9
            assert h[1].columns["WAVELENGTH"].unit == "um"
            assert h[1].columns["FLUX"].unit == "erg s-1 cm-2 AA-1"
            d = h["EXTRACT5PIX1D"].data
            valid = np.isfinite(d["FLUX"]) & np.isfinite(d["FLUX_ERR"]) & (d["FLUX_ERR"] > 0)
            wave = d["WAVELENGTH"]
            metadata[config] = dict(
                filename=path.name,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                RA=h[0].header["RA"],
                DEC=h[0].header["DEC"],
                TARGET=h[0].header["TARGET"],
                HLSPTIER=h[0].header["HLSPTIER"],
                date_begin=h[0].header["DATE-BEG"],
                date_end=h[0].header["DATE-END"],
                first_valid_wave_um=float(wave[valid].min()),
                hb_expected_wave_um=hb_center,
                all_flux_below_first_valid_is_nonfinite=bool(
                    np.all(~np.isfinite(d["FLUX"][wave < wave[valid].min()]))
                ),
            )
            for aperture in [5, 3]:
                d = h[f"EXTRACT{aperture}PIX1D"].data
                for flux, err in [("FLUX", "FLUX_ERR"), ("FLUX_NOD2", "FLUX_ERR_NOD2")]:
                    labels = [("Hb", hb_center, (0.008, 0.015))]
                    if config == "f170lp-g235m":
                        labels.append(("Ha", ha_center, (0.012, 0.020)))
                    for label, center, continuum in labels:
                        for width in [0.0025, 0.0035, 0.0045]:
                            key = f"{config}_{aperture}pix_{flux}_{label}_{width:.4f}"
                            results[key] = integrate(d, center, width, continuum, flux, err)
    report = dict(
        source_id=args.source_id,
        method=(
            "Unweighted flux-density box summation with inverse-variance constant continuum "
            "from red sideband; explicit bin edges; reported diagonal errors plus "
            "continuum-estimation variance; no gap interpolation."
        ),
        caveats=(
            "Post-triage diagnostic, not a calibrated likelihood. Wide Ha boxes can include "
            "NII wings. Apertures and nod choices share photons. Configurations share "
            "calibration/model assumptions. No cause inferred from coverage edge."
        ),
        spectra=metadata,
        results=results,
    )
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / f"independent-spectrum{args.source_id}-receipt.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps(metadata, indent=2))
    for key, row in results.items():
        if "_5pix_" in key and key.endswith("_0.0035"):
            print(key, json.dumps(row))


if __name__ == "__main__":
    main()
