"""Promotion and skip gates must fail closed for undeclared coverage."""

from pathlib import Path

import pytest

from scripts.lint_ledger import COLUMNS, lint_ledger
from scripts.quality_gate import ALLOWED_SKIPS, check_pytest_skips, new_diagnostics


def write_ledger(root: Path, grade: str, missing: str | None = None) -> Path:
    values = {
        name: name.lower().replace(" ", "_").replace("/", "_") + ".json" for name in COLUMNS[2:6]
    }
    for value in values.values():
        (root / value).write_text("{}", encoding="utf-8")
    row = [
        "test finding",
        grade,
        *("—" if name == missing else values[name] for name in COLUMNS[2:6]),
        "test scope",
    ]
    ledger = root / "ledger.md"
    ledger.write_text(
        "| "
        + " | ".join(COLUMNS)
        + " |\n| "
        + " | ".join(["---"] * len(COLUMNS))
        + " |\n| "
        + " | ".join(row)
        + " |\n",
        encoding="utf-8",
    )
    return ledger


@pytest.mark.parametrize("grade", ["Candidate", "Validated"])
@pytest.mark.parametrize("missing", COLUMNS[3:6])
def test_promotion_missing_each_control_fails(tmp_path, grade, missing):
    ledger = write_ledger(tmp_path, grade, missing)
    assert any(missing in error for error in lint_ledger(ledger, tmp_path))


def test_complete_controls_pass_but_missing_evidence_file_fails(tmp_path):
    ledger = write_ledger(tmp_path, "Candidate")
    assert lint_ledger(ledger, tmp_path) == []
    (tmp_path / "evidence.json").unlink()
    assert any("missing/non-repo" in error for error in lint_ledger(ledger, tmp_path))


def test_unconfirmed_grade_requires_evidence_but_not_controls(tmp_path):
    ledger = write_ledger(tmp_path, "Unconfirmed lead", "Null control")
    assert lint_ledger(ledger, tmp_path) == []


def test_unapproved_skip_is_rejected(tmp_path):
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuite><testcase classname="tests.test_new" name="test_skip">'
        '<skipped message="data unavailable" /></testcase></testsuite>'
    )
    assert not check_pytest_skips(report)


def test_allowlist_requires_exact_identity_and_reason(tmp_path):
    identity, reason = next(iter(ALLOWED_SKIPS.items()))
    classname, name = identity.rsplit(".", 1)
    report = tmp_path / "junit.xml"
    report.write_text(
        f'<testsuite><testcase classname="{classname}" name="{name}">'
        f'<skipped message="{reason}" /></testcase></testsuite>'
    )
    assert check_pytest_skips(report)
    report.write_text(report.read_text().replace(reason, "new unexplained skip"))
    assert not check_pytest_skips(report)


def test_new_file_lint_is_not_inherited_from_legacy_baseline(tmp_path):
    from scripts.quality_gate import diagnostic_key

    old = tmp_path / "old.py"
    old.write_text("import unused\n")
    item = {
        "filename": str(old),
        "code": "F401",
        "message": "unused import",
        "location": {"row": 1},
    }
    baseline = [diagnostic_key(item, tmp_path)]
    assert new_diagnostics([item], baseline, tmp_path) == []
    new = tmp_path / "new.py"
    new.write_text(old.read_text())
    assert new_diagnostics([{**item, "filename": str(new)}], baseline, tmp_path)
    assert new_diagnostics([item, item], baseline, tmp_path)
