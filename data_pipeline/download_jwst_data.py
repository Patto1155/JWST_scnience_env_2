"""
Download real JWST data from MAST archive.

This script downloads JWST observations and prepares them for Science OS.
Enhanced to support program ID queries for major surveys like JADES, CEERS, etc.
"""

from astroquery.mast import Observations
import os
from pathlib import Path
from typing import List, Optional, Dict
import json
from datetime import datetime


# Major JWST Survey Programs
JWST_PROGRAMS = {
    "JADES": {
        "description": "JWST Advanced Deep Extragalactic Survey - high-z galaxy studies",
        "program_ids": [1180, 1181, 1210, 1286, 1287],
        "science_case": "Cosmic Dawn / High-z galaxies"
    },
    "CEERS": {
        "description": "Cosmic Evolution Early Release Science",
        "program_ids": [1345],
        "science_case": "Galaxy evolution"
    },
    "SMACS": {
        "description": "SMACS 0723 Deep Field - First Deep Field",
        "program_ids": [2736],
        "science_case": "Deep field imaging"
    },
    "COSMOS-Web": {
        "description": "COSMOS-Web Wide Field Survey",
        "program_ids": [1727],
        "science_case": "Wide-field galaxy survey"
    },
    "PEARLS": {
        "description": "Prime Extragalactic Areas for Reionization and Lensing Science",
        "program_ids": [1176, 2738],
        "science_case": "Reionization studies"
    },
    "GLASS": {
        "description": "GLASS JWST Early Release Science",
        "program_ids": [1324],
        "science_case": "Galaxy evolution through lensing"
    },
    "ERO": {
        "description": "Early Release Observations",
        "program_ids": [2731, 2732, 2733, 2734, 2736],
        "science_case": "Showcase JWST capabilities"
    }
}


def download_jwst_target(target_name: str, filters: List[str] = None,
                         data_dir: str = "data/jwst", max_files: int = 10) -> List[str]:
    """
    Download JWST data for a specific target.

    Args:
        target_name: Name of astronomical target (e.g., "NGC 1365", "M51")
        filters: List of filters to download (e.g., ["F200W", "F356W"])
        data_dir: Directory to save downloaded data
        max_files: Maximum number of files to download

    Returns:
        List of downloaded file paths
    """
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)

    print(f"Searching MAST for JWST observations of {target_name}...")

    # Search for JWST observations
    obs_table = Observations.query_criteria(
        target_name=target_name,
        obs_collection="JWST",
        dataproduct_type="image"
    )

    if len(obs_table) == 0:
        print(f"No JWST observations found for {target_name}")
        return []

    print(f"Found {len(obs_table)} observations")

    # Get data products
    print("Getting data products...")
    data_products = Observations.get_product_list(obs_table[0:5])  # First 5 obs

    # Filter for science products (level 2 calibrated images)
    science_products = Observations.filter_products(
        data_products,
        productType="SCIENCE",
        calib_level=2
    )

    print(f"Found {len(science_products)} science products")
    print(f"Downloading to {data_path}...")

    # Download
    manifest = Observations.download_products(
        science_products[0:max_files],
        download_dir=str(data_path)
    )

    print(f"Downloaded {len(manifest)} files")
    return list(manifest['Local Path'])


def download_by_program_id(program_id: int, data_dir: str = "data/jwst",
                           max_obs: int = 20, max_files_per_obs: int = 5,
                           instrument: str = None,
                           dataproduct_type: str = "image") -> Dict:
    """
    Download JWST data by program ID.

    Args:
        program_id: JWST program ID (e.g., 1345 for CEERS)
        data_dir: Directory to save downloaded data
        max_obs: Maximum number of observations to process
        max_files_per_obs: Maximum files per observation
        instrument: Filter by instrument (NIRCam, MIRI, NIRSpec, NIRISS)
        dataproduct_type: Type of data product (image, spectrum)

    Returns:
        Dictionary with download results and metadata
    """
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Downloading JWST Program {program_id}")
    print(f"{'='*60}")

    # Build query criteria
    criteria = {
        "obs_collection": "JWST",
        "proposal_id": str(program_id),
        "dataproduct_type": dataproduct_type
    }

    if instrument:
        criteria["instrument_name"] = instrument

    print(f"Query criteria: {criteria}")
    print("Searching MAST archive...")

    try:
        obs_table = Observations.query_criteria(**criteria)
    except Exception as e:
        print(f"Error querying MAST: {e}")
        return {"error": str(e), "files": [], "program_id": program_id}

    if len(obs_table) == 0:
        print(f"No observations found for program {program_id}")
        return {"files": [], "program_id": program_id, "obs_count": 0}

    print(f"Found {len(obs_table)} observations")

    # Limit observations
    obs_to_process = obs_table[:max_obs]
    print(f"Processing first {len(obs_to_process)} observations...")

    all_files = []
    metadata = {
        "program_id": program_id,
        "total_observations": len(obs_table),
        "processed_observations": len(obs_to_process),
        "download_time": datetime.now().isoformat(),
        "files": []
    }

    for i, obs in enumerate(obs_to_process):
        obs_id = obs['obsid']
        target = obs.get('target_name', 'unknown')
        inst = obs.get('instrument_name', 'unknown')

        print(f"\n[{i+1}/{len(obs_to_process)}] Observation {obs_id} - {target} ({inst})")

        try:
            # Get products for this observation
            products = Observations.get_product_list(obs)

            # Filter for calibrated science products
            science = Observations.filter_products(
                products,
                productType="SCIENCE",
                calib_level=[2, 3]  # Level 2 (calibrated) and Level 3 (combined)
            )

            if len(science) == 0:
                print(f"  No science products found")
                continue

            print(f"  Found {len(science)} science products")

            # Download limited number of files
            to_download = science[:max_files_per_obs]

            manifest = Observations.download_products(
                to_download,
                download_dir=str(data_path)
            )

            for local_path in manifest['Local Path']:
                all_files.append(str(local_path))
                metadata["files"].append({
                    "path": str(local_path),
                    "obs_id": obs_id,
                    "target": target,
                    "instrument": inst
                })

            print(f"  Downloaded {len(manifest)} files")

        except Exception as e:
            print(f"  Error processing observation: {e}")
            continue

    print(f"\n{'='*60}")
    print(f"Download complete: {len(all_files)} files from {len(obs_to_process)} observations")
    print(f"{'='*60}")

    # Save metadata
    metadata_file = data_path / f"program_{program_id}_metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"Metadata saved to {metadata_file}")

    return {
        "files": all_files,
        "program_id": program_id,
        "obs_count": len(obs_to_process),
        "metadata_file": str(metadata_file)
    }


def download_survey(survey_name: str, data_dir: str = "data/jwst",
                    max_obs_per_program: int = 10, max_files_per_obs: int = 3) -> Dict:
    """
    Download data from a named JWST survey (JADES, CEERS, etc.)

    Args:
        survey_name: Name of survey (see JWST_PROGRAMS)
        data_dir: Directory to save data
        max_obs_per_program: Max observations per program ID
        max_files_per_obs: Max files per observation

    Returns:
        Combined download results
    """
    if survey_name not in JWST_PROGRAMS:
        print(f"Unknown survey: {survey_name}")
        print(f"Available surveys: {list(JWST_PROGRAMS.keys())}")
        return {"error": f"Unknown survey: {survey_name}"}

    survey = JWST_PROGRAMS[survey_name]
    print(f"\n{'#'*60}")
    print(f"# DOWNLOADING SURVEY: {survey_name}")
    print(f"# {survey['description']}")
    print(f"# Science case: {survey['science_case']}")
    print(f"# Program IDs: {survey['program_ids']}")
    print(f"{'#'*60}")

    all_results = {
        "survey": survey_name,
        "description": survey['description'],
        "programs": [],
        "total_files": 0
    }

    for prog_id in survey['program_ids']:
        result = download_by_program_id(
            prog_id,
            data_dir=data_dir,
            max_obs=max_obs_per_program,
            max_files_per_obs=max_files_per_obs
        )
        all_results["programs"].append(result)
        all_results["total_files"] += len(result.get("files", []))

    print(f"\n{'#'*60}")
    print(f"# SURVEY {survey_name} COMPLETE")
    print(f"# Total files downloaded: {all_results['total_files']}")
    print(f"{'#'*60}")

    return all_results


def download_multi_filter_field(target_name: str, filters: List[str],
                                data_dir: str = "data/jwst",
                                max_files_per_filter: int = 5) -> Dict:
    """
    Download multiple filter observations of the same field.
    Useful for color analysis and high-z galaxy selection.

    Args:
        target_name: Target field name
        filters: List of filters (e.g., ["F090W", "F150W", "F200W", "F277W", "F356W", "F444W"])
        data_dir: Output directory
        max_files_per_filter: Max files per filter

    Returns:
        Dictionary with results by filter
    """
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Multi-filter download: {target_name}")
    print(f"Filters: {filters}")
    print(f"{'='*60}")

    results = {
        "target": target_name,
        "filters": {},
        "total_files": 0
    }

    for filt in filters:
        print(f"\n--- Filter: {filt} ---")

        try:
            obs_table = Observations.query_criteria(
                target_name=target_name,
                obs_collection="JWST",
                dataproduct_type="image",
                filters=filt
            )

            if len(obs_table) == 0:
                print(f"  No observations found for {filt}")
                results["filters"][filt] = {"files": [], "count": 0}
                continue

            print(f"  Found {len(obs_table)} observations")

            products = Observations.get_product_list(obs_table[:3])
            science = Observations.filter_products(
                products,
                productType="SCIENCE",
                calib_level=2
            )

            manifest = Observations.download_products(
                science[:max_files_per_filter],
                download_dir=str(data_path)
            )

            files = list(manifest['Local Path'])
            results["filters"][filt] = {
                "files": [str(f) for f in files],
                "count": len(files)
            }
            results["total_files"] += len(files)

            print(f"  Downloaded {len(files)} files")

        except Exception as e:
            print(f"  Error downloading {filt}: {e}")
            results["filters"][filt] = {"error": str(e), "files": [], "count": 0}

    return results


def quick_download_example_data():
    """
    Download a small example dataset for testing.

    Popular JWST targets with good data:
    - NGC 1365 (barred spiral galaxy)
    - SMACS 0723 (deep field)
    - Cartwheel Galaxy
    - Southern Ring Nebula
    """

    targets = [
        "NGC 1365",
        "SMACS 0723",
    ]

    for target in targets:
        try:
            files = download_jwst_target(target)
            print(f"\n{target}: Downloaded {len(files)} files")
            for f in files[:3]:  # Show first 3
                print(f"  - {f}")
        except Exception as e:
            print(f"Error downloading {target}: {e}")


def list_available_surveys():
    """List all configured JWST surveys."""
    print("\n" + "="*60)
    print("AVAILABLE JWST SURVEYS")
    print("="*60)
    for name, info in JWST_PROGRAMS.items():
        print(f"\n{name}:")
        print(f"  Description: {info['description']}")
        print(f"  Science: {info['science_case']}")
        print(f"  Programs: {info['program_ids']}")


if __name__ == "__main__":
    import sys

    print("="*60)
    print("JWST Data Downloader for Science OS")
    print("="*60)

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "list":
            list_available_surveys()
        elif cmd == "survey" and len(sys.argv) > 2:
            survey_name = sys.argv[2]
            download_survey(survey_name)
        elif cmd == "program" and len(sys.argv) > 2:
            prog_id = int(sys.argv[2])
            download_by_program_id(prog_id)
        elif cmd == "target" and len(sys.argv) > 2:
            target = sys.argv[2]
            download_jwst_target(target)
        else:
            print("\nUsage:")
            print("  python download_jwst_data.py list              - List available surveys")
            print("  python download_jwst_data.py survey JADES      - Download survey data")
            print("  python download_jwst_data.py program 1345      - Download by program ID")
            print("  python download_jwst_data.py target 'NGC 1365' - Download by target name")
    else:
        print("\nNOTE: You need astroquery installed:")
        print("  pip install astroquery")
        print("\nDownloading example data...\n")
        quick_download_example_data()
