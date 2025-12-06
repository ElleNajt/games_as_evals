"""Run Werewolf batch experiments with 70B model and both probes."""

from src.config.experiment_config import get_experiment_config
from src.experiments.werewolf.batch_runner import run_batch_experiment
from src.experiments.werewolf.configs import create_werewolf_config

print("=" * 70)
print("Running Werewolf Batch Experiment with 70B Model + Both Probes")
print("=" * 70)

# Get 70B experiment config with both probes
exp_config = get_experiment_config("70b_both")

print(f"Model: {exp_config.model}")
print(f"Backend: {exp_config.backend_type}")
print(f"Probes: {exp_config.probes}")
print(f"Top-k logits: {exp_config.top_k_logits}")
print("=" * 70)
print()

# Create Werewolf configuration with 5 players, 2 werewolves
config = create_werewolf_config(
    exp_config, num_players=5, num_werewolves=2, max_turns=10
)

# Run batch experiment (5 games)
print("Starting Werewolf batch experiment (5 games)...")
print()

results = run_batch_experiment(
    config=config,
    num_rounds=5,
    experiment_name="werewolf_70b_both_probes",
    save_results=True,
)

# Print summary statistics
print()
print("=" * 70)
print("BATCH EXPERIMENT RESULTS")
print("=" * 70)

# Count wins by faction
villager_wins = sum(1 for r in results.round_results if r.get("winner") == "Villagers")
werewolf_wins = sum(1 for r in results.round_results if r.get("winner") == "Werewolves")

print(f"Successful games: {results.successful_rounds}/{results.total_rounds}")
print(f"Villager wins: {villager_wins}")
print(f"Werewolf wins: {werewolf_wins}")

# Calculate average turns
if results.successful_rounds > 0:
    avg_turns = (
        sum(r.get("turns", 0) for r in results.round_results if r.get("success"))
        / results.successful_rounds
    )
    print(f"Average turns per game: {avg_turns:.1f}")

print()
print(f"Detailed results saved to batch_results.json")
print("=" * 70)
