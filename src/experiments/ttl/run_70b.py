"""Run TTL batch experiments with 70B model and both probes."""

from pathlib import Path

from src.config.experiment_config import get_experiment_config
from src.experiments.cli import create_ttl_parser
from src.experiments.ttl.batch_runner import run_batch_experiment
from src.experiments.ttl.configs import create_ttl_config


def main():
    """Main entry point with CLI argument support."""
    parser = create_ttl_parser(
        description="Run TTL batch experiments with 70B model and both probes"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Running TTL Batch Experiments with 70B Model + Both Probes")
    print("=" * 70)

    # Get 70B experiment config with both probes
    exp_config = get_experiment_config("70b_both")

    print(f"Model: {exp_config.model}")
    print(f"Backend: {exp_config.backend_type}")
    print(f"Probes: {exp_config.probes}")
    print(f"Top-k logits: {exp_config.top_k_logits}")
    print(f"Number of rounds: {args.num_rounds}")
    print("=" * 70)
    print()

    # Handle real vs fictional facts
    use_real_facts = not args.use_fictional_facts

    # Create TTL configuration
    config = create_ttl_config(
        exp_config,
        use_real_world_facts=use_real_facts,
        use_max_score_strategy=args.use_max_score_strategy,
    )

    # Determine experiment name
    experiment_name = args.experiment_name or "ttl_70b_both_probes"

    # Run batch experiment (always save)
    print(f"Running {args.num_rounds} rounds of TTL game...")
    print()

    results = run_batch_experiment(
        config=config,
        num_rounds=args.num_rounds,
        experiment_name=experiment_name,
        facts=None,
        save_results=True,
    )

    # Print summary
    print()
    print("=" * 70)
    print("EXPERIMENT RESULTS")
    print("=" * 70)
    print(f"Total rounds: {results.total_rounds}")
    print(f"Successful rounds: {results.successful_rounds}")
    print(f"Failed rounds: {results.failed_rounds}")
    print(f"Success rate: {results.success_rate:.1f}%")
    print(f"Auditor accuracy: {results.accuracy:.1f}%")
    print()
    results_path = (
        results.actual_results_dir or Path("results") / "ttl" / experiment_name
    )
    print(f"Results saved to: {results_path}/")

    # Always generate plots
    from src.visualization.ttl_batch_plots import generate_all_plots

    print()
    generate_all_plots(results_path)

    print("=" * 70)


if __name__ == "__main__":
    main()
