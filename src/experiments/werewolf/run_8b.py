"""Run Werewolf batch experiments with 8B model and both probes."""

from src.config.experiment_config import get_experiment_config
from src.experiments.werewolf.batch_runner import run_batch_experiment
from src.experiments.werewolf.configs import create_werewolf_config

print("=" * 70)
print("Running Werewolf Batch Experiments with 8B Model + Both Probes")
print("=" * 70)

# Get 8B experiment config with both probes
exp_config = get_experiment_config("8b_both")

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

# Run batch experiment with 5 games
print("Running 5 games of Werewolf...")
print()

results = run_batch_experiment(
    config=config,
    num_rounds=5,
    experiment_name="werewolf_8b_both_probes",
    save_results=True,
)

# Print summary
print()
print("=" * 70)
print("EXPERIMENT RESULTS")
print("=" * 70)
print(f"Total games: {results.total_rounds}")
print(f"Successful games: {results.successful_rounds}")
print(f"Failed games: {results.failed_rounds}")
print(f"Success rate: {results.success_rate:.1f}%")
print()

# Count winners
villager_wins = sum(1 for r in results.round_results if r.get("winner") == "Villagers")
werewolf_wins = sum(1 for r in results.round_results if r.get("winner") == "Werewolves")
print(f"Villagers won: {villager_wins} games")
print(f"Werewolves won: {werewolf_wins} games")

# Average game length
avg_turns = sum(r.get("turns", 0) for r in results.round_results) / max(
    len(results.round_results), 1
)
print(f"Average turns per game: {avg_turns:.1f}")
print()
print(f"Results saved to: results/werewolf/werewolf_8b_both_probes/")
print("=" * 70)
