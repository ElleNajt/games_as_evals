"""Tests for logging system."""

import json
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path

import pytest

from src.backends.base import GenerationResult, ProbeScores
from src.config import GameConfig, PlayerConfig
from src.result_logging import ResultsLogger


# Test GameConfig for logging tests
@dataclass
class SimpleGameConfig(GameConfig):
    """Test configuration."""
    
    num_players: int = 2
    
    def __post_init__(self):
        self.players = [
            PlayerConfig(name=f"Player_{i}", backend_type="claude", model="claude-3-5-sonnet-20241022")
            for i in range(self.num_players)
        ]
        super().__post_init__()


class TestResultsLogger:
    """Tests for ResultsLogger."""
    
    def test_logger_creates_directory(self):
        """Test that logger creates results directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SimpleGameConfig(output_dir=tmpdir)
            logger = ResultsLogger(
                config=config,
                game_name="test_game",
                experiment_base="baseline"
            )
            
            # Directory should exist
            assert logger.results_dir.exists()
            assert logger.results_dir.is_dir()
            
            # Should be: tmpdir/test_game/{experiment_name}/
            assert "test_game" in str(logger.results_dir)
            assert "baseline" in str(logger.results_dir)
    
    def test_logger_creates_game_subdirectory(self):
        """Test that logger creates game instance subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SimpleGameConfig(output_dir=tmpdir)
            logger = ResultsLogger(
                config=config,
                game_name="test_game",
                experiment_base="baseline",
                game_id=5
            )
            
            # Should be: tmpdir/test_game/{experiment_name}/game5/
            assert logger.results_dir.exists()
            assert "game5" in str(logger.results_dir)
    
    def test_logger_saves_config(self):
        """Test that logger saves config on initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SimpleGameConfig(output_dir=tmpdir, num_players=3)
            logger = ResultsLogger(
                config=config,
                game_name="test_game",
                experiment_base="baseline"
            )
            
            # Config file should exist
            config_file = logger.results_dir / "config.json"
            assert config_file.exists()
            
            # Should be valid JSON with correct data
            with open(config_file) as f:
                saved_config = json.load(f)
            
            assert saved_config["num_players"] == 3
            assert len(saved_config["players"]) == 3
    
    def test_logger_log_message(self):
        """Test logging a player message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SimpleGameConfig(output_dir=tmpdir)
            logger = ResultsLogger(
                config=config,
                game_name="test_game",
                experiment_base="baseline"
            )
            
            # Log a message
            logger.log_message(
                player_name="Alice",
                role="assistant",
                prompt="What's your move?",
                response="I choose option A.",
                tokens=["I", " choose", " option", " A", "."],
                metadata={"temperature": 0.7}
            )
            
            # Messages file should exist
            messages_file = logger.results_dir / "messages.jsonl"
            assert messages_file.exists()
            
            # Should contain one line
            with open(messages_file) as f:
                lines = f.readlines()
            
            assert len(lines) == 1
            
            # Parse and check content
            entry = json.loads(lines[0])
            assert entry["player_name"] == "Alice"
            assert entry["role"] == "assistant"
            assert entry["prompt"] == "What's your move?"
            assert entry["response"] == "I choose option A."
            assert entry["tokens"] == ["I", " choose", " option", " A", "."]
            assert entry["metadata"]["temperature"] == 0.7
            assert "timestamp" in entry
    
    def test_logger_log_message_with_probe_scores(self):
        """Test logging a message with probe scores."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SimpleGameConfig(output_dir=tmpdir)
            logger = ResultsLogger(
                config=config,
                game_name="test_game",
                experiment_base="baseline"
            )
            
            probe_scores = ProbeScores(
                aggregate_score=0.85,
                token_scores=[0.7, 0.8, 0.9, 0.95],
                phase_scores={"reasoning": 0.6, "answer": 0.95}
            )
            
            logger.log_message(
                player_name="Bob",
                role="assistant",
                prompt="Are you lying?",
                response="No.",
                probe_scores=probe_scores
            )
            
            # Read and check
            messages_file = logger.results_dir / "messages.jsonl"
            with open(messages_file) as f:
                entry = json.loads(f.read())
            
            assert "probe_scores" in entry
            assert entry["probe_scores"]["aggregate_score"] == 0.85
            assert entry["probe_scores"]["token_scores"] == [0.7, 0.8, 0.9, 0.95]
            assert entry["probe_scores"]["phase_scores"]["reasoning"] == 0.6
    
    def test_logger_log_multiple_messages(self):
        """Test logging multiple messages (JSONL format)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SimpleGameConfig(output_dir=tmpdir)
            logger = ResultsLogger(
                config=config,
                game_name="test_game",
                experiment_base="baseline"
            )
            
            # Log multiple messages
            for i in range(5):
                logger.log_message(
                    player_name=f"Player_{i}",
                    role="assistant",
                    prompt=f"Prompt {i}",
                    response=f"Response {i}"
                )
            
            # Should have 5 lines
            messages_file = logger.results_dir / "messages.jsonl"
            with open(messages_file) as f:
                lines = f.readlines()
            
            assert len(lines) == 5
            
            # Each should be valid JSON
            for i, line in enumerate(lines):
                entry = json.loads(line)
                assert entry["player_name"] == f"Player_{i}"
                assert entry["prompt"] == f"Prompt {i}"
                assert entry["response"] == f"Response {i}"
    
    def test_logger_log_game_event(self):
        """Test logging game events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SimpleGameConfig(output_dir=tmpdir)
            logger = ResultsLogger(
                config=config,
                game_name="test_game",
                experiment_base="baseline"
            )
            
            # Log an event
            logger.log_game_event(
                event_type="round_start",
                data={"round": 1, "active_players": 5}
            )
            
            # Events file should exist
            events_file = logger.results_dir / "events.jsonl"
            assert events_file.exists()
            
            # Check content
            with open(events_file) as f:
                entry = json.loads(f.read())
            
            assert entry["event_type"] == "round_start"
            assert entry["data"]["round"] == 1
            assert entry["data"]["active_players"] == 5
            assert "timestamp" in entry
    
    def test_logger_save_results(self):
        """Test saving final results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SimpleGameConfig(output_dir=tmpdir)
            logger = ResultsLogger(
                config=config,
                game_name="test_game",
                experiment_base="baseline"
            )
            
            # Save results
            results = {
                "winner": "villagers",
                "rounds": 8,
                "eliminations": ["Player_1", "Player_3"],
                "final_score": 0.85
            }
            logger.save_results(results)
            
            # Results file should exist
            results_file = logger.results_dir / "results.json"
            assert results_file.exists()
            
            # Check content
            with open(results_file) as f:
                saved_results = json.load(f)
            
            assert saved_results["winner"] == "villagers"
            assert saved_results["rounds"] == 8
            assert saved_results["final_score"] == 0.85
    
    def test_logger_experiment_name_includes_hashes(self):
        """Test that experiment name includes git and config hashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SimpleGameConfig(output_dir=tmpdir)
            logger = ResultsLogger(
                config=config,
                game_name="test_game",
                experiment_base="baseline"
            )
            
            # Experiment name should include hashes
            assert "baseline" in logger.experiment_name
            assert config.git_hash in logger.experiment_name
            assert config.config_hash in logger.experiment_name
            
            # Directory name should match
            assert logger.experiment_name in str(logger.results_dir)
    
    def test_logger_get_results_path(self):
        """Test getting results directory path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SimpleGameConfig(output_dir=tmpdir)
            logger = ResultsLogger(
                config=config,
                game_name="test_game",
                experiment_base="baseline",
                game_id=3
            )
            
            path = logger.get_results_path()
            
            assert path == logger.results_dir
            assert path.exists()
            assert "game3" in str(path)


class TestPlayerLogging:
    """Tests for GamePlayer logging integration."""
    
    def test_player_logs_when_logger_provided(self):
        """Test that GamePlayer logs messages when logger is provided."""
        from unittest.mock import Mock
        from src.backends.base import LLMBackend
        from src.player import GamePlayer
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup
            config = SimpleGameConfig(output_dir=tmpdir)
            logger = ResultsLogger(
                config=config,
                game_name="test_game",
                experiment_base="baseline"
            )
            
            # Create mock backend
            mock_backend = Mock(spec=LLMBackend)
            mock_backend.generate.return_value = GenerationResult(
                text="My response",
                tokens=["My", " response"],
                top_k_logits=None,
                probe_scores=None
            )
            
            # Create player with logger
            player = GamePlayer(
                name="Alice",
                backend=mock_backend,
                system_prompt="You are Alice.",
                logger=logger
            )
            
            # Query player
            result = player.query("What's your move?")
            
            # Should have logged the message
            messages_file = logger.results_dir / "messages.jsonl"
            assert messages_file.exists()
            
            with open(messages_file) as f:
                entry = json.loads(f.read())
            
            assert entry["player_name"] == "Alice"
            assert entry["prompt"] == "What's your move?"
            assert entry["response"] == "My response"
            assert entry["tokens"] == ["My", " response"]
            assert entry["metadata"]["system_prompt"] == "You are Alice."
    
    def test_player_does_not_log_when_logger_not_provided(self):
        """Test that GamePlayer doesn't log when logger is None."""
        from unittest.mock import Mock
        from src.backends.base import LLMBackend
        from src.player import GamePlayer
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock backend
            mock_backend = Mock(spec=LLMBackend)
            mock_backend.generate.return_value = GenerationResult(text="Response")
            
            # Create player WITHOUT logger
            player = GamePlayer(
                name="Bob",
                backend=mock_backend,
                logger=None
            )
            
            # Query player
            result = player.query("Test")
            
            # Should work fine, no logging
            assert result.text == "Response"
