#!/usr/bin/env python3
"""
Test 70B model with both deception and hallucination probes.
Quick single game to check probe separation.
"""

from src.games.cheat.config import CheatConfig
from src.config.player_config import PlayerConfig
from src.games.cheat.orchestrator import CheatOrchestrator

def main():
    print("="*60)
    print("Running 1 game with 70B model + both probes")
    print("="*60)
    
    # Create 3 players with 70B model and both probes
    players = [
        PlayerConfig(
            name="Player_1",
            backend_type="modal",
            model="meta-llama/Llama-3.1-70B-Instruct",
            probes=["deception_8b", "hallucination_8b"],
            can_see_probes=True,  # Can see probe scores
            temperature=0.7,
        ),
        PlayerConfig(
            name="Player_2",
            backend_type="modal",
            model="meta-llama/Llama-3.1-70B-Instruct",
            probes=["deception_8b", "hallucination_8b"],
            can_see_probes=False,  # Cannot see probe scores
            temperature=0.7,
        ),
        PlayerConfig(
            name="Player_3",
            backend_type="modal",
            model="meta-llama/Llama-3.1-70B-Instruct",
            probes=["deception_8b", "hallucination_8b"],
            can_see_probes=False,  # Cannot see probe scores
            temperature=0.7,
        ),
    ]
    
    config = CheatConfig(
        num_players=3,
        num_decks=1,
        max_turns=50,
        provide_probe_scores=True
    )
    
    config.players = players
    
    experiment_name = "cheat_70b_both_probes_test"
    orchestrator = CheatOrchestrator(config, experiment_name=experiment_name)
    
    print(f"\nStarting game with experiment name: {experiment_name}")
    print("All players using 70B model with both probes")
    print("Player_1 can see probe scores, others cannot\n")
    
    orchestrator.run_game()
    
    print("\n" + "="*60)
    print("Game completed!")
    print(f"Results saved to: {orchestrator.logger.results_dir}")
    print("="*60)

if __name__ == "__main__":
    main()
