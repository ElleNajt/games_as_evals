"""Batch TTL experiment runner for running multiple game rounds.

This module provides infrastructure to run multiple TTL game rounds
and aggregate results across rounds.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import json
from pathlib import Path

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
            'total_rounds': self.total_rounds,
            'successful_rounds': self.successful_rounds,
            'failed_rounds': self.failed_rounds,
            'auditor_correct_count': self.auditor_correct_count,
            'success_rate': self.success_rate,
            'accuracy': self.accuracy,
            'round_results': self.round_results,
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
        BatchResults with aggregated statistics
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
            
            if round_result.get('auditor_correct', False):
                results.auditor_correct_count += 1
            
            results.round_results.append({
                'round_id': round_num,
                'success': True,
                'auditor_correct': round_result.get('auditor_correct', False),
                'statements': round_result.get('statements', []),
                'lie_index': round_result.get('lie_index'),
                'auditor_guess': round_result.get('auditor_guess'),
            })
            
        except Exception as e:
            results.failed_rounds += 1
            results.round_results.append({
                'round_id': round_num,
                'success': False,
                'error': str(e),
            })
    
    if save_results:
        output_dir = Path('results') / 'ttl' / experiment_name
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results_file = output_dir / 'batch_results.json'
        with open(results_file, 'w') as f:
            json.dump(results.to_dict(), f, indent=2)
    
    return results
