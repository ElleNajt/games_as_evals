"""Batch runner for Werewolf game experiments."""

from pathlib import Path
from typing import Any, Dict

from src.experiments.batch_runner import BatchRunner
from src.games.werewolf import WerewolfConfig
from src.games.werewolf.game_coordinator import GameCoordinator


def run_werewolf_game(
    config: WerewolfConfig, round_id: int, experiment_name: str, **kwargs
) -> Dict[str, Any]:
    """Run a single werewolf game.

    Args:
        config: Werewolf game configuration
        round_id: Round number for this game
        experiment_name: Name of the experiment
        **kwargs: Additional arguments (ignored)

    Returns:
        Dict containing game results
    """
    coordinator = GameCoordinator(
        config=config, experiment_name=experiment_name, game_id=round_id
    )

    winner = coordinator.run_game()

    # Return results in format expected by batch runner
    return {
        "success": True,
        "winner": winner,
        "turns": coordinator.game.turn_number,
        "results_dir": str(coordinator.logger.results_dir)
        if coordinator.logger
        else None,
    }


def extract_werewolf_stats(game_result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract statistics from a werewolf game result.

    Args:
        game_result: Result dict from run_werewolf_game()

    Returns:
        Dict of statistics to aggregate
    """
    return {
        "winner": game_result.get("winner"),
        "turns": game_result.get("turns", 0),
    }


def run_batch_experiment(
    config: WerewolfConfig,
    num_rounds: int,
    experiment_name: str = "werewolf_batch",
    save_results: bool = True,
    verbose: bool = True,
):
    """Run a batch of werewolf games.

    Args:
        config: Werewolf game configuration
        num_rounds: Number of games to run
        experiment_name: Name for this experiment
        save_results: Whether to save batch results to disk
        verbose: Whether to print progress

    Returns:
        BatchResults object with aggregate statistics
    """
    runner = BatchRunner(
        game_name="werewolf",
        run_game_fn=run_werewolf_game,
        extract_stats_fn=extract_werewolf_stats,
    )

    return runner.run_batch(
        config=config,
        num_rounds=num_rounds,
        experiment_name=experiment_name,
        save_results=save_results,
        verbose=verbose,
    )
