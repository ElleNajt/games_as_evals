#!/usr/bin/env python3
"""
Test true OMNISCIENT mode with mock backend.

An omniscient player can see all players' hands and should dominate.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.games.cheat.config import CheatConfig
from src.games.cheat.orchestrator import CheatOrchestrator
from src.games.cheat.game_state import deal_cards, PlayerState, CheatGameState
from src.config.player_config import PlayerConfig
from src.player import GamePlayer
from src.result_logging.results_logger import ResultsLogger
from src.backends.base import GenerationResult, ProbeScores, ProbeScoreData
import random


class MockBackend:
    """Mock backend that returns simple responses."""
    
    def __init__(self, player_name="MockPlayer", is_omniscient=False):
        self.player_name = player_name
        self.is_omniscient = is_omniscient
        self.call_count = 0
    
    def generate(self, messages, max_tokens=512, temperature=0.7):
        """Generate mock responses."""
        self.call_count += 1
        
        # Get the last user message
        user_msg = None
        for msg in reversed(messages):
            if msg["role"] == "user":
                user_msg = msg["content"]
                break
        
        # Check if this is a play decision or challenge decision
        if "PLAY:" in user_msg and "CARDS:" in user_msg:
            # This is a play decision
            # Normal players lie 70% of the time
            if random.random() < 0.7:
                ranks = ["Two", "Three", "Four", "Five", "Six", "Seven", 
                        "Eight", "Nine", "Ten", "Jack", "Queen", "King", "Ace"]
                response = f"""PLAY: 1
CARDS: {random.choice(ranks)}"""
            else:
                response = """PLAY: 1
CARDS: Ace"""
                
        elif "CHALLENGE" in user_msg or "PASS" in user_msg:
            # This is a challenge decision
            if self.is_omniscient and "OMNISCIENT VIEW" in user_msg:
                # Parse the omniscient view to make perfect decisions
                # Look for the player's actual hand in the prompt
                import re
                
                # Extract what rank they claimed to play
                claimed_match = re.search(r'claimed to play \d+ (\w+)', user_msg)
                if claimed_match:
                    claimed_rank = claimed_match.group(1)
                    
                    # Extract their actual hand
                    hand_match = re.search(r"ACTUAL hand.*?\n({[^}]+})", user_msg, re.DOTALL)
                    if hand_match:
                        hand_str = hand_match.group(1)
                        
                        # Check if they have the claimed rank in their hand
                        # If the claimed rank is NOT in their hand JSON, they must be lying
                        if f'"{claimed_rank}"' in hand_str or f"'{claimed_rank}'" in hand_str:
                            # They have the rank - might be honest
                            # Still challenge sometimes to test
                            response = "PASS"
                        else:
                            # They DON'T have the rank - definitely lying!
                            response = "CHALLENGE"
                    else:
                        response = "CHALLENGE"  # If can't parse, challenge
                else:
                    response = "PASS"
            else:
                # No omniscient view - random challenges (30% of time)
                response = "CHALLENGE" if self.call_count % 3 == 0 else "PASS"
        else:
            response = "I don't understand the question."
        
        return GenerationResult(
            text=response,
            tokens=None,
            top_k_logits=None,
            probe_scores=None
        )


def run_omniscient_test():
    """Run a single game with one omniscient player."""
    
    print("\n" + "="*70)
    print("TEST: TRUE OMNISCIENT MODE (Mock Backend)")
    print("="*70)
    print("Player_1_OMNISCIENT can see ALL players' hands")
    print("They should catch lies perfectly and dominate")
    print("="*70 + "\n")
    
    # Set up game state manually
    num_players = 3
    hands = deal_cards(num_players, num_decks=1)
    
    # Create player configs
    players = [
        PlayerConfig(
            name="Player_1_OMNISCIENT",
            backend_type="mock",
            model="mock-model",
            omniscient_view=True,  # TRUE OMNISCIENT - sees all hands
            system_prompt="You are playing Cheat. You have perfect information about all hands.",
        ),
        PlayerConfig(
            name="Player_2",
            backend_type="mock",
            model="mock-model",
            system_prompt="You are playing Cheat."
        ),
        PlayerConfig(
            name="Player_3",
            backend_type="mock",
            model="mock-model",
            system_prompt="You are playing Cheat."
        ),
    ]
    
    # Create config
    config = CheatConfig(
        num_players=num_players,
        num_decks=1,
        max_turns=30,
    )
    config.players = players
    
    # Set up game state
    player_states = [
        PlayerState(name=players[i].name, hand=hands[i])
        for i in range(num_players)
    ]
    state = CheatGameState(players=player_states)
    
    # Set up logger
    logger = ResultsLogger(
        config=config,
        game_name="cheat",
        experiment_base="omniscient_test",
    )
    
    # Create players with mock backends
    game_players = []
    for i, player_config in enumerate(players):
        is_omniscient = player_config.omniscient_view
        backend = MockBackend(player_name=player_config.name, is_omniscient=is_omniscient)
        player = GamePlayer(
            name=player_config.name,
            backend=backend,
            system_prompt=player_config.system_prompt,
            logger=logger
        )
        game_players.append(player)
    
    # Create orchestrator and inject the mocked components
    orchestrator = CheatOrchestrator(config, experiment_name="omniscient_test")
    orchestrator.state = state
    orchestrator.players = game_players
    orchestrator.logger = logger
    
    # Log initial state
    logger.log_game_event('game_start', {
        'num_players': num_players,
        'num_decks': 1,
    })
    
    # Run the game loop
    turn_count = 0
    while not state.game_over and turn_count < config.max_turns:
        orchestrator._play_turn()
        turn_count += 1
        
        # Check for winner
        winner = state.check_winner()
        if winner:
            break
    
    # Finalize
    results = orchestrator._finalize_game()
    
    # Print analysis
    print("\n" + "="*70)
    print("TEST RESULTS")
    print("="*70)
    print(f"Winner: {results.get('winner', 'None (max turns)')}")
    print(f"Total turns: {results['total_turns']}")
    print(f"\nFinal card counts:")
    for player, count in results['final_hands'].items():
        print(f"  {player}: {count} cards")
    
    if results.get('winner') == 'Player_1_OMNISCIENT':
        print("\n✓ SUCCESS: Omniscient player won as expected!")
        print("  Perfect information leads to dominance")
    else:
        print(f"\n⚠ Note: Omniscient player did not win")
        print("  (With perfect information, they should usually win)")
        if results['final_hands']['Player_1_OMNISCIENT'] < 10:
            print("  But they have fewer cards, showing strong performance")
    
    print("="*70)
    
    return results


if __name__ == "__main__":
    run_omniscient_test()
