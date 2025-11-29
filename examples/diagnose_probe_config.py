#!/usr/bin/env python3
"""
Diagnose probe configuration to understand why we're not seeing separation.
Check bias values, layer numbers, and raw vs transformed scores.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import numpy as np
from src.config.player_config import PlayerConfig


def sigmoid(x):
    """Sigmoid function."""
    return 1 / (1 + np.exp(-x))


def inverse_sigmoid(y):
    """Inverse sigmoid (logit) function."""
    if y <= 0 or y >= 1:
        return None
    return np.log(y / (1 - y))


def main():
    """Diagnose probe configuration."""
    
    print("="*60)
    print("PROBE CONFIGURATION DIAGNOSTICS")
    print("="*60)
    
    # Create a sample player config to see probe settings
    player = PlayerConfig(
        name="Test",
        backend_type="modal",
        model="meta-llama/Llama-3.1-8B-Instruct",
        probes=["deception_8b", "hallucination_8b"],
    )
    
    # Check if we can access probe configs
    print("\n1. PROBE CONFIGURATION:")
    print("-" * 60)
    
    # The probe configs are set in the backend when it initializes
    # Let's check what the defaults are
    from src.backends.modal_backend import ModalBackend
    
    # Create backend to see probe configs
    backend = ModalBackend(
        model="meta-llama/Llama-3.1-8B-Instruct",
        probes=["deception_8b", "hallucination_8b"]
    )
    
    print(f"\nProbe configs loaded:")
    for probe_name, probe_config in backend.probe_configs.items():
        print(f"\n  {probe_name}:")
        print(f"    Volume path: {probe_config.volume_path}")
        print(f"    Probe type: {probe_config.probe_type}")
        print(f"    Layer: {probe_config.layer}")
        print(f"    Bias: {probe_config.bias}")
        print(f"    Description: {probe_config.description}")
    
    print("\n" + "="*60)
    print("2. SCORE TRANSFORMATION ANALYSIS")
    print("="*60)
    
    # Analyze observed scores from our games
    print("\nObserved scores from games (post-sigmoid):")
    print("  Deception probe:")
    print("    Lying: mean=0.7455, range=[0.6923, 0.7867]")
    print("    Honest: mean=0.7418, range=[0.7041, 0.7704]")
    print("\n  Hallucination probe:")
    print("    Lying: mean=0.3335, range=[0.2241, 0.5378]")
    print("    Honest: mean=0.3652, range=[0.2867, 0.4478]")
    
    # Try to reverse engineer what the raw scores might be
    print("\n" + "-"*60)
    print("Attempting to reverse engineer RAW scores (before sigmoid+bias):")
    print("-"*60)
    
    for probe_name, probe_config in backend.probe_configs.items():
        bias = probe_config.bias
        print(f"\n{probe_name} (bias={bias}):")
        
        if probe_name == "deception_8b":
            lying_mean = 0.7455
            honest_mean = 0.7418
        else:  # hallucination_8b
            lying_mean = 0.3335
            honest_mean = 0.3652
        
        # Inverse transform: y = sigmoid(x + bias)
        # So: x = inverse_sigmoid(y) - bias
        lying_raw = inverse_sigmoid(lying_mean)
        honest_raw = inverse_sigmoid(honest_mean)
        
        if lying_raw is not None and honest_raw is not None:
            lying_raw -= bias
            honest_raw -= bias
            
            print(f"  Lying (post-sigmoid={lying_mean:.4f}):")
            print(f"    → Raw score ≈ {lying_raw:.4f}")
            print(f"  Honest (post-sigmoid={honest_mean:.4f}):")
            print(f"    → Raw score ≈ {honest_raw:.4f}")
            print(f"  Raw difference: {lying_raw - honest_raw:.4f}")
            
            # Show effect of bias
            print(f"\n  Effect of bias ({bias}):")
            print(f"    Without bias, lying would be: sigmoid({lying_raw:.4f}) = {sigmoid(lying_raw):.4f}")
            print(f"    Without bias, honest would be: sigmoid({honest_raw:.4f}) = {sigmoid(honest_raw):.4f}")
            print(f"    Difference without bias: {sigmoid(lying_raw) - sigmoid(honest_raw):.4f}")
    
    print("\n" + "="*60)
    print("3. LOAD ACTUAL GAME DATA AND CHECK RAW SCORES")
    print("="*60)
    
    # Load actual game data to see what's stored
    game_dirs = sorted(Path("results/cheat").glob("cheat_both_probes_game_*"))
    
    if game_dirs:
        game_dir = game_dirs[0]
        messages_path = game_dir / "messages.jsonl"
        
        print(f"\nChecking: {game_dir.name}")
        
        if messages_path.exists():
            with open(messages_path) as f:
                msg = json.loads(f.readline())
            
            print("\nFirst message structure:")
            print(f"  Has probe_scores: {'probe_scores' in msg}")
            
            if 'probe_scores' in msg:
                for probe_name, probe_data in msg['probe_scores'].items():
                    print(f"\n  {probe_name}:")
                    print(f"    Keys: {list(probe_data.keys())}")
                    print(f"    Aggregate score: {probe_data.get('aggregate_score', 'N/A')}")
                    
                    token_scores = probe_data.get('token_scores', [])
                    if token_scores:
                        print(f"    Token scores (first 5): {token_scores[:5]}")
                        print(f"    Token scores (mean): {np.mean(token_scores):.4f}")
                        print(f"    Token scores (std): {np.std(token_scores):.4f}")
                        print(f"    Token scores (range): [{np.min(token_scores):.4f}, {np.max(token_scores):.4f}]")
                        
                        # These are POST-sigmoid scores
                        # Try to estimate what raw scores were
                        bias = backend.probe_configs[probe_name].bias
                        raw_scores = [inverse_sigmoid(s) - bias if 0 < s < 1 else None for s in token_scores]
                        raw_scores = [r for r in raw_scores if r is not None]
                        
                        if raw_scores:
                            print(f"\n    Estimated RAW scores (pre-sigmoid, pre-bias):")
                            print(f"      Mean: {np.mean(raw_scores):.4f}")
                            print(f"      Std: {np.std(raw_scores):.4f}")
                            print(f"      Range: [{np.min(raw_scores):.4f}, {np.max(raw_scores):.4f}]")
    
    print("\n" + "="*60)
    print("CONCLUSIONS")
    print("="*60)
    print("\n1. Check if bias values are appropriate for this task")
    print("2. Check if we should be using RAW scores instead of sigmoid-transformed")
    print("3. Consider if the probe layer is optimal for detecting deception")
    print("4. Verify probe files are actually loaded correctly on Modal")


if __name__ == "__main__":
    main()
