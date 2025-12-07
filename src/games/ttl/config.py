"""
Configuration classes for TTL (Two Truths and a Lie) game.
"""

from dataclasses import dataclass
from typing import Optional

from src.config.game_config import GameConfig
from src.config.player_config import PlayerConfig


@dataclass
class TTLPlayerConfig(PlayerConfig):
    """
    Configuration for a TTL player (deceiver or auditor).

    Attributes:
        role: Player role - "deceiver" or "auditor"
        use_max_score_strategy: If True, auditor picks statement with highest probe score (only for auditor role)
        All other attributes inherited from PlayerConfig
    """

    role: str = "deceiver"  # "deceiver" or "auditor"
    use_max_score_strategy: bool = (
        False  # For auditor: just pick max score instead of using LLM
    )

    def __post_init__(self):
        if self.role not in ["deceiver", "auditor"]:
            raise ValueError(
                f"Invalid role: {self.role}. Must be 'deceiver' or 'auditor'"
            )


@dataclass
class TTLConfig(GameConfig):
    """
    Configuration for TTL game.

    Attributes:
        game_name: Name of the game (default: "ttl")
        use_real_world_facts: If True, deceiver generates from knowledge instead of provided facts
        num_rounds: Number of rounds to play
        deceiver_config: Configuration for deceiver player
        auditor_config: Configuration for auditor player (optional - can use Claude for verification only)
    """

    deceiver_config: Optional[TTLPlayerConfig] = (
        None  # Required - set in __post_init__ if None
    )
    auditor_config: Optional[TTLPlayerConfig] = (
        None  # Optional - can use Claude for ground truth only
    )

    game_name: str = "ttl"
    use_real_world_facts: bool = False
    num_rounds: int = 1

    def __post_init__(self):
        super().__post_init__()

        # Check deceiver config is provided
        if self.deceiver_config is None:
            raise ValueError("deceiver_config is required")

        # Validate deceiver role
        if self.deceiver_config.role != "deceiver":
            raise ValueError(
                f"deceiver_config must have role='deceiver', got '{self.deceiver_config.role}'"
            )

        # Validate auditor role if provided
        if self.auditor_config is not None and self.auditor_config.role != "auditor":
            raise ValueError(
                f"auditor_config must have role='auditor', got '{self.auditor_config.role}'"
            )
