"""Generate matplotlib plots for Werewolf batch experiments."""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict


def load_batch_data(experiment_dir: Path) -> Dict[str, Any]:
    """Load batch results and individual game stats."""
    batch_file = experiment_dir / "batch_results.json"
    with open(batch_file) as f:
        batch_data = json.load(f)
    
    games = []
    for i in range(1, batch_data["total_rounds"] + 1):
        stats_file = experiment_dir / f"game{i}" / "game_stats.json"
        if stats_file.exists():
            with open(stats_file) as f:
                games.append(json.load(f))
    
    return {"batch": batch_data, "games": games}


def plot_probe_activations_by_role(data: Dict[str, Any], output_dir: Path) -> Path:
    """Plot probe activation distributions grouped by player role."""
    games = data["games"]
    
    activations_by_role = defaultdict(list)
    
    for game in games:
        if "role_reveal_activations" not in game:
            continue
            
        role_activations = game["role_reveal_activations"]
        player_roles = game.get("player_roles", {})
        
        for player_name, activation in role_activations.items():
            role = player_roles.get(player_name, "Unknown")
            if activation is not None:
                activations_by_role[role].append(activation)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    roles = sorted(activations_by_role.keys())
    positions = range(len(roles))
    
    # Create violin plot
    parts = ax.violinplot(
        [activations_by_role[role] for role in roles],
        positions=positions,
        showmeans=True,
        showmedians=True
    )
    
    ax.set_xticks(positions)
    ax.set_xticklabels(roles)
    ax.set_ylabel('Probe Activation Score', fontsize=12)
    ax.set_title('Probe Activations by Player Role', fontsize=14)
    ax.grid(True, alpha=0.3, axis='y')
    
    output_path = output_dir / "probe_activations_by_role.png"
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    
    return output_path


def plot_game_outcomes(data: Dict[str, Any], output_dir: Path) -> Path:
    """Plot win rates by faction."""
    games = data["games"]
    
    from collections import Counter
    winners = Counter([g.get("winner", "Unknown") for g in games])
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    factions = sorted(winners.keys())
    counts = [winners[f] for f in factions]
    colors = ['#2E7D32' if 'Village' in f else '#C62828' if 'Werewol' in f else '#757575' for f in factions]
    
    bars = ax.bar(factions, counts, color=colors, alpha=0.7)
    ax.set_ylabel('Number of Wins', fontsize=12)
    ax.set_title('Game Outcomes by Faction', fontsize=14)
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontsize=11)
    
    output_path = output_dir / "game_outcomes.png"
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    
    return output_path


def plot_turn_statistics(data: Dict[str, Any], output_dir: Path) -> Path:
    """Plot turn duration statistics."""
    games = data["games"]
    
    turns_by_winner = defaultdict(list)
    for game in games:
        winner = game.get("winner", "Unknown")
        turns = game.get("turns", 0)
        if turns > 0:
            turns_by_winner[winner].append(turns)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    winners = sorted(turns_by_winner.keys())
    turn_data = [turns_by_winner[w] for w in winners]
    
    bp = ax.boxplot(turn_data, labels=winners, patch_artist=True)
    
    for patch in bp['boxes']:
        patch.set_facecolor('lightblue')
        patch.set_alpha(0.7)
    
    ax.set_ylabel('Number of Turns', fontsize=12)
    ax.set_title('Game Length by Winner', fontsize=14)
    ax.grid(True, alpha=0.3, axis='y')
    
    output_path = output_dir / "turn_statistics.png"
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    
    return output_path


def generate_all_plots(experiment_dir: Path) -> List[Path]:
    """Generate all plots for a Werewolf batch experiment."""
    data = load_batch_data(experiment_dir)
    
    plots_dir = experiment_dir / "plots"
    plots_dir.mkdir(exist_ok=True)
    
    plot_files = []
    
    print(f"Generating Werewolf batch plots in {plots_dir}/...")
    
    plot_files.append(plot_probe_activations_by_role(data, plots_dir))
    print(f"  ✓ Probe activations by role")
    
    plot_files.append(plot_game_outcomes(data, plots_dir))
    print(f"  ✓ Game outcomes")
    
    plot_files.append(plot_turn_statistics(data, plots_dir))
    print(f"  ✓ Turn statistics")
    
    print(f"Generated {len(plot_files)} plots")
    
    return plot_files


def main():
    """Main entry point for CLI usage."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m src.visualization.werewolf_batch_plots <experiment_dir>")
        print("\nExample:")
        print("  python -m src.visualization.werewolf_batch_plots results/werewolf/werewolf_8b_both_probes_xxx/")
        sys.exit(1)
    
    experiment_dir = Path(sys.argv[1])
    if not experiment_dir.exists():
        print(f"Error: Directory not found: {experiment_dir}")
        sys.exit(1)
    
    generate_all_plots(experiment_dir)


if __name__ == "__main__":
    main()
