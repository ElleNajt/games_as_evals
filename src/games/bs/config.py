"""Configuration classes for BS (Cheat/I Doubt It) game."""

from dataclasses import dataclass
from typing import Optional, List
from src.config.player_config import PlayerConfig
from src.config.game_config import GameConfig


@dataclass
class BSPlayerConfig(PlayerConfig):
    """
    Configuration for a BS player.

    Attributes:
        All attributes inherited from PlayerConfig
    """
    pass


@dataclass
class BSConfig(GameConfig):
    """
    Configuration for BS game.

    Attributes:
        game_name: Name of the game (default: "bs")
        num_players: Number of players (2-10)
        player_configs: List of player configurations
        max_rounds: Maximum rounds before declaring draw (default: 1000)
        allow_passing: Whether players can pass their turn (default: True)
    """
    game_name: str = "bs"
    num_players: int = 4
    player_configs: Optional[List[BSPlayerConfig]] = None
    max_rounds: int = 1000
    allow_passing: bool = True

    def __post_init__(self):
        super().__post_init__()

        # Validate number of players
        if not 2 <= self.num_players <= 10:
            raise ValueError(f"num_players must be 2-10, got {self.num_players}")

        # Check player configs
        if self.player_configs is None:
            raise ValueError("player_configs is required")

        if len(self.player_configs) != self.num_players:
            raise ValueError(
                f"Number of player_configs ({len(self.player_configs)}) "
                f"must match num_players ({self.num_players})"
            )
