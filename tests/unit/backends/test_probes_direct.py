"""
Direct probe tests without game scaffolding.

Tests that probes can be loaded and used for generation without requiring
the full TTL game infrastructure.
"""

import pytest
import sys
sys.path.insert(0, '/workspace')

from src.backends import create_backend


class TestProbesDirect8B:
    """Test both 8B probes together without game scaffolding."""
    
    def test_8b_both_probes_basic_generation(self):
        """Test 8B model with both deception and hallucination probes."""
        # Create backend with both 8B probes
        backend = create_backend(
            'modal',
            probes=['deception_8b', 'hallucination_8b'],
            top_k_logits=10
        )
        
        # Verify capabilities
        assert backend.supports_logits, "Backend should support logits"
        assert backend.supports_probes, "Backend should support probes"
        assert backend.probes == ['deception_8b', 'hallucination_8b'], f"Expected both probes, got {backend.probes}"
        
        # Generate text that might trigger both probes
        result = backend.generate(
            messages=[{
                'role': 'user',
                'content': 'Tell me a made-up fact about the Eiffel Tower.'
            }],
            max_tokens=50,
            temperature=0.7
        )
        
        # Verify basic generation worked
        assert result.text, "Should generate text"
        assert len(result.text) > 0, "Generated text should not be empty"
        
        # Verify tokens were returned
        assert result.tokens is not None, "Should return tokens"
        assert len(result.tokens) > 0, "Should have tokens"
        
        # Verify top-k logits were returned
        assert result.top_k_logits is not None, "Should return top-k logits"
        assert len(result.top_k_logits) == len(result.tokens), \
            f"Logits count ({len(result.top_k_logits)}) should match tokens count ({len(result.tokens)})"
        
        # Verify each logits entry has alternatives
        for i, logits_dict in enumerate(result.top_k_logits):
            assert isinstance(logits_dict, dict), f"Position {i} logits should be dict"
            assert len(logits_dict) > 0, f"Position {i} should have alternative tokens"
        
        # Verify probe scores for BOTH probes
        assert result.probe_scores is not None, "Should return probe scores"
        assert 'deception_8b' in result.probe_scores.scores, "Should have deception_8b scores"
        assert 'hallucination_8b' in result.probe_scores.scores, "Should have hallucination_8b scores"
        
        # Verify each probe has valid scores
        for probe_name in ['deception_8b', 'hallucination_8b']:
            score_data = result.probe_scores.scores[probe_name]
            assert score_data.aggregate_score is not None, f"{probe_name} should have aggregate score"
            assert isinstance(score_data.aggregate_score, float), f"{probe_name} aggregate should be float"
            assert 0.0 <= score_data.aggregate_score <= 1.0, \
                f"{probe_name} aggregate score should be between 0 and 1, got {score_data.aggregate_score}"
            
            # Verify per-token scores
            assert score_data.per_token_scores is not None, f"{probe_name} should have per-token scores"
            assert len(score_data.per_token_scores) == len(result.tokens), \
                f"{probe_name} per-token scores should match token count"
        
        print(f"\n✓ Generated: {result.text}")
        print(f"✓ Tokens: {len(result.tokens)}")
        print(f"✓ Logits: {len(result.top_k_logits)} positions")
        print(f"✓ Probe scores:")
        for probe_name, score_data in result.probe_scores.scores.items():
            print(f"  - {probe_name}: {score_data.aggregate_score:.3f}")


class TestProbesDirect70B:
    """Test both 70B probes together without game scaffolding."""
    
    @pytest.mark.skip(reason="70B hallucination probe not yet available - need to locate or train it")
    def test_70b_both_probes_basic_generation(self):
        """Test 70B model with both deception and hallucination probes."""
        # Create backend with both 70B probes
        backend = create_backend(
            'modal',
            probes=['deception_70b', 'hallucination_70b'],
            top_k_logits=10
        )
        
        # Verify capabilities
        assert backend.supports_logits, "Backend should support logits"
        assert backend.supports_probes, "Backend should support probes"
        assert backend.probes == ['deception_70b', 'hallucination_70b'], f"Expected both probes, got {backend.probes}"
        
        # Generate text that might trigger both probes
        result = backend.generate(
            messages=[{
                'role': 'user',
                'content': 'Tell me a made-up fact about the Eiffel Tower.'
            }],
            max_tokens=50,
            temperature=0.7
        )
        
        # Verify basic generation worked
        assert result.text, "Should generate text"
        assert len(result.text) > 0, "Generated text should not be empty"
        
        # Verify tokens were returned
        assert result.tokens is not None, "Should return tokens"
        assert len(result.tokens) > 0, "Should have tokens"
        
        # Verify top-k logits were returned
        assert result.top_k_logits is not None, "Should return top-k logits"
        assert len(result.top_k_logits) == len(result.tokens), \
            f"Logits count ({len(result.top_k_logits)}) should match tokens count ({len(result.tokens)})"
        
        # Verify probe scores for BOTH probes
        assert result.probe_scores is not None, "Should return probe scores"
        assert 'deception_70b' in result.probe_scores.scores, "Should have deception_70b scores"
        assert 'hallucination_70b' in result.probe_scores.scores, "Should have hallucination_70b scores"
        
        # Verify each probe has valid scores
        for probe_name in ['deception_70b', 'hallucination_70b']:
            score_data = result.probe_scores.scores[probe_name]
            assert score_data.aggregate_score is not None, f"{probe_name} should have aggregate score"
            assert isinstance(score_data.aggregate_score, float), f"{probe_name} aggregate should be float"
            assert 0.0 <= score_data.aggregate_score <= 1.0, \
                f"{probe_name} aggregate score should be between 0 and 1, got {score_data.aggregate_score}"
            
            # Verify per-token scores
            assert score_data.per_token_scores is not None, f"{probe_name} should have per-token scores"
            assert len(score_data.per_token_scores) == len(result.tokens), \
                f"{probe_name} per-token scores should match token count"
        
        print(f"\n✓ Generated: {result.text}")
        print(f"✓ Tokens: {len(result.tokens)}")
        print(f"✓ Logits: {len(result.top_k_logits)} positions")
        print(f"✓ Probe scores:")
        for probe_name, score_data in result.probe_scores.scores.items():
            print(f"  - {probe_name}: {score_data.aggregate_score:.3f}")
    
    def test_70b_deception_probe_only(self):
        """Test 70B model with deception probe only (hallucination probe not yet available)."""
        # Create backend with deception probe only
        backend = create_backend(
            'modal',
            probes=['deception_70b'],
            top_k_logits=10
        )
        
        # Verify capabilities
        assert backend.supports_logits, "Backend should support logits"
        assert backend.supports_probes, "Backend should support probes"
        assert backend.probes == ['deception_70b'], f"Expected deception_70b probe, got {backend.probes}"
        
        # Generate text that might trigger deception
        result = backend.generate(
            messages=[{
                'role': 'user',
                'content': 'Tell me a convincing lie about historical events.'
            }],
            max_tokens=50,
            temperature=0.7
        )
        
        # Verify basic generation worked
        assert result.text, "Should generate text"
        assert len(result.text) > 0, "Generated text should not be empty"
        
        # Verify tokens and logits
        assert result.tokens is not None, "Should return tokens"
        assert result.top_k_logits is not None, "Should return top-k logits"
        assert len(result.top_k_logits) == len(result.tokens), "Logits should match tokens"
        
        # Verify deception probe scores
        assert result.probe_scores is not None, "Should return probe scores"
        assert 'deception_70b' in result.probe_scores.scores, "Should have deception_70b scores"
        
        score_data = result.probe_scores.scores['deception_70b']
        assert score_data.aggregate_score is not None, "Should have aggregate score"
        assert isinstance(score_data.aggregate_score, float), "Aggregate should be float"
        assert 0.0 <= score_data.aggregate_score <= 1.0, \
            f"Aggregate score should be between 0 and 1, got {score_data.aggregate_score}"
        
        print(f"\n✓ Generated: {result.text}")
        print(f"✓ Tokens: {len(result.tokens)}")
        print(f"✓ Deception score: {score_data.aggregate_score:.3f}")


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v', '-s'])
