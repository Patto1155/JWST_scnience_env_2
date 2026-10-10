"""Audit identifiability of native source-count transport from exported cutouts.

Public code is inspected as data, never imported or executed. Exposure metadata
is geometric provenance, not a local DQ/time/weight or gain calibration map.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import re
import zlib
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np
from astropy.io import fits

from data_pipeline.research_sources import fetch_product
from discovery.deep_control_recovery import json_hash
from discovery.selection_pilot import MANIFEST as IMAGE_MANIFEST

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data_sources/selection_count_audit/manifest.json"


def acquire(directory: Path) -> dict:
    manifest = json.loads(MANIFEST.read_text())
    total, inputs = 0, []
    for product in manifest["products"]:
        path = directory / product["filename"]
        if not path.exists():
            if product.get("acquisition_kind") == "bounded_http_prefix":
                limit = product["expected_bytes"]
                if limit != 4096 or product["max_bytes"] != limit:
                    raise ValueError("Only pinned4096-byte variance prefixes are permitted")
                request = Request(
                    product["url"],
                    headers={"Range": "bytes=0-4095", "User-Agent": "jwst-science-prefix/1"},
                )
                with urlopen(request, timeout=30) as response:
                    raw = response.read(limit)
                    if response.headers.get("ETag") != product["etag"]:
                        raise ValueError("Public variance prefix ETag changed")
                if hashlib.sha256(raw).hexdigest() != product["sha256"]:
                    raise ValueError("Public variance prefix identity changed")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            else:
                fetch_product(product, path, max_bytes=product["max_bytes"], timeout=60)
        raw = path.read_bytes()
        if (
            len(raw) != product["expected_bytes"]
            or hashlib.sha256(raw).hexdigest() != product["sha256"]
        ):
            raise ValueError("Audit source/metadata differs from pinned bytes")
        total += len(raw)
        if total > manifest["acquisition_cap_bytes"]:
            raise ValueError("Audit acquisition cap exceeded")
        inputs.append({"filename": path.name, "bytes": len(raw), "sha256": product["sha256"]})
    probe = json.loads((ROOT / "research_output/selection_variance_public_probes.json").read_text())
    probe_hash = probe.pop("result_content_sha256")
    if json_hash(probe) != probe_hash:
        raise ValueError("Versioned bounded public probe receipt was changed")
    probe_bytes = sum(
        request.get("acquired_body_bytes", 0)
        for record in probe["records"] for request in record["requests"]
    )
    if probe_bytes != probe["actual_acquired_body_bytes"] or probe_bytes > 16384:
        raise ValueError("Bounded public probe byte accounting failed")
    if total + probe_bytes > manifest["acquisition_cap_bytes"]:
        raise ValueError("Combined source plus probe acquisition cap exceeded")
    return {
        "actual_new_bytes": total + probe_bytes,
        "metadata_source_bytes": total,
        "bounded_probe_body_bytes": probe_bytes,
        "repeat_prefix_transfer_bytes": manifest.get("repeat_transfer_bytes", 0),
        "inputs": inputs,
        "source_release": manifest["source_release"],
        "source_git_revision": manifest["source_git_revision"],
        "source_scope": manifest["source_scope"],
    }


def weighted_source_variance(flux: float, counts_per_njy: np.ndarray, weights: np.ndarray) -> float:
    counts, coefficient = np.asarray(counts_per_njy, float), np.asarray(weights, float)
    if (
        counts.ndim != 1
        or counts.shape != coefficient.shape
        or not len(counts)
        or not np.isfinite(counts).all()
        or np.any(counts <= 0)
        or not np.isfinite(coefficient).all()
        or np.any(coefficient < 0)
        or not np.isclose(coefficient.sum(), 1)
        or not np.isfinite(flux)
        or flux < 0
    ):
        raise ValueError("Require nonnegative flux, positive counts and normalized coadd weights")
    return float(flux * np.sum(coefficient**2 / counts))


def scalar_variance_bounds(flux: float, counts_per_njy: np.ndarray) -> list[float]:
    """Exact conditional bounds for one nonnegative normalized scalar coadd.

    Cauchy-Schwarz gives sum(a_i**2/c_i)>=1/sum(c_i); convexity gives
    sum(a_i**2/c_i)<=1/min(c_i). Not a signed aperture/drizzle covariance bound.
    """
    counts = np.asarray(counts_per_njy, float)
    if (
        counts.ndim != 1
        or not len(counts)
        or not np.isfinite(counts).all()
        or np.any(counts <= 0)
        or not np.isfinite(flux)
        or flux < 0
    ):
        raise ValueError("Require positive count conversion and finite nonnegative flux")
    return [float(flux / counts.sum()), float(flux / counts.min())]


def coadd_nonidentifiability() -> dict:
    counts = np.array([1.0, 4.0])
    hypotheses = []
    for weight in (np.array([0.2, 0.8]), np.array([0.8, 0.2])):
        source_var = weighted_source_variance(20, counts, weight)
        background_var = 14.0 - source_var
        native_background = np.repeat(background_var / np.sum(weight**2), 2)
        propagated_background = float(weight @ np.diag(native_background) @ weight)
        hypotheses.append(
            {
                "normalized_local_weights": weight.tolist(),
                "expected_calibrated_source_flux_njy": float(weight @ [20.0, 20.0]),
                "native_input_background_variance_njy2": native_background.tolist(),
                "background_variance_njy2": propagated_background,
                "source_component_variance_njy2": source_var,
                "full_err_variance_njy2": propagated_background + source_var,
                "additional_F20_source_variance_njy2": source_var,
            }
        )
    return {
        "hypotheses": hypotheses,
        "counts_per_njy_given_for_example": counts.tolist(),
        "exported_full_err_inverse_variance": 1 / 14.0,
        "summed_count_conversion_unchanged": 5,
        "source_variance_conditional_bounds_njy2": scalar_variance_bounds(20, counts),
        "scope": (
            "Mathematical calibrated-coadd counterexample: same scene mean, full-ERR "
            "WHT, input identities and total time hide different local weights and "
            "nonnegative native noise decompositions; not a proposed DJA reduction"
        ),
    }


def inspect_release_sources(directory: Path) -> dict:
    source = (directory / "grizli_utils.py").read_text()
    tree = ast.parse(source)
    nodes = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    for name in ("drizzle_from_visit", "drizzle_array_groups"):
        if name not in nodes:
            raise ValueError("Pinned release lacks expected drizzle functions")
    visit = ast.get_source_segment(source, nodes["drizzle_from_visit"])
    required = (
        'weight_type="jwst_var"',
        "med_poisson = np.nanmedian(_var_data)",
        'var = flt["VAR_RNOISE", ext].data + med_poisson',
        "_var = err_data**2",
        "var_list.append(_var)",
        'header["WHT{0:05d}".format(count)]',
        "median_weight,",
    )
    if not all(token in visit for token in required):
        raise ValueError("Unexpected release weight/variance/header strategy; inspect anew")
    release = json.loads((directory / "grizli-1.12.10.json").read_text())
    tag = json.loads((directory / "grizli-tag-1.12.10.json").read_text())
    if (
        release["info"]["version"] != "1.12.10"
        or tag["object"]["sha"] != "3c5b6beb620607993ddf9c300652980c59ed2fa1"
    ):
        raise ValueError("Logged-release source identity mismatch")
    processor_source = (directory / "grizli_aws_visit_processor.py").read_text()
    processor_nodes = {
        node.name: node
        for node in ast.parse(processor_source).body
        if isinstance(node, ast.FunctionDef)
    }
    processor = processor_nodes["cutout_mosaic"]
    writes = {}
    for node in ast.walk(processor):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "writeto" or not node.args:
            continue
        name_expression = ast.get_source_segment(processor_source, node.args[0])
        for kind in ("wht", "var"):
            if f"_{kind}.fits" in name_expression:
                data = next((k.value for k in node.keywords if k.arg == "data"), None)
                if isinstance(data, ast.Name):
                    writes[kind] = data.id
    if writes != {"wht": "outwht", "var": "outvar"}:
        raise ValueError("Unexpected public cutout weight/variance export mapping")
    tile_source = (directory / "grizli_aws_tile_mosaic.py").read_text()
    tile_nodes = {
        node.name: node for node in ast.parse(tile_source).body if isinstance(node, ast.FunctionDef)
    }
    build = tile_nodes["build_mosaic_from_subregions"]
    build_text = ast.get_source_segment(tile_source, build)
    if not all(
        token in build_text
        for token in (
            "llh['NDRIZIM'] = len(exposures)",
            "llh[f'FLT{j+1:05d}'] = exp",
            "llh[k] = im[0].header[k]",
        )
    ):
        raise ValueError("Unexpected released subtile header inheritance")
    return {
        "public_release": "1.12.10",
        "public_tag_commit": tag["object"]["sha"],
        "functions_line_ranges": {
            name: [nodes[name].lineno, nodes[name].end_lineno]
            for name in ("drizzle_from_visit", "drizzle_array_groups")
        },
        "released_cutout_mosaic_export_arrays": writes,
        "released_subtile_header_policy": (
            "Unique FLT contributor list is rebuilt across tiles; remaining header "
            "cards are copied from the last loaded tile, not a per-pixel global table"
        ),
        "extra_functions_line_ranges": {
            "cutout_mosaic": [processor.lineno, processor.end_lineno],
            "build_mosaic_from_subregions": [build.lineno, build.end_lineno],
        },
        "export_semantics_scope": (
            "Released subtile pipeline distinguishes combining WHT from full ERR VAR; "
            "the production thumb handler and exact deployed code are not certified"
        ),
        "observed_source_contract": [
            (
                "jwst_var defaults to local read-noise variance plus median Poisson "
                "variance for combining weights"
            ),
            "full input ERR-squared variance is separately propagated",
            "WHTnnnnn header stores scalar median exposure weight, not a pixel contribution matrix",
        ],
        "scope": (
            "Release-tag source matches logged version; exact production commit/custom "
            "modifications not certified"
        ),
    }


def probe_variance_products(directory: Path) -> dict:
    """Bound public hypotheses using HEAD and at most 4096 response bytes.

    A missing guessed URL is not evidence of global public unavailability.
    No complete association image is acquired, even if Range is ignored.
    """
    html = (directory / "dja_center_assoc_mosaics.html").read_text()
    links = re.findall(r'href="(https://s3[^" ]+_sci.fits.gz)"', html)
    normal = [link for link in links if "grism" not in link]
    if not normal:
        raise ValueError("No normal-imaging association SCI URL in pinned API table")
    variance = normal[0].replace("_sci.fits.gz", "_var.fits.gz")
    thumb = (
        "https://grizli-cutout.herokuapp.com/thumb?ra=53.120000&dec=-27.810000"
        "&filters=f444w-clear&size=2&output="
    )
    hypotheses = [
        ("association-variance-gzip-sibling", variance),
        ("association-variance-uncompressed-sibling", variance.removesuffix(".gz")),
        ("undocumented-thumb-fits_var", thumb + "fits_var"),
        ("undocumented-thumb-fits_variance", thumb + "fits_variance"),
    ]
    records, downloaded = [], 0
    for label, url in hypotheses:
        record = {"hypothesis": label, "url": url, "requests": []}
        for method in ("HEAD", "GET"):
            headers = {"User-Agent": "jwst-science-bounded-variance-audit/1"}
            if method == "GET":
                headers["Range"] = "bytes=0-4095"
            request = Request(url, headers=headers, method=method)
            try:
                response = urlopen(request, timeout=30)
            except HTTPError as error:
                response = error
            except (URLError, TimeoutError) as error:
                record["requests"].append({"method": method, "error": str(error)})
                continue
            with response:
                raw = response.read(4096) if method == "GET" else b""
                downloaded += len(raw)
                entry = {
                    "method": method,
                    "status": response.status,
                    "content_type": response.headers.get("Content-Type"),
                    "content_length": response.headers.get("Content-Length"),
                    "content_range": response.headers.get("Content-Range"),
                    "etag": response.headers.get("ETag"),
                    "acquired_body_bytes": len(raw),
                    "body_prefix_sha256": hashlib.sha256(raw).hexdigest(),
                    "prefix_hex": raw[:80].hex(),
                }
                if raw.startswith(b"\x1f\x8b"):
                    try:
                        unpacked = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(raw, 2880)
                        entry["decompressed_first_cards"] = [
                            unpacked[i : i + 80].decode("ascii", errors="replace")
                            for i in range(0, min(len(unpacked), 800), 80)
                        ]
                    except zlib.error:
                        entry["gzip_prefix_decode"] = "incomplete/invalid bounded prefix"
                record["requests"].append(entry)
        records.append(record)
    result = {
        "schema_version": 1,
        "bounded_probe_cap_body_bytes": 4 * 4096,
        "actual_acquired_body_bytes": downloaded,
        "association_sci_url_from_pinned_api_table": normal[0],
        "records": records,
        "scope": (
            "Guessed sibling/undocumented output flags tested by HEAD plus bounded "
            "prefix only; failure is not evidence that all public variance products "
            "are unavailable. No full image/map acquired."
        ),
    }
    result["result_content_sha256"] = json_hash(result)
    return result


def audit(directory: Path, image_directory: Path) -> dict:
    receipt = acquire(directory)
    source = inspect_release_sources(directory)
    rows = list(csv.DictReader((directory / "dja_exposures_center.csv").open()))
    images = []
    for product in json.loads(IMAGE_MANIFEST.read_text())["products"]:
        path = image_directory / product["filename"]
        raw = path.read_bytes()
        if (
            len(raw) != product["expected_bytes"]
            or hashlib.sha256(raw).hexdigest() != product["sha256"]
        ):
            raise ValueError("Actual selection image differs from original pilot pins")
        with fits.open(path, memmap=False) as hdul:
            header = hdul[0].header
            weight_plane = np.asarray(hdul[1].data, float)
            valid_weight = np.isfinite(weight_plane) & (weight_plane > 0)
            # Publisher inverse weight in calibrated 10-nJy units; not certified full ERR.
            current_variance = 100.0 / weight_plane[valid_weight]
            names = [str(header[k]) for k in header if k.startswith("FLT")]
            native_ids = {name.removesuffix("_rate.fits") for name in names}
            current = [
                r
                for r in rows
                if r["file"] in native_ids and r["filter"] == product["filter"] + "-CLEAR"
            ]
            by_file = {r["file"]: r for r in current}
            if len(current) != len(by_file):
                raise ValueError(
                    "Current exposure-query duplicate identity needs an explicit policy"
                )
            native_scalars = {
                k: header.get(k)
                for k in (
                    "FILTER",
                    "BUNIT",
                    "NDRIZIM",
                    "EXPTIME",
                    "WHTTYPE",
                    "RNPERC",
                    "GRIZLIV",
                    "PHOTFNU",
                    "OPHOTFNU",
                    "PHOTMJSR",
                    "PIXAR_SR",
                    "PSCALER",
                    "DRIZKERN",
                    "DRIZPIXF",
                    "R_PHOTOM",
                    "R_FLAT",
                    "R_DISTOR",
                    "UPDA_CTX",
                )
            }
            map_names = [f"{h.name}/{h.header.get('EXTVER', '')}" for h in hdul]
            weight_keys = [k for k in header if k.startswith("WHT") and k != "WHTTYPE"]
            images.append(
                {
                    "filename": path.name,
                    "sha256": product["sha256"],
                    "native_summary_headers": native_scalars,
                    "publisher_inverse_weight_njy2_quantiles": {
                        label: float(value)
                        for label, value in zip(
                            ("minimum", "p05", "median", "p95", "maximum"),
                            np.quantile(current_variance, [0, 0.05, 0.5, 0.95, 1]),
                        )
                    },
                    "existing_scene_component_bound": (
                        "Only IF this WHT is proven full-ERR inverse variance and "
                        "noise components are independent/nonnegative, current pixel "
                        "source variance lies between zero and 100/WHT; this is not "
                        "a bound for new injected sources or signed aperture covariance"
                    ),
                    "exported_planes": map_names,
                    "contributor_names": names,
                    "unique_contributor_count": len(native_ids),
                    "scalar_median_weight_header_count": len(weight_keys),
                    "center_query_matching_contributor_count": len(current),
                    "center_query_geometric_exptime_sum_s": sum(
                        float(r["exptime"]) for r in current
                    ),
                    "center_query_detectors": sorted({r["detector"] for r in current}),
                    "center_query_scope": (
                        "Current API footprints near the one query center, not per-pixel "
                        "valid/DQ/Poisson-weighted exposure or unchanged historical release"
                    ),
                    "missing_exported_maps": [
                        "per-contributor native gain/time/variance/calibration maps",
                        "separate propagated full-ERR VAR plane or certified WHT mapping",
                        "per-contributor DQ masks and exact distortion/registration transforms",
                        "local coaddition weights and native-to-output overlap coefficients",
                        "context/exposure planes with per-contributor local identity",
                    ],
                }
            )
    plan = json.loads((ROOT / "research_output/selection_pilot_plan.json").read_text())
    response = json.loads((ROOT / "research_output/selection_pilot_response.json").read_text())
    class_audit = {
        "actual_unmasked_scene_sites": len(plan["sites"]),
        "simulated_trials": response["trials"],
        "observed_null_centroid_matches": sum(
            r["centroid_status"] == "matched" for r in response["null_site_controls"]
        ),
        "observed_null_joint_red_passes": sum(
            r["selected_red"] for r in response["null_site_controls"]
        ),
        "verified_actual_star_labels_in_uniform_pilot": 0,
        "verified_actual_faint_galaxy_labels_in_uniform_pilot": 0,
        "verified_actual_high_redshift_labels_in_uniform_pilot": 0,
        "verified_actual_blend_labels_in_uniform_pilot": 0,
        "astronomical_contamination_numerator": None,
        "astronomical_contamination_denominator": None,
        "morphology_labels": (
            "Prescribed modeled point/extended/pair, not independent astronomical identities"
        ),
        "color_labels": (
            "Prescribed three flux-ratio triples; do not identify stars, dusty/nebular "
            "galaxies or high-z sources"
        ),
        "identified_contamination_fraction_if_real_selected_sample_had_only_unknown_labels": [
            0.0,
            1.0,
        ],
        "missing_class_control_domains": [
            "independently labelled faint galaxies spanning intrinsic SED/morphology/redshift",
            "empirically identified stars and broader atmosphere/SED families",
            "labelled realistic blends/background structures and association failures",
            "visit/field-disjoint controls, volume/depth coverage and population sampling weights",
        ],
    }
    result = {
        "schema_version": 1,
        "preregistered_plan_sha256": hashlib.sha256(
            (ROOT / "research_output/selection_count_audit_plan.json").read_bytes()
        ).hexdigest(),
        "acquisition": receipt,
        "release_source_inspection": source,
        "public_variance_probes": json.loads(
            (ROOT / "research_output/selection_variance_public_probes.json").read_text()
        ),
        "public_variance_access_status": (
            "A current F444W association VAR.gz is accessible by HEAD and bounded "
            "Range, 43219789 bytes full product; not acquired. Two guessed small "
            "thumb VAR flags returned PNG, not variance. No global availability "
            "claim follows from guessed flag failures."
        ),
        "separate_var_information_scope": (
            "An identified same-operator full ERR VAR diagonal could bound an "
            "existing pixel source component between zero and VAR under independent "
            "nonnegative components; it cannot isolate a new source increment or "
            "native-output off-diagonal covariance. Current association product is "
            "not the exact historical multi-association selection cutout operator."
        ),
        "current_exposure_query_rows": len(rows),
        "images": images,
        "calibrated_coadd_nonidentifiability": coadd_nonidentifiability(),
        "representative_class_denominators": class_audit,
        "physical_source_poisson_status": (
            "Not identified from current exported cutout contract; native inputs are "
            "public followup work, not inaccessible author data"
        ),
        "unconditional_numeric_variance_bound_from_exported_contract": (
            "nonnegative; no finite numeric upper bound supplied without per-input "
            "count-conversion constraints"
        ),
        "supported_conditional_bound": (
            "For known positive c_i and nonnegative normalized scalar weights: "
            "F/sum(c_i) <= Var_source <= F/min(c_i); not a signed aperture/drizzle "
            "covariance bound"
        ),
        "stopping_decision": (
            "No calibrated count transport or physical uncertainty can be recovered "
            "exactly in this metadata-only round; no rerun or expanded assumed-gain "
            "grid"
        ),
        "next_accessible_reduction": (
            "Recover bounded native RATE/CAL pixels, per-input gain/Poisson/ramp "
            "variance and local DQ/calibration; rebuild input WCS/pixfrac/kernel and "
            "per-pixel weights. Exposure-map time alone cannot reconstruct squared "
            "weights or source-photon cross-covariance."
        ),
    }
    result["result_content_sha256"] = json_hash(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("acquire", "audit", "probe"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--image-input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "acquire":
        print(json.dumps(acquire(args.input), indent=2))
        return
    if args.command == "probe":
        if args.output is None:
            parser.error("probe requires --output")
        args.output.write_text(json.dumps(probe_variance_products(args.input), indent=2) + "\n")
        return
    if args.image_input is None or args.output is None:
        parser.error("audit requires --image-input and --output")
    args.output.write_text(json.dumps(audit(args.input, args.image_input), indent=2) + "\n")


if __name__ == "__main__":
    main()
