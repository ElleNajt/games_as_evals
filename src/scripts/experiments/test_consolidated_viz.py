#!/usr/bin/env python3
"""Test script for consolidated HTML visualization with multi-probe support."""

from pathlib import Path
from src.result_logging.results_logger import ResultsLogger
from src.backends.base import ProbeScores, ProbeScoreData
from src.games.ttl.config import TTLConfig

def test_consolidated_visualization():
    """Test the consolidated HTML visualization feature."""
    
    # Create a simple TTLConfig (GameConfig is abstract)
    config = TTLConfig(
        output_dir="/tmp/test_results",
        use_real_world_facts=False,
    )
    
    # Create ResultsLogger with auto_visualize enabled
    logger = ResultsLogger(
        config=config,
        results_dir=Path("/tmp/test_results"),
        auto_visualize=True,
    )
    
    # Simulate logging multiple messages with multi-probe scores
    
    # Message 1: Deceiver
    tokens1 = ["I", " am", " telling", " the", " truth", "."]
    probe_scores1 = ProbeScores(scores={
        'deception_8b': ProbeScoreData(
            aggregate_score=0.75,
            token_scores=[0.1, 0.3, 0.6, 0.7, 0.9, 0.8]
        ),
        'hallucination_8b': ProbeScoreData(
            aggregate_score=0.25,
            token_scores=[0.05, 0.15, 0.20, 0.30, 0.35, 0.25]
        ),
    })
    logger.log_message("deceiver", tokens1, probe_scores1)
    
    # Message 2: Auditor
    tokens2 = ["That", " sounds", " suspicious", "!"]
    probe_scores2 = ProbeScores(scores={
        'deception_8b': ProbeScoreData(
            aggregate_score=0.15,
            token_scores=[0.1, 0.1, 0.2, 0.2]
        ),
        'hallucination_8b': ProbeScoreData(
            aggregate_score=0.10,
            token_scores=[0.05, 0.08, 0.12, 0.15]
        ),
    })
    logger.log_message("auditor", tokens2, probe_scores2)
    
    # Message 3: Deceiver again
    tokens3 = ["I", " promise", " it", "'s", " real", "!"]
    probe_scores3 = ProbeScores(scores={
        'deception_8b': ProbeScoreData(
            aggregate_score=0.85,
            token_scores=[0.2, 0.7, 0.8, 0.9, 0.95, 0.92]
        ),
        'hallucination_8b': ProbeScoreData(
            aggregate_score=0.40,
            token_scores=[0.15, 0.35, 0.40, 0.45, 0.50, 0.48]
        ),
    })
    logger.log_message("deceiver", tokens3, probe_scores3)
    
    # Generate consolidated visualization
    html_file = logger.generate_consolidated_visualization()
    
    if html_file:
        print(f"✓ Consolidated HTML generated: {html_file}")
        print(f"✓ File size: {html_file.stat().st_size} bytes")
        
        # Read and check content
        with open(html_file, 'r') as f:
            content = f.read()
        
        # Verify key features
        checks = [
            ('Radio buttons present', '<input type="radio" name="probe"' in content),
            ('deception_8b probe', 'deception_8b' in content),
            ('hallucination_8b probe', 'hallucination_8b' in content),
            ('JavaScript present', 'function updateColors()' in content),
            ('Data attributes', 'data-deception_8b' in content and 'data-hallucination_8b' in content),
            ('Message 1', 'Message #1' in content),
            ('Message 2', 'Message #2' in content),
            ('Message 3', 'Message #3' in content),
            ('Deceiver label', 'deceiver' in content.lower()),
            ('Auditor label', 'auditor' in content.lower()),
        ]
        
        print("\nContent verification:")
        all_passed = True
        for check_name, passed in checks:
            status = "✓" if passed else "✗"
            print(f"  {status} {check_name}")
            if not passed:
                all_passed = False
        
        if all_passed:
            print("\n✓ All checks passed! Consolidated visualization working correctly.")
            print(f"\nYou can view the HTML file at: {html_file}")
        else:
            print("\n✗ Some checks failed!")
            return False
    else:
        print("✗ No HTML file generated!")
        return False
    
    return True

if __name__ == "__main__":
    success = test_consolidated_visualization()
    exit(0 if success else 1)
