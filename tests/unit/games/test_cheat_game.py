"""
Tests for the Cheat (Bullshit) card game.
"""

import pytest
from unittest.mock import Mock, patch
from src.games.cheat.config import CheatConfig
from src.games.cheat.game_state import (
    CheatGameState, PlayerState, Card, Rank, 
    create_deck, deal_cards
)
from src.games.cheat.orchestrator import CheatOrchestrator
from src.config.player_config import PlayerConfig


class TestGameState:
    """Test game state management."""
    
    def test_create_deck(self):
        """Test deck creation."""
        deck = create_deck(num_decks=1)
        assert len(deck) == 52
        
        # Check all ranks and suits present
        ranks = {card.rank for card in deck}
        assert len(ranks) == 13
        
        suits = {card.suit for card in deck}
        assert len(suits) == 4
    
    def test_create_two_decks(self):
        """Test creating two decks."""
        deck = create_deck(num_decks=2)
        assert len(deck) == 104
    
    def test_deal_cards(self):
        """Test dealing cards to players."""
        hands = deal_cards(num_players=4, num_decks=1)
        assert len(hands) == 4
        
        # All players should have 13 cards (52/4)
        for hand in hands:
            assert len(hand) == 13
        
        # Total should be 52 cards
        total_cards = sum(len(hand) for hand in hands)
        assert total_cards == 52
    
    def test_deal_cards_uneven(self):
        """Test dealing with uneven distribution."""
        hands = deal_cards(num_players=3, num_decks=1)
        assert len(hands) == 3
        
        # Some players get 17, some get 18 (52 cards / 3 players)
        card_counts = [len(hand) for hand in hands]
        assert min(card_counts) == 17
        assert max(card_counts) == 18
        assert sum(card_counts) == 52
    
    def test_rank_cycle(self):
        """Test rank cycling (King -> Ace)."""
        assert Rank.ACE.next() == Rank.TWO
        assert Rank.KING.next() == Rank.ACE
    
    def test_player_state_operations(self):
        """Test player state card operations."""
        player = PlayerState(name="Test", hand=[
            Card(Rank.ACE, '♠'),
            Card(Rank.ACE, '♥'),
            Card(Rank.KING, '♦')
        ])
        
        assert player.num_cards() == 3
        assert player.has_rank(Rank.ACE)
        assert player.count_rank(Rank.ACE) == 2
        assert not player.has_rank(Rank.QUEEN)
    
    def test_play_cards(self):
        """Test playing cards to pile."""
        players = [
            PlayerState(name="P1", hand=[Card(Rank.ACE, '♠'), Card(Rank.TWO, '♥')]),
            PlayerState(name="P2", hand=[Card(Rank.THREE, '♦')])
        ]
        state = CheatGameState(players=players)
        
        cards = [Card(Rank.ACE, '♠')]
        state.play_cards(
            player_idx=0,
            cards=cards,
            claimed_rank=Rank.ACE,
            claimed_count=1
        )
        
        assert players[0].num_cards() == 1
        assert len(state.pile) == 1
        assert state.last_play is not None
        assert state.last_play['claimed_count'] == 1
    
    def test_resolve_challenge_honest(self):
        """Test challenging an honest play."""
        players = [
            PlayerState(name="P1", hand=[]),
            PlayerState(name="P2", hand=[])
        ]
        state = CheatGameState(players=players)
        
        # P1 plays honestly
        cards = [Card(Rank.ACE, '♠'), Card(Rank.ACE, '♥')]
        state.play_cards(0, cards, Rank.ACE, 2)
        
        # P2 challenges
        result = state.resolve_challenge(1)
        
        assert result['was_lying'] is False
        assert result['loser_idx'] == 1  # Challenger loses
        assert players[1].num_cards() == 2  # Picked up the pile
        assert len(state.pile) == 0
    
    def test_resolve_challenge_lying(self):
        """Test challenging a dishonest play."""
        players = [
            PlayerState(name="P1", hand=[]),
            PlayerState(name="P2", hand=[])
        ]
        state = CheatGameState(players=players)
        
        # P1 lies (plays Kings but claims Aces)
        cards = [Card(Rank.KING, '♠'), Card(Rank.KING, '♥')]
        state.play_cards(0, cards, Rank.ACE, 2)
        
        # P2 challenges
        result = state.resolve_challenge(1)
        
        assert result['was_lying'] is True
        assert result['loser_idx'] == 0  # Liar loses
        assert players[0].num_cards() == 2  # Picked up the pile
        assert len(state.pile) == 0
    
    def test_resolve_challenge_wrong_count(self):
        """Test challenge when count is wrong (also a lie)."""
        players = [
            PlayerState(name="P1", hand=[]),
            PlayerState(name="P2", hand=[])
        ]
        state = CheatGameState(players=players)
        
        # P1 plays 2 Aces but claims 3
        cards = [Card(Rank.ACE, '♠'), Card(Rank.ACE, '♥')]
        state.play_cards(0, cards, Rank.ACE, 3)  # Claimed 3, played 2
        
        # P2 challenges
        result = state.resolve_challenge(1)
        
        assert result['was_lying'] is True  # Wrong count is lying
        assert result['loser_idx'] == 0
    
    def test_check_winner(self):
        """Test winner detection."""
        players = [
            PlayerState(name="P1", hand=[]),  # No cards
            PlayerState(name="P2", hand=[Card(Rank.KING, '♠')])
        ]
        state = CheatGameState(players=players)
        
        winner = state.check_winner()
        assert winner == "P1"
        assert state.game_over
        assert state.winner == "P1"


class TestCheatConfig:
    """Test configuration."""
    
    def test_config_basic(self):
        """Test basic config creation."""
        player_template = PlayerConfig(
            name="template",
            backend_type="claude",
            backend_config={},
            system_prompt="Test"
        )
        
        config = CheatConfig(
            experiment_base="test",
            num_players=4,
            player_template=player_template
        )
        
        assert len(config.players) == 4
        assert config.num_decks == 1  # 4 players, 1 deck
    
    def test_config_auto_two_decks(self):
        """Test automatic 2-deck selection for 5+ players."""
        player_template = PlayerConfig(
            name="template",
            backend_type="claude",
            backend_config={},
            system_prompt="Test"
        )
        
        config = CheatConfig(
            experiment_base="test",
            num_players=6,
            player_template=player_template
        )
        
        assert config.num_decks == 2  # Auto-selected
    
    def test_config_validation(self):
        """Test config validation."""
        player_template = PlayerConfig(
            name="template",
            backend_type="claude",
            backend_config={},
            system_prompt="Test"
        )
        
        # Too few players
        with pytest.raises(ValueError, match="at least 2 players"):
            config = CheatConfig(
                experiment_base="test",
                num_players=1,
                player_template=player_template
            )
        
        # Too many players
        with pytest.raises(ValueError, match="Maximum 10 players"):
            config = CheatConfig(
                experiment_base="test",
                num_players=11,
                player_template=player_template
            )


class TestOrchestratorWithMocks:
    """Test orchestrator with mocked backends."""
    
    @patch('src.player.GamePlayer.from_config')
    @patch('src.result_logging.results_logger.ResultsLogger')
    def test_setup_game(self, mock_logger_class, mock_player_from_config):
        """Test game setup."""
        player_template = PlayerConfig(
            name="template",
            backend_type="claude",
            backend_config={},
            system_prompt="Test"
        )
        
        config = CheatConfig(
            experiment_base="test",
            num_players=3,
            player_template=player_template
        )
        
        # Mock players
        mock_players = [Mock() for _ in range(3)]
        mock_player_from_config.side_effect = mock_players
        
        orchestrator = CheatOrchestrator(config)
        orchestrator.setup_game()
        
        # Check state initialized
        assert orchestrator.state is not None
        assert len(orchestrator.state.players) == 3
        assert len(orchestrator.players) == 3
        
        # Check cards dealt
        total_cards = sum(p.num_cards() for p in orchestrator.state.players)
        assert total_cards == 52  # 1 deck
    
    @patch('src.player.GamePlayer.from_config')
    @patch('src.result_logging.results_logger.ResultsLogger')
    def test_game_flow_with_mocks(self, mock_logger_class, mock_player_from_config):
        """Test a simple game flow with mocked player responses."""
        player_template = PlayerConfig(
            name="template",
            backend_type="claude",
            backend_config={},
            system_prompt="Test"
        )
        
        config = CheatConfig(
            experiment_base="test",
            num_players=2,
            max_turns=5,  # Short game for testing
            player_template=player_template
        )
        
        # Mock players with simple responses
        mock_players = []
        for i in range(2):
            player = Mock()
            
            # Mock play response
            play_response = Mock()
            play_response.text = "PLAY: 1\nSTRATEGY: Playing one card\nCARDS: Ace"
            
            # Mock challenge response (never challenge)
            challenge_response = Mock()
            challenge_response.text = "PASS"
            
            player.query.side_effect = [play_response, challenge_response] * 10
            mock_players.append(player)
        
        mock_player_from_config.side_effect = mock_players
        
        orchestrator = CheatOrchestrator(config)
        results = orchestrator.run_game()
        
        # Game should complete (either winner or max turns)
        assert results is not None
        assert 'total_turns' in results
        assert results['total_turns'] <= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
