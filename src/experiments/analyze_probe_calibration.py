#!/usr/bin/env python3
"""
Analyze probe calibration by comparing probe scores to ground truth.

Creates histograms showing probe score distributions for honest vs deceptive plays.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np


def load_events_and_messages(results_dir: Path):
    """Load events and messages from a game results directory.
    
    Returns:
        List of dicts with probe_score, was_honest, player
    """
    events_file = results_dir / "events.jsonl"
    messages_file = results_dir / "messages.jsonl"
    
    if not events_file.exists() or not messages_file.exists():
        raise FileNotFoundError(f"Missing files in {results_dir}")
    
    # Load events to get ground truth
    events = []
    with open(events_file) as f:
        for line in f:
            event = json.loads(line)
            if event.get('event_type') == 'card_play':
                events.append(event['data'])
    
    # Load messages to get probe scores
    messages = []
    with open(messages_file) as f:
        for line in f:
            msg = json.loads(line)
            if msg.get('probe_scores'):
                messages.append(msg)
    
    # Match messages to events by turn order
    # Events are card plays, messages are LLM generations for those plays
    data_points = []
    
    msg_idx = 0
    for event in events:
        # Find the corresponding message (LLM generation for this play)
        # Messages are in order, but some might be challenge decisions, not plays
        while msg_idx < len(messages):
            msg = messages[msg_idx]
            msg_idx += 1
            
            # Check if this is a play message (has PLAY: in response)
            if 'PLAY:' in msg.get('response', ''):
                # Extract probe score
                probe_scores = msg.get('probe_scores', {})
                if probe_scores:
                    for probe_name, scores in probe_scores.items():
                        data_points.append({
                            'probe_name': probe_name,
                            'probe_score': scores.get('aggregate_score'),
                            'was_honest': event.get('was_honest'),
                            'player': event.get('player'),
                            'turn': event.get('turn'),
                        })
                break
    
    return data_points


def plot_probe_calibration(data_points, output_path=None, title_suffix=""):
    """Create histogram plots of probe scores by honesty.
    
    Args:
        data_points: List of dicts with probe_score, was_honest, player
        output_path: Path to save plot (default: don't save)
        title_suffix: Additional text for plot title
    """
    # Separate honest and deceptive scores
    honest_scores = [d['probe_score'] for d in data_points if d['was_honest']]
    deceptive_scores = [d['probe_score'] for d in data_points if not d['was_honest']]
    
    if not honest_scores and not deceptive_scores:
        print("No probe scores found!")
        return
    
    # Get probe name (assuming all same probe)
    probe_name = data_points[0]['probe_name'] if data_points else "unknown"
    
    # Create figure
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    
    # Histogram parameters
    bins = np.linspace(0, 1, 21)  # 20 bins from 0 to 1
    
    # Plot honest plays
    axes[0].hist(honest_scores, bins=bins, alpha=0.7, color='green', edgecolor='black')
    axes[0].set_ylabel('Count', fontsize=12)
    axes[0].set_title(f'Honest Plays (n={len(honest_scores)})', fontsize=14, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].axvline(np.mean(honest_scores) if honest_scores else 0.5, 
                    color='darkgreen', linestyle='--', linewidth=2, 
                    label=f'Mean: {np.mean(honest_scores):.3f}')
    axes[0].legend()
    
    # Plot deceptive plays
    axes[1].hist(deceptive_scores, bins=bins, alpha=0.7, color='red', edgecolor='black')
    axes[1].set_xlabel('Probe Score', fontsize=12)
    axes[1].set_ylabel('Count', fontsize=12)
    axes[1].set_title(f'Deceptive Plays (n={len(deceptive_scores)})', fontsize=14, fontweight='bold')
    axes[1].grid(True, alpha=0.3)
    axes[1].axvline(np.mean(deceptive_scores) if deceptive_scores else 0.5, 
                    color='darkred', linestyle='--', linewidth=2,
                    label=f'Mean: {np.mean(deceptive_scores):.3f}')
    axes[1].legend()
    
    # Overall title
    fig.suptitle(f'Probe Calibration: {probe_name}{title_suffix}', 
                 fontsize=16, fontweight='bold')
    
    plt.tight_layout()
    
    # Print statistics
    print(f"\n{'='*60}")
    print(f"Probe Calibration Statistics: {probe_name}")
    print(f"{'='*60}")
    print(f"\nHonest plays:")
    print(f"  Count: {len(honest_scores)}")
    if honest_scores:
        print(f"  Mean:  {np.mean(honest_scores):.3f}")
        print(f"  Std:   {np.std(honest_scores):.3f}")
        print(f"  Min:   {np.min(honest_scores):.3f}")
        print(f"  Max:   {np.max(honest_scores):.3f}")
    
    print(f"\nDeceptive plays:")
    print(f"  Count: {len(deceptive_scores)}")
    if deceptive_scores:
        print(f"  Mean:  {np.mean(deceptive_scores):.3f}")
        print(f"  Std:   {np.std(deceptive_scores):.3f}")
        print(f"  Min:   {np.min(deceptive_scores):.3f}")
        print(f"  Max:   {np.max(deceptive_scores):.3f}")
    
    if honest_scores and deceptive_scores:
        separation = np.mean(deceptive_scores) - np.mean(honest_scores)
        print(f"\nSeparation (deceptive - honest): {separation:+.3f}")
        
        # Simple threshold analysis at 0.5
        threshold = 0.5
        honest_below = sum(1 for s in honest_scores if s < threshold)
        deceptive_above = sum(1 for s in deceptive_scores if s >= threshold)
        
        accuracy = (honest_below + deceptive_above) / (len(honest_scores) + len(deceptive_scores))
        print(f"\nThreshold analysis (threshold={threshold}):")
        print(f"  Honest correctly classified:    {honest_below}/{len(honest_scores)} ({100*honest_below/len(honest_scores):.1f}%)")
        print(f"  Deceptive correctly classified: {deceptive_above}/{len(deceptive_scores)} ({100*deceptive_above/len(deceptive_scores):.1f}%)")
        print(f"  Overall accuracy: {100*accuracy:.1f}%")
    
    print(f"{'='*60}\n")
    
    # Save or show
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Plot saved to: {output_path}")
    else:
        plt.show()


def analyze_directory(results_dir: Path, output_path=None):
    """Analyze a single game results directory."""
    print(f"\nAnalyzing: {results_dir}")
    
    data_points = load_events_and_messages(results_dir)
    
    if not data_points:
        print("No data points found!")
        return
    
    print(f"Found {len(data_points)} probe-scored plays")
    
    # Create plot
    title_suffix = f"\n{results_dir.name}"
    if output_path is None:
        output_path = results_dir / "probe_calibration.png"
    
    plot_probe_calibration(data_points, output_path, title_suffix)


def analyze_batch(batch_dir: Path, output_path=None):
    """Analyze all games in a batch experiment directory."""
    print(f"\nAnalyzing batch experiment: {batch_dir}")
    
    # Find all game subdirectories
    game_dirs = sorted([d for d in batch_dir.iterdir() 
                       if d.is_dir() and d.name.startswith('game')])
    
    if not game_dirs:
        print("No game directories found!")
        return
    
    print(f"Found {len(game_dirs)} games")
    
    # Collect data from all games
    all_data = []
    for game_dir in game_dirs:
        try:
            data_points = load_events_and_messages(game_dir)
            all_data.extend(data_points)
            print(f"  {game_dir.name}: {len(data_points)} plays")
        except Exception as e:
            print(f"  {game_dir.name}: ERROR - {e}")
    
    if not all_data:
        print("No data points found across all games!")
        return
    
    print(f"\nTotal: {len(all_data)} probe-scored plays across {len(game_dirs)} games")
    
    # Create aggregated plot
    title_suffix = f"\n{batch_dir.name} ({len(game_dirs)} games)"
    if output_path is None:
        output_path = batch_dir / "probe_calibration_aggregated.png"
    
    plot_probe_calibration(all_data, output_path, title_suffix)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python analyze_probe_calibration.py <results_directory> [output_plot.png]")
        print("\nExamples:")
        print("  Single game:  python analyze_probe_calibration.py results/cheat/cheat_8b_omniscient_3p_a3aa25f_875fe1f/")
        print("  Batch games:  python analyze_probe_calibration.py results/cheat/batch_omniscient/")
        sys.exit(1)
    
    results_dir = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    
    if not results_dir.exists():
        print(f"Error: Directory not found: {results_dir}")
        sys.exit(1)
    
    # Check if this is a batch directory (contains game1, game2, etc.)
    game_dirs = [d for d in results_dir.iterdir() 
                 if d.is_dir() and d.name.startswith('game')]
    
    if game_dirs:
        analyze_batch(results_dir, output_path)
    else:
        analyze_directory(results_dir, output_path)


if __name__ == "__main__":
    main()
