"""Data compression and summarization utilities for tool outputs."""

from typing import Any, Dict, List, Optional
import numpy as np


def summarize_array(
    arr: Any,
    max_sample_size: int = 10,
    include_stats: bool = True,
) -> Dict[str, Any]:
    """
    Summarize an array with statistics and a sample.
    
    Args:
        arr: Array-like data
        max_sample_size: Maximum number of sample values to include
        include_stats: Whether to include statistical summary
    
    Returns:
        Dictionary with summary_stats, sample_preview, and shape info
    """
    arr = np.asarray(arr)
    result: Dict[str, Any] = {}
    
    if include_stats:
        result["summary_stats"] = {
            "mean": float(np.mean(arr)),
            "median": float(np.median(arr)),
            "std": float(np.std(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
        }
    
    # Sample preview
    flat_arr = arr.flatten()
    sample_size = min(max_sample_size, len(flat_arr))
    if sample_size > 0:
        indices = np.linspace(0, len(flat_arr) - 1, sample_size, dtype=int)
        result["sample_preview"] = [float(flat_arr[i]) for i in indices]
    
    result["shape"] = list(arr.shape)
    result["total_elements"] = int(arr.size)
    
    return result


def sample_array(
    arr: Any,
    n_samples: int = 10,
    method: str = "uniform",
) -> List[float]:
    """
    Sample values from an array.
    
    Args:
        arr: Array-like data
        n_samples: Number of samples to return
        method: Sampling method ('uniform', 'random', 'first', 'last')
    
    Returns:
        List of sampled values
    """
    arr = np.asarray(arr).flatten()
    n_samples = min(n_samples, len(arr))
    
    if n_samples == 0:
        return []
    
    if method == "uniform":
        indices = np.linspace(0, len(arr) - 1, n_samples, dtype=int)
        return [float(arr[i]) for i in indices]
    elif method == "random":
        indices = np.random.choice(len(arr), n_samples, replace=False)
        return [float(arr[i]) for i in sorted(indices)]
    elif method == "first":
        return [float(arr[i]) for i in range(n_samples)]
    elif method == "last":
        return [float(arr[i]) for i in range(len(arr) - n_samples, len(arr))]
    else:
        # Default to uniform
        indices = np.linspace(0, len(arr) - 1, n_samples, dtype=int)
        return [float(arr[i]) for i in indices]


def make_histogram(
    arr: Any,
    bins: int = 20,
) -> Dict[str, Any]:
    """
    Create a histogram summary of array data.
    
    Args:
        arr: Array-like data
        bins: Number of histogram bins
    
    Returns:
        Dictionary with bin_centers, counts, and bin_edges
    """
    arr = np.asarray(arr).flatten()
    counts, bin_edges = np.histogram(arr, bins=bins)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    return {
        "bin_centers": [float(x) for x in bin_centers],
        "counts": [int(x) for x in counts],
        "bin_edges": [float(x) for x in bin_edges],
        "total_elements": int(arr.size),
    }

