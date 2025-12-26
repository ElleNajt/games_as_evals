"""Game state management."""

from dataclasses import dataclass, field
from typing import List, Dict
from enum import Enum

from .formula import Formula
from .player import Player
from .objective import Objective


class Phase(Enum):
    """Game phases."""
    THINKING = "thinking"
    NEGOTIATION = "negotiation"
    ASSIGNMENT = "assignment"
    REVELATION = "revelation"
    GAME_OVER = "game_over"


@dataclass
class GameState:
    """Manages the overall game state."""
    formula: Formula
    players: List[Player]
    objective: Objective = field(default_factory=Objective.create_max)
    assignment: Dict[int, bool] = field(default_factory=dict)
    phase: Phase = Phase.THINKING
    round_number: int = 1
    pending_assignments: Dict[int, tuple[int, bool]] = field(default_factory=dict)  # player_id -> (variable, value)
    
    def is_game_over(self) -> bool:
        """Check if all variables have been assigned."""
        all_vars = self.formula.get_all_variables()
        return all(var in self.assignment for var in all_vars)
    
    def calculate_scores(self):
        """Calculate and update player scores based on satisfied clauses."""
        for player in self.players:
            player.score = 0
            for clause_idx in player.clause_indices:
                clause = self.formula.clauses[clause_idx]
                if clause.evaluate(self.assignment) is True:
                    player.score += 1
    
    def advance_phase(self):
        """Move to the next phase."""
        if self.phase == Phase.THINKING:
            self.phase = Phase.NEGOTIATION
        elif self.phase == Phase.NEGOTIATION:
            self.phase = Phase.ASSIGNMENT
        elif self.phase == Phase.ASSIGNMENT:
            self.phase = Phase.REVELATION
        elif self.phase == Phase.REVELATION:
            # Apply assignments and check if game is over
            for player_id, (var, value) in self.pending_assignments.items():
                self.assignment[var] = value
            self.pending_assignments.clear()
            
            if self.is_game_over():
                self.phase = Phase.GAME_OVER
                self.calculate_scores()
            else:
                self.round_number += 1
                self.phase = Phase.THINKING
    
    def submit_assignment(self, player_id: int, variable: int, value: bool):
        """Player submits their variable assignment for this round."""
        player = self.players[player_id]
        if variable not in player.variables:
            raise ValueError(f"Player {player_id} does not own variable {variable}")
        if variable in self.assignment:
            raise ValueError(f"Variable {variable} has already been assigned")
        self.pending_assignments[player_id] = (variable, value)
    
    def all_players_submitted(self) -> bool:
        """Check if all players with unassigned variables have submitted."""
        players_with_vars = [
            p for p in self.players 
            if p.has_unassigned_variables(self.assignment)
        ]
        return len(self.pending_assignments) == len(players_with_vars)
