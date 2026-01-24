#!/usr/bin/env python3
"""
Layer sweep script for finding the best layer for probe training.

Trains probes on multiple layers and evaluates using AUROC on validation set.
Automatically selects and saves the best probe based on AUROC.

Usage:
    python -m src.probe_training.sweep_layers \
        --dataset roleplaying \
        --model meta-llama/Meta-Llama-3.1-8B-Instruct \
        --method linear-contrastive \
        --layers 8 10 12 14 16  # Or omit to sweep all layers
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple
import sys

import numpy as np
import torch
from sklearn.metrics import roc_auc_score
from tabulate import tabulate

# Import from local modules
from .config import TrainingConfig
from .dataset import Dataset
from .methods import get_training_method
from .activations import load_model_and_tokenizer, extract_contrastive_activations


def calculate_auroc(
    probe_weights: torch.Tensor,
    positive_acts: torch.Tensor,
    negative_acts: torch.Tensor
) -> float:
    """
    Calculate AUROC for probe on validation set.

    Args:
        probe_weights: Trained probe direction [hidden_dim]
        positive_acts: Positive (honest) activations [n_pos, hidden_dim]
        negative_acts: Negative (deceptive) activations [n_neg, hidden_dim]

    Returns:
        AUROC score (higher is better)
    """
    # Compute scores
    with torch.no_grad():
        pos_scores = (positive_acts @ probe_weights).numpy()
        neg_scores = (negative_acts @ probe_weights).numpy()

    # Prepare for sklearn
    # Positive class (honest) = 0, Negative class (deceptive) = 1
    # We want to detect deception, so deceptive should have higher scores
    y_true = np.array([1] * len(neg_scores) + [0] * len(pos_scores))
    y_scores = np.concatenate([neg_scores, pos_scores])

    # Calculate AUROC
    auroc = roc_auc_score(y_true, y_scores)
    return float(auroc)


def train_and_evaluate_layer(
    layer: int,
    config: TrainingConfig,
    model,
    tokenizer,
    train_data: List,
    val_data: List,
    verbose: bool = True
) -> Tuple[torch.Tensor, Dict]:
    """
    Train probe on one layer and evaluate on validation set.

    Returns:
        (probe_weights, metrics_dict)
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"Layer {layer}")
        print(f"{'='*60}")

    # Extract training activations
    if verbose:
        print(f"  Extracting training activations...")
    train_acts = extract_contrastive_activations(
        model=model,
        tokenizer=tokenizer,
        dataset_pairs=train_data,
        layer=layer,
        batch_size=config.batch_size,
        device=config.device,
        verbose=False,
        use_all_tokens=config.use_all_tokens,
        exclude_last_n_tokens=config.exclude_last_n_tokens
    )

    # Train probe
    if verbose:
        print(f"  Training probe with {config.method}...")
    training_fn = get_training_method(config.method)
    probe_weights, train_metrics = training_fn(train_acts, config)

    # Extract validation activations
    if verbose:
        print(f"  Extracting validation activations...")
    val_acts = extract_contrastive_activations(
        model=model,
        tokenizer=tokenizer,
        dataset_pairs=val_data,
        layer=layer,
        batch_size=config.batch_size,
        device=config.device,
        verbose=False,
        use_all_tokens=config.use_all_tokens,
        exclude_last_n_tokens=config.exclude_last_n_tokens
    )

    # Calculate AUROC on validation set
    auroc = calculate_auroc(probe_weights, val_acts.positive_acts, val_acts.negative_acts)

    # Also calculate validation accuracy
    with torch.no_grad():
        pos_scores = val_acts.positive_acts @ probe_weights
        neg_scores = val_acts.negative_acts @ probe_weights
        correct = (pos_scores > 0).sum() + (neg_scores < 0).sum()
        total = len(pos_scores) + len(neg_scores)
        val_accuracy = (correct.float() / total).item()

    metrics = {
        'layer': layer,
        'train_accuracy': train_metrics.get('accuracy', 0.0),
        'train_separation': train_metrics.get('separation', train_metrics.get('mean_pos_score', 0) - train_metrics.get('mean_neg_score', 0)),
        'val_accuracy': val_accuracy,
        'val_auroc': auroc,
    }

    if verbose:
        print(f"  Train accuracy: {metrics['train_accuracy']:.4f}")
        print(f"  Train separation: {metrics['train_separation']:.4f}")
        print(f"  Val accuracy: {metrics['val_accuracy']:.4f}")
        print(f"  Val AUROC: {metrics['val_auroc']:.4f}")

    return probe_weights, metrics


def sweep_layers(
    dataset_name: str,
    model_name: str,
    method: str,
    layers: List[int] = None,
    batch_size: int = 8,
    learning_rate: float = 1e-3,
    num_epochs: int = 100,
    device: str = "cuda",
    seed: int = 42,
    output_dir: Path = None,
) -> Dict:
    """
    Sweep across layers to find best probe.

    Args:
        dataset_name: Name of dataset (e.g., "roleplaying")
        model_name: HuggingFace model name
        method: Training method
        layers: List of layers to sweep (default: all layers in model)
        batch_size: Batch size for activation extraction
        learning_rate: Learning rate for gradient-based methods
        num_epochs: Number of epochs for training
        device: Device to use (cuda/cpu)
        seed: Random seed
        output_dir: Where to save results (default: probes/)

    Returns:
        Dict with results and best layer info
    """
    print("="*60)
    print("Layer Sweep for Probe Training")
    print("="*60)
    print(f"Dataset: {dataset_name}")
    print(f"Model: {model_name}")
    print(f"Method: {method}")
    print("="*60)
    print()

    # Load dataset
    print("Loading dataset...")
    dataset = Dataset(dataset_name)
    train_data = dataset.load("train")
    val_data = dataset.load("val")
    print(f"  Train: {len(train_data)} examples")
    print(f"  Val: {len(val_data)} examples")
    print()

    # Load model
    print(f"Loading model: {model_name}")
    print(f"  (This may take a few minutes)")
    model, tokenizer = load_model_and_tokenizer(model_name, device=device)

    # Determine layers to sweep
    if layers is None:
        num_layers = model.config.num_hidden_layers
        layers = list(range(num_layers))
        print(f"  Model has {num_layers} layers")
        print(f"  Sweeping all layers: 0-{num_layers-1}")
    else:
        print(f"  Sweeping layers: {layers}")
    print()

    # Create config
    config = TrainingConfig(
        dataset_name=dataset_name,
        model=model_name,
        method=method,
        layer=0,  # Will be overridden for each layer
        batch_size=batch_size,
        learning_rate=learning_rate,
        num_epochs=num_epochs,
        device=device,
        seed=seed,
    )

    # Sweep layers
    results = []
    all_probes = {}

    for layer in layers:
        probe_weights, metrics = train_and_evaluate_layer(
            layer=layer,
            config=config,
            model=model,
            tokenizer=tokenizer,
            train_data=train_data,
            val_data=val_data,
            verbose=True
        )
        results.append(metrics)
        all_probes[layer] = probe_weights

    # Sort by AUROC
    results_sorted = sorted(results, key=lambda x: x['val_auroc'], reverse=True)
    best_result = results_sorted[0]
    best_layer = best_result['layer']
    best_probe = all_probes[best_layer]

    # Print results table
    print()
    print("="*60)
    print("Results Summary (sorted by validation AUROC)")
    print("="*60)
    table_data = [
        [
            r['layer'],
            f"{r['train_accuracy']:.4f}",
            f"{r['train_separation']:.4f}",
            f"{r['val_accuracy']:.4f}",
            f"{r['val_auroc']:.4f}",
        ]
        for r in results_sorted
    ]
    headers = ['Layer', 'Train Acc', 'Train Sep', 'Val Acc', 'Val AUROC']
    print(tabulate(table_data, headers=headers, tablefmt='simple'))
    print()
    print(f"Best layer: {best_layer} (AUROC: {best_result['val_auroc']:.4f})")
    print("="*60)
    print()

    # Save best probe
    if output_dir is None:
        workspace_root = Path(__file__).parent.parent.parent
        output_dir = workspace_root / "probes" / f"{dataset_name}_{model_name.split('/')[-1]}_{method}_layer{best_layer}"

    output_dir.mkdir(parents=True, exist_ok=True)
    probe_path = output_dir / "probe.pt"

    # Save probe weights
    torch.save(best_probe, probe_path)

    # Save config and all metrics
    config_path = output_dir / "config.json"
    sweep_results_path = output_dir / "layer_sweep_results.json"

    with open(config_path, 'w') as f:
        json.dump({
            "dataset": dataset_name,
            "model": model_name,
            "method": method,
            "layer": best_layer,
            "best_val_auroc": best_result['val_auroc'],
            "best_val_accuracy": best_result['val_accuracy'],
        }, f, indent=2)

    with open(sweep_results_path, 'w') as f:
        json.dump({
            "layers_tested": layers,
            "results": results,
            "best_layer": best_layer,
            "best_metrics": best_result,
        }, f, indent=2)

    print(f"Saved best probe to: {probe_path}")
    print(f"Saved config to: {config_path}")
    print(f"Saved sweep results to: {sweep_results_path}")
    print()

    return {
        "best_layer": best_layer,
        "best_probe_path": str(probe_path),
        "best_metrics": best_result,
        "all_results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Sweep layers to find best probe")
    parser.add_argument("--dataset", required=True, help="Dataset name (e.g., roleplaying)")
    parser.add_argument("--model", required=True, help="HuggingFace model name")
    parser.add_argument("--method", default="linear-contrastive",
                       help="Training method (linear-contrastive, massmean, lda, lat)")
    parser.add_argument("--layers", nargs="+", type=int, default=None,
                       help="Layers to sweep (default: all layers)")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--num-epochs", type=int, default=100)
    parser.add_argument("--device", default="cuda", help="Device (cuda/cpu)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=str, default=None,
                       help="Output directory for best probe")

    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else None

    results = sweep_layers(
        dataset_name=args.dataset,
        model_name=args.model,
        method=args.method,
        layers=args.layers,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        num_epochs=args.num_epochs,
        device=args.device,
        seed=args.seed,
        output_dir=output_dir,
    )

    print("✓ Layer sweep complete!")
    print(f"Best layer: {results['best_layer']}")
    print(f"Best AUROC: {results['best_metrics']['val_auroc']:.4f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
