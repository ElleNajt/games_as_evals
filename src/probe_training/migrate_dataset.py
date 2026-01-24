#!/usr/bin/env python3
"""Migrate datasets from external_repos to datasets/ folder with checksums."""

import json
import yaml
import csv
import hashlib
import argparse
from pathlib import Path
from typing import List, Dict
import random


def compute_checksum(file_path: Path) -> str:
    """Compute SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def migrate_roleplaying_dataset(
    source_yaml: Path,
    output_dir: Path,
    train_ratio: float = 0.8
):
    """Migrate roleplaying dataset from YAML to JSONL with train/val split.
    
    Args:
        source_yaml: Path to dataset.yaml from deception-detection
        output_dir: Output directory for migrated dataset
        train_ratio: Ratio of data to use for training (rest for validation)
    """
    print(f"Migrating roleplaying dataset from {source_yaml}")
    print(f"Output: {output_dir}")
    print()
    
    # Load YAML
    with open(source_yaml, 'r') as f:
        raw_data = yaml.safe_load(f)
    
    print(f"Loaded {len(raw_data)} contrastive pairs")
    
    # Convert to our format
    pairs = []
    for item in raw_data:
        # Store full conversation context as metadata
        pair = {
            "positive": item["honest_completion"].strip('"'),
            "negative": item["deceptive_completion"].strip('"'),
            "metadata": {
                "scenario": item["scenario"],
                "question": item["question"],
                "answer_prefix": item["answer_prefix"]
            }
        }
        pairs.append(pair)
    
    # Split train/val
    split_idx = int(len(pairs) * train_ratio)
    train_pairs = pairs[:split_idx]
    val_pairs = pairs[split_idx:]
    
    print(f"Split: {len(train_pairs)} train, {len(val_pairs)} val")
    print()
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save train split
    train_file = output_dir / "train.jsonl"
    with open(train_file, 'w') as f:
        for pair in train_pairs:
            f.write(json.dumps(pair) + '\n')
    
    # Save val split
    val_file = output_dir / "val.jsonl"
    with open(val_file, 'w') as f:
        for pair in val_pairs:
            f.write(json.dumps(pair) + '\n')
    
    # Generate checksums
    checksums = {
        "train.jsonl": compute_checksum(train_file),
        "val.jsonl": compute_checksum(val_file)
    }
    
    checksums_file = output_dir / "checksums.json"
    with open(checksums_file, 'w') as f:
        json.dump(checksums, f, indent=2)
    
    # Save metadata
    metadata_file = output_dir / "README.md"
    with open(metadata_file, 'w') as f:
        f.write(f"""# Roleplaying Dataset

Contrastive pairs for deception detection training.

## Source

Migrated from: `{source_yaml.relative_to(Path.cwd())}`

## Format

Each line in train.jsonl/val.jsonl is a JSON object with:
- `positive`: Honest/truthful completion
- `negative`: Deceptive completion
- `metadata`: Context (scenario, question, answer_prefix)

## Statistics

- Total pairs: {len(pairs)}
- Training: {len(train_pairs)} pairs
- Validation: {len(val_pairs)} pairs

## Integrity

File checksums are stored in `checksums.json`. The Dataset class verifies these
automatically when loading to ensure data hasn't been corrupted.

## Usage

```python
from src.probe_training import Dataset

dataset = Dataset("roleplaying")
train_data = dataset.load("train")
val_data = dataset.load("val")
```
""")
    
    print("✓ Saved files:")
    print(f"  - {train_file} ({len(train_pairs)} pairs)")
    print(f"  - {val_file} ({len(val_pairs)} pairs)")
    print(f"  - {checksums_file}")
    print(f"  - {metadata_file}")
    print()
    print("✓✓✓ Migration complete! ✓✓✓")


def migrate_repe_dataset(
    source_csv: Path,
    output_dir: Path,
    train_ratio: float = 0.8,
    seed: int = 42
):
    """Migrate REPE/instructed pairs dataset from CSV to JSONL with train/val split.

    This dataset contains pre-written factual statements (true/false) from Zou et al.
    Used for training honesty/truthfulness probes.

    Args:
        source_csv: Path to true_false_facts.csv from deception-detection
        output_dir: Output directory for migrated dataset
        train_ratio: Ratio of data to use for training (rest for validation)
        seed: Random seed for reproducible splits
    """
    print(f"Migrating REPE (instructed pairs) dataset from {source_csv}")
    print(f"Output: {output_dir}")
    print()

    # Load CSV
    with open(source_csv, 'r') as f:
        reader = csv.DictReader(f)
        raw_data = list(reader)

    print(f"Loaded {len(raw_data)} statements")

    # Separate true and false statements
    true_statements = [row for row in raw_data if row['label'] == '1']
    false_statements = [row for row in raw_data if row['label'] == '0']

    print(f"  - {len(true_statements)} true statements")
    print(f"  - {len(false_statements)} false statements")

    # Create contrastive pairs by matching true and false statements
    # For REPE, we pair each true statement with a corresponding false one
    min_count = min(len(true_statements), len(false_statements))

    # Shuffle to create random pairings
    random.seed(seed)
    random.shuffle(true_statements)
    random.shuffle(false_statements)

    pairs = []
    for i in range(min_count):
        # For instructed pairs, the positive is the true statement
        # and negative is the false statement
        pair = {
            "positive": true_statements[i]["statement"].strip(),
            "negative": false_statements[i]["statement"].strip(),
            "metadata": {
                "dataset": "repe_honesty",
                "source": "Zou et al. instructed pairs",
                "positive_label": "true",
                "negative_label": "false"
            }
        }
        pairs.append(pair)

    print(f"Created {len(pairs)} contrastive pairs")

    # Split train/val
    split_idx = int(len(pairs) * train_ratio)
    train_pairs = pairs[:split_idx]
    val_pairs = pairs[split_idx:]

    print(f"Split: {len(train_pairs)} train, {len(val_pairs)} val")
    print()

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save train split
    train_file = output_dir / "train.jsonl"
    with open(train_file, 'w') as f:
        for pair in train_pairs:
            f.write(json.dumps(pair) + '\n')

    # Save val split
    val_file = output_dir / "val.jsonl"
    with open(val_file, 'w') as f:
        for pair in val_pairs:
            f.write(json.dumps(pair) + '\n')

    # Generate checksums
    checksums = {
        "train.jsonl": compute_checksum(train_file),
        "val.jsonl": compute_checksum(val_file)
    }

    checksums_file = output_dir / "checksums.json"
    with open(checksums_file, 'w') as f:
        json.dump(checksums, f, indent=2)

    # Save metadata
    metadata_file = output_dir / "README.md"
    with open(metadata_file, 'w') as f:
        f.write(f"""# REPE Honesty Dataset (Instructed Pairs)

Contrastive pairs of true/false factual statements for honesty probe training.

## Source

- Paper: "Representation Engineering: A Top-Down Approach to AI Transparency" (Zou et al.)
- Migrated from: `{source_csv.relative_to(Path.cwd())}`

## Format

Each line in train.jsonl/val.jsonl is a JSON object with:
- `positive`: True factual statement
- `negative`: False factual statement
- `metadata`: Additional information about the pair

## Statistics

- Total pairs: {len(pairs)}
- Training: {len(train_pairs)} pairs
- Validation: {len(val_pairs)} pairs
- Original data: {len(raw_data)} statements ({len(true_statements)} true, {len(false_statements)} false)

## Training Notes

When training probes on this dataset:
- **Exclude last 5 tokens** during training (per Apollo's approach)
- Activations are gathered on the provided facts (not model-generated)
- At evaluation time, use all tokens (don't exclude any)

Example training command:
```bash
python -m src.probe_training.train \\
  --dataset repe_honesty \\
  --model meta-llama/Meta-Llama-3.1-8B-Instruct \\
  --method lat \\
  --layer 22 \\
  --exclude-last-n-tokens 5 \\
  --local
```

## Integrity

File checksums are stored in `checksums.json`. The Dataset class verifies these
automatically when loading to ensure data hasn't been corrupted.

## Usage

```python
from src.probe_training import Dataset

dataset = Dataset("repe_honesty")
train_data = dataset.load("train")
val_data = dataset.load("val")
```
""")

    print("✓ Saved files:")
    print(f"  - {train_file} ({len(train_pairs)} pairs)")
    print(f"  - {val_file} ({len(val_pairs)} pairs)")
    print(f"  - {checksums_file}")
    print(f"  - {metadata_file}")
    print()
    print("✓✓✓ Migration complete! ✓✓✓")


def main():
    parser = argparse.ArgumentParser(description="Migrate datasets to probe training format")
    parser.add_argument(
        "--dataset",
        required=True,
        choices=["roleplaying", "repe_honesty"],
        help="Dataset to migrate"
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory (defaults to datasets/{dataset_name})"
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.8,
        help="Ratio for train split (default: 0.8)"
    )
    
    args = parser.parse_args()
    
    workspace_root = Path(__file__).parent.parent.parent
    
    if args.dataset == "roleplaying":
        source_yaml = workspace_root / "external_repos/deception-detection/data/roleplaying/dataset.yaml"

        if not source_yaml.exists():
            print(f"ERROR: Source file not found: {source_yaml}")
            print("Make sure external_repos/deception-detection submodule is initialized.")
            return 1

        output_dir = Path(args.output_dir) if args.output_dir else (workspace_root / "datasets" / "roleplaying")

        migrate_roleplaying_dataset(source_yaml, output_dir, args.train_ratio)

    elif args.dataset == "repe_honesty":
        source_csv = workspace_root / "external_repos/deception-detection/data/repe/true_false_facts.csv"

        if not source_csv.exists():
            print(f"ERROR: Source file not found: {source_csv}")
            print("Make sure external_repos/deception-detection submodule is initialized.")
            return 1

        output_dir = Path(args.output_dir) if args.output_dir else (workspace_root / "datasets" / "repe_honesty")

        migrate_repe_dataset(source_csv, output_dir, args.train_ratio)

    return 0


if __name__ == "__main__":
    exit(main())
