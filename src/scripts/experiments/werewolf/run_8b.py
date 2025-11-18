"""Run Werewolf experiments with 8B model and both probes.

NOTE: This is a placeholder script. Werewolf game runner needs to be implemented.
"""
from src.config.experiment_config import get_experiment_config
from src.games.werewolf import WerewolfConfig

print("=" * 70)
print("Werewolf Experiments with 8B Model + Both Probes")
print("=" * 70)
print()
print("NOTE: Werewolf experiment runner not yet implemented.")
print("This script is a placeholder for future implementation.")
print()

# Get 8B experiment config with both probes
exp_config = get_experiment_config('8b_both')

print(f"Model: {exp_config.model}")
print(f"Backend: {exp_config.backend_type}")
print(f"Probes: {exp_config.probes}")
print(f"Top-k logits: {exp_config.top_k_logits}")
print("=" * 70)

# TODO: Implement Werewolf game runner
# Expected usage:
# from src.games.werewolf.game_coordinator import GameCoordinator
# config = WerewolfConfig(...)
# coordinator = GameCoordinator(config)
# results = coordinator.run_game()
