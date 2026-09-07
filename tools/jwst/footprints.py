"""Sky-footprint geometry for JWST exposures.

Cross-filter and multi-epoch photometry is only meaningful where two exposures
see the same sky. NIRCam modules A and B point at non-overlapping fields, and a
short-wave detector covers roughly one quadrant of the long-wave field, so
selecting exposures per filter independently can silently pair images that never
overlap. Every aperture then lands off the detector and returns zero flux, which
downstream code reads as a perfect non-detection.

The helpers here answer that question directly from the WCS rather than by
guessing from file names.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

import numpy as np

# NIRCam detector token as it appears in JWST product names, e.g. ``nrca1``.
DETECTOR_PATTERN = re.compile(r"_(nrc[ab](?:long|[1-4]))(?:_|$)", re.IGNORECASE)

# Default sampling grid for the overlap estimate. 40x40 gives ~0.1% resolution
# on the overlap fraction, which is far finer than any decision made from it.
DEFAULT_SAMPLE_GRID = 40

# Below this fraction the shared area is too small to support a useful
# cross-band or cross-epoch measurement.
MIN_USEFUL_OVERLAP = 0.05

# A sky position belongs to a pixel when it rounds to a valid index, so the
# valid range for a pixel-center coordinate is [-0.5, n - 0.5). Testing against
# [0, n) instead rejects the outermost half-pixel and, because a WCS round trip
# lands on the array edge to within ~1e-11, intermittently rejects the edge row
# and column outright.
PIXEL_EDGE = 0.5


def detector_token(dataset_name: str) -> Optional[str]:
    """Extract the NIRCam detector token from a dataset or file name."""
    match = DETECTOR_PATTERN.search(str(dataset_name))
    return match.group(1).lower() if match else None


def module_letter(dataset_name: str) -> Optional[str]:
    """Return the NIRCam module letter (``a``/``b``), or None if unknown."""
    token = detector_token(dataset_name)
    return token[3] if token else None


def modules_are_disjoint(name_a: str, name_b: str) -> bool:
    """True when two datasets sit on NIRCam modules that cannot share sky."""
    module_a = module_letter(name_a)
    module_b = module_letter(name_b)
    return bool(module_a and module_b and module_a != module_b)


def _image_shape(bundle: Dict[str, Any]) -> Tuple[int, int]:
    """Return (height, width) of a bundle's science array."""
    shape = np.asarray(bundle["sci"]).shape
    return int(shape[-2]), int(shape[-1])


def overlap_fraction(
    bundle_a: Dict[str, Any],
    bundle_b: Dict[str, Any],
    *,
    grid: int = DEFAULT_SAMPLE_GRID,
) -> float:
    """Fraction of bundle A's pixel grid whose sky position falls inside B.

    The measure is deliberately asymmetric: it answers "if I detect sources in
    A, what fraction of them can I measure in B?", which is exactly the question
    the candidate pipeline needs answered. Comparing a long-wave reference
    against a short-wave detector returns roughly 0.25, because one short-wave
    detector tiles a quarter of the long-wave field.
    """
    wcs_a = bundle_a.get("wcs")
    wcs_b = bundle_b.get("wcs")
    if wcs_a is None or wcs_b is None:
        return 0.0

    height_a, width_a = _image_shape(bundle_a)
    height_b, width_b = _image_shape(bundle_b)

    xs = np.linspace(0, width_a - 1, grid)
    ys = np.linspace(0, height_a - 1, grid)
    grid_x, grid_y = np.meshgrid(xs, ys)

    try:
        ra, dec = wcs_a.pixel_to_world_values(grid_x.ravel(), grid_y.ravel())
        x_b, y_b = wcs_b.world_to_pixel_values(ra, dec)
    except Exception:
        return 0.0

    inside = (
        np.isfinite(x_b)
        & np.isfinite(y_b)
        & (x_b >= -PIXEL_EDGE)
        & (y_b >= -PIXEL_EDGE)
        & (x_b < width_b - PIXEL_EDGE)
        & (y_b < height_b - PIXEL_EDGE)
    )
    return float(np.mean(inside))


def sky_to_pixel(bundle: Dict[str, Any], ra: float, dec: float) -> Optional[Tuple[float, float]]:
    """Map a sky position into a bundle's pixel frame, or None when off-array.

    Returning None rather than an out-of-range coordinate keeps callers from
    measuring an aperture that is not on the detector.
    """
    wcs = bundle.get("wcs")
    if wcs is None or ra is None or dec is None:
        return None

    try:
        x, y = wcs.world_to_pixel_values(float(ra), float(dec))
    except Exception:
        return None

    x = float(x)
    y = float(y)
    if not (np.isfinite(x) and np.isfinite(y)):
        return None

    height, width = _image_shape(bundle)
    if (
        x < -PIXEL_EDGE
        or y < -PIXEL_EDGE
        or x >= width - PIXEL_EDGE
        or y >= height - PIXEL_EDGE
    ):
        return None
    return x, y
