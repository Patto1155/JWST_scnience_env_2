"""Preserve exact original Cloudy model files without depending on scratch caches."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def preserve(models_path: Path, directories: list[Path], output: Path) -> dict:
    models = json.loads(models_path.read_text())["models"]
    if not models:
        raise ValueError("at least one complete model required")
    requested = {}
    for model in models:
        if len(model["files"]) != 7 or "Cloudy ends:" not in model["convergence_summary"]:
            raise ValueError("complete converged model receipt required")
        for item in model["files"]:
            name = item["name"]
            if name in requested or Path(name).name != name:
                raise ValueError("unique relative raw filenames required")
            requested[name] = item
    payloads = {}
    for name, expected in requested.items():
        matches = [
            path.read_bytes()
            for directory in directories
            if (path := directory / name).is_file() and path.stat().st_size == expected["bytes"]
        ]
        matches = [payload for payload in matches if sha256(payload) == expected["sha256"]]
        if not matches:
            raise ValueError(f"original raw file missing or modified: {name}")
        payloads[name] = matches[0]
    line_lists = [
        path.read_bytes()
        for directory in directories
        if (path := directory / "pilot-lines.dat").is_file()
    ]
    if not line_lists or any(payload != line_lists[0] for payload in line_lists):
        raise ValueError("one consistent original saved-line list required")
    payloads["pilot-lines.dat"] = line_lists[0]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
                for name, payload in sorted(payloads.items()):
                    member = tarfile.TarInfo(name)
                    member.size = len(payload)
                    member.mode = 0o644
                    archive.addfile(member, io.BytesIO(payload))
    # Verify the finished preservation artifact, including original receipt identities.
    with tarfile.open(output) as archive:
        actual = {member.name: archive.extractfile(member).read() for member in archive}
    if actual != payloads:
        raise ValueError("raw preservation round trip changed original bytes")
    return {
        "schema_version": 1,
        "source_models_receipt_sha256": sha256(models_path.read_bytes()),
        "model_ids": [model["id"] for model in models],
        "archive": {
            "name": output.name,
            "bytes": output.stat().st_size,
            "sha256": sha256(output.read_bytes()),
        },
        "members": [
            {"name": name, "bytes": len(payload), "sha256": sha256(payload)}
            for name, payload in sorted(payloads.items())
        ],
        "deterministic_container_metadata": True,
        "all_original_model_receipt_hashes_verified": True,
        "scope": (
            "Exact original-output audit and restoration. New Cloudy executions have "
            "different runtime text in .out; compare their scientific numeric outputs "
            "with the separate tolerance contract, not whole-file rerun hashes."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--run-directory", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    receipt = preserve(args.models, args.run_directory, args.output)
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
