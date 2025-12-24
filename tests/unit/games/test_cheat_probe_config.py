"""Test probe advantage configuration for Cheat game."""

import pytest
from src.config.player_config import PlayerConfig
from src.games.cheat.config import CheatConfig


class TestCheatProbeAdvantageConfig:
    """Test that probe advantage configuration works correctly."""

    def test_probe_player_override(self):
        """Test that we can override player 0 with probe-assisted config."""
        # Baseline player template
        baseline = PlayerConfig(
            name="Baseline",
            backend_type="mock",
            model="test-model",
            can_see_probes=False,
            probes=["deception_8b", "hallucination_8b"],
        )

        # Probe-assisted player
        probe_player = PlayerConfig(
            name="ProbePlayer",
            backend_type="mock",
            model="test-model",
            can_see_probes=True,
            probes=["deception_8b", "hallucination_8b"],
        )

        # Create config with baseline template
        config = CheatConfig(
            num_players=4,
            num_decks=1,
            max_turns=100,
            player_template=baseline,
            provide_probe_scores=True,
        )

        # Verify all players start as baseline
        assert len(config.players) == 4
        assert all(p.can_see_probes == False for p in config.players)

        # Override player 0 with probe-assisted player
        config.players[0] = probe_player

        # Verify override worked
        assert config.players[0].name == "ProbePlayer"
        assert config.players[0].can_see_probes == True
        assert config.players[1].can_see_probes == False
        assert config.players[2].can_see_probes == False
        assert config.players[3].can_see_probes == False

    def test_provide_probe_scores_flag(self):
        """Test that provide_probe_scores flag is set correctly."""
        baseline = PlayerConfig(
            name="Baseline",
            backend_type="mock",
            model="test-model",
        )

        # With provide_probe_scores=True
        config1 = CheatConfig(
            num_players=4,
            player_template=baseline,
            provide_probe_scores=True,
        )
        assert config1.provide_probe_scores == True

        # With provide_probe_scores=False (default)
        config2 = CheatConfig(
            num_players=4,
            player_template=baseline,
            provide_probe_scores=False,
        )
        assert config2.provide_probe_scores == False

    def test_mixed_probe_visibility(self):
        """Test that we can have mixed probe visibility among players."""
        baseline = PlayerConfig(
            name="Baseline",
            backend_type="mock",
            model="test-model",
            can_see_probes=False,
        )

        probe_player = PlayerConfig(
            name="ProbePlayer",
            backend_type="mock",
            model="test-model",
            can_see_probes=True,
        )

        config = CheatConfig(
            num_players=4,
            player_template=baseline,
            provide_probe_scores=True,
        )

        # Override players 0 and 2 with probe access
        config.players[0] = probe_player
        config.players[2] = probe_player

        # Verify mixed visibility
        assert config.players[0].can_see_probes == True
        assert config.players[1].can_see_probes == False
        assert config.players[2].can_see_probes == True
        assert config.players[3].can_see_probes == False

    def test_probe_configs_preserved(self):
        """Test that probe configurations are preserved when overriding players."""
        baseline = PlayerConfig(
            name="Baseline",
            backend_type="mock",
            model="baseline-model",
            probes=["probe_a"],
        )

        probe_player = PlayerConfig(
            name="ProbePlayer",
            backend_type="mock",
            model="probe-model",
            probes=["probe_b", "probe_c"],
        )

        config = CheatConfig(
            num_players=2,
            player_template=baseline,
        )

        # Verify baseline probes
        assert config.players[0].probes == ["probe_a"]
        assert config.players[1].probes == ["probe_a"]

        # Override player 0
        config.players[0] = probe_player

        # Verify probes are preserved correctly
        assert config.players[0].probes == ["probe_b", "probe_c"]
        assert config.players[1].probes == ["probe_a"]
