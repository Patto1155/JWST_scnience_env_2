"""Reproduce root-adjudicated W1 source-scope arithmetic without acquisition."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

import numpy as np

from discovery.research5_spherex_review import response_coverage
from discovery.research6_yso_pilot import ROOT


def source_scope(visits: list[dict], response: np.ndarray) -> list[dict]:
    rows = []
    for visit in visits:
        channels = [
            c
            for c in visit["channels"]
            if "wavelength_um" in c and 2.8 <= c["wavelength_um"] <= 3.9 and c["edge_pixels"] >= 4
        ]
        coverage = response_coverage(
            np.array([c["wavelength_um"] for c in channels]),
            np.array([c["width_um"] for c in channels]),
            response,
        )
        complete = visit["measured"] == visit["selected"]
        rows.append(
            {
                "campaign": visit["campaign"],
                "selected": visit["selected"],
                "measured": visit["measured"],
                "source_scope_um": [2.8, 3.9],
                "within_scope_channel_count": len(channels),
                "within_scope_nonoverlapping_channels": coverage[
                    "nonoverlapping_nominal_channel_count"
                ],
                "whole_spectrum_photon_coverage": visit["coverage"][
                    "nominal_support_flat_fnu_photon_fraction"
                ],
                "within_scope_photon_coverage": coverage[
                    "nominal_support_flat_fnu_photon_fraction"
                ],
                "all_frames_measured": complete,
                "spectral_coverage_gate": complete
                and coverage["nonoverlapping_nominal_channel_count"] >= 8
                and coverage["nominal_support_flat_fnu_photon_fraction"] >= 0.8,
                "quality_flux_calibration": "not measured",
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "research_output/session_20261014")
    args = parser.parse_args()
    source = args.out / "f_aa_tau_coverage_fast.json"
    inputs = json.loads(source.read_text())
    response_path = ROOT / "research_output/research5_spherex_review_w1_response.txt.gz"
    body = gzip.decompress(response_path.read_bytes())
    pinned = json.loads(
        (ROOT / "research_output/research5_spherex_review_w1_response.txt.receipt.json").read_text()
    )
    if hashlib.sha256(body).hexdigest() != pinned["sha256"]:
        raise ValueError("Official W1 response identity failed")
    rows = source_scope(inputs["visits"], np.loadtxt(io.BytesIO(body)))
    count = sum(row["spectral_coverage_gate"] for row in rows)
    result = {
        "freeze_commit": inputs["freeze_commit"],
        "role": "root-adjudicated original W1 scope; frozen design unchanged",
        "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "reduction_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_scope_um": [2.8, 3.9],
        "visits": rows,
        "eligible_spectral_visit_count": count,
        "two_visit_gate": count >= 2,
        "verdict": "not estimable under frozen contract"
        if count < 2
        else "photometric controls still required",
        "postoutcome_one_percent_diagnostic_not_used": True,
    }
    (args.out / "f_aa_tau_source_scope.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "within_scope_counts": [x["within_scope_nonoverlapping_channels"] for x in rows],
                "eligible_spectral_visit_count": count,
                "verdict": result["verdict"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
