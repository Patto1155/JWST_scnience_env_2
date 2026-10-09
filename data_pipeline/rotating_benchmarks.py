"""Extract a primary paper's numerical model table without inventing yield grids."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from data_pipeline.followup_data import verify


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.rows = []
        self.row = None
        self.cell = None
        self.math_depth = 0

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag == "table" and attributes.get("id") == "S3.T2.2.1":
            self.active = True
        if not self.active:
            return
        if tag == "tr":
            self.row = []
        if tag in {"th", "td"}:
            self.cell = ""
        if tag == "math":
            self.math_depth += 1
            self.cell += attributes.get("alttext", "")

    def handle_endtag(self, tag):
        if not self.active:
            return
        if tag == "math":
            self.math_depth -= 1
        if tag in {"th", "td"} and self.cell is not None:
            self.row.append(self.cell.strip())
            self.cell = None
        if tag == "tr":
            self.rows.append(self.row)
            self.row = None
        if tag == "table":
            self.active = False

    def handle_data(self, value):
        if self.active and self.cell is not None and self.math_depth == 0:
            self.cell += value


def values(text: str) -> list[float]:
    return [float(x) for x in re.findall(r"-?\d+\.\d+", text)]


def extract(input_html: Path, output_csv: Path) -> dict:
    receipt = verify(input_html)
    parser = TableParser()
    parser.feed(input_html.read_text())
    if len(parser.rows) != 25 or parser.rows[0][:2] != ["Scenario", "Z"]:
        raise ValueError("Primary Table2 shape/header mismatch")
    columns = ["scenario", "metallicity_source", "dilution_range_source", "log_OH_plus12_source",
               "log_NO_source", "log_CO_source", "log_HeH_source", "log_C12C13_source"]
    result = []
    scenario = None
    for raw in parser.rows[1:]:
        if len(raw) == 8:
            scenario = " ".join(raw[0].split())
            raw = raw[1:]
        if len(raw) != 7 or scenario is None:
            raise ValueError("Primary Table2 row topology mismatch")
        row = dict(zip(columns, [scenario, *raw]))
        nitrogen, carbon = values(row["log_NO_source"]), values(row["log_CO_source"])
        if not nitrogen or not carbon:
            raise ValueError("Expected numeric NO/CO ranges")
        row.update(log_NC_lower=min(nitrogen)-max(carbon), log_NC_upper=max(nitrogen)-min(carbon))
        # Same primary paper Table3 uses solarNO=-.86 and solarCO=-.23.
        row.update(bracket_NC_lower=row["log_NC_lower"]+.63,
                   bracket_NC_upper=row["log_NC_upper"]+.63)
        result.append(row)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(result[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(result)
    metadata = {"kind": "primary_model_mixed_ISM_table_not_raw_stellar_yields",
                "source_receipt": receipt, "rows": len(result),
                "transform": "ExtractHTMLTable2; NC=NO-CO conservative unpaired endpoint envelope",
                "solar_log_NC": -.63, "solar_basis": "SamepaperTable3logNO=-.86 minus logCO=-.23",
                "science_limit": "Table2dilution constrained toGNz11oxygenrange, notMoMfit; modelrangesare notstatistical uncertainty",
                "bytes": output_csv.stat().st_size,
                "sha256": hashlib.sha256(output_csv.read_bytes()).hexdigest()}
    output_csv.with_name(output_csv.name + ".provenance.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(extract(args.input, args.output), indent=2))


if __name__ == "__main__":
    main()
