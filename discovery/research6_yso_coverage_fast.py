"""Same frozen AA Tau source-WCS gate, with two-range FITS metadata access."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from discovery.research5_spherex_review import response_coverage
from discovery.research6_yso_coverage import RangeMetadata, campaigns
from discovery.research6_yso_pilot import ROOT


def headers_from_ranges(first: bytes, tail: bytes, tail_start: int):
    initial = io.BytesIO(first)
    fits.Header.fromfile(initial)  # PRIMARY has no array in SPHEREx L2.
    header = fits.Header.fromfile(initial)
    candidates = []
    offset = tail.find(b"XTENSION")
    while offset >= 0:
        if (tail_start + offset) % 2880 == 0:
            try:
                table = fits.BinTableHDU.fromstring(tail[offset:])
                if table.header.get("EXTNAME") == "WCS-WAVE":
                    candidates.append(table)
            except (ValueError, OSError):
                pass
        offset = tail.find(b"XTENSION", offset + 1)
    if len(candidates) != 1:
        raise ValueError("Final ranges do not uniquely identify WCS-WAVE table")
    return header, candidates[0]


def fast_channel(exposure: dict, target: dict, budget: dict) -> dict:
    url = exposure["access_url"].replace(
        "https://irsa.ipac.caltech.edu/ibe/data/spherex/",
        "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/",
    )
    stream = RangeMetadata(url, budget)
    try:
        tail_start = max(0, stream.length - 65536)
        stream.fetch(tail_start, stream.length - 1)
        header, table = headers_from_ranges(stream.parts[0][2], stream.parts[-1][2], tail_start)
        hdul = fits.HDUList([fits.PrimaryHDU(), table])
        spatial = WCS(header).celestial
        x, y = spatial.all_world2pix(target["ra"], target["dec"], 0)
        nx, ny = header["NAXIS1"], header["NAXIS2"]
        if not np.isfinite([x, y]).all() or not 0 <= x < nx or not 0 <= y < ny:
            raise ValueError("Source outside IMAGE WCS")
        spectral = WCS(header, fobj=hdul, key="W")
        wavelength, width = map(float, spectral.wcs_pix2world([[x, y]], 0)[0])
        if not np.isfinite([wavelength, width]).all() or width <= 0:
            raise ValueError("Invalid source wavelength/bandwidth")
        return {
            **exposure,
            "status": "source spectral WCS measured",
            "parent_xy": [float(x), float(y)],
            "wavelength_um": wavelength,
            "width_um": width,
            "edge_pixels": float(min(x, y, nx - 1 - x, ny - 1 - y)),
            "source_range_receipts": stream.receipts,
            "no_pixels_measured": True,
        }
    finally:
        stream.parts.clear()
        stream.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "research_output/session_20261014")
    args = parser.parse_args()
    started = time.monotonic()
    out = args.out
    inventory = json.loads((out / "f_current/f_metadata_summary.json").read_text())
    previous = json.loads((out / "f_aa_tau_coverage.json").read_text())
    if (
        hashlib.sha256((ROOT / "docs/frozen/F_YSO_DESIGN.md").read_bytes()).hexdigest()
        != inventory["freeze_sha256"]
    ):
        raise RuntimeError("Frozen design changed")
    target = inventory["targets"][0]
    assert target["name"] == "AA Tau"
    prior = (
        json.loads((out / "f_session_receipts.json").read_text())[
            "instrumented_response_body_bytes"
        ]
        + previous["range_response_body_bytes"]
    )
    journal = out / "f_aa_tau_fast_range_journal.jsonl"
    if journal.exists():
        prior += sum(json.loads(line)["bytes"] for line in journal.read_text().splitlines())
    budget = {
        "remaining": 300_000_000 - prior - 1_000_000,
        "deadline": started + 550,
        "receipts": [],
        "journal": journal,
        "lock": threading.Lock(),
    }
    valid = [x for v in previous["visits"] for x in v["channels"] if "wavelength_um" in x]
    results = {}

    def acquire(exposure):
        try:
            return fast_channel(exposure, target, budget)
        except Exception as error:
            return {**exposure, "status": f"blocked: {error}"}

    with ThreadPoolExecutor(max_workers=8) as pool:
        # Existing 13 photons are validation inputs; no new exposures before this gate.
        verified = list(pool.map(acquire, valid))
        comparisons = []
        for old, new in zip(valid, verified, strict=True):
            agrees = "wavelength_um" in new and np.allclose(
                [*old["parent_xy"], old["wavelength_um"], old["width_um"]],
                [*new["parent_xy"], new["wavelength_um"], new["width_um"]],
                rtol=0,
                atol=1e-10,
            )
            comparisons.append({"obs_id": old["obs_id"], "agrees_at_1e_10": bool(agrees)})
            results[(old["obs_id"], old["detector"])] = new
        validation = {
            "count": len(comparisons),
            "comparisons": comparisons,
            "passes": len(comparisons) == 13 and all(x["agrees_at_1e_10"] for x in comparisons),
        }
        (out / "f_aa_tau_fast_validation.json").write_text(json.dumps(validation, indent=2) + "\n")
        if validation["passes"]:
            new = [
                x
                for x in target["spherex_metadata"]["exposures"]
                if (x["obs_id"], x["detector"]) not in results
            ]
            for item in pool.map(acquire, new):
                results[(item["obs_id"], item["detector"])] = item
    response = np.loadtxt(
        io.BytesIO(
            gzip.decompress(
                (ROOT / "research_output/research5_spherex_review_w1_response.txt.gz").read_bytes()
            )
        )
    )
    visits = []
    for index, group in enumerate(campaigns(target["spherex_metadata"]["exposures"])):
        measured = [
            results.get(
                (x["obs_id"], x["detector"]), {**x, "status": "not accessed: parsing gate failed"}
            )
            for x in group
        ]
        usable = [x for x in measured if "wavelength_um" in x and x["edge_pixels"] >= 4]
        coverage = response_coverage(
            np.array([x["wavelength_um"] for x in usable]),
            np.array([x["width_um"] for x in usable]),
            response,
        )
        visits.append(
            {
                "campaign": index,
                "selected": len(group),
                "measured": len(usable),
                "channels": measured,
                "coverage": coverage,
                "nominal_coverage_gate": coverage["nonoverlapping_nominal_channel_count"] >= 8
                and coverage["nominal_support_flat_fnu_photon_fraction"] >= 0.80,
            }
        )
    result = {
        "freeze_commit": inventory["freeze_commit"],
        "target": "AA Tau",
        "family_trials": 6,
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "validation": validation,
        "visits": visits,
        "prior_instrumented_bytes": prior,
        "range_response_body_bytes": sum(x["bytes"] for x in budget["receipts"]),
        "elapsed_seconds": time.monotonic() - started,
        "not_run": [
            "flux photometry",
            "NEOWISE",
            "ZTF",
            "field-star null",
            "injection recovery",
            "other five YSOs",
            "GOODS-N",
        ],
    }
    (out / "f_aa_tau_coverage_fast.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "elapsed_seconds": result["elapsed_seconds"],
                "validation": validation["passes"],
                "campaigns": [
                    {k: v[k] for k in ("campaign", "selected", "measured", "nominal_coverage_gate")}
                    for v in visits
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
