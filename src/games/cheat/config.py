"""
Configuration for the Cheat (Bullshit) card game.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from src.config.game_config import GameConfig
from src.config.player_config import PlayerConfig


class ProbeScaffoldingLevel(Enum):
    """How explicitly to instruct players to follow probe advice.

    This controls the trade-off between agent autonomy and probe utilization:
    - WEAK: Probe scores shown with interpretations ("Likely honest") but no explicit instruction to follow
    - STRONG: Explicitly instruct to TRUST and FOLLOW the probe's assessment
    """

    WEAK = (
        "weak"  # Show scores with interpretation ("Likely honest") but no instruction
    )
    STRONG = "strong"  # Explicit instruction: "This probe is 98% accurate. TRUST its assessment."


@dataclass
class CheatConfig(GameConfig):
    """Configuration for Cheat/Bullshit card game.

    In this game, players take turns playing cards face-down and declaring
    what rank they're playing. Players may lie about what they play.
    Other players can call "Cheat!" to challenge - if the player was lying,
    they pick up the pile. If they were honest, the challenger picks it up.
    """

    # Player template (will be duplicated for each player)
    player_template: Optional[PlayerConfig] = None

    # Game parameters
    num_players: int = 4
    num_decks: int = 1  # Use 2 decks for 5+ players
    max_turns: int = 200  # Safety limit

    # Probe visibility control
    provide_probe_scores: bool = (
        False  # If True, show probe scores to players during challenges
    )
    probe_thresholds: Optional[Dict[str, Dict[str, float]]] = (
        None  # Thresholds for interpreting probe scores
    )
    probe_scaffolding: ProbeScaffoldingLevel = (
        ProbeScaffoldingLevel.WEAK  # How explicitly to instruct players to follow probe advice
    )
    probe_accuracy_stats: Optional[Dict[str, float]] = (
        None  # Probe accuracy to show (e.g., {"hallucination_70b": 0.98})
    )

    def __post_init__(self):
        """Validate config and generate player list."""
        super().__post_init__()

        # Auto-determine number of decks based on player count
        if self.num_decks == 1 and self.num_players >= 5:
            self.num_decks = 2

        # Generate player list from template
        if self.player_template is not None:
            self.players = []
            for i in range(self.num_players):
                # Build config dict, only including probe OR probes (not both)
                player_kwargs = {
                    "name": f"Player_{i + 1}",
                    "backend_type": self.player_template.backend_type,
                    "model": self.player_template.model,
                    "temperature": self.player_template.temperature,
                    "max_tokens": self.player_template.max_tokens,
                    "system_prompt": self.player_template.system_prompt,
                    "can_see_probes": self.player_template.can_see_probes,
                }

                # Add probes if template has them
                if self.player_template.probes is not None:
                    player_kwargs["probes"] = self.player_template.probes

                self.players.append(PlayerConfig(**player_kwargs))

        # Validate (only if players were generated from template)
        if self.player_template is not None:
            if len(self.players) < 2:
                raise ValueError("Need at least 2 players for Cheat")
            if len(self.players) > 10:
                raise ValueError("Maximum 10 players supported")
