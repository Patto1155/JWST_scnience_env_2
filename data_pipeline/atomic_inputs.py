"""Bounded, hash-pinned optional atomic-model acquisition; no pip/environment mutation."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

PYNEB_VERSION = "1.1.32"
PYNEB_FILENAME = "pyneb-1.1.32-py3-none-any.whl"
PYNEB_URL = (
    "https://files.pythonhosted.org/packages/14/c4/"
    "0557811390e7103d151836be6ffc05af095f801760ad0347541b28a96402/" + PYNEB_FILENAME
)
PYNEB_SHA256 = "96a63479536b4e53fdb36e1da20d72b9291cf920e042d765dd4a0c4ca3160cbe"
PYNEB_BYTES = 28751057
TOTAL_CAP = 100 * 1024**2
CUE_FILENAME = "cue-v0.1.zip"
CUE_URL = "https://zenodo.org/records/11118643/files/yi-jia-li/cue-v0.1.zip?download=1"
CUE_SHA256 = "8c1089f4d7407c57558e14b0f26028379ca14d555a94f873834c767f3cc5abfb"
CUE_BYTES = 31885220


def acquire_file(root: Path, name: str, url: str, sha256: str, size: int) -> dict[str, Any]:
    """Cached files and streamed new bytes both obey independently pinned identity."""
    if size > TOTAL_CAP or Path(name).name != name:
        raise ValueError("invalid atomic-input request")
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    cached = path.exists()
    if not cached:
        temporary = path.with_suffix(path.suffix + ".partial")
        try:
            with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as out:
                count = 0
                while block := response.read(1024**2):
                    count += len(block)
                    if count > size:
                        raise ValueError("atomic input exceeds pinned byte count")
                    out.write(block)
            verify_bytes(temporary, sha256, size)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    verify_bytes(path, sha256, size)
    return {"filename": name, "url": url, "sha256": sha256, "bytes": size, "cached": cached}


def verify_bytes(path: Path, sha256: str, size: int) -> None:
    if path.stat().st_size != size or hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
        raise ValueError("atomic input differs from independently pinned package")


def acquire_pyneb(root: Path) -> dict[str, Any]:
    receipt = acquire_file(root, PYNEB_FILENAME, PYNEB_URL, PYNEB_SHA256, PYNEB_BYTES)
    runtime = root / "pyneb-runtime"
    # Only this independently pinned pure-Python wheel is extracted. No package
    # manager changes a shared environment. Reject traversal and unexpected size.
    with zipfile.ZipFile(root / PYNEB_FILENAME) as archive:
        if sum(x.file_size for x in archive.infolist()) > 200 * 1024**2:
            raise ValueError("expanded package exceeds bound")
        for member in archive.infolist():
            destination = (runtime / member.filename).resolve()
            if not destination.is_relative_to(runtime.resolve()):
                raise ValueError("unsafe package member")
        archive.extractall(runtime)
    result = {
        "schema_version": 1,
        "download_cap_bytes": TOTAL_CAP,
        "inputs": [receipt],
        "runtime_directory": str(runtime.resolve()),
        "source": "https://pypi.org/project/PyNeb/1.1.32/",
        "scope": "Ionic emissivities; no photoionization equilibrium or ion fractions",
    }
    (root / "atomic_input_receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def acquire_cue(root: Path) -> dict[str, Any]:
    if PYNEB_BYTES + CUE_BYTES > TOTAL_CAP:
        raise ValueError("aggregate atomic model acquisition exceeds cap")
    result = acquire_file(root, CUE_FILENAME, CUE_URL, CUE_SHA256, CUE_BYTES)
    result["publisher_md5"] = "370380e7e685acfb03861bfb82650301"
    result["source"] = "https://doi.org/10.5281/zenodo.11118643"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--cue", action="store_true")
    args = parser.parse_args()
    result = acquire_pyneb(args.output_dir)
    if args.cue:
        result["inputs"].append(acquire_cue(args.output_dir))
        (args.output_dir / "atomic_input_receipt.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
