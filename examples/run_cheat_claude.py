#!/usr/bin/env python3
"""
Example: Run a game of Cheat (Bullshit) with Claude.

This demonstrates the Cheat card game using Claude backend (no probes).
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.games.cheat.config import CheatConfig
from src.games.cheat.orchestrator import CheatOrchestrator
from src.config.player_config import PlayerConfig


def main():
    # Create player template using Claude backend
    player_template = PlayerConfig(
        name="template",  # Will be replaced with Player_1, Player_2, etc.
        backend_type="claude",
        backend_config={},
        system_prompt="""You are playing the card game Cheat (also called Bullshit).

Your goal is to be the first to get rid of all your cards.

Key strategies:
- You can lie about which cards you're playing
- Watch for patterns in other players' behavior
- Challenge when you think someone is lying
- But be careful - wrong challenges are costly!

Play strategically to win."""
    )
    
    # Create game config
    config = CheatConfig(
        experiment_base="cheat_claude_test",
        num_players=3,  # Smaller game for faster testing
        num_decks=1,
        max_turns=100,
        player_template=player_template
    )
    
    # Run the game
    print("\nStarting Cheat game with Claude backend...")
    print("This will use the Claude CLI for player decisions.\n")
    
    orchestrator = CheatOrchestrator(config)
    results = orchestrator.run_game()
    
    # Print summary
    print("\n" + "="*60)
    print("GAME SUMMARY")
    print("="*60)
    print(f"Winner: {results['winner']}")
    print(f"Total turns: {results['total_turns']}")
    print(f"\nFinal card counts:")
    for player, cards in results['final_hands'].items():
        print(f"  {player}: {cards} cards")
    print("="*60)


if __name__ == "__main__":
    main()
