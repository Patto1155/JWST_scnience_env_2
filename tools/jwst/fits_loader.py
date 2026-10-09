"""
FITS file loader helpers for strict JWST analysis.

This module keeps the legacy SCI-only loader while adding bundle/WCS helpers
needed by uncertainty-aware photometry and visual evidence tools.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

# Anchor relative dataset paths to the project root, not the cwd of the process.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _lookup_dataset_record(dataset_name: str, db_session=None):
    """Return the dataset row for a registered dataset name, if available."""
    if db_session is not None:
        from core_api.models.datasets import Dataset

        return (
            db_session.query(Dataset)
            .filter(Dataset.name == dataset_name)
            .first()
        )

    try:
        from core_api.db import SessionLocal  # Imported lazily to avoid circular deps
        from core_api.models.datasets import Dataset

        db = SessionLocal()
        try:
            return db.query(Dataset).filter(Dataset.name == dataset_name).first()
        finally:
            db.close()
    except Exception:
        return None


@lru_cache(maxsize=256)
def _resolve_registered_dataset_path(dataset_name: str) -> Tuple[str, Dict[str, Any]]:
    """Resolve registered dataset metadata once for repeated strict-data lookups."""
    dataset = _lookup_dataset_record(dataset_name, db_session=None)
    if dataset is None:
        raise LookupError(dataset_name)

    metadata = dataset.meta_data if isinstance(dataset.meta_data, dict) else {}
    file_path = metadata.get("file_path")
    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError(f"No file_path in metadata for {dataset_name}")

    path_obj = Path(file_path).expanduser()
    if not path_obj.is_absolute():
        path_obj = _PROJECT_ROOT / path_obj
    if not path_obj.exists():
        raise FileNotFoundError(f"FITS file not found: {path_obj}")
    return str(path_obj), dict(metadata)


def resolve_dataset_path(
    dataset_name: str,
    db_session=None,
) -> Tuple[Path, Dict[str, Any]]:
    """
    Resolve a dataset identifier to a local FITS path plus catalog metadata.

    The resolver prefers registered dataset metadata.file_path mappings, but also
    accepts direct file paths and retains the legacy filesystem search fallback.
    """
    if isinstance(dataset_name, Path):
        path_obj = dataset_name.expanduser()
        if not path_obj.exists():
            raise FileNotFoundError(f"FITS file not found: {path_obj}")
        return path_obj, {}

    if not isinstance(dataset_name, str) or not dataset_name.strip():
        raise ValueError("dataset_name must be a non-empty string or Path")

    candidate = Path(dataset_name).expanduser()
    if not candidate.is_absolute():
        anchored = _PROJECT_ROOT / candidate
        if anchored.exists():
            return anchored, {}
    if candidate.exists():
        return candidate, {}

    if db_session is None:
        try:
            path_str, metadata = _resolve_registered_dataset_path(dataset_name)
            return Path(path_str), dict(metadata)
        except LookupError:
            pass
    else:
        dataset = _lookup_dataset_record(dataset_name, db_session=db_session)
        if dataset is not None:
            metadata = dataset.meta_data if isinstance(dataset.meta_data, dict) else {}
            file_path = metadata.get("file_path")
            if not isinstance(file_path, str) or not file_path.strip():
                raise ValueError(f"No file_path in metadata for {dataset_name}")

            path_obj = Path(file_path).expanduser()
            if not path_obj.is_absolute():
                path_obj = _PROJECT_ROOT / path_obj
            if not path_obj.exists():
                raise FileNotFoundError(f"FITS file not found: {path_obj}")
            return path_obj, dict(metadata)

    data_dir = _PROJECT_ROOT / "data" / "jwst"
    fits_files = list(data_dir.rglob(f"*{dataset_name}*.fits"))
    if not fits_files:
        raise ValueError(f"No FITS file found for {dataset_name}")
    return fits_files[0], {}


def _get_hdu(hdul, preferred_name: str, fallback_index: Optional[int] = None):
    """Return a FITS HDU by name when present, otherwise a fallback index."""
    if preferred_name in hdul:
        return hdul[preferred_name]
    if fallback_index is not None and len(hdul) > fallback_index:
        return hdul[fallback_index]
    return None


def _extract_wcs(header) -> Optional[WCS]:
    """Build a WCS object when the header supports it."""
    try:
        wcs = WCS(header)
    except Exception:
        return None

    if getattr(wcs, "pixel_n_dim", 0) < 2 or getattr(wcs, "world_n_dim", 0) < 2:
        return None
    return wcs


def _freeze_array(array: Optional[np.ndarray]) -> Optional[np.ndarray]:
    """Mark cached arrays as read-only to avoid accidental in-place mutation."""
    if array is None:
        return None
    array.setflags(write=False)
    return array


@lru_cache(maxsize=16)
def _load_fits_bundle_version(fits_path_str: str, file_size: int, mtime_ns: int) -> Dict[str, Any]:
    """Cache raw planes by path and file version, never by path alone."""
    del file_size, mtime_ns  # Used in the cache key; data are loaded below.
    fits_path = Path(fits_path_str)

    with fits.open(fits_path) as hdul:
        sci_hdu = _get_hdu(hdul, "SCI", fallback_index=1) or hdul[0]
        err_hdu = _get_hdu(hdul, "ERR", fallback_index=2)
        wht_hdu = _get_hdu(hdul, "WHT")

        sci = np.array(sci_hdu.data, dtype=float)
        if sci is None:
            raise ValueError(f"No image data found in {fits_path}")

        err = None
        if err_hdu is not None and err_hdu.data is not None:
            err = np.array(err_hdu.data, dtype=float)

        wht = None
        if wht_hdu is not None and wht_hdu.data is not None:
            wht = np.array(wht_hdu.data, dtype=float)

        header = sci_hdu.header.copy()
        # Exposure metadata (FILTER, EFFEXPTM, DETECTOR) lives in the primary
        # header, not the SCI header, so keep both.
        primary_header = hdul[0].header.copy()

    if sci.ndim > 2:
        collapse_axes = tuple(range(sci.ndim - 2))
        sci = np.nanmean(sci, axis=collapse_axes)
        if err is not None and err.ndim > 2:
            err = np.nanmean(err, axis=collapse_axes)
        if wht is not None and wht.ndim > 2:
            wht = np.nanmean(wht, axis=collapse_axes)

    validity_mask = np.isfinite(sci)
    if wht is not None and wht.shape == sci.shape:
        validity_mask &= np.isfinite(wht) & (wht > 0)
    elif err is not None and err.shape == sci.shape:
        validity_mask &= np.isfinite(err)

    wcs = _extract_wcs(header)

    return {
        "sci": _freeze_array(sci),
        "err": _freeze_array(err),
        "wht": _freeze_array(wht),
        "header": header,
        "primary_header": primary_header,
        "wcs": wcs,
        "validity_mask": _freeze_array(validity_mask),
    }


def _load_fits_bundle_from_path(fits_path_str: str) -> Dict[str, Any]:
    """Load current file version while retaining the existing path-only API."""
    file_stat = Path(fits_path_str).stat()
    return _load_fits_bundle_version(fits_path_str, file_stat.st_size, file_stat.st_mtime_ns)


def load_fits_bundle(dataset_name: str, db_session=None) -> Dict[str, Any]:
    """
    Load a JWST FITS bundle including SCI, ERR, WHT, header, and WCS.

    The returned bundle intentionally preserves NaNs and invalid pixels so callers
    can make explicit masking decisions.
    """
    fits_path, metadata = resolve_dataset_path(dataset_name, db_session=db_session)
    raw_bundle = _load_fits_bundle_from_path(str(fits_path.resolve()))

    return {
        "sci": raw_bundle["sci"],
        "err": raw_bundle["err"],
        "wht": raw_bundle["wht"],
        "header": raw_bundle["header"].copy(),
        "primary_header": raw_bundle["primary_header"].copy(),
        "wcs": raw_bundle["wcs"],
        "validity_mask": raw_bundle["validity_mask"],
        "dataset_name": dataset_name,
        "file_path": str(fits_path),
        "filter": metadata.get("filter")
        or raw_bundle["primary_header"].get("FILTER")
        or raw_bundle["header"].get("FILTER"),
        "target": metadata.get("target")
        or raw_bundle["primary_header"].get("TARGPROP")
        or raw_bundle["header"].get("TARGPROP"),
        "instrument": metadata.get("instrument")
        or raw_bundle["primary_header"].get("INSTRUME")
        or raw_bundle["header"].get("INSTRUME"),
        "metadata": metadata,
    }


def load_fits_wcs(dataset_name: str, db_session=None) -> Optional[WCS]:
    """Load only the WCS for a registered dataset or FITS file path."""
    return load_fits_bundle(dataset_name, db_session=db_session)["wcs"]


def load_fits_data(dataset_name, db_session=None):
    """
    Load SCI image data for a registered dataset.

    This legacy helper is kept for backward compatibility with the existing tool
    surface. New code should prefer load_fits_bundle().
    """
    return np.array(load_fits_bundle(dataset_name, db_session=db_session)["sci"], dtype=float)


def get_dummy_data(shape=(512, 512)):
    """
    Generate dummy data for testing when real data not available.

    Args:
        shape: Shape of output array

    Returns:
        numpy array with simulated astronomical image
    """
    rng = np.random.RandomState(42)
    background = rng.poisson(10, size=shape).astype(float)

    n_sources = 20
    for _ in range(n_sources):
        x = rng.randint(0, shape[1])
        y = rng.randint(0, shape[0])
        brightness = rng.uniform(100, 1000)

        yy, xx = np.ogrid[:shape[0], :shape[1]]
        sigma = 2.5
        psf = brightness * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * sigma ** 2))
        background += psf

    return background


def _resolve_strict_mode(strict_data):
    """Resolve strict mode from explicit parameter or environment."""
    if strict_data is not None:
        return bool(strict_data)

    env_value = os.getenv("SCIENCE_OS_STRICT_NO_DUMMY", "").strip().lower()
    return env_value in {"1", "true", "yes", "on"}


def _smart_load_data_impl(dataset_identifier, strict_data=None):
    """Implementation with optional strict mode toggle."""
    strict = _resolve_strict_mode(strict_data)

    if dataset_identifier is None:
        if strict:
            raise ValueError(
                "Strict real-data mode enabled: dataset_identifier is required; "
                "dummy fallback is disabled."
            )
        return get_dummy_data()

    db_error = None
    fs_error = None

    try:
        from core_api.db import SessionLocal  # Imported lazily to avoid circular deps

        db = SessionLocal()
        try:
            return load_fits_data(dataset_identifier, db_session=db)
        finally:
            db.close()
    except Exception as exc:
        db_error = exc
        print(f"Could not load via DB ({exc}), trying filesystem search")

    try:
        return load_fits_data(dataset_identifier)
    except Exception as exc:
        fs_error = exc
        if strict:
            raise FileNotFoundError(
                "Strict real-data mode enabled: could not load dataset "
                f"'{dataset_identifier}' from DB or filesystem. "
                f"DB error: {db_error}; FS error: {fs_error}"
            ) from exc
        print(f"Could not load real data ({exc}), using dummy data")
        return get_dummy_data()


def smart_load_data(dataset_identifier, strict_data=None):
    """
    Smart loader that tries real data first, falls back to dummy data.

    Args:
        dataset_identifier: Dataset name or None
        strict_data: If True, disable dummy fallback and raise on load failure.
            If None, falls back to env var SCIENCE_OS_STRICT_NO_DUMMY.

    Returns:
        numpy array of image data
    """
    return _smart_load_data_impl(dataset_identifier, strict_data=strict_data)
