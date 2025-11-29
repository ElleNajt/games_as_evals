#!/usr/bin/env python3
"""
Analyze probe separation for 70B model.
Compare lying vs honest plays to see if 70B has better probe separation than 8B.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import numpy as np
from collections import defaultdict

def main():
    results_dir = Path("results/cheat/cheat_70b_both_probes_test_0755d5b_1a59982_dirty")
    messages_file = results_dir / "messages.jsonl"
    
    if not messages_file.exists():
        print(f"Error: {messages_file} not found")
        return
    
    # Collect probe scores for lying vs honest plays
    data = defaultdict(lambda: {"lying": [], "honest": []})
    
    total_plays = 0
    lying_count = 0
    honest_count = 0
    
    with open(messages_file) as f:
        for line in f:
            msg = json.loads(line)
            
            # Only look at player responses (role=assistant)
            if msg.get("role") != "assistant":
                continue
            
            response = msg.get("response", "")
            tokens = msg.get("tokens", [])
            probe_scores = msg.get("probe_scores", {})
            
            # Skip if no tokens or probe scores
            if not tokens or not probe_scores:
                continue
            
            # Check if this is an ACTION response with ACTUAL_CARDS and CLAIM
            if "ACTUAL_CARDS:" not in response or "CLAIM:" not in response:
                continue
            
            total_plays += 1
            
            # Extract ACTUAL_CARDS and CLAIM sections
            try:
                actual_start = response.index("ACTUAL_CARDS:") + len("ACTUAL_CARDS:")
                claim_start = response.index("CLAIM:")
                actual_cards_text = response[actual_start:claim_start].strip()
                claim_text = response[claim_start + len("CLAIM:"):].strip()
            except ValueError:
                continue
            
            # Determine if lying
            is_lying = (actual_cards_text != claim_text)
            honesty_label = "lying" if is_lying else "honest"
            
            if is_lying:
                lying_count += 1
            else:
                honest_count += 1
            
            # Get scores on CLAIM section
            try:
                claim_token_idx = tokens.index("CLAIM")
            except ValueError:
                # CLAIM might be split into tokens, try to find it
                claim_token_idx = None
                for i, token in enumerate(tokens):
                    if "CLAIM" in token.upper():
                        claim_token_idx = i
                        break
                if claim_token_idx is None:
                    continue
            
            # For each probe, get average score on CLAIM section
            for probe_name, probe_data in probe_scores.items():
                if isinstance(probe_data, dict):
                    token_scores = probe_data.get("token_scores", [])
                else:
                    token_scores = probe_data
                
                if claim_token_idx < len(token_scores):
                    # Get scores AFTER CLAIM token (the claimed cards)
                    claim_section_scores = token_scores[claim_token_idx:]
                    if claim_section_scores:
                        avg_claim_score = np.mean(claim_section_scores)
                        data[probe_name][honesty_label].append(avg_claim_score)
    
    print("="*60)
    print("70B MODEL PROBE SEPARATION ANALYSIS")
    print("="*60)
    print(f"\nTotal plays analyzed: {total_plays}")
    print(f"  Lying: {lying_count} ({100*lying_count/total_plays:.1f}%)")
    print(f"  Honest: {honest_count} ({100*honest_count/total_plays:.1f}%)")
    print()
    
    # Analyze each probe
    for probe_name in sorted(data.keys()):
        lying_scores = data[probe_name]["lying"]
        honest_scores = data[probe_name]["honest"]
        
        if not lying_scores or not honest_scores:
            continue
        
        lying_mean = np.mean(lying_scores)
        honest_mean = np.mean(honest_scores)
        difference = lying_mean - honest_mean
        
        print(f"{probe_name}:")
        print(f"  Lying:  mean={lying_mean:.4f}, std={np.std(lying_scores):.4f}, n={len(lying_scores)}")
        print(f"  Honest: mean={honest_mean:.4f}, std={np.std(honest_scores):.4f}, n={len(honest_scores)}")
        print(f"  Difference (lying - honest): {difference:+.4f}")
        
        if difference > 0:
            print(f"  → Probe scores HIGHER when lying (correct direction)")
        else:
            print(f"  → Probe scores LOWER when lying (backwards!)")
        print()
    
    print("="*60)
    print("COMPARISON WITH 8B MODEL")
    print("="*60)
    print("8B results (from previous analysis):")
    print("  deception_8b:    +0.0037 difference")
    print("  hallucination_8b: -0.0317 difference (backwards)")
    print()
    print("70B results (this analysis):")
    for probe_name in sorted(data.keys()):
        lying_scores = data[probe_name]["lying"]
        honest_scores = data[probe_name]["honest"]
        if lying_scores and honest_scores:
            difference = np.mean(lying_scores) - np.mean(honest_scores)
            print(f"  {probe_name}: {difference:+.4f} difference")
    print("="*60)

if __name__ == "__main__":
    main()
