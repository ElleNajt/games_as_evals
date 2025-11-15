#!/usr/bin/env python3
"""
Run a Werewolf game with 8B model and both deception + hallucination probes.

This script demonstrates using the ExperimentConfig system to configure
a game with consistent model and probe settings.
"""

from src.config.experiment_config import get_experiment_config
from src.games.werewolf import WerewolfConfig, GameCoordinator

def main():
    # Get 8B experiment config with both probes
    exp_config = get_experiment_config("8b_both")
    
    print("=" * 70)
    print("Running Werewolf Game with 8B Model + Both Probes")
    print("=" * 70)
    print(f"Model: {exp_config.model}")
    print(f"Probes: {exp_config.probes}")
    print(f"Top-k logits: {exp_config.top_k_logits}")
    print("=" * 70)
    print()
    
    # Create Werewolf configuration using experiment config
    config = WerewolfConfig(
        **exp_config.to_werewolf_config_kwargs(
            num_players=5,
            num_werewolves=2,
            show_probe_scores=True  # Show probe scores to players during game
        )
    )
    
    # Run the game
    coordinator = GameCoordinator(config, experiment_name="werewolf_8b_demo")
    results = coordinator.run_game()
    
    # Print results
    print()
    print("=" * 70)
    print("GAME RESULTS")
    print("=" * 70)
    print(f"Winner: {results.get('winner', 'Unknown')}")
    print(f"Game length: {results.get('num_rounds', 0)} rounds")
    print(f"Results saved to: results/werewolf/werewolf_8b_demo/")
    print()
    print("Check messages.jsonl for full interaction logs including:")
    print("  - All player messages")
    print("  - Probe scores (deception_8b, hallucination_8b)")
    print("  - Top-k logits for each token")
    print("  - Timestamps and metadata")

if __name__ == "__main__":
    main()
