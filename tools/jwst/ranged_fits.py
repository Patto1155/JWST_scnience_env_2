"""Bounded read-only HTTP FITS ranges with fragment-level provenance.

This verifies returned byte ranges, never pretends to verify whole-file hashes.
Cached blocks are temporary raw downloads and must be deleted after reduction.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

import requests


class RangeBudget:
    def __init__(
        self,
        cap: int = 300_000_000,
        journal: Path | None = None,
        cancel_event: threading.Event | None = None,
    ):
        self.cap = cap
        self.bytes = 0
        self.reserved = 0
        self.receipts: list[dict] = []
        self.first_access: str | None = None
        self.journal = journal
        self.lock = threading.Lock()
        self.cancel_event = cancel_event or threading.Event()
        self.stop_reason: str | None = None

    def _journal(self, event: str, receipt: dict):
        if self.journal is not None:
            self.journal.parent.mkdir(parents=True, exist_ok=True)
            with self.journal.open("a") as stream:
                stream.write(json.dumps({"event": event, **receipt}) + "\n")
                stream.flush()

    def reserve(self, expected: int, receipt: dict):
        with self.lock:
            if self.cancel_event.is_set():
                raise InterruptedError("acquisition cancelled: retain receipts, no scientific null")
            if self.bytes + self.reserved + expected > self.cap:
                self.stop_reason = "frozen pilot cap would be exceeded"
                self._journal(
                    "acquisition_stopped",
                    {
                        "reason": self.stop_reason,
                        "charged_bytes": self.bytes,
                        "reserved_bytes": self.reserved,
                    },
                )
                raise ValueError("range acquisition would exceed frozen pilot cap")
            self.reserved += expected
            self.first_access = self.first_access or receipt["utc"]
            self.receipts.append(receipt)
            self._journal("request_started", receipt)

    def finish(self, expected: int, receipt: dict, raw: bytes, error: BaseException | None):
        with self.lock:
            self.reserved -= expected
            charged = expected if error is not None else len(raw)
            self.bytes += charged
            receipt.update(
                body_bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(),
                charged_body_bytes=charged,
                complete_body_accounting=error is None,
            )
            if error is not None:
                receipt["error"] = f"{type(error).__name__}: {error}"
            self._journal("request_finished", receipt)


class RangedFITS(io.RawIOBase):
    def __init__(self, url: str, size: int, budget: RangeBudget, block: int = 65536):
        super().__init__()
        self.url, self.size, self.budget, self.block = url, size, budget, block
        self.position = 0
        self.cache: dict[int, bytes] = {}
        self.session = requests.Session()

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=io.SEEK_SET):
        position = offset if whence == io.SEEK_SET else self.position + offset
        if whence == io.SEEK_END:
            position = self.size + offset
        if position < 0 or whence not in (io.SEEK_SET, io.SEEK_CUR, io.SEEK_END):
            raise ValueError("invalid seek")
        self.position = position
        return position

    def _fetch(self, start: int, expected: int) -> bytes:
        end = start + expected - 1
        stamp = datetime.now(timezone.utc).isoformat()
        url = self.url + ("&" if "?" in self.url else "?") + f"range_offset={start}"
        attempt = {
            "url": url,
            "requested_range": [start, end],
            "utc": stamp,
            "body_bytes": 0,
            "sha256": hashlib.sha256(b"").hexdigest(),
            "fullfile_hash_verified": False,
            "status": "request_started",
        }
        reserved = expected + 1
        self.budget.reserve(reserved, attempt)
        raw = bytearray()
        error = None
        try:
            with self.session.get(
                url, headers={"Range": f"bytes={start}-{end}"}, timeout=45, stream=True
            ) as response:
                attempt.update(
                    status=response.status_code, content_range=response.headers.get("Content-Range")
                )
                while len(raw) < reserved:
                    chunk = response.raw.read(min(16384, reserved - len(raw)))
                    if not chunk:
                        break
                    raw.extend(chunk)
                match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", attempt["content_range"] or "")
                if (
                    response.status_code != 206
                    or not match
                    or tuple(map(int, match.groups())) != (start, end, self.size)
                ):
                    raise ValueError("archive did not return exact requested range/total identity")
                if len(raw) != expected:
                    raise ValueError("archive range body length differs")
        except BaseException as caught:
            error = caught
            raise
        finally:
            self.budget.finish(reserved, attempt, bytes(raw), error)
        return bytes(raw)

    def _block(self, start):
        if start not in self.cache:
            self.cache[start] = self._fetch(start, min(self.block, self.size - start))
        return self.cache[start]

    def read(self, size=-1):
        size = self.size - self.position if size is None or size < 0 else size
        end = min(self.position + size, self.size)
        blocks = []
        while self.position < end:
            start = self.position // self.block * self.block
            raw = self._block(start)
            offset = self.position - start
            count = min(len(raw) - offset, end - self.position)
            blocks.append(raw[offset : offset + count])
            self.position += count
        return b"".join(blocks)

    def close(self):
        self.cache.clear()
        self.session.close()
        super().close()


class HeaderRangedFITS(RangedFITS):
    """Exact FITS header blocks; contiguous larger target HDUs in one request.

    RATE row sections retain amortized block caching. This changes I/O only.
    All fetched chunks carry the same range identity and budget checks.
    """

    def read(self, size=-1):
        if isinstance(size, int) and (size == 2880 and self.position % 2880 == 0 or size > 2880):
            end = min(self.position + size, self.size)
            count = end - self.position
            if count <= 0:
                return b""
            start = self.position // self.block * self.block
            if start in self.cache and end <= start + len(self.cache[start]):
                raw = self.cache[start][self.position - start : end - start]
            else:
                raw = self._fetch(self.position, count)
            self.position = end
            return raw
        return super().read(size)


def locate_hdu_header(reader: RangedFITS, hint: int, name: str, version: int | None = None):
    """Search a bounded +/-64KiB neighborhood of a prior header offset.

    This is an I/O hint, never an identity shortcut. Callers still verify source,
    units, context and dimensions. Failure requires an explicit scan/stop.
    """
    from astropy.io import fits

    start = max(0, (hint - 65536) // 2880 * 2880)
    end = min(reader.size, ((hint + 65536) // 2880 + 1) * 2880)
    reader.seek(start)
    raw = reader._fetch(start, end - start)
    for position in range(0, len(raw) - 2880 + 1, 2880):
        if not raw[position:].startswith(b"XTENSION"):
            continue
        final = None
        for card in range(position, len(raw) - 79, 80):
            if raw[card : card + 8] == b"END     ":
                final = (card - position + 80 + 2879) // 2880 * 2880
                break
        if final is None:
            continue
        try:
            header = fits.Header.fromstring(raw[position : position + final].decode("ascii"))
        except (ValueError, UnicodeDecodeError):
            continue
        if header.get("EXTNAME") == name and (version is None or header.get("EXTVER") == version):
            return header, start + position, start + position + final
    raise ValueError("prior HDU hint does not locate declared extension")
