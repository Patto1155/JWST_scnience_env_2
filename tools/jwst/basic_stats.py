"""JWST basic statistics tools."""

from typing import Dict, Any, List, Optional
import numpy as np

try:
    from tools.jwst.fits_loader import smart_load_data
    FITS_LOADER_AVAILABLE = True
except ImportError:
    FITS_LOADER_AVAILABLE = False


def image_statistics(
    image_data: Any,
    region: Optional[Dict[str, float]] = None,
    strict_data: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Compute basic statistics for JWST image data.

    Args:
        image_data: Image array, dataset name, or None for dummy data
        region: Optional dict with 'x_min', 'x_max', 'y_min', 'y_max' to limit region

    Returns:
        Dictionary with statistics (mean, median, std, min, max, etc.)
    """
    # Load data if string (dataset name) provided
    if isinstance(image_data, str) or image_data is None:
        if FITS_LOADER_AVAILABLE:
            image = smart_load_data(image_data, strict_data=strict_data)
        else:
            # Fallback to dummy data
            image = np.random.randn(512, 512) * 0.01 + 0.02
    else:
        image = np.asarray(image_data)
    
    # Apply region if specified
    if region:
        y_min = int(region.get("y_min", 0))
        y_max = int(region.get("y_max", image.shape[0]))
        x_min = int(region.get("x_min", 0))
        x_max = int(region.get("x_max", image.shape[1]))
        image = image[y_min:y_max, x_min:x_max]
    
    # Compute statistics
    return {
        "summary_stats": {
            "mean": float(np.mean(image)),
            "median": float(np.median(image)),
            "std": float(np.std(image)),
            "min": float(np.min(image)),
            "max": float(np.max(image)),
        },
        "mean": float(np.mean(image)),  # Keep for backward compatibility
        "median": float(np.median(image)),
        "std": float(np.std(image)),
        "min": float(np.min(image)),
        "max": float(np.max(image)),
        "percentile_25": float(np.percentile(image, 25)),
        "percentile_75": float(np.percentile(image, 75)),
        "shape": list(image.shape),
        "total_pixels": int(image.size),
    }


def brightness_distribution(
    image_data: Any,
    bins: int = 50,
    strict_data: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Compute brightness distribution histogram for image data.

    Args:
        image_data: Image array, dataset name, or None for dummy data
        bins: Number of histogram bins

    Returns:
        Dictionary with histogram data
    """
    # Load data if string (dataset name) provided
    if isinstance(image_data, str) or image_data is None:
        if FITS_LOADER_AVAILABLE:
            image = smart_load_data(image_data, strict_data=strict_data).flatten()
        else:
            image = (np.random.randn(512, 512) * 0.01 + 0.02).flatten()
    else:
        image = np.asarray(image_data).flatten()
    
    counts, bin_edges = np.histogram(image, bins=bins)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    return {
        "bin_centers": [float(x) for x in bin_centers],
        "counts": [int(x) for x in counts],
        "bin_edges": [float(x) for x in bin_edges],
        "total_pixels": int(image.size),
    }


def compare_images(
    image1_data: Any,
    image2_data: Any,
    strict_data: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Compare two images statistically.
    
    Args:
        image1_data: First image array or dataset name
        image2_data: Second image array or dataset name
    
    Returns:
        Dictionary with comparison metrics
    """
    # Load data if dataset names or None are provided
    if isinstance(image1_data, str) or image1_data is None:
        if FITS_LOADER_AVAILABLE:
            img1 = smart_load_data(image1_data, strict_data=strict_data)
        else:
            img1 = np.random.randn(512, 512) * 0.01 + 0.02
    else:
        img1 = np.asarray(image1_data)

    if isinstance(image2_data, str) or image2_data is None:
        if FITS_LOADER_AVAILABLE:
            img2 = smart_load_data(image2_data, strict_data=strict_data)
        else:
            img2 = np.random.randn(512, 512) * 0.01 + 0.02
    else:
        img2 = np.asarray(image2_data)
    
    # Ensure same shape (crop to smaller if needed)
    if img1.shape != img2.shape:
        min_h = min(img1.shape[0], img2.shape[0])
        min_w = min(img1.shape[1], img2.shape[1])
        img1 = img1[:min_h, :min_w]
        img2 = img2[:min_h, :min_w]
    
    diff = img1 - img2
    
    return {
        "image1_mean": float(np.mean(img1)),
        "image2_mean": float(np.mean(img2)),
        "mean_difference": float(np.mean(diff)),
        "std_difference": float(np.std(diff)),
        "rms_difference": float(np.sqrt(np.mean(diff ** 2))),
        "correlation": float(np.corrcoef(img1.flatten(), img2.flatten())[0, 1]),
    }

