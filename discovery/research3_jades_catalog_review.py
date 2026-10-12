"""Independent, bounded catalogue audit. GOODS-N outcome columns are never indexed.

Usage: python independent-review.py --data-root /path/to/pilot --output-root /path/to/review
Input and output directories must be explicit. Outputs are operator review
receipts, not discoveries or calibrated p-values.
"""

import argparse
import hashlib
import json
import warnings
from pathlib import Path

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--reference-root", type=Path, help="Frozen pilot artifacts; defaults to data root"
    )
    args = parser.parse_args(argv)
    root, out = args.data_root.resolve(), args.output_root.resolve()
    warnings.filterwarnings("ignore", category=fits.verify.VerifyWarning)
    reference_root = args.reference_root.resolve() if args.reference_root else root
    pilot = json.loads((reference_root / "catalog-pilot.json").read_text())
    inputs = {}
    for filename in [
        "Combined_DR4_external_v1.2.1.fits",
        "pilot.py",
        "catalog-pilot.json",
        "frozen-design.txt",
    ]:
        input_root = root if filename.endswith(".fits") else reference_root
        inputs[filename] = hashlib.sha256((input_root / filename).read_bytes()).hexdigest()
    with fits.open(root / "Combined_DR4_external_v1.2.1.fits") as hdus:
        field = hdus[1].data["Field"]  # Metadata needed to enforce holdout boundary.
        south_indices = np.flatnonzero(field == "GS")
        obs = hdus[1].data[south_indices]
        lines = hdus["R1000_5pix"].data[south_indices]
        aperture = hdus["R1000_3pix"].data[south_indices]
        assert all(field[row["index"]] == "GS" for row in pilot["rows"])
        assert np.array_equal(obs["Unique_ID"], lines["Unique_ID"])
        assert np.array_equal(obs["Unique_ID"], aperture["Unique_ID"])
        ha, hb = lines["HBaA_6563_flux"], lines["HBaB_4861_flux"]
        ea, eb = lines["HBaA_6563_flux_err"], lines["HBaB_4861_flux_err"]
        usable = np.isfinite(ha) & np.isfinite(hb) & np.isfinite(ea) & np.isfinite(eb)
        usable &= (ha > 0) & (hb > 0) & (ea > 0) & (eb > 0)
        with np.errstate(divide="ignore", invalid="ignore"):
            snr_a, snr_b = ha / ea, hb / eb
        pre = np.isin(obs["z_Spec_flag"], ["A", "B"])
        pre &= (obs["z_Spec"] > 2) & (obs["z_Spec"] < 7)
        pre &= usable & (snr_a >= 10) & (snr_b >= 10)
        raw_a, raw_b = lines["HBaA_6563_filter"], lines["HBaB_4861_filter"]
        same = raw_a == raw_b

        def canonical(a):
            return np.array([s.removeprefix("b'").removesuffix("'") for s in a])

        canonical_same = canonical(raw_a) == canonical(raw_b)
        positions = np.flatnonzero(pre & same)
        sky = SkyCoord(obs["RA_TARG"][positions] * u.deg, obs["Dec_TARG"][positions] * u.deg)
        separation = sky[:, None].separation(sky[None, :]).arcsec
        score = np.minimum(snr_a[positions], snr_b[positions])
        keep, consumed = [], set()
        for index in sorted(range(len(positions)), key=lambda k: -score[k]):
            if index in consumed:
                continue
            keep.append(index)
            consumed.update(np.flatnonzero(separation[index] <= 0.2).tolist())
        retained = positions[keep]
        original_indices = south_indices[retained]
        assert set(map(int, original_indices)) == {row["index"] for row in pilot["rows"]}
        ratios = ha[retained] / hb[retained]
        r3 = aperture["HBaA_6563_flux"][retained] / aperture["HBaB_4861_flux"][retained]
        diag = (ha[retained] - 2.65 * hb[retained]) / np.hypot(ea[retained], 2.65 * eb[retained])
        duplicate_pairs = []
        for i, j in zip(*np.where(np.triu(separation <= 0.2, 1))):
            duplicate_pairs.append(
                dict(
                    ids=[str(obs["Unique_ID"][positions[i]]), str(obs["Unique_ID"][positions[j]])],
                    separation_arcsec=float(separation[i, j]),
                    dr5_ids=[
                        int(obs["NIRCam_DR5_ID"][positions[i]]),
                        int(obs["NIRCam_DR5_ID"][positions[j]]),
                    ],
                    redshifts=[
                        float(obs["z_Spec"][positions[i]]),
                        float(obs["z_Spec"][positions[j]]),
                    ],
                )
            )
        shared_dr5 = []
        ids = obs["NIRCam_DR5_ID"][positions]
        for identifier in np.unique(ids[ids > 0]):
            members = np.flatnonzero(ids == identifier)
            if len(members) > 1:
                shared_dr5.append(
                    dict(
                        dr5_id=int(identifier),
                        count=len(members),
                        max_separation_arcsec=float(separation[np.ix_(members, members)].max()),
                    )
                )
        lead = int(retained[np.argmin(ratios)])
        threshold = 2.65
        difference = ha[lead] - threshold * hb[lead]
        sigma_max = ea[lead] + threshold * eb[lead]
        sigma_min = abs(ea[lead] - threshold * eb[lead])
        all_sky = SkyCoord(obs["RA_TARG"] * u.deg, obs["Dec_TARG"] * u.deg)
        near = all_sky[lead].separation(all_sky).arcsec
        stored_snr = {line: lines[line + "_SNR"].reshape(-1) for line in ["HBaA_6563", "HBaB_4861"]}
        report = dict(
            inputs_sha256=inputs,
            scope=(
                "Independent catalogue triage; GOODS-S outcome rows only. "
                "GOODS-N outcome holdout unopened."
            ),
            selected_observation_rows=int(len(positions)),
            representative_rows=int(len(retained)),
            below_2p65=int(sum(ratios < threshold)),
            below_2p65_in_both_apertures=int(
                sum((ratios < threshold) & np.isfinite(r3) & (r3 < threshold))
            ),
            diagonal_residual_below_minus3=int(sum(diag < -3)),
            matches_pilot_indices=True,
            units={
                col: hdus["R1000_5pix"].columns[col].unit
                for col in [
                    "HBaA_6563_flux",
                    "HBaB_4861_flux",
                    "HBaA_6563_flux_err",
                    "HBaB_4861_flux_err",
                ]
            },
            duplicate_pairs=duplicate_pairs,
            shared_positive_dr5=shared_dr5,
            canonical_filter_extra_eligible_rows=int(sum(pre & canonical_same & ~same)),
            all_selected_stored_snr_ge10=bool(
                np.all(stored_snr["HBaA_6563"][positions] >= 10)
                and np.all(stored_snr["HBaB_4861"][positions] >= 10)
            ),
            stored_snr_max_difference={
                line: float(np.max(np.abs(stored_snr[line][positions] - calc[positions])))
                for line, calc in [("HBaA_6563", snr_a), ("HBaB_4861", snr_b)]
            },
            lead=dict(
                unique_id=str(obs["Unique_ID"][lead]),
                z=float(obs["z_Spec"][lead]),
                flag=str(obs["z_Spec_flag"][lead]),
                RA_deg=float(obs["RA_TARG"][lead]),
                Dec_deg=float(obs["Dec_TARG"][lead]),
                ratio_5=float(ha[lead] / hb[lead]),
                ratio_3=float(aperture["HBaA_6563_flux"][lead] / aperture["HBaB_4861_flux"][lead]),
                diag_residual=float(difference / np.hypot(ea[lead], threshold * eb[lead])),
                conditional_unknown_correlation_residual_range=[
                    float(difference / sigma_max),
                    float(difference / sigma_min),
                ],
                ha_multiplier_to_reach_threshold=float(threshold * hb[lead] / ha[lead]),
                hb_fraction_reduction_to_reach_threshold=float(
                    1 - ha[lead] / (threshold * hb[lead])
                ),
                other_gs_targets_within_1_arcsec=int(sum(near < 1) - 1),
                other_gs_targets_shared_positive_dr5=int(
                    sum(obs["NIRCam_DR5_ID"] == obs["NIRCam_DR5_ID"][lead]) - 1
                ),
            ),
        )
    out.mkdir(parents=True, exist_ok=True)
    (out / "independent-review-receipt.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in ["inputs_sha256", "units", "duplicate_pairs", "shared_positive_dr5"]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
