"""Core statistical tools."""

from typing import Dict, Any, List
import numpy as np


def compute_mean(values: List[float]) -> Dict[str, Any]:
    """
    Compute mean of a list of values.
    
    Args:
        values: List of numeric values
    
    Returns:
        Dictionary with summary_stats and count
    """
    arr = np.asarray(values, dtype=float)
    return {
        "summary_stats": {
            "mean": float(np.mean(arr)),
            "count": len(values),
        },
        "mean": float(np.mean(arr)),  # Keep for backward compatibility
        "count": len(values),
    }


def compute_median(values: List[float]) -> Dict[str, Any]:
    """
    Compute median of a list of values.
    
    Args:
        values: List of numeric values
    
    Returns:
        Dictionary with median and count
    """
    arr = np.asarray(values, dtype=float)
    return {
        "median": float(np.median(arr)),
        "count": len(values),
    }


def compute_std(values: List[float]) -> Dict[str, Any]:
    """
    Compute standard deviation of a list of values.
    
    Args:
        values: List of numeric values
    
    Returns:
        Dictionary with std and count
    """
    arr = np.asarray(values, dtype=float)
    return {
        "std": float(np.std(arr)),
        "mean": float(np.mean(arr)),
        "count": len(values),
    }


def correlation(x: List[float], y: List[float]) -> Dict[str, Any]:
    """
    Compute correlation between two lists.
    
    Args:
        x: First list of values
        y: Second list of values
    
    Returns:
        Dictionary with correlation coefficient
    """
    if len(x) != len(y):
        return {
            "correlation": None,
            "error": "Lists must have same length",
        }
    
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    
    corr = np.corrcoef(x_arr, y_arr)[0, 1]
    
    return {
        "correlation": float(corr) if not np.isnan(corr) else None,
        "count": len(x),
    }

