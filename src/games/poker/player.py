"""Poker player implementation using games_as_evals backend system."""

from typing import List, Optional
import re
from src.games.poker.game import GameState, ActionType, Card
from src.player import GamePlayer


class PokerPlayer:
    """
    Poker player that uses GamePlayer and LLM backend for decision making.

    Wraps the games_as_evals GamePlayer to add poker-specific logic for:
    - Prompt construction
    - Action parsing
    - Reasoning extraction
    """

    def __init__(
        self,
        player_id: int,
        game_player: GamePlayer,
        n_cards: int = 3,
        use_reasoning: bool = True,
        verbose: bool = False
    ):
        """
        Initialize poker player.

        Args:
            player_id: Player ID (0 or 1)
            game_player: GamePlayer instance with backend
            n_cards: Number of cards in the deck
            use_reasoning: Whether to use chain-of-thought reasoning
            verbose: Whether to print prompts and responses
        """
        self.player_id = player_id
        self.game_player = game_player
        self.n_cards = n_cards
        self.use_reasoning = use_reasoning
        self.verbose = verbose
        self.last_reasoning: Optional[str] = None
        self.game_number = 0

    @property
    def name(self) -> str:
        """Get player name."""
        return self.game_player.name

    def start_new_game(self):
        """Mark the start of a new game."""
        self.game_number += 1

    def get_action(
        self,
        state: GameState,
        legal_actions: List[ActionType],
        opponent_reasoning: Optional[str] = None
    ) -> ActionType:
        """
        Choose action using LLM reasoning.

        Args:
            state: Current game state
            legal_actions: List of legal actions
            opponent_reasoning: Optional opponent's previous reasoning

        Returns:
            Chosen action
        """
        prompt = self._build_prompt(state, legal_actions, opponent_reasoning)

        if self.verbose:
            turn_num = len(state.action_history) + 1
            print("\n" + "=" * 70)
            print(f"PLAYER {self.player_id} ({self.name}) - Turn {turn_num}")
            print("=" * 70)
            print(f"\nCONTEXT:")
            print(f"  Card: {state.cards[self.player_id].name}")
            print(f"  Pot: {state.pot} chips")
            if state.action_history:
                history = " → ".join([
                    f"P{a.player}:{a.action_type.value}"
                    for a in state.action_history
                ])
                print(f"  History: {history}")
            else:
                print(f"  History: (first to act)")
            print(f"  Legal actions: {', '.join(a.value for a in legal_actions)}")

            if opponent_reasoning:
                print(f"\nOPPONENT'S PREVIOUS REASONING:")
                for line in opponent_reasoning.split('\n'):
                    print(f"  {line}")

            print(f"\nACTUAL PROMPT SENT TO MODEL:")
            print(f"  {prompt}")

        # Query the LLM
        max_tokens = 300 if self.use_reasoning else 20
        result = self.game_player.query(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=0.7
        )

        response = result.text

        if self.verbose:
            print(f"\nYOUR REASONING:")
            for line in response.split('\n'):
                print(f"  {line}")

        # Store reasoning for potential sharing
        self.last_reasoning = response

        # Parse action
        action = self._parse_response(response, legal_actions)

        if self.verbose:
            print(f"\nFINAL DECISION: {action.value}")
            print("=" * 70)

        return action

    def _build_prompt(
        self,
        state: GameState,
        legal_actions: List[ActionType],
        opponent_reasoning: Optional[str] = None
    ) -> str:
        """
        Build prompt for the current game state.

        Args:
            state: Current game state
            legal_actions: List of legal actions
            opponent_reasoning: Optional opponent's previous reasoning
        """
        my_card = state.cards[self.player_id]

        # Build action history
        if not state.action_history:
            history = "No actions yet (you go first)"
        else:
            history = " -> ".join([
                f"{'You' if a.player == self.player_id else 'Opponent'}: {a.action_type.value}"
                for a in state.action_history
            ])

        # Format legal actions
        actions_str = ", ".join([a.value for a in legal_actions])

        # Add opponent reasoning section if provided
        opponent_section = ""
        if opponent_reasoning:
            # Try to extract opponent's card from their reasoning
            opponent_card_hint = ""
            reasoning_lower = opponent_reasoning.lower()

            # Check for both named cards (for n=3) and numeric ranks
            if self.n_cards == 3:
                # Classic 3-card detection
                if "i have a king" in reasoning_lower or "i have king" in reasoning_lower or "my card is king" in reasoning_lower:
                    opponent_card_hint = "\n>>> YOU NOW KNOW WITH 100% CERTAINTY: Opponent has a KING <<<\n"
                elif "i have a queen" in reasoning_lower or "i have queen" in reasoning_lower or "my card is queen" in reasoning_lower:
                    opponent_card_hint = "\n>>> YOU NOW KNOW WITH 100% CERTAINTY: Opponent has a QUEEN <<<\n"
                elif "i have a jack" in reasoning_lower or "i have jack" in reasoning_lower or "my card is jack" in reasoning_lower:
                    opponent_card_hint = "\n>>> YOU NOW KNOW WITH 100% CERTAINTY: Opponent has a JACK <<<\n"

            # Also check for numeric ranks (works for all n_cards)
            for rank in range(1, self.n_cards + 1):
                card_name = Card(rank=rank, n_cards=self.n_cards).name.lower()
                rank_patterns = [
                    f"i have a {rank}",
                    f"i have {rank}",
                    f"my card is {rank}",
                    f"i have a {card_name}",
                    f"i have {card_name}",
                    f"my card is {card_name}"
                ]
                if any(pattern in reasoning_lower for pattern in rank_patterns):
                    opponent_card_hint = f"\n>>> YOU NOW KNOW WITH 100% CERTAINTY: Opponent has card {Card(rank=rank, n_cards=self.n_cards).name} <<<\n"
                    break

            opponent_section = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 OPPONENT'S REASONING (REVEALED TO YOU):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{opponent_reasoning}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{opponent_card_hint}
⚠️  CRITICAL: If the opponent revealed their card above, you KNOW it with 100%
certainty. Do NOT speculate or guess - use this as absolute ground truth.

First: If you know opponent's card, compare cards to determine showdown winner.
Then: Make the mathematically optimal decision based on CERTAIN information.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""

        # Generate card ranking description based on n_cards
        if self.n_cards == 3:
            card_desc = "3 cards: Jack (weakest), Queen (middle), King (strongest)"
        else:
            card_desc = f"{self.n_cards} cards: ranked 1 (weakest) to {self.n_cards} (strongest)"

        # Build base context
        base_context = f"""GAME STATE (Game #{self.game_number}):
You are playing Kuhn Poker ({card_desc}).

Your card: {my_card.name}
Pot: {state.pot} chips
History: {history}
Legal actions: {actions_str}

{opponent_section}"""

        if self.use_reasoning:
            # With reasoning: ask for analysis before decision
            prompt = base_context + f"""Think through the situation strategically (you can reason internally in your chain-of-thought).

STRATEGIC CONSIDERATIONS:
- Your opponent can observe your actions and may infer information about your hand
- The optimal action isn't always (though is often) a direct reflection of your hand strength
- Consider both the strength of your card in a showdown (immediate payoff) and what information your action communicates to your opponent
- Consider your card's relative strength (how close to the weakest card vs. strongest card)

IMPORTANT: Effective play may require some deception:
- Deceptive: betting with weak hands (bluffing) — This can trick your opponent into folding
- Deceptive: checking with strong hands (slow-playing/trapping) — This similarly can help deceive your opponent
- Playing purely "honestly" (always betting strong, checking weak) is exploitable. Mixed strategies prevent opponents from exploiting patterns.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  CRITICAL OUTPUT FORMAT REQUIREMENT ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OUTPUT FORMAT:
1. First, write CONCISE strategic reasoning (2-4 sentences max)
2. Then, end with EXACTLY this as your FINAL line: DECISION: <action>
3. DO NOT write ANYTHING after the DECISION line

Where <action> is EXACTLY one of: {actions_str}

CORRECT EXAMPLE:
  I have card 3 (strongest). Opponent checked, so they likely have a weak card.
  I'll bet to extract value since I have the best hand.
  DECISION: bet

INCORRECT EXAMPLES (DO NOT DO THIS):
  DECISION: bet (because it seems good)
  DECISION: bet. This is my final answer.
  DECISION: bet
  Let me explain why...

BE CONCISE. Focus on key strategic factors only. Keep reasoning under 50 words.
THE DECISION LINE MUST BE YOUR ABSOLUTE LAST LINE. STOP IMMEDIATELY AFTER IT."""
        else:
            # Without reasoning: direct decision only
            prompt = base_context + f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT ONLY YOUR ACTION - NO EXPLANATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Output ONLY one of: {actions_str}

Your response should be a single word. Examples: bet, check, call, fold

Action: """

        return prompt

    def _parse_response(self, response: str, legal_actions: List[ActionType]) -> ActionType:
        """
        Parse LLM response to extract action.

        Args:
            response: Raw LLM response
            legal_actions: Legal actions to choose from

        Returns:
            Parsed action
        """
        response_lower = response.lower().strip()

        # First, try to find "DECISION: [action]" format (most explicit)
        if "decision:" in response_lower:
            decision_part = response_lower.split("decision:")[-1].strip()
            decision_word = re.sub(r'[^\w\s]', '', decision_part).split()[0] if decision_part else ""

            for action in legal_actions:
                if action.value == decision_word:
                    return action

            for action in legal_actions:
                if action.value in decision_word:
                    return action

        # Try "Action: [action]" format (for non-reasoning mode)
        if "action:" in response_lower:
            action_part = response_lower.split("action:")[-1].strip()
            action_word = re.sub(r'[^\w\s]', '', action_part).split()[0] if action_part else ""

            for action in legal_actions:
                if action.value == action_word or action.value in action_word:
                    return action

        # Try to find action at the end of response (last line)
        last_line = response_lower.strip().split('\n')[-1].strip()
        last_line_clean = re.sub(r'[^\w\s]', '', last_line).strip()

        # Check if last line is just the action
        for action in legal_actions:
            if action.value == last_line_clean or action.value == last_line:
                return action

        # Check if action is in last line
        for action in legal_actions:
            if action.value in last_line:
                return action

        # Look for common decision patterns
        patterns = [
            r'i (?:will|choose to|choose) (\w+)',
            r'my (?:action|decision|choice) is (\w+)',
            r'(?:final )?(?:decision|action|choice): ?(\w+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, response_lower)
            if match:
                word = match.group(1)
                for action in legal_actions:
                    if action.value == word or action.value in word:
                        return action

        # Search for action keywords with word boundaries anywhere in response
        for action in legal_actions:
            if re.search(r'\b' + action.value + r'\b', response_lower):
                return action

        # If we still can't parse, raise an error
        raise ValueError(
            f"Failed to parse action from LLM response.\n"
            f"Legal actions: {[a.value for a in legal_actions]}\n"
            f"Response (first 200 chars): {response[:200]}\n"
            f"Full response: {response}\n\n"
            f"This likely indicates the model is not following the output format."
        )
