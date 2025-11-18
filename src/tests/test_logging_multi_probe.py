"""Tests for logging system with multi-probe support."""

import json
import tempfile
from pathlib import Path

import pytest

from src.backends.base import GenerationResult, ProbeScores, ProbeScoreData
from src.config import GameConfig
from src.result_logging import ResultsLogger


class TestResultsLoggerMultiProbe:
    """Tests for ResultsLogger with multi-probe ProbeScores structure."""
    
    def test_logger_log_message_with_multi_probe_scores(self):
        """Test logging a message with multi-probe scores (new structure)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameConfig(output_dir=tmpdir, git_hash='test123')
            logger = ResultsLogger(
                config=config,
                game_name="test_game",
                experiment_base="baseline"
            )
            
            # Create ProbeScores with new nested structure
            probe_scores = ProbeScores(
                scores={
                    'deception_8b': ProbeScoreData(
                        aggregate_score=0.85,
                        token_scores=[0.7, 0.8, 0.9, 0.95]
                    ),
                    'hallucination_8b': ProbeScoreData(
                        aggregate_score=0.65,
                        token_scores=[0.5, 0.6, 0.7, 0.8]
                    ),
                }
            )
            
            logger.log_message(
                player_name="Bob",
                role="assistant",
                prompt="Are you lying?",
                response="No.",
                tokens=["No", "."],
                probe_scores=probe_scores
            )
            
            # Read and check
            messages_file = logger.results_dir / "messages.jsonl"
            with open(messages_file) as f:
                entry = json.loads(f.read())
            
            # Verify structure
            assert "probe_scores" in entry
            assert "deception_8b" in entry["probe_scores"]
            assert "hallucination_8b" in entry["probe_scores"]
            
            # Verify deception probe scores
            dec_scores = entry["probe_scores"]["deception_8b"]
            assert dec_scores["aggregate_score"] == 0.85
            assert dec_scores["token_scores"] == [0.7, 0.8, 0.9, 0.95]
            
            # Verify hallucination probe scores
            hall_scores = entry["probe_scores"]["hallucination_8b"]
            assert hall_scores["aggregate_score"] == 0.65
            assert hall_scores["token_scores"] == [0.5, 0.6, 0.7, 0.8]
    
    def test_logger_log_message_with_single_probe(self):
        """Test logging with single probe (should still work)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameConfig(output_dir=tmpdir, git_hash='test123')
            logger = ResultsLogger(
                config=config,
                game_name="test_game",
                experiment_base="baseline"
            )
            
            # Single probe
            probe_scores = ProbeScores(
                scores={
                    'deception_8b': ProbeScoreData(
                        aggregate_score=0.75,
                        token_scores=[0.6, 0.7, 0.8, 0.9]
                    ),
                }
            )
            
            logger.log_message(
                player_name="Alice",
                role="assistant",
                prompt="Test",
                response="Response",
                probe_scores=probe_scores
            )
            
            # Read and check
            messages_file = logger.results_dir / "messages.jsonl"
            with open(messages_file) as f:
                entry = json.loads(f.read())
            
            assert "probe_scores" in entry
            assert "deception_8b" in entry["probe_scores"]
            assert entry["probe_scores"]["deception_8b"]["aggregate_score"] == 0.75
    
    def test_logger_log_message_without_probe_scores(self):
        """Test logging without probe scores (should not include probe_scores field)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameConfig(output_dir=tmpdir, git_hash='test123')
            logger = ResultsLogger(
                config=config,
                game_name="test_game",
                experiment_base="baseline"
            )
            
            logger.log_message(
                player_name="Charlie",
                role="assistant",
                prompt="Test",
                response="Response",
                probe_scores=None
            )
            
            # Read and check
            messages_file = logger.results_dir / "messages.jsonl"
            with open(messages_file) as f:
                entry = json.loads(f.read())
            
            # probe_scores should not be present when None
            assert "probe_scores" not in entry
    
    def test_logger_serializes_empty_probe_scores(self):
        """Test that empty ProbeScores dict is serialized correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameConfig(output_dir=tmpdir, git_hash='test123')
            logger = ResultsLogger(
                config=config,
                game_name="test_game",
                experiment_base="baseline"
            )
            
            # Empty ProbeScores
            probe_scores = ProbeScores(scores={})
            
            logger.log_message(
                player_name="Dave",
                role="assistant",
                prompt="Test",
                response="Response",
                probe_scores=probe_scores
            )
            
            # Read and check
            messages_file = logger.results_dir / "messages.jsonl"
            with open(messages_file) as f:
                entry = json.loads(f.read())
            
            # Should have probe_scores field, but it should be an empty dict
            assert "probe_scores" in entry
            assert entry["probe_scores"] == {}
    
    def test_logger_handles_multiple_messages_with_different_probes(self):
        """Test logging multiple messages with different probe configurations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameConfig(output_dir=tmpdir, git_hash='test123')
            logger = ResultsLogger(
                config=config,
                game_name="test_game",
                experiment_base="baseline"
            )
            
            # Message 1: Both probes
            probe_scores_1 = ProbeScores(
                scores={
                    'deception_8b': ProbeScoreData(aggregate_score=0.8, token_scores=[0.8]),
                    'hallucination_8b': ProbeScoreData(aggregate_score=0.6, token_scores=[0.6]),
                }
            )
            logger.log_message(
                player_name="Player1",
                role="assistant",
                prompt="Test1",
                response="Response1",
                probe_scores=probe_scores_1
            )
            
            # Message 2: Only deception probe
            probe_scores_2 = ProbeScores(
                scores={
                    'deception_8b': ProbeScoreData(aggregate_score=0.7, token_scores=[0.7]),
                }
            )
            logger.log_message(
                player_name="Player2",
                role="assistant",
                prompt="Test2",
                response="Response2",
                probe_scores=probe_scores_2
            )
            
            # Message 3: No probes
            logger.log_message(
                player_name="Player3",
                role="assistant",
                prompt="Test3",
                response="Response3",
                probe_scores=None
            )
            
            # Read all messages
            messages_file = logger.results_dir / "messages.jsonl"
            with open(messages_file) as f:
                lines = f.readlines()
            
            assert len(lines) == 3
            
            # Check message 1
            entry1 = json.loads(lines[0])
            assert len(entry1["probe_scores"]) == 2
            assert "deception_8b" in entry1["probe_scores"]
            assert "hallucination_8b" in entry1["probe_scores"]
            
            # Check message 2
            entry2 = json.loads(lines[1])
            assert len(entry2["probe_scores"]) == 1
            assert "deception_8b" in entry2["probe_scores"]
            assert "hallucination_8b" not in entry2["probe_scores"]
            
            # Check message 3
            entry3 = json.loads(lines[2])
            assert "probe_scores" not in entry3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
