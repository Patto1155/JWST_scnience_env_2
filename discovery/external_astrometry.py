"""Reproduce original-image readiness, external astrometry and relative frames."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data_pipeline.original_images import file_sha256, verify_image
from tools.jwst.astrometry import detect_centroids, external_astrometry, reference_sources
from tools.jwst.fits_loader import load_fits_bundle

REFERENCE_SHA256 = "4b588479eb9ebbfd590dd6ea0ea85949f80952e085ea94e874a191d558f4accf"


def run(manifest_path: Path, image_dir: Path, references_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text())
    if file_sha256(references_path) != REFERENCE_SHA256:
        raise ValueError("released reference-coordinate CSV checksum mismatch")
    references = reference_sources(references_path)
    images = []
    by_filter = {}
    for product in manifest["images"]:
        path = image_dir / product["product_filename"]
        ready = verify_image(path, product)
        bundle = load_fits_bundle(str(path.resolve()))
        result = external_astrometry(bundle, references)
        images.append(
            {
                "product_filename": product["product_filename"],
                "filter": product["filter"],
                "sha256": product["sha256"],
                "readiness": ready,
                "external_astrometry": result,
            }
        )
        if product["filter"] in {"F444W", "F090W", "F200W"}:
            by_filter[product["filter"]] = bundle
    relative = []
    if "F444W" in by_filter:
        reference_bundle = by_filter["F444W"]
        pixels = detect_centroids(reference_bundle)
        sky = reference_bundle["wcs"].pixel_to_world(pixels[:, 0], pixels[:, 1])
        secondary = [
            {"id": f"F444W_centroid_{i}", "ra": p.ra.deg, "dec": p.dec.deg}
            for i, p in enumerate(sky)
        ]
        for filt in ("F090W", "F200W"):
            if filt not in by_filter:
                continue
            result = external_astrometry(by_filter[filt], secondary)
            result["interpretation"] = "secondary_image_centroid_cross_band_registration"
            result["limitations"] = [
                "Reference is F444W image centroids; this is not a second external catalog.",
                "Color gradients and blended-source changes contribute to centroid differences.",
                "Bootstrap intervals omit shared-image and image-wide systematic errors.",
                "No measured offset was fitted then applied to the images.",
            ]
            relative.append({"filter": filt, "reference_filter": "F444W", **result})
    return {
        "schema_version": 1,
        "complete_original_archive": False,
        "reference_catalog": {
            "sha256": REFERENCE_SHA256,
            "source_url": "https://jades.herts.ac.uk/DR4/Combined_DR4_external_v1.2.1.fits",
            "unique_AB_GS_reference_sources": len(references),
        },
        "original_product_manifest_sha256": file_sha256(manifest_path),
        "images": images,
        "cross_band_registration": relative,
        "claim": "recovered original science images and measured external-frame consistency",
        "not_established": [
            "new galaxies",
            "Gaia-level absolute frame certification",
            "historical artifact-rate reproduction",
            "full archive coverage",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data_sources/original_images.json"))
    parser.add_argument("--image-dir", type=Path, default=Path("data/original_round2"))
    parser.add_argument(
        "--references", type=Path, default=Path("data_sources/pilot/jades_dr4_reference.csv")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("research_output/original_image_astrometry.json")
    )
    args = parser.parse_args()
    payload = run(args.manifest, args.image_dir, args.references)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    for row in payload["images"]:
        metrics = row["external_astrometry"]
        print(
            row["filter"],
            row["product_filename"],
            metrics["matched_sources"],
            metrics["sample_status"],
            metrics.get("radial_median_arcsec"),
        )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
