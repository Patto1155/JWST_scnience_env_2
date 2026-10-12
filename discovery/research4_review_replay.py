"""Zero-download independent numerical replay from released-coadd compact arrays."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from discovery.research4_review_integration import integrate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--compact-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    original = json.loads(args.receipt.read_text())
    archives, checks = [], []
    for target in original["targets"]:
        assert target["unique_id"].startswith("goods-s-")
        products = {}
        for config in ["f070lp-g140m", "f170lp-g235m"]:
            path = args.compact_root / (
                f"research4_jades_{target['unique_id']}_{config}_inputs.npz"
            )
            products[config] = np.load(path, allow_pickle=False)
            archives.append(
                {
                    "name": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "bytes": path.stat().st_size,
                }
            )
        count = 0
        for key, expected in target["measurements"].items():
            parts = key.split("_")
            config, aperture, width = parts[0], parts[1], float(parts[-1])
            field = "_".join(parts[2:-2])
            error_field = "FLUX_ERR" if field == "FLUX" else "FLUX_ERR_NOD2"
            data = {
                col: products[config][f"{aperture}_{col}"]
                for col in ["WAVELENGTH", field, error_field]
            }
            result = integrate(data, expected["center_um"], width, field, error_field)
            if result != expected:
                raise AssertionError(f"Numerical replay differs: {target['unique_id']} {key}")
            count += 1
        for product in products.values():
            product.close()
        checks.append({"unique_id": target["unique_id"], "exact_measurements": count})
    result = {
        "scope": "Zero-download actual released-coadd-array replay; GOODS-N unopened",
        "original_receipt_sha256": hashlib.sha256(args.receipt.read_bytes()).hexdigest(),
        "all_measurements_match_exactly": True,
        "measurement_count": sum(x["exact_measurements"] for x in checks),
        "products": archives,
        "targets": checks,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        f"Exact match for {result['measurement_count']} line integrations "
        f"from {len(archives)} archives"
    )


if __name__ == "__main__":
    main()
