"""Tests for Werewolf configuration."""

import tempfile
from pathlib import Path

import pytest

from src.games.werewolf import WerewolfConfig
from src.config import PlayerConfig


class TestWerewolfConfig:
    """Tests for WerewolfConfig."""
    
    def test_werewolf_config_builds_correct_player_list(self):
        """Test that WerewolfConfig creates correct players."""
        config = WerewolfConfig(
            num_players=7,
            num_werewolves=2,
            no_seer=False
        )
        
        # Should have 7 players total: 2 werewolves, 1 seer, 4 villagers
        assert len(config.players) == 7
        
        # First 2 should be werewolves
        assert config.players[0].name == "Werewolf_0"
        assert config.players[1].name == "Werewolf_1"
        
        # Next should be seer
        assert config.players[2].name == "Seer"
        
        # Rest should be villagers
        for i in range(4):
            assert config.players[3 + i].name == f"Villager_{i}"
    
    def test_werewolf_config_no_seer(self):
        """Test WerewolfConfig with no seer."""
        config = WerewolfConfig(
            num_players=6,
            num_werewolves=2,
            no_seer=True
        )
        
        # Should have 6 players: 2 werewolves, 4 villagers (no seer)
        assert len(config.players) == 6
        
        # Check no seer in player list
        player_names = [p.name for p in config.players]
        assert "Seer" not in player_names
        
        # Should have 2 werewolves and 4 villagers
        werewolves = [p for p in config.players if "Werewolf" in p.name]
        villagers = [p for p in config.players if "Villager" in p.name]
        assert len(werewolves) == 2
        assert len(villagers) == 4
    
    def test_werewolf_config_custom_player_configs(self):
        """Test WerewolfConfig with custom player configurations."""
        villager_cfg = PlayerConfig(
            name="V",
            backend_type="openrouter",
            model="gpt-4",
            temperature=0.5
        )
        
        werewolf_cfg = PlayerConfig(
            name="W",
            backend_type="modal",
            model="meta-llama/Llama-3.1-8B-Instruct",
            probe="deception_8b",
            temperature=0.9
        )
        
        config = WerewolfConfig(
            num_players=5,
            num_werewolves=1,
            no_seer=True,
            villager_config=villager_cfg,
            werewolf_config=werewolf_cfg
        )
        
        # Check werewolf config
        assert config.players[0].backend_type == "modal"
        assert config.players[0].probe == "deception_8b"
        assert config.players[0].temperature == 0.9
        
        # Check villager configs
        for i in range(1, 5):
            assert config.players[i].backend_type == "openrouter"
            assert config.players[i].model == "gpt-4"
            assert config.players[i].temperature == 0.5
    
    def test_werewolf_config_experiment_name(self):
        """Test experiment name generation."""
        config = WerewolfConfig(num_players=6, num_werewolves=2)
        
        experiment_name = config.get_experiment_name("baseline")
        
        # Should include baseline, git hash, and config hash
        assert "baseline" in experiment_name
        assert config.git_hash in experiment_name
        assert config.config_hash in experiment_name
    
    def test_werewolf_config_different_settings_different_hashes(self):
        """Test that different configs produce different hashes."""
        config1 = WerewolfConfig(num_players=6, max_turns=5)
        config2 = WerewolfConfig(num_players=6, max_turns=10)
        
        # Different settings should produce different hashes
        assert config1.config_hash != config2.config_hash
    
    def test_werewolf_config_save(self):
        """Test saving WerewolfConfig to file."""
        config = WerewolfConfig(
            num_players=6,
            num_werewolves=2,
            max_turns=3,
            provide_probe_scores=True
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "config.json"
            config.save(filepath)
            
            # File should exist and contain correct data
            assert filepath.exists()
            
            import json
            with open(filepath) as f:
                data = json.load(f)
            
            assert data["num_players"] == 6
            assert data["num_werewolves"] == 2
            assert data["max_turns"] == 3
            assert data["provide_probe_scores"] is True
            assert len(data["players"]) == 6
    
    def test_werewolf_config_game_settings(self):
        """Test werewolf-specific game settings."""
        config = WerewolfConfig(
            max_turns=10,
            num_players=12,
            num_werewolves=3,
            num_discussion_rounds=2,
            allow_player_callouts=True,
            provide_probe_scores=True,
            public_cot=True,
            request_reasoning=True
        )
        
        assert config.max_turns == 10
        assert config.num_players == 12
        assert config.num_werewolves == 3
        assert config.num_discussion_rounds == 2
        assert config.allow_player_callouts is True
        assert config.provide_probe_scores is True
        assert config.public_cot is True
        assert config.request_reasoning is True
    
    def test_werewolf_config_instructions(self):
        """Test custom instruction fields."""
        config = WerewolfConfig(
            num_players=6,
            num_werewolves=2,
            additional_instructions="Be strategic.",
            werewolf_instructions="Coordinate with your team.",
            villager_instructions="Trust but verify."
        )
        
        assert config.additional_instructions == "Be strategic."
        assert config.werewolf_instructions == "Coordinate with your team."
        assert config.villager_instructions == "Trust but verify."
