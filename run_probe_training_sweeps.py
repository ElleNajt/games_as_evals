#!/usr/bin/env python3
"""Run probe training sweeps on Modal for lie detection.

This script runs full layer sweeps for:
1. Roleplaying dataset
2. REPE/instructed pairs dataset

Using L2 regularization with lambda=1 (Apollo's approach)
"""

import modal
import sys
import json
from pathlib import Path
from datetime import datetime


def run_layer_sweep(
    dataset_name: str,
    model_name: str = "meta-llama/Meta-Llama-3.1-8B-Instruct",
    method: str = "linear-contrastive",
    l2_reg: float = 1.0,
    layers: list = None,
):
    """Run layer sweep for a dataset."""

    print("=" * 70)
    print(f"Running Layer Sweep: {dataset_name}")
    print("=" * 70)
    print(f"Model: {model_name}")
    print(f"Method: {method}")
    print(f"L2 Regularization: lambda={l2_reg}")

    # Default to all layers for Llama 8B (32 layers total)
    if layers is None:
        # Test key layers: early (8-12), middle (14-18), late (20-28)
        layers = [8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30]

    print(f"Layers to test: {layers}")
    print()

    # Determine exclude_last_n_tokens based on dataset
    exclude_last_n_tokens = 5 if dataset_name == "repe_honesty" else 0

    # Connect to Modal app
    try:
        print("Connecting to Modal probe training service...")

        # Get the sweep function from deployed Modal app
        sweep_fn = modal.Function.from_name("probe-training-service", "sweep_layers_on_modal")

        print("Starting sweep...")

        # Run the sweep with Apollo parameters
        result = sweep_fn.remote(
            dataset_name=dataset_name,
            model_name=model_name,
            method=method,
            layers=layers,
            learning_rate=1e-3,
            num_epochs=100,
            batch_size=8,
            seed=42,
            additional_params={
                'l2_reg': l2_reg,
                'normalize': True,  # Apollo normalization
                'use_all_tokens': True,  # Mean of all tokens
                'exclude_last_n_tokens': exclude_last_n_tokens,
            }
        )

        print()
        print("Sweep completed!")
        print(f"Best layer: {result['best_layer']}")
        print(f"Best AUROC: {result['best_metrics']['val_auroc']:.4f}")
        print(f"Probe saved to: {result['best_probe_path']}")

        # Save results locally
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_dir = Path("sweep_results")
        results_dir.mkdir(exist_ok=True)

        # Create descriptive filename
        model_short = "llama8b"
        filename = f"{dataset_name}_{model_short}_layer{result['best_layer']}_{method}_l2reg{l2_reg}_{timestamp}.json"
        results_path = results_dir / filename

        with open(results_path, "w") as f:
            json.dump(result, f, indent=2, default=str)

        print(f"Results saved to: {results_path}")
        print()

        return result

    except Exception as e:
        print(f"Error running sweep: {e}")
        print("\nMake sure the Modal app is deployed:")
        print("  modal deploy src/modal_deployments/probe_training_service.py")
        return None


def main():
    """Run sweeps for both datasets."""

    print("Starting probe training sweeps for Llama 8B")
    print("=" * 70)
    print()

    # Run sweep for roleplaying dataset
    print("1/2: Roleplaying dataset sweep")
    roleplaying_result = run_layer_sweep(
        dataset_name="roleplaying",
        l2_reg=1.0,
    )

    # Run sweep for REPE/instructed pairs dataset
    print("2/2: REPE honesty dataset sweep")
    repe_result = run_layer_sweep(
        dataset_name="repe_honesty",
        l2_reg=1.0,
    )

    # Summary
    print()
    print("=" * 70)
    print("SWEEP RESULTS SUMMARY")
    print("=" * 70)

    if roleplaying_result:
        print(f"Roleplaying dataset:")
        print(f"  Best layer: {roleplaying_result['best_layer']}")
        print(f"  AUROC: {roleplaying_result['best_metrics']['val_auroc']:.4f}")
        print(f"  Path: {roleplaying_result['best_probe_path']}")
        print()

    if repe_result:
        print(f"REPE honesty dataset:")
        print(f"  Best layer: {repe_result['best_layer']}")
        print(f"  AUROC: {repe_result['best_metrics']['val_auroc']:.4f}")
        print(f"  Path: {repe_result['best_probe_path']}")
        print()

    print("All sweeps completed!")


if __name__ == "__main__":
    main()