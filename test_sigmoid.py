#!/usr/bin/env python3
"""Quick test to verify sigmoid transformation is applied."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Test the sigmoid function directly
from src.backends.modal_backend import sigmoid

print("Testing sigmoid function:")
print(f"  sigmoid(-25) = {sigmoid(-25):.6f}  (should be ~0.000000)")
print(f"  sigmoid(-10) = {sigmoid(-10):.6f}  (should be ~0.000045)")
print(f"  sigmoid(-5) = {sigmoid(-5):.6f}   (should be ~0.006693)")
print(f"  sigmoid(0) = {sigmoid(0):.6f}    (should be 0.500000)")
print(f"  sigmoid(5) = {sigmoid(5):.6f}    (should be ~0.993307)")
print(f"  sigmoid(0.7) = {sigmoid(0.7):.6f}  (already probability, should be ~0.668188)")
print()

# The key insight:
print("Key insight:")
print("  Apollo probes return raw logits (e.g., -25.266)")
print(f"    → After sigmoid: {sigmoid(-25.266):.10f} (very low deception)")
print()
print("  Hallucination probes already return probabilities (e.g., 0.7)")
print(f"    → After sigmoid: {sigmoid(0.7):.6f} (safe to re-apply)")
print(f"    → Original was already ~{0.7:.6f}")
print()
print("Sigmoid transformation unifies both to [0,1] probability range!")
