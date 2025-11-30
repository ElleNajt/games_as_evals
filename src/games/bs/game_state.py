"""Game state management for BS card game."""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple
import random


# Rank values (2-10, J, Q, K, A)
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
SUITS = ['♠', '♥', '♦', '♣']


@dataclass
class Card:
    """Represents a playing card."""
    rank: str
    suit: str

    def __str__(self):
        return f"{self.rank}{self.suit}"

    def __repr__(self):
        return str(self)


@dataclass
class PlayAction:
    """Represents a play action in the game."""
    player_idx: int
    claimed_rank: str
    claimed_count: int
    actual_cards: List[Card]
    is_truthful: bool


@dataclass
class GameState:
    """
    Tracks the state of a BS game.

    Attributes:
        num_players: Number of players
        hands: List of card lists (one per player)
        discard_pile: Stack of all played cards
        play_history: History of all plays
        current_rank_idx: Index into RANKS for current required rank
        current_player: Index of current player
        round_num: Current round number
    """
    num_players: int
    hands: List[List[Card]] = field(default_factory=list)
    discard_pile: List[Card] = field(default_factory=list)
    play_history: List[PlayAction] = field(default_factory=list)
    current_rank_idx: int = 0  # Start with '2'
    current_player: int = 0
    round_num: int = 0

    def __post_init__(self):
        """Initialize the deck and deal cards."""
        if not self.hands:  # Only deal if hands not already set
            self._deal_cards()

    def _create_deck(self) -> List[Card]:
        """Create a standard deck (or 2 decks if 6+ players)."""
        num_decks = 2 if self.num_players >= 6 else 1
        deck = []
        for _ in range(num_decks):
            for rank in RANKS:
                for suit in SUITS:
                    deck.append(Card(rank, suit))
        return deck

    def _deal_cards(self):
        """Deal cards evenly to all players."""
        deck = self._create_deck()
        random.shuffle(deck)

        # Deal evenly
        cards_per_player = len(deck) // self.num_players
        self.hands = []

        for i in range(self.num_players):
            start_idx = i * cards_per_player
            end_idx = start_idx + cards_per_player
            self.hands.append(deck[start_idx:end_idx])

        # Distribute remaining cards
        remaining_start = self.num_players * cards_per_player
        for i, card in enumerate(deck[remaining_start:]):
            self.hands[i].append(card)

    def get_current_rank(self) -> str:
        """Get the current required rank."""
        return RANKS[self.current_rank_idx]

    def advance_rank(self):
        """Move to next rank in sequence."""
        self.current_rank_idx = (self.current_rank_idx + 1) % len(RANKS)

    def next_player(self):
        """Move to next player."""
        self.current_player = (self.current_player + 1) % self.num_players

    def play_cards(self, player_idx: int, claimed_rank: str, cards: List[Card]) -> PlayAction:
        """
        Play cards to the discard pile.

        Args:
            player_idx: Index of playing player
            claimed_rank: Rank being claimed
            cards: Actual cards being played

        Returns:
            PlayAction representing this play
        """
        # Check if claim is truthful
        is_truthful = all(card.rank == claimed_rank for card in cards)

        # Create action
        action = PlayAction(
            player_idx=player_idx,
            claimed_rank=claimed_rank,
            claimed_count=len(cards),
            actual_cards=cards,
            is_truthful=is_truthful
        )

        # Update state
        self.discard_pile.extend(cards)
        self.play_history.append(action)

        # Remove cards from player's hand
        for card in cards:
            self.hands[player_idx].remove(card)

        return action

    def resolve_bs_call(self, caller_idx: int) -> Tuple[bool, int]:
        """
        Resolve a BS call.

        Args:
            caller_idx: Index of player calling BS

        Returns:
            (caller_was_correct, loser_idx)
            - If caller correct: last player was lying, they pick up pile
            - If caller wrong: caller picks up pile
        """
        if not self.play_history:
            # No play to challenge
            return False, caller_idx

        last_play = self.play_history[-1]

        if last_play.is_truthful:
            # Player was telling truth, caller loses
            self.hands[caller_idx].extend(self.discard_pile)
            loser_idx = caller_idx
            caller_was_correct = False
        else:
            # Player was lying, they lose
            self.hands[last_play.player_idx].extend(self.discard_pile)
            loser_idx = last_play.player_idx
            caller_was_correct = True

        # Clear discard pile
        self.discard_pile = []

        return caller_was_correct, loser_idx

    def is_game_over(self) -> Tuple[bool, int]:
        """
        Check if game is over.

        Returns:
            (is_over, winner_idx)
            - winner_idx is -1 if no winner yet
        """
        for i, hand in enumerate(self.hands):
            if len(hand) == 0:
                return True, i

        return False, -1

    def get_hand_sizes(self) -> List[int]:
        """Get current hand sizes for all players."""
        return [len(hand) for hand in self.hands]

    def to_dict(self) -> Dict:
        """Serialize game state to dict."""
        return {
            "num_players": self.num_players,
            "hands": [[str(card) for card in hand] for hand in self.hands],
            "discard_pile": [str(card) for card in self.discard_pile],
            "hand_sizes": self.get_hand_sizes(),
            "current_rank": self.get_current_rank(),
            "current_player": self.current_player,
            "round_num": self.round_num,
            "pile_size": len(self.discard_pile),
        }
