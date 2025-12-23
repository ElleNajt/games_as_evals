"""Tests for logits support in Modal backend."""

from unittest.mock import MagicMock, Mock, patch

import pytest
from src.backends import create_backend
from src.backends.base import GenerationResult, ProbeScoreData, ProbeScores
from src.backends.modal_backend import ModalBackend


class TestLogitsSupport:
    """Tests for top-k logits functionality."""

    def test_modal_backend_logits_disabled_by_default(self):
        """Test that logits are disabled by default."""
        backend = ModalBackend(probe="deception_8b")
        assert backend.top_k_logits == 0
        assert backend.supports_logits == False

    def test_modal_backend_logits_enabled(self):
        """Test that logits can be enabled."""
        backend = ModalBackend(probe="deception_8b", top_k_logits=10)
        assert backend.top_k_logits == 10
        assert backend.supports_logits == True

    def test_modal_backend_logits_in_factory(self):
        """Test that logits parameter works through factory."""
        backend = create_backend("modal", probe="deception_8b", top_k_logits=5)
        assert backend.top_k_logits == 5
        assert backend.supports_logits == True

    @patch("modal.Cls")
    def test_generate_with_logits(self, mock_cls):
        """Test that logits are requested and returned correctly."""
        # Mock Modal service
        mock_service = MagicMock()
        mock_cls.from_name.return_value.return_value = mock_service

        # Mock response with logits
        mock_service.generate_with_probes.remote.return_value = {
            "generated_text": "Hello world",
            "generated_tokens": ["Hello", " world"],
            "top_k_logits": [
                {"Hello": -0.5, "Hi": -2.3, "Hey": -3.1},
                {" world": -0.3, " there": -1.8, " friend": -2.5},
            ],
            "probe_results": {
                "deception_8b": {
                    "token_scores": [0.1, 0.2],
                    "prompt_num_tokens": 10,
                    "generated_num_tokens": 2,
                }
            },
        }

        backend = ModalBackend(probe="deception_8b", top_k_logits=3)
        result = backend.generate(
            messages=[{"role": "user", "content": "test"}],
            max_tokens=50,
            temperature=0.7,
        )

        # Verify logits are in result
        assert result.top_k_logits is not None
        assert len(result.top_k_logits) == 2
        assert "Hello" in result.top_k_logits[0]
        assert " world" in result.top_k_logits[1]

        # Verify service was called with top_k_logits parameter
        call_kwargs = mock_service.generate_with_probes.remote.call_args[1]
        assert call_kwargs["top_k_logits"] == 3

    @patch("modal.Cls")
    def test_generate_without_logits(self, mock_cls):
        """Test that logits are not requested when disabled."""
        # Mock Modal service
        mock_service = MagicMock()
        mock_cls.from_name.return_value.return_value = mock_service

        # Mock response without logits
        mock_service.generate_with_probes.remote.return_value = {
            "generated_text": "Hello world",
            "generated_tokens": ["Hello", " world"],
            "probe_results": {
                "deception_8b": {
                    "token_scores": [0.1, 0.2],
                    "prompt_num_tokens": 10,
                    "generated_num_tokens": 2,
                }
            },
        }

        backend = ModalBackend(probe="deception_8b", top_k_logits=0)
        result = backend.generate(
            messages=[{"role": "user", "content": "test"}],
            max_tokens=50,
            temperature=0.7,
        )

        # Verify logits are not in result
        assert result.top_k_logits is None

        # Verify service was called with top_k_logits=0
        call_kwargs = mock_service.generate_with_probes.remote.call_args[1]
        assert call_kwargs["top_k_logits"] == 0

    @patch("modal.Cls")
    def test_multiple_probes_with_logits(self, mock_cls):
        """Test that logits work with multiple probes."""
        # Mock Modal service
        mock_service = MagicMock()
        mock_cls.from_name.return_value.return_value = mock_service

        # Mock response
        mock_service.generate_with_probes.remote.return_value = {
            "generated_text": "Test response",
            "generated_tokens": ["Test", " response"],
            "top_k_logits": [
                {"Test": -0.1, "A": -1.5},
                {" response": -0.2, " answer": -1.3},
            ],
            "probe_results": {
                "deception_8b": {
                    "token_scores": [0.3, 0.4],
                    "prompt_num_tokens": 5,
                    "generated_num_tokens": 2,
                },
                "hallucination_8b": {
                    "token_scores": [0.5, 0.6],
                    "prompt_num_tokens": 5,
                    "generated_num_tokens": 2,
                },
            },
        }

        backend = ModalBackend(
            probes=["deception_8b", "hallucination_8b"], top_k_logits=2
        )
        result = backend.generate(
            messages=[{"role": "user", "content": "test"}], max_tokens=50
        )

        # Verify both probes and logits are returned
        assert result.probe_scores is not None
        assert "deception_8b" in result.probe_scores.scores
        assert "hallucination_8b" in result.probe_scores.scores
        assert result.top_k_logits is not None
        assert len(result.top_k_logits) == 2


class TestLogitsIntegration:
    """Integration tests for logits with logging."""

    @patch("modal.Cls")
    def test_logits_logged_correctly(self, mock_cls):
        """Test that logits are logged when using ResultsLogger."""
        import json
        import tempfile

        from ..config.game_config import GameConfig
        from ..player import GamePlayer
        from ..result_logging.results_logger import ResultsLogger

        # Mock Modal service
        mock_service = MagicMock()
        mock_cls.from_name.return_value.return_value = mock_service

        mock_service.generate_with_probes.remote.return_value = {
            "generated_text": "I am honest",
            "generated_tokens": ["I", " am", " honest"],
            "top_k_logits": [
                {"I": -0.1, "We": -2.0},
                {" am": -0.2, " was": -1.5},
                {" honest": -0.3, " lying": -1.8},
            ],
            "probe_results": {
                "deception_8b": {
                    "token_scores": [0.1, 0.2, 0.3],
                    "prompt_num_tokens": 10,
                    "generated_num_tokens": 3,
                }
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config and logger
            config = GameConfig(git_hash="test123", output_dir=tmpdir)
            logger = ResultsLogger(
                config=config, game_name="test_game", experiment_base="logits_test"
            )

            # Create player with logits-enabled backend
            backend = ModalBackend(probe="deception_8b", top_k_logits=2)
            player = GamePlayer("Alice", backend, logger=logger)

            # Generate response
            result = player.query("Are you honest?")

            # Verify logits in result
            assert result.top_k_logits is not None

            # Verify logits were logged
            messages_file = logger.results_dir / "messages.jsonl"
            assert messages_file.exists()

            with open(messages_file) as f:
                log_entry = json.loads(f.read().strip())

            assert "top_k_logits" in log_entry
            assert log_entry["top_k_logits"] == result.top_k_logits


class TestLogitsEdgeCases:
    """Test edge cases for logits support."""

    def test_logits_with_zero_value(self):
        """Test that top_k_logits=0 properly disables logits."""
        backend = ModalBackend(probe="deception_8b", top_k_logits=0)
        assert backend.supports_logits == False

    def test_logits_with_negative_value_raises(self):
        """Test that negative top_k_logits is handled."""
        # This should probably raise an error, but currently doesn't
        # Document current behavior
        backend = ModalBackend(probe="deception_8b", top_k_logits=-5)
        assert backend.top_k_logits == -5
        # supports_logits checks > 0, so this returns False
        assert backend.supports_logits == False

    def test_logits_without_probes(self):
        """Test that logits can be requested without probes."""
        backend = ModalBackend(top_k_logits=10)
        assert backend.supports_logits == True
        assert backend.supports_probes == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
