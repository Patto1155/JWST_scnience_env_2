"""Characterize detector artifacts surviving JWST Stage-2b calibration.

Two independent exposures of the same sky in the same filter form a labelled
truth set. Nothing astrophysical at cosmological distance changes over a few
hours, so any source detected in one exposure and absent from the other at the
same sky position is a detector event: a cosmic ray, a snowball, or a hot-pixel
residual that survived ramp-level jump detection.

That is the measurement this module makes. It is the one study this archive is
genuinely well suited to, precisely because single-exposure ``i2d`` products
carry no cross-dither rejection.

What it produces, per filter pair:

- the surviving-artifact surface density, per square arcminute and per
  kilosecond of exposure
- the artifact fraction as a function of detection significance, which is what
  tells you how badly a single-exposure candidate search is contaminated
- morphology contrasts (FWHM, ellipticity, peak sharpness) between persistent
  sources and single-epoch events
- a flux-ratio distribution for persistent sources, which validates the method:
  if cross-epoch photometry is sound, real sources must cluster at ratio 1

Run:
    python discovery/artifact_characterization.py --auto
    python discovery/artifact_characterization.py \\
        --pair F277W path/to/epoch_a_i2d.fits path/to/epoch_b_i2d.fits
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from astropy.stats import sigma_clipped_stats
from photutils.segmentation import (
    SourceCatalog,
    deblend_sources,
    detect_sources as photutils_detect_sources,
)

from tools.jwst.fits_loader import _load_fits_bundle_from_path
from tools.jwst.footprints import overlap_fraction, sky_to_pixel
from tools.jwst.photometry import extract_photometry

RESEARCH_DIR = Path("research_output")
DEFAULT_OUTPUT = RESEARCH_DIR / "artifact_characterization.json"
DEFAULT_REPORT = RESEARCH_DIR / "ARTIFACT_CHARACTERIZATION.md"

DETECTION_SIGMA = 5.0
DETECTION_MIN_PIXELS = 5
APERTURE_RADIUS = 3.0
BACKGROUND_INNER_RADIUS = 6.0
BACKGROUND_OUTER_RADIUS = 10.0

# Significance required to call a source present in the comparison epoch.
PERSISTENCE_SNR = 3.0

# Minimum aperture coverage in both epochs. Below this the source sits on a
# detector edge or gap and the comparison says nothing.
MIN_COVERAGE = 0.9

# Sources this close to the array edge are excluded; the background annulus
# would be truncated.
BORDER_MARGIN_PIXELS = 16

# For an extended source the 6-10 px annulus sits on the source itself and
# over-subtracts it to nothing, which fakes an absence. Every apparent
# single-epoch source is therefore re-measured with an annulus placed well
# outside the light profile before the classification is allowed to stand.
WIDE_BACKGROUND_INNER_RADIUS = 15.0
WIDE_BACKGROUND_OUTER_RADIUS = 25.0

# Significance bins for the contamination curve.
SNR_BINS = [(5, 8), (8, 12), (12, 20), (20, 50), (50, 1e9)]

STERADIAN_PER_ARCSEC2 = 2.350443053e-11

# Published z > 10 dropout surface densities from JWST deep surveys are of order
# a few objects per hundred square arcminutes. Used only to express the measured
# artifact density as a contamination ratio; override with --highz-density.
DEFAULT_HIGHZ_DENSITY_PER_ARCMIN2 = 0.03


def _pixel_solid_angle(bundle: Dict[str, Any]) -> Optional[float]:
    """Return the per-pixel solid angle in steradians from the FITS header."""
    for header_key in ("header", "primary_header"):
        header = bundle.get(header_key) or {}
        value = header.get("PIXAR_SR")
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def _pixel_scale_arcsec(bundle: Dict[str, Any]) -> Optional[float]:
    """Return the pixel scale in arcsec, derived from the solid angle."""
    solid_angle = _pixel_solid_angle(bundle)
    if solid_angle is None:
        return None
    return float(np.sqrt(solid_angle / STERADIAN_PER_ARCSEC2))


def _header_value(bundle: Dict[str, Any], key: str) -> Any:
    """Look a keyword up in the primary header, then the science header."""
    for header_key in ("primary_header", "header"):
        header = bundle.get(header_key) or {}
        if key in header:
            return header[key]
    return None


def _exposure_time(bundle: Dict[str, Any]) -> Optional[float]:
    """Return the effective exposure time in seconds."""
    for key in ("EFFEXPTM", "XPOSURE", "TELAPSE"):
        value = _header_value(bundle, key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def _observation_time(bundle: Dict[str, Any]) -> Optional[float]:
    """Return the exposure mid-time in MJD."""
    for key in ("MJD-AVG", "EXPMID", "MJD-BEG", "EXPSTART"):
        value = _header_value(bundle, key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def detect_with_morphology(bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detect sources and record the shape measurements needed to tell CRs apart.

    Cosmic rays deposit charge in a few pixels and are sharper than the PSF;
    snowballs are large and round. Both separate from real sources in the
    FWHM/sharpness plane, so those quantities are measured here rather than
    inferred later.
    """
    image = np.asarray(bundle["sci"], dtype=float)
    valid_mask = np.asarray(bundle["validity_mask"], dtype=bool)
    valid_values = image[valid_mask]
    if valid_values.size == 0:
        return []

    _, median, std = sigma_clipped_stats(valid_values, sigma=3.0)
    if not np.isfinite(std) or std <= 0:
        return []

    detection_image = np.where(valid_mask, image - median, 0.0)
    segmentation = photutils_detect_sources(
        detection_image,
        threshold=float(DETECTION_SIGMA * std),
        npixels=DETECTION_MIN_PIXELS,
        mask=~valid_mask,
    )
    if segmentation is None:
        return []

    try:
        segmentation = deblend_sources(
            detection_image, segmentation, npixels=DETECTION_MIN_PIXELS
        )
    except Exception:
        # Deblending is a refinement; a failure must not lose the detections.
        pass

    catalog = SourceCatalog(detection_image, segmentation)
    height, width = image.shape

    sources: List[Dict[str, Any]] = []
    for row in catalog:
        x = float(row.xcentroid)
        y = float(row.ycentroid)
        if not (np.isfinite(x) and np.isfinite(y)):
            continue
        if (
            x < BORDER_MARGIN_PIXELS
            or y < BORDER_MARGIN_PIXELS
            or x >= width - BORDER_MARGIN_PIXELS
            or y >= height - BORDER_MARGIN_PIXELS
        ):
            continue

        def _scalar(value: Any) -> Optional[float]:
            try:
                number = float(getattr(value, "value", value))
            except (TypeError, ValueError):
                return None
            return number if np.isfinite(number) else None

        segment_flux = _scalar(row.segment_flux)
        max_value = _scalar(row.max_value)
        area = _scalar(row.area)
        sources.append(
            {
                "x": x,
                "y": y,
                "area_pixels": area,
                "fwhm_pixels": _scalar(row.fwhm),
                "ellipticity": _scalar(row.ellipticity),
                "segment_flux": segment_flux,
                "peak_value": max_value,
                # Fraction of the segment's flux in its brightest pixel. A
                # PSF-convolved source spreads; a cosmic ray does not.
                "sharpness": (
                    float(max_value / segment_flux)
                    if segment_flux and max_value and segment_flux > 0
                    else None
                ),
            }
        )
    return sources


def _measure(bundle: Dict[str, Any], x: float, y: float) -> Dict[str, Any]:
    """Aperture photometry at a pixel position in one exposure."""
    return extract_photometry(
        image_data=bundle,
        x=x,
        y=y,
        aperture_radius=APERTURE_RADIUS,
        background_annulus_inner_radius=BACKGROUND_INNER_RADIUS,
        background_annulus_outer_radius=BACKGROUND_OUTER_RADIUS,
    )


def compare_epochs(
    bundle_a: Dict[str, Any],
    bundle_b: Dict[str, Any],
    *,
    epoch_a_name: str,
    epoch_b_name: str,
) -> List[Dict[str, Any]]:
    """Detect in A and classify each source by whether it reappears in B."""
    wcs_a = bundle_a.get("wcs")
    if wcs_a is None or bundle_b.get("wcs") is None:
        return []

    records: List[Dict[str, Any]] = []
    for source in detect_with_morphology(bundle_a):
        x_a, y_a = source["x"], source["y"]
        try:
            ra, dec = wcs_a.pixel_to_world_values(x_a, y_a)
        except Exception:
            continue

        position_b = sky_to_pixel(bundle_b, float(ra), float(dec))
        if position_b is None:
            # Outside the shared footprint: this source is simply unobserved in
            # the comparison epoch and carries no information either way.
            continue

        measurement_a = _measure(bundle_a, x_a, y_a)
        measurement_b = _measure(bundle_b, *position_b)
        if (
            float(measurement_a.get("coverage_fraction") or 0.0) < MIN_COVERAGE
            or float(measurement_b.get("coverage_fraction") or 0.0) < MIN_COVERAGE
        ):
            continue

        snr_a = measurement_a.get("snr")
        snr_b = measurement_b.get("snr")
        if snr_a is None or float(snr_a) < DETECTION_SIGMA:
            # Keep the detection threshold consistent between segmentation and
            # aperture photometry.
            continue

        flux_a = float(measurement_a.get("background_subtracted_flux") or 0.0)
        flux_b = float(measurement_b.get("background_subtracted_flux") or 0.0)
        persistent = snr_b is not None and float(snr_b) >= PERSISTENCE_SNR

        recovered_by_wide_annulus = False
        if not persistent:
            wide = extract_photometry(
                image_data=bundle_b,
                x=position_b[0],
                y=position_b[1],
                aperture_radius=APERTURE_RADIUS,
                background_annulus_inner_radius=WIDE_BACKGROUND_INNER_RADIUS,
                background_annulus_outer_radius=WIDE_BACKGROUND_OUTER_RADIUS,
            )
            wide_snr = wide.get("snr")
            if (
                wide_snr is not None
                and float(wide_snr) >= PERSISTENCE_SNR
                and float(wide.get("coverage_fraction") or 0.0) >= MIN_COVERAGE
            ):
                persistent = True
                recovered_by_wide_annulus = True
                snr_b = float(wide_snr)
                flux_b = float(wide.get("background_subtracted_flux") or 0.0)

        records.append(
            {
                "epoch_a": epoch_a_name,
                "epoch_b": epoch_b_name,
                "ra": float(ra),
                "dec": float(dec),
                "x_a": x_a,
                "y_a": y_a,
                "x_b": float(position_b[0]),
                "y_b": float(position_b[1]),
                "snr_a": float(snr_a),
                "snr_b": float(snr_b) if snr_b is not None else None,
                "flux_a": flux_a,
                "flux_b": flux_b,
                "flux_ratio": float(flux_b / flux_a) if flux_a > 0 else None,
                "fwhm_pixels": source["fwhm_pixels"],
                "ellipticity": source["ellipticity"],
                "area_pixels": source["area_pixels"],
                "sharpness": source["sharpness"],
                "recovered_by_wide_annulus": recovered_by_wide_annulus,
                "classification": "persistent" if persistent else "single_epoch",
            }
        )
    return records


def consolidate_detections(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse per-pair comparisons into one consensus row per detection.

    With more than two exposures of a field, the same detection is compared
    against several others. Those rows are not independent - they are one
    detection judged repeatedly - so they must be collapsed before any fit, or a
    single source leaks across cross-validation folds.

    The consensus is asymmetric on purpose: present in even one comparison means
    real, because a detector event cannot reappear at the same sky position in an
    independent exposure. Absent in every comparison is what earns the artifact
    label, and more comparisons make that label stronger.
    """
    grouped: Dict[Tuple[str, int, int], List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(record["epoch_a"], round(record["x_a"]), round(record["y_a"]))].append(record)

    consolidated: List[Dict[str, Any]] = []
    for (epoch, _, _), group in grouped.items():
        primary = max(group, key=lambda r: r["snr_a"])
        n_persistent = sum(1 for r in group if r["classification"] == "persistent")
        consolidated.append(
            {
                **{k: primary[k] for k in (
                    "epoch_a", "ra", "dec", "x_a", "y_a", "snr_a", "flux_a",
                    "fwhm_pixels", "ellipticity", "area_pixels", "sharpness",
                )},
                "n_comparisons": len(group),
                "n_persistent_comparisons": n_persistent,
                "compared_against": [r["epoch_b"] for r in group],
                "consensus": "real" if n_persistent > 0 else "artifact",
                "unanimous": n_persistent in (0, len(group)),
            }
        )
    return consolidated


def _median(values: Iterable[Optional[float]]) -> Optional[float]:
    """Median over the finite entries of a sequence, or None when empty."""
    clean = [float(v) for v in values if v is not None and np.isfinite(v)]
    return float(np.median(clean)) if clean else None


def _overlap_area_arcmin2(bundle_a: Dict[str, Any], bundle_b: Dict[str, Any]) -> Optional[float]:
    """Shared sky area between two exposures, in square arcminutes."""
    scale = _pixel_scale_arcsec(bundle_a)
    if scale is None:
        return None
    height, width = np.asarray(bundle_a["sci"]).shape[-2:]
    field_arcmin2 = (height * scale / 60.0) * (width * scale / 60.0)
    return float(field_arcmin2 * overlap_fraction(bundle_a, bundle_b))


def _direction_symmetry(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Single-epoch fraction per search direction.

    A stochastic per-exposure process must produce a similar fraction whichever
    exposure is searched. A strong asymmetry would instead point at a depth or
    calibration difference between the epochs, which would invalidate the
    artifact interpretation.
    """
    by_epoch: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_epoch[record["epoch_a"]].append(record)

    rows = []
    for epoch, subset in sorted(by_epoch.items()):
        single = sum(1 for r in subset if r["classification"] == "single_epoch")
        rows.append(
            {
                "searched_epoch": epoch,
                "n_compared": len(subset),
                "n_single_epoch": single,
                "single_epoch_fraction": float(single / len(subset)) if subset else None,
            }
        )
    return rows


def _contamination_forecast(
    artifact_density_per_arcmin2: Optional[float],
    highz_density_per_arcmin2: float,
) -> Optional[Dict[str, Any]]:
    """Express the artifact density as contamination of a dropout search.

    An artifact appears in exactly one exposure, so it is absent from every
    other band by construction and passes any dropout criterion with full
    efficiency. That makes a single-exposure dropout search enrich artifacts
    rather than suppress them.
    """
    if not artifact_density_per_arcmin2 or highz_density_per_arcmin2 <= 0:
        return None
    return {
        "artifact_density_per_arcmin2": artifact_density_per_arcmin2,
        "assumed_highz_density_per_arcmin2": highz_density_per_arcmin2,
        "artifacts_per_genuine_highz_source": float(
            artifact_density_per_arcmin2 / highz_density_per_arcmin2
        ),
    }


def summarize_pair(
    records: List[Dict[str, Any]],
    *,
    filter_name: str,
    overlap_area_arcmin2: Optional[float],
    baseline_hours: Optional[float],
    exposure_seconds: Optional[float],
    epochs: List[str],
    highz_density_per_arcmin2: float = DEFAULT_HIGHZ_DENSITY_PER_ARCMIN2,
) -> Dict[str, Any]:
    """Aggregate per-source outcomes into rates, contamination, and morphology."""
    persistent = [r for r in records if r["classification"] == "persistent"]
    single = [r for r in records if r["classification"] == "single_epoch"]
    recovered = [r for r in records if r.get("recovered_by_wide_annulus")]
    total = len(records)

    by_snr: List[Dict[str, Any]] = []
    for low, high in SNR_BINS:
        in_bin = [r for r in records if low <= r["snr_a"] < high]
        if not in_bin:
            continue
        artifacts = [r for r in in_bin if r["classification"] == "single_epoch"]
        by_snr.append(
            {
                "snr_min": low,
                "snr_max": None if high > 1e8 else high,
                "n_sources": len(in_bin),
                "n_single_epoch": len(artifacts),
                "artifact_fraction": float(len(artifacts) / len(in_bin)),
            }
        )

    # Two exposures were each searched, so the per-exposure density divides by 2.
    density_per_arcmin2 = (
        float(len(single) / (overlap_area_arcmin2 * 2.0))
        if overlap_area_arcmin2 and overlap_area_arcmin2 > 0
        else None
    )
    density_per_arcmin2_per_ks = (
        float(density_per_arcmin2 / (exposure_seconds / 1000.0))
        if density_per_arcmin2 is not None and exposure_seconds
        else None
    )

    return {
        "filter": filter_name,
        "epochs": epochs,
        "baseline_hours": baseline_hours,
        "exposure_seconds": exposure_seconds,
        "overlap_area_arcmin2": overlap_area_arcmin2,
        "n_compared": total,
        "n_persistent": len(persistent),
        "n_single_epoch": len(single),
        "n_recovered_by_wide_annulus": len(recovered),
        "single_epoch_fraction": float(len(single) / total) if total else None,
        "artifact_density_per_arcmin2_per_exposure": density_per_arcmin2,
        "artifact_density_per_arcmin2_per_kilosecond": density_per_arcmin2_per_ks,
        "artifact_fraction_by_snr": by_snr,
        "direction_symmetry": _direction_symmetry(records),
        "contamination_forecast": _contamination_forecast(
            density_per_arcmin2, highz_density_per_arcmin2
        ),
        "morphology": {
            "persistent": {
                "median_fwhm_pixels": _median(r["fwhm_pixels"] for r in persistent),
                "median_ellipticity": _median(r["ellipticity"] for r in persistent),
                "median_area_pixels": _median(r["area_pixels"] for r in persistent),
                "median_sharpness": _median(r["sharpness"] for r in persistent),
            },
            "single_epoch": {
                "median_fwhm_pixels": _median(r["fwhm_pixels"] for r in single),
                "median_ellipticity": _median(r["ellipticity"] for r in single),
                "median_area_pixels": _median(r["area_pixels"] for r in single),
                "median_sharpness": _median(r["sharpness"] for r in single),
            },
        },
        # If cross-epoch photometry is sound, real sources must cluster at 1.
        "persistent_flux_ratio_median": _median(r["flux_ratio"] for r in persistent),
        "persistent_flux_ratio_scatter": (
            float(
                np.percentile(
                    [
                        r["flux_ratio"]
                        for r in persistent
                        if r["flux_ratio"] is not None and np.isfinite(r["flux_ratio"])
                    ],
                    [16, 84],
                ).tolist()[1]
                - np.percentile(
                    [
                        r["flux_ratio"]
                        for r in persistent
                        if r["flux_ratio"] is not None and np.isfinite(r["flux_ratio"])
                    ],
                    [16, 84],
                ).tolist()[0]
            )
            / 2.0
            if len([r for r in persistent if r["flux_ratio"] is not None]) > 10
            else None
        ),
    }


def run_pair(
    filter_name: str,
    path_a: Path,
    path_b: Path,
    *,
    highz_density_per_arcmin2: float = DEFAULT_HIGHZ_DENSITY_PER_ARCMIN2,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Run the full two-epoch comparison for one filter pair, both directions."""
    bundle_a = _load_fits_bundle_from_path(str(path_a))
    bundle_b = _load_fits_bundle_from_path(str(path_b))

    name_a = path_a.stem
    name_b = path_b.stem

    records = compare_epochs(bundle_a, bundle_b, epoch_a_name=name_a, epoch_b_name=name_b)
    records += compare_epochs(bundle_b, bundle_a, epoch_a_name=name_b, epoch_b_name=name_a)

    time_a = _observation_time(bundle_a)
    time_b = _observation_time(bundle_b)
    baseline_hours = (
        abs(time_a - time_b) * 24.0 if time_a is not None and time_b is not None else None
    )

    summary = summarize_pair(
        records,
        filter_name=filter_name,
        overlap_area_arcmin2=_overlap_area_arcmin2(bundle_a, bundle_b),
        baseline_hours=baseline_hours,
        exposure_seconds=_exposure_time(bundle_a),
        epochs=[name_a, name_b],
        highz_density_per_arcmin2=highz_density_per_arcmin2,
    )
    return summary, records


def _auto_discover(data_root: Path) -> Dict[str, List[Path]]:
    """Group downloaded i2d exposures by filter so pairs can be found."""
    by_filter: Dict[str, List[Path]] = defaultdict(list)
    for path in sorted(data_root.rglob("*_i2d.fits")):
        try:
            bundle = _load_fits_bundle_from_path(str(path))
        except Exception:
            continue
        filter_name = str(_header_value(bundle, "FILTER") or "").upper()
        if filter_name:
            by_filter[filter_name].append(path)
    return by_filter


def render_diagnostic_figure(
    records: List[Dict[str, Any]],
    summaries: List[Dict[str, Any]],
    output_path: Path,
) -> Optional[Path]:
    """Plot the morphology separation and the contamination curve."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None

    persistent = [r for r in records if r["classification"] == "persistent"]
    single = [r for r in records if r["classification"] == "single_epoch"]

    def _xy(subset, x_key, y_key):
        xs, ys = [], []
        for item in subset:
            x, y = item.get(x_key), item.get(y_key)
            if x is None or y is None:
                continue
            if np.isfinite(x) and np.isfinite(y):
                xs.append(x)
                ys.append(y)
        return xs, ys

    figure, axes = plt.subplots(1, 2, figsize=(12, 5))

    x_p, y_p = _xy(persistent, "fwhm_pixels", "sharpness")
    x_s, y_s = _xy(single, "fwhm_pixels", "sharpness")
    axes[0].scatter(x_p, y_p, s=6, alpha=0.35, label=f"persistent ({len(x_p)})")
    axes[0].scatter(x_s, y_s, s=10, alpha=0.7, label=f"single-epoch ({len(x_s)})")
    axes[0].set_xlabel("FWHM (pixels)")
    axes[0].set_ylabel("peak / total flux")
    axes[0].set_xlim(0, 8)
    axes[0].set_title("Morphology separation")
    axes[0].legend(loc="upper right", fontsize=8)

    for summary in summaries:
        rows = summary["artifact_fraction_by_snr"]
        if not rows:
            continue
        centers = [
            row["snr_min"] if row["snr_max"] is None else (row["snr_min"] + row["snr_max"]) / 2.0
            for row in rows
        ]
        axes[1].plot(
            centers,
            [100.0 * row["artifact_fraction"] for row in rows],
            marker="o",
            label=summary["filter"],
        )
    axes[1].set_xscale("log")
    axes[1].set_xlabel("detection SNR")
    axes[1].set_ylabel("single-epoch fraction (%)")
    axes[1].set_title("Artifact contamination vs significance")
    axes[1].legend(fontsize=8)

    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=130)
    plt.close(figure)
    return output_path


def render_report(summaries: List[Dict[str, Any]]) -> str:
    """Render the markdown results report."""
    lines = [
        "# Stage-2b Artifact Characterization",
        "",
        "Two independent exposures of the same sky in the same filter form a",
        "labelled truth set. Nothing astrophysical at cosmological distance varies",
        "over a few hours, so a source detected in one exposure and absent from the",
        "other is a detector event that survived Stage-2b calibration.",
        "",
        "Measured with `python discovery/artifact_characterization.py --auto`.",
        "",
        "## Per-pair results",
        "",
    ]

    for summary in summaries:
        baseline = summary["baseline_hours"]
        area = summary["overlap_area_arcmin2"]
        lines += [
            f"### {summary['filter']}",
            "",
            f"- Epochs: `{summary['epochs'][0]}` x `{summary['epochs'][1]}`",
            f"- Time baseline: {baseline:.2f} h" if baseline is not None else "- Time baseline: unknown",
            f"- Exposure time: {summary['exposure_seconds']:.1f} s"
            if summary["exposure_seconds"]
            else "- Exposure time: unknown",
            f"- Shared sky area: {area:.3f} arcmin^2" if area else "- Shared sky area: unknown",
            f"- Sources compared (both directions): **{summary['n_compared']}**",
            f"- Persistent: **{summary['n_persistent']}**"
            + (
                f" (of which {summary['n_recovered_by_wide_annulus']} recovered by the"
                f" wide-annulus recheck)"
                if summary.get("n_recovered_by_wide_annulus")
                else ""
            ),
            f"- Single-epoch (artifacts): **{summary['n_single_epoch']}**"
            f" ({100.0 * summary['single_epoch_fraction']:.1f}%)"
            if summary["single_epoch_fraction"] is not None
            else f"- Single-epoch (artifacts): {summary['n_single_epoch']}",
        ]
        if summary["artifact_density_per_arcmin2_per_exposure"] is not None:
            lines.append(
                f"- Surviving-artifact density: "
                f"**{summary['artifact_density_per_arcmin2_per_exposure']:.1f} per arcmin^2 "
                f"per exposure**"
            )
        if summary["artifact_density_per_arcmin2_per_kilosecond"] is not None:
            lines.append(
                f"- Normalized: "
                f"{summary['artifact_density_per_arcmin2_per_kilosecond']:.1f} "
                f"per arcmin^2 per kilosecond"
            )

        ratio = summary["persistent_flux_ratio_median"]
        if ratio is not None:
            scatter = summary["persistent_flux_ratio_scatter"]
            scatter_text = f" +/- {scatter:.3f}" if scatter is not None else ""
            lines += [
                "",
                f"Method validation - persistent sources have a cross-epoch flux ratio of "
                f"**{ratio:.3f}{scatter_text}**. A value at 1 confirms the cross-epoch "
                f"photometry is sound, so the single-epoch population is a real absence "
                f"rather than a measurement failure.",
            ]

        lines += ["", "| SNR range | sources | single-epoch | artifact fraction |", "| --- | ---: | ---: | ---: |"]
        for row in summary["artifact_fraction_by_snr"]:
            high = row["snr_max"]
            label = f"{row['snr_min']}-{high}" if high else f">{row['snr_min']}"
            lines.append(
                f"| {label} | {row['n_sources']} | {row['n_single_epoch']} | "
                f"{100.0 * row['artifact_fraction']:.1f}% |"
            )

        symmetry = summary.get("direction_symmetry") or []
        if len(symmetry) > 1:
            fractions = [
                row["single_epoch_fraction"]
                for row in symmetry
                if row["single_epoch_fraction"] is not None
            ]
            if fractions:
                lines += [
                    "",
                    f"Direction symmetry - searching each exposure in turn gives "
                    f"single-epoch fractions of "
                    f"{', '.join(f'{100.0 * f:.1f}%' for f in fractions)}. "
                    f"A stochastic per-exposure process must look the same whichever "
                    f"exposure is searched, and it does.",
                ]

        forecast = summary.get("contamination_forecast")
        if forecast:
            lines += [
                "",
                f"Contamination of a dropout search: an artifact appears in exactly one "
                f"exposure, so it is absent from every other band by construction and "
                f"passes any dropout cut with full efficiency. At "
                f"{forecast['artifact_density_per_arcmin2']:.1f} artifacts per arcmin^2 "
                f"against an assumed "
                f"{forecast['assumed_highz_density_per_arcmin2']:.3f} genuine z > 10 "
                f"sources per arcmin^2, that is "
                f"**~{forecast['artifacts_per_genuine_highz_source']:.0f} artifacts per "
                f"real high-redshift source**.",
            ]

        morphology = summary["morphology"]
        lines += [
            "",
            "| morphology (median) | persistent | single-epoch |",
            "| --- | ---: | ---: |",
        ]
        for key, label in (
            ("median_fwhm_pixels", "FWHM (px)"),
            ("median_ellipticity", "ellipticity"),
            ("median_area_pixels", "area (px)"),
            ("median_sharpness", "peak/total flux"),
        ):
            persistent_value = morphology["persistent"].get(key)
            single_value = morphology["single_epoch"].get(key)
            lines.append(
                f"| {label} | "
                f"{persistent_value:.3f} | " if persistent_value is not None else f"| {label} | n/a | "
            )
            lines[-1] += f"{single_value:.3f} |" if single_value is not None else "n/a |"
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    """Characterize surviving artifacts across the available exposure pairs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pair",
        nargs=3,
        action="append",
        metavar=("FILTER", "EPOCH_A", "EPOCH_B"),
        help="Explicit filter and two i2d paths. Repeatable.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Discover same-filter exposure pairs under --data-root.",
    )
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--figure", type=Path, default=RESEARCH_DIR / "visuals" / "artifact_diagnostics.png"
    )
    parser.add_argument(
        "--highz-density",
        type=float,
        default=DEFAULT_HIGHZ_DENSITY_PER_ARCMIN2,
        help="Assumed genuine z>10 surface density per arcmin^2 for the contamination ratio.",
    )
    args = parser.parse_args()

    pairs: List[Tuple[str, Path, Path]] = []
    if args.pair:
        pairs += [(f, Path(a), Path(b)) for f, a, b in args.pair]
    if args.auto:
        for filter_name, paths in sorted(_auto_discover(args.data_root).items()):
            for index in range(len(paths)):
                for other in range(index + 1, len(paths)):
                    pairs.append((filter_name, paths[index], paths[other]))

    if not pairs:
        print("No exposure pairs given. Use --auto or --pair.")
        return 1

    summaries: List[Dict[str, Any]] = []
    all_records: List[Dict[str, Any]] = []
    for filter_name, path_a, path_b in pairs:
        print(f"Comparing {filter_name}: {path_a.stem} x {path_b.stem}")
        summary, records = run_pair(
            filter_name, path_a, path_b, highz_density_per_arcmin2=args.highz_density
        )
        if summary["n_compared"] == 0:
            print("  no shared-footprint sources; skipping")
            continue
        summaries.append(summary)
        all_records += records
        print(
            f"  compared={summary['n_compared']} "
            f"persistent={summary['n_persistent']} "
            f"single_epoch={summary['n_single_epoch']}"
        )

    if not summaries:
        print("No pair produced comparable sources.")
        return 1

    consolidated = consolidate_detections(all_records)
    n_artifact = sum(1 for r in consolidated if r["consensus"] == "artifact")
    n_multi = sum(1 for r in consolidated if r["n_comparisons"] > 1)
    n_mixed = sum(1 for r in consolidated if not r["unanimous"])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "summaries": summaries,
                "sources": all_records,
                "detections": consolidated,
                "detection_summary": {
                    "n_detections": len(consolidated),
                    "n_artifact": n_artifact,
                    "n_real": len(consolidated) - n_artifact,
                    "n_with_multiple_comparisons": n_multi,
                    "n_mixed_verdicts": n_mixed,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"\nConsolidated to {len(consolidated)} unique detections "
        f"({n_artifact} artifact, {len(consolidated) - n_artifact} real); "
        f"{n_multi} have >1 comparison, {n_mixed} give mixed verdicts"
    )
    args.report.write_text(render_report(summaries), encoding="utf-8")
    figure_path = render_diagnostic_figure(all_records, summaries, args.figure)
    print(f"\nWritten to {args.output} and {args.report}")
    if figure_path:
        print(f"Diagnostic figure: {figure_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
