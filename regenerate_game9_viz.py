#!/usr/bin/env python3
"""Regenerate visualizations for hallucination game9."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.visualization.cheat_plots import generate_cheat_visualizations

# Game directory
game_dir = Path("results/cheat/cheat_hallucination_a4a02b4_c44ddb8_dirty/game9")

print(f"Regenerating visualizations for: {game_dir}")
generate_cheat_visualizations(game_dir)
print("Done!")
