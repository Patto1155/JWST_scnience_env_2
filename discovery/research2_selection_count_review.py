"""Independent native-count identifiability/header and variance control audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zlib
from pathlib import Path

import numpy as np
from astropy.io import fits
from scipy.optimize import minimize


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root, inputs, images, public_head=None):
    manifest_path = root / "data_sources/selection_count_audit/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    artifact_path = root / "research_output/selection_count_audit.json"
    artifact = json.loads(artifact_path.read_text())
    for product in manifest["products"]:
        path = inputs / product["filename"]
        assert path.stat().st_size == product["expected_bytes"] and sha(path) == product["sha256"]
    prefix = inputs / "dja_f444w_assoc_var_prefix4096.bin"
    if prefix.exists():
        header_bytes = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(
            prefix.read_bytes(), 65536
        )
        header = fits.Header.fromstring(header_bytes.decode("ascii", errors="replace"))
        assert header["SIMPLE"] and header["BITPIX"] == -32
        assert header["NAXIS"] == 2 and header["NAXIS1"] == 3976 and header["NAXIS2"] == 4032
    processor = (inputs / "grizli_aws_visit_processor.py").read_text()
    for target, variable in (("wht", "outwht"), ("var", "outvar")):
        assert re.search(r"\{1\}_" + target + r"\.fits.*?data=" + variable, processor, flags=re.S)
    utils = (inputs / "grizli_utils.py").read_text()
    assert "(var_list[i] * use_weights[i]).astype" in utils and "outvar /= outwht" in utils
    assert 'var = flt["VAR_RNOISE", ext].data + med_poisson' in utils
    tile = (inputs / "grizli_aws_tile_mosaic.py").read_text()
    last = tile.index("llh['NDRIZIM'] = len(exposures)")
    assert last < tile.index("llh[f'FLT{j+1:05d}'] = exp", last)
    assert last < tile.index("llh[k] = im[0].header[k]", last)
    rows = list(csv.DictReader((inputs / "dja_exposures_center.csv").open()))
    checked = []
    for entry in artifact["images"]:
        path = images / entry["filename"]
        assert sha(path) == entry["sha256"]
        with fits.open(path) as hdul:
            header = hdul[0].header
            names = [header[k] for k in header if k.startswith("FLT")]
            ids = {name.removesuffix("_rate.fits") for name in names}
            matched = [r for r in rows if r["file"] in ids and r["filter"] == header["FILTER"]]
            expected = [
                len(ids),
                len([k for k in header if k.startswith("WHT") and k != "WHTTYPE"]),
                len(matched),
                sum(float(r["exptime"]) for r in matched),
            ]
            actual = [
                entry["unique_contributor_count"],
                entry["scalar_median_weight_header_count"],
                entry["center_query_matching_contributor_count"],
                entry["center_query_geometric_exptime_sum_s"],
            ]
            assert np.allclose(expected, actual, rtol=0, atol=1e-8)
            assert all(h.name not in ("VAR", "VAR_POISSON", "CON") for h in hdul)
            checked.append(
                {
                    "filename": path.name,
                    "contributor_header_counts": expected[:3],
                    "geometric_exptime_sum_s": expected[3],
                }
            )
    rng = np.random.default_rng(3956)
    counts = np.array([1.0, 4.0])
    simulations = []
    for weight, bg in ((np.array([0.2, 0.8]), 10.0), (np.array([0.8, 0.2]), 1.0)):
        samples = (rng.poisson(20 * counts, size=(200000, 2)) / counts) @ weight
        source_variance = 20 * np.sum(weight * weight / counts)
        noisy = samples + rng.normal(scale=np.sqrt(bg), size=len(samples))
        measured = float(noisy.var(ddof=1))
        assert abs(measured - 14) < 5 * 14 * np.sqrt(2 / (len(samples) - 1))
        simulations.append(
            {
                "source_variance": float(source_variance),
                "background_variance": bg,
                "full_variance": 14.0,
                "simulated_full_variance": measured,
            }
        )
    bound_errors = []
    for _ in range(40):
        c = np.exp(rng.uniform(-2, 2, 5))
        solution = minimize(
            lambda a: np.sum(a * a / c),
            np.ones(5) / 5,
            method="SLSQP",
            bounds=[(0, 1)] * 5,
            constraints={"type": "eq", "fun": lambda a: a.sum() - 1},
            options={"ftol": 1e-13, "maxiter": 100},
        )
        assert solution.success
        error = abs(solution.fun - 1 / c.sum())
        assert error < 1e-11
        maximum = max(1 / c)
        assert abs(maximum - 1 / c.min()) < 1e-14
        bound_errors.append(error)
    classes = artifact["representative_class_denominators"]
    response = json.loads((root / "research_output/selection_pilot_response.json").read_text())
    assert classes["observed_null_centroid_matches"] == sum(
        row["centroid_status"] == "matched" for row in response["null_site_controls"]
    )
    assert classes["observed_null_joint_red_passes"] == sum(
        row["selected_red"] for row in response["null_site_controls"]
    )
    assert classes["astronomical_contamination_numerator"] is None
    assert classes["astronomical_contamination_denominator"] is None
    assert not any(value for key, value in classes.items() if key.startswith("verified_actual_"))
    reviewed = {
        "schema_version": 1,
        "artifact_sha256": sha(artifact_path),
        "manifest_sha256": sha(manifest_path),
        "actual_source_metadata_pins_verified": len(manifest["products"]),
        "actual_headers_and_csv": checked,
        "source_poisson_simulated_counterexample": simulations,
        "independent_constrained_minimum_checks": 40,
        "maximum_scalar_bound_error": max(bound_errors),
        "class_denominator_absent": True,
        "scope": (
            "Pinned released code, actual cutout/CSV headers, independent scalar optimizer "
            "and Poisson simulation. Generic coadd identifiability witness; "
            "no exact DJA duplication. "
            "Public VAR prefix still awaits raw retained bytes for independent decoding; "
            "no native photon calibration or population odds."
        ),
    }
    if public_head is not None:
        head = json.loads(public_head.read_text())
        public = artifact["public_variance_probes"]["records"][0]
        assert head["url"] == public["url"]
        assert head["status"] == 200 and head["content_length"] == "43219789"
        assert head["etag"] == public["requests"][0]["etag"]
        assert head["body_bytes_acquired"] == 0
        reviewed["independent_zero_body_public_HEAD"] = head
    if prefix.exists():
        reviewed["actual_public_VAR_prefix"] = {
            "bytes": prefix.stat().st_size,
            "sha256": sha(prefix),
            "decoded_primary_shape": [3976, 4032],
            "decoded_BITPIX": -32,
            "scope": "Only retained primary FITS header decoded; full variance image not acquired.",
        }
        reviewed["scope"] = (
            "Pinned released code, actual cutout/CSV headers, independent scalar optimization "
            "and Poisson simulation, independently decoded public VAR prefix. Generic "
            "coadd witness, not exact DJA duplication or native count calibration/population odds."
        )
    return reviewed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "inputs", "images", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--public-head", type=Path)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(audit(args.root, args.inputs, args.images, args.public_head), indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
