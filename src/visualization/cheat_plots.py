"""Visualization utilities for Cheat game probe analysis."""

import json
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np


def load_events(results_dir: Path) -> List[Dict]:
    """Load events from events.jsonl file."""
    events_file = results_dir / "events.jsonl"
    if not events_file.exists():
        raise FileNotFoundError(f"Events file not found: {events_file}")

    events = []
    with open(events_file, "r") as f:
        for line in f:
            events.append(json.loads(line))
    return events


def extract_probe_data(events: List[Dict]) -> Dict:
    """Extract probe scores and ground truth from card_play events.

    Returns:
        Dict with structure:
        {
            "deception_70b": {
                "honest": [scores],
                "lying": [scores]
            },
            "hallucination_70b": {
                "honest": [scores],
                "lying": [scores]
            }
        }
    """
    probe_data = {}

    for event in events:
        if event.get("event_type") != "card_play":
            continue

        data = event.get("data", {})
        was_honest = data.get("was_honest")
        probe_scores = data.get("probe_scores", {})

        if was_honest is None or not probe_scores:
            continue

        behavior = "honest" if was_honest else "lying"

        for probe_name, score in probe_scores.items():
            if probe_name not in probe_data:
                probe_data[probe_name] = {"honest": [], "lying": []}
            probe_data[probe_name][behavior].append(score)

    return probe_data


def plot_probe_histograms(probe_data: Dict, output_dir: Path):
    """Generate histogram plots for each probe, split by honest/lying behavior.

    Args:
        probe_data: Dict from extract_probe_data()
        output_dir: Directory to save plots
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for probe_name, data in probe_data.items():
        honest_scores = data["honest"]
        lying_scores = data["lying"]

        if not honest_scores and not lying_scores:
            print(f"No data for {probe_name}, skipping")
            continue

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))

        # Determine bins
        all_scores = honest_scores + lying_scores
        bins = np.linspace(min(all_scores), max(all_scores), 30)

        # Plot histograms
        ax.hist(
            honest_scores,
            bins=bins,
            alpha=0.5,
            label=f"Honest (n={len(honest_scores)})",
            color="green",
            edgecolor="black",
        )
        ax.hist(
            lying_scores,
            bins=bins,
            alpha=0.5,
            label=f"Lying (n={len(lying_scores)})",
            color="red",
            edgecolor="black",
        )

        # Calculate statistics
        honest_mean = np.mean(honest_scores) if honest_scores else 0
        lying_mean = np.mean(lying_scores) if lying_scores else 0

        # Add vertical lines for means
        if honest_scores:
            ax.axvline(
                honest_mean,
                color="green",
                linestyle="--",
                linewidth=2,
                label=f"Honest mean: {honest_mean:.3f}",
            )
        if lying_scores:
            ax.axvline(
                lying_mean,
                color="red",
                linestyle="--",
                linewidth=2,
                label=f"Lying mean: {lying_mean:.3f}",
            )

        # Labels and title
        ax.set_xlabel("Probe Score", fontsize=12)
        ax.set_ylabel("Frequency", fontsize=12)
        ax.set_title(
            f"{probe_name} - Score Distribution by Behavior",
            fontsize=14,
            fontweight="bold",
        )
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)

        # Save figure
        output_file = output_dir / f"{probe_name}_histogram.png"
        plt.tight_layout()
        plt.savefig(output_file, dpi=150)
        plt.close()

        print(f"Saved: {output_file}")
        print(f"  Honest: mean={honest_mean:.3f}, n={len(honest_scores)}")
        print(f"  Lying: mean={lying_mean:.3f}, n={len(lying_scores)}")


def generate_cheat_visualizations(results_dir: Path):
    """Generate all visualizations for a Cheat game results directory.

    Args:
        results_dir: Path to results directory (e.g., results/cheat/cheat_test_xxx/)
    """
    results_dir = Path(results_dir)
    print(f"Generating visualizations for: {results_dir}")

    # Load events
    events = load_events(results_dir)
    print(f"Loaded {len(events)} events")

    # Extract probe data
    probe_data = extract_probe_data(events)
    print(f"Found probes: {list(probe_data.keys())}")

    # Generate histograms
    viz_dir = results_dir / "visualizations"
    plot_probe_histograms(probe_data, viz_dir)

    print(f"\nVisualizations saved to: {viz_dir}/")
    return viz_dir


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.visualization.cheat_plots <results_dir>")
        print(
            "Example: python -m src.visualization.cheat_plots results/cheat/cheat_test_1fe1238_7fc7c05"
        )
        sys.exit(1)

    results_dir = Path(sys.argv[1])
    generate_cheat_visualizations(results_dir)
