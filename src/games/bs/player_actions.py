"""Player action handlers for BS game using LLM backends."""

import re
import json
from typing import List, Optional, Dict, Any, Tuple
from src.player import GamePlayer
from .config import BSPlayerConfig
from .game_state import Card, RANKS


def get_play_decision(
    player: GamePlayer,
    config: BSPlayerConfig,
    hand: List[Card],
    current_rank: str,
    hand_sizes: List[int],
    player_idx: int,
    recent_plays: List[str],
    allow_passing: bool = True,
) -> Dict[str, Any]:
    """
    Ask player what cards to play.

    Args:
        player: GamePlayer instance
        config: Player configuration
        hand: Player's current hand
        current_rank: Required rank to play
        hand_sizes: Current hand sizes of all players
        player_idx: This player's index
        recent_plays: Recent play descriptions
        allow_passing: Whether passing is allowed

    Returns:
        Dict with:
        - action: "play" or "pass"
        - claimed_rank: Rank being claimed
        - claimed_count: Number of cards claimed
        - cards_to_play: List of Card objects to actually play
    """
    # Build hand representation
    hand_str = ", ".join([str(card) for card in sorted(hand, key=lambda c: RANKS.index(c.rank))])

    # Build game context
    other_hand_sizes = [f"Player {i}: {size} cards" for i, size in enumerate(hand_sizes) if i != player_idx]
    game_context = "\n".join([
        f"Your hand ({len(hand)} cards): {hand_str}",
        f"Other players: {', '.join(other_hand_sizes)}",
        f"Cards in discard pile: {sum(hand_sizes) - sum([len(hand)]) if len(hand_sizes) > 0 else 0}",
    ])

    # Build recent history
    history_str = "\n".join(recent_plays[-5:]) if recent_plays else "No plays yet."

    # Build prompt
    pass_option = "\n- PASS: Skip your turn" if allow_passing else ""

    prompt = f"""You are playing BS (Cheat/I Doubt It). It's your turn.

Game State:
{game_context}

Current Required Rank: {current_rank}

Recent Plays:
{history_str}

You must play cards of rank {current_rank} (or claim to). You can:
- PLAY TRUTHFULLY: Play actual {current_rank}s from your hand
- BLUFF: Play other cards but claim they are {current_rank}s{pass_option}

Choose your action. Respond in JSON format:
{{
  "action": "play" or "pass",
  "cards": ["card1", "card2", ...],
  "reasoning": "brief explanation"
}}

Examples:
{{"action": "play", "cards": ["2♠", "2♥"], "reasoning": "I have two 2s"}}
{{"action": "play", "cards": ["5♠", "3♥"], "reasoning": "Bluffing with off-rank cards"}}
{{"action": "pass", "cards": [], "reasoning": "Don't have the rank and don't want to bluff"}}

Your response:"""

    # Generate decision
    result = player.query(
        prompt=prompt,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
    )

    # Parse response
    text = result.text.strip()

    # Try to extract JSON
    json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
    if not json_match:
        # Fallback: pass if allowed, else random play
        if allow_passing:
            return {
                "action": "pass",
                "claimed_rank": current_rank,
                "claimed_count": 0,
                "cards_to_play": [],
                "error": "Could not parse response",
                "raw_response": text,
            }
        else:
            # Play first card as fallback
            card = hand[0] if hand else None
            return {
                "action": "play",
                "claimed_rank": current_rank,
                "claimed_count": 1,
                "cards_to_play": [card] if card else [],
                "error": "Could not parse response, playing first card",
                "raw_response": text,
            }

    try:
        decision = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return {
            "action": "pass" if allow_passing else "play",
            "claimed_rank": current_rank,
            "claimed_count": 0,
            "cards_to_play": [],
            "error": "Invalid JSON",
            "raw_response": text,
        }

    action = decision.get("action", "pass")

    if action == "pass":
        return {
            "action": "pass",
            "claimed_rank": current_rank,
            "claimed_count": 0,
            "cards_to_play": [],
            "reasoning": decision.get("reasoning", ""),
            "raw_response": text,
        }

    # Parse cards to play
    card_strs = decision.get("cards", [])
    cards_to_play = []

    for card_str in card_strs:
        # Try to match card from hand
        matched = False
        for card in hand:
            if str(card) == card_str or (card.rank in card_str and card.suit in card_str):
                cards_to_play.append(card)
                matched = True
                break

        if not matched:
            # Card not in hand - might be a bluff attempt with invalid card
            # Just skip it
            pass

    # Ensure we have at least one card if action is play
    if not cards_to_play and hand:
        cards_to_play = [hand[0]]

    return {
        "action": "play",
        "claimed_rank": current_rank,
        "claimed_count": len(cards_to_play),
        "cards_to_play": cards_to_play,
        "reasoning": decision.get("reasoning", ""),
        "raw_response": text,
    }


def get_bs_call_decision(
    player: GamePlayer,
    config: BSPlayerConfig,
    last_play_description: str,
    hand_sizes: List[int],
    player_idx: int,
    pile_size: int,
) -> Dict[str, Any]:
    """
    Ask player whether to call BS on the last play.

    Args:
        player: GamePlayer instance
        config: Player configuration
        last_play_description: Description of last play
        hand_sizes: Current hand sizes
        player_idx: This player's index
        pile_size: Size of discard pile

    Returns:
        Dict with:
        - call_bs: True/False
        - reasoning: Explanation
    """
    other_hand_sizes = [f"Player {i}: {size} cards" for i, size in enumerate(hand_sizes) if i != player_idx]

    prompt = f"""You are playing BS (Cheat/I Doubt It).

Last Play: {last_play_description}

Game State:
- Other players: {', '.join(other_hand_sizes)}
- Discard pile size: {pile_size} cards

Do you want to call BS (challenge this play)? If you're right, they pick up all {pile_size} cards. If you're wrong, YOU pick up all {pile_size} cards.

Respond in JSON format:
{{
  "call_bs": true or false,
  "reasoning": "brief explanation"
}}

Your response:"""

    result = player.query(
        prompt=prompt,
        max_tokens=min(config.max_tokens, 100),  # Short response
        temperature=config.temperature,
    )

    text = result.text.strip()

    # Try to extract JSON
    json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
    if not json_match:
        return {
            "call_bs": False,
            "reasoning": "Could not parse response",
            "raw_response": text,
        }

    try:
        decision = json.loads(json_match.group(0))
        return {
            "call_bs": decision.get("call_bs", False),
            "reasoning": decision.get("reasoning", ""),
            "raw_response": text,
        }
    except json.JSONDecodeError:
        return {
            "call_bs": False,
            "reasoning": "Invalid JSON",
            "raw_response": text,
        }
