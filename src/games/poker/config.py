"""
Configuration for Kuhn Poker.
"""

from dataclasses import dataclass
from typing import List, Optional
from src.config.game_config import GameConfig
from src.config.player_config import PlayerConfig


@dataclass
class PokerConfig(GameConfig):
    """Configuration for Kuhn Poker.

    Kuhn Poker is a simplified poker game that serves as a standard test problem
    in game theory. It's the simplest game that exhibits bluffing behavior.

    Game Rules:
    - 2 players, each gets 1 card (private)
    - N cards ranked from 1 (lowest) to N (highest)
    - For classic 3-card: Jack (1), Queen (2), King (3)
    - Each player antes 1 chip
    - Single betting round
    - At showdown, higher card wins
    - Bet size: 1 chip
    """

    # Game parameters
    n_cards: int = 3  # Number of cards in the deck (default: 3 for classic Kuhn Poker)
    num_games: int = 100  # Number of games to run
    seed: Optional[int] = None  # Random seed for reproducibility

    # Reasoning control
    use_reasoning: bool = True  # Whether to use chain-of-thought reasoning
    share_reasoning: bool = False  # Whether to share opponent's reasoning

    # Probe visibility control
    provide_probe_scores: bool = False  # If True, show probe scores to players

    def __post_init__(self):
        """Validate config."""
        super().__post_init__()

        # Kuhn Poker is always 2-player
        if len(self.players) != 2:
            raise ValueError("Kuhn Poker requires exactly 2 players")

        if self.n_cards < 3:
            raise ValueError("n_cards must be >= 3")

        # Validate player names
        for i, player in enumerate(self.players):
            if not player.name:
                player.name = f"Player_{i}"
