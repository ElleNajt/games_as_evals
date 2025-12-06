"""Batch TTL experiment runner for running multiple game rounds."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.games.ttl import TTLConfig
from src.games.ttl.orchestrator_unified import run_game_round


@dataclass
class BatchResults:
    """Results from a batch of TTL game rounds."""

    total_rounds: int
    successful_rounds: int
    failed_rounds: int
    auditor_correct_count: int
    round_results: List[Dict[str, Any]] = field(default_factory=list)
    actual_results_dir: Optional[Path] = None

    @property
    def success_rate(self) -> float:
        """Percentage of rounds that completed successfully."""
        if self.total_rounds == 0:
            return 0.0
        return (self.successful_rounds / self.total_rounds) * 100

    @property
    def accuracy(self) -> float:
        """Percentage of rounds where auditor guessed correctly."""
        if self.successful_rounds == 0:
            return 0.0
        return (self.auditor_correct_count / self.successful_rounds) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_rounds": self.total_rounds,
            "successful_rounds": self.successful_rounds,
            "failed_rounds": self.failed_rounds,
            "auditor_correct_count": self.auditor_correct_count,
            "success_rate": self.success_rate,
            "accuracy": self.accuracy,
            "round_results": self.round_results,
        }


def run_batch_experiment(
    config: TTLConfig,
    num_rounds: int,
    experiment_name: str,
    facts: Optional[List[str]] = None,
    save_results: bool = True,
) -> BatchResults:
    """Run a batch of TTL game rounds.

    Args:
        config: TTL game configuration with player configs
        num_rounds: Number of rounds to run
        experiment_name: Name for this batch experiment
        facts: Optional list of facts to use (None = generate random)
        save_results: Whether to save results to disk

    Returns:
        BatchResults with aggregated statistics and actual_results_dir
    """
    results = BatchResults(
        total_rounds=num_rounds,
        successful_rounds=0,
        failed_rounds=0,
        auditor_correct_count=0,
    )

    for round_num in range(1, num_rounds + 1):
        try:
            round_result = run_game_round(
                config=config,
                facts=facts,
                experiment_name=experiment_name,
                round_id=round_num,
            )

            results.successful_rounds += 1

            # Track actual results directory from first successful game
            if results.actual_results_dir is None and "results_dir" in round_result:
                # Get parent directory (removes /game1, /game2, etc.)
                results.actual_results_dir = Path(round_result["results_dir"]).parent

            if round_result.get("auditor_correct", False):
                results.auditor_correct_count += 1

            # Extract lie_index and auditor_guess from the round_result
            revealed_lie = round_result.get("revealed_lie")
            auditor_with_probe = round_result.get("auditor_guesses", {}).get(
                "with_probe", {}
            )

            # Extract probe scores
            probe_scores = round_result.get("deceiver_generation", {}).get(
                "probe_scores", {}
            )

            results.round_results.append(
                {
                    "round_id": round_num,
                    "success": True,
                    "auditor_correct": round_result.get("auditor_correct", False),
                    "statements": round_result.get("statements", []),
                    "lie_index": revealed_lie,
                    "auditor_guess": auditor_with_probe.get("original_guess"),
                    "probe_scores": probe_scores,
                }
            )

        except Exception as e:
            results.failed_rounds += 1
            results.round_results.append(
                {
                    "round_id": round_num,
                    "success": False,
                    "error": str(e),
                }
            )

    if save_results and results.actual_results_dir:
        # Save to the actual results directory with git hash
        output_dir = results.actual_results_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        results_file = output_dir / "batch_results.json"
        with open(results_file, "w") as f:
            json.dump(results.to_dict(), f, indent=2)

    return results
