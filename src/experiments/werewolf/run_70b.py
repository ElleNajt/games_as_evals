"""Run Werewolf game with 70B model and both probes."""

from src.config.experiment_config import get_experiment_config
from src.experiments.werewolf.configs import create_werewolf_config
from src.games.werewolf.game_coordinator import GameCoordinator

print("=" * 70)
print("Running Werewolf Game with 70B Model + Both Probes")
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

# Run the game
print("Starting Werewolf game...")
print()

coordinator = GameCoordinator(
    config=config, experiment_name="werewolf_70b_both_probes", game_id=1
)

winner = coordinator.run_game()

# Print summary
print()
print("=" * 70)
print("GAME RESULTS")
print("=" * 70)
print(f"Winner: {winner}")
print(f"Turns played: {coordinator.game.turn_number}")
print()
print(f"Results saved to: results/werewolf/werewolf_70b_both_probes/game1/")
print("=" * 70)
