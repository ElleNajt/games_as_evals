#!/usr/bin/env python3
"""
Example: Using ExperimentConfig to configure games consistently.

This shows how to define probe/model settings once and apply them
to multiple different games.
"""

from src.config.experiment_config import ExperimentConfig, get_experiment_config
from src.experiments.werewolf.configs import create_werewolf_config
from src.experiments.ttl.configs import create_ttl_config
from src.games.werewolf import WerewolfConfig
from src.games.ttl import TTLConfig


def example_1_using_preset():
    """Use a predefined preset for quick setup."""
    print("=" * 70)
    print("Example 1: Using preset 'x8b_both'")
    print("=" * 70)
    
    # Get predefined config
    exp = get_experiment_config("8b_both")
    print(f"Model: {exp.model}")
    print(f"Probes: {exp.probes}")
    print(f"Top-k logits: {exp.top_k_logits}")
    
    # Apply to Werewolf
    werewolf_config = WerewolfConfig(**exp.to_werewolf_config_kwargs(
        num_players=6,
        num_werewolves=2
    ))
    print(f"\nWerewolf players: {len(werewolf_config.players)}")
    print(f"Villager probes: {werewolf_config.players[2].probes}")
    
    # Apply to TTL with same settings
    ttl_config = TTLConfig(**exp.to_ttl_config_kwargs())
    print(f"\nTTL deceiver probes: {ttl_config.deceiver_config.probes}")
    print(f"TTL auditor probes: {ttl_config.auditor_config.probes}")


def example_2_custom_config():
    """Create a custom experiment configuration."""
    print("\n" + "=" * 70)
    print("Example 2: Custom configuration")
    print("=" * 70)
    
    # Define your own config
    exp = ExperimentConfig(
        model="meta-llama/Llama-3.3-70B-Instruct",
        probes=["deception_70b", "hallucination_70b"],
        top_k_logits=20,  # More logits
        temperature=0.9,  # Higher temperature
        experiment_name="high_temp_experiment",
        description="Testing with higher temperature and 70B model"
    )
    
    print(f"Experiment: {exp.experiment_name}")
    print(f"Description: {exp.description}")
    print(f"Temperature: {exp.temperature}")
    
    # Use in both games
    werewolf_config = WerewolfConfig(**exp.to_werewolf_config_kwargs(
        num_players=8,
        max_turns=10
    ))
    
    ttl_config = TTLConfig(**exp.to_ttl_config_kwargs(
        use_real_world_facts=False
    ))
    
    print(f"\nBoth games using: {exp.model}")
    print(f"Both games have probes: {exp.probes}")


def example_3_baseline_comparison():
    """Set up baseline (no probes) vs experimental (with probes) configs."""
    print("\n" + "=" * 70)
    print("Example 3: Baseline vs Experimental")
    print("=" * 70)
    
    # Baseline: no probes
    baseline = get_experiment_config("baseline_8b")
    baseline.experiment_name = "baseline"
    
    # Experimental: with probes
    experimental = get_experiment_config("8b_both")
    experimental.experiment_name = "with_probes"
    
    # Run same game with both configs
    baseline_werewolf = WerewolfConfig(**baseline.to_werewolf_config_kwargs())
    experimental_werewolf = WerewolfConfig(**experimental.to_werewolf_config_kwargs())
    
    print(f"Baseline probes: {baseline.probes}")
    print(f"Experimental probes: {experimental.probes}")
    print("\nNow you can run both and compare results!")


def example_4_different_probes_per_game():
    """Use different probe combinations for different games."""
    print("\n" + "=" * 70)
    print("Example 4: Different probes for different games")
    print("=" * 70)
    
    # Werewolf: focus on deception
    werewolf_exp = ExperimentConfig(
        model="meta-llama/Meta-Llama-3.1-8B-Instruct",
        probes=["deception_8b"],
        experiment_name="werewolf_deception_only"
    )
    
    # TTL: focus on hallucination
    ttl_exp = ExperimentConfig(
        model="meta-llama/Meta-Llama-3.1-8B-Instruct",
        probes=["hallucination_8b"],
        experiment_name="ttl_hallucination_only"
    )
    
    werewolf_config = WerewolfConfig(**werewolf_exp.to_werewolf_config_kwargs())
    ttl_config = TTLConfig(**ttl_exp.to_ttl_config_kwargs())
    
    print(f"Werewolf uses: {werewolf_exp.probes}")
    print(f"TTL uses: {ttl_exp.probes}")


def example_5_sweep_across_configs():
    """Run experiments across multiple configurations."""
    print("\n" + "=" * 70)
    print("Example 5: Sweeping across configurations")
    print("=" * 70)
    
    configs_to_test = [
        "baseline_8b",
        "8b_deception",
        "8b_hallucination",
        "8b_both"
    ]
    
    print("Preparing to run Werewolf with:")
    for preset_name in configs_to_test:
        exp = get_experiment_config(preset_name)
        config = WerewolfConfig(**exp.to_werewolf_config_kwargs())
        
        print(f"\n  {preset_name}:")
        print(f"    Model: {exp.model}")
        print(f"    Probes: {exp.probes if exp.probes else 'none'}")
        
        # You would run the game here:
        # from src.games.werewolf import GameCoordinator
        # coordinator = GameCoordinator(config, experiment_name=preset_name)
        # results = coordinator.run_game()


if __name__ == "__main__":
    example_1_using_preset()
    example_2_custom_config()
    example_3_baseline_comparison()
    example_4_different_probes_per_game()
    example_5_sweep_across_configs()
    
    print("\n" + "=" * 70)
    print("All examples complete!")
    print("=" * 70)
