"""One explicit budget-reserved Range recovery after E2 filesystem failure."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from discovery.smacs_e2_run import E2_FREEZE, RECEIPTS, require_freeze, reserve, save


def main() -> None:
    require_freeze(E2_FREEZE)
    cache = Path("/tmp/jwst_smacs_e2_cache")
    out = RECEIPTS / "e2_acquisition.json"
    original = out.read_bytes()
    backup = RECEIPTS / "e2_acquisition_failed.json"
    if backup.exists():
        raise FileExistsError("recovery already attempted; reconcile instead of retrying")
    backup.write_bytes(original)
    ledger = json.loads(original)
    if ledger["status"] != "blocked: acquisition failure":
        raise ValueError("not the recorded failed acquisition")
    refheads = json.loads((RECEIPTS / "e_reference_heads.json").read_text())["products"]
    completed = {x["name"] for x in ledger["products"] if x["status"] == "complete"}
    ledger["explicit_recovery"] = "Range continuation after synchronized workspace filled disk"
    ledger["resolved_cache"] = str(cache)
    ledger["status"] = "explicit bounded recovery"
    save(out, ledger)
    for p in refheads:
        if p["filename"] in completed:
            continue
        name, expected = p["filename"], int(p["content_length"])
        partial = cache / (name + ".partial")
        prefix = partial.stat().st_size if partial.exists() else 0
        length = expected - prefix
        reserve(ledger, length)
        row = {
            "name": name,
            "url": p["requested_url"],
            "kind": "reference",
            "bytes": expected,
            "prefix_bytes": prefix,
            "reserved_bytes": length,
            "body_bytes": 0,
            "status": "reserved explicit continuation",
        }
        ledger["products"].append(row)
        save(out, ledger)
        digest = hashlib.sha256()
        if prefix:
            with partial.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
            row["prefix_sha256"] = digest.hexdigest()
        request_headers = {"Range": f"bytes={prefix}-"} if prefix else {}
        try:
            with urlopen(
                Request(p["requested_url"], headers=request_headers), timeout=60
            ) as response:
                row["http_status"] = response.status
                row["resolved_url"] = response.url
                row["etag"] = response.headers.get("ETag")
                row["last_modified"] = response.headers.get("Last-Modified")
                row["content_range"] = response.headers.get("Content-Range")
                if response.status != (206 if prefix else 200):
                    raise ValueError("server does not honor bounded Range request")
                if int(response.headers["Content-Length"]) != length:
                    raise ValueError("remaining body length differs from reservation")
                if prefix and row["content_range"] != f"bytes {prefix}-{expected - 1}/{expected}":
                    raise ValueError("Range identity/total changed")
                with partial.open("ab" if prefix else "xb") as stream:
                    while chunk := response.read(1024 * 1024):
                        row["body_bytes"] += len(chunk)
                        ledger["actual_new_body_bytes"] += len(chunk)
                        if row["body_bytes"] > length:
                            raise ValueError("response exceeds explicit recovery reservation")
                        stream.write(chunk)
                        digest.update(chunk)
                        save(out, ledger)
                if row["body_bytes"] != length:
                    raise ValueError("truncated continuation")
                row["sha256"] = digest.hexdigest()
                row["status"] = "complete"
                row["completed_utc"] = datetime.now(timezone.utc).isoformat()
                partial.replace(cache / name)
        except BaseException as exc:
            row["status"] = "failed explicit recovery"
            row["error"] = f"{type(exc).__name__}: {exc}"
            ledger["status"] = "blocked after explicit recovery"
            save(out, ledger)
            raise
        save(out, ledger)
    ledger["status"] = "complete"
    save(out, ledger)
    print(ledger["reserved_total_bytes"], ledger["actual_new_body_bytes"])


if __name__ == "__main__":
    main()
