"""Original output preservation detects corruption and fixes container metadata."""

import hashlib
import json
import tarfile

import pytest

from tools.jwst.cloudy_raw_archive import preserve


def test_raw_preservation_and_changed_runtime_rejection(tmp_path):
    files = []
    originals = {}
    for suffix in ("in", "out", "lin", "emergent.lin", "ovr", "abn", "avr"):
        name = "model000." + suffix
        payload = ("original " + suffix + "\n").encode()
        (tmp_path / name).write_bytes(payload)
        originals[name] = payload
        files.append(
            {"name": name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
        )
    (tmp_path / "pilot-lines.dat").write_text("original saved line identities\n")
    model_path = tmp_path / "models.json"
    model_path.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "id": "model000",
                        "files": files,
                        "convergence_summary": "Cloudy ends: 3 iterations",
                    }
                ]
            }
        )
    )
    first = tmp_path / "first.tar.gz"
    receipt = preserve(model_path, [tmp_path], first)
    second = tmp_path / "second.tar.gz"
    preserve(model_path, [tmp_path], second)
    assert first.read_bytes() == second.read_bytes()
    assert receipt["all_original_model_receipt_hashes_verified"]
    with tarfile.open(first) as archive:
        for name, payload in originals.items():
            assert archive.extractfile(name).read() == payload
            assert archive.getmember(name).mtime == 0
    # Runtime text can differ on reexecution, but original preservation must fail closed.
    (tmp_path / "model000.out").write_text("new run runtime\n")
    with pytest.raises(ValueError, match="missing or modified"):
        preserve(model_path, [tmp_path], tmp_path / "rejected.tar.gz")
    assert not (tmp_path / "rejected.tar.gz").exists()
