"""Acquire faithful compact SPHEREx slices with exact HTTP-range receipts."""

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import requests
from astropy.io import fits
from astropy.wcs import WCS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_output"


class RangeFile(io.RawIOBase):
    def __init__(self, url):
        super().__init__()
        self.name = url
        self.url = url
        self.pos = 0
        self.length = None
        self.parts = []
        self.receipts = []
        self.bodybytes = 0
        self.fetch(0, 65535)

    def fetch(self, start, end):
        if self.length is not None:
            end = min(end, self.length - 1)
        with requests.get(
            self.url, headers={"Range": f"bytes={start}-{end}"}, timeout=40, stream=True
        ) as r:
            if r.status_code != 206:
                raise RuntimeError(f"Range failed {r.status_code}; body not consumed")
            actual = r.headers["Content-Range"]
            lohi, total = actual.split(" ")[1].split("/")
            lo, hi = map(int, lohi.split("-"))
            total = int(total)
            if lo != start or hi > end or (self.length is not None and total != self.length):
                raise RuntimeError("Range identity failed")
            etag = r.headers.get("ETag")
            if hasattr(self, "etag") and self.etag != etag:
                raise RuntimeError("Source ETag changed between ranges")
            self.etag = etag
            chunks = []
            n = 0
            for chunk in r.iter_content(65536):
                n += len(chunk)
                if self.bodybytes + n > 12_000_000 or n > hi - lo + 1:
                    raise RuntimeError("Per-file response budget exceeded")
                chunks.append(chunk)
            body = b"".join(chunks)
            if len(body) != hi - lo + 1:
                raise RuntimeError("Truncated range response")
            self.length = total
            self.parts.append((lo, hi + 1, body))
            self.bodybytes += len(body)
            self.receipts.append(
                {
                    "url": r.url,
                    "range": actual,
                    "bytes": len(body),
                    "etag": etag,
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
            )

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

    def read(self, n=-1):
        if n < 0:
            n = self.length - self.pos
        n = min(n, self.length - self.pos)
        if n <= 0:
            return b""
        for lo, hi, b in self.parts:
            if lo <= self.pos and self.pos + n <= hi:
                x = b[self.pos - lo : self.pos - lo + n]
                self.pos += n
                return x
        start = self.pos
        end = min(self.length - 1, start + max(n, 65536) - 1)
        self.fetch(start, end)
        b = self.parts[-1][2][:n]
        self.pos += len(b)
        return b


def acquire_one(i, r):
    url = r["access_url"].replace(
        "https://irsa.ipac.caltech.edu/ibe/data/spherex/",
        "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/",
    )
    stream = RangeFile(url)
    with fits.open(stream, memmap=False, lazy_load_hdus=True) as h:
        sky = WCS(h["IMAGE"].header, fobj=h).celestial
        x, y = sky.all_world2pix(57.641985, 35.585679, 0)
        ny, nx = h["IMAGE"].shape
        if not np.all(np.isfinite([x, y])) or not 0 <= x < nx or not 0 <= y < ny:
            raise RuntimeError("Requested source outside original image")
        x0 = max(0, int(np.floor(x)) - 12)
        x1 = min(nx, x0 + 25)
        y0 = max(0, int(np.floor(y)) - 12)
        y1 = min(ny, y0 + 25)
        out = [fits.PrimaryHDU(header=h[0].header.copy())]
        for name in ["IMAGE", "VARIANCE", "FLAGS", "ZODI"]:
            hh = h[name].header.copy()
            data = h[name].section[y0:y1, :][:, x0:x1].copy()
            for key in ["CRPIX1", "CRPIX1A", "CRPIX1W"]:
                if key in hh:
                    hh[key] -= x0
            for key in ["CRPIX2", "CRPIX2A", "CRPIX2W"]:
                if key in hh:
                    hh[key] -= y0
            hh["ORIGX0"] = x0
            hh["ORIGY0"] = y0
            out.append(fits.ImageHDU(data=data, header=hh, name=name))
        epsf = h["EPSF"]
        ep = epsf.data
        distances = np.hypot(ep["XCENTER"] - x, ep["YCENTER"] - y)
        epsf_indices = np.argsort(distances)[:5]
        original_epsf_header = epsf.header.tostring()
        original_epsf_sha256 = hashlib.sha256(ep.tobytes()).hexdigest()
        out.append(
            fits.BinTableHDU(data=ep[epsf_indices].copy(), header=epsf.header.copy(), name="EPSF")
        )
        out.append(h["WCS-WAVE"].copy())
        image = fits.HDUList(out)
        b = io.BytesIO()
        image.writeto(b, checksum=True)
        body = b.getvalue()
        file = OUT / f"research5_time_spherex_{i:03d}.fits.gz"
        file.write_bytes(gzip.compress(body, mtime=0))
        receipt = {
            "url": url,
            "source_bytes": stream.bodybytes,
            "source_ranges": stream.receipts,
            "original_epsf_sha256": original_epsf_sha256,
            "original_epsf_header": original_epsf_header,
            "epsf_original_indices": epsf_indices.tolist(),
            "cutout_sha256": hashlib.sha256(body).hexdigest(),
            "cutout_bytes": len(body),
            "original_xy": [float(x), float(y)],
            "slice": [x0, x1, y0, y1],
            "metadata": {k: r[k] for k in ["t_min", "t_max", "obs_id", "energy_bandpassname"]},
            "status": (
                "actual observational pixel slice, faithful header-offset update; "
                "no measured photometry"
            ),
        }
        file.with_suffix(".receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        ranges = Path("/tmp") / f"research5_time_spherex_{i:03d}_ranges.json.gz"
        import base64

        ranges.write_bytes(
            gzip.compress(
                json.dumps(
                    [
                        {"lo": lo, "hi": hi, "bytes_b64": base64.b64encode(b).decode()}
                        for lo, hi, b in stream.parts
                    ]
                ).encode(),
                mtime=0,
            )
        )
        print(
            json.dumps(
                {
                    "index": i,
                    "source_bytes": stream.bodybytes,
                    "cutout_bytes": len(body),
                    "xy": [float(x), float(y)],
                }
            ),
            flush=True,
        )
        return receipt


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--ids", default="")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--stop", type=int, default=1)
    args = p.parse_args()
    rr = list(
        csv.DictReader(
            io.StringIO(
                gzip.decompress(
                    (OUT / "research5_time_spherex_qr3_sia.csv.gz").read_bytes()
                ).decode()
            )
        )
    )
    ids = (
        [int(v) for v in args.ids.split(",") if v]
        if args.ids
        else list(range(args.start, min(args.stop, len(rr))))
    )
    existing = sum(
        json.loads(p.read_text()).get("source_bytes", 0)
        for p in OUT.glob("research5_time_spherex_*.fits.receipt.json")
    )
    if 23_000_000 + existing + len(ids) * 12_000_000 > 300_000_000:
        raise RuntimeError("Conservative campaign reservation exceeds300MB")
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda i: acquire_one(i, rr[i]), ids))
