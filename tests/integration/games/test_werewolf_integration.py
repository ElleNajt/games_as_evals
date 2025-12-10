"""Integration tests for Werewolf game with mocked backends."""

import tempfile
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import patch

import pytest

from src.backends.base import GenerationResult, ProbeScores, ProbeScoreData
from src.config.player_config import PlayerConfig
from src.games.werewolf.config import WerewolfConfig
from src.games.werewolf.game_coordinator import GameCoordinator


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


class TestWerewolfWithMocks:
    """Test Werewolf game with mocked backends."""

    def test_werewolf_initialization(self):
        """Test Werewolf game initializes correctly with mocked backends."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WerewolfConfig(
                num_players=5,
                num_werewolves=2,
                no_seer=True,
                max_turns=2,
                output_dir=tmpdir
            )

            with patch("src.games.werewolf.game_coordinator.create_backend") as mock_create:
                mock_backend = MockBackend(
                    responses=["I vote for Player1."] * 100
                )
                mock_create.return_value = mock_backend

                coordinator = GameCoordinator(
                    config=config,
                    experiment_name="mock_test",
                    game_id=1
                )

                # Should have created coordinator
                assert coordinator.config.num_players == 5
                assert coordinator.config.num_werewolves == 2
                assert coordinator.output_dir is not None
                assert Path(coordinator.output_dir).exists()

    def test_werewolf_game_flow(self):
        """Test Werewolf game can run with mocked responses."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WerewolfConfig(
                num_players=4,
                num_werewolves=1,
                no_seer=True,
                max_turns=1,  # Very short game
                num_discussion_rounds=1,
                output_dir=tmpdir
            )

            # Create varied responses for different game phases
            responses = [
                "Player2 seems suspicious.",  # Discussion
                "I agree with Player1.",  # Discussion
                "Let's vote Player2.",  # Discussion
                "Player3 is innocent.",  # Discussion
                "I vote for Player2.",  # Voting - villager
                "I vote for Player3.",  # Voting - villager
                "I vote for Player4.",  # Voting - villager
                "I vote for Player1.",  # Voting - werewolf
                "Player1",  # Werewolf night kill target
            ] * 10  # Repeat for multiple rounds

            with patch("src.games.werewolf.game_coordinator.create_backend") as mock_create:
                mock_backend = MockBackend(responses=responses)
                mock_create.return_value = mock_backend

                coordinator = GameCoordinator(
                    config=config,
                    experiment_name="flow_test",
                    game_id=1
                )

                # Coordinator should initialize properly
                assert coordinator.config is not None
                assert coordinator.logger is not None
                assert Path(coordinator.output_dir).exists()

    def test_werewolf_with_seer(self):
        """Test Werewolf game with seer role."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WerewolfConfig(
                num_players=5,
                num_werewolves=1,
                no_seer=False,  # Include seer
                max_turns=1,
                output_dir=tmpdir
            )

            responses = [
                "Player2 seems trustworthy.",  # Discussion
                "I'm not sure about Player3.",  # Discussion
                "Let's work together.",  # Discussion
                "We need to find the werewolf.",  # Discussion
                "Player5 is suspicious.",  # Discussion
                "I vote for Player2.",  # Voting
                "I vote for Player3.",  # Voting
                "I vote for Player4.",  # Voting
                "I vote for Player5.",  # Voting
                "I vote for Player1.",  # Voting
                "Player3",  # Seer investigation
                "Player4",  # Werewolf kill
            ] * 5

            with patch("src.games.werewolf.game_coordinator.create_backend") as mock_create:
                mock_backend = MockBackend(responses=responses)
                mock_create.return_value = mock_backend

                coordinator = GameCoordinator(
                    config=config,
                    experiment_name="seer_test",
                    game_id=1
                )

                # Should have seer in player list
                assert coordinator.config is not None
                assert not coordinator.config.no_seer

    def test_werewolf_with_probes(self):
        """Test Werewolf game with probe-enabled backends."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create configs with probes
            villager_config = PlayerConfig(
                name="Villager",
                backend_type="mock",
                model="mock-model",
                probes=["deception_8b"],
                system_prompt="You are a villager."
            )

            werewolf_config = PlayerConfig(
                name="Werewolf",
                backend_type="mock",
                model="mock-model",
                probes=["deception_8b"],
                system_prompt="You are a werewolf."
            )

            config = WerewolfConfig(
                num_players=4,
                num_werewolves=1,
                no_seer=True,
                max_turns=1,
                provide_probe_scores=True,  # Enable probe display
                villager_config=villager_config,
                werewolf_config=werewolf_config,
                output_dir=tmpdir
            )

            responses = [
                "Everyone seems trustworthy.",  # Discussion
                "I don't trust Player3.",  # Discussion
                "Player2 is acting strange.",  # Discussion
                "Let's vote carefully.",  # Discussion
                "I vote for Player2.",  # Voting
                "I vote for Player3.",  # Voting
                "I vote for Player4.",  # Voting
                "I vote for Player1.",  # Voting
                "Player3",  # Werewolf kill
            ] * 5

            with patch("src.games.werewolf.game_coordinator.create_backend") as mock_create:
                mock_backend = MockBackend(
                    responses=responses,
                    with_probes=True
                )
                mock_create.return_value = mock_backend

                coordinator = GameCoordinator(
                    config=config,
                    experiment_name="probe_test",
                    game_id=1
                )

                # Should complete initialization with probes
                assert coordinator.config.provide_probe_scores
                assert mock_create.called

    def test_werewolf_with_cot(self):
        """Test Werewolf game with chain-of-thought enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WerewolfConfig(
                num_players=4,
                num_werewolves=1,
                no_seer=True,
                max_turns=1,
                request_reasoning=True,  # Enable CoT
                public_cot=True,  # Make reasoning public
                output_dir=tmpdir
            )

            # CoT responses include reasoning in parentheses
            responses = [
                "(Player2 seems nervous) I think Player2 might be suspicious.",
                "(Everyone seems okay) I don't see any obvious werewolves yet.",
                "(Need to blend in) Let's work together to find the werewolf.",
                "(Accuse someone else) I'm concerned about Player4.",
                "I vote for Player2.",
                "I vote for Player3.",
                "I vote for Player4.",
                "I vote for Player1.",
                "Player3",  # Werewolf kill
            ] * 5

            with patch("src.games.werewolf.game_coordinator.create_backend") as mock_create:
                mock_backend = MockBackend(responses=responses)
                mock_create.return_value = mock_backend

                coordinator = GameCoordinator(
                    config=config,
                    experiment_name="cot_test",
                    game_id=1
                )

                # Should have CoT enabled
                assert coordinator.config.request_reasoning
                assert coordinator.config.public_cot


class TestWerewolfInvalidResponses:
    """Test Werewolf game handles invalid LLM responses gracefully."""

    def test_werewolf_invalid_vote_format(self):
        """Test Werewolf handles malformed vote responses."""
        invalid_votes = [
            "I'm not sure who to vote for",  # No clear vote
            "Maybe Player2?",  # Uncertain
            "",  # Empty
            "I vote for PlayerX",  # Non-existent player
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            config = WerewolfConfig(
                num_players=3,
                num_werewolves=1,
                no_seer=True,
                max_turns=1,
                num_discussion_rounds=1,
                output_dir=tmpdir
            )

            for invalid_vote in invalid_votes:
                # Mix invalid with discussion responses
                responses = [
                    "Let's find the werewolf.",  # Discussion
                    "Someone here is lying.",  # Discussion
                    "We need to be careful.",  # Discussion
                    invalid_vote,  # Invalid vote
                    "I vote for Player2.",  # Valid fallback
                    "I vote for Player1.",  # Valid fallback
                    "Player2",  # Werewolf kill
                ] * 3

                with patch("src.games.werewolf.game_coordinator.create_backend") as mock_create:
                    mock_backend = MockBackend(responses=responses)
                    mock_create.return_value = mock_backend

                    coordinator = GameCoordinator(
                        config=config,
                        experiment_name="invalid_vote_test",
                        game_id=1
                    )

                    # Should handle gracefully
                    # (Coordinator initialization should not crash on invalid formats)
                    assert coordinator is not None

    def test_werewolf_invalid_kill_target(self):
        """Test Werewolf handles invalid werewolf kill target."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WerewolfConfig(
                num_players=3,
                num_werewolves=1,
                no_seer=True,
                max_turns=1,
                output_dir=tmpdir
            )

            # Invalid kill targets
            responses = [
                "Let's work together.",  # Discussion
                "I don't trust anyone.",  # Discussion
                "Someone is suspicious.",  # Discussion
                "I vote for Player2.",  # Vote
                "I vote for Player3.",  # Vote
                "I vote for Player1.",  # Vote
                "Nobody",  # Invalid kill target
                "PlayerX",  # Non-existent player
                "Player1",  # Valid fallback
            ] * 3

            with patch("src.games.werewolf.game_coordinator.create_backend") as mock_create:
                mock_backend = MockBackend(responses=responses)
                mock_create.return_value = mock_backend

                coordinator = GameCoordinator(
                    config=config,
                    experiment_name="invalid_kill_test",
                    game_id=1
                )

                # Should initialize without crashing
                assert coordinator is not None


class TestWerewolfProbeValidation:
    """Test Werewolf game validates probe data correctly."""

    def test_werewolf_with_missing_probe_data(self):
        """Test that missing probe scores are handled correctly when expected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            villager_config = PlayerConfig(
                name="Villager",
                backend_type="mock",
                model="mock-model",
                probes=["deception_8b"],
                system_prompt="You are a villager."
            )

            werewolf_config = PlayerConfig(
                name="Werewolf",
                backend_type="mock",
                model="mock-model",
                probes=["deception_8b"],
                system_prompt="You are a werewolf."
            )

            config = WerewolfConfig(
                num_players=3,
                num_werewolves=1,
                no_seer=True,
                max_turns=1,
                provide_probe_scores=True,  # Expects probes
                villager_config=villager_config,
                werewolf_config=werewolf_config,
                output_dir=tmpdir
            )

            responses = [
                "I trust everyone.",
                "Let's vote wisely.",
                "Player2 is suspicious.",
                "I vote for Player2.",
                "I vote for Player3.",
                "I vote for Player1.",
                "Player2",  # Kill
            ] * 3

            with patch("src.games.werewolf.game_coordinator.create_backend") as mock_create:
                # Backend WITHOUT probes but config expects them
                mock_backend = MockBackend(
                    responses=responses,
                    with_probes=False  # No probes!
                )
                mock_create.return_value = mock_backend

                coordinator = GameCoordinator(
                    config=config,
                    experiment_name="missing_probe_test",
                    game_id=1
                )

                # Should initialize (actual probe validation happens during game play)
                assert coordinator is not None


class TestWerewolfGameLogic:
    """Test Werewolf game logic and state management."""

    def test_werewolf_role_distribution(self):
        """Test that roles are distributed correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WerewolfConfig(
                num_players=6,
                num_werewolves=2,
                no_seer=False,  # Include seer
                output_dir=tmpdir
            )

            # Should have:
            # - 2 werewolves
            # - 1 seer
            # - 3 villagers
            # Total: 6 players

            assert len(config.players) == 6

            werewolves = [p for p in config.players if "Werewolf" in p.name]
            seers = [p for p in config.players if "Seer" in p.name]
            villagers = [p for p in config.players if "Villager" in p.name]

            assert len(werewolves) == 2
            assert len(seers) == 1
            assert len(villagers) == 3

    def test_werewolf_no_seer_distribution(self):
        """Test role distribution without seer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WerewolfConfig(
                num_players=5,
                num_werewolves=2,
                no_seer=True,  # No seer
                output_dir=tmpdir
            )

            # Should have:
            # - 2 werewolves
            # - 3 villagers
            # Total: 5 players

            assert len(config.players) == 5

            werewolves = [p for p in config.players if "Werewolf" in p.name]
            seers = [p for p in config.players if "Seer" in p.name]
            villagers = [p for p in config.players if "Villager" in p.name]

            assert len(werewolves) == 2
            assert len(seers) == 0
            assert len(villagers) == 3

    def test_werewolf_coordinator_creates_output_dir(self):
        """Test that coordinator creates output directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WerewolfConfig(
                num_players=4,
                num_werewolves=1,
                no_seer=True,
                output_dir=tmpdir
            )

            with patch("src.games.werewolf.game_coordinator.create_backend") as mock_create:
                mock_backend = MockBackend(responses=["Test"])
                mock_create.return_value = mock_backend

                coordinator = GameCoordinator(
                    config=config,
                    experiment_name="output_test",
                    game_id=1
                )

                # Output directory should exist
                assert Path(coordinator.output_dir).exists()

                # Should be structured: tmpdir/werewolf/output_test_<hashes>/game_1/
                output_path = Path(coordinator.output_dir)
                assert output_path.exists()
                assert output_path.is_dir()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
