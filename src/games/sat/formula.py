"""3-SAT formula generation and evaluation."""

import random
from dataclasses import dataclass
from typing import List, Set, Tuple


@dataclass
class Literal:
    """A literal in a clause (variable with optional negation)."""
    variable: int
    negated: bool
    
    def evaluate(self, assignment: dict[int, bool]) -> bool | None:
        """Evaluate this literal given variable assignments."""
        if self.variable not in assignment:
            return None
        value = assignment[self.variable]
        return not value if self.negated else value
    
    def __str__(self) -> str:
        return f"{'¬' if self.negated else ''}x{self.variable}"


@dataclass
class Clause:
    """A clause in the formula (disjunction of k literals)."""
    literals: List[Literal]
    owner: int  # Player ID who owns this clause
    
    def evaluate(self, assignment: dict[int, bool]) -> bool | None:
        """
        Evaluate this clause given variable assignments.
        Returns True if satisfied, False if unsatisfied, None if undetermined.
        """
        has_unknown = False
        for lit in self.literals:
            val = lit.evaluate(assignment)
            if val is True:
                return True
            if val is None:
                has_unknown = True
        return None if has_unknown else False
    
    def __str__(self) -> str:
        return f"({' ∨ '.join(str(lit) for lit in self.literals)})"


class Formula:
    """A k-SAT formula."""
    
    def __init__(self, num_variables: int, num_clauses: int, literals_per_clause: int = 3):
        self.num_variables = num_variables
        self.num_clauses = num_clauses
        self.literals_per_clause = literals_per_clause
        self.clauses: List[Clause] = []
    
    def generate_random(self, num_players: int):
        """Generate a random k-SAT formula with clauses assigned to players."""
        for i in range(self.num_clauses):
            # Pick k distinct variables
            k = min(self.literals_per_clause, self.num_variables)
            variables = random.sample(range(self.num_variables), k)
            # Randomly negate each
            literals = [
                Literal(var, random.choice([True, False]))
                for var in variables
            ]
            # Assign to player in round-robin fashion
            owner = i % num_players
            self.clauses.append(Clause(literals, owner))
    
    def generate_symmetric(self, num_players: int):
        """
        Generate a perfectly symmetric 3-SAT formula using rotated copies approach.
        
        Creates m copies of a base formula (one per player), rotates them around players,
        ensuring each player faces an isomorphic strategic situation.
        
        For n base variables and m players:
        - Variables: x_i^k where i ∈ {1,...,n}, k ∈ {0,...,m-1}
        - Player k controls all variables x_i^j where i mod n = k (independent of j)
        - Each player receives clauses C_{(i-k) mod |C|}^k from copy k
        """
        if self.num_clauses % num_players != 0:
            raise ValueError(f"num_clauses ({self.num_clauses}) must be divisible by num_players ({num_players})")
        if self.num_variables % num_players != 0:
            raise ValueError(f"num_variables ({self.num_variables}) must be divisible by num_players ({num_players})")
        
        num_base_vars = self.num_variables // num_players
        num_base_clauses = self.num_clauses // num_players
        
        # Generate base formula
        base_formula = self._generate_base_formula(num_base_vars, num_base_clauses)
        
        # Create m copies of the formula, one per player/superscript
        for copy_k in range(num_players):
            # For each clause in the base formula
            for clause_idx, base_clause in enumerate(base_formula):
                # Create concrete clause with superscript k
                literals = []
                for base_var, negated in base_clause:
                    # Map base variable i, copy k → actual variable ID
                    actual_var_id = self._compute_var_id(base_var, copy_k, num_base_vars, num_players)
                    literals.append(Literal(actual_var_id, negated))
                
                # Determine which player owns this clause
                # Player i gets clauses C_{(i-k) mod num_base_clauses}^k
                # Inverse: clause C_j^k belongs to player (j+k) mod num_players
                player_id = (clause_idx + copy_k) % num_players
                
                self.clauses.append(Clause(literals, player_id))
    
    def _compute_var_id(self, base_var_subscript: int, copy_superscript: int, num_base_vars: int, num_players: int) -> int:
        """
        Map (base_var_subscript, copy_superscript) to actual variable ID.
        
        Args:
            base_var_subscript: 1-indexed (1, 2, ..., num_base_vars)
            copy_superscript: 0-indexed (0, 1, ..., num_players-1)
            num_base_vars: number of base variables
            num_players: number of players
        
        Returns:
            Actual variable ID ensuring var_id mod num_players = base_var_subscript mod num_players
        """
        # Which player should control this variable?
        owner_player = (base_var_subscript - 1) % num_players
        
        # Which "slot" within that player's variables?
        # Group by base_var, then by copy
        slot = ((base_var_subscript - 1) // num_players) * num_players + copy_superscript
        
        # Actual variable ID
        var_id = owner_player + slot * num_players
        
        return var_id
    
    def _generate_base_formula(self, num_base_vars: int, num_base_clauses: int) -> List[List[Tuple[int, bool]]]:
        """
        Generate a random base k-SAT formula.
        
        Args:
            num_base_vars: number of base variables
            num_base_clauses: number of base clauses
        
        Returns:
            List of clauses, where each clause is a list of (base_var, negated) tuples.
            base_var is 1-indexed (1, 2, ..., num_base_vars)
        """
        base_formula = []
        for _ in range(num_base_clauses):
            # Pick k distinct base variables
            k = min(self.literals_per_clause, num_base_vars)
            vars_in_clause = random.sample(range(1, num_base_vars + 1), k)
            
            # Randomly negate
            clause = [(var, random.choice([True, False])) for var in vars_in_clause]
            base_formula.append(clause)
        
        return base_formula
    
    def _create_clause_template(self, clauses_per_player: int, vars_per_player: int, num_players: int):
        """
        Create an abstract template of clauses.
        
        Returns a list of clause templates, where each template is a list of 
        (player_offset, var_index, negated) tuples.
        
        player_offset: 0 = my variables, 1 = next player's variables, etc.
        var_index: which variable within that player's space (0, 1, 2, ...)
        negated: whether the literal is negated
        
        IMPORTANT: This creates a TRULY SYMMETRIC template. All players get
        structurally identical clauses with identical negation patterns.
        The only difference is the actual variable IDs used.
        """
        template = []
        
        # Use deterministic negation patterns that guarantee symmetry
        # Pattern cycles through different negation combinations
        negation_patterns = [
            [False, False, False],  # All positive
            [True, False, False],   # First negated
            [False, True, False],   # Second negated
            [False, False, True],   # Third negated
            [True, True, False],    # First two negated
            [True, False, True],    # First and third negated
            [False, True, True],    # Last two negated
            [True, True, True],     # All negated
        ]
        
        for i in range(clauses_per_player):
            # Pick 3 distinct variable sources
            # Use a deterministic pattern that ensures symmetry
            var_idx_0 = i % vars_per_player
            var_idx_1 = (i + 1) % vars_per_player
            var_idx_2 = (i + 2) % vars_per_player
            
            # Cycle through clause types: own vars, opponent vars, mixed
            clause_type = i % 3
            
            if clause_type == 0:
                # 2 own vars + 1 opponent var
                var_sources = [
                    (0, var_idx_0),
                    (0, var_idx_1),
                    (1, var_idx_2),
                ]
            elif clause_type == 1:
                # 1 own var + 2 opponent vars
                var_sources = [
                    (0, var_idx_0),
                    (1, var_idx_1),
                    (1, var_idx_2),
                ]
            else:
                # Mix: one from each player type (for 2-player: 2 own, 1 opponent)
                var_sources = [
                    (0, var_idx_0),
                    (0, var_idx_1),
                    (1, var_idx_2),
                ]
            
            # Ensure all 3 variable sources are distinct
            seen = set()
            final_sources = []
            for player_offset, var_idx in var_sources:
                key = (player_offset, var_idx)
                if key in seen:
                    # Find a different var_idx
                    for alt_idx in range(vars_per_player):
                        alt_key = (player_offset, alt_idx)
                        if alt_key not in seen:
                            key = alt_key
                            var_idx = alt_idx
                            break
                seen.add(key)
                final_sources.append((player_offset, var_idx))
            
            # Use deterministic negation pattern
            negation_pattern = negation_patterns[i % len(negation_patterns)]
            
            clause_literals = [
                (player_offset, var_idx, negated)
                for (player_offset, var_idx), negated in zip(final_sources, negation_pattern)
            ]
            
            template.append(clause_literals)
        
        return template
    
    def get_all_variables(self) -> Set[int]:
        """Get all variables in the formula."""
        variables = set()
        for clause in self.clauses:
            for lit in clause.literals:
                variables.add(lit.variable)
        return variables
    
    def evaluate(self, assignment: dict[int, bool]) -> Tuple[int, int]:
        """
        Evaluate the formula.
        Returns (satisfied_clauses, total_clauses).
        """
        satisfied = sum(1 for clause in self.clauses if clause.evaluate(assignment) is True)
        return satisfied, len(self.clauses)
    
    def __str__(self) -> str:
        return ' ∧ '.join(str(clause) for clause in self.clauses)
