"""Analyze probe activations by player role in Werewolf games."""

import json
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict


def load_experiment_data(experiment_dir: Path) -> Dict[str, Any]:
    """Load batch results and individual game results."""
    batch_file = experiment_dir / "batch_results.json"
    with open(batch_file) as f:
        batch_data = json.load(f)
    
    games = []
    for i in range(1, batch_data["total_rounds"] + 1):
        game_dir = experiment_dir / f"game{i}"
        if not game_dir.exists():
            continue
            
        # Load game stats which contains role information
        stats_file = game_dir / "game_stats.json"
        if stats_file.exists():
            with open(stats_file) as f:
                games.append(json.load(f))
    
    return {"batch": batch_data, "games": games}


def analyze_probe_by_role(data: Dict[str, Any]) -> None:
    """Analyze probe activations grouped by player role."""
    games = data["games"]
    
    print("=" * 80)
    print("PROBE ACTIVATIONS BY ROLE")
    print("=" * 80)
    print()
    
    # Collect activations by role
    activations_by_role = defaultdict(list)
    
    for game_idx, game in enumerate(games, 1):
        if "role_reveal_activations" not in game:
            print(f"Warning: Game {game_idx} missing role_reveal_activations")
            continue
            
        role_activations = game["role_reveal_activations"]
        player_roles = game.get("player_roles", {})
        
        print(f"Game {game_idx}:")
        print(f"  Winner: {game.get('winner', 'Unknown')}")
        print(f"  Turns: {game.get('turns', 'Unknown')}")
        print(f"  Role activations:")
        
        for player_name, activation in role_activations.items():
            role = player_roles.get(player_name, "Unknown")
            if activation is not None:
                activations_by_role[role].append(activation)
                print(f"    {player_name} ({role}): {activation:.3f}")
        print()
    
    # Summary statistics by role
    print("=" * 80)
    print("SUMMARY BY ROLE")
    print("=" * 80)
    print()
    
    for role in sorted(activations_by_role.keys()):
        activations = activations_by_role[role]
        if activations:
            avg = sum(activations) / len(activations)
            min_val = min(activations)
            max_val = max(activations)
            print(f"{role.upper()}:")
            print(f"  Count: {len(activations)}")
            print(f"  Average: {avg:.3f}")
            print(f"  Range: [{min_val:.3f}, {max_val:.3f}]")
            print()


def analyze_game_outcomes(data: Dict[str, Any]) -> None:
    """Analyze game outcomes by faction."""
    games = data["games"]
    
    print("=" * 80)
    print("GAME OUTCOMES")
    print("=" * 80)
    print()
    
    villager_wins = sum(1 for g in games if g.get("winner") == "Villagers")
    werewolf_wins = sum(1 for g in games if g.get("winner") == "Werewolves")
    total = len(games)
    
    print(f"Total games: {total}")
    print(f"Villager wins: {villager_wins} ({100*villager_wins/total if total > 0 else 0:.1f}%)")
    print(f"Werewolf wins: {werewolf_wins} ({100*werewolf_wins/total if total > 0 else 0:.1f}%)")
    
    # Average game length
    turns = [g.get("turns", 0) for g in games if "turns" in g]
    if turns:
        avg_turns = sum(turns) / len(turns)
        print(f"\nAverage game length: {avg_turns:.1f} turns")
        print(f"Turn range: [{min(turns)}, {max(turns)}]")


def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m src.analysis.werewolf.analyze_probe_by_role <experiment_dir>")
        print("\nExample:")
        print("  python -m src.analysis.werewolf.analyze_probe_by_role results/werewolf/werewolf_8b_both_probes_xxx/")
        sys.exit(1)
    
    experiment_dir = Path(sys.argv[1])
    if not experiment_dir.exists():
        print(f"Error: Directory not found: {experiment_dir}")
        sys.exit(1)
    
    data = load_experiment_data(experiment_dir)
    analyze_probe_by_role(data)
    analyze_game_outcomes(data)


if __name__ == "__main__":
    main()
