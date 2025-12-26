"""Player state and actions."""

from dataclasses import dataclass, field
from typing import Set


@dataclass
class Player:
    """Represents a player in the game."""
    id: int
    name: str
    variables: Set[int] = field(default_factory=set)
    clause_indices: Set[int] = field(default_factory=set)
    score: int = 0
    
    def has_unassigned_variables(self, assignment: dict[int, bool]) -> bool:
        """Check if player has any unassigned variables."""
        return any(var not in assignment for var in self.variables)
    
    def get_unassigned_variables(self, assignment: dict[int, bool]) -> Set[int]:
        """Get the set of unassigned variables for this player."""
        return {var for var in self.variables if var not in assignment}
    
    def __str__(self) -> str:
        return f"Player {self.id} ({self.name})"
