"""Objective functions for the 3-SAT game."""

from dataclasses import dataclass
from typing import List, Callable


@dataclass
class Objective:
    """Defines the winning objective for the game.
    
    Attributes:
        name: Short name (e.g., "MAX", "MIN")
        description: Description for prompts (e.g., "maximizing your satisfied clauses")
        setup_text: Explanation shown in initial setup (e.g., "You score 1 point for each satisfied clause. Higher score wins.")
        sort_key: Function that takes a player and returns a value for sorting (higher values win)
    """
    name: str
    description: str
    setup_text: str
    sort_key: Callable
    
    @staticmethod
    def create_max() -> 'Objective':
        """Create MAX objective (maximize satisfied clauses, higher score wins)."""
        return Objective(
            name="MAX",
            description="maximizing your satisfied clauses",
            setup_text="You score 1 point for each satisfied clause. HIGHER score wins.",
            sort_key=lambda player: player.score
        )
    
    @staticmethod
    def create_min() -> 'Objective':
        """Create MIN objective (minimize satisfied clauses, lower score wins)."""
        return Objective(
            name="MIN",
            description="minimizing your satisfied clauses (lower score wins)",
            setup_text="You score 1 point for each satisfied clause. LOWER score wins.",
            sort_key=lambda player: -player.score  # Negate so lower scores sort higher
        )
    
    @staticmethod
    def from_string(name: str) -> 'Objective':
        """Create objective from string name ("MAX" or "MIN")."""
        if name.upper() == "MAX":
            return Objective.create_max()
        elif name.upper() == "MIN":
            return Objective.create_min()
        else:
            raise ValueError(f"Unknown objective: {name}. Must be 'MAX' or 'MIN'")
