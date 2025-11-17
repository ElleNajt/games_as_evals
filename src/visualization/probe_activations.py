#!/usr/bin/env python3
"""
Visualization tools for probe activations on generated text.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Rectangle
import numpy as np


def normalize_scores(scores: List[float], vmin: float = 0.0, vmax: float = 1.0) -> List[float]:
    """
    Normalize scores to [0, 1] range for color mapping.
    
    Args:
        scores: List of probe scores
        vmin: Minimum value for normalization (default: 0.0)
        vmax: Maximum value for normalization (default: 1.0)
    
    Returns:
        List of normalized scores in [0, 1]
    """
    scores_array = np.array(scores)
    normalized = (scores_array - vmin) / (vmax - vmin)
    return np.clip(normalized, 0, 1).tolist()


def get_color_for_score(score: float) -> str:
    """
    Convert a normalized score [0, 1] to a color.
    Green (low activation) -> Yellow -> Red (high activation)
    
    Args:
        score: Normalized score in [0, 1]
    
    Returns:
        Hex color string
    """
    # Create a colormap from green to yellow to red
    cmap = mcolors.LinearSegmentedColormap.from_list(
        'activation',
        ['#00ff00', '#ffff00', '#ff0000']  # Green -> Yellow -> Red
    )
    
    rgba = cmap(score)
    # Convert to hex
    return mcolors.to_hex(rgba)


def create_token_visualization(
    tokens: List[str],
    probe_scores: Dict[str, List[float]],
    title: str = "Probe Activations",
    figsize: Tuple[int, int] = (16, 8),
    vmin: float = 0.0,
    vmax: float = 1.0,
    save_path: Optional[Path] = None,
) -> None:
    """
    Create a visualization of tokens colored by probe activations.
    
    Args:
        tokens: List of generated tokens
        probe_scores: Dict mapping probe name to list of token scores
        title: Title for the visualization
        figsize: Figure size (width, height)
        vmin: Minimum value for score normalization
        vmax: Maximum value for score normalization
        save_path: Optional path to save the figure
    """
    num_probes = len(probe_scores)
    if num_probes == 0:
        print("No probe scores to visualize")
        return
    
    # Create figure with subplots for each probe
    fig, axes = plt.subplots(num_probes, 1, figsize=figsize)
    if num_probes == 1:
        axes = [axes]
    
    fig.suptitle(title, fontsize=16, fontweight='bold')
    
    for ax_idx, (probe_name, scores) in enumerate(probe_scores.items()):
        ax = axes[ax_idx]
        
        # Normalize scores
        normalized_scores = normalize_scores(scores, vmin, vmax)
        
        # Clear axis
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        
        # Add probe name as title
        ax.text(0.5, 0.95, probe_name, 
                horizontalalignment='center',
                verticalalignment='top',
                fontsize=14, fontweight='bold',
                transform=ax.transAxes)
        
        # Layout tokens in rows
        x_offset = 0.02
        y_offset = 0.85
        max_width = 0.96
        line_height = 0.08
        
        for i, (token, score, norm_score) in enumerate(zip(tokens, scores, normalized_scores)):
            # Clean up token display
            display_token = token.replace('Ġ', ' ').replace('Ċ', '\\n')
            
            # Estimate token width (rough approximation)
            token_width = len(display_token) * 0.012
            
            # Check if we need to wrap to next line
            if x_offset + token_width > max_width:
                x_offset = 0.02
                y_offset -= line_height
            
            # Get color for this score
            color = get_color_for_score(norm_score)
            
            # Add background rectangle
            rect = Rectangle(
                (x_offset, y_offset - 0.04), 
                token_width, 
                0.06,
                facecolor=color,
                edgecolor='black',
                linewidth=0.5,
                transform=ax.transAxes,
                zorder=1
            )
            ax.add_patch(rect)
            
            # Add token text
            ax.text(
                x_offset + token_width/2, 
                y_offset,
                display_token,
                horizontalalignment='center',
                verticalalignment='center',
                fontsize=10,
                fontfamily='monospace',
                transform=ax.transAxes,
                zorder=2
            )
            
            x_offset += token_width + 0.005
        
        # Add colorbar for this probe
        cmap = mcolors.LinearSegmentedColormap.from_list(
            'activation',
            ['#00ff00', '#ffff00', '#ff0000']
        )
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=mcolors.Normalize(vmin=vmin, vmax=vmax))
        sm.set_array([])
        
        # Create colorbar on the right side
        cbar_ax = fig.add_axes([0.92, 0.1 + (num_probes - ax_idx - 1) * (0.8 / num_probes), 
                                0.02, 0.8 / num_probes - 0.05])
        cbar = plt.colorbar(sm, cax=cbar_ax)
        cbar.set_label('Activation', rotation=270, labelpad=20)
    
    plt.tight_layout(rect=[0, 0, 0.9, 0.96])
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved visualization to: {save_path}")
    
    plt.show()


def visualize_ttl_game(
    game_results_path: Path,
    vmin: float = 0.0,
    vmax: float = 1.0,
    save_dir: Optional[Path] = None,
) -> None:
    """
    Visualize probe activations for a TTL game.
    
    Args:
        game_results_path: Path to game_results.json file
        vmin: Minimum value for score normalization
        vmax: Maximum value for score normalization
        save_dir: Optional directory to save visualizations
    """
    # Load game results
    with open(game_results_path) as f:
        data = json.load(f)
    
    if 'deceiver_generation' not in data:
        print("No deceiver_generation data found")
        return
    
    dec_gen = data['deceiver_generation']
    
    # Get tokens and probe scores
    tokens = dec_gen.get('generated_tokens', [])
    probe_token_scores = dec_gen.get('probe_token_scores', {})
    
    if not tokens:
        print("No tokens found")
        return
    
    if not probe_token_scores:
        print("No token-level probe scores found")
        return
    
    # Create visualization
    title = f"Probe Activations - {game_results_path.parent.name}"
    
    save_path = None
    if save_dir:
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / f"{game_results_path.parent.name}_activations.png"
    
    create_token_visualization(
        tokens=tokens,
        probe_scores=probe_token_scores,
        title=title,
        vmin=vmin,
        vmax=vmax,
        save_path=save_path,
    )
    
    # Print summary statistics
    print("\nProbe Score Statistics:")
    print("=" * 60)
    for probe_name, scores in probe_token_scores.items():
        scores_array = np.array(scores)
        print(f"{probe_name}:")
        print(f"  Mean:   {scores_array.mean():.4f}")
        print(f"  Std:    {scores_array.std():.4f}")
        print(f"  Min:    {scores_array.min():.4f}")
        print(f"  Max:    {scores_array.max():.4f}")
        print(f"  Median: {np.median(scores_array):.4f}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python probe_activations.py <path_to_game_results.json> [vmin] [vmax]")
        sys.exit(1)
    
    game_path = Path(sys.argv[1])
    vmin = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    vmax = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    
    # Save to same directory as game results
    save_dir = game_path.parent
    
    visualize_ttl_game(game_path, vmin=vmin, vmax=vmax, save_dir=save_dir)
