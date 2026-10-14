"""Prospective pole-field YSO feasibility; metadata only, never science products."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from discovery.research6_yso_pilot import BoundedMetadata, csv_rows, sha256

ROOT = Path(__file__).resolve().parents[1]
FREEZE = "docs/frozen/E_YSO_POLE_METADATA_DESIGN.md"
POLES = (("north", 270.0, 66.560708), ("south", 90.0, -66.560708))
COLLECTIONS = ("spherex_qr2_deep", "spherex_qr3_deep")


def load_json(path: Path) -> dict:
    """Read an unchanged metadata replay in plain or gzip-packaged JSON form."""
    body = path.read_bytes()
    if path.suffix == ".gz":
        body = gzip.decompress(body)
    return json.loads(body)


def inventory(rows: list[dict]) -> dict:
    """Inventory days, never mistake detector limits for source wavelengths."""
    unique = {}
    for row in rows:
        key = (row["obs_id"], row["energy_bandpassname"])
        if key not in unique:
            unique[key] = {
                "obs_id": key[0],
                "detector": key[1],
                "mjd": float(row["t_min"]),
                "collection": row["obs_collection"],
            }
    exposures = sorted(unique.values(), key=lambda x: (x["mjd"], x["obs_id"], x["detector"]))
    return {
        "raw_rows": len(rows),
        "physical_exposures": len(exposures),
        "utc_day_bins": len({math.floor(x["mjd"]) for x in exposures}),
        "detector_names": sorted({x["detector"] for x in exposures}),
        "source_eligible_visit_count": None,
        "eligibility_reason": (
            "SIA detector band bounds do not provide source channel wavelength/width"
        ),
        "exposures": exposures,
    }


def gate(targets: list[dict]) -> dict:
    """Fail closed on unknown source coverage and unknown matched controls."""
    passed = [
        t
        for t in targets
        if isinstance(t.get("eligible_visits"), int)
        and t["eligible_visits"] >= 8
        and t.get("eligible_matched_controls", 0) >= 5
    ]
    return {
        "passes": len(passed) >= 5,
        "certified_qualifying_targets": len(passed),
        "unknown_coverage_targets": sum(t.get("eligible_visits") is None for t in targets),
        "reason": (
            "requires five targets with eight source-qualified visits and five same-field controls"
        ),
    }


def necessary_metadata_gate(targets: list[dict]) -> dict:
    """Frame counts reject visits; incomplete catalogue photometry remains unknown."""
    possible = []
    unknown_k = []
    for target in targets:
        counts = Counter(math.floor(x["mjd"]) for x in target["inventory"]["exposures"])
        days_with_eight_frames = sum(count >= 8 for count in counts.values())
        try:
            has_k = math.isfinite(float(target["identity"].get("K", "")))
        except (TypeError, ValueError):
            has_k = False
        target["necessary_condition_metadata"] = {
            "max_frames_in_utc_day": max(counts.values(), default=0),
            "upper_bound_source_qualified_visits": days_with_eight_frames,
            "frozen_K_matching_available": has_k,
            "source_visit_wavelengths_measured": False,
        }
        if days_with_eight_frames >= 8:
            if has_k:
                possible.append(target["identity"]["main_id"])
            else:
                unknown_k.append(target["identity"]["main_id"])
    return {
        "upper_bound_qualifying_targets": len(possible) + len(unknown_k),
        "currently_K_assignable_possible_targets": len(possible),
        "unknown_K_target_ids": unknown_k,
        "possible_target_ids": possible,
        "fails_necessary_gate": len(possible) + len(unknown_k) < 5,
        "reason": "a day with fewer than eight frames cannot supply eight source channels; "
        "missing SIMBAD K is unresolved photometry, not absence of 2MASS coverage",
    }


def query(client: BoundedMetadata, name: str, sql: str) -> list[dict] | None:
    body = client.get(
        name,
        "https://simbad.cds.unistra.fr/simbad/sim-tap/sync",
        {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": sql},
    )
    if body is None:
        return None
    try:
        return csv_rows(body)
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=ROOT / "research_output/calibrated_20261014/e_poles"
    )
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--summarize-only", type=Path)
    args = parser.parse_args()
    if args.summarize_only:
        summary = load_json(args.summarize_only)
        verdict = necessary_metadata_gate(summary["targets"])
        output = args.summarize_only.parent / "e_necessary_gate.json"
        output.write_text(
            json.dumps(
                {
                    "verdict": verdict,
                    "targets": [
                        {
                            "identity": t["identity"],
                            "necessary_condition_metadata": t["necessary_condition_metadata"],
                        }
                        for t in summary["targets"]
                    ],
                },
                indent=2,
            )
            + "\n"
        )
        print(json.dumps(verdict))
        return 0
    if shutil.disk_usage(ROOT).free < 5_000_000_000:
        raise RuntimeError("Disk floor violated before metadata acquisition")
    commit = subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", FREEZE], cwd=ROOT, text=True
    ).strip()
    frozen = subprocess.check_output(["git", "show", f"{commit}:{FREEZE}"], cwd=ROOT)
    if frozen != (ROOT / FREEZE).read_bytes():
        raise RuntimeError("Design must be committed before access")
    client = BoundedMetadata(args.out, args.timeout, 30_000_000)
    summary = {
        "freeze_commit": commit,
        "freeze_sha256": sha256(frozen),
        "mode": "metadata only",
        "targets": [],
        "pole_identity_queries": [],
        "executed_code_sha256": sha256(Path(__file__).read_bytes()),
    }
    for pole, ra, dec in POLES:
        distance = f"DISTANCE(POINT('ICRS',b.ra,b.dec),POINT('ICRS',{ra},{dec}))"
        sql = (
            "SELECT TOP 10 b.main_id,b.otype,b.ra,b.dec,b.coo_bibcode,f.K,"
            + distance
            + " AS pole_distance FROM basic AS b LEFT JOIN allfluxes AS f ON b.oid=f.oidref "
            "WHERE b.otype IN ('Y*O','TT*','YSO','TTau*') AND "
            f"1=CONTAINS(POINT('ICRS',b.ra,b.dec),CIRCLE('ICRS',{ra},{dec},10)) "
            "ORDER BY pole_distance,main_id"
        )
        rows = query(client, f"pole_{pole}_identities", sql)
        summary["pole_identity_queries"].append(
            {
                "pole": pole,
                "status": "ok" if rows is not None else "blocked",
                "selected_count": len(rows) if rows is not None else None,
            }
        )
        if rows is None:
            continue
        for idx, identity in enumerate(rows):
            target = {
                "pole": pole,
                "identity": identity,
                "collection_queries": [],
                "eligible_visits": None,
                "eligible_matched_controls": 0,
            }
            allrows = []
            for collection in COLLECTIONS:
                body = client.get(
                    f"{pole}_{idx}_{collection}",
                    "https://irsa.ipac.caltech.edu/SIA",
                    {
                        "COLLECTION": collection,
                        "POS": f"CIRCLE {identity['ra']} {identity['dec']} 0.000277778",
                        "BAND": "2.8e-6 3.9e-6",
                        "CALIB": "2",
                        "RESPONSEFORMAT": "CSV",
                        "MAXREC": "10000",
                    },
                )
                srows = None
                if body is not None:
                    try:
                        srows = csv_rows(body)
                        if len(srows) >= 10000:
                            raise ValueError("Truncated at MAXREC, cannot certify completeness")
                        allrows.extend(srows)
                    except ValueError:
                        srows = None
                target["collection_queries"].append(
                    {"collection": collection, "rows": len(srows) if srows is not None else None}
                )
            target["inventory"] = inventory(allrows)
            try:
                kmag = float(identity.get("K", ""))
                if not math.isfinite(kmag):
                    raise ValueError("Nonfinite K")
            except ValueError:
                target["control_status"] = (
                    "target 2MASS K missing: frozen magnitude match unavailable"
                )
            else:
                d = (
                    "DISTANCE(POINT('ICRS',b.ra,b.dec),"
                    f"POINT('ICRS',{identity['ra']},{identity['dec']}))"
                )
                csql = (
                    "SELECT TOP 5 b.main_id,b.otype,b.ra,b.dec,f.K,"
                    + d
                    + " AS control_distance FROM basic AS b JOIN allfluxes AS f ON b.oid=f.oidref "
                    "WHERE b.otype='*' AND "
                    f"1=CONTAINS(POINT('ICRS',b.ra,b.dec),"
                    f"CIRCLE('ICRS',{identity['ra']},{identity['dec']},0.5)) "
                    f"AND f.K BETWEEN {kmag - 1} AND {kmag + 1} ORDER BY control_distance,main_id"
                )
                controls = query(client, f"{pole}_{idx}_controls", csql)
                target["potential_controls"] = controls
                target["control_status"] = (
                    "coverage unknown: no source-channel metadata to qualify matched controls"
                )
            summary["targets"].append(target)
            (args.out / "e_summary_partial.json").write_text(json.dumps(summary, indent=2) + "\n")
    summary.update(
        gate=gate(summary["targets"]),
        response_body_bytes=client.total,
        first_access_utc=client.first_access,
        receipts=client.receipts,
        science_product_bytes=0,
    )
    (args.out / "e_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        json.dumps(
            {k: summary[k] for k in ["gate", "response_body_bytes", "pole_identity_queries"]}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
