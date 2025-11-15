#!/usr/bin/env python3
"""
Run a Two Truths and a Lie game with 8B model and both probes.

This script demonstrates using the ExperimentConfig system to configure
a TTL game with consistent model and probe settings.
"""

from src.config.experiment_config import get_experiment_config
from src.games.ttl import TTLConfig
from src.games.ttl.orchestrator_unified import run_game_round

def main():
    # Get 8B experiment config with both probes
    exp_config = get_experiment_config("8b_both")
    
    print("=" * 70)
    print("Running Two Truths and a Lie with 8B Model + Both Probes")
    print("=" * 70)
    print(f"Model: {exp_config.model}")
    print(f"Probes: {exp_config.probes}")
    print(f"Top-k logits: {exp_config.top_k_logits}")
    print("=" * 70)
    print()
    
    # Create TTL configuration using experiment config
    config = TTLConfig(
        **exp_config.to_ttl_config_kwargs(
            use_real_world_facts=True  # Deceiver generates own facts
        )
    )
    
    # Optional: provide specific facts instead
    # facts = [
    #     "The Eiffel Tower is in Paris",
    #     "Water boils at 100°C at sea level",
    #     "The Earth orbits the Sun"
    # ]
    
    # Run a single round
    print("Running game round...")
    results = run_game_round(
        config=config,
        facts=None,  # None means deceiver generates own facts
        experiment_name="ttl_8b_demo",
        round_id=1
    )
    
    # Print results
    print()
    print("=" * 70)
    print("GAME RESULTS")
    print("=" * 70)
    print(f"Auditor guessed correctly: {results.get('auditor_correct', False)}")
    print()
    
    if 'statements' in results:
        print("Statements generated:")
        for i, stmt in enumerate(results['statements'], 1):
            marker = " (LIE)" if i - 1 == results.get('lie_index', -1) else ""
            print(f"  {i}. {stmt}{marker}")
    
    print()
    print(f"Auditor's guess: Statement #{results.get('auditor_guess', '?')}")
    print(f"Actual lie: Statement #{results.get('lie_index', -1) + 1}")
    print()
    print(f"Results saved to: results/ttl/ttl_8b_demo/round1/")
    print()
    print("Check the following files:")
    print("  - deceiver_messages.jsonl: Deceiver's generation with probe scores")
    print("  - auditor_messages.jsonl: Auditor's reasoning")
    print("  - results.json: Complete round results")
    print()
    print("Probe scores available for each statement:")
    print("  - deception_8b: How deceptive the statement appears")
    print("  - hallucination_8b: How factually accurate the statement is")

if __name__ == "__main__":
    main()
