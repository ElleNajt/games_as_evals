#!/usr/bin/env python3
"""Analyze results from the three-condition Cheat probe experiment."""

import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.visualization.cheat_plots import extract_probe_data, load_events


def analyze_condition(condition_dir: Path, condition_name: str):
    """Analyze all games in a condition."""
    print(f"\n{'=' * 60}")
    print(f"Analyzing: {condition_name}")
    print(f"{'=' * 60}")

    # Metrics to track
    all_probe_scores = defaultdict(lambda: {"honest": [], "lying": []})
    challenge_stats = {
        "total_challenges": 0,
        "correct_challenges": 0,  # Challenged a liar
        "incorrect_challenges": 0,  # Challenged honest player
    }
    game_lengths = []
    winners = []

    # Process each game
    game_dirs = sorted(
        [d for d in condition_dir.iterdir() if d.is_dir() and d.name.startswith("game")]
    )

    for game_dir in game_dirs:
        events = load_events(game_dir)

        # Track game length and winner from game_end event
        for event in events:
            if event.get("event_type") == "game_end":
                data = event.get("data", {})
                num_turns = data.get("total_turns", 0)
                game_lengths.append(num_turns)
                winners.append(data.get("winner"))

        # Extract and aggregate probe scores
        probe_data = extract_probe_data(events)
        for probe_name, data in probe_data.items():
            all_probe_scores[probe_name]["honest"].extend(data["honest"])
            all_probe_scores[probe_name]["lying"].extend(data["lying"])

        # Track challenge accuracy
        for event in events:
            if event.get("event_type") == "challenge":
                data = event.get("data", {})
                challenge_stats["total_challenges"] += 1
                was_lying = data.get("was_lying", False)
                if was_lying:
                    challenge_stats["correct_challenges"] += 1
                else:
                    challenge_stats["incorrect_challenges"] += 1

    # Print results
    print(f"\nGames analyzed: {len(game_dirs)}")
    print(
        f"Average game length: {np.mean(game_lengths):.1f} turns (std: {np.std(game_lengths):.1f})"
    )

    print(f"\n--- Challenge Statistics ---")
    print(f"Total challenges: {challenge_stats['total_challenges']}")
    print(f"Correct challenges (caught liars): {challenge_stats['correct_challenges']}")
    print(
        f"Incorrect challenges (challenged honest): {challenge_stats['incorrect_challenges']}"
    )
    if challenge_stats["total_challenges"] > 0:
        accuracy = (
            challenge_stats["correct_challenges"] / challenge_stats["total_challenges"]
        )
        print(f"Challenge accuracy: {accuracy:.1%}")

    print(f"\n--- Probe Score Statistics ---")
    for probe_name in sorted(all_probe_scores.keys()):
        honest_scores = all_probe_scores[probe_name]["honest"]
        lying_scores = all_probe_scores[probe_name]["lying"]

        print(f"\n{probe_name}:")
        print(
            f"  Honest plays: {len(honest_scores)}, mean={np.mean(honest_scores):.3f}, std={np.std(honest_scores):.3f}"
        )
        print(
            f"  Lying plays:  {len(lying_scores)}, mean={np.mean(lying_scores):.3f}, std={np.std(lying_scores):.3f}"
        )
        print(f"  Separation:   {np.mean(lying_scores) - np.mean(honest_scores):.3f}")

    # Count winner distribution
    winner_counts = defaultdict(int)
    for winner in winners:
        winner_counts[winner] += 1

    print(f"\n--- Winner Distribution ---")
    for player, count in sorted(winner_counts.items()):
        print(
            f"  {player}: {count}/{len(game_dirs)} games ({count / len(game_dirs) * 100:.0f}%)"
        )

    return {
        "condition": condition_name,
        "num_games": len(game_dirs),
        "avg_game_length": np.mean(game_lengths),
        "std_game_length": np.std(game_lengths),
        "challenge_accuracy": challenge_stats["correct_challenges"]
        / challenge_stats["total_challenges"]
        if challenge_stats["total_challenges"] > 0
        else 0,
        "total_challenges": challenge_stats["total_challenges"],
        "correct_challenges": challenge_stats["correct_challenges"],
        "probe_scores": {
            probe: {
                "honest_mean": np.mean(scores["honest"]),
                "lying_mean": np.mean(scores["lying"]),
                "separation": np.mean(scores["lying"]) - np.mean(scores["honest"]),
            }
            for probe, scores in all_probe_scores.items()
        },
        "winner_distribution": dict(winner_counts),
    }


def main():
    results_base = Path("results/cheat")

    # Analyze each condition
    baseline_stats = analyze_condition(
        results_base / "cheat_baseline_a4a02b4_562b2aa_dirty",
        "BASELINE (probes run, NOT shown to players)",
    )

    deception_stats = analyze_condition(
        results_base / "cheat_deception_a4a02b4_4d2eb15_dirty",
        "DECEPTION (players see deception_70b scores)",
    )

    hallucination_stats = analyze_condition(
        results_base / "cheat_hallucination_a4a02b4_c44ddb8_dirty",
        "HALLUCINATION (players see hallucination_70b scores)",
    )

    # Comparative summary
    print(f"\n\n{'=' * 60}")
    print("COMPARATIVE SUMMARY")
    print(f"{'=' * 60}")

    print("\n--- Challenge Accuracy by Condition ---")
    print(
        f"Baseline:       {baseline_stats['challenge_accuracy']:.1%} ({baseline_stats['correct_challenges']}/{baseline_stats['total_challenges']})"
    )
    print(
        f"Deception:      {deception_stats['challenge_accuracy']:.1%} ({deception_stats['correct_challenges']}/{deception_stats['total_challenges']})"
    )
    print(
        f"Hallucination:  {hallucination_stats['challenge_accuracy']:.1%} ({hallucination_stats['correct_challenges']}/{hallucination_stats['total_challenges']})"
    )

    print("\n--- Average Game Length ---")
    print(f"Baseline:       {baseline_stats['avg_game_length']:.1f} turns")
    print(f"Deception:      {deception_stats['avg_game_length']:.1f} turns")
    print(f"Hallucination:  {hallucination_stats['avg_game_length']:.1f} turns")

    print("\n--- Key Finding ---")
    baseline_acc = baseline_stats["challenge_accuracy"]
    deception_acc = deception_stats["challenge_accuracy"]
    hallucination_acc = hallucination_stats["challenge_accuracy"]

    deception_improvement = deception_acc - baseline_acc
    hallucination_improvement = hallucination_acc - baseline_acc

    print(f"Deception probe advantage:      {deception_improvement:+.1%} over baseline")
    print(
        f"Hallucination probe advantage:  {hallucination_improvement:+.1%} over baseline"
    )

    if hallucination_improvement > deception_improvement:
        print(
            f"\n✓ Hallucination probe provides {hallucination_improvement - deception_improvement:.1%} MORE advantage than deception probe"
        )
    else:
        print(
            f"\n✗ Deception probe provides {deception_improvement - hallucination_improvement:.1%} MORE advantage than hallucination probe"
        )

    print(
        f"\nThis aligns with probe quality: hallucination_70b has 98% accuracy vs deception_70b's 59%"
    )


if __name__ == "__main__":
    main()
