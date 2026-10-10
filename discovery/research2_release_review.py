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
    "mom_native_row_response.json": (
        "dc9cb69",
        "ee0a79bcc65ff60da25cbd97ad8e9aca895a70d9c7f222dca7039da29036ab00",
        42996,
    ),
    "mom_native_local_identifiability.json": (
        "b44f219",
        "36538f611670eed232c07064fc731e90c88211e384a34b5054fa35441cb45ce2",
        21243,
    ),
    "mom_cloudy_focused_pair_rate_v3.json": (
        "6d6fd5e",
        "3c4d1dfb18cb011b8640c7b8425c94c03773b5a42dcb8fa8c8b0e6ccc4f220f2",
        292222,
    ),
    "mom_public_metadata_v1.json": (
        "f9b22f9",
        "80ad68c99411d46f8abae2dbce113596499041d15edb8efa81da0a5fb5ee4f1d",
        37452,
    ),
    "mom_compact_followup_v1.json": (
        "ba99a31",
        "fdd3d749ac25ddbb31db71cdc7148029437aa6cf3f59717f73acfab069d76053",
        4514,
    ),
    "capers_pixtab_coverage_v1.json": (
        "6ce04a5",
        "a22f30092bfb51149221733e4575cc4a6f3082f13c0e85ea62a751292558436c",
        19505,
    ),
    "capers_companion_coverage_v1.json": (
        "a768eb3",
        "043de0ad96cf0d1c47e46fc74af591f13637c5755625f42f60109e505c3ff168",
        5077,
    ),
    "capers_s2d_coverage_v1.json": (
        "db0e170",
        "b0da433b8f1168006b38435b12c427aef86158efd61e21737b3304f042176570",
        7212,
    ),
    "cloudy_inputs.json": (
        "04766f6",
        "cb4561102fcf35f491ea561e0a5fddf80b5d636b3ba0a11e3f1c0f0aa08ff39c",
        17023,
    ),
    "mom_cloudy_capped_pilot.json": (
        "e6393e4",
        "639ad54753e7aa18d105ec6c8941c47f94ef8a9ed85b194d827aa7ed519b692e",
        12527,
    ),
    "selection_pilot_response.json": (
        "ecc2c481ca8abbbb620f46520fcffdc666b6dbb7",
        "f1b19aea12e4623e1b3a6253399f9f4a12eaf629e760ac659020e5f5a7fc2b10",
        67681,
    ),
    "selection_pilot_validation.json": (
        "ecc2c481ca8abbbb620f46520fcffdc666b6dbb7",
        "a5f11a952618938aeaf27ac98620e5c55eec7d08326710b482a3b61ca6f324c3",
        1044,
    ),
    "selection_count_audit_validation.json": (
        "f6ee1a869a6cdb5ca1e5c2964e31239d20b1095e",
        "7caeb744a8a12702d2944068ee4e48cd00f4923088a8de6ebc55511109e4de3d",
        2078,
    ),
    "selection_variance_public_probes.json": (
        "670d86737639202c359aa05f88af1d5257ef25da",
        "d4f283a7e40a07cff998a071a1d44c53224f3d22f9e1f6ab8a2b260a63128c89",
        6422,
    ),
    "selection_var_prefix_retention.json": (
        "65d16cb",
        "231cfd06ffc9b4863381a6c87b755aba3f0de393f6146e5635cd483caca8c892",
        912,
    ),
    "survivor46_medium_v1.png": (
        "2a1247a",
        "437cacc6e1887e7095578124edb3ec9d7bf28b5b16fdd8ff2a8c94245d52c29c",
        142407,
    ),
    "research2_download_ledger.json": (
        "360c0fb",
        "1a6a2f821ba35c6485cd6b66d12425b59d307d67bbebbee9e417f22b9dee706c",
        7034,
    ),
    "research2_download_ledger_v2.json": (
        "5f7e1c6",
        "2073a6ba008933a9f9963c258c9419cb178956ec0fab1fd0e0f5306982ebd176",
        8655,
    ),
    "research2_download_ledger_v3.json": (
        "2ef87ba",
        "09b9f42a2e708da32529e4244bcbb8f658cc7b4e3ffbf4c303ef1c37d2eae642",
        10406,
    ),
    "mom_cloudy_atomic_provenance.json": (
        "97524d5",
        "1c18ee7532e63ba7c69374408d4c37fefdec29b894aa503f5af90a91e3cfa7fb",
        3086,
    ),
    "mom_cloudy_original_pair_raw.json": (
        "56262de",
        "0b3d997a933c4a1c5e70c722b561686d5fb47823ac92fc71240c458d0c076c69",
        2920,
    ),
    "mom_cloudy_original_pair_raw.tar.gz": (
        "56262de",
        "0bfc0261772b5dd338518aaa6859bb2c39dd844557a5e3c40cca7bc0f5e4f2dd",
        228541,
    ),
    "mom_cloudy_capped_raw.json": (
        "df3150b",
        "f68fc2d9d01215f4fe840142ed7964724a55b914b517324ec0d15c75bfa76032",
        7678,
    ),
    "mom_cloudy_capped_raw.tar.gz": (
        "df3150b",
        "173170e34feaca94eb4735f62fa417f921b387c7103ad2bffe0bce27ad068dec",
        316171,
    ),
    "mom_cloudy_pilot20_rate_v3.json": (
        "a49e7f3",
        "7ef48626ddfb7c882d9725b17939c3a7752151de734e3ab4c46472b940127759",
        2221190,
    ),
    "mom_cloudy_pilot20_raw.json": (
        "a49e7f3",
        "7e334f516463fbb0304c118b3822c468d2d84ba9b030afe75be85d9018dc50e2",
        21869,
    ),
    "mom_cloudy_pilot20_raw.tar.gz": (
        "a49e7f3",
        "5b36c11a1f9839e30d433198ad47ec7c69e977f476992aaa26beae853fcf4f4a",
        2276836,
    ),
    "mom_cloudy_observation_contrasts.json": (
        "12ee3b6",
        "a73b72229e2f20f87c14b29b84f88f50a8cb594cb0ff220eb22b93d4b8c65a29",
        310697,
    ),
    "mom_cloudy_observation_execution.json": (
        "12ee3b6",
        "f4d2e25846ca27fa1626bb6f7a46991b6fdf7ddb8dbd0ea8383af9ed4482b109",
        1064,
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
