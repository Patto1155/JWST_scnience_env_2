"""AA Tau frozen first-target coverage gate, using wavelength-only official FITS ranges."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
from astropy.io import fits
from astropy.wcs import WCS

from discovery.research5_spherex_review import response_coverage
from discovery.research6_yso_pilot import ROOT


class RangeMetadata(io.RawIOBase):
    """Seekable bounded exact Range bodies; never retain a full raw product."""

    def __init__(self, url: str, budget: dict):
        self.url, self.budget = url, budget
        self.pos, self.length = 0, None
        self.parts: list[tuple[int, int, bytes]] = []
        self.receipts: list[dict] = []
        self.etag = None
        self.name = url
        self.fetch(0, 65535)

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = (
            offset if whence == 0 else self.pos + offset if whence == 1 else self.length + offset
        )
        return self.pos

    def fetch(self, start, end):
        if time.monotonic() > self.budget["deadline"]:
            raise RuntimeError("Frozen 600-second numerical-run limit reached")
        end = min(end, self.length - 1) if self.length else end
        if end - start + 1 > self.budget["remaining"]:
            raise RuntimeError("Aggregate pilot response-body cap would be exceeded")
        receipt = {
            "url": self.url,
            "requested_range": f"bytes={start}-{end}",
            "utc": datetime.now(timezone.utc).isoformat(),
            "bytes": 0,
        }
        chunks = []
        try:
            with requests.get(
                self.url,
                headers={"Range": receipt["requested_range"]},
                timeout=min(15, max(0.01, self.budget["deadline"] - time.monotonic())),
                stream=True,
            ) as response:
                receipt["status"] = response.status_code
                for chunk in response.iter_content(65536):
                    chunks.append(chunk)
                    receipt["bytes"] += len(chunk)
                    self.budget["remaining"] -= len(chunk)
                    if self.budget["remaining"] < 0 or receipt["bytes"] > end - start + 1:
                        raise RuntimeError("Range response exceeded declared bound")
                body = b"".join(chunks)
                if response.status_code != 206:
                    raise RuntimeError(f"Range status {response.status_code}")
                content_range = response.headers["Content-Range"]
                lohi, total = content_range.split()[1].split("/")
                lo, hi = map(int, lohi.split("-"))
                total = int(total)
                if lo != start or hi > end or len(body) != hi - lo + 1:
                    raise RuntimeError("Range identity/length mismatch")
                if self.length is not None and self.length != total:
                    raise RuntimeError("Product length changed")
                etag = response.headers.get("ETag")
                if self.etag is not None and self.etag != etag:
                    raise RuntimeError("Product ETag changed")
                self.etag, self.length = etag, total
                receipt.update(content_range=content_range, etag=etag)
                self.parts.append((lo, hi + 1, body))
        except Exception as error:
            receipt["error"] = str(error)
            raise
        finally:
            receipt["sha256"] = hashlib.sha256(b"".join(chunks)).hexdigest()
            self.receipts.append(receipt)
            self.budget["receipts"].append(receipt)
            if "journal" in self.budget:
                with self.budget["lock"]:
                    with self.budget["journal"].open("a") as journal:
                        journal.write(json.dumps(receipt) + "\n")

    def read(self, n=-1):
        if n < 0:
            n = self.length - self.pos
        n = min(n, self.length - self.pos)
        if n <= 0:
            return b""
        for lo, hi, body in self.parts:
            if lo <= self.pos and self.pos + n <= hi:
                result = body[self.pos - lo : self.pos - lo + n]
                self.pos += len(result)
                return result
        start = self.pos
        self.fetch(start, min(self.length - 1, start + max(n, 65536) - 1))
        result = self.parts[-1][2][:n]
        self.pos += len(result)
        return result


def campaigns(exposures: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
    for exposure in sorted(exposures, key=lambda e: e["mjd_start"]):
        if not groups or exposure["mjd_start"] - groups[-1][-1]["mjd_start"] > 30:
            groups.append([])
        groups[-1].append(exposure)
    return groups


def source_channel(exposure: dict, ra: float, dec: float, budget: dict) -> dict:
    url = exposure["access_url"].replace(
        "https://irsa.ipac.caltech.edu/ibe/data/spherex/",
        "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/",
    )
    stream = RangeMetadata(url, budget)
    try:
        with fits.open(stream, memmap=False, lazy_load_hdus=True) as hdul:
            header = hdul["IMAGE"].header
            spatial = WCS(header, fobj=hdul).celestial
            x, y = spatial.all_world2pix(ra, dec, 0)
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
        # Raw ranges are temporary in-memory bytes, erased after compact reduction.
        stream.parts.clear()
        stream.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "research_output/session_20261014")
    args = parser.parse_args()
    started = time.monotonic()
    inventory = json.loads(args.metadata.read_text())
    design = ROOT / "docs/frozen/F_YSO_DESIGN.md"
    if hashlib.sha256(design.read_bytes()).hexdigest() != inventory["freeze_sha256"]:
        raise RuntimeError("Frozen design changed after archive access")
    target = inventory["targets"][0]
    assert target["name"] == "AA Tau"
    groups = campaigns(target["spherex_metadata"]["exposures"])
    chosen = [("earliest", groups[0]), ("latest", groups[-1])]
    response_path = ROOT / "research_output/research5_spherex_review_w1_response.txt.gz"
    response_body = gzip.decompress(response_path.read_bytes())
    response_receipt = json.loads(
        response_path.with_suffix("").with_suffix(".txt.receipt.json").read_text()
    )
    if hashlib.sha256(response_body).hexdigest() != response_receipt["sha256"]:
        raise RuntimeError("Official W1 response identity mismatch")
    response = np.loadtxt(io.BytesIO(response_body))
    # All earlier instrumented metadata runs, plus a conservative 1MB allocation
    # for the disclosed unreceipted documentation probe; no raw science restores.
    prior = json.loads((args.out / "f_session_receipts.json").read_text())[
        "instrumented_response_body_bytes"
    ]
    budget = {
        "remaining": 300_000_000 - prior - 1_000_000,
        "deadline": started + 600,
        "receipts": [],
    }
    result = {
        "freeze_commit": inventory["freeze_commit"],
        "first_science_access_utc": None,
        "metadata_sha256": hashlib.sha256(args.metadata.read_bytes()).hexdigest(),
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "target": "AA Tau",
        "family_trials": 6,
        "visits": [],
        "prior_instrumented_body_bytes": prior,
        "unverified_probe_reserve_bytes": 1_000_000,
        "official_response_sha256": response_receipt["sha256"],
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
    for label, exposures in chosen:
        visit = {"label": label, "selected_exposure_count": len(exposures), "channels": []}
        for exposure in exposures:
            try:
                channel = source_channel(exposure, target["ra"], target["dec"], budget)
                visit["channels"].append(channel)
            except Exception as error:
                visit["channels"].append({**exposure, "status": f"blocked: {error}"})
            if budget["receipts"] and result["first_science_access_utc"] is None:
                result["first_science_access_utc"] = budget["receipts"][0]["utc"]
            if time.monotonic() > budget["deadline"] or budget["remaining"] <= 0:
                break
        usable = [c for c in visit["channels"] if "wavelength_um" in c and c["edge_pixels"] >= 4]
        coverage = response_coverage(
            np.array([c["wavelength_um"] for c in usable]),
            np.array([c["width_um"] for c in usable]),
            response,
        )
        visit["coverage"] = coverage
        visit["coverage_gate_passes"] = (
            coverage["nonoverlapping_nominal_channel_count"] >= 8
            and coverage["nominal_support_flat_fnu_photon_fraction"] >= 0.80
        )
        visit["all_selected_headers_measured"] = len(usable) == len(exposures)
        result["visits"].append(visit)
        if time.monotonic() > budget["deadline"] or budget["remaining"] <= 0:
            break
    result.update(
        elapsed_seconds=time.monotonic() - started,
        range_response_body_bytes=sum(r["bytes"] for r in budget["receipts"]),
        range_receipts=budget["receipts"],
    )
    result["coverage_verdict"] = (
        "both measured visits satisfy nominal coverage gate; photometry still pending"
        if len(result["visits"]) == 2 and all(v["coverage_gate_passes"] for v in result["visits"])
        else "frozen W1 coverage gate not satisfied by measured visits; no W1 variability statistic"
    )
    (args.out / "f_aa_tau_coverage.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("coverage_verdict", "elapsed_seconds", "range_response_body_bytes")
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
