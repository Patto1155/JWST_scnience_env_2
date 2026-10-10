import hashlib
import json
import subprocess

import pytest

from discovery import research2_release_review as review


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root).decode().strip()


@pytest.fixture
def repository(tmp_path, monkeypatch):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Independent test")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    output = tmp_path / "research_output"
    output.mkdir()
    (output / "historical.json").write_text('{"contract":1}\n')
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "Historical contract")
    monkeypatch.setattr(review, "BASELINE", git(tmp_path, "rev-parse", "HEAD"))
    raw = b'{"new_measurement":[1,2,3]}\n'
    (output / "measurement.json").write_bytes(raw)
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "Reviewed measurement")
    monkeypatch.setattr(
        review,
        "CANONICAL",
        {"measurement.json": ("frozen", hashlib.sha256(raw).hexdigest(), len(raw))},
    )
    return tmp_path


def commit_all(root):
    git(root, "add", ".")
    git(root, "commit", "-qm", "Changed tree")


def test_clean_tree_and_historical_contract(repository):
    result = review.audit(repository)
    assert result["strict_valid_tracked_json_count"] == 2
    assert result["baseline_research_artifacts_preserved_count"] == 1
    assert len(result["canonical_science_artifacts"]) == 1


def test_valid_json_corruption_cannot_pass_identity(repository):
    path = repository / "research_output/measurement.json"
    path.write_text('{"new_measurement":[9,2,3]}\n')
    commit_all(repository)
    with pytest.raises(AssertionError, match="Canonical artifact changed"):
        review.audit(repository)


def test_uncommitted_bytes_and_historical_edits_fail(repository):
    path = repository / "research_output/historical.json"
    path.write_text('{"contract":2}\n')
    with pytest.raises(AssertionError, match="Working tree changed"):
        review.audit(repository)
    commit_all(repository)
    with pytest.raises(AssertionError, match="historical.json"):
        review.audit(repository)


@pytest.mark.parametrize("raw", [b'{"x":NaN}', b'{"x":Infinity}', b'{"x":'])
def test_any_tracked_json_must_be_strict(repository, raw):
    (repository / "unrelated.json").write_bytes(raw)
    commit_all(repository)
    with pytest.raises((ValueError, json.JSONDecodeError)):
        review.audit(repository)


def test_new_science_requires_explicit_strict_lint_coverage(repository):
    module = repository / "discovery/new_science.py"
    module.parent.mkdir()
    module.write_text("CONDITIONAL_RESULT = 1\n")
    script = repository / "scripts/quality_gate.py"
    script.parent.mkdir()
    script.write_text("RESEARCH2_SCIENCE_LINT_TARGETS = []\n")
    commit_all(repository)
    with pytest.raises(AssertionError, match="lack strict lint coverage"):
        review.audit(repository)
    script.write_text("RESEARCH2_SCIENCE_LINT_TARGETS = ['discovery/new_science.py']\n")
    commit_all(repository)
    assert review.audit(repository)["strict_new_science_lint_coverage"] == {
        "new_scientific_module_count": 1,
        "uncovered": [],
    }
