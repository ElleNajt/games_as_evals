"""Run Werewolf batch experiments with 70B model and both probes."""

from pathlib import Path

from src.config.experiment_config import get_experiment_config
from src.experiments.cli import create_werewolf_parser
from src.experiments.werewolf.batch_runner import run_batch_experiment
from src.experiments.werewolf.configs import create_werewolf_config


def main():
    """Main entry point with CLI argument support."""
    parser = create_werewolf_parser(
        description="Run Werewolf batch experiments with 70B model and both probes"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Running Werewolf Batch Experiment with 70B Model + Both Probes")
    print("=" * 70)

    # Get 70B experiment config with both probes
    exp_config = get_experiment_config("70b_both")

    print(f"Model: {exp_config.model}")
    print(f"Backend: {exp_config.backend_type}")
    print(f"Probes: {exp_config.probes}")
    print(f"Top-k logits: {exp_config.top_k_logits}")
    print(f"Number of rounds: {args.num_rounds}")
    print(f"Players: {args.num_players}")
    print(f"Werewolves: {args.num_werewolves}")
    print(f"Max turns per game: {args.max_turns}")
    print("=" * 70)
    print()

    # Create Werewolf configuration
    config = create_werewolf_config(
        exp_config,
        num_players=args.num_players,
        num_werewolves=args.num_werewolves,
        max_turns=args.max_turns,
    )

    # Determine experiment name
    experiment_name = args.experiment_name or "werewolf_70b_both_probes"

    # Run batch experiment (always save)
    print(f"Starting Werewolf batch experiment ({args.num_rounds} games)...")
    print()

    results = run_batch_experiment(
        config=config,
        num_rounds=args.num_rounds,
        experiment_name=experiment_name,
        save_results=True,
    )

    # Print summary statistics
    print()
    print("=" * 70)
    print("BATCH EXPERIMENT RESULTS")
    print("=" * 70)

    # Count wins by faction
    villager_wins = sum(
        1 for r in results.round_results if r.get("winner") == "Villagers"
    )
    werewolf_wins = sum(
        1 for r in results.round_results if r.get("winner") == "Werewolves"
    )

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

    results_path = (
        results.actual_results_dir or Path("results") / "werewolf" / experiment_name
    )
    print()
    print(f"Results saved to: {results_path}/")

    # Always generate plots
    from src.visualization.werewolf_batch_plots import generate_all_plots

    print()
    generate_all_plots(results_path)

    print("=" * 70)


if __name__ == "__main__":
    main()
