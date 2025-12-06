"""Analyze lie position patterns in TTL experiments."""

import json
from pathlib import Path
from typing import Dict, Any
from collections import Counter


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


def analyze_lie_patterns(data: Dict[str, Any]) -> None:
    """Analyze patterns in where lies appear and what auditor guesses."""
    games = data["games"]
    
    print("=" * 80)
    print("LIE PATTERN ANALYSIS")
    print("=" * 80)
    print()
    
    # Check if auditor without probe is just guessing positions
    without_probe_guesses = [g["auditor_guesses"]["without_probe"]["original_guess"] for g in games]
    guess_counts = Counter(without_probe_guesses)
    
    print("Auditor WITHOUT probe guess distribution:")
    print("=" * 80)
    for pos in sorted(guess_counts.keys()):
        count = guess_counts[pos]
        pct = 100 * count / len(games)
        print(f"Position {pos}: {count}/{len(games)} ({pct:.1f}%)")
    
    # Check actual lie distribution
    print("\n" + "=" * 80)
    print("Actual lie distribution:")
    print("=" * 80)
    
    lie_positions = [g["revealed_lie"] for g in games]
    lie_counts = Counter(lie_positions)
    
    for pos in sorted(lie_counts.keys()):
        count = lie_counts[pos]
        pct = 100 * count / len(games)
        print(f"Position {pos}: {count}/{len(games)} ({pct:.1f}%)")
    
    # Sample of lies vs truths
    print("\n" + "=" * 80)
    print("Sample of lies vs truths:")
    print("=" * 80)
    
    for i, game in enumerate(games[:5], 1):
        lie_pos = game["revealed_lie"]
        statements = game["deceiver_generation"]["statements"]
        
        print(f"\nRound {i}: Lie at position {lie_pos}")
        for j, stmt in enumerate(statements, 1):
            marker = "  <-- LIE" if j == lie_pos else "  <-- TRUTH"
            # Truncate long statements
            stmt_preview = stmt[:100] + "..." if len(stmt) > 100 else stmt
            print(f"  {j}. {stmt_preview}{marker}")


def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m src.analysis.ttl.analyze_lie_patterns <experiment_dir>")
        print("\nExample:")
        print("  python -m src.analysis.ttl.analyze_lie_patterns results/ttl/ttl_8b_both_probes_abc123_def456/")
        sys.exit(1)
    
    experiment_dir = Path(sys.argv[1])
    if not experiment_dir.exists():
        print(f"Error: Directory not found: {experiment_dir}")
        sys.exit(1)
    
    data = load_experiment_data(experiment_dir)
    analyze_lie_patterns(data)


if __name__ == "__main__":
    main()
