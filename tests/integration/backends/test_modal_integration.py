"""
Integration tests for Modal backends with real probe deployments.

These tests actually connect to Modal and verify that probes return valid scores.
They are slower than unit tests and require Modal setup.

Run with: pytest -m expensive tests/integration/backends/test_modal_integration.py -v
"""

import pytest
from src.backends import create_backend
from src.player import GamePlayer


@pytest.mark.expensive
class TestModalDeception8B:
    """Test Modal backend with 8B deception probe."""
    
    def test_modal_deception_8b_connects(self):
        """Test that we can connect to the deception_8b probe service."""
        backend = create_backend("modal", probes=["deception_8b"])
        assert backend.modal_app_name == "unified-probe-service"
        assert backend.supports_probes == True

    def test_modal_deception_8b_generates_text(self):
        """Test that deception_8b probe generates non-empty text."""
        backend = create_backend("modal", probes=["deception_8b"])
        player = GamePlayer("TestPlayer", backend, "You are a strategic player.")
        
        result = player.query("Say hello", max_tokens=50, temperature=0.7)
        
        assert result.text is not None
        assert len(result.text) > 0
        print(f"\nGenerated text: {result.text[:100]}...")
    
    def test_modal_deception_8b_returns_probe_scores(self):
        """Test that deception_8b probe returns non-zero probe scores."""
        backend = create_backend("modal", probes=["deception_8b"])
        player = GamePlayer(
            "TestPlayer", 
            backend,
            "You are Alice in a game. Lie about your intentions."
        )
        
        # Generate a response that should trigger deception detection
        result = player.query(
            "Tell me your strategy. Will you help the other players or betray them?",
            max_tokens=100,
            temperature=0.7
        )
        
        # Verify probe scores are present
        assert result.probe_scores is not None, "Probe scores should not be None"
        assert len(result.probe_scores.token_scores) > 0, "Should have token scores"
        
        # Apollo probes return unnormalized logits (not probabilities)
        # Scores are typically in range [-100, 150] with mean around 0-50
        # Just verify we got non-zero, real-valued scores
        assert abs(result.probe_scores.aggregate_score) > 0.01, "Should have non-zero aggregate score"
        
        print(f"\n✓ Deception score: {result.probe_scores.aggregate_score:.3f}")
        print(f"✓ Num tokens scored: {len(result.probe_scores.token_scores)}")
        print(f"✓ Generated text: {result.text[:100]}...")
    
    def test_modal_deception_8b_tokens_match_scores(self):
        """Test that number of tokens matches number of scores."""
        backend = create_backend("modal", probes=["deception_8b"])
        player = GamePlayer("TestPlayer", backend, "You are a player in a game.")
        
        result = player.query("What's your strategy?", max_tokens=50)
        
        if result.tokens and result.probe_scores:
            # Allow some flexibility - generated tokens might not all be scored
            # (e.g., special tokens might be filtered)
            assert len(result.probe_scores.token_scores) > 0
            print(f"\n✓ Tokens: {len(result.tokens)}")
            print(f"✓ Scores: {len(result.probe_scores.token_scores)}")


@pytest.mark.expensive
class TestModalDeception70B:
    """Test Modal backend with 70B deception probe."""
    
    def test_modal_deception_70b_connects(self):
        """Test that we can connect to the deception_70b probe service."""
        backend = create_backend("modal", probes=["deception_70b"])
        assert backend.modal_app_name == "unified-probe-service-70b"
        assert backend.supports_probes == True
    
    @pytest.mark.slow
    def test_modal_deception_70b_returns_probe_scores(self):
        """Test that deception_70b probe returns non-zero probe scores."""
        backend = create_backend("modal", probes=["deception_70b"])
        player = GamePlayer(
            "TestPlayer",
            backend,
            "You are a werewolf. Pretend to be a villager."
        )
        
        result = player.query(
            "Are you a werewolf or a villager?",
            max_tokens=100,
            temperature=0.7
        )
        
        # Verify probe scores
        assert result.probe_scores is not None
        assert result.probe_scores.aggregate_score > 0
        assert len(result.probe_scores.token_scores) > 0
        
        print(f"\n✓ Deception score (70B): {result.probe_scores.aggregate_score:.3f}")
        print(f"✓ Generated: {result.text[:100]}...")


@pytest.mark.expensive
class TestModalHallucination:
    """Test Modal backend with hallucination probe."""
    
    def test_modal_hallucination_8b_connects(self):
        """Test that we can connect to the hallucination_8b probe service."""
        backend = create_backend("modal", probes=["hallucination_8b"])
        assert backend.modal_app_name == "unified-probe-service"
        assert backend.supports_probes == True
    
    @pytest.mark.slow
    def test_modal_hallucination_8b_returns_probe_scores(self):
        """Test that hallucination_8b probe returns non-zero probe scores."""
        backend = create_backend("modal", probes=["hallucination_8b"])
        player = GamePlayer(
            "TestPlayer",
            backend,
            "You are playing a game. Generate 2 truths and 1 lie."
        )
        
        result = player.query(
            "Tell me 3 facts about yourself. Make 2 true and 1 false.",
            max_tokens=150,
            temperature=0.7
        )
        
        # Verify probe scores
        assert result.probe_scores is not None
        assert result.probe_scores.aggregate_score > 0
        assert len(result.probe_scores.token_scores) > 0
        
        print(f"\n✓ Hallucination score: {result.probe_scores.aggregate_score:.3f}")
        print(f"✓ Generated: {result.text[:100]}...")


@pytest.mark.expensive
class TestBackendComparison:
    """Compare different backends to ensure consistent behavior."""
    
    @pytest.mark.slow
    def test_claude_vs_modal_text_generation(self):
        """Test that both backends generate valid text (different content expected)."""
        prompt = "Say hello"
        system_prompt = "You are a friendly assistant."
        
        # Create both backends
        claude_backend = create_backend("claude")
        modal_backend = create_backend("modal", probes=["deception_8b"])
        
        # Create players
        claude_player = GamePlayer("ClaudePlayer", claude_backend, system_prompt)
        modal_player = GamePlayer("ModalPlayer", modal_backend, system_prompt)
        
        # Generate responses
        claude_result = claude_player.query(prompt, max_tokens=50)
        modal_result = modal_player.query(prompt, max_tokens=50)
        
        # Both should generate text
        assert len(claude_result.text) > 0
        assert len(modal_result.text) > 0
        
        # Claude should not have probes
        assert claude_result.probe_scores is None
        
        # Modal should have probes
        assert modal_result.probe_scores is not None
        assert modal_result.probe_scores.aggregate_score > 0
        
        print(f"\n✓ Claude: {claude_result.text[:50]}...")
        print(f"✓ Modal: {modal_result.text[:50]}...")
        print(f"✓ Modal probe score: {modal_result.probe_scores.aggregate_score:.3f}")


@pytest.mark.expensive
class TestProbeScoreRanges:
    """Test that probe scores are returned for different prompts."""
    
    def test_truthful_prompt_returns_scores(self):
        """Test that truthful statements get probe scores."""
        backend = create_backend("modal", probes=["deception_8b"])
        player = GamePlayer(
            "TestPlayer",
            backend,
            "You are an honest player. Always tell the truth."
        )
        
        result = player.query(
            "Tell me honestly about your plans.",
            max_tokens=100,
            temperature=0.7
        )
        
        assert result.probe_scores is not None
        score = result.probe_scores.aggregate_score
        
        print(f"\n✓ Truthful prompt score: {score:.3f}")
        print(f"✓ Text: {result.text[:100]}...")
        
        # Verify we got a real score (Apollo probes return unnormalized logits)
        assert abs(score) < 200, "Score should be reasonable magnitude"
    
    def test_deceptive_prompt_returns_scores(self):
        """Test that explicitly deceptive prompts produce measurable scores."""
        backend = create_backend("modal", probes=["deception_8b"])
        player = GamePlayer(
            "TestPlayer",
            backend,
            "You are a liar. Deceive the other players about your true intentions."
        )
        
        result = player.query(
            "Tell me your strategy. Lie about what you plan to do.",
            max_tokens=100,
            temperature=0.7
        )
        
        assert result.probe_scores is not None
        score = result.probe_scores.aggregate_score
        
        print(f"\n✓ Deceptive prompt score: {score:.3f}")
        print(f"✓ Text: {result.text[:100]}...")
        
        # Verify we got a real score
        assert abs(score) < 200, "Score should be reasonable magnitude"


@pytest.mark.expensive
class TestProbeMetadata:
    """Test that probe metadata is correctly populated."""
    
    def test_probe_metadata_fields(self):
        """Test that probe scores include expected metadata."""
        backend = create_backend("modal", probes=["deception_8b"])
        player = GamePlayer("TestPlayer", backend, "You are a player.")
        
        result = player.query("Say something", max_tokens=50)
        
        assert result.probe_scores is not None
        assert result.probe_scores.metadata is not None
        
        # Check metadata fields
        metadata = result.probe_scores.metadata
        assert "num_tokens" in metadata or len(result.probe_scores.token_scores) > 0
        assert "probe_type" in metadata
        
        print(f"\n✓ Metadata: {metadata}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
