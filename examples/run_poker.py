"""
Example script to run Kuhn Poker games with LLM agents.

This demonstrates how to use the integrated poker game with the games_as_evals backend system.

Usage:
    # Run with Modal backend (8B model with deception probe)
    python examples/run_poker.py --backend modal --model-size 8b --probe deception_8b

    # Run with Claude backend (no probes)
    python examples/run_poker.py --backend claude --model claude-sonnet-4-5

    # Run 5-card variant
    python examples/run_poker.py --backend modal --model-size 8b --n-cards 5 --num-games 50
"""

import argparse
from src.games.poker import PokerConfig, PokerOrchestrator
from src.config.player_config import PlayerConfig


def main():
    parser = argparse.ArgumentParser(description="Run Kuhn Poker with LLM agents")

    # Backend configuration
    parser.add_argument(
        "--backend",
        type=str,
        default="modal",
        choices=["modal", "claude", "openrouter"],
        help="Backend type to use"
    )
    parser.add_argument(
        "--model-size",
        type=str,
        default="8b",
        choices=["8b", "70b"],
        help="Model size for Modal backend (ignored for other backends)"
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Model name (for claude/openrouter backends)"
    )
    parser.add_argument(
        "--probe",
        type=str,
        help="Probe to use (e.g., deception_8b, deception_70b) - only for Modal backend"
    )

    # Game configuration
    parser.add_argument(
        "--n-cards",
        type=int,
        default=3,
        help="Number of cards in the deck (default: 3 for classic Kuhn Poker)"
    )
    parser.add_argument(
        "--num-games",
        type=int,
        default=100,
        help="Number of games to run (default: 100)"
    )
    parser.add_argument(
        "--no-reasoning",
        action="store_true",
        help="Disable chain-of-thought reasoning (faster but less strategic)"
    )
    parser.add_argument(
        "--share-reasoning",
        action="store_true",
        help="Share opponent's reasoning between players (makes game easier)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Random seed for reproducibility"
    )

    # Experiment configuration
    parser.add_argument(
        "--experiment-name",
        type=str,
        default="poker_test",
        help="Experiment name for results logging"
    )

    args = parser.parse_args()

    # Determine model name
    if args.backend == "modal":
        model = args.model_size
    elif args.model:
        model = args.model
    elif args.backend == "claude":
        model = "claude-sonnet-4-5"
    elif args.backend == "openrouter":
        model = "anthropic/claude-3.5-sonnet"
    else:
        model = "default"

    # Determine probes (only for Modal backend)
    probes = None
    if args.backend == "modal" and args.probe:
        probes = [args.probe]

    # Create player configurations
    player_configs = [
        PlayerConfig(
            name="Player_0",
            backend_type=args.backend,
            model=model,
            probes=probes,
            temperature=0.7,
            max_tokens=300 if not args.no_reasoning else 20,
        ),
        PlayerConfig(
            name="Player_1",
            backend_type=args.backend,
            model=model,
            probes=probes,
            temperature=0.7,
            max_tokens=300 if not args.no_reasoning else 20,
        ),
    ]

    # Create poker config
    config = PokerConfig(
        player_configs=player_configs,
        n_cards=args.n_cards,
        num_games=args.num_games,
        seed=args.seed,
        use_reasoning=not args.no_reasoning,
        share_reasoning=args.share_reasoning,
    )

    # Print configuration
    print(f"\n{'='*60}")
    print(f"Kuhn Poker Configuration")
    print(f"{'='*60}")
    print(f"Backend: {args.backend}")
    print(f"Model: {model}")
    if probes:
        print(f"Probes: {probes}")
    print(f"Cards: {args.n_cards}")
    print(f"Games: {args.num_games}")
    print(f"Reasoning: {'enabled' if not args.no_reasoning else 'disabled'}")
    print(f"Share reasoning: {'yes' if args.share_reasoning else 'no'}")
    if args.seed:
        print(f"Seed: {args.seed}")
    print(f"{'='*60}\n")

    # Create orchestrator and run
    orchestrator = PokerOrchestrator(
        config=config,
        experiment_name=args.experiment_name
    )

    results = orchestrator.run_batch()

    print(f"\nResults:")
    print(f"  Player 0: {results['player_0']['wins']} wins ({100*results['player_0']['win_rate']:.1f}%)")
    print(f"  Player 1: {results['player_1']['wins']} wins ({100*results['player_1']['win_rate']:.1f}%)")
    print(f"  Average payoff (Player 0): {results['average_payoff_player_0']:.3f} chips/game")


if __name__ == "__main__":
    main()
