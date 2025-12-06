"""Generate matplotlib plots for TTL batch experiments."""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import Dict, List, Any


def load_batch_data(experiment_dir: Path) -> Dict[str, Any]:
    """Load batch results and individual game results."""
    batch_file = experiment_dir / "batch_results.json"
    with open(batch_file) as f:
        batch_data = json.load(f)
    
    games = []
    for i in range(1, batch_data["total_rounds"] + 1):
        game_file = experiment_dir / f"game{i}" / "game_results.json"
        if game_file.exists():
            with open(game_file) as f:
                games.append(json.load(f))
    
    return {"batch": batch_data, "games": games}


def plot_probe_score_distributions(data: Dict[str, Any], output_dir: Path) -> Path:
    """Plot probe score distributions for lies vs truths."""
    games = data["games"]
    
    lie_scores = []
    truth_scores = []
    
    for game in games:
        lie_pos = game["revealed_lie"]
        avg_scores = game["deceiver_generation"]["avg_scores"]
        
        for pos, score in avg_scores.items():
            if int(pos) == lie_pos:
                lie_scores.append(score)
            else:
                truth_scores.append(score)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Create histogram
    bins = np.linspace(0.5, 1.0, 20)
    ax.hist(truth_scores, bins=bins, alpha=0.6, label='Truths', color='green')
    ax.hist(lie_scores, bins=bins, alpha=0.6, label='Lies', color='red')
    
    ax.set_xlabel('Probe Score', fontsize=12)
    ax.set_ylabel('Frequency', fontsize=12)
    ax.set_title('Probe Score Distribution: Lies vs Truths', fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    
    output_path = output_dir / "probe_score_distribution.png"
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    
    return output_path


def plot_auditor_accuracy_over_time(data: Dict[str, Any], output_dir: Path) -> Path:
    """Plot auditor accuracy over rounds."""
    games = data["games"]
    
    rounds = list(range(1, len(games) + 1))
    with_probe_correct = [1 if g["auditor_correct_with_probe"] else 0 for g in games]
    without_probe_correct = [1 if g["auditor_correct_without_probe"] else 0 for g in games]
    
    # Calculate cumulative accuracy
    with_probe_cumulative = np.cumsum(with_probe_correct) / np.arange(1, len(games) + 1)
    without_probe_cumulative = np.cumsum(without_probe_correct) / np.arange(1, len(games) + 1)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Per-round accuracy
    ax1.plot(rounds, with_probe_correct, 'o-', label='With Probe', color='blue', linewidth=2)
    ax1.plot(rounds, without_probe_correct, 's-', label='Without Probe', color='orange', linewidth=2)
    ax1.set_xlabel('Round', fontsize=12)
    ax1.set_ylabel('Correct (1) / Incorrect (0)', fontsize=12)
    ax1.set_title('Per-Round Auditor Accuracy', fontsize=14)
    ax1.legend(fontsize=11)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(-0.1, 1.1)
    
    # Cumulative accuracy
    ax2.plot(rounds, with_probe_cumulative, 'o-', label='With Probe', color='blue', linewidth=2)
    ax2.plot(rounds, without_probe_cumulative, 's-', label='Without Probe', color='orange', linewidth=2)
    ax2.set_xlabel('Round', fontsize=12)
    ax2.set_ylabel('Cumulative Accuracy', fontsize=12)
    ax2.set_title('Cumulative Auditor Accuracy', fontsize=14)
    ax2.legend(fontsize=11)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0, 1)
    
    output_path = output_dir / "auditor_accuracy_over_time.png"
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    
    return output_path


def plot_lie_position_analysis(data: Dict[str, Any], output_dir: Path) -> Path:
    """Plot lie position distribution and accuracy by position."""
    games = data["games"]
    
    # Count lies by position
    from collections import Counter
    lie_positions = [g["revealed_lie"] for g in games]
    lie_counts = Counter(lie_positions)
    
    # Count correct guesses by position
    correct_by_position = {1: 0, 2: 0, 3: 0}
    total_by_position = {1: 0, 2: 0, 3: 0}
    
    for game in games:
        lie_pos = game["revealed_lie"]
        total_by_position[lie_pos] += 1
        if game["auditor_correct_with_probe"]:
            correct_by_position[lie_pos] += 1
    
    # Calculate accuracy by position
    accuracy_by_position = {
        pos: (correct_by_position[pos] / total_by_position[pos] if total_by_position[pos] > 0 else 0)
        for pos in [1, 2, 3]
    }
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Lie position distribution
    positions = sorted(lie_counts.keys())
    counts = [lie_counts[pos] for pos in positions]
    ax1.bar(positions, counts, color=['steelblue', 'coral', 'mediumseagreen'])
    ax1.set_xlabel('Statement Position', fontsize=12)
    ax1.set_ylabel('Number of Lies', fontsize=12)
    ax1.set_title('Lie Position Distribution', fontsize=14)
    ax1.set_xticks([1, 2, 3])
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Accuracy by position
    positions = sorted(accuracy_by_position.keys())
    accuracies = [accuracy_by_position[pos] for pos in positions]
    ax2.bar(positions, accuracies, color=['steelblue', 'coral', 'mediumseagreen'])
    ax2.set_xlabel('Statement Position', fontsize=12)
    ax2.set_ylabel('Auditor Accuracy (with probe)', fontsize=12)
    ax2.set_title('Auditor Accuracy by Lie Position', fontsize=14)
    ax2.set_xticks([1, 2, 3])
    ax2.set_ylim(0, 1)
    ax2.grid(True, alpha=0.3, axis='y')
    
    output_path = output_dir / "lie_position_analysis.png"
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    
    return output_path


def plot_probe_following_behavior(data: Dict[str, Any], output_dir: Path) -> Path:
    """Plot how often auditor follows probe recommendations."""
    games = data["games"]
    
    followed_probe = []
    probe_was_correct = []
    
    for game in games:
        avg_scores = game["deceiver_generation"]["avg_scores"]
        highest_score_pos = int(max(avg_scores.items(), key=lambda x: x[1])[0])
        with_probe_guess = game["auditor_guesses"]["with_probe"]["original_guess"]
        lie_pos = game["revealed_lie"]
        
        followed = (with_probe_guess == highest_score_pos)
        probe_correct = (highest_score_pos == lie_pos)
        
        followed_probe.append(followed)
        probe_was_correct.append(probe_correct)
    
    # Create 2x2 contingency data
    followed_and_correct = sum(1 for i in range(len(games)) if followed_probe[i] and probe_was_correct[i])
    followed_and_wrong = sum(1 for i in range(len(games)) if followed_probe[i] and not probe_was_correct[i])
    not_followed_and_correct = sum(1 for i in range(len(games)) if not followed_probe[i] and probe_was_correct[i])
    not_followed_and_wrong = sum(1 for i in range(len(games)) if not followed_probe[i] and not probe_was_correct[i])
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    categories = ['Followed Probe\n& Probe Correct', 'Followed Probe\n& Probe Wrong', 
                  'Ignored Probe\n& Probe Correct', 'Ignored Probe\n& Probe Wrong']
    values = [followed_and_correct, followed_and_wrong, not_followed_and_correct, not_followed_and_wrong]
    colors = ['darkgreen', 'orange', 'gold', 'darkred']
    
    bars = ax.bar(categories, values, color=colors, alpha=0.7)
    ax.set_ylabel('Number of Games', fontsize=12)
    ax.set_title('Auditor Probe-Following Behavior', fontsize=14)
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontsize=11)
    
    output_path = output_dir / "probe_following_behavior.png"
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    
    return output_path


def generate_all_plots(experiment_dir: Path) -> List[Path]:
    """Generate all plots for a TTL batch experiment."""
    data = load_batch_data(experiment_dir)
    
    # Create plots subdirectory
    plots_dir = experiment_dir / "plots"
    plots_dir.mkdir(exist_ok=True)
    
    plot_files = []
    
    print(f"Generating TTL batch plots in {plots_dir}/...")
    
    # Generate each plot
    plot_files.append(plot_probe_score_distributions(data, plots_dir))
    print(f"  ✓ Probe score distribution")
    
    plot_files.append(plot_auditor_accuracy_over_time(data, plots_dir))
    print(f"  ✓ Auditor accuracy over time")
    
    plot_files.append(plot_lie_position_analysis(data, plots_dir))
    print(f"  ✓ Lie position analysis")
    
    plot_files.append(plot_probe_following_behavior(data, plots_dir))
    print(f"  ✓ Probe following behavior")
    
    print(f"Generated {len(plot_files)} plots")
    
    return plot_files


def main():
    """Main entry point for CLI usage."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m src.visualization.ttl_batch_plots <experiment_dir>")
        print("\nExample:")
        print("  python -m src.visualization.ttl_batch_plots results/ttl/ttl_8b_both_probes_xxx/")
        sys.exit(1)
    
    experiment_dir = Path(sys.argv[1])
    if not experiment_dir.exists():
        print(f"Error: Directory not found: {experiment_dir}")
        sys.exit(1)
    
    generate_all_plots(experiment_dir)


if __name__ == "__main__":
    main()
