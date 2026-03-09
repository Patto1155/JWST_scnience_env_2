"""Core visualization tools."""

from typing import Dict, Any, List, Optional
import numpy as np
from pathlib import Path


def save_histogram(
    values: List[float],
    output_path: str,
    bins: int = 30,
    title: str = "Histogram",
) -> Dict[str, Any]:
    """
    Save a histogram plot to file.
    
    Args:
        values: List of values to plot
        output_path: Path to save the plot
        bins: Number of bins
        title: Plot title
    
    Returns:
        Dictionary with status and path
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # Non-interactive backend
        import matplotlib.pyplot as plt
        
        arr = np.asarray(values, dtype=float)
        
        plt.figure(figsize=(8, 6))
        plt.hist(arr, bins=bins, edgecolor="black", alpha=0.7)
        plt.xlabel("Value")
        plt.ylabel("Frequency")
        plt.title(title)
        plt.grid(True, alpha=0.3)
        
        # Ensure output directory exists
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()
        
        return {
            "status": "success",
            "output_path": output_path,
            "bins": bins,
            "count": len(values),
        }
    except ImportError:
        # Fallback if matplotlib not available
        return {
            "status": "error",
            "error": "matplotlib not available",
            "output_path": None,
        }


def save_scatter_plot(
    x: List[float],
    y: List[float],
    output_path: str,
    title: str = "Scatter Plot",
    xlabel: str = "X",
    ylabel: str = "Y",
) -> Dict[str, Any]:
    """
    Save a scatter plot to file.
    
    Args:
        x: X values
        y: Y values
        output_path: Path to save the plot
        title: Plot title
        xlabel: X axis label
        ylabel: Y axis label
    
    Returns:
        Dictionary with status and path
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        
        if len(x) != len(y):
            return {
                "status": "error",
                "error": "x and y must have same length",
            }
        
        plt.figure(figsize=(8, 6))
        plt.scatter(x, y, alpha=0.6, s=20)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.title(title)
        plt.grid(True, alpha=0.3)
        
        # Ensure output directory exists
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()
        
        return {
            "status": "success",
            "output_path": output_path,
            "count": len(x),
        }
    except ImportError:
        return {
            "status": "error",
            "error": "matplotlib not available",
            "output_path": None,
        }

