#!/usr/bin/env python
"""
Integration test for Modal backend with real probes and logits.

This test requires:
1. Modal service deployed: modal deploy src/modal_deployments/unified_probe_service.py
2. Probes uploaded to Modal volume
3. Modal CLI configured: modal setup

Run with: python test_modal_integration.py
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from backends import create_backend
from backends.base import GenerationResult


def test_basic_generation_no_probes():
    """Test 1: Basic generation without probes."""
    print("\n" + "="*60)
    print("TEST 1: Basic generation (no probes, no logits)")
    print("="*60)
    
    backend = create_backend("modal")
    
    result = backend.generate(
        messages=[{"role": "user", "content": "What is 2+2?"}],
        max_tokens=20,
        temperature=0.7
    )
    
    assert isinstance(result, GenerationResult)
    assert result.text
    assert result.probe_scores is None
    assert result.top_k_logits is None
    
    print(f"✓ Generated text: {result.text}")
    print(f"✓ No probes: {result.probe_scores is None}")
    print(f"✓ No logits: {result.top_k_logits is None}")
    print("PASS")


def test_single_probe():
    """Test 2: Single probe without logits."""
    print("\n" + "="*60)
    print("TEST 2: Single probe (deception_8b, no logits)")
    print("="*60)
    
    backend = create_backend("modal", probe="deception_8b")
    
    result = backend.generate(
        messages=[{"role": "user", "content": "Tell me a convincing lie."}],
        max_tokens=30,
        temperature=0.7
    )
    
    assert result.text
    assert result.tokens is not None
    assert result.probe_scores is not None
    assert "deception_8b" in result.probe_scores.scores
    assert result.top_k_logits is None  # Not requested
    
    probe_score = result.probe_scores["deception_8b"]
    print(f"✓ Generated text: {result.text}")
    print(f"✓ Tokens: {len(result.tokens)}")
    print(f"✓ Probe aggregate score: {probe_score.aggregate_score:.3f}")
    print(f"✓ Token scores: {len(probe_score.token_scores)} scores")
    print(f"✓ No logits (not requested): {result.top_k_logits is None}")
    print("PASS")


def test_single_probe_with_logits():
    """Test 3: Single probe WITH logits."""
    print("\n" + "="*60)
    print("TEST 3: Single probe with logits (deception_8b, top_k=10)")
    print("="*60)
    
    backend = create_backend("modal", probe="deception_8b", top_k_logits=10)
    
    assert backend.supports_logits == True
    
    result = backend.generate(
        messages=[{"role": "user", "content": "What is the capital of France?"}],
        max_tokens=20,
        temperature=0.7
    )
    
    assert result.text
    assert result.tokens is not None
    assert result.probe_scores is not None
    assert result.top_k_logits is not None  # NOW REQUESTED
    
    # Validate logits structure
    assert len(result.top_k_logits) == len(result.tokens), \
        f"Logits ({len(result.top_k_logits)}) != tokens ({len(result.tokens)})"
    
    for i, token_logits in enumerate(result.top_k_logits):
        assert isinstance(token_logits, dict)
        assert len(token_logits) > 0
        assert len(token_logits) <= 10  # At most top-10
        
        # Check values are log probabilities (negative)
        for token, logprob in token_logits.items():
            assert isinstance(logprob, (int, float))
            # Log probs are typically negative (but allow 0)
            assert logprob <= 0.01, f"Logprob {logprob} for token '{token}' seems wrong"
    
    probe_score = result.probe_scores["deception_8b"]
    print(f"✓ Generated text: {result.text}")
    print(f"✓ Tokens: {len(result.tokens)}")
    print(f"✓ Probe score: {probe_score.aggregate_score:.3f}")
    print(f"✓ Logits: {len(result.top_k_logits)} token positions")
    print(f"✓ Example logits for token 0 ({result.tokens[0]}):")
    for token, logprob in list(result.top_k_logits[0].items())[:3]:
        print(f"    {token!r}: {logprob:.3f}")
    print("PASS")


def test_multiple_probes_with_logits():
    """Test 4: Multiple probes with logits."""
    print("\n" + "="*60)
    print("TEST 4: Multiple probes with logits")
    print("="*60)
    
    backend = create_backend(
        "modal",
        probes=["deception_8b", "hallucination_8b"],
        top_k_logits=5
    )
    
    result = backend.generate(
        messages=[{"role": "user", "content": "I have been to the moon."}],
        max_tokens=25,
        temperature=0.7
    )
    
    assert result.text
    assert result.tokens is not None
    assert result.probe_scores is not None
    assert result.top_k_logits is not None
    
    # Check both probes present
    assert "deception_8b" in result.probe_scores.scores
    assert "hallucination_8b" in result.probe_scores.scores
    
    # Validate logits
    assert len(result.top_k_logits) == len(result.tokens)
    for token_logits in result.top_k_logits:
        assert len(token_logits) <= 5  # top-5 requested
    
    dec_score = result.probe_scores["deception_8b"].aggregate_score
    hal_score = result.probe_scores["hallucination_8b"].aggregate_score
    
    print(f"✓ Generated text: {result.text}")
    print(f"✓ Deception score: {dec_score:.3f}")
    print(f"✓ Hallucination score: {hal_score:.3f}")
    print(f"✓ Logits: {len(result.top_k_logits)} positions, top-5 per token")
    print("PASS")


def test_logits_without_probes():
    """Test 5: Logits without probes."""
    print("\n" + "="*60)
    print("TEST 5: Logits without probes")
    print("="*60)
    
    backend = create_backend("modal", top_k_logits=10)
    
    assert backend.supports_logits == True
    assert backend.supports_probes == False
    
    result = backend.generate(
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=15,
        temperature=0.7
    )
    
    assert result.text
    assert result.probe_scores is None
    assert result.top_k_logits is not None
    
    print(f"✓ Generated text: {result.text}")
    print(f"✓ No probes: {result.probe_scores is None}")
    print(f"✓ Logits present: {len(result.top_k_logits)} positions")
    print("PASS")


def test_edge_cases():
    """Test 6: Edge cases."""
    print("\n" + "="*60)
    print("TEST 6: Edge cases")
    print("="*60)
    
    # Very short generation
    backend = create_backend("modal", probe="deception_8b", top_k_logits=10)
    
    result = backend.generate(
        messages=[{"role": "user", "content": "Say one word."}],
        max_tokens=1,
        temperature=0.0  # Deterministic
    )
    
    assert result.text
    assert result.tokens is not None
    assert len(result.tokens) >= 1
    assert len(result.top_k_logits) == len(result.tokens)
    
    print(f"✓ Very short generation (max_tokens=1)")
    print(f"  Tokens: {result.tokens}")
    print(f"  Logits: {len(result.top_k_logits)} positions")
    print("PASS")


def save_test_results(results_file="modal_integration_results.json"):
    """Save a test result for inspection."""
    print("\n" + "="*60)
    print("Saving example result for inspection")
    print("="*60)
    
    backend = create_backend("modal", probe="deception_8b", top_k_logits=10)
    
    result = backend.generate(
        messages=[{"role": "user", "content": "The sky is green."}],
        max_tokens=30,
        temperature=0.7
    )
    
    # Convert to dict for JSON serialization
    result_dict = {
        "text": result.text,
        "tokens": result.tokens,
        "top_k_logits": result.top_k_logits,
        "probe_scores": {
            "deception_8b": {
                "aggregate_score": result.probe_scores["deception_8b"].aggregate_score,
                "token_scores": result.probe_scores["deception_8b"].token_scores,
                "metadata": result.probe_scores["deception_8b"].metadata,
            }
        }
    }
    
    with open(results_file, "w") as f:
        json.dump(result_dict, f, indent=2)
    
    print(f"✓ Saved to {results_file}")


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print(" MODAL BACKEND INTEGRATION TEST SUITE")
    print("="*70)
    print("\nThis will test the Modal backend with real probes and logits support.")
    print("Make sure:")
    print("  1. Modal service is deployed")
    print("  2. Probes are uploaded to volume")
    print("  3. You have Modal access configured")
    
    input("\nPress Enter to continue...")
    
    try:
        test_basic_generation_no_probes()
        test_single_probe()
        test_single_probe_with_logits()
        test_multiple_probes_with_logits()
        test_logits_without_probes()
        test_edge_cases()
        save_test_results()
        
        print("\n" + "="*70)
        print(" ALL TESTS PASSED! ✓")
        print("="*70)
        print("\nThe Modal backend is working correctly with:")
        print("  ✓ Basic generation")
        print("  ✓ Single probe support")
        print("  ✓ Multiple probe support")
        print("  ✓ Top-k logits extraction")
        print("  ✓ Combined probes + logits")
        print("\nCheck modal_integration_results.json for example output.")
        
    except Exception as e:
        print("\n" + "="*70)
        print(" TEST FAILED! ✗")
        print("="*70)
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
