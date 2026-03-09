#!/usr/bin/env python3
"""Test Modal probe training sweep directly."""

import modal
import json

# Connect to the deployed probe training service
app = modal.App.from_name("probe-training-service")

# Get the sweep function
sweep_fn = modal.Function.from_name("probe-training-service", "sweep_layers_on_modal")

print("Running test sweep for roleplaying dataset...")
print("Testing layers [20, 22, 24]")
print()

# Test with a few layers
result = sweep_fn.remote(
    dataset_name="roleplaying",
    model_name="meta-llama/Meta-Llama-3.1-8B-Instruct",
    method="linear-contrastive",
    layers=[20, 22, 24],
    learning_rate=1e-3,
    num_epochs=100,
    batch_size=8,
    seed=42,
    additional_params={
        'l2_reg': 1.0,  # L2 regularization (lambda=1)
        'normalize': True,  # Apollo normalization
        'use_all_tokens': True,  # Mean of all tokens
        'exclude_last_n_tokens': 0,  # Don't exclude for roleplaying
    }
)

print("Sweep complete!")
print(f"Best layer: {result['best_layer']}")
print(f"Best AUROC: {result['best_metrics']['val_auroc']:.4f}")
print(f"Probe path: {result['best_probe_path']}")

# Save results
with open("test_sweep_results.json", "w") as f:
    json.dump(result, f, indent=2, default=str)

print("\nResults saved to test_sweep_results.json")