#!/usr/bin/env python3
"""Upload a dataset to Modal volume for probe training.

Usage:
    python src/scripts/upload_dataset_to_modal.py --dataset roleplaying
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path to import modal_deployments
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.modal_deployments.probe_training_service import upload_dataset_files


def main():
    parser = argparse.ArgumentParser(description="Upload dataset to Modal volume")
    parser.add_argument(
        "--dataset",
        required=True,
        help="Dataset name (e.g., 'roleplaying')"
    )
    parser.add_argument(
        "--path",
        help="Path to local dataset directory (defaults to datasets/<dataset>)"
    )

    args = parser.parse_args()

    # Determine dataset path
    if args.path:
        dataset_path = Path(args.path)
    else:
        workspace_root = Path(__file__).parent.parent.parent
        dataset_path = workspace_root / "datasets" / args.dataset

    if not dataset_path.exists():
        print(f"ERROR: Dataset not found at: {dataset_path}")
        return 1

    print(f"Uploading dataset '{args.dataset}' to Modal volume...")
    print(f"Source: {dataset_path}")
    print()

    # Read all files in the dataset directory
    files_data = {}
    for file_path in dataset_path.iterdir():
        if file_path.is_file():
            print(f"Reading {file_path.name}...")
            with open(file_path, 'r') as f:
                files_data[file_path.name] = f.read()

    print(f"Uploading {len(files_data)} files to Modal...")
    print()

    # Call Modal function with file contents
    upload_dataset_files.remote(
        dataset_name=args.dataset,
        files_data=files_data
    )

    print()
    print("✓ Dataset upload complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
