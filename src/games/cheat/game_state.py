"""
Game state management for Cheat/Bullshit.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import random


class Rank(Enum):
    """Card ranks in play order."""
    ACE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    
    def __str__(self):
        names = {
            1: "Ace", 2: "Two", 3: "Three", 4: "Four", 5: "Five",
            6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten",
            11: "Jack", 12: "Queen", 13: "King"
        }
        return names[self.value]
    
    @classmethod
    def from_value(cls, value: int) -> 'Rank':
        """Get rank from 1-13."""
        return cls(((value - 1) % 13) + 1)
    
    def next(self) -> 'Rank':
        """Get next rank in cycle (King -> Ace)."""
        return Rank.from_value(self.value + 1)


@dataclass
class Card:
    """A playing card."""
    rank: Rank
    suit: str  # Not used for gameplay, just for tracking
    
    def __str__(self):
        return f"{self.rank}{self.suit}"
    
    def __repr__(self):
        return str(self)


@dataclass
class PlayerState:
    """State for a single player."""
    name: str
    hand: List[Card] = field(default_factory=list)
    is_eliminated: bool = False
    
    def num_cards(self) -> int:
        """Number of cards in hand."""
        return len(self.hand)
    
    def has_rank(self, rank: Rank) -> bool:
        """Check if player has any cards of this rank."""
        return any(card.rank == rank for card in self.hand)
    
    def count_rank(self, rank: Rank) -> int:
        """Count how many cards of this rank player has."""
        return sum(1 for card in self.hand if card.rank == rank)
    
    def remove_cards(self, cards: List[Card]):
        """Remove specific cards from hand."""
        for card in cards:
            self.hand.remove(card)
    
    def add_cards(self, cards: List[Card]):
        """Add cards to hand."""
        self.hand.extend(cards)


@dataclass
class CheatGameState:
    """Game state for Cheat/Bullshit."""
    players: List[PlayerState]
    pile: List[Card] = field(default_factory=list)
    current_player_idx: int = 0
    current_rank: Rank = Rank.ACE
    turn_number: int = 0
    last_play: Optional[Dict] = None  # {player_idx, claimed_rank, claimed_count, actual_cards}
    game_over: bool = False
    winner: Optional[str] = None
    
    def current_player(self) -> PlayerState:
        """Get current player."""
        return self.players[self.current_player_idx]
    
    def next_turn(self):
        """Advance to next player and rank."""
        self.current_player_idx = (self.current_player_idx + 1) % len(self.players)
        self.current_rank = self.current_rank.next()
        self.turn_number += 1
        
        # Skip eliminated players
        start_idx = self.current_player_idx
        while self.players[self.current_player_idx].is_eliminated:
            self.current_player_idx = (self.current_player_idx + 1) % len(self.players)
            if self.current_player_idx == start_idx:
                # All players eliminated somehow (shouldn't happen)
                self.game_over = True
                return
    
    def play_cards(self, player_idx: int, cards: List[Card], claimed_rank: Rank, claimed_count: int):
        """Player plays cards to the pile."""
        player = self.players[player_idx]
        player.remove_cards(cards)
        self.pile.extend(cards)
        
        self.last_play = {
            'player_idx': player_idx,
            'player_name': player.name,
            'claimed_rank': claimed_rank,
            'claimed_count': claimed_count,
            'actual_cards': cards
        }
    
    def resolve_challenge(self, challenger_idx: int) -> Dict:
        """Resolve a challenge.
        
        Returns:
            Dict with keys: was_lying, loser_idx, loser_name, cards_picked_up
        """
        if self.last_play is None:
            raise ValueError("No play to challenge")
        
        played_cards = self.last_play['actual_cards']
        claimed_rank = self.last_play['claimed_rank']
        claimed_count = self.last_play['claimed_count']
        player_idx = self.last_play['player_idx']
        
        # Check if the play was honest
        all_correct_rank = all(card.rank == claimed_rank for card in played_cards)
        correct_count = len(played_cards) == claimed_count
        was_honest = all_correct_rank and correct_count
        
        # Determine loser
        if was_honest:
            # Challenger was wrong, they pick up the pile
            loser_idx = challenger_idx
        else:
            # Player was lying, they pick up the pile
            loser_idx = player_idx
        
        loser = self.players[loser_idx]
        cards_picked_up = len(self.pile)
        loser.add_cards(self.pile)
        self.pile = []
        
        return {
            'was_lying': not was_honest,
            'loser_idx': loser_idx,
            'loser_name': loser.name,
            'cards_picked_up': cards_picked_up,
            'challenged_player': self.last_play['player_name'],
            'challenger': self.players[challenger_idx].name
        }
    
    def check_winner(self) -> Optional[str]:
        """Check if anyone has won (0 cards)."""
        for player in self.players:
            if not player.is_eliminated and player.num_cards() == 0:
                self.game_over = True
                self.winner = player.name
                return player.name
        return None
    
    def get_player_by_name(self, name: str) -> Optional[PlayerState]:
        """Get player state by name."""
        for player in self.players:
            if player.name == name:
                return player
        return None
    
    def get_game_state_summary(self) -> str:
        """Get a text summary of the current game state."""
        lines = [
            f"Turn {self.turn_number}",
            f"Current rank to play: {self.current_rank}",
            f"Pile size: {len(self.pile)} cards",
            "",
            "Players:"
        ]
        
        for i, player in enumerate(self.players):
            marker = "→ " if i == self.current_player_idx else "  "
            status = " (ELIMINATED)" if player.is_eliminated else ""
            lines.append(f"{marker}{player.name}: {player.num_cards()} cards{status}")
        
        return "\n".join(lines)


def create_deck(num_decks: int = 1) -> List[Card]:
    """Create a shuffled deck of cards."""
    suits = ['♠', '♥', '♦', '♣']
    deck = []
    
    for _ in range(num_decks):
        for rank in Rank:
            for suit in suits:
                deck.append(Card(rank, suit))
    
    random.shuffle(deck)
    return deck


def deal_cards(num_players: int, num_decks: int = 1) -> List[List[Card]]:
    """Deal cards to players as evenly as possible."""
    deck = create_deck(num_decks)
    hands = [[] for _ in range(num_players)]
    
    for i, card in enumerate(deck):
        hands[i % num_players].append(card)
    
    return hands
