#!/usr/bin/env python3
"""Test script for hallucination probe with unified backend system."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import PlayerConfig
from src.player import GamePlayer
from src.result_logging import ResultsLogger


def main():
    print("=" * 80)
    print("HALLUCINATION PROBE TEST - Unified Backend")
    print("=" * 80)
    
    # Create player config with hallucination probe
    config = PlayerConfig(
        name="TestPlayer",
        backend_type="modal",
        model="meta-llama/Meta-Llama-3.1-8B-Instruct",
        probe="hallucination_8b",
        temperature=0.7,
        max_tokens=200,
        system_prompt="You are a helpful assistant."
    )
    
    print(f"\nPlayer Config:")
    print(f"  Backend: {config.backend_type}")
    print(f"  Model: {config.model}")
    print(f"  Probe: {config.probe}")
    
    # Create logger
    logger = ResultsLogger(
        game_name="hallucination_test",
        experiment_name="unified_backend_test",
        output_dir="./results"
    )
    
    print(f"\nResults directory: {logger.results_dir}")
    
    # Create player with unified backend
    print(f"\nCreating GamePlayer with unified backend...")
    player = GamePlayer(
        name=config.name,
        player_config=config,
        logger=logger
    )
    
    # Test query 1: True statement
    print(f"\n{'=' * 80}")
    print("TEST 1: True statement (should have low hallucination score)")
    print(f"{'=' * 80}")
    
    prompt1 = "The capital of France is Paris. Respond with: 'That is correct.'"
    result1 = player.query(prompt=prompt1, max_tokens=50, temperature=0.7)
    
    print(f"\nPrompt: {prompt1}")
    print(f"Response: {result1.text}")
    if result1.probe_scores:
        print(f"Hallucination score: {result1.probe_scores.aggregate_score:.4f}")
        print(f"Token scores: {[f'{s:.3f}' for s in result1.probe_scores.token_scores[:10]]}")
    
    # Test query 2: Made-up fact
    print(f"\n{'=' * 80}")
    print("TEST 2: Made-up fact (should have higher hallucination score)")
    print(f"{'=' * 80}")
    
    prompt2 = "The tallest mountain on Mars is called Mount Everest and is 50km high. Respond with: 'That is an interesting fact.'"
    result2 = player.query(prompt=prompt2, max_tokens=50, temperature=0.7)
    
    print(f"\nPrompt: {prompt2}")
    print(f"Response: {result2.text}")
    if result2.probe_scores:
        print(f"Hallucination score: {result2.probe_scores.aggregate_score:.4f}")
        print(f"Token scores: {[f'{s:.3f}' for s in result2.probe_scores.token_scores[:10]]}")
    
    # Test query 3: Generate facts
    print(f"\n{'=' * 80}")
    print("TEST 3: Generate two truths and a lie")
    print(f"{'=' * 80}")
    
    prompt3 = """Generate two truths and a lie about animals. Format:
1. [statement]
2. [statement]  
3. [statement]"""
    
    result3 = player.query(prompt=prompt3, max_tokens=150, temperature=0.7)
    
    print(f"\nPrompt: {prompt3}")
    print(f"Response: {result3.text}")
    if result3.probe_scores:
        print(f"\nHallucination score: {result3.probe_scores.aggregate_score:.4f}")
        print(f"Number of tokens: {len(result3.probe_scores.token_scores)}")
        
        # Show token-level scores
        if result3.tokens and len(result3.tokens) == len(result3.probe_scores.token_scores):
            print(f"\nToken-level analysis (first 20 tokens):")
            for token, score in zip(result3.tokens[:20], result3.probe_scores.token_scores[:20]):
                print(f"  {token:20s} {score:.4f}")
    
    print(f"\n{'=' * 80}")
    print("TEST COMPLETE")
    print(f"{'=' * 80}")
    print(f"\nResults saved to: {logger.results_dir}")
    print(f"Check messages.jsonl for detailed logs")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
