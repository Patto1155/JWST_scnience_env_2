"""Quickstart example - demonstrates how to use the Science OS API."""

import requests
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8000"


def list_tools() -> Dict[str, Any]:
    """List all available tools."""
    response = requests.get(f"{BASE_URL}/tools")
    return response.json()


def list_datasets() -> Dict[str, Any]:
    """List all available datasets."""
    response = requests.get(f"{BASE_URL}/datasets")
    return response.json()


def create_experiment_run() -> Dict[str, Any]:
    """Create and start a simple experiment run."""
    experiment_spec = {
        "objective": "Compute statistics on dummy image data",
        "datasets": ["jwst_ngc1234_f200w"],
        "steps": [
            {
                "tool_name": "image_statistics",
                "parameters": {
                    "image_data": None,  # Will use default dummy data
                },
            },
            {
                "tool_name": "compute_mean",
                "parameters": {
                    "values": [1.0, 2.0, 3.0, 4.0, 5.0],
                },
            },
        ],
    }
    
    run_request = {
        "spec": experiment_spec,
    }
    
    response = requests.post(f"{BASE_URL}/runs", json=run_request)
    return response.json()


def get_run_status(run_id: int) -> Dict[str, Any]:
    """Get status of a run."""
    response = requests.get(f"{BASE_URL}/runs/{run_id}")
    return response.json()


if __name__ == "__main__":
    print("Science OS Quickstart Example")
    print("=" * 50)
    
    # List tools
    print("\n1. Available Tools:")
    tools = list_tools()
    for tool in tools["tools"]:
        print(f"   - {tool['name']}: {tool['description']}")
    
    # List datasets
    print("\n2. Available Datasets:")
    datasets = list_datasets()
    for dataset in datasets["datasets"]:
        print(f"   - {dataset['name']}: {dataset['description']}")
    
    # Create a run
    print("\n3. Creating experiment run...")
    run = create_experiment_run()
    run_id = run["id"]
    print(f"   Run created with ID: {run_id}")
    print(f"   Status: {run['status']}")
    
    # Wait a bit and check status
    import time
    print("\n4. Waiting for run to complete...")
    time.sleep(2)
    
    status = get_run_status(run_id)
    print(f"   Status: {status['status']}")
    if status.get("result"):
        print(f"   Result: {json.dumps(status['result'], indent=2)}")

