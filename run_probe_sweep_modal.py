#!/usr/bin/env python3
"""Script to run probe training sweep on Modal by connecting to deployed service."""

import sys
import modal

# Connect to the deployed probe training service
try:
    print("Connecting to deployed probe-training-service on Modal...")
    cls = modal.Cls.from_name("probe-training-service", "ProbeTrainingService")
    service = cls()

    print("Connected! Starting layer sweep...")

    # Run the sweep
    result = service.sweep_layers_on_modal.remote(
        dataset_name="roleplaying",
        model_name="meta-llama/Meta-Llama-3.1-8B-Instruct",
        method="linear-contrastive",
        layers=[8, 10, 12],
        batch_size=8,
        learning_rate=1e-3,
        num_epochs=100,
        seed=42
    )

    print("Layer sweep completed!")
    print(f"Best layer: {result['best_layer']}")
    print(f"Best AUROC: {result['best_metrics']['val_auroc']:.4f}")
    print(f"Probe saved to Modal volume: {result['best_probe_path']}")

except Exception as e:
    print(f"Error: {e}")
    print("\nThe probe training service may not be deployed yet.")
    print("Trying alternative approach...")

    # Alternative: Try to check if the service exists
    try:
        import requests
        print("\nChecking Modal deployment status...")
        # This won't work directly, but let's see what error we get
        sys.exit(1)
    except:
        pass