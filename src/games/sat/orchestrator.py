"""
Simple SAT game orchestrator using games_as_evals backend.
"""

import json
from typing import Dict, List, Optional

from src.backends import create_backend
from src.games.sat.config import SATConfig
from src.games.sat.formula import Formula
from src.games.sat.game_state import GameState
from src.games.sat.objective import Objective
from src.games.sat.player import Player as SATPlayer
from src.player import GamePlayer
from src.result_logging.results_logger import ResultsLogger


class SATOrchestrator:
    """Orchestrates a 3-SAT game."""

    def __init__(
        self,
        config: SATConfig,
        experiment_name: str = "sat_test",
        game_id: Optional[int] = None,
    ):
        self.config = config
        self.experiment_name = experiment_name
        self.game_id = game_id
        self.state: Optional[GameState] = None
        self.players: List[GamePlayer] = []
        self.logger: Optional[ResultsLogger] = None

    def setup_game(self):
        """Initialize game state and players."""
        # Generate formula
        formula = Formula(
            num_variables=self.config.num_variables,
            num_clauses=self.config.num_clauses,
            literals_per_clause=self.config.literals_per_clause,
        )

        # Generate clauses (random or symmetric based on config)
        if self.config.symmetric:
            formula.generate_symmetric(num_players=self.config.num_players)
        else:
            formula.generate_random(num_players=self.config.num_players)

        # Create SAT players
        sat_players = []
        variables_per_player = self.config.num_variables // self.config.num_players
        for i in range(self.config.num_players):
            start_var = i * variables_per_player
            end_var = (
                start_var + variables_per_player
                if i < self.config.num_players - 1
                else self.config.num_variables
            )
            variables = set(range(start_var, end_var))

            sat_player = SATPlayer(
                id=i, name=self.config.players[i].name, variables=variables
            )
            sat_players.append(sat_player)

        # Create game state
        objective = Objective.from_string(self.config.objective)
        self.state = GameState(
            formula=formula,
            players=sat_players,
            objective=objective,
        )

        # Setup logging
        self.logger = ResultsLogger(
            config=self.config,
            game_name="sat",
            experiment_base=self.experiment_name,
            game_id=self.game_id,
        )

        # Create game players with backends
        self.players = []
        for player_config in self.config.players:
            backend = create_backend(
                backend_type=player_config.backend_type,
                model=player_config.model,
                probes=player_config.probes,
            )
            player = GamePlayer(
                name=player_config.name,
                backend=backend,
                system_prompt=player_config.system_prompt
                or self._get_default_system_prompt(),
                logger=self.logger,
            )
            self.players.append(player)

        # Log initial state
        self.logger.log_game_event(
            "game_start",
            {
                "num_players": self.config.num_players,
                "num_variables": self.config.num_variables,
                "num_clauses": self.config.num_clauses,
                "objective": self.config.objective,
                "formula": str(formula),
            },
        )

    def _get_default_system_prompt(self) -> str:
        """Get default system prompt for SAT game."""
        return """You are playing a cooperative 3-SAT game. 
Your goal is to work with other players to maximize the number of satisfied clauses.
You will be assigned specific variables to set to True or False.
Think strategically and communicate with other players to coordinate your choices."""

    def run_game(self):
        """Run the SAT game."""
        if self.state is None:
            raise ValueError("Game not setup. Call setup_game() first.")

        print(f"\nStarting SAT game with {self.config.num_players} players")
        print(f"Formula: {self.state.formula}")
        print(f"Objective: {self.config.objective}")
        print(f"Players: {[p.name for p in self.players]}")
        print(
            f"Variables per player: {[self.state.players[i].variables for i in range(len(self.state.players))]}\n"
        )

        # Simple game loop: each round, each player assigns one variable
        while (
            not self.state.is_game_over()
            and self.state.round_number <= self.config.max_turns
        ):
            print(f"=== Round {self.state.round_number} ===")

            # Each player picks a variable to assign
            for i, player in enumerate(self.players):
                sat_player = self.state.players[i]

                # Find unassigned variables for this player
                unassigned = [
                    v for v in sat_player.variables if v not in self.state.assignment
                ]
                if not unassigned:
                    continue

                # Create prompt for player
                prompt = self._create_assignment_prompt(sat_player, unassigned)

                # Get player's choice
                print(f"{player.name} is choosing a variable...")
                response = player.query(prompt)

                # Parse response (simple version - just pick first unassigned variable and set to True for now)
                variable = unassigned[0]
                value = True

                print(f"  {player.name} sets x{variable} = {value}")
                self.state.submit_assignment(i, variable, value)

            # Advance to revelation phase
            self.state.phase = (
                self.state.phase.REVELATION
                if hasattr(self.state.phase, "REVELATION")
                else None
            )
            self.state.advance_phase()

        # Calculate final scores
        self.state.calculate_scores()

        # Count satisfied clauses
        satisfied = sum(
            1
            for clause in self.state.formula.clauses
            if clause.evaluate(self.state.assignment) is True
        )

        print(f"\n=== Game Over ===")
        print(f"Final assignment: {self.state.assignment}")
        print(f"Satisfied clauses: {satisfied}/{len(self.state.formula.clauses)}")
        print(f"Player scores: {[(p.name, p.score) for p in self.state.players]}")

        self.logger.log_game_event(
            "game_end",
            {
                "satisfied_clauses": satisfied,
                "total_clauses": len(self.state.formula.clauses),
                "final_assignment": self.state.assignment,
                "player_scores": {p.name: p.score for p in self.state.players},
            },
        )

        return self.state

    def _create_assignment_prompt(
        self, player: SATPlayer, unassigned: List[int]
    ) -> str:
        """Create prompt for player to assign a variable."""
        prompt = f"""You are {player.name} in a cooperative 3-SAT game.

Your variables: {sorted(player.variables)}
Unassigned variables: {sorted(unassigned)}
Current assignment: {self.state.assignment}

Formula:
{self.state.formula}

Choose ONE variable from your unassigned variables and set it to True or False.
Respond with just: "x<variable> = <True/False>"

Example: "x3 = True"
"""
        return prompt
