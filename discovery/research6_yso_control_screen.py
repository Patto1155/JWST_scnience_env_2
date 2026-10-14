"""Frozen fixed-target AllWISE field-control count screen; no variability outcomes."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

from astropy.table import Table

from discovery.research6_yso_pilot import ROOT, BoundedMetadata


def allwise_rows(body: bytes):
    table = Table.read(io.BytesIO(body), format="ascii.ipac")
    return [{k: str(row[k]) for k in table.colnames} for row in table]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "research_output/session_20261014")
    args = parser.parse_args()
    inputs = json.loads((args.out / "f_current/f_metadata_summary.json").read_text())
    client = BoundedMetadata(args.out / "f_other_controls", 25)
    results = []
    for i, target in enumerate(inputs["targets"][1:], start=1):
        base = {
            "catalog": "allwise_p3as_psd",
            "spatial": "cone",
            "objstr": f"{target['ra']} {target['dec']}",
            "radius": 3,
            "radunits": "arcsec",
            "outfmt": 1,
            "selcols": "designation,ra,dec,w1mpro,w1sigmpro,cc_flags,w1rchi2,w1sat,ext_flg",
        }
        entry = {
            "name": target["name"],
            "selection": "frozen0.5deg,+/-0.5magW1",
            "family_trials": 6,
        }
        body = client.get(
            f"target_{i}", "https://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query", base
        )
        if body is None:
            entry["status"] = "identity metadata blocked"
        else:
            try:
                matches = allwise_rows(body)
                entry["target_matches"] = matches
                if len(matches) != 1:
                    raise ValueError("AllWISE target association not unique")
                magnitude = float(matches[0]["w1mpro"])
                params = {
                    **base,
                    "radius": 0.5,
                    "radunits": "deg",
                    "constraints": (
                        f"w1mpro>={magnitude - 0.5:.6f} "
                        f"AND w1mpro<={magnitude + 0.5:.6f}"
                    ),
                }
                field_body = client.get(
                    f"field_{i}", "https://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query", params
                )
                if field_body is None:
                    entry["status"] = "field metadata blocked"
                else:
                    rows = allwise_rows(field_body)
                    maximum = [
                        r
                        for r in rows
                        if r["designation"] != matches[0]["designation"] and r["cc_flags"][0] == "0"
                    ]
                    entry.update(
                        all_field_rows=rows,
                        clean_W1_other_source_upper_bound=len(maximum),
                        remaining_possible_controls=maximum,
                        status="frozen minimum10controls impossible"
                        if len(maximum) < 10
                        else "Gaia/YSO eligibility remains to be checked",
                    )
            except (ValueError, KeyError) as error:
                entry["status"] = f"parse/identity blocked: {error}"
        results.append(entry)
        (client.out / "f_other_target_control_screen.json").write_text(
            json.dumps(results, indent=2) + "\n"
        )
    print(
        json.dumps(
            [
                {k: r.get(k) for k in ("name", "status", "clean_W1_other_source_upper_bound")}
                for r in results
            ],
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
