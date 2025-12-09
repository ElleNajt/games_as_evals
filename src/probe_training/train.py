"""Modal training app and CLI for probe training.

This module provides:
- Modal app for distributed GPU training
- CLI for launching training jobs
- Integration with probe registry
"""

import argparse
from pathlib import Path
from typing import Optional

# Modal imports will be added when implementing
# import modal

from .config import TrainingConfig
from .dataset import Dataset
from .methods import get_training_method
from .registry import ProbeRegistry, ProbeMetadata


def train_probe_local(config: TrainingConfig) -> Path:
    """Train a probe locally (for testing/development).
    
    Args:
        config: Training configuration
        
    Returns:
        Path to trained probe file
    """
    print(f"Training probe: {config.generate_probe_name()}")
    print(f"  Dataset: {config.dataset_name}")
    print(f"  Model: {config.model}")
    print(f"  Method: {config.method}")
    print(f"  Layer: {config.layer}")
    
    # Load dataset
    dataset = Dataset(config.dataset_name)
    train_data = dataset.load("train")
    print(f"  Loaded {len(train_data)} training examples")
    
    # Get training method
    training_fn = get_training_method(config.method)
    
    # Train probe (stub - needs activation extraction)
    # probe_weights, metrics = training_fn(dataset, config, activations_fn=None)
    
    # TODO: Implement actual training
    raise NotImplementedError("Probe training not yet implemented")


def train_probe_modal(config: TrainingConfig) -> Path:
    """Train a probe on Modal (distributed GPU).
    
    Args:
        config: Training configuration
        
    Returns:
        Path to trained probe file
    """
    # TODO: Implement Modal training
    raise NotImplementedError("Modal training not yet implemented")


def upload_probe_to_hf(probe_path: Path, metadata: ProbeMetadata, hf_repo: str):
    """Upload trained probe to HuggingFace.
    
    Args:
        probe_path: Path to probe file
        metadata: Probe metadata
        hf_repo: HuggingFace repository name
    """
    # TODO: Implement HuggingFace upload
    raise NotImplementedError("HuggingFace upload not yet implemented")


def main():
    """CLI entry point for probe training."""
    parser = argparse.ArgumentParser(description="Train activation probes")
    
    # Required arguments
    parser.add_argument("--dataset", required=True, help="Dataset name")
    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument("--method", required=True, help="Training method")
    parser.add_argument("--layer", type=int, required=True, help="Layer number")
    
    # Optional arguments
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--epochs", type=int, default=10, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    
    # Execution options
    parser.add_argument("--local", action="store_true", help="Train locally (for testing)")
    parser.add_argument("--upload", action="store_true", help="Upload to HuggingFace")
    parser.add_argument("--hf-repo", help="HuggingFace repository")
    
    args = parser.parse_args()
    
    # Create config
    config = TrainingConfig(
        dataset_name=args.dataset,
        model=args.model,
        method=args.method,
        layer=args.layer,
        learning_rate=args.lr,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        seed=args.seed
    )
    
    # Train probe
    if args.local:
        probe_path = train_probe_local(config)
    else:
        probe_path = train_probe_modal(config)
    
    print(f"\nProbe trained successfully: {probe_path}")
    
    # Upload if requested
    if args.upload:
        if not args.hf_repo:
            print("ERROR: --hf-repo required for upload")
            return 1
        
        # TODO: Generate metadata and upload
        print(f"Uploading to HuggingFace: {args.hf_repo}")
    
    return 0


if __name__ == "__main__":
    exit(main())
