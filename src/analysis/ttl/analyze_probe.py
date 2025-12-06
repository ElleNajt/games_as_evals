"""Analyze probe behavior and accuracy for TTL experiments."""

import json
from pathlib import Path
from typing import Dict, List, Any


def load_experiment_data(experiment_dir: Path) -> Dict[str, Any]:
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


def analyze_probe_performance(data: Dict[str, Any]) -> None:
    """Analyze probe performance across all games."""
    games = data["games"]
    
    print("=" * 80)
    print("PROBE PERFORMANCE ANALYSIS")
    print("=" * 80)
    print()
    
    print("Round-by-round analysis:")
    print("=" * 80)
    
    raw_probe_correct = 0
    auditor_with_probe_correct = 0
    auditor_without_probe_correct = 0
    auditor_followed_probe = 0
    
    for i, game in enumerate(games, 1):
        lie_pos = game["revealed_lie"]
        avg_scores = game["deceiver_generation"]["avg_scores"]
        
        highest_score_pos = max(avg_scores.items(), key=lambda x: x[1])[0]
        probe_correct = (int(highest_score_pos) == lie_pos)
        
        print(f"\nRound {i}:")
        print(f"  Lie position: {lie_pos}")
        print(f"  Probe scores:")
        for pos in sorted(avg_scores.keys(), key=int):
            score = avg_scores[pos]
            marker = "  <-- LIE" if int(pos) == lie_pos else ""
            marker += "  <-- HIGHEST PROBE SCORE" if pos == highest_score_pos else ""
            print(f"    Statement {pos}: {score:.4f}{marker}")
        
        with_probe_guess = game["auditor_guesses"]["with_probe"]["original_guess"]
        without_probe_guess = game["auditor_guesses"]["without_probe"]["original_guess"]
        
        print(f"  Auditor WITH probe guess: {with_probe_guess}")
        print(f"  Auditor WITHOUT probe guess: {without_probe_guess}")
        
        followed_probe = (with_probe_guess == int(highest_score_pos))
        print(f"  Did auditor follow probe? {followed_probe}")
        print(f"  Was probe correct? {probe_correct}")
        print(f"  Was auditor WITH probe correct? {game['auditor_correct_with_probe']}")
        print(f"  Was auditor WITHOUT probe correct? {game['auditor_correct_without_probe']}")
        
        if probe_correct:
            raw_probe_correct += 1
        if game["auditor_correct_with_probe"]:
            auditor_with_probe_correct += 1
        if game["auditor_correct_without_probe"]:
            auditor_without_probe_correct += 1
        if followed_probe:
            auditor_followed_probe += 1
    
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    
    total = len(games)
    print(f"\nTotal games: {total}")
    print(f"\nRaw probe accuracy (highest score = lie): {raw_probe_correct}/{total} ({100*raw_probe_correct/total:.1f}%)")
    print(f"Auditor WITH probe accuracy: {auditor_with_probe_correct}/{total} ({100*auditor_with_probe_correct/total:.1f}%)")
    print(f"Auditor WITHOUT probe accuracy: {auditor_without_probe_correct}/{total} ({100*auditor_without_probe_correct/total:.1f}%)")
    print(f"Times auditor followed probe: {auditor_followed_probe}/{total} ({100*auditor_followed_probe/total:.1f}%)")
    
    if auditor_without_probe_correct > 0:
        improvement = ((auditor_with_probe_correct - auditor_without_probe_correct) / 
                      auditor_without_probe_correct * 100)
        print(f"\nProbe improvement: {improvement:+.1f}% relative to baseline")
    else:
        print(f"\nProbe improvement: N/A (baseline is 0%)")


def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m src.analysis.ttl.analyze_probe <experiment_dir>")
        print("\nExample:")
        print("  python -m src.analysis.ttl.analyze_probe results/ttl/ttl_8b_both_probes_abc123_def456/")
        sys.exit(1)
    
    experiment_dir = Path(sys.argv[1])
    if not experiment_dir.exists():
        print(f"Error: Directory not found: {experiment_dir}")
        sys.exit(1)
    
    data = load_experiment_data(experiment_dir)
    analyze_probe_performance(data)


if __name__ == "__main__":
    main()
