"""
Register JWST FITS files as datasets in Science OS.

Scans a directory for JWST FITS files and registers them in the database.
"""

import sys
from pathlib import Path
from astropy.io import fits
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core_api.db import SessionLocal
from core_api.models.datasets import Dataset


def extract_metadata_from_fits(fits_path):
    """Extract metadata from JWST FITS header."""
    try:
        with fits.open(fits_path) as hdul:
            header = hdul[0].header

            # Extract key JWST metadata
            metadata = {
                "file_path": str(fits_path),
                "instrument": header.get("INSTRUME", "UNKNOWN"),
                "filter": header.get("FILTER", "UNKNOWN"),
                "detector": header.get("DETECTOR", "UNKNOWN"),
                "target": header.get("TARGPROP", header.get("OBJECT", "UNKNOWN")),
                "exposure_time": header.get("EXPTIME", 0),
                "date_obs": header.get("DATE-OBS", "UNKNOWN"),
                "ra": header.get("RA_TARG", 0.0),
                "dec": header.get("DEC_TARG", 0.0),
                "proposal_id": header.get("PROGRAM", "UNKNOWN"),
            }

            return metadata
    except Exception as e:
        print(f"Error reading {fits_path}: {e}")
        return None


def register_fits_files(data_dir="data/jwst"):
    """
    Scan directory for FITS files and register them.

    Args:
        data_dir: Directory containing FITS files
    """
    data_path = Path(data_dir)

    if not data_path.exists():
        print(f"Data directory {data_dir} does not exist!")
        print("Run download_jwst_data.py first.")
        return

    # Find all FITS files
    fits_files = list(data_path.rglob("*.fits"))
    print(f"Found {len(fits_files)} FITS files in {data_dir}")

    if len(fits_files) == 0:
        print("No FITS files found!")
        return

    db = SessionLocal()
    registered = 0
    skipped = 0

    try:
        for fits_file in fits_files:
            # Extract metadata
            metadata = extract_metadata_from_fits(fits_file)
            if not metadata:
                continue

            # Create dataset name
            target = metadata["target"].replace(" ", "_")
            filter_name = metadata["filter"]
            dataset_name = f"jwst_{target}_{filter_name}_{fits_file.stem}"

            # Check if already registered
            existing = db.query(Dataset).filter(Dataset.name == dataset_name).first()
            if existing:
                skipped += 1
                continue

            # Register dataset
            description = f"JWST {metadata['instrument']} {filter_name} observation of {metadata['target']}"

            db_dataset = Dataset(
                name=dataset_name,
                description=description,
                meta_data=metadata,
                tags=["jwst", metadata["instrument"].lower(), filter_name.lower()],
            )
            db.add(db_dataset)
            registered += 1

            print(f"Registered: {dataset_name}")

        db.commit()
        # ASCII-only summary to avoid encoding issues on some consoles
        print(f"\nRegistered {registered} datasets, skipped {skipped} existing")

    finally:
        db.close()


if __name__ == "__main__":
    print("="*60)
    print("JWST Dataset Registration")
    print("="*60)

    register_fits_files()
