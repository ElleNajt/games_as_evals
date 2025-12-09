"""
Comprehensive unit tests for basic game play mechanics.

Tests core game functionality without requiring LLM backends:
- Card game mechanics (BS/Cheat)
- Game state management
- Win conditions
- Turn management
- Rule enforcement
"""

import pytest
from src.games.bs.game_state import (
    GameState, Card, PlayAction, RANKS, SUITS
)


class TestBSGameMechanics:
    """Test BS (Bullshit) card game core mechanics."""

    def test_deck_creation_single(self):
        """Test creating a standard 52-card deck."""
        state = GameState(num_players=4)

        # Should have dealt all 52 cards
        total_cards = sum(len(hand) for hand in state.hands)
        assert total_cards == 52

        # Each player should have 13 cards (52/4)
        for hand in state.hands:
            assert len(hand) == 13

    def test_deck_creation_two_decks(self):
        """Test creating two decks for 6+ players."""
        state = GameState(num_players=6)

        # Should have dealt all 104 cards (2 decks)
        total_cards = sum(len(hand) for hand in state.hands)
        assert total_cards == 104

    def test_card_distribution_uneven(self):
        """Test card distribution when players don't divide evenly."""
        state = GameState(num_players=3)

        # 52 cards / 3 players = 17.33 per player
        # Some get 17, some get 18
        hand_sizes = [len(hand) for hand in state.hands]
        assert min(hand_sizes) == 17
        assert max(hand_sizes) == 18
        assert sum(hand_sizes) == 52

    def test_rank_advancement(self):
        """Test rank cycling through sequence."""
        state = GameState(num_players=2)

        # Start at '2'
        assert state.get_current_rank() == '2'
        assert state.current_rank_idx == 0

        # Advance through sequence
        state.advance_rank()
        assert state.get_current_rank() == '3'

        # Cycle back to beginning after 'A'
        state.current_rank_idx = 12  # 'A'
        assert state.get_current_rank() == 'A'
        state.advance_rank()
        assert state.get_current_rank() == '2'
        assert state.current_rank_idx == 0

    def test_player_rotation(self):
        """Test player turn rotation."""
        state = GameState(num_players=4)

        assert state.current_player == 0

        state.next_player()
        assert state.current_player == 1

        state.next_player()
        state.next_player()
        assert state.current_player == 3

        # Cycle back to player 0
        state.next_player()
        assert state.current_player == 0

    def test_truthful_play(self):
        """Test playing cards truthfully."""
        state = GameState(num_players=2)

        # Create cards and add to player's hand
        cards = [Card('5', '♠'), Card('5', '♥')]
        state.hands[0] = cards.copy()

        initial_hand_size = len(state.hands[0])

        # Play cards truthfully
        action = state.play_cards(
            player_idx=0,
            claimed_rank='5',
            cards=cards
        )

        # Verify action
        assert action.is_truthful
        assert action.claimed_rank == '5'
        assert action.claimed_count == 2
        assert len(action.actual_cards) == 2

        # Verify state changes
        assert len(state.hands[0]) == initial_hand_size - 2
        assert len(state.discard_pile) == 2
        assert len(state.play_history) == 1

    def test_deceptive_play(self):
        """Test playing cards deceptively."""
        state = GameState(num_players=2)

        # Create mismatched cards
        cards = [Card('7', '♠'), Card('8', '♥')]
        state.hands[0] = cards.copy()

        # Claim they're all 7s (lie)
        action = state.play_cards(
            player_idx=0,
            claimed_rank='7',
            cards=cards
        )

        # Should be marked as untruthful
        assert not action.is_truthful
        assert action.claimed_rank == '7'
        assert action.claimed_count == 2

    def test_bs_call_on_liar(self):
        """Test calling BS on a lying player."""
        state = GameState(num_players=2)

        # Player 0 lies
        cards = [Card('K', '♠'), Card('Q', '♥')]
        state.hands[0] = []
        state.hands[1] = []
        state.play_cards(0, '7', cards)

        # Player 1 calls BS
        caller_was_correct, loser_idx = state.resolve_bs_call(1)

        # Caller should be correct
        assert caller_was_correct
        assert loser_idx == 0  # Liar loses

        # Liar picks up pile
        assert len(state.hands[0]) == 2
        assert len(state.discard_pile) == 0

    def test_bs_call_on_truth_teller(self):
        """Test calling BS on an honest player."""
        state = GameState(num_players=2)

        # Player 0 tells truth
        cards = [Card('7', '♠'), Card('7', '♥')]
        state.hands[0] = []
        state.hands[1] = []
        state.play_cards(0, '7', cards)

        # Player 1 wrongly calls BS
        caller_was_correct, loser_idx = state.resolve_bs_call(1)

        # Caller should be wrong
        assert not caller_was_correct
        assert loser_idx == 1  # Caller loses

        # Caller picks up pile
        assert len(state.hands[1]) == 2
        assert len(state.discard_pile) == 0

    def test_game_over_detection(self):
        """Test game over when player has no cards."""
        state = GameState(num_players=3)

        # Give player 0 no cards (winner)
        state.hands[0] = []
        state.hands[1] = [Card('K', '♠')]
        state.hands[2] = [Card('Q', '♥')]

        is_over, winner_idx = state.is_game_over()

        assert is_over
        assert winner_idx == 0

    def test_game_not_over(self):
        """Test game continues when all players have cards."""
        state = GameState(num_players=3)

        # All players have cards
        for i in range(3):
            state.hands[i] = [Card('K', '♠'), Card('Q', '♥')]

        is_over, winner_idx = state.is_game_over()

        assert not is_over
        assert winner_idx == -1

    def test_hand_sizes(self):
        """Test getting hand sizes for all players."""
        state = GameState(num_players=4)

        # Manually set hand sizes
        state.hands[0] = [Card('2', '♠')] * 10
        state.hands[1] = [Card('3', '♥')] * 5
        state.hands[2] = [Card('4', '♦')] * 15
        state.hands[3] = [Card('5', '♣')] * 3

        sizes = state.get_hand_sizes()

        assert sizes == [10, 5, 15, 3]

    def test_play_history_tracking(self):
        """Test that play history is maintained."""
        state = GameState(num_players=2)

        # Make several plays
        cards1 = [Card('2', '♠')]
        cards2 = [Card('3', '♥'), Card('3', '♦')]
        cards3 = [Card('4', '♣')]

        state.hands[0] = cards1 + cards2 + cards3
        state.hands[1] = []

        state.play_cards(0, '2', [cards1[0]])
        state.play_cards(0, '3', cards2)
        state.play_cards(0, '4', [cards3[0]])

        # Verify history
        assert len(state.play_history) == 3
        assert state.play_history[0].claimed_rank == '2'
        assert state.play_history[1].claimed_rank == '3'
        assert state.play_history[2].claimed_rank == '4'

    def test_pile_accumulation(self):
        """Test discard pile grows with plays."""
        state = GameState(num_players=2)

        # Make multiple plays without BS calls
        cards1 = [Card('2', '♠'), Card('2', '♥')]
        cards2 = [Card('3', '♦'), Card('3', '♣')]

        state.hands[0] = cards1 + cards2
        state.hands[1] = []

        state.play_cards(0, '2', cards1)
        assert len(state.discard_pile) == 2

        state.play_cards(0, '3', cards2)
        assert len(state.discard_pile) == 4

    def test_pile_clears_after_bs_call(self):
        """Test discard pile clears after BS resolution."""
        state = GameState(num_players=2)

        # Build up pile
        cards = [Card('K', '♠'), Card('Q', '♥'), Card('J', '♦')]
        state.hands[0] = []
        state.hands[1] = []
        state.play_cards(0, 'K', cards)

        assert len(state.discard_pile) == 3

        # Call BS
        state.resolve_bs_call(1)

        # Pile should be cleared
        assert len(state.discard_pile) == 0

    def test_state_serialization(self):
        """Test game state can be serialized to dict."""
        state = GameState(num_players=2)
        state.hands[0] = [Card('K', '♠'), Card('Q', '♥')]
        state.hands[1] = [Card('J', '♦')]
        state.discard_pile = [Card('10', '♣')]
        state.current_rank_idx = 5
        state.current_player = 1
        state.round_num = 3

        state_dict = state.to_dict()

        # Verify structure
        assert state_dict['num_players'] == 2
        assert state_dict['hand_sizes'] == [2, 1]
        assert state_dict['pile_size'] == 1
        assert state_dict['current_rank'] == '7'  # Index 5
        assert state_dict['current_player'] == 1
        assert state_dict['round_num'] == 3

        # Verify cards serialized
        assert len(state_dict['hands']) == 2
        assert len(state_dict['hands'][0]) == 2
        assert state_dict['hands'][0][0] == 'K♠'


class TestCardOperations:
    """Test Card class and operations."""

    def test_card_creation(self):
        """Test creating cards."""
        card = Card('A', '♠')
        assert card.rank == 'A'
        assert card.suit == '♠'

    def test_card_string_representation(self):
        """Test card string formatting."""
        card = Card('K', '♥')
        assert str(card) == 'K♥'
        assert repr(card) == 'K♥'

    def test_card_equality(self):
        """Test card equality comparison."""
        card1 = Card('Q', '♦')
        card2 = Card('Q', '♦')
        card3 = Card('Q', '♣')

        assert card1.rank == card2.rank
        assert card1.suit == card2.suit
        assert card1.suit != card3.suit


class TestPlayAction:
    """Test PlayAction class."""

    def test_play_action_creation(self):
        """Test creating a play action."""
        cards = [Card('7', '♠'), Card('7', '♥')]
        action = PlayAction(
            player_idx=0,
            claimed_rank='7',
            claimed_count=2,
            actual_cards=cards,
            is_truthful=True
        )

        assert action.player_idx == 0
        assert action.claimed_rank == '7'
        assert action.claimed_count == 2
        assert len(action.actual_cards) == 2
        assert action.is_truthful

    def test_deceptive_action(self):
        """Test marking deceptive actions."""
        cards = [Card('7', '♠'), Card('8', '♥')]  # Mismatched
        action = PlayAction(
            player_idx=1,
            claimed_rank='7',
            claimed_count=2,
            actual_cards=cards,
            is_truthful=False
        )

        assert not action.is_truthful


class TestGameEdgeCases:
    """Test edge cases in game mechanics."""

    def test_empty_hand_after_win(self):
        """Test winner has empty hand."""
        state = GameState(num_players=2)

        # Give player 0 one card, play it
        card = Card('A', '♠')
        state.hands[0] = [card]
        state.hands[1] = [Card('K', '♥')]

        state.play_cards(0, 'A', [card])

        # Player 0 should have empty hand
        assert len(state.hands[0]) == 0

        # Game should be over
        is_over, winner = state.is_game_over()
        assert is_over
        assert winner == 0

    def test_large_pile_bs_call(self):
        """Test BS call with large accumulated pile."""
        state = GameState(num_players=2)

        # Build large pile
        state.hands[0] = []
        state.hands[1] = []

        for i in range(10):
            cards = [Card(RANKS[i % len(RANKS)], SUITS[i % len(SUITS)])]
            state.play_cards(0, RANKS[i % len(RANKS)], cards)

        assert len(state.discard_pile) == 10

        # Last play was truthful or not - call BS
        state.resolve_bs_call(1)

        # One player should have all 10 cards
        total_cards = sum(len(hand) for hand in state.hands)
        assert total_cards == 10

    def test_no_play_history_bs_call(self):
        """Test BS call when no plays have been made."""
        state = GameState(num_players=2)
        state.hands[0] = []
        state.hands[1] = []

        # Try to call BS with no play history
        caller_was_correct, loser = state.resolve_bs_call(1)

        # Caller should lose (no play to challenge)
        assert not caller_was_correct
        assert loser == 1

    def test_multiple_players_rotation(self):
        """Test player rotation with many players."""
        state = GameState(num_players=6)

        # Cycle through all players
        for i in range(6):
            assert state.current_player == i
            state.next_player()

        # Should be back to player 0
        assert state.current_player == 0

    def test_rank_full_cycle(self):
        """Test cycling through all 13 ranks."""
        state = GameState(num_players=2)

        # Cycle through all ranks
        for i, expected_rank in enumerate(RANKS):
            assert state.current_rank_idx == i
            assert state.get_current_rank() == expected_rank
            state.advance_rank()

        # Should be back to '2'
        assert state.current_rank_idx == 0
        assert state.get_current_rank() == '2'


class TestGameInvariants:
    """Test that game invariants are maintained."""

    def test_total_cards_constant(self):
        """Test total cards remains constant (conservation)."""
        state = GameState(num_players=4)

        initial_total = sum(len(hand) for hand in state.hands)
        assert initial_total == 52

        # Make some plays
        if len(state.hands[0]) >= 2:
            cards = state.hands[0][:2]
            state.play_cards(0, cards[0].rank, cards)

        # Total cards should be conserved
        total_in_hands = sum(len(hand) for hand in state.hands)
        total_in_pile = len(state.discard_pile)
        assert total_in_hands + total_in_pile == initial_total

    def test_no_duplicate_cards_single_deck(self):
        """Test no duplicate cards in single deck game."""
        state = GameState(num_players=4)

        # Collect all cards
        all_cards = []
        for hand in state.hands:
            all_cards.extend(hand)

        # Check uniqueness by comparing counts
        # Each rank-suit combination should appear exactly once
        card_strings = [f"{card.rank}{card.suit}" for card in all_cards]
        assert len(card_strings) == len(set(card_strings))

    def test_player_count_matches_hands(self):
        """Test number of hands matches number of players."""
        for num_players in [2, 3, 4, 5, 6]:
            state = GameState(num_players=num_players)
            assert len(state.hands) == num_players


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
