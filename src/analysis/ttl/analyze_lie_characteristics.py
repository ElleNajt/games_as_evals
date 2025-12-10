"""Analyze characteristics of lies vs truths in TTL experiments."""

import json
from pathlib import Path
from typing import Dict, Any, List


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


def analyze_lie_characteristics(data: Dict[str, Any]) -> None:
    """Analyze characteristics of lies vs truths."""
    games = data["games"]
    
    print("=" * 80)
    print("LIE vs TRUTH CHARACTERISTICS")
    print("=" * 80)
    print()
    
    lie_lengths = []
    truth_lengths = []
    
    for game in games:
        lie_pos = game["revealed_lie"]
        statements = game["deceiver_generation"]["statements"]
        
        for i, stmt in enumerate(statements, 1):
            if i == lie_pos:
                lie_lengths.append(len(stmt))
            else:
                truth_lengths.append(len(stmt))
    
    print("Statement lengths:")
    print(f"  Average lie length: {sum(lie_lengths)/len(lie_lengths):.1f} chars")
    print(f"  Average truth length: {sum(truth_lengths)/len(truth_lengths):.1f} chars")
    
    # Sample lies
    print("\n" + "=" * 80)
    print("Sample lies to look for patterns:")
    print("=" * 80)
    
    for i, game in enumerate(games[:min(10, len(games))], 1):
        lie_pos = game["revealed_lie"]
        lie_stmt = game["deceiver_generation"]["statements"][lie_pos - 1]
        
        print(f"\nRound {i} LIE:")
        print(f"  {lie_stmt}")
    
    # Check for common patterns
    print("\n" + "=" * 80)
    print("Do lies contain specific keywords/patterns?")
    print("=" * 80)
    
    lie_texts = [g["deceiver_generation"]["statements"][g["revealed_lie"] - 1] for g in games]
    
    patterns = {
        'family/relatives': ['parent', 'mother', 'father', 'brother', 'sister', 'husband', 'wife', 'family'],
        'locations': ['from', 'Tokyo', 'originally', 'born in', 'lives in'],
        'education': ['degree', 'Master', 'Bachelor', 'Ph.D.', 'studied'],
        'career/work': ['works', 'career', 'profession', 'job'],
        'superlatives': ['first-ever', 'renowned', 'award-winning', 'famous'],
    }
    
    for category, words in patterns.items():
        count = sum(1 for lie in lie_texts if any(word.lower() in lie.lower() for word in words))
        pct = 100 * count / len(lie_texts) if lie_texts else 0
        print(f"{category}: {count}/{len(lie_texts)} lies ({pct:.0f}%)")


def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m src.analysis.ttl.analyze_lie_characteristics <experiment_dir>")
        print("\nExample:")
        print("  python -m src.analysis.ttl.analyze_lie_characteristics results/ttl/ttl_8b_both_probes_abc123_def456/")
        sys.exit(1)
    
    experiment_dir = Path(sys.argv[1])
    if not experiment_dir.exists():
        print(f"Error: Directory not found: {experiment_dir}")
        sys.exit(1)
    
    data = load_experiment_data(experiment_dir)
    analyze_lie_characteristics(data)


if __name__ == "__main__":
    main()
