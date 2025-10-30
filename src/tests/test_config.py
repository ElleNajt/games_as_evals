"""Tests for configuration system."""

import json
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path

import pytest

from src.config import GameConfig, PlayerConfig


# Test GameConfig subclass
@dataclass
class SimpleGameConfig(GameConfig):
    """Test configuration with simple player setup."""
    
    num_players: int = 2
    player_template: PlayerConfig = field(default_factory=lambda: PlayerConfig(
        name="Player",
        backend_type="claude",
        model="claude-3-5-sonnet-20241022"
    ))
    
    def __post_init__(self):
        """Build players list."""
        self.players = [
            replace(self.player_template, name=f"Player_{i}")
            for i in range(self.num_players)
        ]
        super().__post_init__()


class TestPlayerConfig:
    """Tests for PlayerConfig."""
    
    def test_player_config_creation(self):
        """Test creating a player config."""
        config = PlayerConfig(
            name="Alice",
            backend_type="modal",
            model="meta-llama/Llama-3.1-8B-Instruct",
            probe="deception_8b",
            temperature=0.8,
            max_tokens=512,
            system_prompt="You are a player."
        )
        
        assert config.name == "Alice"
        assert config.backend_type == "modal"
        assert config.model == "meta-llama/Llama-3.1-8B-Instruct"
        assert config.probe == "deception_8b"
        assert config.temperature == 0.8
        assert config.max_tokens == 512
        assert config.system_prompt == "You are a player."
    
    def test_player_config_defaults(self):
        """Test player config with defaults."""
        config = PlayerConfig(
            name="Bob",
            backend_type="claude",
            model="claude-3-5-sonnet-20241022"
        )
        
        assert config.probe is None
        assert config.temperature == 0.7
        assert config.max_tokens == 512
        assert config.system_prompt == ""
    
    def test_player_config_to_dict(self):
        """Test converting player config to dict."""
        config = PlayerConfig(
            name="Charlie",
            backend_type="openrouter",
            model="gpt-4",
            probe=None,
            temperature=0.5
        )
        
        config_dict = config.to_dict()
        
        assert config_dict["name"] == "Charlie"
        assert config_dict["backend_type"] == "openrouter"
        assert config_dict["model"] == "gpt-4"
        assert config_dict["probe"] is None
        assert config_dict["temperature"] == 0.5


class TestGameConfig:
    """Tests for GameConfig base class."""
    
    def test_game_config_computes_git_hash(self):
        """Test that game config computes git hash."""
        config = SimpleGameConfig()
        
        # Should have a git hash (either real hash or "nogit")
        assert config.git_hash is not None
        assert len(config.git_hash) >= 6  # Short hash is at least 6 chars
    
    def test_game_config_computes_config_hash(self):
        """Test that game config computes config hash."""
        config = SimpleGameConfig()
        
        # Should have a config hash
        assert config.config_hash is not None
        assert len(config.config_hash) == 7  # SHA256 truncated to 7 chars
    
    def test_game_config_different_configs_have_different_hashes(self):
        """Test that different configs produce different hashes."""
        config1 = SimpleGameConfig(num_players=2)
        config2 = SimpleGameConfig(num_players=3)
        
        # Different configs should have different hashes
        assert config1.config_hash != config2.config_hash
    
    def test_game_config_same_configs_have_same_hashes(self):
        """Test that identical configs produce same hashes."""
        config1 = SimpleGameConfig(num_players=2, output_dir="./results")
        config2 = SimpleGameConfig(num_players=2, output_dir="./results")
        
        # Same configs should have same hashes (git hash may differ if commits happen)
        assert config1.config_hash == config2.config_hash
    
    def test_game_config_builds_players_list(self):
        """Test that subclass populates players list."""
        config = SimpleGameConfig(num_players=3)
        
        assert len(config.players) == 3
        assert config.players[0].name == "Player_0"
        assert config.players[1].name == "Player_1"
        assert config.players[2].name == "Player_2"
    
    def test_game_config_get_experiment_name(self):
        """Test experiment name generation."""
        config = SimpleGameConfig()
        experiment_name = config.get_experiment_name("baseline")
        
        # Format: baseline_{git_hash}_{config_hash}[_dirty]
        parts = experiment_name.split("_")
        assert parts[0] == "baseline"
        assert len(parts) >= 3  # At least baseline, git_hash, config_hash
        
        # If dirty, should end with _dirty
        if config.is_dirty:
            assert experiment_name.endswith("_dirty")
    
    def test_game_config_to_dict(self):
        """Test converting config to dict."""
        config = SimpleGameConfig(num_players=2)
        config_dict = config.to_dict()
        
        assert "output_dir" in config_dict
        assert "players" in config_dict
        assert "git_hash" in config_dict
        assert "config_hash" in config_dict
        assert "is_dirty" in config_dict
        assert "num_players" in config_dict
        
        # Players should be dicts
        assert isinstance(config_dict["players"], list)
        assert len(config_dict["players"]) == 2
        assert isinstance(config_dict["players"][0], dict)
    
    def test_game_config_save_and_load(self):
        """Test saving config to file."""
        config = SimpleGameConfig(num_players=3, output_dir="./test_results")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "config.json"
            
            # Save config
            config.save(filepath)
            
            # File should exist and be valid JSON
            assert filepath.exists()
            with open(filepath) as f:
                saved_data = json.load(f)
            
            assert saved_data["num_players"] == 3
            assert saved_data["output_dir"] == "./test_results"
            assert len(saved_data["players"]) == 3
            
            # Verify player data is serialized correctly
            assert saved_data["players"][0]["name"] == "Player_0"
            assert saved_data["players"][0]["backend_type"] == "claude"
    
    def test_game_config_hash_excludes_auto_computed_fields(self):
        """Test that config hash doesn't include git_hash, config_hash, is_dirty."""
        config1 = SimpleGameConfig(num_players=2)
        
        # Manually modify auto-computed fields
        original_hash = config1.config_hash
        config1.git_hash = "abcdefg"
        config1.is_dirty = not config1.is_dirty
        
        # Recompute hash
        new_hash = config1._compute_config_hash()
        
        # Hash should be unchanged (auto-computed fields excluded)
        assert new_hash == original_hash


class TestWerewolfConfigPattern:
    """Tests demonstrating the Werewolf config pattern."""
    
    @dataclass
    class WerewolfConfig(GameConfig):
        """Example Werewolf config."""
        
        num_villagers: int = 3
        num_werewolves: int = 1
        villager_config: PlayerConfig = field(default_factory=lambda: PlayerConfig(
            name="Villager",
            backend_type="claude",
            model="claude-3-5-sonnet-20241022"
        ))
        werewolf_config: PlayerConfig = field(default_factory=lambda: PlayerConfig(
            name="Werewolf",
            backend_type="modal",
            model="meta-llama/Llama-3.1-8B-Instruct",
            probe="deception_8b"
        ))
        
        def __post_init__(self):
            villagers = [
                replace(self.villager_config, name=f"Villager_{i}")
                for i in range(self.num_villagers)
            ]
            werewolves = [
                replace(self.werewolf_config, name=f"Werewolf_{i}")
                for i in range(self.num_werewolves)
            ]
            self.players = villagers + werewolves
            super().__post_init__()
    
    def test_werewolf_config_creates_correct_players(self):
        """Test that Werewolf config creates right number of players."""
        config = self.WerewolfConfig(num_villagers=5, num_werewolves=2)
        
        assert len(config.players) == 7
        
        # First 5 should be villagers
        for i in range(5):
            assert config.players[i].name == f"Villager_{i}"
            assert config.players[i].backend_type == "claude"
            assert config.players[i].probe is None
        
        # Last 2 should be werewolves
        for i in range(2):
            assert config.players[5 + i].name == f"Werewolf_{i}"
            assert config.players[5 + i].backend_type == "modal"
            assert config.players[5 + i].probe == "deception_8b"
    
    def test_werewolf_config_different_role_configs(self):
        """Test that roles can have different configs."""
        config = self.WerewolfConfig(
            num_villagers=2,
            num_werewolves=1,
            villager_config=PlayerConfig(
                name="V",
                backend_type="openrouter",
                model="gpt-4",
                temperature=0.5
            ),
            werewolf_config=PlayerConfig(
                name="W",
                backend_type="modal",
                model="meta-llama/Llama-3.1-70B-Instruct",
                probe="deception_70b",
                temperature=0.9
            )
        )
        
        # Villagers
        assert config.players[0].backend_type == "openrouter"
        assert config.players[0].model == "gpt-4"
        assert config.players[0].temperature == 0.5
        
        # Werewolves
        assert config.players[2].backend_type == "modal"
        assert config.players[2].model == "meta-llama/Llama-3.1-70B-Instruct"
        assert config.players[2].probe == "deception_70b"
        assert config.players[2].temperature == 0.9
