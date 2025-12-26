#!/usr/bin/env python3
"""
Simple test script to verify SAT game integration with games_as_evals backend.
"""

from src.config.player_config import PlayerConfig
from src.games.sat.config import SATConfig
from src.games.sat.orchestrator import SATOrchestrator


def test_sat_integration():
    """Test that SAT game can be created with games_as_evals backend."""
    print("Testing SAT game integration with games_as_evals backend...")

    # Create player template using Modal backend (like Cheat/TTL do)
    player_template = PlayerConfig(
        name="",  # Will be overridden
        backend_type="modal",
        model="meta-llama/Llama-3.1-8B-Instruct",
        probes=[],
        can_see_probes=False,
    )

    # Create SAT config
    config = SATConfig(
        player_template=player_template,
        num_players=2,
        num_variables=8,
        num_clauses=16,
        literals_per_clause=3,
        objective="MAX",
        competitive_mode=False,
    )

    print(f"\nConfig created:")
    print(f"  Players: {config.num_players}")
    print(f"  Variables: {config.num_variables}")
    print(f"  Clauses: {config.num_clauses}")
    print(f"  Objective: {config.objective}")

    # Create orchestrator
    orchestrator = SATOrchestrator(
        config=config, experiment_name="sat_integration_test"
    )

    # Setup game
    orchestrator.setup_game()

    # Run game (just setup for now)
    state = orchestrator.run_game()

    print("\n✓ SAT game successfully integrated with games_as_evals backend!")
    print(f"✓ Game state created with {len(state.players)} players")
    print(f"✓ Formula has {len(state.formula.clauses)} clauses")
    print(f"✓ Logging to: {orchestrator.logger.results_dir}")

    return True


if __name__ == "__main__":
    try:
        test_sat_integration()
    except Exception as e:
        print(f"\n✗ Integration test failed: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
