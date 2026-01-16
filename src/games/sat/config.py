"""
Configuration for the 3-SAT game.
"""

from dataclasses import dataclass
from typing import Dict, Optional

from src.config.game_config import GameConfig
from src.config.player_config import PlayerConfig


@dataclass
class SATConfig(GameConfig):
    """Configuration for 3-SAT cooperative game.

    In this game, players collectively try to maximize the number of satisfied
    clauses in a 3-SAT formula by choosing variable assignments.
    """

    # Player template (will be duplicated for each player)
    player_template: Optional[PlayerConfig] = None

    # Game parameters
    num_players: int = 2
    num_variables: int = 8
    num_clauses: int = 64
    literals_per_clause: int = 3

    # Game modes
    competitive_mode: bool = False  # If True, players compete for individual scores
    two_winners_mode: bool = False  # If True, both highest and lowest scorers win
    symmetric: bool = False  # If True, generate symmetric formula

    # Competitiveness instruction (appears in system prompt)
    competitiveness_instruction: str = "You are playing a COMPETITIVE 3-SAT game. Your goal is to satisfy as many of YOUR clauses as possible to WIN the game."

    # Objective
    objective: str = "MAX"  # "MAX" or "MIN" - maximize or minimize satisfied clauses

    # Game flow control
    enable_negotiation: bool = True  # Negotiation phase before assignments
    num_negotiation_rounds: int = 3  # Number of negotiation rounds
    max_turns: Optional[int] = None  # Maximum rounds (None = unlimited)

    # Probe visibility control (when using Modal backend with probes)
    show_probe_scores: bool = False  # If True, annotate negotiation messages with probe scores for players who can_see_probes
    probe_thresholds: Optional[Dict[str, Dict[str, float]]] = (
        None  # Thresholds for interpreting probe scores
    )

    def __post_init__(self):
        """Validate config and generate player list."""
        super().__post_init__()

        # Generate player list from template
        if self.player_template is not None:
            self.players = []
            for i in range(self.num_players):
                # Build config dict
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

        # Validate
        if self.player_template is not None:
            if len(self.players) < 2:
                raise ValueError("SAT game requires at least 2 players")

            if self.num_variables < self.num_players:
                raise ValueError(
                    f"Need at least {self.num_players} variables for {self.num_players} players"
                )

            if self.num_clauses < 1:
                raise ValueError("Need at least 1 clause")

            if self.literals_per_clause not in [2, 3]:
                raise ValueError("Only 2-SAT and 3-SAT are supported")

            if self.objective not in ["MAX", "MIN"]:
                raise ValueError("Objective must be 'MAX' or 'MIN'")
