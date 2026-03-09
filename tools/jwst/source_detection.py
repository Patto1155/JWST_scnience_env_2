"""Source detection tools for JWST mosaics."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from astropy.stats import sigma_clipped_stats
from photutils.segmentation import SourceCatalog, deblend_sources, detect_sources as photutils_detect_sources

from tools.jwst.fits_loader import load_fits_bundle


def _sanitize_name(value: str) -> str:
    """Convert arbitrary values into filesystem-safe output prefixes."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "jwst"


def _json_ready(value: Any) -> Any:
    """Convert numpy-heavy structures into JSON-safe values."""
    if isinstance(value, dict):
        return {key: _json_ready(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return value


def _normalize_image_for_display(
    image: np.ndarray,
    valid_mask: np.ndarray,
    lower_pct: float = 1.0,
    upper_pct: float = 99.5,
) -> np.ndarray:
    """Create an asinh-stretched display image using valid pixels only."""
    valid_values = image[valid_mask]
    if valid_values.size == 0:
        return np.zeros_like(image, dtype=float)

    vmin = float(np.nanpercentile(valid_values, lower_pct))
    vmax = float(np.nanpercentile(valid_values, upper_pct))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        vmax = vmin + 1.0

    clipped = np.clip(np.where(valid_mask, image, vmin), vmin, vmax)
    scaled = (clipped - vmin) / (vmax - vmin)
    return np.arcsinh(10.0 * scaled) / np.arcsinh(10.0)


def detect_sources(
    image_data: Any,
    threshold_sigma: float = 3.0,
    min_pixels: int = 9,
    deblend: bool = True,
    top_n: int = 50,
    border_margin: int = 16,
    output_dir: str = "catalogs",
    output_prefix: Optional[str] = None,
    strict_data: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Detect and rank sources in a JWST image using source segmentation.

    The output catalog is JSON so coding agents can inspect and reuse it across
    runs without reparsing binary tables.
    """
    del strict_data  # strictness is enforced by the sandbox calling conventions

    if not isinstance(image_data, str):
        raise ValueError("detect_sources requires a registered dataset name")

    bundle = load_fits_bundle(image_data)
    image = np.asarray(bundle["sci"], dtype=float)
    valid_mask = np.asarray(bundle["validity_mask"], dtype=bool)

    valid_values = image[valid_mask]
    if valid_values.size == 0:
        raise ValueError(f"No valid science pixels available for {image_data}")

    _, median, std = sigma_clipped_stats(valid_values, sigma=3.0)
    if not np.isfinite(std) or std <= 0:
        raise ValueError(f"Image standard deviation is invalid for {image_data}")

    detection_image = np.where(valid_mask, image - median, 0.0)
    threshold = float(threshold_sigma * std)
    segmentation = photutils_detect_sources(
        detection_image,
        threshold=threshold,
        npixels=max(int(min_pixels), 1),
        mask=~valid_mask,
    )

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    prefix = output_prefix or _sanitize_name(image_data)
    catalog_path = output_root / f"{prefix}_catalog.json"
    overlay_path = output_root / f"{prefix}_segmentation.png"

    if catalog_path.exists() and overlay_path.exists():
        cached = json.loads(catalog_path.read_text(encoding="utf-8"))
        if (
            cached.get("dataset_name") == image_data
            and float(cached.get("threshold_sigma", -1.0)) == float(threshold_sigma)
            and int(cached.get("min_pixels", -1)) == int(min_pixels)
            and int(cached.get("border_margin", -1)) == int(border_margin)
            and bool(cached.get("deblend", True)) == bool(deblend)
        ):
            sources = list(cached.get("sources", []))
            return {
                "source_count": int(cached.get("source_count", len(sources))),
                "catalog_path": str(catalog_path),
                "segmentation_overlay_path": str(overlay_path),
                "top_sources": sources[: max(int(top_n), 0)],
                "artifacts": [
                    {"path": str(catalog_path), "kind": "catalog"},
                    {"path": str(overlay_path), "kind": "segmentation_overlay"},
                ],
                "cache_hit": True,
            }

    if segmentation is None:
        payload = {
            "dataset_name": image_data,
            "file_path": bundle["file_path"],
            "threshold_sigma": float(threshold_sigma),
            "min_pixels": int(min_pixels),
            "border_margin": int(border_margin),
            "deblend": bool(deblend),
            "source_count": 0,
            "sources": [],
        }
        catalog_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        fig, ax = plt.subplots(figsize=(8, 8))
        ax.imshow(_normalize_image_for_display(image, valid_mask), cmap="gray", origin="lower")
        ax.set_title(f"{image_data} segmentation (0 sources)")
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        fig.tight_layout()
        fig.savefig(overlay_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

        return {
            "source_count": 0,
            "catalog_path": str(catalog_path),
            "segmentation_overlay_path": str(overlay_path),
            "top_sources": [],
            "artifacts": [
                {"path": str(catalog_path), "kind": "catalog"},
                {"path": str(overlay_path), "kind": "segmentation_overlay"},
            ],
        }

    if deblend:
        segmentation = deblend_sources(
            detection_image,
            segmentation,
            npixels=max(int(min_pixels), 1),
            progress_bar=False,
        )

    catalog = SourceCatalog(detection_image, segmentation, mask=~valid_mask)

    sources: List[Dict[str, Any]] = []
    height, width = image.shape
    for source in catalog:
        source_id = int(source.label)
        x = float(source.xcentroid)
        y = float(source.ycentroid)
        edge_distance_px = float(min(x, y, width - 1 - x, height - 1 - y))
        if edge_distance_px < border_margin:
            continue

        source_mask = segmentation.data == source_id
        source_valid = source_mask & valid_mask
        if not np.any(source_valid):
            continue

        flux_proxy_raw = getattr(source.segment_flux, "value", source.segment_flux)
        area_raw = getattr(source.area, "value", source.area)
        ra = None
        dec = None
        if bundle["wcs"] is not None:
            try:
                ra, dec = bundle["wcs"].pixel_to_world_values(x, y)
                ra = float(ra)
                dec = float(dec)
            except Exception:
                ra = None
                dec = None

        sources.append(
            {
                "source_id": source_id,
                "x": x,
                "y": y,
                "ra": ra,
                "dec": dec,
                "flux_proxy": float(flux_proxy_raw),
                "area": float(area_raw),
                "coverage_fraction": float(np.sum(source_valid) / np.sum(source_mask)),
                "edge_distance_px": edge_distance_px,
            }
        )

    sources.sort(key=lambda item: item["flux_proxy"], reverse=True)
    top_sources = sources[: max(int(top_n), 0)]

    payload = {
        "dataset_name": image_data,
        "file_path": bundle["file_path"],
        "filter": bundle.get("filter"),
        "target": bundle.get("target"),
        "instrument": bundle.get("instrument"),
        "threshold_sigma": float(threshold_sigma),
        "min_pixels": int(min_pixels),
        "border_margin": int(border_margin),
        "deblend": bool(deblend),
        "source_count": len(sources),
        "sources": sources,
    }
    catalog_path.write_text(json.dumps(_json_ready(payload), indent=2), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(_normalize_image_for_display(image, valid_mask), cmap="gray", origin="lower")
    segmentation_overlay = np.ma.masked_where(segmentation.data <= 0, segmentation.data)
    ax.imshow(segmentation_overlay, cmap="nipy_spectral", origin="lower", alpha=0.35)
    if sources:
        xs = [item["x"] for item in sources]
        ys = [item["y"] for item in sources]
        ax.scatter(xs, ys, s=10, c="white", linewidths=0.3, edgecolors="black")
    ax.set_title(f"{image_data} segmentation ({len(sources)} sources)")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    fig.tight_layout()
    fig.savefig(overlay_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return {
        "source_count": len(sources),
        "catalog_path": str(catalog_path),
        "segmentation_overlay_path": str(overlay_path),
        "top_sources": top_sources,
        "artifacts": [
            {"path": str(catalog_path), "kind": "catalog"},
            {"path": str(overlay_path), "kind": "segmentation_overlay"},
        ],
        "cache_hit": False,
    }
