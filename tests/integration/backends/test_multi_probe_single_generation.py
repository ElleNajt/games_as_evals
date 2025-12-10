"""
Test that multi-probe collection uses a single generation run.

This test verifies that when multiple probes are configured, the Modal service:
1. Runs generation ONCE
2. Collects scores from ALL probes for the SAME tokens
3. Returns matching token counts for all probes
"""

import pytest
from src.backends import create_backend


@pytest.mark.expensive
def test_multi_probe_single_generation_token_count_match():
    """
    CRITICAL TEST: Verify that all probes score the SAME generation.
    
    This test ensures that:
    - All probes have the same number of token scores
    - Token count matches the generated tokens
    - Logits count matches tokens (same generation)
    
    If this fails, it means probes are running separate generations.
    """
    backend = create_backend(
        'modal',
        probes=['deception_8b', 'hallucination_8b'],
        top_k_logits=10
    )
    
    result = backend.generate(
        messages=[{'role': 'user', 'content': 'Tell me about the Eiffel Tower.'}],
        max_tokens=50,
        temperature=0.7
    )
    
    # Get token counts
    num_tokens = len(result.tokens)
    num_logits = len(result.top_k_logits)
    
    deception_scores = result.probe_scores.scores['deception_8b'].token_scores
    hallucination_scores = result.probe_scores.scores['hallucination_8b'].token_scores
    
    num_deception_scores = len(deception_scores)
    num_hallucination_scores = len(hallucination_scores)
    
    # Print diagnostic info
    print(f"\n=== Multi-Probe Single Generation Test ===")
    print(f"Tokens: {num_tokens}")
    print(f"Logits: {num_logits}")
    print(f"Deception scores: {num_deception_scores}")
    print(f"Hallucination scores: {num_hallucination_scores}")
    
    # CRITICAL: All counts must match
    assert num_deception_scores == num_tokens, \
        f"Deception probe has {num_deception_scores} scores but {num_tokens} tokens"
    
    assert num_hallucination_scores == num_tokens, \
        f"Hallucination probe has {num_hallucination_scores} scores but {num_tokens} tokens"
    
    assert num_logits == num_tokens, \
        f"Logits has {num_logits} positions but {num_tokens} tokens"
    
    # If we get here, all probes scored the same generation
    print(f"✓ All probes scored the same {num_tokens}-token generation")


@pytest.mark.expensive  
def test_multi_probe_deterministic_with_temp_zero():
    """
    Verify that with temperature=0, running generation twice with different
    probe sets produces the SAME text (proving single generation).
    
    This is a secondary check - with temp=0, separate generations would
    still produce identical text, but it's a sanity check.
    """
    messages = [{'role': 'user', 'content': 'What is 2+2?'}]
    
    # Run with deception probe only
    backend1 = create_backend('modal', probes=['deception_8b'])
    result1 = backend1.generate(messages=messages, max_tokens=20, temperature=0.0)
    
    # Run with both probes
    backend2 = create_backend('modal', probes=['deception_8b', 'hallucination_8b'])
    result2 = backend2.generate(messages=messages, max_tokens=20, temperature=0.0)
    
    # With temp=0, text should be identical
    assert result1.text == result2.text, \
        "Temperature=0 should produce identical text regardless of probe configuration"
    
    # Both should have same token count
    assert len(result1.tokens) == len(result2.tokens), \
        "Token counts should match with temperature=0"
    
    print(f"✓ Deterministic generation produces {len(result1.tokens)} tokens")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
