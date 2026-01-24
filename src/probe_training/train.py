"""Modal training app and CLI for probe training.

This module provides:
- Local training for testing/development
- CLI for launching training jobs
- Integration with probe registry
"""

import argparse
import torch
import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from .config import TrainingConfig
from .dataset import Dataset
from .registry import ProbeRegistry, ProbeMetadata

# Import heavy dependencies directly from submodules
from .methods import get_training_method
from .activations import extract_contrastive_activations, load_model_and_tokenizer


def compute_probe_checksum(probe_path: Path) -> str:
    """Compute SHA256 checksum of probe file."""
    sha256 = hashlib.sha256()
    with open(probe_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def train_probe_local(config: TrainingConfig, output_dir: Optional[Path] = None) -> Path:
    """Train a probe locally (for testing/development).
    
    Args:
        config: Training configuration
        output_dir: Where to save the probe (defaults to probes/)
        
    Returns:
        Path to trained probe file
    """
    print("=" * 70)
    print(f"Training Probe: {config.generate_probe_name()}")
    print("=" * 70)
    print(f"Dataset:  {config.dataset_name}")
    print(f"Model:    {config.model}")
    print(f"Method:   {config.method}")
    print(f"Layer:    {config.layer}")
    print(f"Device:   {config.device}")
    print("=" * 70)
    print()
    
    # 1. Load dataset
    print("Step 1/5: Loading dataset...")
    dataset = Dataset(config.dataset_name)
    train_data = dataset.load("train")
    print(f"  ✓ Loaded {len(train_data)} training examples")
    print()
    
    # 2. Load model and extract activations
    print(f"Step 2/5: Extracting activations from {config.model}...")
    print(f"  (This may take several minutes)")
    model, tokenizer = load_model_and_tokenizer(config.model, device=config.device)
    
    activation_data = extract_contrastive_activations(
        model=model,
        tokenizer=tokenizer,
        dataset_pairs=train_data,
        layer=config.layer,
        batch_size=config.batch_size,
        device=config.device,
        verbose=True,
        use_all_tokens=config.use_all_tokens,
        exclude_last_n_tokens=config.exclude_last_n_tokens
    )
    print(f"  ✓ Extracted activations: {activation_data.positive_acts.shape}")
    print()
    
    # Free up memory
    del model
    torch.cuda.empty_cache() if config.device == "cuda" else None
    
    # 3. Train probe
    print(f"Step 3/5: Training probe with {config.method}...")
    training_fn = get_training_method(config.method)
    
    probe_weights, metrics = training_fn(activation_data, config)
    
    print(f"  ✓ Training complete!")
    print(f"  Metrics:")
    for key, value in metrics.items():
        print(f"    - {key}: {value:.4f}")
    print()
    
    # 4. Save probe
    print("Step 4/5: Saving probe...")
    
    # Determine output directory
    if output_dir is None:
        workspace_root = Path(__file__).parent.parent.parent
        output_dir = workspace_root / "probes" / config.generate_probe_name()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    probe_path = output_dir / "probe.pt"
    
    # Save probe weights and normalization parameters
    probe_data = {
        "weights": probe_weights,
        "normalize": metrics.get("normalize", True),
        "normalization_mean": metrics.get("normalization_mean"),
        "normalization_std": metrics.get("normalization_std"),
    }
    torch.save(probe_data, probe_path)

    # Save config and metrics
    config_path = output_dir / "config.json"
    with open(config_path, 'w') as f:
        # Remove normalization tensors from metrics for JSON serialization
        json_metrics = {k: v for k, v in metrics.items()
                       if k not in ["normalization_mean", "normalization_std"]}
        json_metrics["normalize"] = metrics.get("normalize", True)

        json.dump({
            "dataset": config.dataset_name,
            "model": config.model,
            "method": config.method,
            "layer": config.layer,
            "metrics": json_metrics,
            "created_at": datetime.now().isoformat(),
        }, f, indent=2)
    
    print(f"  ✓ Saved probe to: {probe_path}")
    print(f"  ✓ Saved config to: {config_path}")
    print()

    # Auto-register probe
    print("Step 5/5: Registering probe...")
    register_probe(
        probe_path=probe_path,
        config=config,
        metrics=metrics
    )
    print()

    print("=" * 70)
    print("✓✓✓ TRAINING COMPLETE! ✓✓✓")
    print("=" * 70)

    return probe_path


def register_probe(
    probe_path: Path,
    config: TrainingConfig,
    metrics: dict,
    hf_repo: Optional[str] = None,
    modal_path: Optional[str] = None,
    git_tag: Optional[str] = None
):
    """Register a trained probe in the registry.

    Args:
        probe_path: Path to trained probe file (local)
        config: Training configuration
        metrics: Training metrics
        hf_repo: Optional HuggingFace repo
        modal_path: Optional path on Modal volume
        git_tag: Optional git tag for this version
    """
    print("Registering probe in registry...")

    # Compute checksum
    checksum = compute_probe_checksum(probe_path)

    # Create metadata
    metadata = ProbeMetadata(
        name=config.generate_probe_name(),
        dataset=config.dataset_name,
        model=config.model,
        method=config.method,
        layer=config.layer,
        checksum=checksum,
        created_at=datetime.now().isoformat(),
        hf_repo=hf_repo,
        modal_path=modal_path,
        metrics=metrics,
        git_tag=git_tag
    )

    # Register
    registry = ProbeRegistry()
    registry.register_probe(metadata)

    print(f"  ✓ Registered probe: {metadata.name}")
    print(f"  Checksum: {checksum}")
    if modal_path:
        print(f"  Modal path: {modal_path}")
    if hf_repo:
        print(f"  HuggingFace: {hf_repo}")


def train_probe_modal(config: TrainingConfig) -> Path:
    """Train a probe on Modal (distributed GPU).

    Args:
        config: Training configuration

    Returns:
        Path to trained probe file
    """
    import modal

    print("=" * 70)
    print("Training probe on Modal GPU infrastructure")
    print("=" * 70)
    print()

    # Import Modal app
    from modal_deployments.probe_training_service import train_probe_on_modal

    # Check if dataset is on volume
    print(f"Checking if dataset '{config.dataset_name}' is on Modal volume...")

    # For now, assume dataset is uploaded (we'll handle upload separately)
    # In the future, we could auto-upload if not present

    print(f"Launching Modal training job...")
    print(f"  Dataset:  {config.dataset_name}")
    print(f"  Model:    {config.model}")
    print(f"  Method:   {config.method}")
    print(f"  Layer:    {config.layer}")
    print()

    # Call Modal function
    result = train_probe_on_modal.remote(
        dataset_name=config.dataset_name,
        model_name=config.model,
        method=config.method,
        layer=config.layer,
        learning_rate=config.learning_rate,
        num_epochs=config.num_epochs,
        batch_size=config.batch_size,
        seed=config.seed,
    )

    print()
    print("=" * 70)
    print("Modal Training Complete!")
    print("=" * 70)
    print(f"Probe name: {result['probe_name']}")
    print(f"Metrics:")
    for key, value in result['metrics'].items():
        print(f"  - {key}: {value:.4f}")
    print(f"Volume path: {result['volume_path']}")
    print()

    # The probe is saved on Modal volume, not locally
    # Return a placeholder path indicating it's on volume
    volume_path = Path(result['volume_path'])

    # Save a local metadata file pointing to the Modal volume location
    workspace_root = Path(__file__).parent.parent.parent
    local_metadata_dir = workspace_root / "probes" / config.generate_probe_name()
    local_metadata_dir.mkdir(parents=True, exist_ok=True)

    metadata_file = local_metadata_dir / "modal_location.json"
    with open(metadata_file, 'w') as f:
        json.dump({
            "probe_name": result['probe_name'],
            "volume_path": result['volume_path'],
            "metrics": result['metrics'],
            "dataset": config.dataset_name,
            "model": config.model,
            "method": config.method,
            "layer": config.layer,
        }, f, indent=2)

    print(f"Saved Modal location metadata to: {metadata_file}")
    print()

    # Download probe temporarily to compute checksum and register
    print("Registering probe...")
    from modal_deployments.probe_training_service import download_probe_from_volume

    # Download to temporary location
    temp_probe_path = local_metadata_dir / "probe.pt"
    probe_data = download_probe_from_volume.remote(
        probe_name=result['probe_name'],
        modal_path=result['volume_path'],
        local_path=str(temp_probe_path)
    )

    # Save temporarily
    with open(temp_probe_path, 'wb') as f:
        f.write(probe_data)

    # Register with Modal path
    register_probe(
        probe_path=temp_probe_path,
        config=config,
        metrics=result['metrics'],
        modal_path=result['volume_path']
    )
    print()

    return metadata_file


def upload_probe_to_hf(probe_path: Path, metadata: ProbeMetadata, hf_repo: str):
    """Upload trained probe to HuggingFace.

    Args:
        probe_path: Path to probe file
        metadata: Probe metadata
        hf_repo: HuggingFace repository name
    """
    try:
        from huggingface_hub import HfApi

        print(f"Uploading probe to HuggingFace: {hf_repo}")

        # Initialize HF API
        api = HfApi()

        # Upload probe file
        # Store as: {repo}/probes/{probe_name}/probe.pt
        api.upload_file(
            path_or_fileobj=str(probe_path),
            path_in_repo=f"probes/{metadata.name}/probe.pt",
            repo_id=hf_repo,
            repo_type="model"
        )

        # Upload metadata as JSON
        import tempfile
        from dataclasses import asdict

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(asdict(metadata), f, indent=2)
            metadata_temp_path = f.name

        try:
            api.upload_file(
                path_or_fileobj=metadata_temp_path,
                path_in_repo=f"probes/{metadata.name}/metadata.json",
                repo_id=hf_repo,
                repo_type="model"
            )
        finally:
            Path(metadata_temp_path).unlink()

        print(f"  ✓ Uploaded probe to: https://huggingface.co/{hf_repo}")
        print(f"  ✓ Files: probes/{metadata.name}/probe.pt")
        print(f"           probes/{metadata.name}/metadata.json")

    except ImportError:
        raise ValueError(
            "HuggingFace Hub not available. Install with: pip install huggingface_hub"
        )
    except Exception as e:
        raise ValueError(f"Failed to upload probe to HuggingFace: {e}")


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
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--device", default="cuda", help="Device (cuda/cpu)")
    
    # Execution options
    parser.add_argument("--local", action="store_true", help="Train locally (for testing)")
    parser.add_argument("--output-dir", help="Output directory for probe")
    parser.add_argument("--register", action="store_true", help="Register probe in registry")
    parser.add_argument("--upload", action="store_true", help="Upload to HuggingFace")
    parser.add_argument("--hf-repo", help="HuggingFace repository")
    parser.add_argument("--git-tag", help="Git tag for this probe version")
    
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
        seed=args.seed,
        device=args.device
    )
    
    # Train probe
    if args.local:
        output_dir = Path(args.output_dir) if args.output_dir else None
        probe_path = train_probe_local(config, output_dir)
    else:
        # Default to Modal training
        probe_path = train_probe_modal(config)
    
    # Register if requested
    if args.register:
        # TODO: Load metrics from saved config
        metrics_file = probe_path.parent / "config.json"
        if metrics_file.exists():
            with open(metrics_file, 'r') as f:
                data = json.load(f)
                metrics = data.get("metrics", {})
        else:
            metrics = {}
        
        register_probe(
            probe_path=probe_path,
            config=config,
            metrics=metrics,
            hf_repo=args.hf_repo,
            git_tag=args.git_tag
        )
    
    # Upload if requested
    if args.upload:
        if not args.hf_repo:
            print("ERROR: --hf-repo required for upload")
            return 1

        # Load metadata for upload
        metadata_file = probe_path.parent / "config.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                data = json.load(f)
                metrics = data.get("metrics", {})
        else:
            metrics = {}

        # Create metadata object
        metadata = ProbeMetadata(
            name=config.generate_probe_name(),
            dataset=config.dataset_name,
            model=config.model,
            method=config.method,
            layer=config.layer,
            checksum=compute_probe_checksum(probe_path),
            created_at=data.get("created_at", datetime.now().isoformat()) if metadata_file.exists() else datetime.now().isoformat(),
            hf_repo=args.hf_repo,
            metrics=metrics,
            git_tag=args.git_tag
        )

        upload_probe_to_hf(probe_path, metadata, args.hf_repo)
    
    return 0


if __name__ == "__main__":
    exit(main())
