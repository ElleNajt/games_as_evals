"""Unified batch experiment runner for running multiple game rounds.

This module provides a generic infrastructure to run multiple game rounds
and aggregate results across rounds for any game type.
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class BatchResults:
    """Results from a batch of game rounds."""

    game_name: str
    """Name of the game (e.g., 'cheat', 'werewolf', 'ttl')"""

    experiment_name: str
    """Name of this batch experiment"""

    total_rounds: int
    """Total number of rounds attempted"""

    successful_rounds: int = 0
    """Number of rounds that completed successfully"""

    failed_rounds: int = 0
    """Number of rounds that failed"""

    round_results: List[Dict[str, Any]] = field(default_factory=list)
    """Detailed results from each round"""

    aggregated_stats: Dict[str, Any] = field(default_factory=dict)
    """Aggregated statistics across all rounds"""

    @property
    def success_rate(self) -> float:
        """Percentage of rounds that completed successfully."""
        if self.total_rounds == 0:
            return 0.0
        return (self.successful_rounds / self.total_rounds) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "game_name": self.game_name,
            "experiment_name": self.experiment_name,
            "total_rounds": self.total_rounds,
            "successful_rounds": self.successful_rounds,
            "failed_rounds": self.failed_rounds,
            "success_rate": self.success_rate,
            "aggregated_stats": self.aggregated_stats,
            "round_results": self.round_results,
        }

    def save(self, output_dir: Optional[Path] = None):
        """Save results to JSON file.

        Args:
            output_dir: Directory to save to (default: results/{game_name}/{experiment_name})
        """
        if output_dir is None:
            output_dir = Path("results") / self.game_name / self.experiment_name

        output_dir.mkdir(parents=True, exist_ok=True)

        results_file = output_dir / "batch_results.json"
        with open(results_file, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

        print(f"\nBatch results saved to: {results_file}")
        return results_file


class BatchRunner:
    """Generic batch runner for running multiple game rounds.

    Works for any game type - just provide a run_game function and
    optional statistics extraction function.
    """

    def __init__(
        self,
        game_name: str,
        run_game_fn: Callable[..., Dict[str, Any]],
        extract_stats_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    ):
        """Initialize batch runner.

        Args:
            game_name: Name of the game (e.g., 'cheat', 'werewolf', 'ttl')
            run_game_fn: Function to run a single game round
                Should return a dict with game results
            extract_stats_fn: Optional function to extract statistics from game result
                Takes game result dict, returns stats dict
                If None, uses the entire game result as stats
        """
        self.game_name = game_name
        self.run_game_fn = run_game_fn
        self.extract_stats_fn = extract_stats_fn or (lambda x: x)

    def run_batch(
        self,
        num_rounds: int,
        experiment_name: str,
        game_kwargs: Optional[Dict[str, Any]] = None,
        save_results: bool = True,
        verbose: bool = True,
    ) -> BatchResults:
        """Run a batch of game rounds.

        Args:
            num_rounds: Number of rounds to run
            experiment_name: Name for this batch experiment
            game_kwargs: Keyword arguments to pass to run_game_fn
            save_results: Whether to save results to disk
            verbose: Whether to print progress

        Returns:
            BatchResults with aggregated statistics
        """
        game_kwargs = game_kwargs or {}

        results = BatchResults(
            game_name=self.game_name,
            experiment_name=experiment_name,
            total_rounds=num_rounds,
        )

        # Track the actual results directory from the first game
        actual_results_dir = None

        if verbose:
            print(f"\n{'=' * 70}")
            print(f"Running batch experiment: {experiment_name}")
            print(f"Game: {self.game_name}")
            print(f"Rounds: {num_rounds}")
            print(f"{'=' * 70}\n")

        for round_num in range(1, num_rounds + 1):
            if verbose:
                print(f"\n--- Round {round_num}/{num_rounds} ---")

            try:
                # Run the game
                game_result = self.run_game_fn(
                    round_id=round_num, experiment_name=experiment_name, **game_kwargs
                )

                results.successful_rounds += 1

                # Extract the actual results directory from the first successful game
                if actual_results_dir is None and "results_dir" in game_result:
                    # Get parent directory (remove game1/, game2/, etc.)
                    actual_results_dir = Path(game_result["results_dir"]).parent

                # Extract statistics
                stats = self.extract_stats_fn(game_result)

                # Store round result
                results.round_results.append(
                    {
                        "round_id": round_num,
                        "success": True,
                        **stats,
                    }
                )

                if verbose:
                    print(f"Round {round_num} completed successfully")

            except Exception as e:
                results.failed_rounds += 1
                results.round_results.append(
                    {
                        "round_id": round_num,
                        "success": False,
                        "error": str(e),
                    }
                )

                if verbose:
                    print(f"Round {round_num} FAILED: {e}")

        # Aggregate statistics across all successful rounds
        results.aggregated_stats = self._aggregate_stats(results.round_results)

        if verbose:
            self._print_summary(results)

        if save_results:
            # Use actual results directory if available, otherwise fallback to default
            results.save(output_dir=actual_results_dir)

            # Try to generate aggregated probe calibration analysis if available
            try:
                import subprocess

                # Check if analyze_probe_calibration.py exists
                script_path = Path(__file__).parent / "analyze_probe_calibration.py"
                if script_path.exists():
                    # Use actual results directory
                    results_dir = actual_results_dir or (
                        Path("results") / self.game_name / experiment_name
                    )
                    if results_dir.exists():
                        # Run the analysis script
                        subprocess.run(
                            ["python", str(script_path), str(results_dir)],
                            capture_output=True,
                            check=False,
                        )
                        if verbose:
                            print(
                                f"\nProbe calibration analysis generated (if probe data available)"
                            )
            except Exception as e:
                if verbose:
                    print(f"\nNote: Could not generate probe calibration analysis: {e}")

        return results

    def _aggregate_stats(self, round_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate statistics across all rounds.

        Counts occurrences of values for each stat, and computes win rates
        for 'winner' field if present.
        """
        successful_rounds = [r for r in round_results if r.get("success", False)]

        if not successful_rounds:
            return {}

        aggregated = {
            "num_successful_rounds": len(successful_rounds),
        }

        # Collect all stat keys from successful rounds
        stat_keys = set()
        for round_result in successful_rounds:
            stat_keys.update(
                k for k in round_result.keys() if k not in ["round_id", "success"]
            )

        # Count occurrences for each stat
        for key in stat_keys:
            values = [r.get(key) for r in successful_rounds if key in r]

            # For winner field, compute win rates
            if key == "winner":
                winner_counts = defaultdict(int)
                for winner in values:
                    if winner:  # Skip None winners
                        winner_counts[winner] += 1

                aggregated["winner_counts"] = dict(winner_counts)
                aggregated["win_rates"] = {
                    player: (count / len(successful_rounds)) * 100
                    for player, count in winner_counts.items()
                }

            # For numeric values, compute mean
            elif all(isinstance(v, (int, float)) for v in values if v is not None):
                numeric_values = [v for v in values if v is not None]
                if numeric_values:
                    aggregated[f"{key}_mean"] = sum(numeric_values) / len(
                        numeric_values
                    )

            # For categorical values, count occurrences
            else:
                value_counts = defaultdict(int)
                for value in values:
                    if value is not None:
                        value_counts[str(value)] += 1
                aggregated[f"{key}_counts"] = dict(value_counts)

        return aggregated

    def _print_summary(self, results: BatchResults):
        """Print a summary of batch results."""
        print(f"\n{'=' * 70}")
        print("BATCH RESULTS SUMMARY")
        print(f"{'=' * 70}")
        print(f"Total rounds: {results.total_rounds}")
        print(f"Successful: {results.successful_rounds}")
        print(f"Failed: {results.failed_rounds}")
        print(f"Success rate: {results.success_rate:.1f}%")

        if results.aggregated_stats:
            print(f"\nAGGREGATED STATISTICS:")

            # Print winner stats if available
            if "win_rates" in results.aggregated_stats:
                print(f"\nWin rates:")
                for player, rate in sorted(
                    results.aggregated_stats["win_rates"].items(),
                    key=lambda x: x[1],
                    reverse=True,
                ):
                    count = results.aggregated_stats["winner_counts"][player]
                    print(
                        f"  {player}: {rate:.1f}% ({count}/{results.successful_rounds} wins)"
                    )

            # Print other aggregated stats
            for key, value in results.aggregated_stats.items():
                if key not in ["num_successful_rounds", "winner_counts", "win_rates"]:
                    if isinstance(value, dict):
                        print(f"\n{key}:")
                        for k, v in value.items():
                            print(f"  {k}: {v}")
                    else:
                        print(f"  {key}: {value}")

        print(f"{'=' * 70}\n")
