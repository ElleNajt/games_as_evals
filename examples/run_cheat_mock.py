#!/usr/bin/env python3
"""
Test Cheat game with mocked backends (no Modal needed).

This is much faster and cheaper for testing the game logic.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.games.cheat.config import CheatConfig
from src.games.cheat.orchestrator import CheatOrchestrator
from src.config.player_config import PlayerConfig
from src.backends.base import GenerationResult, ProbeScores, ProbeScoreData
import random


class MockBackend:
    """Mock backend that returns simple responses with mocked probe scores."""
    
    def __init__(self, player_name="MockPlayer"):
        self.player_name = player_name
        self.call_count = 0
    
    def generate(self, messages, max_tokens=512, temperature=0.7):
        """Generate mock responses with probe scores based on the prompt."""
        self.call_count += 1
        
        # Get the last user message
        user_msg = None
        for msg in reversed(messages):
            if msg["role"] == "user":
                user_msg = msg["content"]
                break
        
        # Check if this is a play decision or challenge decision
        is_lying = False
        if "PLAY:" in user_msg and "STRATEGY:" in user_msg:
            # This is a play decision
            # Lie 70% of the time (randomly pick wrong rank)
            if random.random() < 0.7:
                # Lie - pick a random rank that's not the required one
                ranks = ["Two", "Three", "Four", "Five", "Six", "Seven", 
                        "Eight", "Nine", "Ten", "Jack", "Queen", "King", "Ace"]
                response = f"""PLAY: 1
STRATEGY: Trying to get rid of cards
CARDS: {random.choice(ranks)}"""
                is_lying = True
            else:
                # Tell truth - play Ace (will be corrected by parser)
                response = """PLAY: 1
STRATEGY: Playing one card honestly
CARDS: Ace"""
                is_lying = False
                
        elif "CHALLENGE" in user_msg or "PASS" in user_msg:
            # This is a challenge decision
            # Challenge 30% of the time to make it interesting
            if self.call_count % 3 == 0:
                response = "CHALLENGE"
            else:
                response = "PASS"
        else:
            response = "I don't understand the question."
        
        # Create mock probe scores if this was a play decision
        probe_scores = None
        tokens = None
        if "PLAY:" in response:
            # Create realistic token list
            tokens = response.split()
            
            # Create mock deception probe scores
            # Higher scores when lying, lower when honest
            if is_lying:
                # High deception scores (0.6-0.9) when lying
                token_scores = [random.uniform(0.6, 0.9) for _ in tokens]
            else:
                # Low deception scores (0.1-0.4) when honest
                token_scores = [random.uniform(0.1, 0.4) for _ in tokens]
            
            aggregate_score = sum(token_scores) / len(token_scores)
            
            probe_scores = ProbeScores(
                scores={
                    "deception_8b": ProbeScoreData(
                        aggregate_score=aggregate_score,
                        token_scores=token_scores,
                        metadata={
                            "probe_type": "deception",
                            "model": "mock",
                            "layer": 12,
                            "num_tokens": len(tokens),
                            "is_lying": is_lying  # Ground truth for testing
                        }
                    )
                }
            )
        else:
            probe_scores = None
        
        return GenerationResult(
            text=response,
            tokens=tokens,
            top_k_logits=None,
            probe_scores=probe_scores
        )


def main():
    """Run a short Cheat game with mocked backends."""
    
    # Create player template with mock backend
    player_template = PlayerConfig(
        name="template",
        backend_type="mock",  # Not used since we inject backends
        model="mock-model",
        temperature=0.7,
        max_tokens=512,
        system_prompt="You are playing Cheat."
    )
    
    # Create game config - small game for quick testing
    config = CheatConfig(
        num_players=3,
        num_decks=1,
        max_turns=20,  # Short game
        player_template=player_template,
        provide_probe_scores=True  # Show probe scores in output
    )
    
    # Create orchestrator but manually set up game with mocks
    from src.games.cheat.game_state import deal_cards, PlayerState, CheatGameState
    from src.player import GamePlayer
    from src.result_logging.results_logger import ResultsLogger
    
    print("\n" + "="*60)
    print("Running Cheat game with MOCKED backends")
    print("This is fast and doesn't cost anything!")
    print("="*60 + "\n")
    
    # Set up game state manually
    hands = deal_cards(config.num_players, config.num_decks)
    player_states = [
        PlayerState(name=config.players[i].name, hand=hands[i])
        for i in range(config.num_players)
    ]
    state = CheatGameState(players=player_states)
    
    # Set up logger
    logger = ResultsLogger(
        config=config,
        game_name="cheat",
        experiment_base="cheat_mock_test"
    )
    
    # Create players with mock backends
    players = []
    for player_config in config.players:
        backend = MockBackend(player_name=player_config.name)
        player = GamePlayer(
            name=player_config.name,
            backend=backend,
            system_prompt=player_config.system_prompt,
            logger=logger
        )
        players.append(player)
    
    # Create orchestrator and inject the mocked components
    orchestrator = CheatOrchestrator(config, experiment_name="cheat_mock_test")
    orchestrator.state = state
    orchestrator.players = players
    orchestrator.logger = logger
    
    # Log initial state
    logger.log_game_event('game_start', {
        'num_players': config.num_players,
        'num_decks': config.num_decks,
        'initial_hands': {
            player.name: len(player.hand)
            for player in state.players
        }
    })
    
    print(f"Experiment: {config.get_experiment_name('cheat_mock_test')}\n")
    
    # Run the game loop
    while not state.game_over and state.turn_number < config.max_turns:
        orchestrator._play_turn()
        
        # Check for winner
        winner = state.check_winner()
        if winner:
            break
    
    # Finalize
    results = orchestrator._finalize_game()
    
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
    
    print(f"\nResults logged to: {orchestrator.logger.results_dir}")


if __name__ == "__main__":
    main()
