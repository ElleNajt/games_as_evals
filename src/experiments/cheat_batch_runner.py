"""Batch runner for Cheat game experiments.

This module provides a convenient interface for running batches of Cheat games
using the unified batch runner framework.
"""

from typing import Any, Dict, Optional
from pathlib import Path

from .batch_runner import BatchRunner
from ..games.cheat.config import CheatConfig
from ..games.cheat.orchestrator import CheatOrchestrator


def run_cheat_game(
    config: CheatConfig,
    round_id: int,
    experiment_name: str,
    **kwargs
) -> Dict[str, Any]:
    """Run a single Cheat game round.
    
    Args:
        config: Cheat game configuration
        round_id: Round number (for logging)
        experiment_name: Name of experiment
        **kwargs: Additional arguments (unused, for compatibility)
        
    Returns:
        Game results dict
    """
    orchestrator = CheatOrchestrator(
        config, 
        experiment_name=experiment_name,
        game_id=round_id  # Pass round_id as game_id for subdirectory organization
    )
    results = orchestrator.run_game()
    return results


def extract_cheat_stats(game_result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key statistics from a Cheat game result.
    
    Args:
        game_result: Full game result from CheatOrchestrator
        
    Returns:
        Dict of key statistics for aggregation (excludes metadata like results_dir)
    """
    stats = {
        'winner': game_result.get('winner'),
        'total_turns': game_result.get('total_turns'),
    }
    
    # Add final card counts for each player
    if 'final_hands' in game_result:
        for player, count in game_result['final_hands'].items():
            stats[f'{player}_final_cards'] = count
    
    # Add challenge statistics if available
    if 'challenge_stats' in game_result:
        challenge_stats = game_result['challenge_stats']
        for player, player_stats in challenge_stats.items():
            stats[f'{player}_total_challenges'] = player_stats.get('total_challenges', 0)
            stats[f'{player}_correct_challenges'] = player_stats.get('correct_challenges', 0)
            
            # Calculate accuracy if they made any challenges
            total = player_stats.get('total_challenges', 0)
            if total > 0:
                correct = player_stats.get('correct_challenges', 0)
                stats[f'{player}_challenge_accuracy'] = (correct / total) * 100
    
    # Note: results_dir is excluded - it's metadata, not a statistic
    return stats


class CheatBatchRunner:
    """Convenience class for running batches of Cheat games."""
    
    def __init__(self, config: CheatConfig):
        """Initialize with a Cheat game configuration.
        
        Args:
            config: CheatConfig instance with player configurations
        """
        self.config = config
        self.batch_runner = BatchRunner(
            game_name='cheat',
            run_game_fn=lambda **kwargs: run_cheat_game(config, **kwargs),
            extract_stats_fn=extract_cheat_stats,
        )
    
    def run(
        self,
        num_rounds: int,
        experiment_name: str,
        save_results: bool = True,
        verbose: bool = True,
    ):
        """Run a batch of Cheat game rounds.
        
        Args:
            num_rounds: Number of rounds to run
            experiment_name: Name for this batch experiment
            save_results: Whether to save results to disk
            verbose: Whether to print progress
            
        Returns:
            BatchResults with aggregated statistics
        """
        return self.batch_runner.run_batch(
            num_rounds=num_rounds,
            experiment_name=experiment_name,
            save_results=save_results,
            verbose=verbose,
        )
