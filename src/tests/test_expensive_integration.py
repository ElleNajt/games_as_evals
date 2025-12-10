"""
Expensive integration tests that hit real Modal deployments.

These tests are marked as 'expensive' and skipped by default.
Run with: pytest -m expensive
Or run all tests: pytest -m "expensive or not expensive"

Requirements:
- Modal authenticated (modal setup)
- unified-probe-service deployed with probes
- unified-probe-service-70b deployed (for 70B tests)
"""

import pytest

from src.backends import create_backend
from src.config.experiment_config import get_experiment_config
from src.experiments.ttl.configs import create_ttl_config
from src.experiments.werewolf.configs import create_werewolf_config
from src.games.ttl import TTLConfig
from src.games.ttl.orchestrator_unified import run_game_round

# Mark all tests in this module as expensive
pytestmark = pytest.mark.expensive


class TestBackendIntegration8B:
    """Test 8B backend with various probe configurations."""

    def test_8b_single_probe_deception(self):
        """Test 8B model with single deception probe."""
        backend = create_backend("modal", probes=["deception_8b"], top_k_logits=10)

        result = backend.generate(
            messages=[{"role": "user", "content": "Tell me a convincing lie."}],
            max_tokens=20,
            temperature=0.7,
        )

        # Verify structure
        assert result.text is not None
        assert result.tokens is not None
        assert result.probe_scores is not None
        assert result.top_k_logits is not None

        # Verify probe scores - access via dict-like interface
        assert "deception_8b" in result.probe_scores
        probe_data = result.probe_scores["deception_8b"]
        assert 0 <= probe_data.aggregate_score <= 1
        assert len(probe_data.token_scores) == len(result.tokens)

        # Verify logits
        assert len(result.top_k_logits) == len(result.tokens)

        print(f"\n✓ Deception score: {probe_data.aggregate_score:.3f}")
        print(f"✓ Generated {len(result.tokens)} tokens")

    def test_8b_single_probe_hallucination(self):
        """Test 8B model with single hallucination probe."""
        backend = create_backend("modal", probes=["hallucination_8b"], top_k_logits=10)

        result = backend.generate(
            messages=[{"role": "user", "content": "Make up a false historical fact."}],
            max_tokens=20,
            temperature=0.7,
        )

        # Verify structure
        assert result.text is not None
        assert result.tokens is not None
        assert result.probe_scores is not None

        # Verify probe scores
        assert "hallucination_8b" in result.probe_scores
        probe_data = result.probe_scores["hallucination_8b"]
        assert 0 <= probe_data.aggregate_score <= 1
        assert len(probe_data.token_scores) == len(result.tokens)

        print(f"\n✓ Hallucination score: {probe_data.aggregate_score:.3f}")

    def test_8b_both_probes(self):
        """Test 8B model with both deception and hallucination probes."""
        backend = create_backend(
            "modal", probes=["deception_8b", "hallucination_8b"], top_k_logits=10
        )

        result = backend.generate(
            messages=[{"role": "user", "content": "Make up a convincing story."}],
            max_tokens=30,
            temperature=0.7,
        )

        # Verify both probes present - access via .scores.items()
        assert "deception_8b" in result.probe_scores.scores
        assert "hallucination_8b" in result.probe_scores.scores

        deception = result.probe_scores.scores["deception_8b"]
        hallucination = result.probe_scores.scores["hallucination_8b"]

        assert 0 <= deception.aggregate_score <= 1
        assert 0 <= hallucination.aggregate_score <= 1

        print(f"\n✓ Deception: {deception.aggregate_score:.3f}")
        print(f"✓ Hallucination: {hallucination.aggregate_score:.3f}")


class TestTTLGame8B:
    """Test TTL game with 8B model and various probe configurations."""

    def test_ttl_8b_both_probes(self):
        """Run 1 round of TTL with 8B and both deception + hallucination probes."""
        exp_config = get_experiment_config("8b_both")
        config = create_ttl_config(exp_config, use_real_world_facts=True)

        # Verify config - should have both probes
        assert config.deceiver_config.probes == ["deception_8b", "hallucination_8b"]
        assert config.auditor_config.probes == ["deception_8b", "hallucination_8b"]

        # Run one round
        results = run_game_round(
            config=config,
            facts=None,
            experiment_name="test_ttl_8b_both",
            round_id=1,
        )

        # Verify results structure
        assert "statements" in results
        assert "revealed_lie" in results
        assert "auditor_guesses" in results
        assert len(results["statements"]) == 3
        assert 1 <= results["revealed_lie"] <= 3

        print(f"\n✓ Generated statements: {results['statements']}")
        print(f"✓ Lie was at position: {results['revealed_lie']}")
        print(f"✓ Auditor guesses: {results['auditor_guesses']}")

    def test_ttl_8b_both_probes(self):
        """Run 1 round of TTL with 8B and both probes."""
        exp_config = get_experiment_config("8b_both")
        config = create_ttl_config(exp_config, use_real_world_facts=True)

        # Verify config
        assert set(config.deceiver_config.probes) == {
            "deception_8b",
            "hallucination_8b",
        }
        assert set(config.auditor_config.probes) == {"deception_8b", "hallucination_8b"}

        # Run one round
        results = run_game_round(
            config=config, facts=None, experiment_name="test_ttl_8b_both", round_id=1
        )

        # Verify results
        assert "statements" in results
        assert "revealed_lie" in results
        assert "auditor_guesses" in results
        assert len(results["statements"]) == 3

        print(f"\n✓ TTL with both probes completed successfully")
        print(f"✓ Auditor correct: {results.get('auditor_correct', False)}")


class TestWerewolfGame8B:
    """Test Werewolf game with 8B model and probes."""

    def test_werewolf_8b_both_probes(self):
        """Run 1 day/night cycle of Werewolf with 8B and both probes."""
        from src.games.werewolf import GameCoordinator, WerewolfConfig

        exp_config = get_experiment_config("8b_both")

        # Create Werewolf config with both probes
        config = create_werewolf_config(
            exp_config,
            num_players=5,
            num_werewolves=2,
            no_seer=True,  # Disable seer for faster test
            max_turns=1,  # Just one day/night cycle
        )

        # Verify config
        assert config.num_players == 5
        assert config.num_werewolves == 2
        assert config.villager_config.probes == ["deception_8b", "hallucination_8b"]
        assert config.werewolf_config.probes == ["deception_8b", "hallucination_8b"]

        # Run the game
        coordinator = GameCoordinator(
            config=config, experiment_name="test_werewolf_8b_both", game_id=1
        )
        winner = coordinator.run_game()

        # Verify results - run_game returns winner string
        assert winner in ["Villagers", "Werewolves"]
        assert coordinator.game.turn_number >= 1

        print(f"\n✓ Werewolf game completed")
        print(f"✓ Winner: {winner}")
        print(f"✓ Rounds played: {coordinator.game.turn_number}")


@pytest.mark.skip(
    reason="70B requires 4x H100 GPUs - only run when 70B service is deployed"
)
class TestBackendIntegration70B:
    """
    Test 70B backend with various probe configurations.

    NOTE: These tests require unified-probe-service-70b to be deployed:
    - modal deploy src/modal_deployments/unified_probe_service_70b.py
    - 4x H100 GPUs required
    - Expensive to run
    """

    def test_70b_single_probe_deception(self):
        """Test 70B model with deception probe."""
        backend = create_backend("modal", probes=["deception_70b"], top_k_logits=10)

        result = backend.generate(
            messages=[{"role": "user", "content": "Tell me a deceptive statement."}],
            max_tokens=20,
            temperature=0.7,
        )

        assert "deception_70b" in result.probe_scores
        probe_data = result.probe_scores["deception_70b"]
        assert 0 <= probe_data.aggregate_score <= 1

        print(f"\n✓ 70B Deception score: {probe_data.aggregate_score:.3f}")

    def test_70b_both_probes(self):
        """Test 70B model with both probes."""
        exp_config = get_experiment_config("70b_both")

        backend = create_backend(
            "modal", probes=exp_config.probes, top_k_logits=exp_config.top_k_logits
        )

        result = backend.generate(
            messages=[{"role": "user", "content": "Create a fictional scenario."}],
            max_tokens=30,
            temperature=0.7,
        )

        assert "deception_70b" in result.probe_scores.scores
        assert "hallucination_70b" in result.probe_scores.scores

        deception = result.probe_scores.scores["deception_70b"]
        hallucination = result.probe_scores.scores["hallucination_70b"]

        print(f"\n✓ 70B Deception: {deception.aggregate_score:.3f}")
        print(f"✓ 70B Hallucination: {hallucination.aggregate_score:.3f}")


class TestTTLGame70B:
    """Test TTL game with 70B model."""

    def test_ttl_70b_both_probes(self):
        """Run 1 round of TTL with 70B and both probes."""
        exp_config = get_experiment_config("70b_both")
        config = create_ttl_config(exp_config, use_real_world_facts=True)

        # Verify config
        assert set(config.deceiver_config.probes) == {
            "deception_70b",
            "hallucination_70b",
        }
        assert set(config.auditor_config.probes) == {
            "deception_70b",
            "hallucination_70b",
        }

        # Run one round
        results = run_game_round(
            config=config, facts=None, experiment_name="test_ttl_70b_both", round_id=1
        )

        # Verify results structure
        assert "statements" in results
        assert "revealed_lie" in results
        assert "auditor_guesses" in results
        assert len(results["statements"]) == 3
        assert 1 <= results["revealed_lie"] <= 3

        print(f"\n✓ 70B TTL with both probes completed")
        print(f"✓ Statements: {results['statements']}")
        print(f"✓ Revealed lie: {results['revealed_lie']}")
        print(f"✓ Auditor guesses: {results['auditor_guesses']}")


if __name__ == "__main__":
    # For manual testing
    print("Running expensive integration tests...")
    print("These require Modal deployment with probes!")
    print("\nTo run 8B tests only:")
    print("  pytest src/tests/test_expensive_integration.py -m expensive -k '8B' -v -s")
    print("\nTo run ALL expensive tests (including 70B):")
    print(
        "  pytest src/tests/test_expensive_integration.py -m expensive --run-all -v -s"
    )
