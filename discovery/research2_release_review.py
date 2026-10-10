"""Independent exact-artifact/strict-JSON release audit of a fetched Git tree."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path

BASELINE = "379ff35786aff31535335bbe7d1de114f91dd3c4"
CANONICAL = {
    "candidate_neighborhood_v1.json": (
        "2b050c0",
        "10e74e8bd2c0b33b0a0e67927189580d5ac1e98561a6822924d8ed8b93a0b973",
        321806,
    ),
    "mom_author_provenance_v1.json": (
        "a4743ac",
        "e437c0de391c935d4d56ace5b9193db857135df1c6dabac464da9f79ddb4ec37",
        6585,
    ),
    "mom_cloudy_first_model.json": (
        "04766f6",
        "0c6718059538fcdb3739697c0a6dd77d915b69f2c23e057171972da3b939f6b4",
        259922,
    ),
    "mom_cloudy_signed_coupling.json": (
        "04766f6",
        "4c8ca3718c0d40281f0e5c458db87ee840dabfe8439c7bab1b6d8d67df40deb4",
        1147,
    ),
    "mom_cloudy_signed_coupling.npz": (
        "04766f6",
        "fa68e7585ee4c800f9543ad336b011f73eafa0a2ab6b7ee4ae6f1a6b416e7da2",
        15596,
    ),
    "mom_native_measurement_validation.json": (
        "4c65726",
        "c7e31e81a6bb6b9b4b81bf48661ccfa28475be5cf6b226f85113c78fe73074ca",
        136735,
    ),
    "mom_observation_design.json": (
        "f94252a",
        "45b067f2b394692613181700e5574f1ad3ede94dd90d69980d875518dc23fc59",
        36377,
    ),
    "mom_shared_systematics_v1.json": (
        "7c6cb10",
        "1871b31010506955003a5a629077a59273ba7dd1a9e5dfb5b101ee2d7905a0f8",
        8745,
    ),
    "survivor46_flame_v1.json": (
        "645174e",
        "7ed820f1482291db279c75445bd5e41403490aeada7a65c705eff9bb7b9d1c49",
        55021,
    ),
    "survivor46_medium_v1.json": (
        "2a1247a",
        "df00194c821bc3ff4b17ffd95c9fe7ba885c8f297f2bbdb636baf5da8f582eec",
        19680,
    ),
    "survivor46_multiplicity_v1.json": (
        "0eb1771",
        "767053b087f99b947103f6fbf0eb321ed0d652f7a9a7a64c3847a6fdae132834",
        31330,
    ),
    "mom_cloudy_focused_pair.json": (
        "62634bf",
        "50e63ba57d14c7cd664995ce1ec619f3118df2aa30f846551339a05ff0dd65fd",
        427426,
    ),
    "mom_cloudy_openblas_control.json": (
        "71f7011",
        "3b9444fe78925d99e91f50bf9fc850f1394bc361ba8f3ab671be0c4eb68077ee",
        9181,
    ),
    "mom_cloudy_enhanced_backend_control.json": (
        "5ebf3b2",
        "0d10acea141a94a911013fce551aa2e31b46450d89d26eafc94d5b3ecfdd1892",
        8357,
    ),
    "selection_count_audit.json": (
        "65d16cb",
        "c46b28bda61602b692f39c177eb9325329fd1a7a17440c1739da918b1bf28a46",
        53516,
    ),
    "mom_native_rate_noise.json": (
        "18ff94b",
        "5e9cc7e5e46870f0221c42f762a1186a1396f440e6b34f2b42d5c5fb259d9fc7",
        48427,
    ),
    "mom_native_rate_noise_arrays.npz": (
        "18ff94b",
        "4d679850b44b28ed3d8fc71f0e7fd41f0aa7a7cfcd95aff896de97b728bdfa5e",
        2181867,
    ),
}


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root)


def reject_constant(value):
    raise ValueError("Nonstandard JSON constant: " + value)


def science_lint_coverage(root, revision):
    added = (
        git(
            root,
            "diff",
            "--name-only",
            "--diff-filter=A",
            BASELINE,
            revision,
            "--",
            "discovery",
            "data_pipeline",
            "tools/jwst",
        )
        .decode()
        .splitlines()
    )
    scientific = sorted(name for name in added if name.endswith(".py"))
    if not scientific:
        return {"new_scientific_module_count": 0, "uncovered": []}
    config = ast.parse(git(root, "show", revision + ":scripts/quality_gate.py"))
    targets = set()
    for node in config.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "RESEARCH2_SCIENCE_LINT_TARGETS"
            for target in node.targets
        ):
            targets.update(ast.literal_eval(node.value))
    uncovered = sorted(set(scientific) - targets)
    assert not uncovered, "New scientific modules lack strict lint coverage: " + ", ".join(
        uncovered
    )
    return {"new_scientific_module_count": len(scientific), "uncovered": uncovered}


def audit(root, require_lint_coverage=True):
    revision = git(root, "rev-parse", "HEAD").decode().strip()
    subprocess.run(["git", "merge-base", "--is-ancestor", BASELINE, revision], cwd=root, check=True)
    names = git(root, "ls-tree", "-r", "--name-only", revision).decode().splitlines()
    json_count = 0
    for name in names:
        if name.endswith(".json"):
            raw = (root / name).read_bytes()
            assert raw == git(root, "show", revision + ":" + name), "Working tree changed: " + name
            json.loads(raw, parse_constant=reject_constant)
            json_count += 1
    baseline = (
        git(root, "ls-tree", "-r", "--name-only", BASELINE, "research_output").decode().splitlines()
    )
    for name in baseline:
        assert git(root, "rev-parse", BASELINE + ":" + name) == git(
            root, "rev-parse", revision + ":" + name
        ), name
    pinned = []
    for filename, (frozen, expected_sha256, expected_bytes) in CANONICAL.items():
        name = "research_output/" + filename
        published = git(root, "show", revision + ":" + name)
        assert len(published) == expected_bytes, "Canonical artifact bytes changed: " + filename
        assert hashlib.sha256(published).hexdigest() == expected_sha256, (
            "Canonical artifact changed: " + filename
        )
        pinned.append(
            {
                "filename": filename,
                "frozen_science_revision": frozen,
                "bytes": len(published),
                "sha256": hashlib.sha256(published).hexdigest(),
                "published_git_blob": git(root, "rev-parse", revision + ":" + name)
                .decode()
                .strip(),
            }
        )
    coverage = science_lint_coverage(root, revision) if require_lint_coverage else None
    return {
        "schema_version": 1,
        "fetched_release_revision": revision,
        "handover_baseline_ancestor": BASELINE,
        "strict_valid_tracked_json_count": json_count,
        "baseline_research_artifacts_preserved_count": len(baseline),
        "canonical_science_artifacts": pinned,
        "strict_new_science_lint_coverage": coverage,
        "scope": (
            "Exact Git/SHA256 artifact identities plus strict JSON across a fresh fetched tree; "
            "numerical review and executable test validation remain separate."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interim-skip-lint-coverage", action="store_true")
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(audit(args.root.resolve(), not args.interim_skip_lint_coverage), indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
