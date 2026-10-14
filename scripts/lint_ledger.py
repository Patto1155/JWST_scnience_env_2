"""Validate the sole claim ledger and require controls before promotion."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRADES = {"Validated", "Candidate", "Unconfirmed lead", "Null", "Rejected", "Superseded"}
COLUMNS = (
    "Finding",
    "Grade",
    "Evidence",
    "Null control",
    "Injection recovery",
    "Independent repeat/holdout",
    "Scope",
)
CONTROL_COLUMNS = COLUMNS[3:6]
EMPTY = {"", "-", "—", "None", "N/A", "Not run"}


def referenced_paths(cell: str) -> list[str]:
    """Accept Markdown links, backtick paths or semicolon-separated bare paths."""
    if cell.strip() in EMPTY:
        return []
    links = re.findall(r"\[[^\]]*\]\(([^)]+)\)", cell)
    if links:
        return links
    quoted = re.findall(r"`([^`]+)`", cell)
    if quoted:
        return quoted
    return [part.strip() for part in cell.split(";") if part.strip()]


def lint_ledger(ledger: Path, root: Path = ROOT) -> list[str]:
    """Check grades, evidence and three distinct control roles for every row."""
    if not ledger.is_file():
        return [f"Missing claim ledger: {ledger}"]
    errors = []
    header_seen = False
    count = 0
    for line_number, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
        if not line.lstrip().startswith("|"):
            continue
        cells = tuple(cell.strip() for cell in line.strip().strip("|").split("|"))
        if cells == COLUMNS:
            header_seen = True
            continue
        if not header_seen or all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        if len(cells) != len(COLUMNS):
            errors.append(f"Line {line_number}: expected {len(COLUMNS)} columns")
            continue
        row = dict(zip(COLUMNS, cells))
        count += 1
        prefix = f"Line {line_number} ({row['Finding']})"
        if row["Grade"] not in GRADES:
            errors.append(f"{prefix}: invalid grade {row['Grade']!r}")
        if not referenced_paths(row["Evidence"]):
            errors.append(f"{prefix}: missing Evidence artifact")
        for column in COLUMNS[2:6]:
            paths = referenced_paths(row[column])
            if column in CONTROL_COLUMNS and row["Grade"] in {"Validated", "Candidate"}:
                if not paths:
                    errors.append(f"{prefix}: promotion requires {column} artifact")
            for path in paths:
                # No web URL, external path, traversal or anchor substitutes for a saved artifact.
                target = (root / path).resolve()
                if not target.is_relative_to(root.resolve()) or not target.is_file():
                    errors.append(f"{prefix}: {column} references missing/non-repo file {path!r}")
    if not header_seen or count == 0:
        errors.append("Ledger must contain the required header and at least one finding")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", nargs="?", type=Path, default=ROOT / "docs/CLAIM_LEDGER.md")
    args = parser.parse_args()
    errors = lint_ledger(args.ledger)
    for error in errors:
        print(f"[LEDGER][FAIL] {error}")
    if not errors:
        print("[LEDGER][OK] Grades, evidence paths and promotion controls checked")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
