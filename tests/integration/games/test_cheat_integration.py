"""Integration tests for Cheat/BS game with mocked backends."""

import tempfile
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import patch

import pytest

from src.backends.base import GenerationResult, ProbeScores, ProbeScoreData
from src.config.player_config import PlayerConfig
from src.games.cheat.config import CheatConfig
from src.games.cheat.orchestrator import CheatOrchestrator


class MockBackend:
    """Mock backend that returns predefined responses."""

    def __init__(
        self,
        responses: Optional[List[str]] = None,
        with_probes: bool = False,
        with_logits: bool = False
    ):
        self.responses = responses or ["Mock response."]
        self.call_count = 0
        self._with_probes = with_probes
        self._with_logits = with_logits

    @property
    def supports_probes(self) -> bool:
        return self._with_probes

    @property
    def supports_logits(self) -> bool:
        return self._with_logits

    def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> GenerationResult:
        """Return mock response."""
        response_text = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1

        tokens = response_text.split() if self._with_probes or self._with_logits else None

        probe_scores = None
        if self._with_probes:
            probe_scores = ProbeScores(
                scores={
                    "deception_8b": ProbeScoreData(
                        aggregate_score=0.5,
                        token_scores=[0.5] * len(tokens) if tokens else [],
                        metadata={"num_tokens": len(tokens) if tokens else 0, "probe_type": "deception"}
                    )
                }
            )

        top_k_logits = None
        if self._with_logits and tokens:
            top_k_logits = [
                {token: -1.0, "alt1": -2.0, "alt2": -3.0}
                for token in tokens
            ]

        return GenerationResult(
            text=response_text,
            tokens=tokens,
            top_k_logits=top_k_logits,
            probe_scores=probe_scores
        )


class TestCheatWithMocks:
    """Test Cheat game with mocked backends."""

    def test_cheat_basic_setup(self):
        """Test Cheat game initializes correctly with mocked backends."""
        with tempfile.TemporaryDirectory() as tmpdir:
            player_template = PlayerConfig(
                name="template",
                backend_type="mock",
                model="mock-model",
                system_prompt="You are playing Cheat."
            )

            config = CheatConfig(
                num_players=3,
                num_decks=1,
                max_turns=10,
                player_template=player_template,
                output_dir=tmpdir
            )

            with patch("src.games.cheat.orchestrator.create_backend") as mock_create:
                mock_backend = MockBackend(
                    responses=["ACTUAL_CARDS: Two\nCLAIM: Two"] * 100
                )
                mock_create.return_value = mock_backend

                orchestrator = CheatOrchestrator(
                    config=config,
                    experiment_name="mock_test",
                    game_id=1
                )
                orchestrator.setup_game()

                # Verify setup
                assert len(orchestrator.players) == 3
                assert orchestrator.state is not None
                assert len(orchestrator.state.players) == 3
                assert orchestrator.logger is not None

    def test_cheat_game_completes(self):
        """Test Cheat game can complete with mocked responses."""
        with tempfile.TemporaryDirectory() as tmpdir:
            player_template = PlayerConfig(
                name="template",
                backend_type="mock",
                model="mock-model",
                system_prompt="You are playing Cheat."
            )

            config = CheatConfig(
                num_players=3,
                num_decks=1,
                max_turns=10,  # Short game for testing
                player_template=player_template,
                output_dir=tmpdir
            )

            # Create varied responses for realistic play
            play_responses = [
                "ACTUAL_CARDS: Two\nCLAIM: Two",  # Honest play
                "ACTUAL_CARDS: King\nCLAIM: Three",  # Lie
                "ACTUAL_CARDS: Ace\nCLAIM: Ace",  # Honest
            ]

            challenge_responses = ["PASS"] * 20  # Don't challenge for now

            # Interleave play and challenge responses
            all_responses = []
            for _ in range(50):
                all_responses.append(play_responses[_ % len(play_responses)])
                all_responses.extend(challenge_responses[:2])  # Each play followed by potential challenges

            with patch("src.games.cheat.orchestrator.create_backend") as mock_create:
                mock_backend = MockBackend(responses=all_responses)
                mock_create.return_value = mock_backend

                orchestrator = CheatOrchestrator(
                    config=config,
                    experiment_name="completion_test",
                    game_id=1
                )

                results = orchestrator.run_game()

                # Verify game completed
                assert results is not None
                assert "winner" in results or "reason" in results
                assert "total_turns" in results
                assert "final_hands" in results
                assert mock_backend.call_count > 0

    def test_cheat_with_probes(self):
        """Test Cheat game with probe-enabled mocked backends."""
        with tempfile.TemporaryDirectory() as tmpdir:
            player_template = PlayerConfig(
                name="template",
                backend_type="mock",
                model="mock-model",
                probes=["deception_8b"],
                system_prompt="You are playing Cheat."
            )

            config = CheatConfig(
                num_players=3,
                num_decks=1,
                max_turns=5,
                player_template=player_template,
                provide_probe_scores=True,  # Enable probe display
                output_dir=tmpdir
            )

            play_responses = [
                "ACTUAL_CARDS: King\nCLAIM: Two",  # Lie - should have high probe score
            ]
            challenge_responses = ["PASS"] * 10

            all_responses = []
            for _ in range(20):
                all_responses.append(play_responses[0])
                all_responses.extend(challenge_responses[:2])

            with patch("src.games.cheat.orchestrator.create_backend") as mock_create:
                mock_backend = MockBackend(
                    responses=all_responses,
                    with_probes=True
                )
                mock_create.return_value = mock_backend

                orchestrator = CheatOrchestrator(
                    config=config,
                    experiment_name="probe_test",
                    game_id=1
                )

                results = orchestrator.run_game()

                # Should complete successfully with probes
                assert results is not None
                assert mock_backend.call_count > 0

    def test_cheat_challenge_flow(self):
        """Test Cheat game handles challenges correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            player_template = PlayerConfig(
                name="template",
                backend_type="mock",
                model="mock-model",
                system_prompt="You are playing Cheat."
            )

            config = CheatConfig(
                num_players=3,
                num_decks=1,
                max_turns=20,
                player_template=player_template,
                output_dir=tmpdir
            )

            # Mix of plays and challenges
            responses = [
                "ACTUAL_CARDS: King\nCLAIM: Two",  # Lie
                "CHALLENGE",  # Challenge the lie
                "PASS",  # Other player passes
                "ACTUAL_CARDS: Two\nCLAIM: Two",  # Honest play
                "PASS",  # No challenge
                "PASS",
            ] * 10

            with patch("src.games.cheat.orchestrator.create_backend") as mock_create:
                mock_backend = MockBackend(responses=responses)
                mock_create.return_value = mock_backend

                orchestrator = CheatOrchestrator(
                    config=config,
                    experiment_name="challenge_test",
                    game_id=1
                )

                results = orchestrator.run_game()

                # Game should handle challenges without crashing
                assert results is not None
                assert "total_turns" in results


class TestCheatInvalidResponses:
    """Test Cheat game handles invalid LLM responses gracefully."""

    def test_cheat_invalid_play_format(self):
        """Test Cheat handles malformed play responses."""
        invalid_plays = [
            "I'll play some cards",  # No structure
            "ACTUAL_CARDS:",  # Missing cards
            "CLAIM: Two",  # Missing actual cards
            "",  # Empty
            "Just playing randomly",  # Wrong format
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            player_template = PlayerConfig(
                name="template",
                backend_type="mock",
                model="mock-model",
                system_prompt="You are playing Cheat."
            )

            config = CheatConfig(
                num_players=2,
                num_decks=1,
                max_turns=3,
                player_template=player_template,
                output_dir=tmpdir
            )

            for invalid_play in invalid_plays:
                # Mix invalid with valid challenge responses
                responses = [invalid_play, "PASS", "PASS"] * 5

                with patch("src.games.cheat.orchestrator.create_backend") as mock_create:
                    mock_backend = MockBackend(responses=responses)
                    mock_create.return_value = mock_backend

                    orchestrator = CheatOrchestrator(
                        config=config,
                        experiment_name="invalid_test",
                        game_id=1
                    )

                    # Should handle gracefully (fallback to valid play)
                    try:
                        results = orchestrator.run_game()
                        assert results is not None
                    except Exception as e:
                        # If it raises, should be clear error
                        assert "parse" in str(e).lower() or "format" in str(e).lower()

    def test_cheat_missing_probe_scores(self):
        """Test Cheat crashes loudly when probe scores are missing but expected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            player_template = PlayerConfig(
                name="template",
                backend_type="mock",
                model="mock-model",
                probes=["deception_8b"],
                system_prompt="You are playing Cheat."
            )

            config = CheatConfig(
                num_players=2,
                num_decks=1,
                max_turns=2,
                player_template=player_template,
                provide_probe_scores=True,  # Expects probe scores
                output_dir=tmpdir
            )

            responses = [
                "ACTUAL_CARDS: King\nCLAIM: Two",
                "PASS",
                "PASS"
            ] * 5

            with patch("src.games.cheat.orchestrator.create_backend") as mock_create:
                # Backend WITHOUT probes but config expects them
                mock_backend = MockBackend(
                    responses=responses,
                    with_probes=False  # No probes!
                )
                mock_create.return_value = mock_backend

                orchestrator = CheatOrchestrator(
                    config=config,
                    experiment_name="missing_probe_test",
                    game_id=1
                )

                # Should crash with ValueError about missing probe scores
                with pytest.raises(ValueError, match="probe_scores are missing"):
                    orchestrator.run_game()


class TestCheatProbeValidation:
    """Test Cheat game validates probe scores correctly."""

    def test_cheat_validates_probe_presence(self):
        """Test that missing deception_8b probe raises clear error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            player_template = PlayerConfig(
                name="template",
                backend_type="mock",
                model="mock-model",
                probes=["wrong_probe"],  # Wrong probe name
                system_prompt="You are playing Cheat."
            )

            config = CheatConfig(
                num_players=2,
                num_decks=1,
                max_turns=2,
                player_template=player_template,
                provide_probe_scores=True,
                output_dir=tmpdir
            )

            responses = ["ACTUAL_CARDS: Two\nCLAIM: Two", "PASS", "PASS"] * 3

            with patch("src.games.cheat.orchestrator.create_backend") as mock_create:
                # Mock backend with wrong probe name
                class WrongProbeBackend(MockBackend):
                    def generate(self, messages, max_tokens=512, temperature=0.7):
                        result = super().generate(messages, max_tokens, temperature)
                        # Replace probe with wrong name
                        if result.probe_scores:
                            # Get the original probe data and rename it
                            original_data = result.probe_scores.scores["deception_8b"]
                            result.probe_scores = ProbeScores(
                                scores={"wrong_probe": original_data}
                            )
                        return result

                mock_backend = WrongProbeBackend(
                    responses=responses,
                    with_probes=True
                )
                mock_create.return_value = mock_backend

                orchestrator = CheatOrchestrator(
                    config=config,
                    experiment_name="wrong_probe_test",
                    game_id=1
                )

                # Should crash with ValueError about missing deception_8b
                with pytest.raises(ValueError, match="deception_8b"):
                    orchestrator.run_game()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
